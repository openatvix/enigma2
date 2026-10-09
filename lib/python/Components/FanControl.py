import os
import re

from Components.config import config, ConfigSubList, ConfigSubsection, ConfigSlider
from Tools.BoundFunction import boundFunction
import NavigationInstance
from enigma import iRecordableService


class FanControl:
	def __init__(self):
		if os.path.exists("/proc/stb/fp/fan_vlt") or os.path.exists("/proc/stb/fp/fan_pwm") or os.path.exists("/proc/stb/fp/fan_speed"):
			self.fancount = 1
		else:
			self.fancount = 0
		self.createConfig()
		config.misc.standbyCounter.addNotifier(self.standbyCounterChanged, initial_call=False)

	def setVoltage_PWM(self):
		for fanid in range(self.getFanCount()):
			cfg = self.getConfig(fanid)
			self.setVoltage(fanid, cfg.vlt.value)
			self.setPWM(fanid, cfg.pwm.value)
			print("[FanControl]: setting fan values: fanid = %d, voltage = %d, pwm = %d" % (fanid, cfg.vlt.value, cfg.pwm.value))

	def setVoltage_PWM_Standby(self):
		for fanid in range(self.getFanCount()):
			cfg = self.getConfig(fanid)
			self.setVoltage(fanid, cfg.vlt_standby.value)
			self.setPWM(fanid, cfg.pwm_standby.value)
			print("[FanControl]: setting fan values (standby mode): fanid = %d, voltage = %d, pwm = %d" % (fanid, cfg.vlt_standby.value, cfg.pwm_standby.value))

	def getRecordEvent(self, recservice, event):
		recordings = len(NavigationInstance.instance.getRecordings())
		if event == iRecordableService.evEnd:
			if recordings == 0:
				self.setVoltage_PWM_Standby()
		elif event == iRecordableService.evStart:
			if recordings == 1:
				self.setVoltage_PWM()

	def leaveStandby(self):
		NavigationInstance.instance.record_event.remove(self.getRecordEvent)
		recordings = NavigationInstance.instance.getRecordings()
		if not recordings:
			self.setVoltage_PWM()

	def standbyCounterChanged(self, configElement):
		from Screens.Standby import inStandby
		inStandby.onClose.append(self.leaveStandby)
		recordings = NavigationInstance.instance.getRecordings()
		NavigationInstance.instance.record_event.append(self.getRecordEvent)
		if not recordings:
			self.setVoltage_PWM_Standby()

	def createConfig(self):
		def setVlt(fancontrol, fanid, configElement):
			fancontrol.setVoltage(fanid, configElement.value)

		def setPWM(fancontrol, fanid, configElement):
			fancontrol.setPWM(fanid, configElement.value)

		config.fans = ConfigSubList()
		for fanid in range(self.getFanCount()):
			fan = ConfigSubsection()
			fan.vlt = ConfigSlider(default=15, increment=5, limits=(0, 255))
			fan.pwm = ConfigSlider(default=0, increment=5, limits=(0, 255))
			fan.vlt_standby = ConfigSlider(default=5, increment=5, limits=(0, 255))
			fan.pwm_standby = ConfigSlider(default=0, increment=5, limits=(0, 255))
			fan.vlt.addNotifier(boundFunction(setVlt, self, fanid))
			fan.pwm.addNotifier(boundFunction(setPWM, self, fanid))
			config.fans.append(fan)

	def getConfig(self, fanid):
		return config.fans[fanid]

	def getFanCount(self):
		return self.fancount

	def hasRPMSensor(self, fanid):
		return os.path.exists("/proc/stb/fp/fan_speed")

	def hasFanControl(self, fanid):
		return os.path.exists("/proc/stb/fp/fan_vlt") or os.path.exists("/proc/stb/fp/fan_pwm")

	def getFanSpeed(self, fanid):
		try:
			with open("/proc/stb/fp/fan_speed", "r") as f:
				data = f.readline().strip()
				if not data:
					return 0
				# Extract numeric value using regex (handles "1234 RPM", "1234", "1234rpm", etc.)
				match = re.search(r'(\d+)', data)
				if match:
					return int(match.group(1))
				return 0
		except (IOError, OSError, ValueError):
			return 0

	def getVoltage(self, fanid):
		try:
			with open("/proc/stb/fp/fan_vlt", "r") as f:
				data = f.readline().strip()
				if data:
					return int(data, 16)
				return 0
		except (IOError, OSError, ValueError):
			return 0

	def setVoltage(self, fanid, value):
		if value > 255 or value < 0:
			return
		try:
			with open("/proc/stb/fp/fan_vlt", "w") as f:
				f.write("%x" % value)
		except (IOError, OSError):
			pass

	def getPWM(self, fanid):
		try:
			with open("/proc/stb/fp/fan_pwm", "r") as f:
				data = f.readline().strip()
				if data:
					return int(data, 16)
				return 0
		except (IOError, OSError, ValueError):
			return 0

	def setPWM(self, fanid, value):
		if value > 255 or value < 0:
			return
		try:
			with open("/proc/stb/fp/fan_pwm", "w") as f:
				f.write("%x" % value)
		except (IOError, OSError):
			pass


fancontrol = FanControl()
