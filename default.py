# coding=utf-8
import os, sys
import xbmc, xbmcaddon, xbmcgui, xbmcplugin, urllib, xbmcvfs
import xml.etree.ElementTree as xmltree
import cPickle as pickle
import cProfile
import pstats
import random
import time
from time import gmtime, strftime
from datetime import datetime
from traceback import print_exc

if sys.version_info < (2, 7):
    import simplejson
else:
    import json as simplejson

__addon__        = xbmcaddon.Addon()
__addonid__      = __addon__.getAddonInfo('id').decode( 'utf-8' )
__addonversion__ = __addon__.getAddonInfo('version')
__language__     = __addon__.getLocalizedString
__cwd__          = __addon__.getAddonInfo('path').decode("utf-8")
__addonname__    = __addon__.getAddonInfo('name').decode("utf-8")
__resource__     = xbmc.translatePath( os.path.join( __cwd__, 'resources', 'lib' ) ).decode("utf-8")
__datapath__     = os.path.join( xbmc.translatePath( "special://profile/" ).decode( 'utf-8' ), "addon_data", __addonid__ )
__masterpath__   = os.path.join( xbmc.translatePath( "special://masterprofile/" ).decode( 'utf-8' ), "addon_data", __addonid__ )
__profilepath__  = xbmc.translatePath( "special://profile/" ).decode('utf-8')
__skinpath__     = xbmc.translatePath( "special://skin/shortcuts/" ).decode('utf-8')
__defaultpath__  = xbmc.translatePath( os.path.join( __cwd__, 'resources', 'shortcuts').encode("utf-8") ).decode("utf-8")

sys.path.append(__resource__)

import xmlfunctions
XML = xmlfunctions.XMLFunctions()
import datafunctions
DATA = datafunctions.DataFunctions()
import library
LIBRARY = library.LibraryFunctions()

hashlist = []

def log(txt):
    if isinstance (txt,str):
        txt = txt.decode('utf-8')
    message = u'%s: %s' % (__addonid__, txt)
    xbmc.log(msg=message.encode('utf-8'), level=xbmc.LOGDEBUG)
        
