from Screens.Screen import Screen
from Screens.ParentalControlSetup import ProtectedScreen
from enigma import eConsoleAppContainer, eDVBDB, eTimer, eSize, ePoint, getDesktop

from Components.ActionMap import ActionMap, NumberActionMap
from Components.config import config, ConfigSubsection, ConfigSelection, ConfigText
from Components.PluginComponent import plugins
from Components.PluginList import *
from Components.Label import Label
from Components.Language import language
from Components.ServiceList import refreshServiceList
from Components.Harddisk import harddiskmanager
from Components.Sources.StaticText import StaticText
from Components.SystemInfo import BoxInfo, hassoftcaminstalled
from Components.Pixmap import Pixmap
from Components import Opkg
from Screens.MessageBox import MessageBox
from Screens.ChoiceBox import ChoiceBox
from Screens.Console import Console
from Plugins.Plugin import PluginDescriptor
from Tools.Directories import fileExists, resolveFilename, SCOPE_PLUGINS, SCOPE_CURRENT_SKIN
from Tools.LoadPixmap import LoadPixmap

from skin import parseColor
from time import time
import os, math

language.addCallback(plugins.reloadPlugins)

# Ensure plugin_style exists
if not hasattr(config.misc, "plugin_style"):
    config.misc.plugin_style = ConfigSelection(
        default="list",
        choices=[("list", "List")]
    )

config.misc.pluginbrowser = ConfigSubsection()
config.misc.pluginbrowser.plugin_order = ConfigText(default="")


def getDesktopSize():
    s = getDesktop(0).size()
    return (s.width(), s.height())


def isFullHD():
    desktopSize = getDesktopSize()
    return desktopSize[0] == 1920


class PluginBrowserSummary(Screen):
    def __init__(self, session, parent):
        Screen.__init__(self, session, parent=parent)
        self["entry"] = StaticText("")
        self["desc"] = StaticText("")
        self.onShow.append(self.addWatcher)
        self.onHide.append(self.removeWatcher)

    def addWatcher(self):
        self.parent.onChangedEntry.append(self.selectionChanged)
        self.parent.selectionChanged()

    def removeWatcher(self):
        self.parent.onChangedEntry.remove(self.selectionChanged)

    def selectionChanged(self, name, desc):
        self["entry"].text = name
        self["desc"].text = desc


