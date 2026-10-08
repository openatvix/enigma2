#include <lib/base/cfile.h>
#include <lib/base/ebase.h>
#include <lib/base/eerror.h>
#include <lib/base/wrappers.h>
#include <lib/dvb/decoder.h>
#include <lib/components/tuxtxtapp.h>
#include <lib/python/pythonconfig.h>
#include <linux/dvb/audio.h>
#include <linux/dvb/video.h>
#include <linux/dvb/dmx.h>

#include <unistd.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <errno.h>

#include <lib/dvb/fccdecoder.h>

#ifndef VIDEO_SOURCE_HDMI
#define VIDEO_SOURCE_HDMI 2
#endif
#ifndef AUDIO_SOURCE_HDMI
#define AUDIO_SOURCE_HDMI 2
#endif
#ifndef AUDIO_GET_PTS
#define AUDIO_GET_PTS _IOR('o', 19, __u64)
#endif
#ifndef VIDEO_GET_FRAME_RATE
#define VIDEO_GET_FRAME_RATE _IOR('o', 56, unsigned int)
#endif

DEFINE_REF(eDVBAudio);

eDVBAudio::eDVBAudio(eDVBDemux *demux, int dev)
	:m_demux(demux), m_dev(dev)
{
	char filename[128] = {};
	sprintf(filename, "/dev/dvb/adapter%d/audio%d", demux ? demux->adapter : 0, dev);
	m_fd = ::open(filename, O_RDWR | O_CLOEXEC);
	if (m_fd < 0)
		eWarning("[eDVBAudio] %s: %m", filename);
	if (demux)
	{
		sprintf(filename, "/dev/dvb/adapter%d/demux%d", demux->adapter, demux->demux);
		m_fd_demux = ::open(filename, O_RDWR | O_CLOEXEC);
		if (m_fd_demux < 0)
			eWarning("[eDVBAudio] %s: %m", filename);
	}
	else
	{
		m_fd_demux = -1;
	}

#ifndef DREAMBOX
	if (m_fd >= 0)
	{
		::ioctl(m_fd, AUDIO_SELECT_SOURCE, demux ? AUDIO_SOURCE_DEMUX : AUDIO_SOURCE_HDMI);
	}
#endif
}

int eDVBAudio::startPid(int pid, int type)
{
	if (m_fd_demux >= 0)
	{
		dmx_pes_filter_params pes = {};

		pes.pid      = pid;
		pes.input    = DMX_IN_FRONTEND;
		pes.output   = DMX_OUT_DECODER;
		switch (m_dev)
		{
		case 0:
			pes.pes_type = DMX_PES_AUDIO0;
			break;
		case 1:
			pes.pes_type = DMX_PES_AUDIO1;
			break;
		case 2:
			pes.pes_type = DMX_PES_AUDIO2;
			break;
		case 3:
			pes.pes_type = DMX_PES_AUDIO3;
			break;
		}
		pes.flags    = 0;
		eDebugNoNewLineStart("[eDVBAudio%d] DMX_SET_PES_FILTER pid=0x%04x ", m_dev, pid);
		if (::ioctl(m_fd_demux, DMX_SET_PES_FILTER, &pes) < 0)
		{
			eDebugNoNewLine("failed: %m\n");
			return -errno;
		}
		eDebugNoNewLine("ok\n");
		eDebugNoNewLineStart("[eDVBAudio%d] DEMUX_START ", m_dev);
		if (::ioctl(m_fd_demux, DMX_START) < 0)
		{
			eDebugNoNewLine("failed: %m\n");
			return -errno;
		}
		eDebugNoNewLine("ok\n");
	}

	if (m_fd >= 0)
	{
		int bypass = 0;

		switch (type)
		{
		case aMPEG:
			bypass = 1;
			break;
		case aAC3:
		case aAC4: /* FIXME: AC4 most probably will use other bypass value */
			bypass = 0;
			break;
		case aDTS:
			bypass = 2;
			break;
		case aAAC:
			bypass = 8;
			break;
		case aAACHE:
			bypass = 9;
			break;
		case aLPCM:
			bypass = 6;
			break;
		case aDTSHD:
			bypass = 0x10;
			break;
		case aDRA:
			bypass = 0x40;
			break;
		case aDDP:
#ifdef DREAMBOX
		bypass = 7;
#else
		bypass = 0x22;
#endif
		break;
		}

		eDebugNoNewLineStart("[eDVBAudio%d] AUDIO_SET_BYPASS bypass=%d ", m_dev, bypass);
		if (::ioctl(m_fd, AUDIO_SET_BYPASS_MODE, bypass) < 0)
			eDebugNoNewLine("failed: %m\n");
		else
			eDebugNoNewLine("ok\n");

		/* Do NOT freeze here. Freezing/unfreezing is controlled exclusively
		 * by eTSMPEGDecoder::setState() via the state machine. Freezing inside
		 * startPid caused black screens on PID-only changes because the
		 * unfreeze logic in setState() was not always triggered. */
		eDebugNoNewLineStart("[eDVBAudio%d] AUDIO_PLAY ", m_dev);
		if (::ioctl(m_fd, AUDIO_PLAY) < 0)
			eDebugNoNewLine("failed: %m\n");
		else
			eDebugNoNewLine("ok\n");
	}
	return 0;
}

void eDVBAudio::stop()
{
	if (m_fd >= 0)
	{
		eDebugNoNewLineStart("[eDVBAudio%d] AUDIO_STOP ", m_dev);
		if (::ioctl(m_fd, AUDIO_STOP) < 0)
			eDebugNoNewLine("failed: %m\n");
		else
			eDebugNoNewLine("ok\n");
	}
	if (m_fd_demux >= 0)
	{
		eDebugNoNewLineStart("[eDVBAudio%d] DEMUX_STOP ", m_dev);
		if (::ioctl(m_fd_demux, DMX_STOP) < 0)
			eDebugNoNewLine("failed: %m\n");
		else
			eDebugNoNewLine("ok\n");
	}
}

void eDVBAudio::flush()
{
	if (m_fd >= 0)
	{
		eDebugNoNewLineStart("[eDVBAudio%d] AUDIO_CLEAR_BUFFER ", m_dev);
		if (::ioctl(m_fd, AUDIO_CLEAR_BUFFER) < 0)
			eDebugNoNewLine("failed: %m\n");
		else
			eDebugNoNewLine("ok\n");
	}
}

void eDVBAudio::freeze()
{
	if (m_fd >= 0)
	{
		eDebugNoNewLineStart("[eDVBAudio%d] AUDIO_PAUSE ", m_dev);
		if (::ioctl(m_fd, AUDIO_PAUSE) < 0)
			eDebugNoNewLine("failed: %m\n");
		else
			eDebugNoNewLine("ok\n");
	}
}

void eDVBAudio::unfreeze()
{
	if (m_fd >= 0)
	{
		eDebugNoNewLineStart("[eDVBAudio%d] AUDIO_CONTINUE ", m_dev);
		if (::ioctl(m_fd, AUDIO_CONTINUE) < 0)
			eDebugNoNewLine("failed: %m\n");
		else
			eDebugNoNewLine("ok\n");
	}
}

