# -*- coding: utf-8 -*-

# Copyright 2012-2013 AGR Audio, Industria e Comercio LTDA. <contato@moddevices.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os, sys
from os.path import join

DEV_ENVIRONMENT = bool(int(os.environ.get('MOD_DEV_ENVIRONMENT', False)))
DEV_HMI = bool(int(os.environ.get('MOD_DEV_HMI', DEV_ENVIRONMENT)))
DEV_HOST = bool(int(os.environ.get('MOD_DEV_HOST', DEV_ENVIRONMENT)))

LOG = bool(int(os.environ.get('MOD_LOG', False)))

APP     = bool(int(os.environ.get('MOD_APP', False)))
DESKTOP = bool(int(os.environ.get('MOD_DESKTOP', False)))

# Enable for testing carla instead of mod-host
HOST_CARLA = bool(int(os.environ.get('MOD_HOST_CARLA', False)))

API_KEY = os.environ.get('MOD_API_KEY', '/usr/share/mod/keys/mod_api_key.pub')
DEVICE_KEY = os.environ.get('MOD_DEVICE_KEY')
DEVICE_TAG = os.environ.get('MOD_DEVICE_TAG')
DEVICE_UID = os.environ.get('MOD_DEVICE_UID')
KEYPATH = os.environ.get('MOD_KEY_PATH', '/root/keys')
DEVICE_SERIAL = os.environ.get('MOD_DEVICE_SERIAL', join(KEYPATH, 'serial'))
DEVICE_MODEL = os.environ.get('MOD_DEVICE_MODEL', join(KEYPATH, 'model'))

DATA_DIR = os.environ.get('MOD_DATA_DIR', '/dados')
BANKS_JSON_FILE = os.environ.get('MOD_BANKS_JSON', join(DATA_DIR, 'banks.json'))
LAST_STATE_JSON_FILE = os.environ.get('MOD_LAST_STATE_JSON', join(DATA_DIR, 'last.json'))

DOWNLOAD_TMP_DIR = os.environ.get('MOD_DOWNLOAD_TMP_DIR', '/tmp/mod-ui')

LV2_PLUGIN_DIR = os.path.expanduser("~/.lv2/")
LV2_PEDALBOARDS_DIR = os.path.expanduser("~/.pedalboards/")

HMI_BAUD_RATE = os.environ.get('MOD_HMI_BAUD_RATE', 10000000)
HMI_SERIAL_PORT = os.environ.get('MOD_HMI_SERIAL_PORT')

MANAGER_PORT = 5555

DEVICE_WEBSERVER_PORT = int(os.environ.get('MOD_DEVICE_WEBSERVER_PORT', 80))

HTML_DIR = os.environ.get('MOD_HTML_DIR', join(sys.prefix, 'share/mod/html/'))

DEFAULT_ICON_TEMPLATE = join(HTML_DIR, 'resources/templates/pedal-default.html')
DEFAULT_SETTINGS_TEMPLATE = join(HTML_DIR, 'resources/settings.html')
DEFAULT_ICON_IMAGE = { 'thumbnail': join(HTML_DIR, 'resources/pedals/default-thumbnail.png'),
                       'screenshot': join(HTML_DIR, 'resources/pedals/default-screenshot.png')
                       }

BLUETOOTH_PIN = os.environ.get('MOD_BLUETOOTH_PIN', join(DATA_DIR, 'bluetooth.pin'))

PHANTOM_BINARY = os.environ.get('MOD_PHANTOM_BINARY', '/usr/bin/phantomjs')

SCREENSHOT_JS = os.environ.get('MOD_SCREENSHOT_JS', join(sys.prefix, 'share/mod/screenshot.js'))

MAX_THUMB_HEIGHT = 350
MAX_THUMB_WIDTH = 350
MAX_SCREENSHOT_HEIGHT = 1024
MAX_SCREENSHOT_WIDTH = 1024

DEFAULT_PACKAGE_SERVER_PORT = 8889
# If environment variable is not set, then the address will be built by javascript,
# using current host and default port above
PACKAGE_SERVER_ADDRESS = os.environ.get('MOD_PACKAGE_SERVER_ADDRESS')

CLOUD_HTTP_ADDRESS = os.environ.get('MOD_CLOUD_HTTP_ADDRESS', "http://api.dev.moddevices.com")

if os.path.exists("/root/repository"):
    fh = open("/root/repository")
    default_repo = fh.read().strip()
    fh.close()
else:
    default_repo = 'http://packages.moddevices.com/api'
PACKAGE_REPOSITORY = os.environ.get('MOD_PACKAGE_REPOSITORY', default_repo)

if os.path.exists("/root/avatar"):
    fh = open("/root/avatar")
    default_avatar_url = fh.read().strip()
    fh.close()
else:
    default_avatar_url = 'http://gravatar.com/avatar'
AVATAR_URL = os.environ.get('MOD_AVATAR_URL', default_avatar_url)

TUNER_URI = "http://guitarix.sourceforge.net/plugins/gxtuner#tuner"
TUNER = 9994
TUNER_PORT = "in"
TUNER_MON_PORT = "FREQ"

JS_CUSTOM_CHANNEL = bool(int(os.environ.get('MOD_JS_CUSTOM_CHANNEL', False)))
AUTO_CLOUD_BACKUP = bool(int(os.environ.get('MOD_AUTO_CLOUD_BACKUP', False)))

CAPTURE_PATH='/tmp/capture.ogg'
PLAYBACK_PATH='/tmp/playback.ogg'
