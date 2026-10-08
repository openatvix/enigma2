#ifndef __decoder_h
#define __decoder_h

#include <lib/base/object.h>
#include <lib/dvb/demux.h>

class eSocketNotifier;

class eDVBAudio: public iObject
{
	DECLARE_REF(eDVBAudio);
private:
	ePtr<eDVBDemux> m_demux;
	int m_fd, m_fd_demux, m_dev, m_is_freezed;
public:
	enum { aMPEG, aAC3, aDTS, aAAC, aAACHE, aLPCM, aDTSHD, aDDP, aDRA, aAC4 };
	eDVBAudio(eDVBDemux *demux, int dev);
	enum { aMonoLeft, aStereo, aMonoRight };
	void setChannel(int channel);
	void stop();
	int startPid(int pid, int type);
	void flush();
	void freeze();
	void unfreeze();
	int getPTS(pts_t &now);
	virtual ~eDVBAudio();
};

class eDVBVideo: public iObject, public sigc::trackable
{
	DECLARE_REF(eDVBVideo);
private:
	ePtr<eDVBDemux> m_demux;
	int m_fd, m_fd_demux, m_dev;
	bool m_fcc_enable;
	bool m_hold_on_zap;
	static int m_close_invalidates_attributes;
	int m_is_slow_motion, m_is_fast_forward, m_is_freezed;
	ePtr<eSocketNotifier> m_sn;
	void video_event(int what);
	sigc::signal<void(struct iTSMPEGDecoder::videoEvent)> m_event;
	int m_width, m_height, m_framerate, m_aspect, m_progressive, m_gamma;
	static int readApiSize(int fd, int &xres, int &yres, int &aspect);
public:
	enum { UNKNOWN = -1, MPEG2, MPEG4_H264, VC1 = 3, MPEG4_Part2, VC1_SM, MPEG1, H265_HEVC, AVS = 16, AVS2 = 40 };
	eDVBVideo(eDVBDemux *demux, int dev, bool fcc_enable=false);
	void stop();                      /* default: freeze last frame (hold) */
	void stop(int freeze_last_frame); /* explicit control */
	int startPid(int pid, int type=MPEG2);
	int changePid(int pid, int type=MPEG2); /* reuse open fd, no destroy */
	void flush();
	void freeze();
	int setSlowMotion(int repeat);
	int setFastForward(int skip);
	void unfreeze();
	int getPTS(pts_t &now);
	virtual ~eDVBVideo();

	bool holdOnZap() const { return m_hold_on_zap; }
	void setHoldOnZap(bool v) { m_hold_on_zap = v; }

	RESULT connectEvent(const sigc::slot<void(struct iTSMPEGDecoder::videoEvent)> &event, ePtr<eConnection> &conn);
	int getWidth();
	int getHeight();
	int getProgressive();
	int getFrameRate();
	int getAspect();
	int getGamma();
};

class eDVBPCR: public iObject
{
	DECLARE_REF(eDVBPCR);
private:
	ePtr<eDVBDemux> m_demux;
	int m_fd_demux, m_dev;
public:
	eDVBPCR(eDVBDemux *demux, int dev);
	int startPid(int pid);
	void stop();
	virtual ~eDVBPCR();
};

class eDVBTText: public iObject
{
	DECLARE_REF(eDVBTText);
private:
	ePtr<eDVBDemux> m_demux;
	int m_fd_demux, m_dev;
public:
	eDVBTText(eDVBDemux *demux, int dev);
	int startPid(int pid);
	void stop();
	virtual ~eDVBTText();
};

class eTSMPEGDecoder: public sigc::trackable, public iTSMPEGDecoder
{
	DECLARE_REF(eTSMPEGDecoder);
private:
	static int m_pcm_delay;
	static int m_ac3_delay;
	static int m_audio_channel;
	std::string m_radio_pic;
	ePtr<eDVBDemux> m_demux;
	ePtr<eDVBAudio> m_audio;
	ePtr<eDVBVideo> m_video;
	ePtr<eDVBPCR> m_pcr;
	ePtr<eDVBTText> m_text;
	int m_vpid, m_vtype, m_apid, m_atype, m_pcrpid, m_textpid;
	enum
	{
		changeVideo = 1,
		changeAudio = 2,
		changePCR   = 4,
		changeText  = 8,
		changeState = 16,
	};
	int m_changed, m_decoder;
	int m_state;
	int m_ff_sm_ratio;
	bool m_has_audio;
	bool m_hold_on_zap;
	void applyZapMode();
	int setState();
	ePtr<eConnection> m_demux_event_conn;
	ePtr<eConnection> m_video_event_conn;

	void demux_event(int event);
	void video_event(struct videoEvent);
	sigc::signal<void(struct videoEvent)> m_video_event;
	int m_video_clip_fd;
	ePtr<eTimer> m_showSinglePicTimer;
	int m_fcc_fd;
	bool m_fcc_enable;
	int m_fcc_state;
	int m_fcc_feid;
	int m_fcc_vpid;
	int m_fcc_vtype;
	int m_fcc_pcrpid;
	void finishShowSinglePic(); // called by timer
public:
	enum { pidNone = -1 };
	eTSMPEGDecoder(eDVBDemux *demux, int decoder);
	virtual ~eTSMPEGDecoder();
	RESULT setVideoPID(int vpid, int type);
	RESULT setAudioPID(int apid, int type);
	RESULT setAudioChannel(int channel);
	int getAudioChannel();
	RESULT setPCMDelay(int delay);
	int getPCMDelay() { return m_pcm_delay; }
	RESULT setAC3Delay(int delay);
	int getAC3Delay() { return m_ac3_delay; }
	RESULT setSyncPCR(int pcrpid);
	RESULT setTextPID(int textpid);
	RESULT setSyncMaster(int who);

	enum {
		stateStop,
		statePause,
		statePlay,
		stateDecoderFastForward,
		stateTrickmode,
		stateSlowMotion
	};
	RESULT set(); /* just apply settings, keep state */
	RESULT play(); /* -> play */
	RESULT pause(); /* -> pause */
	RESULT setFastForward(int frames_to_skip); /* -> decoder fast forward */
	RESULT setSlowMotion(int repeat); /* -> slow motion **/
	RESULT setTrickmode(); /* -> highspeed fast forward */

	RESULT flush();
	RESULT showSinglePic(const char *filename);
	RESULT setRadioPic(const std::string &filename);
		/* what 0=auto, 1=video, 2=audio. */
	RESULT getPTS(int what, pts_t &pts);
	RESULT connectVideoEvent(const sigc::slot<void(struct videoEvent)> &event, ePtr<eConnection> &connection);
	int getVideoWidth();
	int getVideoHeight();
	int getVideoProgressive();
	int getVideoFrameRate();
	int getVideoAspect();
	int getVideoGamma();
	static RESULT setHwPCMDelay(int delay);
	static RESULT setHwAC3Delay(int delay);

	enum
	{
		fcc_state_stop,
		fcc_state_ready,
		fcc_state_decoding
	};

	void freeDecoder() override;

	RESULT prepareFCC(int fe_id, int vpid, int vtype, int pcrpid);
	RESULT fccStart();
	RESULT fccStop();
	RESULT fccDecoderStart();
	RESULT fccDecoderStop();
	RESULT fccUpdatePids(int fe_id, int vpid, int vtype, int pcrpid);
	RESULT fccSetPids(int fe_id, int vpid, int vtype, int pcrpid);
	RESULT fccGetFD();
	RESULT fccFreeFD();
};

#endif