void eDVBAudio::setChannel(int channel)
{
	if (m_fd >= 0)
	{
		int val = AUDIO_STEREO;
		switch (channel)
		{
		case aMonoLeft: val = AUDIO_MONO_LEFT; break;
		case aMonoRight: val = AUDIO_MONO_RIGHT; break;
		default: break;
		}
		eDebugNoNewLineStart("[eDVBAudio%d] AUDIO_CHANNEL_SELECT %d ", m_dev, val);
		if (::ioctl(m_fd, AUDIO_CHANNEL_SELECT, val) < 0)
			eDebugNoNewLine("failed: %m\n");
		else
			eDebugNoNewLine("ok\n");
	}
}

int eDVBAudio::getPTS(pts_t &now)
{
	if (m_fd >= 0)
	{
		if (::ioctl(m_fd, AUDIO_GET_PTS, &now) < 0)
			eDebug("[eDVBAudio%d] AUDIO_GET_PTS failed: %m", m_dev);
	}
	return 0;
}

eDVBAudio::~eDVBAudio()
{
	unfreeze();
	if (m_fd >= 0)
		::close(m_fd);
	if (m_fd_demux >= 0)
		::close(m_fd_demux);
	eDebug("[eDVBAudio%d] destroy", m_dev);
}

DEFINE_REF(eDVBVideo);

int eDVBVideo::m_close_invalidates_attributes = -1;

eDVBVideo::eDVBVideo(eDVBDemux *demux, int dev, bool fcc_enable)
	: m_demux(demux), m_dev(dev), m_fcc_enable(fcc_enable),
	m_hold_on_zap(false),
	m_width(-1), m_height(-1), m_framerate(-1), m_aspect(-1), m_progressive(-1), m_gamma(-1)
{
	char filename[128] = {};
	sprintf(filename, "/dev/dvb/adapter%d/video%d", demux ? demux->adapter : 0, dev);
	m_fd = ::open(filename, O_RDWR | O_CLOEXEC);
	if (m_fd < 0)
		eWarning("[eDVBVideo] %s: %m", filename);
	else
	{
		eDebug("[eDVBVideo] Video Device: %s", filename);
		m_sn = eSocketNotifier::create(eApp, m_fd, eSocketNotifier::Priority);
		CONNECT(m_sn->activated, eDVBVideo::video_event);
	}
	if (demux)
	{
		sprintf(filename, "/dev/dvb/adapter%d/demux%d", demux->adapter, demux->demux);
		m_fd_demux = ::open(filename, O_RDWR | O_CLOEXEC);
		if (m_fd_demux < 0)
			eWarning("[eDVBVideo] %s: %m", filename);
		else
			eDebug("[eDVBVideo] demux device: %s", filename);
	}
	else
	{
		m_fd_demux = -1;
	}

	/* Always force the video source to the demuxer for live TV. The
	 * zapmodeDM "hold" logic is about VIDEO_STOP flag and fd lifetime,
	 * not about VIDEO_SELECT_SOURCE. Doing this unconditionally removes
	 * the black-screen regression caused by a lingering VIDEO_SOURCE_MEMORY
	 * (from showSinglePic or a failed previous zap). */
#ifndef DREAMBOX
	if (m_fd >= 0)
	{
		::ioctl(m_fd, VIDEO_SELECT_SOURCE, demux ? VIDEO_SOURCE_DEMUX : VIDEO_SOURCE_HDMI);
	}
#endif

	/* Attribute invalidation detection. Independent of zap mode. */
	if (m_close_invalidates_attributes < 0)
	{
		readApiSize(m_fd, m_width, m_height, m_aspect);
		m_close_invalidates_attributes = (m_width == -1) ? 1 : 0;
	}
}

// not finally values i think.. !!
#define VIDEO_STREAMTYPE_MPEG2 0
#define VIDEO_STREAMTYPE_MPEG4_H264 1
#define VIDEO_STREAMTYPE_VC1 3
#define VIDEO_STREAMTYPE_MPEG4_Part2 4
#define VIDEO_STREAMTYPE_VC1_SM 5
#define VIDEO_STREAMTYPE_MPEG1 6
#ifdef DREAMBOX
#define VIDEO_STREAMTYPE_H265_HEVC 22
#else
#define VIDEO_STREAMTYPE_H265_HEVC 7
#endif
#define VIDEO_STREAMTYPE_AVS 16
#define VIDEO_STREAMTYPE_AVS2 40

static int videoStreamTypeFor(int type)
{
	switch (type)
	{
	default:
	case eDVBVideo::MPEG2:
		return VIDEO_STREAMTYPE_MPEG2;
	case eDVBVideo::MPEG4_H264:
		return VIDEO_STREAMTYPE_MPEG4_H264;
	case eDVBVideo::MPEG1:
		return VIDEO_STREAMTYPE_MPEG1;
	case eDVBVideo::MPEG4_Part2:
		return VIDEO_STREAMTYPE_MPEG4_Part2;
	case eDVBVideo::VC1:
		return VIDEO_STREAMTYPE_VC1;
	case eDVBVideo::VC1_SM:
		return VIDEO_STREAMTYPE_VC1_SM;
	case eDVBVideo::H265_HEVC:
		return VIDEO_STREAMTYPE_H265_HEVC;
	case eDVBVideo::AVS:
		return VIDEO_STREAMTYPE_AVS;
	case eDVBVideo::AVS2:
		return VIDEO_STREAMTYPE_AVS2;
	}
}

int eDVBVideo::startPid(int pid, int type)
{
	if (m_fcc_enable)
		return 0;

	if (m_fd >= 0)
	{
		int streamtype = videoStreamTypeFor(type);

		eDebugNoNewLineStart("[eDVBVideo%d] VIDEO_SET_STREAMTYPE %d - ", m_dev, streamtype);
		if (::ioctl(m_fd, VIDEO_SET_STREAMTYPE, streamtype) < 0)
			eDebugNoNewLine("failed: %m\n");
		else
			eDebugNoNewLine("ok\n");
	}

	if (m_fd_demux >= 0)
	{
		dmx_pes_filter_params pes = {};
		pes.pid      = pid;
		pes.input    = DMX_IN_FRONTEND;
		pes.output   = DMX_OUT_DECODER;
		switch (m_dev)
		{
		case 0:
			pes.pes_type = DMX_PES_VIDEO0;
			break;
		case 1:
			pes.pes_type = DMX_PES_VIDEO1;
			break;
		case 2:
			pes.pes_type = DMX_PES_VIDEO2;
			break;
		case 3:
			pes.pes_type = DMX_PES_VIDEO3;
			break;
		}
		pes.flags    = 0;
		eDebugNoNewLineStart("[eDVBVideo%d] DMX_SET_PES_FILTER pid=0x%04x ", m_dev, pid);
		if (::ioctl(m_fd_demux, DMX_SET_PES_FILTER, &pes) < 0)
		{
			eDebugNoNewLine("failed: %m\n");
			return -errno;
		}
		eDebugNoNewLine("ok\n");
		eDebugNoNewLineStart("[eDVBVideo%d] DEMUX_START ", m_dev);
		if (::ioctl(m_fd_demux, DMX_START) < 0)
		{
			eDebugNoNewLine("failed: %m\n");
			return -errno;
		}
		eDebugNoNewLine("ok\n");
	}

	if (m_fd >= 0)
	{
		/* Freezing is now handled exclusively by eTSMPEGDecoder::setState()
		 * via the state table. Do not freeze here. */
		eDebugNoNewLineStart("[eDVBVideo%d] VIDEO_PLAY ", m_dev);
		if (::ioctl(m_fd, VIDEO_PLAY) < 0)
			eDebugNoNewLine("failed: %m\n");
		else
			eDebugNoNewLine("ok\n");
	}
	return 0;
}

