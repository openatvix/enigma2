#include <lib/base/eerror.h>
#include <lib/gdi/egl/platform/dreambox/dreambox_window_provider.h>
#include <lib/gdi/fb.h>

#include <cstring>
#include <cstdlib>
#include <cstdint>

#ifdef HAVE_GLES3
#include <GLES3/gl3.h>
#else
#include <GLES2/gl2.h>
#endif

// drm/drm_fourcc.h's DRM_FORMAT_ABGR8888. A diagnostic pass (comparing
// known-good source-image RGB values against the bytes actually handed to
// glTexImage2D/glTexSubImage2D for both text and picon uploads) proved the
// GPU texture pipeline puts the right byte in the right place every time -
// so the visible R/B swap users saw was never in texture uploads at all.
// This is the one remaining untested link: it tells the vendor's native-
// pixmap EGL surface how to interpret the live scanout framebuffer memory
// that GL renders directly into and the display controller reads from.
// ARGB8888 (memory order B,G,R,A) matched gTextureManager's own BGRA
// assumption for enigma2 surfaces, but that's a fact about *enigma2's* CPU
// pixmaps, not about what this SoC's display plane actually expects -
// several Broadcom-based STB graphics stacks are known to swap R/B in their
// hardware compositor's native order. Try ABGR8888 (memory order R,G,B,A).
#define DRM_FORMAT_ABGR8888 0x34324241

DreamboxWindowProvider::DreamboxWindowProvider() : m_page_count(1), m_height(0), m_page_bytes(0) {
	memset(m_pixmaps, 0, sizeof(m_pixmaps));
}

DreamboxWindowProvider::~DreamboxWindowProvider() {
	cleanup();
}

bool DreamboxWindowProvider::init(int width, int height) {
	fbClass* fb = fbClass::getInstance();
	if (!fb) {
		// gFBDC (the classic gDC) is not built when EGL is enabled (see
		// lib/gdi/Makefile.inc) - it used to be the sole owner of fbClass's
		// construction (gFBDC::gFBDC() does "fb = new fbClass;"), so we take
		// over that responsibility here since we're now the sole consumer of
		// the live framebuffer.
		fb = new fbClass;
		if (!fb) {
			eDebug("[DreamboxWindowProvider] failed to construct fbClass");
			return false;
		}
	}

	// fbClass only opens the device and reads the *boot-time* mode in its
	// constructor - stride is left uninitialized and lfb unmapped until
	// SetMode() actually programs the mode (this is what gFBDC::setResolution()
	// normally does; gFBDC is not built when EGL is enabled, so we do it here).
	if (fb->SetMode(width, height, 32) < 0) {
		eDebug("[DreamboxWindowProvider] fbClass::SetMode(%dx%d) failed", width, height);
		return false;
	}

	m_height = height;

	// fbClass::SetMode() allocates fb->getNumPages() pages stacked in one
	// mmap'd virtual framebuffer (fb->lfb, offset 0 = page 0's base) - describe
	// each as its own pixmap so gEGLDC can create one EGLSurface per page and
	// ping-pong rendering between them (see gEGLDC::flip()/tryInitEGL())
	// instead of always rendering into (and therefore visibly drawing into)
	// whichever page is currently on screen - see the class comment.
	m_page_count = fb->getNumPages();
	if (m_page_count < 1)
		m_page_count = 1;
	if (m_page_count > kMaxPages)
		m_page_count = kMaxPages;

	m_page_bytes = (unsigned long)fb->Stride() * (unsigned long)height;
	for (int i = 0; i < m_page_count; ++i) {
		m_pixmaps[i].mem.magic = DMEGL_PIXMAP_MAGIC;
		m_pixmaps[i].mem.length = m_page_bytes;
		m_pixmaps[i].mem.offset = 0;
		m_pixmaps[i].mem.fd = -1; // no separate fd: addr is already mapped below
		m_pixmaps[i].mem.phys = (uintptr_t)fb->getPhysAddr() + (uintptr_t)i * m_page_bytes;
		m_pixmaps[i].mem.addr = fb->lfb + (size_t)i * m_page_bytes;

		m_pixmaps[i].width = (unsigned int)width;
		m_pixmaps[i].height = (unsigned int)height;
		m_pixmaps[i].pitch = fb->Stride();
		m_pixmaps[i].format = DRM_FORMAT_ABGR8888;
	}

	// Show page 0 initially - gEGLDC starts rendering into a *different*
	// page (see its m_render_page initialization in tryInitEGL()) so the
	// very first frame never renders into what's simultaneously on screen.
	fb->setOffset(0);

	eDebug("[DreamboxWindowProvider] init %dx%d pitch=%u pages=%d phys=0x%lx", width, height, m_pixmaps[0].pitch, m_page_count, (unsigned long)m_pixmaps[0].mem.phys);
	return true;
}

