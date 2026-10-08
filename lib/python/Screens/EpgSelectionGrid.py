# -*- coding: utf-8 -*-
#
# OpenPLI compatibility shim for plugins expecting EpgSelectionGrid
#

from Screens.EpgSelection import EPGSelection


class EPGSelectionGrid(EPGSelection):
    """
    Compatibility wrapper to allow plugins requiring EpgSelectionGrid
    to run on images that only provide EPGSelection (like OpenPLI).
    """

    def __init__(self, session, *args, **kwargs):
        # Mark as non-grid for plugins that check this
        self.isGrid = False

        # Remove unsupported Grid-specific kwargs
        self._sanitize_kwargs(kwargs)

        # Init base class
        super(EPGSelectionGrid, self).__init__(session, *args, **kwargs)

    # --------------------------------------------------
    # Internal helpers
    # --------------------------------------------------
    def _sanitize_kwargs(self, kwargs):
        # Common parameters used in OpenViX / ATV grid EPG
        unsupported = [
            "graphic",
            "epg_type",
            "timeline",
            "viewMode",
            "display",
            "grid",
            "multi",
            "skin_name"
        ]

        for key in unsupported:
            kwargs.pop(key, None)

    # --------------------------------------------------
    # Compatibility / dummy methods
    # --------------------------------------------------

    def setTimeline(self, *args, **kwargs):
        pass

    def moveToService(self, *args, **kwargs):
        pass

    def moveToEvent(self, *args, **kwargs):
        pass

    def setCurrentService(self, *args, **kwargs):
        pass

    def refreshGrid(self, *args, **kwargs):
        pass

    def reload(self, *args, **kwargs):
        pass

    def setMode(self, *args, **kwargs):
        pass

    # Some plugins may call this
    def setEPGType(self, *args, **kwargs):
        pass

    # Navigation fallbacks
    def nextPage(self):
        try:
            self.pageDown()
        except Exception:
            pass

    def prevPage(self):
        try:
            self.pageUp()
        except Exception:
            pass

    # Optional: flag check used in some plugins
    def isGridMode(self):
        return False