/* Reuse the already-open video fd for a new PID. This does not close the
 * device, so the driver's last displayed frame is preserved in "hold" mode.
 * Used on PID-only changes when we already have an m_video instance. */
int eDVBVideo::changePid(int pid, int type)
{
	if (m_fcc_enable)
		return 0;

	if (m_fd >= 0)
	{
		int streamtype = videoStreamTypeFor(type);

		eDebugNoNewLineStart("[eDVBVideo%d] VIDEO_SET_STREAMTYPE %d - ", m_dev, streamtype);
		if (::ioctl(m_fd, VIDEO_SET_STREAMTYPE, streamtype) < 0)
			eDebugNoNewLine("failed: %m\n");
		else
			eDebugNoNewLine("ok\n");
	}

	if (m_fd_demux >= 0)
	{
		dmx_pes_filter_params pes = {};
		pes.pid      = pid;
		pes.input    = DMX_IN_FRONTEND;
		pes.output   = DMX_OUT_DECODER;
		switch (m_dev)
		{
		case 0: pes.pes_type = DMX_PES_VIDEO0; break;
		case 1: pes.pes_type = DMX_PES_VIDEO1; break;
		case 2: pes.pes_type = DMX_PES_VIDEO2; break;
		case 3: pes.pes_type = DMX_PES_VIDEO3; break;
		}
		pes.flags = 0;

		eDebugNoNewLineStart("[eDVBVideo%d] DMX_SET_PES_FILTER pid=0x%04x ", m_dev, pid);
		if (::ioctl(m_fd_demux, DMX_SET_PES_FILTER, &pes) < 0)
		{
			eDebugNoNewLine("failed: %m\n");
			return -errno;
		}
		eDebugNoNewLine("ok\n");
		eDebugNoNewLineStart("[eDVBVideo%d] DEMUX_START ", m_dev);
		if (::ioctl(m_fd_demux, DMX_START) < 0)
		{
			eDebugNoNewLine("failed: %m\n");
			return -errno;
		}
		eDebugNoNewLine("ok\n");
	}

	if (m_fd >= 0)
	{
		eDebugNoNewLineStart("[eDVBVideo%d] VIDEO_PLAY ", m_dev);
		if (::ioctl(m_fd, VIDEO_PLAY) < 0)
			eDebugNoNewLine("failed: %m\n");
		else
			eDebugNoNewLine("ok\n");
	}
	return 0;
}

void eDVBVideo::stop()
{
	stop(1); /* default: freeze last frame (hold) */
}

void eDVBVideo::stop(int freeze_last_frame)
{
	if (m_fcc_enable)
		return;

	if (m_fd_demux >= 0)
	{
		eDebugNoNewLineStart("[eDVBVideo%d] DEMUX_STOP  ", m_dev);
		if (::ioctl(m_fd_demux, DMX_STOP) < 0)
			eDebugNoNewLine("failed: %m\n");
		else
			eDebugNoNewLine("ok\n");
	}

	if (m_fd >= 0)
	{
		eDebugNoNewLineStart("[eDVBVideo%d] VIDEO_STOP %d ", m_dev, freeze_last_frame);
		if (::ioctl(m_fd, VIDEO_STOP, freeze_last_frame) < 0)
			eDebugNoNewLine("failed: %m\n");
		else
			eDebugNoNewLine("ok\n");
	}
}

void eDVBVideo::flush()
{
	if (m_fd >= 0)
	{
		eDebugNoNewLineStart("[eDVBVideo%d] VIDEO_CLEAR_BUFFER ", m_dev);
		if (::ioctl(m_fd, VIDEO_CLEAR_BUFFER) < 0)
			eDebugNoNewLine("failed: %m\n");
		else
			eDebugNoNewLine("ok\n");
	}
}

void eDVBVideo::freeze()
{
	if (m_fd >= 0)
	{
		eDebugNoNewLineStart("[eDVBVideo%d] VIDEO_FREEZE ", m_dev);
		if (::ioctl(m_fd, VIDEO_FREEZE) < 0)
			eDebugNoNewLine("failed: %m\n");
		else
			eDebugNoNewLine("ok\n");
	}
}

void eDVBVideo::unfreeze()
{
	if (m_fd >= 0)
	{
		eDebugNoNewLineStart("[eDVBVideo%d] VIDEO_CONTINUE ", m_dev);
		if (::ioctl(m_fd, VIDEO_CONTINUE) < 0)
			eDebugNoNewLine("failed: %m\n");
		else
			eDebugNoNewLine("ok\n");
	}
}

int eDVBVideo::setSlowMotion(int repeat)
{
	if (m_fd >= 0)
	{
		eDebugNoNewLineStart("[eDVBVideo%d] VIDEO_SLOWMOTION %d ", m_dev, repeat);
		int ret = ::ioctl(m_fd, VIDEO_SLOWMOTION, repeat);
		if (ret < 0)
			eDebugNoNewLine("failed: %m\n");
		else
			eDebugNoNewLine("ok\n");
		return ret;
	}
	return 0;
}

int eDVBVideo::setFastForward(int skip)
{
	if (m_fd >= 0)
	{
		eDebugNoNewLineStart("[eDVBVideo%d] VIDEO_FAST_FORWARD %d ", m_dev, skip);
		int ret = ::ioctl(m_fd, VIDEO_FAST_FORWARD, skip);
		if (ret < 0)
			eDebugNoNewLine("failed: %m\n");
		else
			eDebugNoNewLine("ok\n");
		return ret;
	}
	return 0;
}

int eDVBVideo::getPTS(pts_t &now)
{
	if (m_fd >= 0)
	{
		int ret = ::ioctl(m_fd, VIDEO_GET_PTS, &now);
		if (ret < 0)
			eDebug("[eDVBVideo%d] VIDEO_GET_PTS failed: %m", m_dev);
		return ret;
	}
	return 0;
}

eDVBVideo::~eDVBVideo()
{
	if (m_fd >= 0)
		::close(m_fd);
	if (m_fd_demux >= 0)
		::close(m_fd_demux);
	eDebug("[eDVBVideo%d] destroy", m_dev);
}

