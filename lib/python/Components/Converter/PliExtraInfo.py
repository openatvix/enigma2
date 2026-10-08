from enigma import iServiceInformation, iPlayableService, eDVBCI_UI
from Components.Converter.Converter import Converter
from Components.Element import cached
from Components.config import config
from Components.SystemInfo import SystemInfo
from Tools.Transponder import ConvertToHumanReadable
from Tools.GetEcmInfo import GetEcmInfo
from Components.Converter.Poll import Poll
from Tools.Directories import pathExists
from skin import parameters
import os
import re

# Fix: Import gettext for _() function
try:
    from gettext import gettext as _
except ImportError:
    def _(text):
        return text

# Get CI instance
try:
    dvbCIUI = eDVBCI_UI.getInstance()
except:
    dvbCIUI = None

# Detect DreamBox
IS_DREAMBOX = False
try:
    with open("/proc/stb/info/model", "r") as f:
        model = f.read().strip().upper()
        if "DM" in model or "DREAM" in model:
            IS_DREAMBOX = True
except:
    pass

# CAID data - complete list
caid_data = (
    ("0x4a30", "0x4a30", "DVN-JET", "TB", "DVN", False),
    ("0x4ad2", "0x4ad3", "STREAMGUARD", "SM", "SMG", False),
    ("0x4a02", "0x4a02", "TONGFANG", "TF", "TGF", False),
    ("0x100", "0x1ff", "Seca", "S", "SECA", True),
    ("0x500", "0x5ff", "Via", "V", "VIA", True),
    ("0x600", "0x6ff", "Irdeto", "I", "IRD", True),
    ("0x900", "0x9ff", "NDS", "Nd", "NDS", True),
    ("0xb00", "0xbff", "Conax", "Co", "CONAX", True),
    ("0xd00", "0xdff", "CryptoW", "Cw", "CRW", True),
    ("0xe00", "0xeff", "PowerVU", "P", "PV", False),
    ("0x1000", "0x10FF", "Tandberg", "TB", "TAND", False),
    ("0x1700", "0x17ff", "Beta", "B", "BETA", True),
    ("0x1800", "0x18ff", "Nagra", "N", "NAGRA", True),
    ("0x2600", "0x2600", "Biss", "Bi", "BiSS", False),
    ("0x2700", "0x2710", "Dre3", "D3", "DRE3", False),
    ("0x4ae0", "0x4ae1", "Dre", "D", "DRE", False),
    ("0x4aee", "0x4aee", "BulCrypt", "B1", "BUL", False),
    ("0x5581", "0x5581", "BulCrypt", "B2", "BUL", False),
    ("0x5601", "0x5604", "Verimatrix", "Vm", "VER", False)
)

# Stream type to codec map
codec_data = {
    -1: "N/A",
    0: "MPEG2 H.262",
    1: "MPEG4 H.264",
    2: "H263",
    3: "VC1",
    4: "MPEG4 VC",
    5: "VC1 SM",
    6: "MPEG1 H.261",
    7: "HEVC H.265",
    8: "VP8",
    9: "VP9",
    10: "XVID",
    11: "N/A 11",
    12: "N/A 12",
    13: "DIVX 3.11",
    14: "DIVX 4",
    15: "DIVX 5",
    16: "AVS",
    17: "N/A 17",
    18: "VP6",
    19: "N/A 19",
    20: "N/A 20",
    21: "SPARK",
    22: "HEVC H.265",
    40: "AVS2",
    41: "AVS3",
    42: "N/A 42",
    43: "N/A 43",
    44: "N/A 44",
    45: "N/A 45",
    46: "N/A 46",
    47: "N/A 47",
    48: "N/A 48",
    49: "N/A 49",
    50: "N/A 50",
}

# Gamma data
gamma_data = {
    -1: "",
    0: "SDR",
    1: "HDR",
    2: "HDR10",
    3: "HLG",
}


def addspace(text):
    if text:
        text += " "
    return text


def _safe_int(value, default=0):
    """Safely convert to int"""
    if value is None:
        return default
    if isinstance(value, bytes):
        try:
            if value.startswith(b'0x') or value.startswith(b'0X'):
                return int(value, 16)
            return int(value)
        except:
            return default
    if isinstance(value, str):
        try:
            if value.startswith('0x') or value.startswith('0X'):
                return int(value, 16)
            return int(value)
        except:
            return default
    try:
        return int(value)
    except:
        return default


def _safe_str(value, default=""):
    """Safely convert to string"""
    if value is None:
        return default
    if isinstance(value, bytes):
        try:
            return value.decode('utf-8', errors='ignore')
        except:
            return str(value)
    return str(value)


