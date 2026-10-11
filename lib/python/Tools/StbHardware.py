from fcntl import ioctl
from os import path
from struct import pack, unpack
from time import time, localtime, gmtime


def _dbg(msg):
    # Route to eTrace/eDebug if available, otherwise print
    try:
        from enigma import eDebug
        eDebug("[StbHardware] %s" % msg)
    except Exception:
        print("[StbHardware] %s" % msg)


def getFPVersion():
    ret = None
    # 1) Standard STB path
    try:
        with open("/proc/stb/fp/version", "r") as f:
            ret = f.read().strip()
            if ret.isdigit():
                ret = int(ret)
    except IOError:
        pass
    # 2) Legacy DMM ioctl
    if ret is None:
        try:
            fp = open("/dev/dbox/fp0")
            try:
                ret = ioctl(fp.fileno(), 0)
            finally:
                fp.close()
        except IOError:
            pass
    # 3) DM920 devicetree tag
    if ret is None:
        try:
            with open("/sys/firmware/devicetree/base/bolt/tag", "r") as f:
                ret = f.read().rstrip("\0").strip()
        except (IOError, OSError):
            pass
    if ret is None:
        _dbg("getFPVersion not available on this box")
    return ret


def setFPWakeuptime(wutime):
    # 1) Standard STB path
    try:
        with open("/proc/stb/fp/wakeup_time", "w") as f:
            f.write(str(wutime))
        return
    except IOError:
        pass
    # 2) Legacy DMM ioctl
    try:
        fp = open("/dev/dbox/fp0")
        try:
            ioctl(fp.fileno(), 6, pack('L', wutime))
        finally:
            fp.close()
        return
    except IOError:
        pass
    # 3) DM920 uses RTC wakealarm via /sys/class/rtc/rtc0
    try:
        with open("/sys/class/rtc/rtc0/wakealarm", "w") as f:
            f.write(str(int(wutime)))
        return
    except (IOError, OSError):
        pass
    _dbg("setFPWakeuptime not available on this box")


def setRTCoffset(forsleep=None):
    # ViX-correct timezone handling (uses seconds, includes DST)
    if forsleep is None:
        if localtime().tm_isdst:
            forsleep = 3600 - timezone
        else:
            forsleep = 7200 + timezone
    try:
        with open("/proc/stb/fp/rtc_offset", "w") as f:
            f.write(str(forsleep))
        _dbg("set RTC offset to %s sec." % forsleep)
    except IOError:
        _dbg("setRTCoffset not available on this box")


def setRTCtime(wutime):
    if path.exists("/proc/stb/fp/rtc_offset"):
        setRTCoffset()
    # 1) Standard STB path
    try:
        with open("/proc/stb/fp/rtc", "w") as f:
            f.write(str(wutime))
        return
    except IOError:
        pass
    # 2) Legacy DMM ioctl
    try:
        fp = open("/dev/dbox/fp0")
        try:
            ioctl(fp.fileno(), 0x101, pack('L', wutime))
        finally:
            fp.close()
        return
    except IOError:
        pass
    # 3) DM920 kernel RTC
    try:
        with open("/sys/class/rtc/rtc0/since_epoch", "w") as f:
            f.write(str(int(wutime)))
        return
    except (IOError, OSError):
        pass
    _dbg("setRTCtime not available on this box")


def getFPWakeuptime():
    ret = 0
    # 1) Standard STB path
    try:
        with open("/proc/stb/fp/wakeup_time", "r") as f:
            ret = int(f.read().strip())
        return ret
    except (IOError, ValueError):
        pass
    # 2) Legacy DMM ioctl
    try:
        fp = open("/dev/dbox/fp0")
        try:
            ret = unpack('L', ioctl(fp.fileno(), 5, '    '))[0]
        finally:
            fp.close()
        return ret
    except IOError:
        pass
    # 3) DM920 kernel RTC
    try:
        with open("/sys/class/rtc/rtc0/wakealarm", "r") as f:
            ret = int(f.read().strip() or 0)
        return ret
    except (IOError, ValueError):
        pass
    _dbg("getFPWakeuptime not available on this box")
    return ret


wasTimerWakeup = None


def getFPWasTimerWakeup():
    global wasTimerWakeup
    if wasTimerWakeup is not None:
        return wasTimerWakeup
    wasTimerWakeup = False
    # 1) Standard STB path
    try:
        with open("/proc/stb/fp/was_timer_wakeup", "r") as f:
            wasTimerWakeup = bool(int(f.read().strip()))
    except (IOError, ValueError):
        # 2) Legacy DMM ioctl
        try:
            fp = open("/dev/dbox/fp0")
            try:
                wasTimerWakeup = bool(unpack('B', ioctl(fp.fileno(), 9, ' '))[0])
            finally:
                fp.close()
        except IOError:
            # 3) DM920 kernel RTC — wakealarm is cleared by kernel on wake
            try:
                with open("/sys/class/rtc/rtc0/wakealarm", "r") as f:
                    # If alarm time is in the past and matches boot time → timer wakeup
                    alarm = int(f.read().strip() or 0)
                    wasTimerWakeup = bool(alarm)
            except (IOError, ValueError):
                _dbg("getFPWasTimerWakeup not available on this box")
    if wasTimerWakeup:
        clearFPWasTimerWakeup()
    return wasTimerWakeup


def clearFPWasTimerWakeup():
    # 1) Standard STB path
    try:
        with open("/proc/stb/fp/was_timer_wakeup", "w") as f:
            f.write('0')
        return
    except IOError:
        pass
    # 2) Legacy DMM ioctl
    try:
        fp = open("/dev/dbox/fp0")
        try:
            ioctl(fp.fileno(), 10)
        finally:
            fp.close()
        return
    except IOError:
        pass
    # 3) DM920 kernel RTC — clear wakealarm
    try:
        with open("/sys/class/rtc/rtc0/wakealarm", "w") as f:
            f.write('0')
        return
    except (IOError, OSError):
        pass
    _dbg("clearFPWasTimerWakeup not available on this box")