void eDVBVideo::video_event(int)
{
	while (m_fd >= 0)
	{
		int retval;
		pollfd pfd[1] = {};
		pfd[0].fd = m_fd;
		pfd[0].events = POLLPRI;
		retval = ::poll(pfd, 1, 0);
		if (retval < 0 && errno == EINTR) continue;
		if (retval <= 0) break;
		struct video_event evt = {};
		eDebugNoNewLineStart("[eDVBVideo%d] VIDEO_GET_EVENT ", m_dev);
		if (::ioctl(m_fd, VIDEO_GET_EVENT, &evt) < 0)
		{
			eDebugNoNewLine("failed: %m\n");
			break;
		}
		else
		{
			if (evt.type == VIDEO_EVENT_SIZE_CHANGED)
			{
				struct iTSMPEGDecoder::videoEvent event = {};
				event.type = iTSMPEGDecoder::videoEvent::eventSizeChanged;
				m_aspect = event.aspect = evt.u.size.aspect_ratio == 0 ? 2 : 3;
				m_height = event.height = evt.u.size.h;
				m_width = event.width = evt.u.size.w;
				eDebugNoNewLine("SIZE_CHANGED %dx%d aspect %d\n", m_width, m_height, m_aspect);
				m_event(event);
			}
			else if (evt.type == VIDEO_EVENT_FRAME_RATE_CHANGED)
			{
				struct iTSMPEGDecoder::videoEvent event = {};
				event.type = iTSMPEGDecoder::videoEvent::eventFrameRateChanged;
				m_framerate = event.framerate = evt.u.frame_rate;
				eDebugNoNewLine("FRAME_RATE_CHANGED %d fps\n", m_framerate);
				m_event(event);
			}
			else if (evt.type == 16 /*VIDEO_EVENT_PROGRESSIVE_CHANGED*/)
			{
				struct iTSMPEGDecoder::videoEvent event = {};
				event.type = iTSMPEGDecoder::videoEvent::eventProgressiveChanged;
				m_progressive = event.progressive = evt.u.frame_rate;
				eDebugNoNewLine("PROGRESSIVE_CHANGED %d\n", m_progressive);
				m_event(event);
			}
			else if (evt.type == 17 /*VIDEO_EVENT_GAMMA_CHANGED*/)
			{
				struct iTSMPEGDecoder::videoEvent event = {};
				event.type = iTSMPEGDecoder::videoEvent::eventGammaChanged;
				m_gamma = event.gamma = evt.u.frame_rate;
				eDebugNoNewLine("GAMMA_CHANGED %d\n", m_gamma);
				m_event(event);
			}
			else
				eDebugNoNewLine("unhandled DVBAPI Video Event %d\n", evt.type);
		}
	}
}

RESULT eDVBVideo::connectEvent(const sigc::slot<void(struct iTSMPEGDecoder::videoEvent)> &event, ePtr<eConnection> &conn)
{
	conn = new eConnection(this, m_event.connect(event));
	return 0;
}

int eDVBVideo::readApiSize(int fd, int &xres, int &yres, int &aspect)
{
	video_size_t size = {};
	if (!::ioctl(fd, VIDEO_GET_SIZE, &size))
	{
		xres = size.w;
		yres = size.h;
		aspect = size.aspect_ratio == 0 ? 2 : 3;
		return 0;
	}
	return -1;
}

int eDVBVideo::getWidth()
{
	if (!m_close_invalidates_attributes)
	{
		if (m_width == -1)
			readApiSize(m_fd, m_width, m_height, m_aspect);
	}
	return m_width;
}

int eDVBVideo::getHeight()
{
	if (!m_close_invalidates_attributes)
	{
		if (m_height == -1)
			readApiSize(m_fd, m_width, m_height, m_aspect);
	}
	return m_height;
}

int eDVBVideo::getAspect()
{
	if (!m_close_invalidates_attributes)
	{
		if (m_aspect == -1)
			readApiSize(m_fd, m_width, m_height, m_aspect);
	}
	return m_aspect;
}

int eDVBVideo::getProgressive()
{
	if (!m_close_invalidates_attributes)
	{
		if (m_progressive == -1)
		{
			char tmp[64] = {};
			sprintf(tmp, "/proc/stb/vmpeg/%d/progressive", m_dev);
			CFile::parseIntHex(&m_progressive, tmp);
		}
	}
	return m_progressive;
}

int eDVBVideo::getFrameRate()
{
	if (!m_close_invalidates_attributes)
	{
		if (m_framerate == -1)
		{
			if (m_fd >= 0)
			{
				::ioctl(m_fd, VIDEO_GET_FRAME_RATE, &m_framerate);
			}
		}
	}
	return m_framerate;
}

int eDVBVideo::getGamma()
{
	if (!m_close_invalidates_attributes)
	{
		if (m_gamma == -1)
		{
			char tmp[64] = {};
			sprintf(tmp, "/proc/stb/vmpeg/%d/gamma", m_dev);
			CFile::parseIntHex(&m_gamma, tmp);
		}
	}
	return m_gamma;
}

DEFINE_REF(eDVBPCR);

eDVBPCR::eDVBPCR(eDVBDemux *demux, int dev): m_demux(demux), m_dev(dev)
{
	char filename[128] = {};
	sprintf(filename, "/dev/dvb/adapter%d/demux%d", demux->adapter, demux->demux);
	m_fd_demux = ::open(filename, O_RDWR | O_CLOEXEC);
	if (m_fd_demux < 0)
		eWarning("[eDVBPCR] %s: %m", filename);
}

int eDVBPCR::startPid(int pid)
{
	if (m_fd_demux < 0)
		return -1;
	dmx_pes_filter_params pes = {};

	pes.pid      = pid;
	pes.input    = DMX_IN_FRONTEND;
	pes.output   = DMX_OUT_DECODER;
	switch (m_dev)
	{
	case 0: pes.pes_type = DMX_PES_PCR0; break;
	case 1: pes.pes_type = DMX_PES_PCR1; break;
	case 2: pes.pes_type = DMX_PES_PCR2; break;
	case 3: pes.pes_type = DMX_PES_PCR3; break;
	}
	pes.flags    = 0;
	eDebugNoNewLineStart("[eDVBPCR%d] DMX_SET_PES_FILTER pid=0x%04x ", m_dev, pid);
	if (::ioctl(m_fd_demux, DMX_SET_PES_FILTER, &pes) < 0)
	{
		eDebugNoNewLine("failed: %m\n");
		return -errno;
	}
	eDebugNoNewLine("ok\n");
	eDebugNoNewLineStart("[eDVBPCR%d] DEMUX_START ", m_dev);
	if (::ioctl(m_fd_demux, DMX_START) < 0)
	{
		eDebugNoNewLine("failed: %m\n");
		return -errno;
	}
	eDebugNoNewLine("ok\n");
	return 0;
}

void eDVBPCR::stop()
{
	eDebugNoNewLineStart("[eDVBPCR%d] DEMUX_STOP ", m_dev);
	if (::ioctl(m_fd_demux, DMX_STOP) < 0)
		eDebugNoNewLine("failed: %m\n");
	else
		eDebugNoNewLine("ok\n");
}

eDVBPCR::~eDVBPCR()
{
	if (m_fd_demux >= 0)
		::close(m_fd_demux);
	eDebug("[eDVBPCR%d] destroy", m_dev);
}

DEFINE_REF(eDVBTText);

