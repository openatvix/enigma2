from Components.Converter.Converter import Converter
from Components.Element import cached
from Components.Converter.Poll import Poll
from enigma import eConsoleAppContainer
import os


class PliExtra(Poll, Converter):
	TEMPERATURE = 0
	HDDTEMP = 1
	CPULOAD = 2
	CPUSPEED = 3
	FANINFO = 4
	UPTIME = 5

	def __init__(self, type):
		Converter.__init__(self, type)
		Poll.__init__(self)
		self.container = eConsoleAppContainer()
		type = type.split(",")
		self.short_list = True
		self.list = []
		self.shortFormat = "Short" in type
		if "CPULoad" in type:
			self.type = self.CPULOAD
		elif "CPUSpeed" in type:
			self.type = self.CPUSPEED
		elif "Temperature" in type:
			self.type = self.TEMPERATURE
		elif "Uptime" in type:
			self.type = self.UPTIME
		elif "HDDTemp" in type:
			self.type = self.HDDTEMP
			self.hddtemp_output = b""
			self.hddtemp = "Waiting for HDD Temp Data..."
			self.container.appClosed.append(self.runFinished)
			self.container.dataAvail.append(self.dataAvail)
			self.container.execute("hddtemp -n -q /dev/sda")
		elif "FanInfo" in type:
			self.type = self.FANINFO
		if "HDDTemp" in type:
			self.poll_interval = 500
		else:
			self.poll_interval = 7000
		self.poll_enabled = True

	def dataAvail(self, data):
		# Python 3.14: data can be bytes OR str depending on enigma2 build
		if isinstance(data, str):
			data = data.encode("utf-8", "ignore")
		if isinstance(self.hddtemp_output, str):
			self.hddtemp_output = self.hddtemp_output.encode("utf-8", "ignore")
		self.hddtemp_output += data

	def runFinished(self, retval):
		if not self.hddtemp_output:
			self.hddtemp = "HDD Temp: N/A"
			return
		temp = self.hddtemp_output.decode("utf-8", "ignore").strip()
		if not temp or "No such file" in temp or "not found" in temp or "command not found" in temp:
			self.hddtemp = "HDD Temp: N/A"
			return
		try:
			t = int(temp)
		except (ValueError, TypeError):
			self.hddtemp = "HDD Temp: N/A"
			return
		if t > 0:
			self.hddtemp = "HDD Temp: %s\u00b0C" % t
		else:
			self.hddtemp = "HDD idle or N/A"
		self.hddtemp_output = b""

	def _read_file(self, path):
		try:
			with open(path, "r") as f:
				return f.read().strip()
		except Exception:
			return ""

	@cached
	def getText(self):
		if self.type == self.CPULOAD:
			load = self._read_file("/proc/loadavg")
			if load:
				cpuload = load[:4].replace("\n", "").replace(" ", "")
				return "CPU Load: %s" % cpuload
			return ""

		elif self.type == self.TEMPERATURE:
			systemp = ""
			cputemp = ""
			# --- DM920: /sys/class/thermal/thermal_zone0/temp is the only working source ---
			thermal = self._read_file("/sys/class/thermal/thermal_zone0/temp")
			if thermal:
				try:
					cputemp = "%d\u00b0C" % (int(thermal) // 1000)
				except (ValueError, TypeError):
					pass
			# Board/system temp (generic enigma2 paths)
			if not cputemp:
				val = self._read_file("/proc/stb/sensors/temp0/value")
				if val:
					systemp = "Sys Temp: %s\u00b0C" % val
				else:
					val = self._read_file("/proc/stb/fp/temp_sensor")
					if val:
						systemp = "Board: %s\u00b0C" % val
			# AVS sensor (DM920 has none, harmless fallback)
			if not cputemp:
				val = self._read_file("/proc/stb/fp/temp_sensor_avs")
				if val:
					cputemp = "%s\u00b0C" % val
			if systemp == "" and cputemp == "":
				return "Temperature: N/A"
			if systemp == "":
				return "CPU Temp: %s" % cputemp
			if cputemp == "":
				return systemp
			return "%s CPU: %s" % (systemp, cputemp)

		elif self.type == self.HDDTEMP:
			return self.hddtemp

		elif self.type == self.CPUSPEED:
			try:
				# Try /proc/cpuinfo first (some Broadcom builds expose "cpu MHz")
				cpuspeed = 0
				for line in self._read_file("/proc/cpuinfo").splitlines():
					parts = [x.strip() for x in line.split(":")]
					if len(parts) >= 2 and parts[0] == "cpu MHz":
						try:
							cpuspeed = "%1.0f" % float(parts[1])
						except (ValueError, TypeError):
							pass
				if not cpuspeed:
					# DM920: /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq -> 1719000
					freq = self._read_file("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq")
					if freq:
						try:
							cpuspeed = str(int(freq) // 1000)
						except (ValueError, TypeError):
							cpuspeed = "-"
					else:
						freq = self._read_file("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq")
						if freq:
							try:
								cpuspeed = str(int(freq) // 1000)
							except (ValueError, TypeError):
								cpuspeed = "-"
						else:
							cpuspeed = "-"
				return "CPU Speed: %s MHz" % cpuspeed
			except Exception:
				return ""

		if self.type == self.FANINFO:
			fs = self._read_file("/proc/stb/fp/fan_speed")
			fv_raw = self._read_file("/proc/stb/fp/fan_vlt")
			fp_raw = self._read_file("/proc/stb/fp/fan_pwm")
			fv = ""
			fp = ""
			try:
				if fv_raw:
					fv = str(int(fv_raw, 16))
			except (ValueError, TypeError):
				fv = ""
			try:
				if fp_raw:
					fp = str(int(fp_raw, 16))
			except (ValueError, TypeError):
				fp = ""
			if not fs:
				return "Fan Info: N/A"
			if self.shortFormat:
				return "%s - %sV - P:%s" % (fs, fv, fp)
			return "Speed: %s V: %s PWM: %s" % (fs, fv, fp)

		elif self.type == self.UPTIME:
			uptime_info = self._read_file("/proc/uptime").split()
			if not uptime_info:
				return "Uptime: N/A"
			try:
				total_seconds = float(uptime_info[0])
			except (ValueError, TypeError):
				return "Uptime: N/A"
			MINUTE = 60
			HOUR = MINUTE * 60
			DAY = HOUR * 24
			days = int(total_seconds // DAY)
			hours = int(total_seconds % DAY // HOUR)
			minutes = int(total_seconds % HOUR // MINUTE)
			seconds = int(total_seconds % MINUTE)
			uptime = ""
			if self.shortFormat:
				uptime = "%sd %sh %sm %ss" % (days, hours, minutes, seconds)
			else:
				if days > 0:
					uptime += "%d %s, " % (days, "day" if days == 1 else "days")
				if uptime or hours > 0:
					uptime += "%d %s, " % (hours, "hr" if hours == 1 else "hrs")
				if uptime or minutes > 0:
					uptime += "%d %s" % (minutes, "min" if minutes == 1 else "mins")
			return "Uptime: %s" % uptime

		return ""

	text = property(getText)

	def changed(self, what):
		if what[0] == self.CHANGED_POLL:
			self.downstream_elements.changed(what)
