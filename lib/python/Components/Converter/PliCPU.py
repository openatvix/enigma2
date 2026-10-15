from Components.Converter.Converter import Converter
from Components.Converter.Poll import Poll
from Components.Element import cached


class PliCPU(Converter, object):
	CPU_ALL = -2
	CPU_TOTAL = -1

	def __init__(self, type):
		Converter.__init__(self, type)
		self.percentlist = []
		self.pfmt = "%3d%%"
		if not type or type == "Total":
			self.type = self.CPU_TOTAL
			self.sfmt = "$0"
		elif len(type) == 1 and type[0].isdigit():
			self.type = int(type)
			self.sfmt = "$" + type
			self.pfmt = "%d"
		else:
			self.type = self.CPU_ALL
			self.sfmt = str(type)
			cpus = cpuUsageMonitor.getCpusCount()
			if cpus > -1:
				pos = 0
				while True:
					pos = self.sfmt.find("$", pos)
					if pos == -1:
						break
					if pos < len(self.sfmt) - 1 and self.sfmt[pos + 1].isdigit() and int(self.sfmt[pos + 1]) > cpus:
						self.sfmt = self.sfmt.replace("$" + self.sfmt[pos + 1], "")
					pos += 1

	def doSuspend(self, suspended):
		if suspended:
			cpuUsageMonitor.disconnectCallback(self.gotPercentage)
		else:
			cpuUsageMonitor.connectCallback(self.gotPercentage)

	def gotPercentage(self, list):
		self.percentlist = list
		self.changed((self.CHANGED_POLL,))

	@cached
	def getText(self):
		res = self.sfmt[:]
		if not self.percentlist:
			self.percentlist = [0] * 3
		for i in range(len(self.percentlist)):
			res = res.replace("$" + str(i), self.pfmt % self.percentlist[i])

		res = res.replace("$?", "%d" % (len(self.percentlist) - 1))
		return res

	@cached
	def getValue(self):
		if self.type in range(len(self.percentlist)):
			i = self.type
		else:
			i = 0
		try:
			value = self.percentlist[i]
		except IndexError:
			value = 0

		return value

	text = property(getText)
	value = property(getValue)
	range = 100


class CpuUsageMonitor(Poll, object):

	def __init__(self):
		Poll.__init__(self)
		self.__callbacks = []
		self.__curr_info = self.getCpusInfo()
		self.poll_interval = 1000

	def getCpusCount(self):
		return len(self.__curr_info) - 1

	def getCpusInfo(self):
		res = []
		try:
			with open("/proc/stat", "r") as fd:
				for l in fd:
					if l.find("cpu") == 0:
						tmp = l.split()
						# tmp = ['cpu', user, nice, system, idle, iowait, irq, softirq, steal, ...]
						# Need at least user..iowait -> 6 numbers, so len(tmp) >= 7
						if len(tmp) < 7:
							continue
						try:
							nums = [int(x) for x in tmp[1:]]
						except (ValueError, TypeError):
							continue
						total = sum(nums)
						# After dropping 'cpu' at index 0:
						#   nums[3] = idle, nums[4] = iowait
						busy = total - nums[3] - nums[4]
						res.append([tmp[0], total, busy])
		except Exception:
			pass
		return res

	def poll(self):
		prev_info, self.__curr_info = self.__curr_info, self.getCpusInfo()
		if len(self.__callbacks):
			info = []
			for i in range(len(self.__curr_info)):
				try:
					delta_total = self.__curr_info[i][1] - prev_info[i][1]
					delta_busy = self.__curr_info[i][2] - prev_info[i][2]
					if delta_total <= 0:
						p = 0
					else:
						p = (100 * delta_busy) // delta_total
						if p < 0:
							p = 0
						elif p > 100:
							p = 100
				except (ZeroDivisionError, IndexError):
					p = 0
				info.append(p)

			for f in self.__callbacks:
				f(info)

	def connectCallback(self, func):
		if func not in self.__callbacks:
			self.__callbacks.append(func)
		if not self.poll_enabled:
			self.poll()
			self.poll_enabled = True

	def disconnectCallback(self, func):
		if func in self.__callbacks:
			self.__callbacks.remove(func)
		if not len(self.__callbacks) and self.poll_enabled:
			self.poll_enabled = False


cpuUsageMonitor = CpuUsageMonitor()
