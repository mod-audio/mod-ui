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

APP = bool(int(os.environ.get('MOD_APP', False)))
LOG = bool(int(os.environ.get('MOD_LOG', False)))

# Enable for testing carla instead of mod-host
HOST_CARLA = bool(int(os.environ.get('MOD_HOST_CARLA', False)))

API_KEY = os.environ.pop('MOD_API_KEY', '/usr/share/mod/keys/mod_api_key.pub')
DEVICE_KEY = os.environ.pop('MOD_DEVICE_KEY', None)
DEVICE_TAG = os.environ.pop('MOD_DEVICE_TAG', None)
DEVICE_UID = os.environ.pop('MOD_DEVICE_UID', None)
IMAGE_VERSION_PATH = os.environ.pop('MOD_IMAGE_VERSION_PATH', '/etc/mod-release/release')

if os.path.isfile(IMAGE_VERSION_PATH):
    with open(IMAGE_VERSION_PATH, 'r') as fh:
        IMAGE_VERSION = fh.read().strip() or None
else:
    IMAGE_VERSION = None

DATA_DIR = os.environ.get('MOD_DATA_DIR', '/dados')
KEYS_PATH = os.environ.get('MOD_KEYS_PATH', join(DATA_DIR, 'keys') + os.sep)
BANKS_JSON_FILE = os.environ.get('MOD_BANKS_JSON', join(DATA_DIR, 'banks.json'))
FAVORITES_JSON_FILE = os.environ.get('MOD_FAVORITES_JSON', join(DATA_DIR, 'favorites.json'))
LAST_STATE_JSON_FILE = os.environ.get('MOD_LAST_STATE_JSON', join(DATA_DIR, 'last.json'))
PREFERENCES_JSON_FILE = os.environ.get('MOD_PREFERENCES_JSON', join(DATA_DIR, 'prefs.json'))
USER_ID_JSON_FILE = os.environ.get('MOD_USER_ID_JSON', join(DATA_DIR, 'user-id.json'))

DOWNLOAD_TMP_DIR = os.environ.get('MOD_DOWNLOAD_TMP_DIR', '/tmp/mod-ui')

LV2_PLUGIN_DIR = os.path.expanduser("~/.lv2/")
LV2_PEDALBOARDS_DIR = os.path.expanduser("~/.pedalboards/")

HMI_BAUD_RATE = os.environ.get('MOD_HMI_BAUD_RATE', 10000000)
HMI_SERIAL_PORT = os.environ.get('MOD_HMI_SERIAL_PORT', "/dev/ttyUSB0")

DEVICE_WEBSERVER_PORT = int(os.environ.get('MOD_DEVICE_WEBSERVER_PORT', 80))

HTML_DIR = os.environ.get('MOD_HTML_DIR', join(sys.prefix, 'share/mod/html/'))
DEFAULT_PEDALBOARD_COPY = os.environ.pop('MOD_DEFAULT_PEDALBOARD', join(sys.prefix, 'share/mod/default.pedalboard'))
DEFAULT_PEDALBOARD = join(LV2_PEDALBOARDS_DIR, "default.pedalboard")

DEFAULT_ICON_TEMPLATE = join(HTML_DIR, 'resources/templates/pedal-default.html')
DEFAULT_SETTINGS_TEMPLATE = join(HTML_DIR, 'resources/settings.html')
DEFAULT_ICON_IMAGE = {
    'thumbnail': join(HTML_DIR, 'resources/pedals/default-thumbnail.png'),
    'screenshot': join(HTML_DIR, 'resources/pedals/default-screenshot.png')
}

PHANTOM_BINARY = os.environ.get('MOD_PHANTOM_BINARY', '/usr/bin/phantomjs')

SCREENSHOT_JS = os.environ.get('MOD_SCREENSHOT_JS', join(sys.prefix, 'share/mod/screenshot.js'))

MAX_THUMB_HEIGHT = 350
MAX_THUMB_WIDTH = 350

# Cloud API addresses
CLOUD_HTTP_ADDRESS = os.environ.pop('MOD_CLOUD_HTTP_ADDRESS', "http://api.dev.moddevices.com/v2")
PEDALBOARDS_HTTP_ADDRESS = os.environ.pop('MOD_PEDALBOARDS_HTTP_ADDRESS', "https://pedalboards-dev.moddevices.com")
CONTROLCHAIN_HTTP_ADDRESS = os.environ.pop('MOD_CONTROLCHAIN_HTTP_ADDRESS',
                                           "http://download.moddevices.com/releases/cc-firmware/v1")

TUNER = os.environ.get('MOD_TUNER_PLUGIN', "gxtuner")
TUNER_INSTANCE_ID = 9994

if TUNER == "tuna":
    TUNER_URI = "urn:mod:tuna"
    TUNER_INPUT_PORT = "in"
    TUNER_MONITOR_PORT = "freq_out"
else:
    TUNER_URI = "urn:mod:gxtuner"
    TUNER_INPUT_PORT = "in"
    TUNER_MONITOR_PORT = "FREQ"

PEDALBOARD_INSTANCE = "/pedalboard"
PEDALBOARD_INSTANCE_ID = 9995
PEDALBOARD_URI = "urn:mod:pedalboard"

CAPTURE_PATH='/tmp/capture.ogg'
PLAYBACK_PATH='/tmp/playback.ogg'

UPDATE_FILE='/data/modduo.tar'
USING_256_FRAMES_FILE='/data/using-256-frames'