class PliExtraInfo(Poll, Converter):
    """Full featured PliExtraInfo for DreamBox DM920 with IPTV support"""
    
    # Type constants
    CryptoInfo = "CryptoInfo"
    CryptoBar = "CryptoBar"
    CryptoSpecial = "CryptoSpecial"
    Resolution = "Resolution"
    ResolutionString = "ResolutionString"
    VideoCodec = "VideoCodec"
    Gamma = "Gamma"
    Settings = "Settings"
    All = "All"
    PIDInfo = "PIDInfo"
    ServiceInfo = "ServiceInfo"
    TransponderInfo = "TransponderInfo"
    TransponderFrequency = "TransponderFrequency"
    TransponderSymbolRate = "TransponderSymbolRate"
    TransponderPolarization = "TransponderPolarization"
    TransponderFEC = "TransponderFEC"
    TransponderModulation = "TransponderModulation"
    OrbitalPosition = "OrbitalPosition"
    TunerType = "TunerType"
    TunerSystem = "TunerSystem"
    OrbitalPositionOrTunerSystem = "OrbitalPositionOrTunerSystem"
    TerrestrialChannelNumber = "TerrestrialChannelNumber"
    TransponderInfoMisPls = "TransponderInfoMisPls"
    TransponderName = "TransponderName"
    CurrentCrypto = "CurrentCrypto"
    CryptoNameCaid = "CryptoNameCaid"
    ServiceRef = "ServiceRef"
    ProviderName = "ProviderName"
    # IPTV specific types
    IPTVInfo = "IPTVInfo"
    IPTVUrl = "IPTVUrl"
    IPTVStreamType = "IPTVStreamType"
    IPTVHost = "IPTVHost"
    
    def __init__(self, type):
        Converter.__init__(self, type)
        Poll.__init__(self)
        self.type = type
        self.poll_interval = 1000
        self.poll_enabled = True
        
        # CA table for boolean checks
        self.ca_table = (
            ("CryptoCaidDvnAvailable", "TB", False),
            ("CryptoCaidSmsxAvailable", "SM", False),
            ("CryptoCaidTongfangAvailable", "TF", False),
            ("CryptoCaidSecaAvailable", "S", False),
            ("CryptoCaidViaAvailable", "V", False),
            ("CryptoCaidIrdetoAvailable", "I", False),
            ("CryptoCaidNDSAvailable", "Nd", False),
            ("CryptoCaidConaxAvailable", "Co", False),
            ("CryptoCaidCryptoWAvailable", "Cw", False),
            ("CryptoCaidPowerVUAvailable", "P", False),
            ("CryptoCaidBetaAvailable", "B", False),
            ("CryptoCaidNagraAvailable", "N", False),
            ("CryptoCaidBissAvailable", "Bi", False),
            ("CryptoCaidDre3Available", "D3", False),
            ("CryptoCaidDreAvailable", "D", False),
            ("CryptoCaidBulCrypt1Available", "B1", False),
            ("CryptoCaidBulCrypt2Available", "B2", False),
            ("CryptoCaidVerimatrixAvailable", "Vm", False),
            ("CryptoCaidTandbergAvailable", "TB", False),
            ("CryptoCaidDvnSelected", "TB", True),
            ("CryptoCaidSmsxSelected", "SM", True),
            ("CryptoCaidTongfangSelected", "TF", True),
            ("CryptoCaidSecaSelected", "S", True),
            ("CryptoCaidViaSelected", "V", True),
            ("CryptoCaidIrdetoSelected", "I", True),
            ("CryptoCaidNDSSelected", "Nd", True),
            ("CryptoCaidConaxSelected", "Co", True),
            ("CryptoCaidCryptoWSelected", "Cw", True),
            ("CryptoCaidPowerVUSelected", "P", True),
            ("CryptoCaidBetaSelected", "B", True),
            ("CryptoCaidNagraSelected", "N", True),
            ("CryptoCaidBissSelected", "Bi", True),
            ("CryptoCaidDre3Selected", "D3", True),
            ("CryptoCaidDreSelected", "D", True),
            ("CryptoCaidBulCrypt1Selected", "B1", True),
            ("CryptoCaidBulCrypt2Selected", "B2", True),
            ("CryptoCaidVerimatrixSelected", "Vm", True),
            ("CryptoCaidTandbergSelected", "TB", True),
        )
        
        self.ecmdata = GetEcmInfo()
        self.feraw = None
        self.fedata = None
        self.updateFEdata = None
        self.current_source = ""
        self.current_caid = "0"
        self.current_provid = "0"
        self.current_ecmpid = "0"
        self.is_iptv = False
        self.iptv_url = ""
        self.iptv_host = ""
        self.iptv_stream_type = ""
        self.iptv_full_ref = ""
        
        # Get colors from skin
        try:
            self.cryptocolors = parameters.get("PliExtraInfoCryptoColors", 
                (0x004C7D3F, 0x009F9F9F, 0x00EEEE00, 0x00FFFFFF))
        except:
            self.cryptocolors = (0x004C7D3F, 0x009F9F9F, 0x00EEEE00, 0x00FFFFFF)

    def _safe_int(self, value, default=0):
        return _safe_int(value, default)

    def _safe_str(self, value, default=""):
        return _safe_str(value, default)

    def _is_iptv_service(self, refstr):
        """Check if service is IPTV"""
        if not refstr:
            return False
        refstr = refstr.lower()
        # Check for IPTV indicators
        iptv_patterns = [
            '%3a//', 'http://', 'https://', 'rtsp://', 'rtmp://',
            'udp://', 'rtp://', 'mms://', '.m3u8', '.ts', 'stream',
            'live', 'iptv'
        ]
        for pattern in iptv_patterns:
            if pattern in refstr:
                return True
        return False

    def _clean_iptv_url(self, url):
        """Clean IPTV URL by removing channel name from the end"""
        if not url:
            return url
        
        # Remove everything after the last colon if it looks like a channel name
        match = re.search(r'^(.*):[^:/\\]+$', url)
        if match:
            after_colon = url.split(':')[-1]
            if not after_colon.isdigit() and '/' not in after_colon and '?' not in after_colon:
                return match.group(1)
        
        # Also handle case where URL ends with :ChannelName without any path
        match = re.search(r'^(.*)(:[^:/\\?]+)$', url)
        if match:
            after = match.group(2)
            if after.startswith(':') and len(after) > 1:
                channel_name = after[1:]
                if re.search(r'[a-zA-Z]', channel_name) and not channel_name.isdigit():
                    return match.group(1)
        
        return url

    def _parse_iptv_url(self, refstr):
        """Parse IPTV URL from service reference"""
        if not refstr:
            return "", "", ""
        
        self.iptv_full_ref = refstr
        
        clean_ref = refstr.replace("%3a", ":").replace("%3A", ":")
        clean_ref = clean_ref.replace("%2f", "/").replace("%2F", "/")
        clean_ref = clean_ref.replace("%3f", "?").replace("%3F", "?")
        clean_ref = clean_ref.replace("%3d", "=").replace("%3D", "=")
        clean_ref = clean_ref.replace("%26", "&")
        
        url = ""
        host = ""
        stream_type = ""
        
        url_patterns = [
            r'(https?://[^\s/?#]+[^\s]*)',
            r'(rtsp://[^\s/?#]+[^\s]*)',
            r'(rtmp://[^\s/?#]+[^\s]*)',
            r'(udp://[^\s/?#]+[^\s]*)',
            r'(rtp://[^\s/?#]+[^\s]*)',
            r'(mms://[^\s/?#]+[^\s]*)',
        ]
        
        for pattern in url_patterns:
            match = re.search(pattern, clean_ref, re.IGNORECASE)
            if match:
                url = match.group(1)
                break
        
        if not url:
            protocols = ['http://', 'https://', 'rtsp://', 'rtmp://', 'udp://', 'rtp://', 'mms://']
            for protocol in protocols:
                if protocol in clean_ref:
                    start = clean_ref.find(protocol)
                    end = clean_ref.find(' ', start)
                    if end == -1:
                        end = len(clean_ref)
                    url = clean_ref[start:end]
                    break
        
        if not url:
            parts = clean_ref.split(':')
            for i, part in enumerate(parts):
                if part in ['http', 'https', 'rtsp', 'rtmp', 'udp', 'rtp', 'mms']:
                    url = ':'.join(parts[i:])
                    break
        
        if url:
            url = self._clean_iptv_url(url)
        
        if url:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                host = parsed.netloc or parsed.path.split('/')[0]
                if '@' in host:
                    host = host.split('@')[-1]
                if ':' in host:
                    host = host.split(':')[0]
                if url.startswith('http://') or url.startswith('https://'):
                    if '.m3u8' in url.lower():
                        stream_type = 'HLS'
                    elif '.ts' in url.lower():
                        stream_type = 'TS'
                    else:
                        stream_type = 'HTTP'
                elif url.startswith('rtsp://'):
                    stream_type = 'RTSP'
                elif url.startswith('rtmp://'):
                    stream_type = 'RTMP'
                elif url.startswith('udp://'):
                    stream_type = 'UDP'
                elif url.startswith('rtp://'):
                    stream_type = 'RTP'
                elif url.startswith('mms://'):
                    stream_type = 'MMS'
            except:
                pass
        
        return url, host, stream_type

    def getCryptoInfo(self, info):
        """Get crypto information"""
        try:
            refstr = info.getInfoString(iServiceInformation.sServiceref)
            if refstr:
                refstr = self._safe_str(refstr, "")
                if self._is_iptv_service(refstr):
                    self.is_iptv = True
                    self.iptv_url, self.iptv_host, self.iptv_stream_type = self._parse_iptv_url(refstr)
                else:
                    self.is_iptv = False
                    self.iptv_url = ""
                    self.iptv_host = ""
                    self.iptv_stream_type = ""
        except:
            self.is_iptv = False
        
        if info.getInfo(iServiceInformation.sIsCrypted) == 1:
            data = self.ecmdata.getEcmData()
            if data and len(data) >= 4:
                self.current_source = self._safe_str(data[0], "")
                self.current_caid = self._safe_str(data[1], "0")
                self.current_provid = self._safe_str(data[2], "0")
                self.current_ecmpid = self._safe_str(data[3], "0")
            else:
                self.current_source = ""
                self.current_caid = "0"
                self.current_provid = "0"
                self.current_ecmpid = "0"
        else:
            self.current_source = ""
            self.current_caid = "0"
            self.current_provid = "0"
            self.current_ecmpid = "0"

    # ============ CRYPTO METHODS ============

    def createCryptoBar(self, info):
        """Create colored crypto status bar"""
        if self.is_iptv:
            return "\c00FF6600IPTV"
            
        res = ""
        try:
            available_caids = info.getInfoObject(iServiceInformation.sCAIDs)
        except:
            available_caids = []
            
        try:
            colors = parameters.get("PliExtraInfoColors", 
                (0x0000FF00, 0x00FF0000, 0x00FFFFFF, 0x007F7F7F))
        except:
            colors = (0x0000FF00, 0x00FF0000, 0x00FFFFFF, 0x007F7F7F)
        
        current_caid_int = self._safe_int(self.current_caid, 0)
        
        for caid_entry in caid_data:
            start_caid = self._safe_int(caid_entry[0], 0)
            end_caid = self._safe_int(caid_entry[1], 0)
            
            if start_caid <= current_caid_int <= end_caid:
                color = "\c%08x" % colors[0]
            else:
                color = "\c%08x" % colors[2]
                try:
                    if available_caids:
                        for caid in available_caids:
                            caid_int = self._safe_int(caid, 0)
                            if start_caid <= caid_int <= end_caid:
                                color = "\c%08x" % colors[1]
                                break
                except:
                    pass

            if color != "\c%08x" % colors[2] or caid_entry[5]:
                if res:
                    res += " "
                res += color + caid_entry[3]

        res += "\c%08x" % colors[3]
        return res

    def createCurrentCaidLabel(self, info):
        """Create current CAID label with CI support"""
        if self.is_iptv:
            return "IPTV"
            
        res = ""
        decodingCiSlot = -1
        
        NUM_CI = SystemInfo.get("CommonInterface", 0)
        if NUM_CI and NUM_CI > 0 and dvbCIUI:
            for slot in range(NUM_CI):
                try:
                    stateDecoding = dvbCIUI.getDecodingState(slot)
                    stateSlot = dvbCIUI.getState(slot)
                    if stateDecoding == 2 and stateSlot not in (-1, 0, 3):
                        decodingCiSlot = slot
                except:
                    pass
        
        if not pathExists("/tmp/ecm.info") and decodingCiSlot == -1:
            return "FTA"
        
        if decodingCiSlot > -1 and not pathExists("/tmp/ecm.info"):
            return "CI%d" % (decodingCiSlot)
            
        current_caid_int = self._safe_int(self.current_caid, 0)
        for caid_entry in caid_data:
            start_caid = self._safe_int(caid_entry[0], 0)
            end_caid = self._safe_int(caid_entry[1], 0)
            if start_caid <= current_caid_int <= end_caid:
                res = caid_entry[4]
                break
                
        if decodingCiSlot > -1:
            return "CI%d + %s" % (decodingCiSlot, res)
        return res

    def createCryptoSpecial(self, info):
        """Create crypto special info with CAID/Provider/SID"""
        if self.is_iptv:
            return self.iptv_url if self.iptv_url else self.iptv_host or "IPTV"
            
        try:
            refstr = info.getInfoString(iServiceInformation.sServiceref)
            if refstr:
                refstr = self._safe_str(refstr, "")
        except:
            refstr = ""
        
        if refstr and self._is_iptv_service(refstr):
            url, host, _ = self._parse_iptv_url(refstr)
            return url if url else host or "IPTV"
        
        caid_name = "Free to Air"
        current_caid_int = self._safe_int(self.current_caid, 0)
        if current_caid_int == 0:
            current_provid_int = self._safe_int(self.current_provid, 0)
            try:
                sid = info.getInfo(iServiceInformation.sSID)
                if sid is None or sid < 0:
                    sid = 0
            except:
                sid = 0
            return "FTA:%06X:%04X" % (current_provid_int, sid)
            
        try:
            for caid_entry in caid_data:
                start_caid = self._safe_int(caid_entry[0], 0)
                end_caid = self._safe_int(caid_entry[1], 0)
                if start_caid <= current_caid_int <= end_caid:
                    caid_name = caid_entry[2]
                    break
                    
            current_provid_int = self._safe_int(self.current_provid, 0)
            try:
                sid = info.getInfo(iServiceInformation.sSID)
                if sid is None or sid < 0:
                    sid = 0
            except:
                sid = 0
                
            return "%s:%04X:%06X:%04X" % (caid_name, current_caid_int, current_provid_int, sid)
        except:
            pass
        return ""

    def createCryptoNameCaid(self, info):
        """Create crypto name with CAID"""
        if self.is_iptv:
            return "IPTV"
            
        caid_name = "FTA"
        current_caid_int = self._safe_int(self.current_caid, 0)
        if current_caid_int == 0:
            return caid_name
        try:
            for caid_entry in caid_data:
                start_caid = self._safe_int(caid_entry[0], 0)
                end_caid = self._safe_int(caid_entry[1], 0)
                if start_caid <= current_caid_int <= end_caid:
                    caid_name = caid_entry[2]
                    break
            return "%s:%04X" % (caid_name, current_caid_int)
        except:
            pass
        return ""

    # ============ IPTV SPECIFIC METHODS ============

    def createIPTVInfo(self, info):
        """Get IPTV information - shows URL with stream type"""
        if self.is_iptv:
            if self.iptv_url and self.iptv_stream_type:
                return "%s (%s)" % (self.iptv_url, self.iptv_stream_type)
            elif self.iptv_url:
                return self.iptv_url
            elif self.iptv_host:
                return self.iptv_host
        return ""

    def createIPTVUrl(self, info):
        """Get IPTV URL - cleaned without channel name"""
        if self.is_iptv and self.iptv_url:
            return self.iptv_url
        return ""

    def createIPTVStreamType(self, info):
        """Get IPTV stream type only"""
        if self.is_iptv and self.iptv_stream_type:
            return self.iptv_stream_type
        return ""

    def createIPTVHost(self, info):
        """Get IPTV host only"""
        if self.is_iptv and self.iptv_host:
            return self.iptv_host
        return ""

    # ============ VIDEO METHODS ============

    def createResolution(self, info):
        """Get video resolution"""
        try:
            with open("/proc/stb/vmpeg/0/yres", "r") as f:
                yres = int(f.read(), 16)
            if yres > 4096 or yres == 0:
                return ""
        except:
            return ""
        try:
            with open("/proc/stb/vmpeg/0/xres", "r") as f:
                xres = int(f.read(), 16)
            if xres > 4096 or xres == 0:
                return ""
        except:
            return ""
        mode = ""
        try:
            with open("/proc/stb/vmpeg/0/progressive", "r") as f:
                mode = "p" if int(f.read(), 16) else "i"
        except:
            pass
        fps = ""
        try:
            with open("/proc/stb/vmpeg/0/framerate", "r") as f:
                fps = str((int(f.read()) + 500) // 1000)
        except:
            pass

        if fps:
            return "%sx%s%s@%s" % (xres, yres, mode, fps)
        return "%sx%s%s" % (xres, yres, mode)

    def createGamma(self, info):
        """Get gamma/HDR information"""
        try:
            gamma = info.getInfo(iServiceInformation.sGamma)
            return gamma_data.get(gamma, "")
        except:
            return ""

    def createVideoCodec(self, info):
        """Get video codec name with DreamBox support"""
        try:
            video_type = info.getInfo(iServiceInformation.sVideoType)
            # DreamBox HEVC handling
            if IS_DREAMBOX and video_type == 7:
                return codec_data.get(video_type, "N/A")
            return codec_data.get(video_type, "N/A")
        except:
            return "N/A"

    def createResolutionString(self, info):
        """Get resolution with gamma"""
        resolution = self.createResolution(info)
        gamma = self.createGamma(info)
        if resolution and gamma:
            return resolution + " " + gamma
        return resolution or gamma or ""

    # ============ PID METHODS ============

    def createPIDInfo(self, info):
        """Create PID information string"""
        try:
            vpid = info.getInfo(iServiceInformation.sVideoPID)
            apid = info.getInfo(iServiceInformation.sAudioPID)
            pcrpid = info.getInfo(iServiceInformation.sPCRPID)
            sidpid = info.getInfo(iServiceInformation.sSID)
            tsid = info.getInfo(iServiceInformation.sTSID)
            onid = info.getInfo(iServiceInformation.sONID)
        except:
            return ""
        
        vpid = max(0, vpid if vpid is not None else -1)
        apid = max(0, apid if apid is not None else -1)
        pcrpid = max(0, pcrpid if pcrpid is not None else -1)
        sidpid = max(0, sidpid if sidpid is not None else -1)
        tsid = max(0, tsid if tsid is not None else -1)
        onid = max(0, onid if onid is not None else -1)
        
        return "%d-%d:%05d:%04d:%04d:%04d" % (onid, tsid, sidpid, vpid, apid, pcrpid)

    # ============ SERVICE METHODS ============

    def createProviderName(self, info):
        """Get provider name"""
        try:
            provider = info.getInfoString(iServiceInformation.sProvider)
            if provider:
                provider = self._safe_str(provider, "")
                if not provider and self.is_iptv:
                    return self.iptv_host or ""
                return provider
        except:
            pass
        return ""

    def createServiceRef(self, info):
        """Get service reference"""
        try:
            ref = info.getInfoString(iServiceInformation.sServiceref)
            return self._safe_str(ref, "") if ref else ""
        except:
            return ""

    # ============ TRANSPONDER METHODS ============

    def createTransponderInfo(self, fedata, feraw, info):
        """Create transponder information"""
        if self.is_iptv:
            return self.iptv_url if self.iptv_url else self.iptv_host or ""
            
        if not feraw:
            refstr = info.getInfoString(iServiceInformation.sServiceref)
            if refstr and "%3a//" in refstr.lower():
                return refstr.split(":")[10].replace("%3a", ":").replace("%3A", ":")
            return ""
            
        tuner_type = self._safe_str(feraw.get("tuner_type", ""))
        if "DVB-T" in tuner_type:
            tmp = (addspace(self.createChannelNumber(fedata, feraw)) + 
                   addspace(self.createFrequency(fedata)) + 
                   addspace(self.createPolarization(fedata)))
        else:
            tmp = addspace(self.createFrequency(fedata)) + addspace(self.createPolarization(fedata))
            
        return (addspace(self.createTunerSystem(fedata)) + tmp + 
                addspace(self.createSymbolRate(fedata, feraw)) + 
                addspace(self.createFEC(fedata, feraw)) +
                addspace(self.createModulation(fedata)) + 
                addspace(self.createOrbPos(feraw)) + 
                addspace(self.createMisPls(fedata)))

    def createFrequency(self, fedata):
        """Get frequency"""
        try:
            frequency = fedata.get("frequency")
            if frequency:
                if frequency > 1000000:
                    return "%d %s" % (int(frequency // 1000000.0 + 0.5), _("MHz"))
                return str(frequency)
        except:
            pass
        return ""

    def createChannelNumber(self, fedata, feraw):
        """Get terrestrial channel number"""
        try:
            tuner_type = self._safe_str(feraw.get("tuner_type", ""))
            if "DVB-T" in tuner_type:
                channel = fedata.get("channel")
                return self._safe_str(channel, "") if channel else ""
        except:
            pass
        return ""

    def createSymbolRate(self, fedata, feraw):
        """Get symbol rate"""
        try:
            tuner_type = self._safe_str(feraw.get("tuner_type", ""))
            if "DVB-T" in tuner_type:
                bandwidth = fedata.get("bandwidth")
                return self._safe_str(bandwidth, "") if bandwidth else ""
            else:
                symbolrate = fedata.get("symbol_rate")
                if symbolrate:
                    return str(symbolrate // 1000)
        except:
            pass
        return ""

    def createPolarization(self, fedata):
        """Get polarization"""
        try:
            pol = fedata.get("polarization_abbreviation")
            return self._safe_str(pol, "") if pol else ""
        except:
            return ""

    def createFEC(self, fedata, feraw):
        """Get FEC information"""
        try:
            tuner_type = self._safe_str(feraw.get("tuner_type", ""))
            if "DVB-T" in tuner_type:
                code_rate_lp = fedata.get("code_rate_lp")
                code_rate_hp = fedata.get("code_rate_hp")
                guard_interval = fedata.get("guard_interval")
                if code_rate_lp and code_rate_hp and guard_interval:
                    return self._safe_str(code_rate_lp) + "-" + self._safe_str(code_rate_hp) + "-" + self._safe_str(guard_interval)
            else:
                fec = fedata.get("fec_inner")
                if fec:
                    return self._safe_str(fec, "")
        except:
            pass
        return ""

    def createModulation(self, fedata):
        """Get modulation"""
        try:
            tuner_type = self._safe_str(fedata.get("tuner_type", ""))
            if tuner_type == _("Terrestrial") or tuner_type == "Terrestrial":
                constellation = fedata.get("constellation")
                if constellation:
                    return self._safe_str(constellation, "")
            else:
                modulation = fedata.get("modulation")
                if modulation:
                    return self._safe_str(modulation, "")
        except:
            pass
        return ""

    def createTunerType(self, feraw):
        """Get tuner type"""
        try:
            tuner_type = feraw.get("tuner_type")
            return self._safe_str(tuner_type, "") if tuner_type else ""
        except:
            return ""

    def createTunerSystem(self, fedata):
        """Get tuner system"""
        try:
            system = fedata.get("system")
            return self._safe_str(system, "") if system else ""
        except:
            return ""

    def createOrbPos(self, feraw):
        """Get orbital position"""
        try:
            orbpos = feraw.get("orbital_position")
            if orbpos:
                if orbpos > 1800:
                    return _("%.1f° W") % ((3600 - orbpos) / 10.0)
                elif orbpos > 0:
                    return _("%.1f° E") % (orbpos / 10.0)
        except:
            pass
        return ""

    def createOrbPosOrTunerSystem(self, fedata, feraw):
        """Get orbital position or tuner system"""
        orbpos = self.createOrbPos(feraw)
        if orbpos != "":
            return orbpos
        return self.createTunerSystem(fedata)

    def createTransponderName(self, feraw):
        """Get transponder/satellite name"""
        try:
            orbpos = feraw.get("orbital_position")
            if orbpos is None:
                return ""
            if orbpos > 1800:
                return _("%.1f° W") % ((3600 - orbpos) / 10.0)
            elif orbpos > 0:
                return _("%.1f° E") % (orbpos / 10.0)
        except:
            pass
        return ""

    def createMisPls(self, fedata):
        """Create MIS/PLS information"""
        if not fedata:
            return ""
        tmp = ""
        
        is_id = fedata.get("is_id")
        if is_id is not None and is_id > -1:
            tmp = "MIS %d" % is_id
            
        pls_mode = fedata.get("pls_mode")
        pls_code = fedata.get("pls_code")
        if pls_code is not None and pls_code > 0:
            tmp = addspace(tmp) + "%s %d" % (self._safe_str(pls_mode, ""), pls_code)
            
        t2mi_plp_id = fedata.get("t2mi_plp_id")
        t2mi_pid = fedata.get("t2mi_pid")
        if t2mi_plp_id is not None and t2mi_plp_id > -1:
            tmp = addspace(tmp) + "T2MI %d PID %d" % (t2mi_plp_id, t2mi_pid)
            
        return tmp

    # ============ MAIN METHODS ============

    @cached
    def getText(self):
        """Main getText method"""
        service = self.source.service
        if service is None:
            return ""
        info = service and service.info()

        if not info:
            return ""

        try:
            try:
                show_crypto = int(config.usage.show_cryptoinfo.value) > 0
            except:
                show_crypto = False

            self.getCryptoInfo(info)

            # === IPTV TYPES ===
            if self.type == "IPTVInfo":
                return self.createIPTVInfo(info)
            if self.type == "IPTVUrl":
                return self.createIPTVUrl(info)
            if self.type == "IPTVStreamType":
                return self.createIPTVStreamType(info)
            if self.type == "IPTVHost":
                return self.createIPTVHost(info)

            # === CRYPTO TYPES ===
            if self.type == "CryptoInfo":
                if show_crypto:
                    return addspace(self.createCryptoBar(info)) + self.createCryptoSpecial(info)
                else:
                    return addspace(self.createCryptoBar(info)) + addspace(self.current_source) + self.createCryptoSpecial(info)

            if self.type == "CurrentCrypto":
                return self.createCurrentCaidLabel(info)

            if self.type == "CryptoBar":
                return self.createCryptoBar(info)

            if self.type == "CryptoSpecial":
                return self.createCryptoSpecial(info)

            if self.type == "CryptoNameCaid":
                return self.createCryptoNameCaid(info)

            # === VIDEO TYPES ===
            if self.type == "Resolution":
                return self.createResolution(info)

            if self.type == "ResolutionString":
                return addspace(self.createResolution(info)) + self.createGamma(info)

            if self.type == "VideoCodec":
                return self.createVideoCodec(info)

            if self.type == "Gamma":
                return self.createGamma(info)

            # Update frontend data
            if self.updateFEdata:
                self.updateFEdata = False
                feinfo = service.frontendInfo()
                if feinfo:
                    try:
                        source_value = config.usage.infobar_frontend_source.value
                        if isinstance(source_value, bytes):
                            source_value = source_value.decode('utf-8', errors='ignore')
                        self.feraw = feinfo.getAll(source_value == "settings")
                        if self.feraw:
                            self.fedata = ConvertToHumanReadable(self.feraw)
                    except:
                        pass

            # Get transponder data
            feraw = self.feraw
            if not feraw:
                try:
                    feraw = info.getInfoObject(iServiceInformation.sTransponderData)
                    if feraw:
                        self.fedata = ConvertToHumanReadable(feraw)
                    else:
                        self.fedata = None
                except:
                    self.fedata = None
            else:
                if self.fedata is None:
                    try:
                        self.fedata = ConvertToHumanReadable(feraw)
                    except:
                        self.fedata = {}

            fedata = self.fedata

            # === ALL - IPTV: Codec/Resolution first, URL below ===
            if self.type == "All":
                if self.is_iptv:
                    provider = self.createProviderName(info)
                    codec = self.createVideoCodec(info)
                    resolution = self.createResolution(info)
                    gamma = self.createGamma(info)
                    iptv_display = self.iptv_url if self.iptv_url else self.iptv_host
                    
                    first_line = addspace(provider) + addspace(codec) + addspace(resolution) + gamma
                    second_line = iptv_display
                    
                    return first_line + "\n" + second_line
                    
                elif show_crypto:
                    return (addspace(self.createProviderName(info)) + 
                            self.createTransponderInfo(fedata, feraw, info) + "\n" +
                            addspace(self.createCryptoBar(info)) + 
                            addspace(self.createCryptoSpecial(info)) + "\n" +
                            addspace(self.createPIDInfo(info)) + 
                            addspace(self.createVideoCodec(info)) + 
                            addspace(self.createResolution(info)) + 
                            self.createGamma(info))
                else:
                    return (addspace(self.createProviderName(info)) + 
                            self.createTransponderInfo(fedata, feraw, info) + "\n" +
                            addspace(self.createCryptoBar(info)) + 
                            self.current_source + "\n" +
                            addspace(self.createCryptoSpecial(info)) + 
                            addspace(self.createVideoCodec(info)) + 
                            addspace(self.createResolution(info)) + 
                            self.createGamma(info))

            # === PID ===
            if self.type == "PIDInfo":
                return self.createPIDInfo(info)

            # === SERVICE INFO - IPTV: Codec/Resolution first, then URL ===
            if self.type == "ServiceInfo":
                if self.is_iptv:
                    provider = self.createProviderName(info)
                    codec = self.createVideoCodec(info)
                    resolution = self.createResolution(info)
                    gamma = self.createGamma(info)
                    iptv_display = self.iptv_url if self.iptv_url else self.iptv_host
                    
                    return addspace(provider) + addspace(codec) + addspace(resolution) + gamma + " " + iptv_display
                    
                return (addspace(self.createProviderName(info)) + 
                        addspace(self.createTunerSystem(fedata)) + 
                        addspace(self.createFrequency(fedata)) + 
                        addspace(self.createPolarization(fedata)) +
                        addspace(self.createSymbolRate(fedata, feraw)) + 
                        addspace(self.createFEC(fedata, feraw)) + 
                        addspace(self.createModulation(fedata)) + 
                        addspace(self.createOrbPos(feraw)) +
                        addspace(self.createTransponderName(feraw)) +
                        addspace(self.createVideoCodec(info)) + 
                        addspace(self.createResolution(info)) + 
                        self.createGamma(info))

            # === SERVICE REF ===
            if self.type == "ServiceRef":
                return self.createServiceRef(info)

            # === PROVIDER ===
            if self.type == "ProviderName":
                return self.createProviderName(info)

            if not feraw:
                if self.is_iptv:
                    return self.iptv_url if self.iptv_url else self.iptv_host
                return ""

            # === TRANSPONDER TYPES ===
            if self.type == "TransponderInfo":
                return self.createTransponderInfo(fedata, feraw, info)

            if self.type == "TransponderFrequency":
                return self.createFrequency(fedata)

            if self.type == "TransponderSymbolRate":
                return self.createSymbolRate(fedata, feraw)

            if self.type == "TransponderPolarization":
                return self.createPolarization(fedata)

            if self.type == "TransponderFEC":
                return self.createFEC(fedata, feraw)

            if self.type == "TransponderModulation":
                return self.createModulation(fedata)

            if self.type == "OrbitalPosition":
                return self.createOrbPos(feraw)

            if self.type == "TunerType":
                return self.createTunerType(feraw)

            if self.type == "TunerSystem":
                return self.createTunerSystem(fedata)

            if self.type == "OrbitalPositionOrTunerSystem":
                return self.createOrbPosOrTunerSystem(fedata, feraw)

            if self.type == "TerrestrialChannelNumber":
                return self.createChannelNumber(fedata, feraw)

            if self.type == "TransponderInfoMisPls":
                return self.createMisPls(fedata)

            if self.type == "TransponderName":
                return self.createTransponderName(feraw)

            return _("invalid type")
            
        except Exception as e:
            return "FTA"

    text = property(getText)

    @cached
    def getBool(self):
        """Get boolean value for crypto indicators"""
        try:
            service = self.source.service
            info = service and service.info()

            if not info:
                return False

            request_caid = None
            request_selected = None
            for x in self.ca_table:
                if x[0] == self.type:
                    request_caid = x[1]
                    request_selected = x[2]
                    break

            if request_caid is None:
                return False

            if info.getInfo(iServiceInformation.sIsCrypted) != 1:
                return False

            data = self.ecmdata.getEcmData()
            if data is None or len(data) < 2:
                return False

            current_caid = self._safe_str(data[1], "0")
            current_caid_int = self._safe_int(current_caid, 0)

            try:
                available_caids = info.getInfoObject(iServiceInformation.sCAIDs)
            except:
                available_caids = []

            for caid_entry in caid_data:
                if caid_entry[3] == request_caid:
                    if request_selected:
                        start_caid = self._safe_int(caid_entry[0], 0)
                        end_caid = self._safe_int(caid_entry[1], 0)
                        if start_caid <= current_caid_int <= end_caid:
                            return True
                    else:
                        try:
                            if available_caids:
                                for caid in available_caids:
                                    caid_int = self._safe_int(caid, 0)
                                    start_caid = self._safe_int(caid_entry[0], 0)
                                    end_caid = self._safe_int(caid_entry[1], 0)
                                    if start_caid <= caid_int <= end_caid:
                                        return True
                        except:
                            pass

            return False
        except:
            return False

    boolean = property(getBool)

    def changed(self, what):
        """Handle change events"""
        try:
            if what[0] == self.CHANGED_SPECIFIC:
                self.updateFEdata = False
                if what[1] == iPlayableService.evNewProgramInfo:
                    self.updateFEdata = True
                if what[1] == iPlayableService.evEnd:
                    self.feraw = None
                    self.fedata = None
                Converter.changed(self, what)
            elif what[0] == self.CHANGED_POLL and self.updateFEdata is not None:
                self.updateFEdata = False
                Converter.changed(self, what)
        except:
            pass