eDVBTText::eDVBTText(eDVBDemux *demux, int dev)
    :m_demux(demux), m_dev(dev)
{
	char filename[128] = {};
	sprintf(filename, "/dev/dvb/adapter%d/demux%d", demux->adapter, demux->demux);
	m_fd_demux = ::open(filename, O_RDWR | O_CLOEXEC);
	if (m_fd_demux < 0)
		eWarning("[eDVBText] %s: %m", filename);
}

int eDVBTText::startPid(int pid)
{
	if (m_fd_demux < 0)
		return -1;
	dmx_pes_filter_params pes = {};

	pes.pid      = pid;
	pes.input    = DMX_IN_FRONTEND;
	pes.output   = DMX_OUT_DECODER;
	switch (m_dev)
	{
	case 0: pes.pes_type = DMX_PES_TELETEXT0; break;
	case 1: pes.pes_type = DMX_PES_TELETEXT1; break;
	case 2: pes.pes_type = DMX_PES_TELETEXT2; break;
	case 3: pes.pes_type = DMX_PES_TELETEXT3; break;
	}
	pes.flags    = 0;

	eDebugNoNewLineStart("[eDVBText%d] DMX_SET_PES_FILTER pid=0x%04x ", m_dev, pid);
	if (::ioctl(m_fd_demux, DMX_SET_PES_FILTER, &pes) < 0)
	{
		eDebugNoNewLine("failed: %m\n");
		return -errno;
	}
	eDebugNoNewLine("ok\n");
	eDebugNoNewLineStart("[eDVBText%d] DEMUX_START ", m_dev);
	if (::ioctl(m_fd_demux, DMX_START) < 0)
	{
		eDebugNoNewLine("failed: %m\n");
		return -errno;
	}
	eDebugNoNewLine("ok\n");
	return 0;
}

void eDVBTText::stop()
{
	eDebugNoNewLineStart("[eDVBText%d] DEMUX_STOP ", m_dev);
	if (::ioctl(m_fd_demux, DMX_STOP) < 0)
		eDebugNoNewLine("failed: %m\n");
	else
		eDebugNoNewLine("ok\n");
}

eDVBTText::~eDVBTText()
{
	if (m_fd_demux >= 0)
		::close(m_fd_demux);
	eDebug("[eDVBText%d] destroy", m_dev);
}

DEFINE_REF(eTSMPEGDecoder);

void eTSMPEGDecoder::applyZapMode()
{
	std::string zapmodeDM = eConfigManager::getConfigValue("config.misc.zapmodeDM");
	m_hold_on_zap = (zapmodeDM == "hold");
	if (m_video)
		m_video->setHoldOnZap(m_hold_on_zap);
}

int eTSMPEGDecoder::setState()
{
	int res = 0;

	/* Refresh zap mode from config on every state transition, so a live
	 * setting change takes effect without a restart. */
	applyZapMode();

	int noaudio = (m_state != statePlay) && (m_state != statePause);
	int nott = noaudio;

	if ((noaudio && m_audio) || (!m_audio && !noaudio))
		m_changed |= changeAudio | changeState;

	if ((nott && m_text) || (!m_text && !nott))
		m_changed |= changeText | changeState;

	const char *decoder_states[] = {"stop", "pause", "play", "decoderfastforward", "trickmode", "slowmotion"};
	eDebug("[eTSMPEGDecoder] decoder state: %s, vpid=%04x, apid=%04x (zapmode=%s)",
		decoder_states[m_state], m_vpid, m_apid, m_hold_on_zap ? "hold" : "black");

	int changed = m_changed;
	if (m_changed & changePCR)
	{
		if (m_pcr)
			m_pcr->stop();
		m_pcr = 0;
	}
	if (m_changed & changeVideo)
	{
		if (m_video)
		{
			/* Only stop the video if we are going to destroy it.
			 * If we can reuse the fd (PID-only change), we call
			 * changePid() below instead. */
			bool keep_open = (!m_hold_on_zap) ? false : true;
			/* On a full teardown, still need to stop the demux filter.
			 *
			 * IMPORTANT (DM920 / Broadcom quirk):
			 * The VIDEO_STOP ioctl argument is inverted on these SoCs
			 * relative to the DVB API spec:
			 *     arg 0 -> freeze last frame (hold)
			 *     arg 1 -> black screen
			 * We therefore pass the inverse of what the DVB spec expects,
			 * otherwise "Black screen" gives hold and "Hold screen" gives
			 * a black screen (the exact symptom being fixed here). */
			m_video->stop(m_hold_on_zap ? 0 : 1);
			if (!keep_open || (m_vpid < 0) || (m_vpid >= 0x1FFF))
			{
				m_video = 0;
				m_video_event_conn = 0;
			}
			/* If keep_open is true and vpid valid, we keep m_video alive
			 * and changePid() will be called in the changeVideo block. */
		}
	}
	if (m_changed & changeAudio)
	{
		if (m_audio)
			m_audio->stop();
		m_audio = 0;
	}
	if (m_changed & changeText)
	{
		if (m_text)
		{
			m_text->stop();
			if (m_demux && m_decoder == 0)
				eTuxtxtApp::getInstance()->stopCaching();
		}
		m_text = 0;
	}
	if (m_changed & changePCR)
	{
		if ((m_pcrpid >= 0) && (m_pcrpid < 0x1FFF))
		{
			m_pcr = new eDVBPCR(m_demux, m_decoder);
			if (m_pcr->startPid(m_pcrpid))
				res = -1;
		}
		m_changed &= ~changePCR;
	}
	if (m_changed & changeAudio)
	{
		if ((m_apid >= 0) && (m_apid < 0x1FFF) && !noaudio)
		{
			m_audio = new eDVBAudio(m_demux, m_decoder);
			if (m_audio->startPid(m_apid, m_atype))
				res = -1;
		}
		m_changed &= ~changeAudio;
	}
	if (m_changed & changeVideo)
	{
		if ((m_vpid >= 0) && (m_vpid < 0x1FFF))
		{
			if (m_video)
			{
				/* Reuse the existing video fd. This preserves the frozen
				 * frame in "hold" mode, because we never closed the fd. */
				if (m_video->changePid(m_vpid, m_vtype))
					res = -1;
			}
			else
			{
				m_video = new eDVBVideo(m_demux, m_decoder, m_fcc_enable);
				m_video->setHoldOnZap(m_hold_on_zap);
				m_video->connectEvent(sigc::mem_fun(*this, &eTSMPEGDecoder::video_event), m_video_event_conn);
				if (m_video->startPid(m_vpid, m_vtype))
					res = -1;
			}
		}
		else
		{
			/* vpid is invalid: drop the video object. */
			m_video = 0;
			m_video_event_conn = 0;
		}
		m_changed &= ~changeVideo;
	}
	if (m_changed & changeText)
	{
		if ((m_textpid >= 0) && (m_textpid < 0x1FFF) && !nott)
		{
			m_text = new eDVBTText(m_demux, m_decoder);
			if (m_text->startPid(m_textpid))
				res = -1;

			if (m_demux && m_decoder == 0)
			{
				uint8_t demux = 0;
				m_demux->getCADemuxID(demux);
				eTuxtxtApp::getInstance()->startCaching(m_textpid, demux);
			}
		}
		else if (m_demux && m_decoder == 0)
			eTuxtxtApp::getInstance()->resetPid();

		m_changed &= ~changeText;
	}

	if (changed & (changeState|changeVideo|changeAudio))
	{
		int state_table[6][4] =
			{
				/* [stateStop] =                 */ {0, 0, 0},
				/* [statePause] =                */ {0, 0, 0},
				/* [statePlay] =                 */ {1, 0, 0},
				/* [stateDecoderFastForward] =   */ {1, 0, m_ff_sm_ratio},
				/* [stateHighspeedFastForward] = */ {1, 0, 1},
				/* [stateSlowMotion] =           */ {1, m_ff_sm_ratio, 0}
			};
		int *s = state_table[m_state];
		if (changed & (changeState|changeVideo) && m_video)
		{
			m_video->setSlowMotion(s[1]);
			m_video->setFastForward(s[2]);
			if (s[0])
				m_video->unfreeze();
			else
				m_video->freeze();
		}
		if (changed & (changeState|changeAudio) && m_audio)
		{
			if (s[0])
				m_audio->unfreeze();
			else
				m_audio->freeze();
		}
		m_changed &= ~changeState;
	}

	if (changed && !m_video && m_audio && m_radio_pic.length())
		showSinglePic(m_radio_pic.c_str());

	return res;
}

