#pragma once

#include <EGL/dreameglplatform.h>
#include <lib/gdi/egl/inative_window_provider.h>

// EGL native-pixmap provider for Dreambox's VC5/BEGL stack (libvc5dream.so /
// libv3ddriver.so). This platform only implements eglCreatePlatformPixmapSurfaceEXT
// with a struct dmegl_pixmap_handle (see EGL/dreameglplatform.h, shipped by
// Dream Property GmbH in the libvc5dream-dev package) - there is no fbdev_window
// or other native-window surface type here, unlike the Amlogic/Mali-fbdev backend.
//
// Rather than allocating a separate offscreen pixmap and then needing an
// undocumented ioctl to composite it onto the visible display, this provider
// describes the *existing* framebuffer memory (the same one fbClass/gFBDC
// already renders the CPU/2D path into) as a set of pixmaps, one per page
// fbClass::SetMode() actually allocated (typically 3, for triple buffering -
// see fb.cpp). gEGLDC creates one EGLSurface per page and ping-pongs
// rendering between them (see gEGLDC::flip()), panning the display
// (FBIOPAN_DISPLAY, via fbClass::setOffset()) to whichever page a frame just
// finished rendering into.
class DreamboxWindowProvider : public INativeWindowProvider {
private:
	static const int kMaxPages = 3;
	dmegl_pixmap_handle m_pixmaps[kMaxPages];
	int m_page_count;
	int m_height; // page N's scanout line offset is N * m_height (see presentPixmap())
	unsigned long m_page_bytes; // one page's size in bytes (see copyPageContent())

public:
	DreamboxWindowProvider();
	virtual ~DreamboxWindowProvider();

	// INativeWindowProvider
	bool init(int width, int height) override;
	EGLNativeDisplayType getNativeDisplay() override;
	bool usesPixmapSurface() const override { return true; }
	// Proven true - the display controller on this SoC reads GL-rendered
	// pixel bytes with R and B swapped relative to what GL wrote. Two
	// independent observations established this:
	//
	//  1. The original ground-truth debug swatch (still present as
	//     debugSwatch()) said "does NOT swap", because glReadPixels reads
	//     back through the same EGL surface GL wrote to, so the scanout
	//     swap happens *downstream* of the read and cancels on the round
	//     trip. That result was misleading - the swatch cannot detect a
	//     scanout quirk by construction.
	//
	//  2. When this method was temporarily flipped to false, every solid
	//     colour drawn to the screen came out R/B swapped: the PLi skin's
	//     red "All" button rendered as blue, yellow "Provider" as cyan,
	//     yellow EPG titles as cyan, etc. Setting it back to true makes
	//     them all correct.
	//
	// So every solid-colour fragment shader must pre-swap its output (see
	// the u_rbswap uniform in gshader.cpp, gadvanced_shader.cpp,
	// gtext_shader.cpp), and every 32bpp enigma2 pixmap upload must
	// declare the memory as GL_RGBA (a pre-swap that cancels the scanout
	// swap on the way out - see gtexture_manager.cpp and
	// gegldc.cpp's uploadOverlayBand()).
	bool needsRenderTargetRBSwap() const override { return true; }
	int getPageCount() const override { return m_page_count; }
	void* getNativePixmap(int page) override;
	void presentPixmap(int page) override;
	void copyPageContent(int from, int to) override;
	void cleanup() override;

	// Diagnostic only (ENIGMA_EGL_DEBUG_SWATCH=1) - see the definition's
	// comment. Called by gEGLDC::initEGL() once, after the EGL context is
	// current. Logs the GL round-trip of a known colour; see the method's
	// own comment for why this cannot detect a *scanout* R/B swap (only a
	// GL-internal one). Kept as a sanity check that GL itself is
	// straight-through; not a proof of scanout behaviour.
	void debugSwatch();
};
