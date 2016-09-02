# -*- coding: utf-8 -*-
"""
A Kodi plugin for ESPN Player
"""
import sys
import os
import urllib
import urlparse

from resources.lib.espnlib import espnlib

import xbmc
import xbmcaddon
import xbmcvfs
import xbmcgui
import xbmcplugin

addon = xbmcaddon.Addon()
addon_path = xbmc.translatePath(addon.getAddonInfo('path'))
addon_profile = xbmc.translatePath(addon.getAddonInfo('profile'))
language = addon.getLocalizedString
logging_prefix = '[%s-%s]' % (addon.getAddonInfo('id'), addon.getAddonInfo('version'))

if not xbmcvfs.exists(addon_profile):
    xbmcvfs.mkdir(addon_profile)

_url = sys.argv[0]  # get the plugin url in plugin:// notation
_handle = int(sys.argv[1])  # get the plugin handle as an integer number

username = addon.getSetting('email')
password = addon.getSetting('password')
cookie_file = os.path.join(addon_profile, 'cookie_file')

if addon.getSetting('debug') == 'false':
    debug = False
else:
    debug = True

espn = espnlib(cookie_file, debug)


def addon_log(string):
    if debug:
        xbmc.log("%s: %s" % (logging_prefix, string))
        
def services_menu():
    listing = []
    services = espn.get_services()
    
    for name, service in services.items():
        listitem = xbmcgui.ListItem(label=name)
        listitem.setProperty('IsPlayable', 'false')
        parameters = {'action': 'list_games', 'service': service}
        recursive_url = _url + '?' + urllib.urlencode(parameters)
        is_folder = True
        listing.append((recursive_url, listitem, is_folder))
    xbmcplugin.addDirectoryItems(_handle, listing, len(listing))
    xbmcplugin.endOfDirectory(_handle)
    
def list_games(service):
    listing = []
    games = espn.get_games(service)
    
    for game in games:
        if game['game_status'] == 'inplay' or game['game_status'] == 'archive':
            listitem = xbmcgui.ListItem(label=game['name'])
            listitem.setProperty('IsPlayable', 'true')
            parameters = {'action': 'play_video', 'airringId': game['airringId']}
            recursive_url = _url + '?' + urllib.urlencode(parameters)
            is_folder = False
            listing.append((recursive_url, listitem, is_folder))
    xbmcplugin.addDirectoryItems(_handle, listing, len(listing))
    xbmcplugin.endOfDirectory(_handle)

    
def play_video(airringId):
    stream_url = espn.get_stream_url(airringId)
    playitem = xbmcgui.ListItem(path=stream_url)
    playitem.setProperty('IsPlayable', 'true')
    xbmcplugin.setResolvedUrl(_handle, True, listitem=playitem)

def router(paramstring):
    """Router function that calls other functions depending on the provided paramstring."""
    params = dict(urlparse.parse_qsl(paramstring))
    if params:
        if params['action'] == 'list_games':
            list_games(params['service'])
        elif params['action'] == 'play_video':
            play_video(params['airringId'])
    else:
    
        try:
            espn.login(username, password)
            services_menu()
        except espn.LoginFailure as error:
            addon_log('login failed')
            dialog = xbmcgui.Dialog()
            dialog.ok(language(30005),
                      language(30006))
            
            sys.exit(0)


if __name__ == '__main__':
    router(sys.argv[2][1:])  # trim the leading '?' from the plugin call paramstring