int eTSMPEGDecoder::m_pcm_delay=-1,
	eTSMPEGDecoder::m_ac3_delay=-1;

RESULT eTSMPEGDecoder::setHwPCMDelay(int delay)
{
	if (delay != m_pcm_delay )
	{
		if (CFile::writeIntHex("/proc/stb/audio/audio_delay_pcm", delay*90) >= 0)
		{
			m_pcm_delay = delay;
			return 0;
		}
	}
	return -1;
}

RESULT eTSMPEGDecoder::setHwAC3Delay(int delay)
{
	if ( delay != m_ac3_delay )
	{
		if (CFile::writeIntHex("/proc/stb/audio/audio_delay_bitstream", delay*90) >= 0)
		{
			m_ac3_delay = delay;
			return 0;
		}
	}
	return -1;
}

RESULT eTSMPEGDecoder::setPCMDelay(int delay)
{
	return m_decoder == 0 ? setHwPCMDelay(delay) : -1;
}

RESULT eTSMPEGDecoder::setAC3Delay(int delay)
{
	return m_decoder == 0 ? setHwAC3Delay(delay) : -1;
}

eTSMPEGDecoder::eTSMPEGDecoder(eDVBDemux *demux, int decoder)
	: m_demux(demux),
		m_vpid(-1), m_vtype(-1), m_apid(-1), m_atype(-1), m_pcrpid(-1), m_textpid(-1),
		m_changed(0), m_decoder(decoder), m_has_audio(false), m_hold_on_zap(false),
		m_video_clip_fd(-1), m_showSinglePicTimer(eTimer::create(eApp)),
		m_fcc_fd(-1), m_fcc_enable(false), m_fcc_state(fcc_state_stop), m_fcc_feid(-1), m_fcc_vpid(-1), m_fcc_vtype(-1), m_fcc_pcrpid(-1)
{
	if (m_demux)
	{
		m_demux->connectEvent(sigc::mem_fun(*this, &eTSMPEGDecoder::demux_event), m_demux_event_conn);
	}
	CONNECT(m_showSinglePicTimer->timeout, eTSMPEGDecoder::finishShowSinglePic);
	m_state = stateStop;

	char filename[128] = {};
	sprintf(filename, "/dev/dvb/adapter%d/audio%d", m_demux ? m_demux->adapter : 0, m_decoder);
	m_has_audio = !access(filename, W_OK);

	applyZapMode();

	if (m_demux && m_decoder == 0)
		eTuxtxtApp::getInstance()->initCache();
}

void eTSMPEGDecoder::freeDecoder()
{
	/* Release demux filter objects by closing their fds (via destructors).
	 * Unlike stop() which uses ioctl(DMX_STOP), close() lets the kernel
	 * clean up filters without going through the Broadcom playpump path.
	 * This prevents deadlocks/crashes on mipsel PVR-sourced demuxes. */
	m_video = nullptr;
	m_audio = nullptr;
	m_pcr = nullptr;
	m_text = nullptr;
	m_video_event_conn = nullptr;
	m_demux_event_conn = nullptr;
	m_changed = 0;
}

eTSMPEGDecoder::~eTSMPEGDecoder()
{
	finishShowSinglePic();
	m_vpid = m_apid = m_pcrpid = m_textpid = pidNone;
	m_changed = -1;
	setState();
	fccStop();
	fccFreeFD();

	if (m_demux && m_decoder == 0)
		eTuxtxtApp::getInstance()->freeCache();
}

RESULT eTSMPEGDecoder::setVideoPID(int vpid, int type)
{
	if ((m_vpid != vpid) || (m_vtype != type))
	{
		m_changed |= changeVideo;
		m_vpid = vpid;
		m_vtype = type;
	}
	return 0;
}

RESULT eTSMPEGDecoder::setAudioPID(int apid, int type)
{
	if (!m_has_audio) apid = -1;

	if ((m_apid != apid) || (m_atype != type))
	{
		m_changed |= changeAudio;
		m_atype = type;
		m_apid = apid;
	}
	return 0;
}

int eTSMPEGDecoder::m_audio_channel = -1;

RESULT eTSMPEGDecoder::setAudioChannel(int channel)
{
	if (channel == -1)
		channel = ac_stereo;
	if (m_decoder == 0 && m_audio_channel != channel)
	{
		if (m_audio)
		{
			m_audio->setChannel(channel);
			m_audio_channel=channel;
		}
		else
			eDebug("[eTSMPEGDecoder] setAudioChannel but no audio decoder exist");
	}
	return 0;
}

int eTSMPEGDecoder::getAudioChannel()
{
	return m_audio_channel == -1 ? ac_stereo : m_audio_channel;
}

RESULT eTSMPEGDecoder::setSyncPCR(int pcrpid)
{
	if (!m_has_audio) pcrpid = -1;

	if (m_pcrpid != pcrpid)
	{
		m_changed |= changePCR;
		m_pcrpid = pcrpid;
	}
	return 0;
}

RESULT eTSMPEGDecoder::setTextPID(int textpid)
{
	if (m_textpid != textpid)
	{
		m_changed |= changeText;
		m_textpid = textpid;
	}
	return 0;
}

RESULT eTSMPEGDecoder::setSyncMaster(int who)
{
	return -1;
}

RESULT eTSMPEGDecoder::set()
{
	return setState();
}

RESULT eTSMPEGDecoder::play()
{
	if (m_state == statePlay)
	{
		if (!m_changed)
			return 0;
	} else
	{
		m_state = statePlay;
		m_changed |= changeState;
	}
	return setState();
}

RESULT eTSMPEGDecoder::pause()
{
	if (m_state == statePause)
		return 0;
	m_state = statePause;
	m_changed |= changeState;
	return setState();
}

