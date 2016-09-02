# -*- coding: utf-8 -*-
"""
A Kodi-agnostic library for ESPN Player
"""
import codecs
import os
import cookielib
import calendar
from datetime import datetime, timedelta
import time
from urllib import urlencode
import re
import json
import uuid
import HTMLParser

import requests
import xmltodict


class espnlib(object):
    def __init__(self, cookie_file, debug=False):
        self.debug = debug
        self.base_url = 'https://espnplayer.com/espnplayer'
        self.servlets_url = self.base_url + '/servlets'
        self.simpleconsole_url = self.servlets_url + '/simpleconsole'
        self.http_session = requests.Session()
        self.cookie_jar = cookielib.LWPCookieJar(cookie_file)
        try:
            self.cookie_jar.load(ignore_discard=True, ignore_expires=True)
        except IOError:
            pass
        self.http_session.cookies = self.cookie_jar

    class LoginFailure(Exception):
        def __init__(self, value):
            self.value = value

        def __str__(self):
            return repr(self.value)

    class AuthFailure(Exception):
        def __init__(self, value):
            self.value = value

        def __str__(self):
            return repr(self.value)

    def log(self, string):
        if self.debug:
            try:
                print '[espnlib]: %s' % string
            except UnicodeEncodeError:
                # we can't anticipate everything in unicode they might throw at
                # us, but we can handle a simple BOM
                bom = unicode(codecs.BOM_UTF8, 'utf8')
                print '[espnlib]: %s' % string.replace(bom, '')
            except:
                pass

    def make_request(self, url, method, payload=None, headers=None):
        """Make an http request. Return the response."""
        self.log('Request URL: %s' % url)
        self.log('Headers: %s' % headers)

        try:
            if method == 'get':
                req = self.http_session.get(url, params=payload, headers=headers, allow_redirects=False, verify=False)
            else:  # post
                req = self.http_session.post(url, data=payload, headers=headers, allow_redirects=False, verify=False)
            req.raise_for_status()
            self.log('Response code: %s' % req.status_code)
            self.log('Response: %s' % req.content)
            self.cookie_jar.save(ignore_discard=True, ignore_expires=False)
            return req.content
        except requests.exceptions.HTTPError as error:
            self.log('An HTTP error occurred: %s' % error)
            raise
        except requests.exceptions.ConnectionError as error:
            self.log('Connection Error: - %s' % error.message)
            raise
        except requests.exceptions.RequestException as error:
            self.log('Error: - %s' % error.value)
            raise
            
    def login(self, username=None, password=None):
        """Complete login process for ESPN Player. Errors (auth issues, blackout,
        etc) are raised as LoginFailure.
        """
        if self.check_for_subscription():
            self.log('Already logged into ESPN Player.')
        else:
            if username and password:
                self.log('Not (yet) logged into ESPN Player.')
                self.login_to_account(username, password)
                if not self.check_for_subscription():
                    raise self.LoginFailure('Login failed')

            else:
                self.log('No username and password supplied.')
                raise self.LoginFailure('No username and password supplied.')

    def login_to_account(self, username, password):
        """Blindly authenticate to ESPN Player. Use check_for_subscription() to
        determine success.
        """
        url = self.base_url + '/secure/login'
        post_data = {
            'username': username,
            'password': password
        }
        self.make_request(url=url, method='post', payload=post_data)
        
    def check_for_subscription(self):
        """Return whether a subscription and user name are detected. Determines
        whether a login was successful."""
        url = self.simpleconsole_url
        post_data = {'isFlex': 'true'}
        sc_data = self.make_request(url=url, method='post', payload=post_data)

        if '</userName>' not in sc_data:
            self.log('No user name detected in ESPN Player response.')
            return False
        elif '</subscriptions>' not in sc_data:
            self.log('No subscription detected in ESPN Player response.')
            return False
        else:
            self.log('Subscription and user name detected in ESPN Player response.')
            return True
            
    def get_services(self):
        """Return a dict of the services the user is subscribed to."""
        services = {}
        subscribed_services = []
        url = self.simpleconsole_url
        post_data = {'isFlex': 'true'}
        sc_data = self.make_request(url=url, method='post', payload=post_data)
        sc_dict = xmltodict.parse(sc_data)['result']
        
        for service in sc_dict['user']['subscriptions'].values():
            subscribed_services.append(service)
        
        for service in sc_dict['leagues']['league']:
            if service['type'] in subscribed_services:
                services[service['name']] = service['type']
        
        return services
        
    def get_games(self, product, category='all'):
        url = self.servlets_url + '/games'
        payload = {
            'product': product,
            'category': category,
            'format': 'xml'
        }
        
        game_data = self.make_request(url=url, method='get', payload=payload)
        game_dict = xmltodict.parse(game_data)['EspnPlayerGameData']
        games = game_dict['Games']['Game']
        
        return games
        
    def get_pkan(self, airingId):
        url = 'http://neulion.go.com/espngeo/dgetpkan'
        payload = {
            'airingId': airingId
        }
        pkan = self.make_request(url=url, method='get', payload=payload)
        return pkan
        
    def get_stream_url(self, airingId):
        url = 'http://neulion.go.com/espngeo/startSession'
        payload = {
            'channel': 'espn3',
            'simulcastAiringId': airingId,
            'playbackScenario': 'HTTP_CLOUD_WIRED',
            'playerId': 'neulion',
            'pkan': self.get_pkan(airingId),
            'pkanType': 'TOKEN',
            'tokenType': 'GATEKEEPER',
            'ttl': '480'
        }
        stream_data = self.make_request(url=url, method='post', payload=payload)
        stream_dict = xmltodict.parse(stream_data)['user-verified-media-response']
        stream_url = stream_dict['user-verified-event']['user-verified-content']['user-verified-media-item']['url']
        
        return stream_url
        
    def get_channels(self, product):
        channels = {}
        url = self.servlets_url + '/channels'
        channel_data = self.make_request(url=url, method='get', payload=payload)
        channel_dict = xmltodict.parse(channel_data)['channels']['channel']
        
        for channel in channel_dict:
            channel_name = channel['name']
            channel_id = channel['id']
            channels[channel_name] = channel_id
            
        return channels
