﻿# -*- coding: utf-8 -*-
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
    services = espn.get_services()

    if len(services) == 1:
        # list main menu directly if one service is found
        main_menu(services.values()[0])
    else:
        for name, service in services.items():
            parameters = {'action': 'main_menu', 'service': service}
            add_item(name, parameters)
        xbmcplugin.endOfDirectory(_handle)


def main_menu(service):
    listing = []
    items = ['live', 'upcoming', 'archive', 'channels']

    for item in items:
        if item == 'live':
            game_status = 'inplay'
        else:
            game_status = item

        title = item.title()
        if item == 'channels':
            parameters = {'action': 'list_channels', 'service': service}
        else:
            parameters = {'action': 'list_games', 'service': service, 'game_status': game_status}
            
        add_item(title, parameters)
    xbmcplugin.endOfDirectory(_handle)


def list_games(service, game_status):
    items = []
    games = espn.get_games(service)

    for game in games:
        game_date = espn.parse_datetime(game['game_date_GMT'], localize=True)
        if game['game_status'] == game_status:
            title = '%s (%s)' % (game['name'], game_date.strftime('%Y-%m-%d %H:%M'))
            game_image = game['game_image'].split('.jpg')[0] + '.jpg'
            parameters = {'action': 'play_video', 'airringId': game['airring_id']}
            
            art = {
                'thumb': game_image,
                'fanart': game_image,
                'cover': game_image,
            }
        
            items = add_item(title, parameters, items=items, playable=True, set_art=art)
    xbmcplugin.addDirectoryItems(_handle, items, len(items))
    xbmcplugin.endOfDirectory(_handle)


def list_channels(service):
    channels = espn.get_channels(service)

    for name, id in channels.items():
        listitem = xbmcgui.ListItem(label=name)
        listitem.setProperty('IsPlayable', 'true')
        art = {'thumb': 'http://a.espncdn.com/prod/assets/watchespn/appletv/images/channels-carousel/%s.png' % id}
        parameters = {'action': 'play_channel', 'airringId': '0', 'channel': id}
        add_item(name, parameters, playable=True, set_art=art)
    xbmcplugin.endOfDirectory(_handle)


def play_video(airringId, channel=None):
    if channel:
        stream_url = espn.get_stream_url(airringId, channel)
    else:
        stream_url = espn.get_stream_url(airringId)
    if stream_url['bitrates']:
        bitrate = select_bitrate(stream_url['bitrates'].keys())
        if bitrate:
            play_url = stream_url['bitrates'][bitrate]
            playitem = xbmcgui.ListItem(path=play_url)
            playitem.setProperty('IsPlayable', 'true')
            xbmcplugin.setResolvedUrl(_handle, True, listitem=playitem)
    else:
        dialog = xbmcgui.Dialog()
        dialog.ok(language(30005), language(30013))


def ask_bitrate(bitrates):
    """Presents a dialog for user to select from a list of bitrates.
    Returns the value of the selected bitrate."""
    options = []
    for bitrate in bitrates:
        options.append(bitrate + ' Kbps')
    dialog = xbmcgui.Dialog()
    ret = dialog.select(language(30010), options)
    if ret > -1:
        return bitrates[ret]


def select_bitrate(manifest_bitrates=None):
    """Returns a bitrate while honoring the user's preference."""
    bitrate_setting = int(addon.getSetting('preferred_bitrate'))
    if bitrate_setting == 0:
        preferred_bitrate = 'highest'
    elif bitrate_setting == 1:
        preferred_bitrate = 'limit'
    else:
        preferred_bitrate = 'ask'

    manifest_bitrates.sort(key=int, reverse=True)
    if preferred_bitrate == 'highest':
        return manifest_bitrates[0]
    elif preferred_bitrate == 'limit':
        allowed_bitrates = []
        max_bitrate_allowed = int(addon.getSetting('max_bitrate_allowed'))
        for bitrate in manifest_bitrates:
            if max_bitrate_allowed >= int(bitrate):
                allowed_bitrates.append(str(bitrate))
        if allowed_bitrates:
            return allowed_bitrates[0]
    else:
        return ask_bitrate(manifest_bitrates)

    
def add_item(title, parameters, items=False, folder=True, playable=False, set_info=False, set_art=False,
             watched=False, set_content=False):
    listitem = xbmcgui.ListItem(label=title)
    if playable:
        listitem.setProperty('IsPlayable', 'true')
        folder = False
    if set_art:
        listitem.setArt(set_art)
    else:
        listitem.setArt({'icon': os.path.join(addon_path, 'icon.png')})
        listitem.setArt({'fanart': os.path.join(addon_path, 'fanart.jpg')})
    if set_info:
        listitem.setInfo('video', set_info)
    if not watched:
        listitem.addStreamInfo('video', {'duration': 0})
    if set_content:
        xbmcplugin.setContent(_handle, set_content)

    listitem.setContentLookup(False)  # allows sending custom headers/cookies to ffmpeg
    recursive_url = _url + '?' + urllib.urlencode(parameters)

    if items is False:
        xbmcplugin.addDirectoryItem(_handle, recursive_url, listitem, folder)
    else:
        items.append((recursive_url, listitem, folder))
        return items


def router(paramstring):
    """Router function that calls other functions depending on the provided paramstring."""
    params = dict(urlparse.parse_qsl(paramstring))
    if params:
        if params['action'] == 'main_menu':
            main_menu(params['service'])
        elif params['action'] == 'list_channels':
            list_channels(params['service'])
        elif params['action'] == 'list_games':
            list_games(params['service'], params['game_status'])
        elif params['action'] == 'play_video':
            play_video(params['airringId'])
        elif params['action'] == 'play_channel':
            play_video(params['airringId'], params['channel'])
            
    else:
        try:
            espn.login(username, password)
            services_menu()
        except espn.LoginFailure:
            addon_log('login failed')
            dialog = xbmcgui.Dialog()
            dialog.ok(language(30005),
                      language(30006))

            sys.exit(0)


if __name__ == '__main__':
    router(sys.argv[2][1:])  # trim the leading '?' from the plugin call paramstring