RESULT eTSMPEGDecoder::setFastForward(int frames_to_skip)
{
	if (!m_video)
		return -1;

	if ((m_state == stateDecoderFastForward) && (m_ff_sm_ratio == frames_to_skip))
		return 0;

	m_state = stateDecoderFastForward;
	m_ff_sm_ratio = frames_to_skip;
	m_changed |= changeState;
	return setState();
}

RESULT eTSMPEGDecoder::setSlowMotion(int repeat)
{
	if (!m_video)
		return -1;

	if ((m_state == stateSlowMotion) && (m_ff_sm_ratio == repeat))
		return 0;

	m_state = stateSlowMotion;
	m_ff_sm_ratio = repeat;
	m_changed |= changeState;
	return setState();
}

RESULT eTSMPEGDecoder::setTrickmode()
{
	if (!m_video)
		return -1;

	if (m_state == stateTrickmode)
		return 0;

	m_state = stateTrickmode;
	m_changed |= changeState;
	return setState();
}

RESULT eTSMPEGDecoder::flush()
{
	if (m_audio)
		m_audio->flush();
	if (m_video)
		m_video->flush();
	return 0;
}

void eTSMPEGDecoder::demux_event(int event)
{
	switch (event)
	{
	case eDVBDemux::evtFlush:
		flush();
		break;
	default:
		break;
	}
}

RESULT eTSMPEGDecoder::getPTS(int what, pts_t &pts)
{
	if (what == 0) /* auto */
		what = m_video ? 1 : 2;

	if (what == 1) /* video */
	{
		if (m_video)
			return m_video->getPTS(pts);
		else
			return -1;
	}

	if (what == 2) /* audio */
	{
		if (m_audio)
			return m_audio->getPTS(pts);
		else
			return -1;
	}

	return -1;
}

RESULT eTSMPEGDecoder::setRadioPic(const std::string &filename)
{
	m_radio_pic = filename;
	return 0;
}

RESULT eTSMPEGDecoder::showSinglePic(const char *filename)
{
	if (m_decoder == 0)
	{
		eDebug("[eTSMPEGDecoder] showSinglePic %s", filename);
		int f = open(filename, O_RDONLY);
		if (f >= 0)
		{
			struct stat s = {};
			fstat(f, &s);
			if (m_video_clip_fd == -1)
				m_video_clip_fd = open("/dev/dvb/adapter0/video0", O_WRONLY);
			if (m_video_clip_fd >= 0)
			{
				bool seq_end_avail = false;
				size_t pos=0;
				unsigned char pes_header[] = { 0x00, 0x00, 0x01, 0xE0, 0x00, 0x00, 0x80, 0x80, 0x05, 0x21, 0x00, 0x01, 0x00, 0x01 };
				unsigned char seq_end[] = { 0x00, 0x00, 0x01, 0xB7 };
				unsigned char iframe[s.st_size];
				unsigned char stuffing[8192];
				int streamtype;
				memset(stuffing, 0, sizeof(stuffing));
				ssize_t ret = read(f, iframe, s.st_size);
				if (ret < 0) eDebug("[eTSMPEGDecoder] read failed: %m");
				if (iframe[0] == 0x00 && iframe[1] == 0x00 && iframe[2] == 0x00 && iframe[3] == 0x01 && (iframe[4] & 0x0f) == 0x07)
					streamtype = VIDEO_STREAMTYPE_MPEG4_H264;
				else
					streamtype = VIDEO_STREAMTYPE_MPEG2;

				if (ioctl(m_video_clip_fd, VIDEO_SELECT_SOURCE, VIDEO_SOURCE_MEMORY) < 0)
					eDebug("[eTSMPEGDecoder] VIDEO_SELECT_SOURCE MEMORY failed: %m");
				if (ioctl(m_video_clip_fd, VIDEO_SET_STREAMTYPE, streamtype) < 0)
					eDebug("[eTSMPEGDecoder] VIDEO_SET_STREAMTYPE failed: %m");
				if (ioctl(m_video_clip_fd, VIDEO_PLAY) < 0)
					eDebug("[eTSMPEGDecoder] VIDEO_PLAY failed: %m");
				if (ioctl(m_video_clip_fd, VIDEO_CONTINUE) < 0)
					eDebug("[eTSMPEGDecoder] VIDEO_CONTINUE: %m");
				if (ioctl(m_video_clip_fd, VIDEO_CLEAR_BUFFER) < 0)
					eDebug("[eTSMPEGDecoder] VIDEO_CLEAR_BUFFER: %m");
				while(pos <= static_cast<size_t>(s.st_size-4) && !(seq_end_avail = (!iframe[pos] && !iframe[pos+1] && iframe[pos+2] == 1 && iframe[pos+3] == 0xB7)))
					++pos;
				if ((iframe[3] >> 4) != 0xE)
					writeAll(m_video_clip_fd, pes_header, sizeof(pes_header));
				else
					iframe[4] = iframe[5] = 0x00;
				writeAll(m_video_clip_fd, iframe, s.st_size);
				if (!seq_end_avail)
				{
					ret = write(m_video_clip_fd, seq_end, sizeof(seq_end));
					if (ret < 0) eDebug("[eTSMPEGDecoder] write failed: %m");
				}
				writeAll(m_video_clip_fd, stuffing, 8192);
				m_showSinglePicTimer->start(150, true);
			}
			close(f);
		}
		else
		{
			eDebug("[eTSMPEGDecoder] couldnt open %s: %m", filename);
			return -1;
		}
	}
	else
	{
		eDebug("[eTSMPEGDecoder] only show single pics on first decoder");
		return -1;
	}
	return 0;
}

void eTSMPEGDecoder::finishShowSinglePic()
{
	if (m_video_clip_fd >= 0)
	{
		if (ioctl(m_video_clip_fd, VIDEO_STOP, 0) < 0)
			eDebug("[eTSMPEGDecoder] VIDEO_STOP failed: %m");
		if (ioctl(m_video_clip_fd, VIDEO_SELECT_SOURCE, VIDEO_SOURCE_DEMUX) < 0)
			eDebug("[eTSMPEGDecoder] VIDEO_SELECT_SOURCE DEMUX failed: %m");
		close(m_video_clip_fd);
		m_video_clip_fd = -1;
	}
}

RESULT eTSMPEGDecoder::connectVideoEvent(const sigc::slot<void(struct videoEvent)> &event, ePtr<eConnection> &conn)
{
	conn = new eConnection(this, m_video_event.connect(event));
	return 0;
}

void eTSMPEGDecoder::video_event(struct videoEvent event)
{
	m_video_event(event);
}

int eTSMPEGDecoder::getVideoWidth()
{
	if (m_video)
		return m_video->getWidth();
	return -1;
}

int eTSMPEGDecoder::getVideoHeight()
{
	if (m_video)
		return m_video->getHeight();
	return -1;
}

int eTSMPEGDecoder::getVideoProgressive()
{
	if (m_video)
		return m_video->getProgressive();
	return -1;
}

int eTSMPEGDecoder::getVideoFrameRate()
{
	if (m_video)
		return m_video->getFrameRate();
	return -1;
}

int eTSMPEGDecoder::getVideoAspect()
{
	if (m_video)
		return m_video->getAspect();
	return -1;
}