class PluginBrowser(Screen, ProtectedScreen):
    def __init__(self, session):
        Screen.__init__(self, session)
        self.setTitle(_("Plugin browser"))
        ProtectedScreen.__init__(self)

        self.firsttime = True
        self.current_style = getattr(config.misc.plugin_style, "value", "list")
        self.is_grid_mode = self.current_style in ("grid1", "grid2", "grid3", "grid4", "grid5", "grid6", "grid7", "grid8", "grid9")

        # Set skin name based on mode
        if self.is_grid_mode:
            self.skinName = "PluginBrowserNew"
        else:
            self.skinName = "PluginBrowser"

        # Common elements
        self["key_red"] = self["red"] = Label(_("Remove plugins"))
        self["key_green"] = self["green"] = Label(_("Download plugins"))
        self["key_menu"] = StaticText(_("MENU"))
        self["help_text"] = Label(_("Press MENU to change view style"))

        # Grid-specific elements
        self['pages'] = Label()
        self['plugin_description'] = Label()

        # List-specific elements
        self.list = []
        self["list"] = PluginList(self.list)

        # Base actions - always available
        self["actions"] = ActionMap(["WizardActions", "MenuActions"],
        {
            "ok": self.ok,
            "back": self.close,
            "menu": self.openViewMenu,
        })

        self["PluginDownloadActions"] = ActionMap(["ColorActions"],
        {
            "red": self.delete,
            "green": self.download
        })

        # Direction actions for sorting (original implementation)
        self["DirectionActions"] = ActionMap(["DirectionActions"],
        {
            "moveUp": self.moveUp,
            "moveDown": self.moveDown
        })

        # Number actions for list view quick select
        self["NumberActions"] = NumberActionMap(["NumberActions"],
        {
            "1": self.keyNumberGlobal,
            "2": self.keyNumberGlobal,
            "3": self.keyNumberGlobal,
            "4": self.keyNumberGlobal,
            "5": self.keyNumberGlobal,
            "6": self.keyNumberGlobal,
            "7": self.keyNumberGlobal,
            "8": self.keyNumberGlobal,
            "9": self.keyNumberGlobal,
            "0": self.keyNumberGlobal
        })

        # Help actions
        self["HelpActions"] = ActionMap(["HelpActions"],
        {
            "displayHelp": self.showHelp,
        })

        # Navigation actions
        self["NavigationActions"] = ActionMap(["DirectionActions"],
        {
            "up": self.moveUp,
            "down": self.moveDown,
            "left": self.keyLeft,
            "right": self.keyRight,
        })

        self.help = False
        self.number = 0
        self.nextNumberTimer = eTimer()
        self.nextNumberTimer.callback.append(self.okbuttonClick)

        # Grid-specific variables
        self.mainlist = []
        self.plugins_pos = []
        self.plugins = []
        self.current = 0
        self.current_page = 0

        # Set colors based on style
        self.setColors()

        # Build appropriate skin
        if self.is_grid_mode:
            self.skin = self.buildGridSkin()
        else:
            self.skin = self.buildListSkin()

        self.onFirstExecBegin.append(self.checkWarnings)
        self.onShown.append(self.updateView)
        self.onChangedEntry = []
        self["list"].onSelectionChanged.append(self.selectionChanged)
        self.onLayoutFinish.append(self.saveListsize)

    def showHelp(self):
        """Show help information - required for HelpActions"""
        if self.is_grid_mode:
            return
        if config.usage.menu_show_numbers.value not in ("menu&plugins", "plugins"):
            self.help = not self.help
            self.updateList(self.help)

    def setColors(self):
        """Set colors based on current grid style"""
        # Grid 1 - Dark theme
        if config.misc.plugin_style.value == "grid1":
            self.backgroundColor = "#44000000"
            self.primaryColor = "#282828"
            self.primaryColorLabel = "#DCE1E3"
            self.secondaryColor = "#4e4e4e"
            self.secondaryColorLabel = "#FFFFFF"
        # Grid 2 - Teal theme
        elif config.misc.plugin_style.value == "grid2":
            self.backgroundColor = "#21292A"
            self.primaryColor = "#191F22"
            self.primaryColorLabel = "#DCE1E3"
            self.secondaryColor = "#39474F"
            self.secondaryColorLabel = "#FFFFFF"
        # Grid 3 - Transparent theme
        elif config.misc.plugin_style.value == "grid3":
            self.backgroundColor = "#44000000"
            self.primaryColor = "#16000000"
            self.primaryColorLabel = "#00ffffff"
            self.secondaryColor = "#696969"
            self.secondaryColorLabel = "#FFFFFF"
        # Grid 4 - Ocean Blue theme
        elif config.misc.plugin_style.value == "grid4":
            self.backgroundColor = "#0A1A2A"
            self.primaryColor = "#1A3A5A"
            self.primaryColorLabel = "#E6F7FF"
            self.secondaryColor = "#3A7B94"
            self.secondaryColorLabel = "#FFFFFF"
        # Grid 5 - Sunset theme
        elif config.misc.plugin_style.value == "grid5":
            self.backgroundColor = "#3D2B1F"
            self.primaryColor = "#8B4C39"
            self.primaryColorLabel = "#FFE4C4"
            self.secondaryColor = "#C35E3A"
            self.secondaryColorLabel = "#FFFFFF"
        # Grid 6 - Emerald theme
        elif config.misc.plugin_style.value == "grid6":
            self.backgroundColor = "#1A3A2B"
            self.primaryColor = "#2D5A3C"
            self.primaryColorLabel = "#E3F2E3"
            self.secondaryColor = "#4C9A6E"
            self.secondaryColorLabel = "#FFFFFF"
        # Grid 7 - Frosted Glass
        elif config.misc.plugin_style.value == "grid7":
            self.backgroundColor = "#44000000"
            self.primaryColor = "#2D5A8C"
            self.primaryColorLabel = "#FFFFFF"
            self.secondaryColor = "#3A7B9F"
            self.secondaryColorLabel = "#FFFFFF"
        # Grid 8 - Amber Glow
        elif config.misc.plugin_style.value == "grid8":
            self.backgroundColor = "#1A1505"
            self.primaryColor = "#2A200A"
            self.primaryColorLabel = "#FFEBCD"
            self.secondaryColor = "#736003"
            self.secondaryColorLabel = "#FFFFFF"
        # Grid 9 - Violet Dream
        elif config.misc.plugin_style.value == "grid9":
            self.backgroundColor = "#1A0A20"
            self.primaryColor = "#4B0082"
            self.primaryColorLabel = "#E6E6FA"
            self.secondaryColor = "#8C54A0"
            self.secondaryColorLabel = "#FFFFFF"
        else:
            # Default for list mode
            self.backgroundColor = "#44000000"
            self.primaryColor = "#282828"
            self.primaryColorLabel = "#DCE1E3"
            self.secondaryColor = "#4e4e4e"
            self.secondaryColorLabel = "#FFFFFF"

    def buildListSkin(self):
        """Build skin for list view"""
        if isFullHD():
            return """
            <screen name="PluginBrowser" position="0,0" size="1920,1080" flags="wfNoBorder" backgroundColor="#44000000">
                <eLabel text="Plugin Browser" position="50,12" size="900,100" font="Regular;75" foregroundColor="#00ffffff" backgroundColor="#44000000" transparent="1" zPosition="2" />
                <widget name="plugin_description" position="50,105" size="900,100" font="Regular;40" foregroundColor="#00b0f7e4" backgroundColor="#44000000" transparent="1" zPosition="2" />
                <widget source="global.CurrentTime" render="Label" position="1617,12" size="273,100" font="Regular;80" halign="right" backgroundColor="#44000000" transparent="1" foregroundColor="#00ffffff">
                    <convert type="ClockToText">
                </convert>
                </widget>
                <widget backgroundColor="#44000000" position="1128,105" size="762,50" font="Regular;40" foregroundColor="#00b0f7e4" halign="right" render="Label" source="global.CurrentTime" transparent="1">
                    <convert type="ClockToText">FullDate</convert>
                </widget>
                <widget name="help_text" position="50,1000" size="400,40" font="Regular;25" foregroundColor="#00b0f7e4" backgroundColor="#44000000" transparent="1" zPosition="2" halign="left" valign="bottom" />
                <widget name="list" position="50,190" size="1820,800" zPosition="1" />
                <eLabel position="67,1065" size="300,8" backgroundColor="#00ff2525" foregroundColor="#00ff2525" zPosition="4"/>
                <eLabel position="393,1065" size="300,8" backgroundColor="#00389416" foregroundColor="#00389416" zPosition="4"/>
                <widget name="key_red" position="67,1013" size="300,50" font="Regular;32" zPosition="1" halign="center" valign="center" foregroundColor="#00ffffff" backgroundColor="#16000000" transparent="1"/>
                <widget name="key_green" position="393,1013" size="300,50" font="Regular;32" zPosition="1" halign="center" valign="center" foregroundColor="#00ffffff" backgroundColor="#16000000" transparent="1"/>
            </screen>
            """
        else:
            return """
            <screen name="PluginBrowser" position="0,0" size="1280,720" flags="wfNoBorder" backgroundColor="#44000000">
                <eLabel text="Plugin Browser" position="20,12" size="563,45" font="Regular;40" foregroundColor="#00ffffff" backgroundColor="#44000000" transparent="1" zPosition="2" />
                <widget name="plugin_description" position="20,60" size="567,32" font="Regular;28" foregroundColor="#00b0f7e4" backgroundColor="#44000000" transparent="1" zPosition="2" />
                <widget source="global.CurrentTime" render="Label" position="1000,12" size="273,100" font="Regular;50" halign="right" backgroundColor="#44000000" transparent="1" foregroundColor="#00ffffff">
                    <convert type="ClockToText">
                </convert>
                </widget>
                <widget backgroundColor="#44000000" position="813,60" size="462,32" font="Regular;28" foregroundColor="#00b0f7e4" halign="right" render="Label" source="global.CurrentTime" transparent="1">
                    <convert type="ClockToText">FullDate</convert>
                </widget>
                <widget name="help_text" position="20,650" size="400,40" font="Regular;25" foregroundColor="#00b0f7e4" backgroundColor="#44000000" transparent="1" zPosition="2" halign="left" valign="bottom" />
                <widget name="list" position="10,110" size="1260,530" zPosition="1" />
                <eLabel position="67,712" size="200,5" backgroundColor="#00ff2525" foregroundColor="#00ff2525" zPosition="4"/>
                <eLabel position="293,712" size="200,5" backgroundColor="#00389416" foregroundColor="#00389416" zPosition="4"/>
                <widget name="key_red" position="67,677" size="200,35" font="Regular;28" zPosition="1" halign="center" valign="center" foregroundColor="#00ffffff" backgroundColor="#16000000" transparent="1"/>
                <widget name="key_green" position="293,677" size="200,35" font="Regular;28" zPosition="1" halign="center" valign="center" foregroundColor="#00ffffff" backgroundColor="#16000000" transparent="1"/>
            </screen>
            """

    def buildGridSkin(self):
        """Build skin for grid view - using PluginBrowserNew as skin name"""
        if isFullHD():
            # HD coordinates
            posxstart = 50
            posystart = 190
            posxplus = 260
            posyplus = 260
            iconsize = "250,250"

            # Screen dimensions
            positionx = 0
            positiony = 0
            sizex = 1920
            sizey = 1080

            # Title and info positions
            positionx1 = 50
            positiony1 = 12
            sizex1 = 900
            sizey1 = 100
            font1 = 75

            positionx2 = 50
            positiony2 = 105
            sizex2 = 900
            sizey2 = 100
            font2 = 40

            positionx3 = 1617
            positiony3 = 12
            sizex3 = 273
            sizey3 = 100
            font3 = 80

            positionx4 = 1128
            positiony4 = 105
            sizex4 = 762
            sizey4 = 50
            font4 = 40

            positionx5 = 1683
            positiony5 = 975
            sizex5 = 220
            sizey5 = 85
            font5 = 40

            # Key positions
            eLabelx1 = 67
            eLabely1 = 1065
            eLabelx2 = 393
            eLabely2 = 1065
            eLabelx3 = 719
            eLabely3 = 1065
            eLabelx4 = 1045
            eLabely4 = 1065
            eLabel1ysizex = 300
            eLabel1ysizey = 8

            positionxkey1 = 67
            positionxkey2 = 393
            positionxkey3 = 719
            positionxkey4 = 1045
            positionykey = 1013
            sizekeysx = 300
            sizekeysy = 50
            fontkey = 32
        else:
            # SD coordinates
            posxstart = 10
            posystart = 110
            posxplus = 180
            posyplus = 190
            iconsize = "150,150"

            positionx = 0
            positiony = 0
            sizex = 1280
            sizey = 720

            positionx1 = 20
            positiony1 = 12
            sizex1 = 563
            sizey1 = 45
            font1 = 40

            positionx2 = 20
            positiony2 = 60
            sizex2 = 567
            sizey2 = 32
            font2 = 28

            positionx3 = 1000
            positiony3 = 12
            sizex3 = 273
            sizey3 = 100
            font3 = 50

            positionx4 = 813
            positiony4 = 60
            sizex4 = 462
            sizey4 = 32
            font4 = 28

            positionx5 = 1130
            positiony5 = 655
            sizex5 = 160
            sizey5 = 50
            font5 = 27

            eLabelx1 = 67
            eLabely1 = 712
            eLabelx2 = 293
            eLabely2 = 712
            eLabelx3 = 519
            eLabely3 = 712
            eLabelx4 = 750
            eLabely4 = 712
            eLabel1ysizex = 200
            eLabel1ysizey = 5

            positionxkey1 = 67
            positionxkey2 = 293
            positionxkey3 = 519
            positionxkey4 = 750
            positionykey = 677
            sizekeysx = 200
            sizekeysy = 35
            fontkey = 28

        posx = posxstart
        posy = posystart
        list_dummy = []
        skincontent = ""

        # Base skin with PluginBrowserNew as screen name
        skin = """
            <screen name="PluginBrowserNew" position="%d,%d" size="%d,%d" flags="wfNoBorder" backgroundColor="%s">
                <eLabel text="Plugin Browser" position="%d,%d" size="%d,%d" font="Regular;%d" foregroundColor="#00ffffff" backgroundColor="#44000000" transparent="1" zPosition="2" />
                <widget name="plugin_description" position="%d,%d" size="%d,%d" font="Regular;%d" foregroundColor="#00b0f7e4" backgroundColor="#44000000" transparent="1" zPosition="2" />
                <widget source="global.CurrentTime" render="Label" position="%d,%d" size="%d,%d" font="Regular;%d" halign="right" backgroundColor="#44000000" transparent="1" foregroundColor="#00ffffff">
                    <convert type="ClockToText">
                </convert>
                </widget>
                <widget backgroundColor="#44000000" position="%d,%d" size="%d,%d" font="Regular;%d" foregroundColor="#00b0f7e4" halign="right" render="Label"  source="global.CurrentTime" transparent="1">
                <convert type="ClockToText">FullDate</convert>
                </widget>
                <widget name="pages" foregroundColor="#00ffffff" position="%d,%d" size="%d,%d" font="Regular;%d" zPosition="2" halign="center" valign="center" transparent="1" />
                <widget name="help_text" position="%d,%d" size="%d,%d" font="Regular;%d" foregroundColor="#00b0f7e4" backgroundColor="#44000000" transparent="1" zPosition="2" halign="left" valign="bottom" />
                <eLabel position="%d,%d" size="%d,%d" backgroundColor="#00ff2525" foregroundColor="#00ff2525" zPosition="4"/>
                <eLabel position="%d,%d" size="%d,%d" backgroundColor="#00389416" foregroundColor="#00389416" zPosition="4"/>
                <widget name="key_red" position="%d,%d" size="%d,%d" font="Regular;%d" zPosition="1" halign="center" valign="center" foregroundColor="#00ffffff" backgroundColor="#16000000" transparent="1"/>
                <widget name="key_green" position="%d,%d" size="%d,%d" font="Regular;%d" zPosition="1" halign="center" valign="center" foregroundColor="#00ffffff" backgroundColor="#16000000" transparent="1"/>
            """ % (positionx, positiony, sizex, sizey, self.backgroundColor,
                   positionx1, positiony1, sizex1, sizey1, font1,
                   positionx2, positiony2, sizex2, sizey2, font2,
                   positionx3, positiony3, sizex3, sizey3, font3,
                   positionx4, positiony4, sizex4, sizey4, font4,
                   positionx5, positiony5, sizex5, sizey5, font5,
                   positionx5-200, positiony5+60, 500, 40, 25,
                   eLabelx1, eLabely1, eLabel1ysizex, eLabel1ysizey,
                   eLabelx2, eLabely2, eLabel1ysizex, eLabel1ysizey,
                   positionxkey1, positionykey, sizekeysx, sizekeysy, fontkey,
                   positionxkey2, positionykey, sizekeysx, sizekeysy, fontkey)

        # Generate grid items
        count = 0
        for x, p in enumerate(plugins.getPlugins(PluginDescriptor.WHERE_PLUGINMENU)):
            x += 1
            count += 1
            if isFullHD():
                skincontent += '<widget backgroundColor="'+self.primaryColor+'" name="plugin_' + str(x) + '" position="' + str(posx) + ',' + str(posy) + '" size="' + iconsize + '" />'
                skincontent += '<widget foregroundColor="'+self.primaryColorLabel+'" name="label_'+str(x)+'" position="'+str(posx+10)+','+str(posy+139)+'" size="220,84" zPosition="3" font="Regular;32" halign="center" valign="center" transparent="1" />'
                skincontent += '<widget  name="icon_'+str(x)+'" position="'+str(posx+30)+','+str(posy+40)+'" size="180,80" zPosition="3" alphatest="on" transparent="1" />'
            else:
                skincontent += '<widget backgroundColor="'+self.primaryColor+'" name="plugin_' + str(x) + '" position="' + str(posx) + ',' + str(posy) + '" size="' + iconsize + '" />'
                skincontent += '<widget foregroundColor="'+self.primaryColorLabel+'" name="label_'+str(x)+'" position="'+str(posx)+','+str(posy+20)+'" size="150,65" zPosition="3" font="Regular;22" halign="center" valign="center" transparent="1" />'
                skincontent += '<widget  name="icon_'+str(x)+'" position="'+str(posx+10)+','+str(posy+20)+'" size="150,50" zPosition="3" alphatest="on" transparent="1" />'

            self.plugins_pos.append((posx, posy))
            self.plugins.append((p.name, p.description, p, p.icon))
            self["plugin_"+str(x)] = Label()
            self["label_"+str(x)] = Label()
            self["icon_"+str(x)] = Pixmap()
            self["label_"+str(x)].setText(p.name)

            posx += posxplus
            list_dummy.append(x)
            if len(list_dummy) == 7:
                list_dummy[:] = []
                posx = posxstart
                posy += posyplus
            if count == 21:
                posx = posxstart
                posy = posystart
                count = 0

        skin += skincontent
        skin += '</screen>'

        # Calculate pages
        self.total_pages = int(math.ceil(float(len(self.plugins))/21))
        count = 1
        counting = 1
        list_dummy = []
        for x in range(1, len(self.plugins)+1):
            if count == 21:
                count += 1
                counting += 1
                list_dummy.append(x)
                self.mainlist.append(list_dummy)
                count = 1
                list_dummy = []
            else:
                count += 1
                counting += 1
                list_dummy.append(x)
                if int(counting) == len(self.plugins)+1:
                    self.mainlist.append(list_dummy)

        return skin

    def updateView(self):
        """Update the view based on current mode"""
        if self.is_grid_mode:
            self.updateGrid()
            # Hide list widget
            self["list"].hide()
        else:
            self.updateList(False)
            # Hide grid widgets
            self['pages'].hide()
            self['plugin_description'].hide()
            for i in range(1, len(self.plugins)+1):
                if hasattr(self, "plugin_"+str(i)):
                    self["plugin_"+str(i)].hide()
                    self["label_"+str(i)].hide()
                    self["icon_"+str(i)].hide()

    def updateGrid(self):
        """Initialize grid view"""
        self.setIcons()
        self.activeBox()

    def updateList(self, showHelp=False):
        """Update the list view with plugins"""
        self.list = []
        pluginlist = plugins.getPlugins(PluginDescriptor.WHERE_PLUGINMENU)[:]
        for x in config.misc.pluginbrowser.plugin_order.value.split(","):
            plugin = [p for p in pluginlist if os.path.basename(p.path) == x]
            if plugin:
                self.list.append(PluginEntryComponent(plugin[0], self.listWidth))
                pluginlist.remove(plugin[0])
        self.list = self.list + [PluginEntryComponent(plugin, self.listWidth) for plugin in pluginlist]
        if config.usage.menu_show_numbers.value in ("menu&plugins", "plugins") or showHelp:
            for x in enumerate(self.list):
                tmp = list(x[1][1])
                tmp[7] = "%s %s" % (x[0] + 1, tmp[7])
                x[1][1] = tuple(tmp)
        self["list"].l.setList(self.list)

    def openViewMenu(self):
        """Open menu to change view style"""
        menu_list = [
            (_("View as list"), "list"),
            (_("Grid 1 - Dark"), "grid1"),
            (_("Grid 2 - Teal"), "grid2"),
            (_("Grid 3 - Transparent"), "grid3"),
            (_("Grid 4 - Ocean Blue"), "grid4"),
            (_("Grid 5 - Sunset"), "grid5"),
            (_("Grid 6 - Emerald"), "grid6"),
            (_("Grid 7 - Frosted Glass"), "grid7"),
            (_("Grid 8 - Amber Glow"), "grid8"),
            (_("Grid 9 - Violet Dream"), "grid9"),
        ]

        # Find current style
        current_idx = 0
        for i, (name, style) in enumerate(menu_list):
            if style == config.misc.plugin_style.value:
                current_idx = i
                break

        # Title with note
        title = _("Select Plugin Browser View Style\n\nNote:\nSwitching between styles works instantly!")

        # Open the choice box
        self.session.openWithCallback(
            self.viewMenuCallback,
            ChoiceBox,
            title=title,
            list=menu_list,
            selection=current_idx
        )

    def viewMenuCallback(self, choice):
        """Handle view menu selection"""
        if choice:
            new_style = choice[1]
            if new_style != config.misc.plugin_style.value:
                # Save new style
                config.misc.plugin_style.value = new_style
                config.misc.plugin_style.save()

                # Close current browser first
                self.close()

                # Use a timer to reopen after closing
                self.reopenTimer = eTimer()
                self.reopenTimer.callback.append(self.reopenBrowser)
                self.reopenTimer.start(100, True)

    def reopenBrowser(self):
        """Reopen the browser with the new style"""
        self.session.open(PluginBrowser)

    # List view methods
    def saveListsize(self):
        listsize = self["list"].instance.size()
        self.listWidth = listsize.width()
        self.listHeight = listsize.height()

    def createSummary(self):
        return PluginBrowserSummary

    def selectionChanged(self):
        if not self.is_grid_mode:
            item = self["list"].getCurrent()
            if item:
                p = item[0]
                name = p.name
                desc = p.description
                self["plugin_description"].setText(desc)
            else:
                name = "-"
                desc = ""
            for cb in self.onChangedEntry:
                cb(name, desc)

    def checkWarnings(self):
        if len(plugins.warnings):
            text = _("Some plugins are not available:\n")
            for (pluginname, error) in plugins.warnings:
                text += "%s (%s)\n" % (pluginname, error)
            plugins.resetWarnings()
            self.session.open(MessageBox, text=text, type=MessageBox.TYPE_WARNING)

    def ok(self):
        """OK button handler"""
        if self.is_grid_mode:
            if self.plugins and self.current < len(self.plugins):
                plugin = self.plugins[self.current][2]
                try:
                    plugin(session=self.session)
                except Exception as e:
                    print("[PluginBrowser] Plugin failed:", e)
        else:
            current = self["list"].l.getCurrentSelection()
            if current:
                plugin = current[0]
                try:
                    plugin(session=self.session)
                except Exception as e:
                    print("[PluginBrowser] Plugin failed:", e)
        self.help = False

    def setDefaultList(self, answer):
        if answer:
            config.misc.pluginbrowser.plugin_order.value = ""
            config.misc.pluginbrowser.plugin_order.save()
            self.updateList(False)

    def keyNumberGlobal(self, number):
        if self.is_grid_mode:
            return
        if number == 0 and self.number == 0:
            if len(self.list) > 0 and config.misc.pluginbrowser.plugin_order.value != "":
                self.session.openWithCallback(self.setDefaultList, MessageBox, _("Sort plugins list to default?"), MessageBox.TYPE_YESNO)
        else:
            self.number = self.number * 10 + number
            if self.number and self.number <= len(self.list):
                if number * 10 > len(self.list) or self.number >= 10:
                    self.okbuttonClick()
                else:
                    self.nextNumberTimer.start(1400, True)
            else:
                self.resetNumberKey()

    def okbuttonClick(self):
        if self.is_grid_mode:
            return
        self["list"].moveToIndex(self.number - 1)
        self.resetNumberKey()
        self.ok()

    def resetNumberKey(self):
        self.nextNumberTimer.stop()
        self.number = 0

    def moveUp(self):
        """Move plugin up in the list (for sorting)"""
        if self.is_grid_mode:
            self.keyUp()
        else:
            self.move(-1)

    def moveDown(self):
        """Move plugin down in the list (for sorting)"""
        if self.is_grid_mode:
            self.keyDown()
        else:
            self.move(1)

    def move(self, direction):
        """Original move method for sorting plugins"""
        if self.is_grid_mode:
            return
        if len(self.list) > 1:
            currentIndex = self["list"].getSelectionIndex()
            swapIndex = (currentIndex + direction) % len(self.list)

            # Original logic for moving plugins
            if currentIndex == 0 and swapIndex != 1:
                self.list = self.list[1:] + [self.list[0]]
            elif swapIndex == 0 and currentIndex != 1:
                self.list = [self.list[-1]] + self.list[:-1]
            else:
                self.list[currentIndex], self.list[swapIndex] = self.list[swapIndex], self.list[currentIndex]

            self["list"].l.setList(self.list)

            # Update selection
            if direction == 1:
                self["list"].down()
            else:
                self["list"].up()

            # Save the new order - original format
            plugin_order = []
            for x in self.list:
                try:
                    plugin_order.append(os.path.basename(x[0].path))
                except Exception:
                    continue
            config.misc.pluginbrowser.plugin_order.value = ",".join(plugin_order)
            config.misc.pluginbrowser.plugin_order.save()

    def keyLeft(self):
        if self.is_grid_mode:
            self.moveGrid(1, 'backwards')

    def keyRight(self):
        if self.is_grid_mode:
            self.moveGrid(1, 'forward')

    def keyUp(self):
        if self.is_grid_mode:
            self.moveGrid(7, 'backwards')

    def keyDown(self):
        if self.is_grid_mode:
            self.moveGrid(7, 'forward')

    # Grid view methods
    def setIcons(self):
        for x, elem in enumerate(self.plugins):
            x += 1
            icon = elem[3] or LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, "icons/plugin.png"))
            self['icon_'+str(x)].instance.setScale(1)
            self['icon_'+str(x)].instance.setPixmap(icon)

    def activeBox(self):
        if not self.plugins:
            return
        for index, plugin in enumerate(self.plugins):
            index += 1
            if index == self.current+1:
                self["plugin_description"].setText(plugin[1])
                pos = self.plugins_pos[self.current]
                if isFullHD():
                    self["plugin_"+str(index)].instance.resize(eSize(270, 270))
                    self["plugin_" +str(index)].instance.move(ePoint(pos[0]-10, pos[1]-10))
                    self["label_" +str(index)].instance.move(ePoint(pos[0]+10, pos[1]+155))
                else:
                    self["plugin_"+str(index)].instance.resize(eSize(190, 190))
                    self["plugin_" +str(index)].instance.move(ePoint(pos[0]-10, pos[1]-10))
                    self["label_" +str(index)].instance.move(ePoint(pos[0]+5, pos[1]+110))
                self["plugin_" + str(index)].instance.setBackgroundColor(parseColor(self.secondaryColor))
                self["plugin_"+str(index)].instance.invalidate()
                self["label_" + str(index)].instance.setBackgroundColor(parseColor(self.secondaryColor))
                self["label_"+str(index)].instance.setForegroundColor(parseColor(self.secondaryColorLabel))
            else:
                pos = self.plugins_pos[index-1]
                if isFullHD():
                    self["plugin_"+str(index)].instance.resize(eSize(250, 250))
                    self["plugin_"+str(index)].instance.move(ePoint(pos[0], pos[1]))
                    self["label_" +str(index)].instance.move(ePoint(pos[0]+10, pos[1]+139))
                else:
                    self["plugin_"+str(index)].instance.resize(eSize(170, 170))
                    self["plugin_"+str(index)].instance.move(ePoint(pos[0], pos[1]))
                    self["label_" +str(index)].instance.move(ePoint(pos[0]+10, pos[1]+90))
                self["plugin_" + str(index)].instance.setBackgroundColor(parseColor(self.primaryColor))
                self["plugin_"+str(index)].instance.invalidate()
                self["label_" + str(index)].instance.setBackgroundColor(parseColor(self.primaryColor))
                self["label_" + str(index)].instance.setForegroundColor(parseColor(self.primaryColorLabel))
        self.paint_hide()
        self.currentPage()

    def currentPage(self):
        self['pages'].setText("Page {}/{}".format(self.current_page+1, self.total_pages))

    def moveGrid(self, step, direction):
        if not self.is_grid_mode or not self.plugins:
            return
        ls = list(range(1, len(self.plugins_pos)+1))
        if direction == 'backwards':
            self.current -= step
        else:
            self.current += step
        # safer wrap
        self.current %= len(ls)

        for i in range(self.total_pages):
            if ls[self.current] in self.mainlist[i]:
                self.current_page = i
        self.activeBox()

    def paint_hide(self):
        for i in range(self.total_pages):
            if i != self.current_page:
                for x in self.mainlist[i]:
                    self["plugin_"+str(x)].hide()
                    self["label_"+str(x)].hide()
                    self['icon_'+str(x)].hide()
            else:
                for x in self.mainlist[i]:
                    self["plugin_"+str(x)].show()
                    self["label_"+str(x)].show()
                    self["icon_"+str(x)].show()

    # Common methods
    def isProtected(self):
        return config.ParentalControl.setuppinactive.value and (not config.ParentalControl.config_sections.main_menu.value or hasattr(self.session, 'infobar') and self.session.infobar is None) and config.ParentalControl.config_sections.plugin_browser.value

    def exit(self):
        self.close(True)

    def delete(self):
        self.session.openWithCallback(self.PluginDownloadBrowserClosed, PluginDownloadBrowser, PluginDownloadBrowser.REMOVE)

    def download(self):
        self.session.openWithCallback(self.PluginDownloadBrowserClosed, PluginDownloadBrowser, PluginDownloadBrowser.DOWNLOAD, self.firsttime)
        self.firsttime = False

    def PluginDownloadBrowserClosed(self, returnValue):
        if returnValue == None:
            if self.is_grid_mode:
                self.updateGrid()
            else:
                self.updateList(False)
            self.checkWarnings()
        elif returnValue == 0:
            self.download()
        else:
            self.delete()

    def openExtensionmanager(self):
        if fileExists(resolveFilename(SCOPE_PLUGINS, "SystemPlugins/SoftwareManager/plugin.py")):
            try:
                from Plugins.SystemPlugins.SoftwareManager.plugin import PluginManager
            except ImportError:
                self.session.open(MessageBox, _("The software management extension is not installed!\nPlease install it."), type=MessageBox.TYPE_INFO, timeout=10)
            else:
                self.session.openWithCallback(self.PluginDownloadBrowserClosed, PluginManager)