class Main:
    # MAIN ENTRY POINT
    def __init__(self):
        self._parse_argv()
        self.WINDOW = xbmcgui.Window(10000)         
        
        # Create data and master paths if not exists
        if not xbmcvfs.exists(__datapath__):
            xbmcvfs.mkdir(__datapath__)
        if not xbmcvfs.exists(__masterpath__):
            xbmcvfs.mkdir(__masterpath__)
        
        # Perform action specified by user
        if not self.TYPE:
            line1 = "This addon is for skin developers, and requires skin support"
            xbmcgui.Dialog().ok(__addonname__, line1)
            
        if self.TYPE=="buildxml":
            XML.buildMenu( self.MENUID, self.GROUP, self.LEVELS, self.MODE )
            
        if self.TYPE=="launch":
            xbmcplugin.setResolvedUrl( handle=int( sys.argv[1]), succeeded=False, listitem=xbmcgui.ListItem() )
            self._launch_shortcut( self.PATH )
        if self.TYPE=="launchpvr":
            xbmc.executeJSONRPC('{ "jsonrpc": "2.0", "id": 0, "method": "Player.Open", "params": { "item": {"channelid": ' + self.CHANNEL + '} } }')
        if self.TYPE=="manage":
            self._manage_shortcuts( self.GROUP, self.NOLABELS, self.GROUPNAME )
        if self.TYPE=="list":
            self._check_Window_Properties()
            self._list_shortcuts( self.GROUP )
        if self.TYPE=="submenu":
            self._check_Window_Properties()
            self._list_submenu( self.MENUID, self.LEVEL )
        if self.TYPE=="settings":
            self._check_Window_Properties()
            self._manage_shortcut_links() 
            
        if self.TYPE=="hidesubmenu":
            self._hidesubmenu( self.MENUID )
        if self.TYPE=="focusmenu":
            self._focus_menu( self.MENUID, self.LABELID, self.FOCUS, self.LENGTH )
            if self.SUBMENUID is not None:
                self._focus_menu( self.SUBMENUID, self.SUBLABELID, self.SUBFOCUS, self.SUBLENGTH )
            
        if self.TYPE=="shortcuts":
            # We're just going to choose a shortcut, and save its details to the given
            # skin labels
            xbmcgui.Window( 10000 ).clearProperty( "skinshortcuts-overrides-script" )
            xbmcgui.Window( 10000 ).clearProperty( "skinshortcuts-overrides-script-data" )
            xbmcgui.Window( 10000 ).clearProperty( "skinshortcuts-overrides-skin" )
            xbmcgui.Window( 10000 ).clearProperty( "skinshortcuts-overrides-skin-data" )
            xbmcgui.Window( 10000 ).clearProperty( "skinshortcuts-overrides-user" )
            xbmcgui.Window( 10000 ).clearProperty( "skinshortcuts-overrides-user-data" )
            xbmcgui.Window( 10000 ).clearProperty( "skinshortcutsAdditionalProperties" )
            
            selectedShortcut = LIBRARY.selectShortcut( "", custom = self.CUSTOM )
            
            # Now set the skin strings
            if selectedShortcut is not None:
                path = urllib.unquote( selectedShortcut.getProperty( "Path" ) )
                if selectedShortcut.getProperty( "chosenPath" ):
                    path = urllib.unquote( selectedShortcut.getProperty( "chosenPath" ) )

                if path.startswith( "pvr-channel://" ):
                    path = "RunScript(script.skinshortcuts,type=launchpvr&channel=" + path.replace( "pvr-channel://", "" ) + ")"
                if self.LABEL is not None and selectedShortcut.getLabel() != "":
                    xbmc.executebuiltin( "Skin.SetString(" + self.LABEL + "," + selectedShortcut.getLabel() + ")" )
                if self.ACTION is not None:
                    xbmc.executebuiltin( "Skin.SetString(" + self.ACTION + "," + path + " )" )
                if self.SHORTCUTTYPE is not None:
                    xbmc.executebuiltin( "Skin.SetString(" + self.SHORTCUTTYPE + "," + selectedShortcut.getLabel2() + ")" )
                if self.THUMBNAIL is not None and selectedShortcut.getProperty( "thumbnail" ):
                    # REWRITE, to better return thumb or icon
                    xbmc.executebuiltin( "Skin.SetString(" + self.THUMBNAIL + "," + selectedShortcut.getProperty( "thumbnail" ) + ")" )
                
        if self.TYPE=="resetall":
            # Tell XBMC not to try playing any media
            try:
                xbmcplugin.setResolvedUrl( handle=int( sys.argv[1]), succeeded=False, listitem=xbmcgui.ListItem() )
            except:
                log( "Not launched from a list item" )
            self._reset_all_shortcuts()

    def _parse_argv( self ):
        try:
            params = dict( arg.split( "=" ) for arg in sys.argv[ 1 ].split( "&" ) )
            self.TYPE = params.get( "type", "" )
        except:
            #print_exc()
            try:
                params = dict( arg.split( "=" ) for arg in sys.argv[ 2 ].split( "&" ) )
                self.TYPE = params.get( "?type", "" )
            except:
                self.TYPE = ""
                params = {}
        
        self.GROUP = params.get( "group", "" )
        self.GROUPNAME = params.get( "groupname", None )
        self.PATH = params.get( "path", "" )
        self.MENUID = params.get( "mainmenuID", "0" )
        self.LEVEL = params.get( "level", "" )
        self.LEVELS = params.get( "levels", "0" )
        self.CUSTOMID = params.get( "customid", "" )
        self.MODE = params.get( "mode", None )
        self.CHANNEL = params.get( "channel", None )
        self.LABELID = params.get( "labelid", None )
        
        self.FOCUS = params.get( "focus", None )
        self.LENGTH = params.get( "length", None )
        self.SUBMENUID = params.get( "submenuID", None )
        self.SUBLABELID = params.get( "sublabelid", None )
        self.SUBFOCUS = params.get( "subfocus", None )
        self.SUBLENGTH = params.get( "sublength", None )
        
        # Properties when using LIBRARY._displayShortcuts
        self.LABEL = params.get( "skinLabel", None )
        self.ACTION = params.get( "skinAction", None )
        self.SHORTCUTTYPE = params.get( "skinType", None )
        self.THUMBNAIL = params.get( "skinThumnbail", None )
        self.GROUPING = params.get( "grouping", None )
        self.CUSTOM = params.get( "custom", "False" )
        
        self.NOLABELS = params.get( "nolabels", "false" ).lower()
        
        
    def _check_Window_Properties( self ):
        # Check if the user has changed skin or profile
        if self.WINDOW.getProperty("skinsettings-currentSkin-Path") and self.WINDOW.getProperty("skinsettings-currentProfile-Path"):
            if self.WINDOW.getProperty("skinsettings-currentSkin-Path") != xbmc.getSkinDir().encode( 'utf-8' ) or self.WINDOW.getProperty("skinsettings-currentProfile-Path") != __profilepath__.encode( 'utf-8' ):
                self.reset_window_properties()
                self.WINDOW.setProperty("skinsettings-currentSkin-Path", xbmc.getSkinDir() )
                self.WINDOW.setProperty("skinsettings-currentProfile-Path", __profilepath__ )
        else:
            self.WINDOW.setProperty("skinsettings-currentSkin-Path", xbmc.getSkinDir() )
            self.WINDOW.setProperty("skinsettings-currentProfile-Path", __profilepath__ )
    
    
    # -----------------
    # PRIMARY FUNCTIONS
    # -----------------

    def _launch_shortcut( self, path ):
        log( "### Launching shortcut" )
        
        action = urllib.unquote( self.PATH )
        
        if action.find("::MULTIPLE::") == -1:
            # Single action, run it
            xbmc.executebuiltin( action )
        else:
            # Multiple actions, separated by |
            actions = action.split( "|" )
            for singleAction in actions:
                if singleAction != "::MULTIPLE::":
                    xbmc.executebuiltin( singleAction )
        
    
    def _manage_shortcuts( self, group, nolabels, groupname ):
        import gui
        ui= gui.GUI( "script-skinshortcuts.xml", __cwd__, "default", group=group, nolabels=nolabels, groupname=groupname )
        ui.doModal()
        del ui
        
        # Update home window property (used to automatically refresh type=settings)
        xbmcgui.Window( 10000 ).setProperty( "skinshortcuts",strftime( "%Y%m%d%H%M%S",gmtime() ) )
        
        # Clear window properties for this group, and for backgrounds, widgets, properties
        xbmcgui.Window( 10000 ).clearProperty( "skinshortcuts-" + group )        
        xbmcgui.Window( 10000 ).clearProperty( "skinshortcutsWidgets" )        
        xbmcgui.Window( 10000 ).clearProperty( "skinshortcutsCustomProperties" )        
        xbmcgui.Window( 10000 ).clearProperty( "skinshortcutsBackgrounds" )        
        

    def _list_shortcuts( self, group ):
        log( "### Listing shortcuts for group " + group )
        if group == "":
            log( "### - NO GROUP PASSED")
            # Return an empty list
            xbmcplugin.endOfDirectory(handle=int(sys.argv[1]))
            return None
        
        # Load shortcuts and overrides
        listitems = DATA._get_shortcuts( group )
        saveItems = []
        
        i = 0
        
        DATA._clear_labelID()
        
        for item in listitems:
            i += 1
            # Generate a listitem
            action = item[4].encode( "utf-8" )
            if urllib.unquote( action ).startswith( "pvr-channel://" ):
                log( " Changed action" )
                action = urllib.quote( "RunScript(script.skinshortcuts,type=launchpvr&channel=" + urllib.unquote( action ).replace( "pvr-channel://", "" ) + ")" )
            
            log( " - " + item[0] + " (" + action + ")" )
            
            path = sys.argv[0].decode( 'utf-8' ) + "?type=launch&path=" + action + "&group=" + self.GROUP
            
            listitem = xbmcgui.ListItem(label=item[0], label2=item[1], iconImage=item[2], thumbnailImage=item[3])
            listitem.setProperty( 'IsPlayable', 'True')
            if group == "mainmenu":
                listitem.setProperty( "labelID", DATA._get_labelID( item[5] ).encode('utf-8') )
            listitem.setProperty( "action", urllib.unquote( action ) )
            listitem.setProperty( "group", group )
            listitem.setProperty( "path", path )
            
            # Set an additional property to use for inbuilt submenu visibility
            listitem.setProperty( "submenuVisibility", str( i ) )
            
            # Localize label2 (type of shortcut)
            if not item[1].find( "::SCRIPT::" ) == -1:
                listitem.setLabel2( __language__( int( item[1][10:] ) ) )
                            
            # Add additional properties
            if len( item[6] ) != 0:
                repr( item[6] )
                for property in item[6]:
                    listitem.setProperty( property[0], property[1] )
                    log( " - Additional Property: " + property[0] + " = " + property[1] )
            
            saveItems.append( ( path, listitem ) )

        # Return the list
        xbmcplugin.addDirectoryItems( handle=int(sys.argv[1]), items=saveItems )
        xbmcplugin.endOfDirectory(handle=int(sys.argv[1]))
        
                
    def _list_submenu( self, mainmenuID, levelInt ):
        log( "### Listing submenu group " + mainmenuID )
        if mainmenuID == "0":
            log( "### - NO MAIN MENU ID PASSED")
            # Return an empty list
            xbmcplugin.endOfDirectory(handle=int(sys.argv[1]))
            return None
            
        fullMenu = True
        mainmenuListItems = []
        if self.GROUP:
            # Retrieve passed main menu items
            groups = self.GROUP.split( ",")
            for group in groups:
                mainmenuListItems.append( group )
            fullMenu = False
        else:
            # Load shortcuts for the main menu
            mainmenuListItems = DATA._get_shortcuts( "mainmenu" )
            
        saveItems = []
        
        i = 0
        
        for mainmenuItem in mainmenuListItems:
            i += 1
            # Load menu for each labelID
            mainmenuLabelID = mainmenuItem
            if fullMenu == True:
                mainmenuLabelID = mainmenuItem[5].encode( 'utf-8' )
                
            if levelInt == "":
                listitems = DATA._get_shortcuts( mainmenuLabelID )
            else:
                listitems = DATA._get_shortcuts( mainmenuLabelID + "." + levelInt )
            for item in listitems:
                action = item[4].encode( "utf-8" )
                if urllib.unquote( action ).startswith( "pvr-channel://" ):
                    log( " Changed action" )
                    action = urllib.quote( "RunScript(script.skinshortcuts,type=launchpvr&channel=" + urllib.unquote( action ).replace( "pvr-channel://", "" ) + ")" )
                
                log( " - " + item[0] + " (" + action + ")" )
                
                path = sys.argv[0].decode('utf-8') + "?type=launch&path=" + action + "&group=" + mainmenuLabelID.decode('utf-8')
                
                listitem = xbmcgui.ListItem(label=item[0], label2=item[1], iconImage=item[2], thumbnailImage=item[3])
                
                listitem.setProperty('IsPlayable', 'True')
                listitem.setProperty( "labelID", item[5].encode('utf-8') )
                listitem.setProperty( "action", urllib.unquote( action ) )
                listitem.setProperty( "group", mainmenuLabelID.decode('utf-8') )
                listitem.setProperty( "path", path )
                
                if fullMenu == True:
                    listitem.setProperty( "node.visible", "StringCompare(Container(" + mainmenuID + ").ListItem.Property(submenuVisibility)," + str( i ) + ")" )
                else:
                    listitem.setProperty( "node.visible", "StringCompare(Container(" + mainmenuID + ").ListItem.Property(submenuVisibility)," + mainmenuLabelID + ")" )
                
                # Localize label2 (type of shortcut)
                if not listitem.getLabel2().find( "::SCRIPT::" ) == -1:
                    listitem.setLabel2( __language__( int( listitem.getLabel2()[10:] ) ) )
                
                # Add additional properties
                if len( item[6] ) != 0:
                    for property in item[6]:
                        if property[0] == "node.visible":
                            listitem.setProperty( property[0], listitem.getProperty( "node.visible" ) + " + [" + property[1] + "]" )
                        else:
                            listitem.setProperty( property[0], property[1] )
                            log( " - Additional Property: " + property[0] + " = " + property[1] )
                
                saveItems.append( ( path, listitem ) )
        
        # Return the list
        xbmcplugin.addDirectoryItems( handle=int(sys.argv[1]), items=saveItems )
        xbmcplugin.endOfDirectory(handle=int(sys.argv[1]))
    

    def _reset_all_shortcuts( self ):
        log( "### Resetting all shortcuts" )
        dialog = xbmcgui.Dialog()
        
        # Ask the user if they're sure they want to do this
        if dialog.yesno(__language__(32037), __language__(32038)):
            for files in xbmcvfs.listdir( __datapath__ ):
                # Try deleting all shortcuts
                if files:
                    for file in files:
                        file_path = os.path.join( __datapath__, file.decode( 'utf-8' ) ).encode( 'utf-8' )
                        if xbmcvfs.exists( file_path ):
                            try:
                                xbmcvfs.delete( file_path )
                            except:
                                print_exc()
                                log( "### ERROR could not delete file %s" % file[0] )
        
            # Update home window property (used to automatically refresh type=settings)
            xbmcgui.Window( 10000 ).setProperty( "skinshortcuts",strftime( "%Y%m%d%H%M%S",gmtime() ) )   
            
            # Reset all window properties (so menus will be reloaded)
            self.reset_window_properties()
        
    
    # ----------------
    # SKINSETTINGS.XML
    # ----------------
    
    def _manage_shortcut_links ( self ):
        log( "### Generating list for skin settings" )
        pathAddition = ""
        
        # Create link to manage main menu
        if self.LEVEL == "":
            path = sys.argv[0].decode('utf-8') + "?type=launch&path=" + urllib.quote( "RunScript(script.skinshortcuts,type=manage&group=mainmenu&nolabels=" + self.NOLABELS + ")" )
            displayLabel = self._get_customised_settings_string("main")
            listitem = xbmcgui.ListItem(label=displayLabel, label2="", iconImage="DefaultShortcut.png", thumbnailImage="DefaultShortcut.png")
            listitem.setProperty('isPlayable', 'False')
            xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=path, listitem=listitem, isFolder=False)
        else:
            pathAddition = "." + self.LEVEL
        
        # Set path based on user defined mainmenu, then skin-provided, then script-provided
        if xbmcvfs.exists( os.path.join( __datapath__ , "mainmenu.shortcuts" ) ):
            # User defined shortcuts
            path = os.path.join( __datapath__ , "mainmenu.shortcuts" )
        elif xbmcvfs.exists( os.path.join( __skinpath__ , "mainmenu.shortcuts" ) ):
            # Skin-provided defaults
            path = os.path.join( __skinpath__ , "mainmenu.shortcuts" )
        elif xbmcvfs.exists( os.path.join( __defaultpath__ , "mainmenu.shortcuts" ) ):
            # Script-provided defaults
            path = os.path.join( __defaultpath__ , "mainmenu.shortcuts" )
        else:
            # No custom shortcuts or defaults available
            path = ""
            
        if not path == "":
            try:
                # Try loading shortcuts
                file = xbmcvfs.File( path )
                loaditems = eval( file.read() )
                file.close()
                
                listitems = []
                
                for item in loaditems:
                    itemEncoded = item[0].encode( 'utf-8' )
                    path = sys.argv[0].decode('utf-8') + "?type=launch&path=" + urllib.quote( "RunScript(script.skinshortcuts,type=manage&group=" + itemEncoded + pathAddition + "&nolabels=" + self.NOLABELS + ")" )
                    
                    # Get localised label
                    if not item[0].find( "::SCRIPT::" ) == -1:
                        localLabel = __language__(int( item[0][10:] ) )
                        path = sys.argv[0].decode('utf-8') + "?type=launch&path=" + urllib.quote( "RunScript(script.skinshortcuts,type=manage&group=" + self.createNiceName( item[0][10:] ).encode("ascii", "xmlcharrefreplace") + pathAddition + "&nolabels=" + self.NOLABELS + ")" )
                    elif not item[0].find( "::LOCAL::" ) == -1:
                        localLabel = xbmc.getLocalizedString(int( item[0][9:] ) )
                        path = sys.argv[0].decode('utf-8') + "?type=launch&path=" + urllib.quote( "RunScript(script.skinshortcuts,type=manage&group=" + self.createNiceName( item[0][9:] ).encode("ascii", "xmlcharrefreplace") + pathAddition + "&nolabels=" + self.NOLABELS + ")" )
                    else:
                        localLabel = item[0]
                        
                    # Get display label
                    displayLabel = self._get_customised_settings_string("submenu").replace("::MENUNAME::", localLabel)
                    
                    #listitem = xbmcgui.ListItem(label=__language__(32036) + item[0], label2="", iconImage="", thumbnailImage="")
                    listitem = xbmcgui.ListItem(label=displayLabel, label2="", iconImage="", thumbnailImage="")
                    listitem.setProperty('isPlayable', 'True')
                        
                    xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=path, listitem=listitem)

            except:
                print_exc()
                log( "### ERROR could not load file %s" % path )
        
        # Add a link to reset all shortcuts
        if self.LEVEL == "":
            path = sys.argv[0].decode('utf-8') + "?type=resetall"
            displayLabel = self._get_customised_settings_string("reset")
            listitem = xbmcgui.ListItem(label=displayLabel, label2="", iconImage="DefaultShortcut.png", thumbnailImage="DefaultShortcut.png")
            listitem.setProperty('isPlayable', 'True')
            xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=path, listitem=listitem)
        
        # Save the list
        xbmcplugin.endOfDirectory(handle=int(sys.argv[1]))
    
    
    def _get_customised_settings_string( self, group ):
        # This function will return the customised settings string for the given group
        tree = DATA._get_overrides_skin()
        if tree is not None:
            elems = tree.findall('settingslabel')
            for elem in elems:
                if elem is not None and elem.attrib.get( 'type' ) == group:
                    if self.LEVEL != "":
                        if elem.attrib.get( 'level' ) == self.LEVEL:
                            if elem.text.isdigit():
                                return xbmc.getLocalizedString( int( elem.text ) )
                            else:
                                return elem.text
                    else:
                        if 'level' not in elem.attrib:
                            if elem.text.isdigit():
                                return xbmc.getLocalizedString( int( elem.text ) )
                            else:
                                return elem.text
                                
        # If we get here, no string has been specified in overrides.xml
        if group == "main":
            return __language__(32035)
        elif group == "submenu" and self.LEVEL == "":
            return __language__(32036)
        elif group == "submenu" and self.LEVEL != "":
            return "::MENUNAME::"
        elif group == "reset":
            return __language__(32037)
        return "::MENUNAME::"
                            
    
    def reset_window_properties( self ):
        xbmcgui.Window( 10000 ).clearProperty( "skinshortcuts-overrides-skin" )
        xbmcgui.Window( 10000 ).clearProperty( "skinshortcutsAdditionalProperties" )
        xbmcgui.Window( 10000 ).clearProperty( "skinshortcuts-mainmenu" )
        listitems = DATA._get_shortcuts( "mainmenu" )
        for item in listitems:
            # Get labelID so we can check shortcuts for this menu item
            groupName = item[0].replace(" ", "").lower().encode('utf-8')
            
            # Localize strings
            if not item[0].find( "::SCRIPT::" ) == -1:
                groupName = DATA.createNiceName( item[0][10:] ).encode('utf-8')
            elif not item[0].find( "::LOCAL::" ) == -1:
                groupName = DATA.createNiceName( item[0][9:] ).encode('utf-8')
                
            # Clear the property
            xbmcgui.Window( 10000 ).clearProperty( "skinshortcuts-" + groupName )
            
            # Clear any additional submenus
            i = 0
            finished = False
            while finished == False:
                i = i + 1
                if xbmcgui.Window( 10000 ).getProperty( "skinshortcuts-" + groupName + "." + str( i ) ):
                    xbmcgui.Window( 10000 ).clearProperty( "skinshortcuts-" + groupName + "." + str( i ) )
                else:
                    finished = True
                    
    def _hidesubmenu( self, menuid ):
        count = 0
        while xbmc.getCondVisibility( "!IsEmpty(Container(" + menuid + ").ListItem(" + str( count ) + ").Property(isSubmenu))" ):
            count -= 1
            
        if count != 0:
            xbmc.executebuiltin( "Control.Move(" + menuid + "," + str( count ) + " )" )
        
        xbmc.executebuiltin( "ClearProperty(submenuVisibility, 10000)" )
        
    def _focus_menu( self, menuid, labelid, focus, length ):
        log( "### Setting Focus" )
        if focus is None:
            log( "Focus value needs to be set to focus menu" )
            
        xbmc.executebuiltin( "SetFocus(" + menuid + "," + focus + ")" )

        count = 0
        totalCount = int( xbmc.getInfoLabel("Container(" + menuid + ").NumItems" ) )
        maxCount = totalCount - int( length )
        log( "### Matched to " + labelid + " : " + xbmc.getInfoLabel("Container(" + menuid + ").ListItem.Property(labelID)" ) )
        
        if xbmc.getCondVisibility( "StringCompare(Container(" + menuid + ").ListItem.Property(labelID)," + labelid + ")" ):
            log( "The focus is correct" )
            # The focus has to be correct
            return
        
        log( "### Total items: " + str( totalCount ) )
        
        # Set to zero
        xbmc.executebuiltin( "SetFocus(" + menuid + ",1000)" )
        xbmc.executebuiltin( "Control.Move(" + menuid + ",1)" )
        
        # Find the item
        count = 0
        while xbmc.getCondVisibility( "!StringCompare(Container(" + menuid + ").ListItem(" + str( count ) + ").Property(labelID)," + labelid + ")" ):
            count += 1
            if count > (totalCount + 1):
                log( "### Can't find item" )
                return
            
        # We now know the offset we need
        offset = int( focus ) - count
        offset = -offset
        log( "### Found item at " + str( count ) + ", expected at " + focus + ". Therefore offset of " + str( offset ) + " needed" )
        xbmc.executebuiltin( "Control.Move(" + menuid + "," + str( int( length ) + offset ) + ")" )
        #xbmc.sleep( 100 )
        xbmc.executebuiltin( "SetFocus(" + menuid + "," + focus + ")" )
        #xbmc.sleep( 100 )
        log( "### matched to " + labelid + " : " + xbmc.getInfoLabel("Container(" + menuid + ").ListItem.Property(labelID)" ) )
        log( "### Finished" )
                    
if ( __name__ == "__main__" ):
    log('script version %s started' % __addonversion__)
    
    # Profiling
    #filename = os.path.join( __datapath__, strftime( "%Y%m%d%H%M%S",gmtime() ) + "-" + str( random.randrange(0,100000) ) + ".log" )
    #cProfile.run( 'Main()', filename )
    
    #stream = open( filename + ".txt", 'w')
    #p = pstats.Stats( filename, stream = stream )
    #p.sort_stats( "cumulative" )
    #p.print_stats()
    
    # No profiling
    Main()
    
    log('script stopped')