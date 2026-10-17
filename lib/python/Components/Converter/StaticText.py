from Components.Converter.Converter import Converter


class StaticText(Converter):
	def __init__(self, text):
		Converter.__init__(self, text)
		self.text = str(text)
