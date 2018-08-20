# -*- coding: utf-8 -*-
"""
A Kodi-agnostic library for ESPN Player
"""
import json
import codecs
import cookielib
import calendar
import time
import os
import uuid
from urllib import urlencode
from datetime import datetime, timedelta

import requests
import m3u8
import xmltodict


class ESPNPlayer(object):
    def __init__(self, settings_folder, debug=False):
        self.debug = debug
        self.http_session = requests.Session()
        self.settings_folder = settings_folder
        self.cookie_jar = cookielib.LWPCookieJar(os.path.join(self.settings_folder, 'cookie_file'))
        self.credentials_file = os.path.join(settings_folder, 'credentials')
        self.credentials = self.get_credentials()
        self.base_url = 'https://www.espnplayer.com'
        try:
            self.cookie_jar.load(ignore_discard=True, ignore_expires=True)
        except IOError:
            pass
        self.http_session.cookies = self.cookie_jar

    class ESPNPlayerError(Exception):
        def __init__(self, value):
            self.value = value

        def __str__(self):
            return repr(self.value)

    def log(self, string):
        if self.debug:
            try:
                print '[ESPN Player]: %s' % string
            except UnicodeEncodeError:
                # we can't anticipate everything in unicode they might throw at
                # us, but we can handle a simple BOM
                bom = unicode(codecs.BOM_UTF8, 'utf8')
                print '[ESPN Player]: %s' % string.replace(bom, '')
            except:
                pass

    def make_request(self, url, method, params=None, payload=None, headers=None):
        """Make an HTTP request. Return the response."""
        self.log('Request URL: %s' % url)
        self.log('Method: %s' % method)
        if params:
            self.log('Params: %s' % params)
        if payload:
            self.log('Payload: %s' % payload)
        if headers:
            self.log('Headers: %s' % headers)

        if method == 'get':
            req = self.http_session.get(url, params=params, headers=headers)
        elif method == 'put':
            req = self.http_session.put(url, params=params, data=payload, headers=headers)
        else:  # post
            req = self.http_session.post(url, params=params, data=payload, headers=headers)
        self.log('Response code: %s' % req.status_code)
        self.log('Response: %s' % req.content)
        self.cookie_jar.save(ignore_discard=True, ignore_expires=False)

        try:
            return json.loads(req.content)
        except ValueError:
            return req.content

    def login(self, username=None, password=None):
        """Login process for ESPN Player."""
        url = self.base_url + '/secure/authenticate'
        if self.credentials.get('token'):
            payload = {'token': self.credentials['token']}
        else:
            payload = {
                'username': username,
                'password': password,
                'deviceid': str(uuid.uuid4()),
                'devicetype': '8'
            }

        payload['format'] = 'json'
        headers = {'User-Agent': 'Android'}
        data = self.make_request(url, method='post', payload=payload, headers=headers)

        if data['code'] == 'loginsuccess':
            self.save_credentials(data['data'])
            return True
        else:
            raise self.ESPNPlayerError(data['code'])

    def get_categories(self):
        url = self.base_url + '/category/espnplayer'
        params = {'format': 'json'}
        data = self.make_request(url, method='get', params=params)

        return data['subCategories']

    def get_schedule(self, service):
        url = self.base_url + '/schedule'
        params = {
            'lid': service,
            'ps': '300',
            'format': 'json'
        }

        schedule = self.make_request(url, method='get', params=params)
        return schedule

    def get_channels(self):
        url = self.base_url + '/channels'
        params = {'format': 'json'}
        data = self.make_request(url, method='get', params=params)
        return data

    def get_pkan(self, airing_id):
        """Return a 'pkan' token needed to request a stream URL."""
        url = 'http://neulion.go.com/espngeo/dgetpkan'
        payload = {
            'airingId': airing_id
        }
        pkan = self.make_request(url=url, method='get', payload=payload)
        return pkan

    def get_stream_url(self, airing_id, channel='espn3'):
        """Return the URL for a stream. _mediaAuth cookie is needed for decryption."""
        stream_url = {}
        auth_cookie = None
        url = 'http://neulion.go.com/espngeo/startSession'
        payload = {
            'channel': channel,
            'simulcastAiringId': airing_id,
            'playbackScenario': 'HTTP_CLOUD_WIRED',
            'playerId': 'neulion',
            'pkan': self.get_pkan(airing_id),
            'pkanType': 'TOKEN',
            'tokenType': 'GATEKEEPER',
            'ttl': '480'
        }
        req = self.make_request(url=url, method='post', payload=payload)
        stream_data = req.content

        try:
            stream_dict = xmltodict.parse(stream_data)['user-verified-media-response']['user-verified-event']['user-verified-content']['user-verified-media-item']
        except KeyError:
            self.log('Unable to get stream dict.')
            return False

        if req.cookies:
            self.log('Cookies: %s' % req.cookies)
            for cookie in req.cookies:
                if cookie.name == '_mediaAuth':
                    auth_cookie = '%s=%s; path=%s; domain=%s;' % (cookie.name, cookie.value, cookie.path, cookie.domain)

        if stream_dict['url']:
            stream_url['manifest'] = stream_dict['url']
            self.log('HLS manifest found (primary).')
        elif stream_dict['hls-backup-url']:
            stream_url['manifest'] = stream_dict['hls-backup-url']
            self.log('HLS manifest found (backup).')
        elif stream_dict['alt-url']:
            stream_url['manifest'] = stream_dict['alt-url']
            self.log('HLS manifest found (alternative).')
        else:
            stream_url['manifest'] = None
            self.log('No HLS manifest found.')

        if stream_url['manifest']:
            if stream_url['manifest'].startswith('http'):
                stream_url['bitrates'] = self.parse_m3u8_manifest(stream_url['manifest'], auth_cookie=auth_cookie)
            else:
                stream_url['bitrates'] = []
                self.log('Invalid manifest URL found: %s' % stream_url['manifest'])

        return stream_url

    def parse_m3u8_manifest(self, manifest_url, auth_cookie=None):
        """Return the stream URL along with its bitrate."""
        streams = {}
        m3u8_manifest = self.make_request(manifest_url, method='get')

        m3u8_header = {'Cookie': auth_cookie}
        m3u8_obj = m3u8.loads(m3u8_manifest)

        for playlist in m3u8_obj.playlists:
            bitrate = int(playlist.stream_info.bandwidth) / 1000
            if playlist.uri.startswith('http'):
                stream_url = playlist.uri
            else:
                stream_url = manifest_url[:manifest_url.rfind('/') + 1] + playlist.uri
            streams[str(bitrate)] = stream_url + '|' + urlencode(m3u8_header)

        return streams

    def save_credentials(self, credentials):
        if 'token' not in credentials and self.get_credentials().get('token'):
            credentials['token'] = self.get_credentials()['token']  # resave token
        with open(self.credentials_file, 'w') as fh_credentials:
            fh_credentials.write(json.dumps(credentials))

    def reset_credentials(self):
        credentials = {}
        with open(self.credentials_file, 'w') as fh_credentials:
            fh_credentials.write(json.dumps(credentials))

    def get_credentials(self):
        try:
            with open(self.credentials_file, 'r') as fh_credentials:
                credentials_dict = json.loads(fh_credentials.read())
                return credentials_dict
        except IOError:
            self.reset_credentials()
            with open(self.credentials_file, 'r') as fh_credentials:
                return json.loads(fh_credentials.read())

    def parse_datetime(self, game_date, localize=False):
        """Parse ESPN Player date string to datetime object."""
        date_time_format = '%Y-%m-%dT%H:%M:%S.000'
        datetime_obj = datetime(*(time.strptime(game_date, date_time_format)[0:6]))
        if localize:
            return self.utc_to_local(datetime_obj)
        else:
            return datetime_obj

    @staticmethod
    def utc_to_local(self, utc_dt):
        """Convert UTC time to local time."""
        # get integer timestamp to avoid precision lost
        timestamp = calendar.timegm(utc_dt.timetuple())
        local_dt = datetime.fromtimestamp(timestamp)
        assert utc_dt.resolution >= timedelta(microseconds=1)
        return local_dt.replace(microsecond=utc_dt.microsecond)
