import sys
import urlparse
import json

from resources.lib.kodihelper import KodiHelper

base_url = sys.argv[0]
handle = int(sys.argv[1])
helper = KodiHelper(base_url, handle)


def run():
    try:
        router(sys.argv[2][1:])  # trim the leading '?' from the plugin call paramstring
    except helper.espn.ESPNPlayerError as error:
        helper.dialog('ok', helper.language(30005), error.value)

def list_categories():
    categories = helper.espn.get_categories()
    for category in categories:
        helper.add_item(category['name'], params={})
    helper.eod()


def router(paramstring):
    """Router function that calls other functions depending on the provided paramstring."""
    params = dict(urlparse.parse_qsl(paramstring))
    if helper.has_prerequisites():
        if 'action' in params:
            if params['action'] == 'noop':
                pass
        else:
            list_categories()
