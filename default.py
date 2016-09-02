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
    listing = []
    services = espn.get_services()

    for name, service in services.items():
        listitem = xbmcgui.ListItem(label=name)
        listitem.setProperty('IsPlayable', 'false')
        parameters = {'action': 'main_menu', 'service': service}
        recursive_url = _url + '?' + urllib.urlencode(parameters)
        is_folder = True
        listing.append((recursive_url, listitem, is_folder))
    xbmcplugin.addDirectoryItems(_handle, listing, len(listing))
    xbmcplugin.endOfDirectory(_handle)


def main_menu(service):
    listing = []
    items = ['live', 'upcoming', 'archive', 'channels']

    for item in items:
        if item == 'live':
            game_status = 'inplay'
        else:
            game_status = item

        listitem = xbmcgui.ListItem(label=item.title())
        listitem.setProperty('IsPlayable', 'false')
        if item == 'channels':
            parameters = {'action': 'list_channels', 'service': service}
        else:
            parameters = {'action': 'list_games', 'service': service, 'game_status': game_status}
        recursive_url = _url + '?' + urllib.urlencode(parameters)
        is_folder = True
        listing.append((recursive_url, listitem, is_folder))
    xbmcplugin.addDirectoryItems(_handle, listing, len(listing))
    xbmcplugin.endOfDirectory(_handle)


def list_games(service, game_status):
    listing = []
    games = espn.get_games(service)

    for game in games:
        if game['game_status'] == game_status:
            listitem = xbmcgui.ListItem(label=game['name'])
            listitem.setProperty('IsPlayable', 'true')
            parameters = {'action': 'play_video', 'airringId': game['airringId']}
            recursive_url = _url + '?' + urllib.urlencode(parameters)
            is_folder = False
            listing.append((recursive_url, listitem, is_folder))
    xbmcplugin.addDirectoryItems(_handle, listing, len(listing))
    xbmcplugin.endOfDirectory(_handle)


def list_channels(service):
    listing = []
    channels = espn.get_channels(service)

    for name, id in channels.items():
        listitem = xbmcgui.ListItem(label=name)
        listitem.setProperty('IsPlayable', 'true')
        listitem.setArt({'thumb': 'http://neulionms-a.akamaihd.net/espn/player/espnplayer/static/images_v3/leagues/ESPN_COLLEGE_PASS/channel_logo_%s.png' % id})
        parameters = {'action': 'play_channel', 'airringId': '0', 'channel': id}
        recursive_url = _url + '?' + urllib.urlencode(parameters)
        is_folder = False
        listing.append((recursive_url, listitem, is_folder))
    xbmcplugin.addDirectoryItems(_handle, listing, len(listing))
    xbmcplugin.endOfDirectory(_handle)


def play_video(airringId, channel=None):
    if channel:
        stream_url = espn.get_stream_url(airringId, channel)
    else:
        stream_url = espn.get_stream_url(airringId)

    bitrate = select_bitrate(stream_url['bitrates'].keys())
    if bitrate:
        play_url = stream_url['bitrates'][bitrate]
        playitem = xbmcgui.ListItem(path=play_url)
        playitem.setProperty('IsPlayable', 'true')
        xbmcplugin.setResolvedUrl(_handle, True, listitem=playitem)


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
    else:
        preferred_bitrate = 'ask'

    manifest_bitrates.sort(key=int, reverse=True)
    if preferred_bitrate == 'highest':
        return manifest_bitrates[0]
    else:
        return ask_bitrate(manifest_bitrates)


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
        except espn.LoginFailure as error:
            addon_log('login failed')
            dialog = xbmcgui.Dialog()
            dialog.ok(language(30005),
                      language(30006))

            sys.exit(0)


if __name__ == '__main__':
    router(sys.argv[2][1:])  # trim the leading '?' from the plugin call paramstring
