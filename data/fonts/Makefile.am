#
# WARNING: If you modify the files installed here, change the version
# number of the enigma2-fonts package in enigma2.bb.
#
installdir = $(datadir)/fonts

dist_install_DATA = \
	ae_AlMateen.ttf \
	andale.ttf \
	DejaVuSans.ttf \
	lcd.ttf \
	LiberationSans-BoldItalic.ttf \
	LiberationSans-Bold.ttf \
	LiberationSans-Italic.ttf \
	LiberationSans-Regular.ttf \
	md_khmurabi_10.ttf \
	nmsbd.ttf \
	NotoNaskhArabic-Regular.ttf
	Roboto-BlackItalic.ttf \
	Roboto-Black.ttf \
	Roboto-BoldItalic.ttf \
	Roboto-Bold.ttf \
	valis_enigma.ttf \
	wqy-microhei.ttc

install-data-hook:
	cd $(DESTDIR)$(datadir)/fonts && \
	$(LN_S) wqy-microhei.ttc fallback.font