// Diagnostic one-shot: draw a known (1,0,0,1) quad into the first page
// through the SAME shader path the real renderer uses, read it back with
// glReadPixels, and log what the framebuffer actually contains. This is the
// only way to tell whether this SoC's scanout really swaps R/B from what GL
// writes (the hypothesis behind needsRenderTargetRBSwap() == true and the
// per-shader mix(c, c.bgra, u_rbswap) compensation), or whether that
// compensation is what's actually CAUSING a swap that shouldn't exist.
//
// Called by gEGLDC::initEGL() (see gles_version.h's needsRBSwap comment) so
// the EGL context/surface are already current when this runs. Requires an
// EGL surface for page 0 to be bound as the draw target; if not, does
// nothing and returns. Logs (never throws, never asserts): this is
// diagnostic-only, gated by ENIGMA_EGL_DEBUG_SWATCH=1.
//
// Interpretation of the log line:
//   "readback R=255 G=0 B=0"  -> scanout does NOT swap. Set
//                                needsRenderTargetRBSwap() to false, and
//                                change gtexture_manager.cpp back to
//                                GL_BGRA_EXT. The per-shader swap should
//                                then stay (it makes the *output* R=255
//                                reach scanout as R, given a non-swapping
//                                scanout) - i.e. the shaders were right,
//                                the provider override was wrong.
//   "readback R=0 G=0 B=255"  -> scanout DOES swap. Keep the provider
//                                override true, and REMOVE the per-shader
//                                mix(c, c.bgra, u_rbswap) compensation
//                                (currently double-swapping on top of the
//                                provider's own compensation for textured
//                                draws - see the review notes).
//
// Run once on the box, read the log, then delete this whole method and its
// call site - it is not meant to ship enabled.
void DreamboxWindowProvider::debugSwatch() {
	// TEMPORARY: unconditional for one diagnostic build - revert to
	// getenv("ENIGMA_EGL_DEBUG_SWATCH") before committing.

	// A known-value draw through the *simplest* possible path: no shader,
	// no texture, no blend, no projection matrix - glClear() the page to
	// solid red, then read one pixel back.
	glBindFramebuffer(GL_FRAMEBUFFER, 0);
	glDisable(GL_SCISSOR_TEST);
	glClearColor(1.0f, 0.0f, 0.0f, 1.0f);
	glClear(GL_COLOR_BUFFER_BIT);
	glFinish();

	uint8_t px[4] = {0, 0, 0, 0};
	glReadPixels(0, 0, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, px);
	const GLenum err = glGetError();

	eDebug("[DreamboxWindowProvider] DEBUG SWATCH: wrote (R=255,G=0,B=0) via glClearColor+glClear, "
	       "readback R=%u G=%u B=%u A=%u glError=0x%x",
	       px[0], px[1], px[2], px[3], (unsigned)err);

	if (err == GL_NO_ERROR) {
		if (px[0] > 200 && px[2] < 50) {
			eDebug("[DreamboxWindowProvider] DEBUG SWATCH verdict: scanout does NOT swap R/B "
			       "-> set needsRenderTargetRBSwap() to false and revert gtexture_manager.cpp to GL_BGRA_EXT");
		} else if (px[2] > 200 && px[0] < 50) {
			eDebug("[DreamboxWindowProvider] DEBUG SWATCH verdict: scanout DOES swap R/B "
			       "-> keep needsRenderTargetRBSwap() true and remove the per-shader u_rbswap compensation");
		} else {
			eDebug("[DreamboxWindowProvider] DEBUG SWATCH verdict: inconclusive (readback not pure red or blue) "
			       "- try again after a real frame has been drawn, or check whether GL_RGBA is supported for glReadPixels on this driver");
		}
	}
}