int eTSMPEGDecoder::getVideoGamma()
{
	if (m_video)
		return m_video->getGamma();
	return -1;
}

#define FCC_SET_VPID 100
#define FCC_SET_APID 101
#define FCC_SET_PCRPID 102
#define FCC_SET_VCODEC 103
#define FCC_SET_ACODEC 104
#define FCC_SET_FRONTEND_ID 105
#define FCC_START 106
#define FCC_STOP 107
#define FCC_DECODER_START 108
#define FCC_DECODER_STOP 109

RESULT eTSMPEGDecoder::prepareFCC(int fe_id, int vpid, int vtype, int pcrpid)
{
	if ((fccGetFD() == -1) || (fccSetPids(fe_id, vpid, vtype, pcrpid) < 0) || (fccStart() < 0))
	{
		fccFreeFD();
		return -1;
	}

	m_fcc_enable = true;

	return 0;
}

RESULT eTSMPEGDecoder::fccDecoderStart()
{
	if (m_fcc_fd == -1)
		return -1;

	if (m_fcc_state != fcc_state_ready)
	{
		eDebug("[eTSMPEGDecoder] FCC decoder is already in decoding state.");
		return 0;
	}

	if (ioctl(m_fcc_fd, FCC_DECODER_START) < 0)
	{
		eDebug("[eTSMPEGDecoder] ioctl FCC_DECODER_START failed! (%m)");
		return -1;
	}

	m_fcc_state = fcc_state_decoding;

	eDebug("[eTSMPEGDecoder] FCC_DECODER_START OK!");
	return 0;
}

RESULT eTSMPEGDecoder::fccDecoderStop()
{
	if (m_fcc_fd == -1)
		return -1;

	if (m_fcc_state != fcc_state_decoding)
	{
		eDebug("[eTSMPEGDecoder] FCC decoder is not in decoding state.");
	}
	else if (ioctl(m_fcc_fd, FCC_DECODER_STOP) < 0)
	{
		eDebug("[eTSMPEGDecoder] ioctl FCC_DECODER_STOP failed! (%m)");
		return -1;
	}

	m_fcc_state = fcc_state_ready;

	finishShowSinglePic();

	m_vpid = m_apid = m_pcrpid = m_textpid = pidNone;
	m_changed = -1;
	setState();

	eDebug("[eTSMPEGDecoder] FCC_DECODER_STOP OK!");
	return 0;
}

RESULT eTSMPEGDecoder::fccUpdatePids(int fe_id, int vpid, int vtype, int pcrpid)
{
	if ((fe_id != m_fcc_feid) || (vpid != m_fcc_vpid) || (vtype != m_fcc_vtype) || (pcrpid != m_fcc_pcrpid))
	{
		fccStop();
		if (prepareFCC(fe_id, vpid, vtype, pcrpid))
		{
			eDebug("[eTSMPEGDecoder] prepare FCC failed!");
			return -1;
		}
	}
	return 0;
}

RESULT eTSMPEGDecoder::fccStart()
{
	if (m_fcc_fd == -1)
		return -1;

	if (m_fcc_state != fcc_state_stop)
	{
		eDebug("[eTSMPEGDecoder] FCC is already started!");
		return 0;
	}
	else if (ioctl(m_fcc_fd, FCC_START) < 0)
	{
		eDebug("[eTSMPEGDecoder] ioctl FCC_START failed! (%m)");
		return -1;
	}

	eDebug("[eTSMPEGDecoder] FCC_START OK!");

	m_fcc_state = fcc_state_ready;
	return 0;
}

RESULT eTSMPEGDecoder::fccStop()
{
	if (m_fcc_fd == -1)
		return -1;

	if (m_fcc_state == fcc_state_stop)
	{
		eDebug("[eTSMPEGDecoder] FCC is already stopped!");
		return 0;
	}
	else if (m_fcc_state == fcc_state_decoding)
	{
		fccDecoderStop();
	}

	if (ioctl(m_fcc_fd, FCC_STOP) < 0)
	{
		eDebug("[eTSMPEGDecoder] ioctl FCC_STOP failed! (%m)");
		return -1;
	}

	m_fcc_state = fcc_state_stop;

	eDebug("[eTSMPEGDecoder] FCC_STOP OK!");
	return 0;
}

RESULT eTSMPEGDecoder::fccSetPids(int fe_id, int vpid, int vtype, int pcrpid)
{
	int streamtype = VIDEO_STREAMTYPE_MPEG2;

	if (m_fcc_fd == -1)
		return -1;

	if (ioctl(m_fcc_fd, FCC_SET_FRONTEND_ID, fe_id) < 0)
	{
		eDebug("[eTSMPEGDecoder] FCC_SET_FRONTEND_ID failed! (%m)");
		return -1;
	}
	else if(ioctl(m_fcc_fd, FCC_SET_PCRPID, pcrpid) < 0)
	{
		eDebug("[eTSMPEGDecoder] FCC_SET_PCRPID failed! (%m)");
		return -1;
	}
	else if (ioctl(m_fcc_fd, FCC_SET_VPID, vpid) < 0)
	{
		eDebug("[eTSMPEGDecoder] FCC_SET_VPID failed! (%m)");
		return -1;
	}

	switch(vtype)
	{
		default:
		case eDVBVideo::MPEG2:
			break;
		case eDVBVideo::MPEG4_H264:
			streamtype = VIDEO_STREAMTYPE_MPEG4_H264;
			break;
		case eDVBVideo::MPEG1:
			streamtype = VIDEO_STREAMTYPE_MPEG1;
			break;
		case eDVBVideo::MPEG4_Part2:
			streamtype = VIDEO_STREAMTYPE_MPEG4_Part2;
			break;
		case eDVBVideo::VC1:
			streamtype = VIDEO_STREAMTYPE_VC1;
			break;
		case eDVBVideo::VC1_SM:
			streamtype = VIDEO_STREAMTYPE_VC1_SM;
			break;
		case eDVBVideo::H265_HEVC:
			streamtype = VIDEO_STREAMTYPE_H265_HEVC;
			break;
	}

	if(ioctl(m_fcc_fd, FCC_SET_VCODEC, streamtype) < 0)
	{
		eDebug("[eTSMPEGDecoder] FCC_SET_VCODEC failed! (%m)");
		return -1;
	}

	m_fcc_feid = fe_id;
	m_fcc_vpid = vpid;
	m_fcc_vtype = vtype;
	m_fcc_pcrpid = pcrpid;

	return 0;
}

RESULT eTSMPEGDecoder::fccGetFD()
{
	if (m_fcc_fd == -1)
	{
		eFCCDecoder* fcc = eFCCDecoder::getInstance();
		if (fcc != NULL)
		{
			m_fcc_fd = fcc->allocateFcc();
		}
	}

	return m_fcc_fd;
}

RESULT eTSMPEGDecoder::fccFreeFD()
{
	if (m_fcc_fd != -1)
	{
		eFCCDecoder* fcc = eFCCDecoder::getInstance();
		if (fcc != NULL)
		{
			fcc->freeFcc(m_fcc_fd);
			m_fcc_fd = -1;
		}
	}

	return 0;
}