class PluginDownloadBrowser(Screen):
    DOWNLOAD = 0
    REMOVE = 1
    PLUGIN_PREFIX = 'enigma2-plugin-'
    lastDownloadDate = None

    def __init__(self, session, type=0, needupdate=True):
        Screen.__init__(self, session)

        self.type = type
        self.needupdate = needupdate

        self.container = eConsoleAppContainer()
        self.container.appClosed.append(self.runFinished)
        self.container.dataAvail.append(self.dataAvail)
        self.onLayoutFinish.append(self.startRun)
        self.setTitle(_("Downloadable new plugins") if self.type == self.DOWNLOAD else _("Remove plugins"))
        self.list = []
        self["list"] = PluginList(self.list)
        self.pluginlist = []
        self.expanded = []
        self.installedplugins = []
        self.plugins_changed = False
        self.reload_settings = False
        self.check_softcams = False
        self.check_settings = False
        self.install_settings_name = ''
        self.remove_settings_name = ''
        self["text"] = Label(_("Downloading plugin information. Please wait...") if self.type == self.DOWNLOAD else _("Getting plugin information. Please wait..."))
        self["key_red"] = Label(_("Cancel"))
        self["key_green"] = Label(_("Expand"))
        self["key_blue"] = Label(_("Remove plugins") if self.type == self.DOWNLOAD else _("Download plugins"))
        self.run = 0
        self.remainingdata = ""
        self["actions"] = ActionMap(["WizardActions"],
        {
            "ok": self.go,
            "back": self.requestClose,
        })
        self["PluginDownloadActions"] = ActionMap(["ColorActions"], {
            "blue": self.delete if self.type == self.DOWNLOAD else self.download,
            "red": self.requestClose,
            "green": self.go}
        )
        if os.path.isfile('/usr/bin/opkg'):
            self.opkg = '/usr/bin/opkg'
            self.opkg_install = self.opkg + ' install'
            self.opkg_remove = self.opkg + ' remove --autoremove'
        else:
            self.opkg = 'opkg'
            self.opkg_install = 'opkg install -force-defaults'
            self.opkg_remove = self.opkg + ' remove'
        self["list"].onSelectionChanged.append(self.selectionChanged)

    def selectionChanged(self):
        selection = self["list"].l.getCurrentSelection()
        if selection:
            selection = selection[0]
            if isinstance(selection, str): # category
                self["key_green"].text = _("Collapse") if selection in self.expanded else _("Expand")
            else:
                self["key_green"].text = _("Install plugin") if self.type == self.DOWNLOAD else _("Remove plugin")

    def go(self):
        selection = self["list"].l.getCurrentSelection()
        if selection:
            selection = selection[0]
            if isinstance(selection, str): # category
                if selection in self.expanded:
                    self.expanded.remove(selection)
                else:
                    self.expanded.append(selection)
                self.updateList()
            else:
                if self.type == self.DOWNLOAD:
                    self.session.openWithCallback(self.runInstall, MessageBox, _("Do you really want to download\nthe plugin \"%s\"?") % selection.name)
                elif self.type == self.REMOVE:
                    self.session.openWithCallback(self.runInstall, MessageBox, _("Do you really want to remove\nthe plugin \"%s\"?") % selection.name)

    def delete(self):
        self.requestClose(1)

    def download(self):
        self.requestClose(0)

    def requestClose(self, returnValue=None):
        if self.plugins_changed:
            plugins.readPluginList(resolveFilename(SCOPE_PLUGINS))
        if self.reload_settings:
            self["text"].setText(_("Reloading bouquets and services..."))
            eDVBDB.getInstance().reloadBouquets()
            eDVBDB.getInstance().reloadServicelist()
            from Components.ParentalControl import parentalControl
            parentalControl.open()
            refreshServiceList()
        if self.check_softcams:
            BoxInfo.setItem("HasSoftcamInstalled", hassoftcaminstalled())
        plugins.readPluginList(resolveFilename(SCOPE_PLUGINS))
        self.container.appClosed.remove(self.runFinished)
        self.container.dataAvail.remove(self.dataAvail)
        self.close(returnValue)

    def resetPostInstall(self):
        try:
            del self.postInstallCall
        except:
            pass

    def installDestinationCallback(self, result):
        if result is not None:
            dest = result[1]
            if dest.startswith('/'):
                # Custom install path, add it to the list too
                dest = os.path.normpath(dest)
                extra = '--add-dest %s:%s -d %s' % (dest, dest, dest)
                Opkg.opkgAddDestination(dest)
            else:
                extra = '-d ' + dest
            self.doInstall(self.installFinished, self["list"].l.getCurrentSelection()[0].name + ' ' + extra)
        else:
            self.resetPostInstall()

    def runInstall(self, val):
        if val:
            if self.type == self.DOWNLOAD:
                if self["list"].l.getCurrentSelection()[0].name.startswith("picons-"):
                    supported_filesystems = frozenset(('ext4', 'ext3', 'ext2', 'reiser', 'reiser4', 'jffs2', 'ubifs', 'rootfs'))
                    candidates = []
                    import Components.Harddisk
                    mounts = Components.Harddisk.getProcMounts()
                    for partition in harddiskmanager.getMountedPartitions(False, mounts):
                        if partition.filesystem(mounts) in supported_filesystems:
                            candidates.append((partition.description, partition.mountpoint))
                    if candidates:
                        from Components.Renderer import Picon
                        self.postInstallCall = Picon.initPiconPaths
                        self.session.openWithCallback(self.installDestinationCallback, ChoiceBox, title=_("Install picons on"), list=candidates)
                    return
                self.install_settings_name = self["list"].l.getCurrentSelection()[0].name
                if self["list"].l.getCurrentSelection()[0].name.startswith('settings-'):
                    self.check_settings = True
                    self.startOpkgListInstalled(self.PLUGIN_PREFIX + 'settings-*')
                else:
                    self.runSettingsInstall()
            elif self.type == self.REMOVE:
                self.doRemove(self.installFinished, self["list"].l.getCurrentSelection()[0].name)

    def doRemove(self, callback, pkgname):
        pkgname = self.PLUGIN_PREFIX + pkgname
        self.session.openWithCallback(callback, Console, cmdlist=[self.opkg_remove + Opkg.opkgExtraDestinations() + " " + pkgname, "sync"], skin="Console_Pig")

    def doInstall(self, callback, pkgname):
        pkgname = self.PLUGIN_PREFIX + pkgname
        self.session.openWithCallback(callback, Console, cmdlist=[self.opkg_install + " " + pkgname, "sync"], skin="Console_Pig")

    def runSettingsRemove(self, val):
        if val:
            self.doRemove(self.runSettingsInstall, self.remove_settings_name)

    def runSettingsInstall(self):
        self.doInstall(self.installFinished, self.install_settings_name)

    def startOpkgListInstalled(self, pkgname=PLUGIN_PREFIX + '*'):
        self.container.execute(self.opkg + Opkg.opkgExtraDestinations() + " list_installed '%s'" % pkgname)

    def startOpkgListAvailable(self):
        self.container.execute(self.opkg + Opkg.opkgExtraDestinations() + " list '" + self.PLUGIN_PREFIX + "*'")

    def startRun(self):
        listsize = self["list"].instance.size()
        self["list"].instance.hide()
        self.listWidth = listsize.width()
        self.listHeight = listsize.height()
        if self.type == self.DOWNLOAD:
            if self.needupdate and not PluginDownloadBrowser.lastDownloadDate or (time() - PluginDownloadBrowser.lastDownloadDate) > 3600:
                # Only update from internet once per hour
                self.container.execute(self.opkg + " update")
                PluginDownloadBrowser.lastDownloadDate = time()
            else:
                self.run = 1
                self.startOpkgListInstalled()
        elif self.type == self.REMOVE:
            self.run = 1
            self.startOpkgListInstalled()

    def installFinished(self):
        if hasattr(self, 'postInstallCall'):
            try:
                self.postInstallCall()
            except Exception as ex:
                print("[PluginBrowser] postInstallCall failed:", ex)
            self.resetPostInstall()
        try:
            os.unlink('/tmp/opkg.conf')
        except:
            pass
        for plugin in self.pluginlist:
            if plugin[3] == self["list"].l.getCurrentSelection()[0].name:
                self.pluginlist.remove(plugin)
                break
        self.plugins_changed = True
        if self["list"].l.getCurrentSelection()[0].name.startswith("settings-"):
            self.reload_settings = True
        if self["list"].l.getCurrentSelection()[0].name.startswith("softcams-"):
            self.check_softcams = True
        self.expanded = []
        self.updateList()
        self["list"].moveToIndex(0)

    def runFinished(self, retval):
        if self.check_settings:
            self.check_settings = False
            self.runSettingsInstall()
            return
        self.remainingdata = ""
        if self.run == 0:
            self.run = 1
            if self.type == self.DOWNLOAD:
                self.startOpkgListInstalled()
        elif self.run == 1 and self.type == self.DOWNLOAD:
            self.run = 2
            pluginlist = []
            self.pluginlist = pluginlist
            for plugin in Opkg.enumPlugins(self.PLUGIN_PREFIX):
                if plugin[0] not in self.installedplugins:
                    pluginlist.append(plugin + (plugin[0][15:],))
            if pluginlist:
                pluginlist.sort()
                self.updateList()
                self["text"].instance.hide()
                self["list"].instance.show()
            else:
                self["text"].setText(_("No new plugins found"))
        else:
            if self.pluginlist:
                self.updateList()
                self["text"].instance.hide()
                self["list"].instance.show()
            else:
                self["text"].setText(_("No new plugins found"))

    def dataAvail(self, str):
        #prepend any remaining data from the previous call
        str = self.remainingdata + str.decode(errors="ignore")
        #split in lines
        lines = str.split('\n')
        #'str' should end with '\n', so when splitting, the last line should be empty. If this is not the case, we received an incomplete line
        if len(lines[-1]):
            #remember this data for next time
            self.remainingdata = lines[-1]
            lines = lines[0:-1]
        else:
            self.remainingdata = ""

        if self.check_settings:
            self.check_settings = False
            self.remove_settings_name = str.split(' - ')[0].replace(self.PLUGIN_PREFIX, '')
            self.session.openWithCallback(self.runSettingsRemove, MessageBox, _('You already have a channel list installed,\nwould you like to remove\n"%s"?') % self.remove_settings_name)
            return

        if self.run == 1:
            for x in lines:
                plugin = x.split(" - ", 2)
                # 'opkg list_installed' only returns name + version, no description field
                if len(plugin) >= 2:
                    if not plugin[0].endswith('-dev') and not plugin[0].endswith('-staticdev') and not plugin[0].endswith('-dbg') and not plugin[0].endswith('-doc') and not plugin[0].endswith('-src'):
                        if plugin[0] not in self.installedplugins:
                            if self.type == self.DOWNLOAD:
                                self.installedplugins.append(plugin[0])
                            else:
                                if len(plugin) == 2:
                                    plugin.append('')
                                plugin.append(plugin[0][15:])
                                self.pluginlist.append(plugin)

    def updateList(self):
        list = []
        expandableIcon = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, "icons/expandable-plugins.png"))
        expandedIcon = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, "icons/expanded-plugins.png"))
        verticallineIcon = LoadPixmap(resolveFilename(SCOPE_CURRENT_SKIN, "icons/verticalline-plugins.png"))

        self.plugins = {}
        for x in self.pluginlist:
            split = x[3].split('-', 1)
            if len(split) < 2:
                continue
            if split[0] not in self.plugins:
                self.plugins[split[0]] = []

            self.plugins[split[0]].append((PluginDescriptor(name=x[3], description=x[2], icon=verticallineIcon), split[1], x[1]))

        for x in self.plugins.keys():
            if x in self.expanded:
                list.append(PluginCategoryComponent(x, expandedIcon, self.listWidth))
                list.extend([PluginDownloadComponent(plugin[0], plugin[1], plugin[2], self.listWidth) for plugin in self.plugins[x]])
            else:
                list.append(PluginCategoryComponent(x, expandableIcon, self.listWidth))
        self.list = list
        self["list"].l.setList(list)