EGLNativeDisplayType DreamboxWindowProvider::getNativeDisplay() {
	return EGL_DEFAULT_DISPLAY;
}

void* DreamboxWindowProvider::getNativePixmap(int page) {
	if (page < 0 || page >= m_page_count)
		return nullptr;
	return &m_pixmaps[page];
}

void DreamboxWindowProvider::presentPixmap(int page) {
	// TEST: the glReadPixels forced-copy that used to live here was added
	// based on a readback diagnostic captured *before* the gRC-thread EGL
	// context-affinity fix (see grc.cpp/egl_init.cpp) - at that time NOTHING
	// rendered at all (viewport was (0,0,0,0)), so of course the native
	// "driver writes directly into the described pixmap memory" mechanism
	// looked broken. That was a symptom of the real bug, not proof this path
	// is bad. Now that rendering actually happens on the correct thread with
	// a correct viewport, trust the vendor's native pixmap-surface write
	// mechanism again and just wait for completion - glReadPixels may have
	// been misinterpreting this GPU's internal tiled/compressed render
	// target layout as plain linear memory, which would explain banding.
	glFinish();

	// Multi-page: page just finished rendering (and, per glFinish() above,
	// is actually done) - pan the display to it. Single-page (m_page_count
	// == 1, e.g. this platform's fbdev only granted one buffer): nothing to
	// pan between, same as the old behavior.
	if (m_page_count > 1) {
		fbClass* fb = fbClass::getInstance();
		if (fb) {
			// Wait for vsync BEFORE panning, not after: FBIOPAN_DISPLAY takes
			// effect relative to whatever point in the scan cycle it's
			// issued at, so panning at an arbitrary moment can apply
			// mid-scan and tear the frame between the old and new page.
			// This is the same wait-then-pan order gfbdc.cpp's classic 2D
			// path uses for gOpcode::flush's CONFIG_ION branch.
			fb->waitVSync();
			fb->setOffset(page * m_height);
		}
	}
}

void DreamboxWindowProvider::copyPageContent(int from, int to) {
	if (from < 0 || from >= m_page_count || to < 0 || to >= m_page_count || from == to || m_page_bytes == 0)
		return;

	// Plain CPU memcpy between two pages of the same mmap'd framebuffer -
	// both are already the "trust this as plain linear memory" pixmap
	// representation this whole provider relies on (see the DRM_FORMAT_ABGR8888
	// comment above and presentPixmap()), so no GPU/EGL involvement is needed
	// or safe to assume here: `from` was already fully resolved by a prior
	// glFinish() (see presentPixmap()) before this is ever called, and `to`
	// has not been made the EGL draw target's *content* yet at this point in
	// gEGLDC::flip() (only eglMakeCurrent'd, no draws issued) - so this is the
	// first and only writer touching `to` this frame.
	memcpy(m_pixmaps[to].mem.addr, m_pixmaps[from].mem.addr, m_page_bytes);
}

void DreamboxWindowProvider::cleanup() {
	// Nothing to release: the framebuffer memory is owned by fbClass, not us.
}
