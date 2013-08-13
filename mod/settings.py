# -*- coding: utf-8 -*-

# Copyright 2012-2013 AGR Audio, Industria e Comercio LTDA. <contato@portalmod.com>
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
CONTROLLER_INSTALLED = bool(int(os.environ.get('MOD_CONTROLLER_INSTALLED', True)))

if DEV_ENVIRONMENT:
    ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
else:
    ROOT = os.getcwd()

DATA_DIR = os.environ.get('MOD_DATA_DIR', os.path.join(ROOT, 'dados'))

HARDWARE_DIR = os.environ.get('MOD_HARDWARE_DIR', os.path.join(DATA_DIR, 'hardware'))

KEYPATH = os.environ.get('MOD_KEY_PATH', join(ROOT, 'keys'))

CLOUD_PUB = os.environ.get('MOD_CLOUD_PUB', join(KEYPATH, 'cloud_key.pub'))
DEVICE_KEY = os.environ.get('MOD_DEVICE_KEY', join(KEYPATH, 'device_key.pem'))
DEVICE_PUB = os.environ.get('MOD_DEVICE_PUB', join(KEYPATH, 'device_key.pub'))
DEVICE_SERIAL = os.environ.get('MOD_DEVICE_SERIAL', join(KEYPATH, 'serial'))
DEVICE_MODEL =  os.environ.get('MOD_DEVICE_MODEL', join(KEYPATH, 'model'))

PLUGIN_LIBRARY_DIR = os.environ.get('MOD_PLUGIN_LIBRARY_DIR', join(DATA_DIR, 'lib'))
PLUGIN_INSTALLATION_TMP_DIR = os.environ.get('MOD_PLUGIN_INSTALLATION_DIR', join(DATA_DIR, 'lib_tmp'))
INDEX_PATH = os.environ.get('MOD_INDEX_PATH', join(DATA_DIR, 'effects.index'))
EFFECT_DIR = os.environ.get('MOD_EFFECT_DIR', join(DATA_DIR, 'effects'))
PEDALBOARD_DIR = os.environ.get('MOD_PEDALBOARD_DIR', join(DATA_DIR, 'pedalboards'))
PEDALBOARD_BINARY_DIR = join(PEDALBOARD_DIR, 'binary')
PEDALBOARD_INDEX_PATH = os.environ.get('MOD_PEDALBOARD_INDEX_PATH', join(DATA_DIR, 'pedalboards.index'))
BANKS_JSON_FILE = os.environ.get('MOD_BANKS_JSON', join(DATA_DIR, 'banks.json'))
BANKS_BINARY_FILE = os.environ.get('MOD_BANKS_BINARY', join(DATA_DIR, 'banks.bin'))
FAVORITES_DIR = os.environ.get('MOD_FAVORITES_DIR', join(DATA_DIR, 'favorites'))
DOWNLOAD_TMP_DIR = os.environ.get('MOD_DOWNLOAD_TMP_DIR', join(DATA_DIR, 'tmp/effects'))

UNITS_TTL_PATH = os.environ.get('MOD_UNITS_TTL_PATH', join(ROOT, '../units.ttl'))

CONTROLLER_SERIAL_PORT = os.environ.get('MOD_CONTROLLER_SERIAL_PORT', '/dev/ttyS0')
CONTROLLER_BAUD_RATE = os.environ.get('MOD_CONTROLLER_BAUD_RATE', 115200)
MANAGER_PORT = 5555

EFFECT_DB_FILE = os.environ.get('MOD_EFFECT_DB_FILE', join(DATA_DIR, 'effects.json'))

default_port = 8888 if DEV_ENVIRONMENT else 80
DEVICE_WEBSERVER_PORT = int(os.environ.get('MOD_DEVICE_WEBSERVER_PORT', default_port))

CLOUD_HTTP_ADDRESS = os.environ.get('MOD_CLOUD_HTTP_ADDRESS', 'http://cloud.portalmod.com/')

if DEV_ENVIRONMENT:
    default_html = os.path.join(ROOT, 'html')
else:
    default_html = os.path.join(sys.prefix, 'share', 'html')

HTML_DIR = os.environ.get('MOD_HTML_DIR', default_html)

DEFAULT_ICON_TEMPLATE = os.path.join(HTML_DIR, 'resources/templates/pedal-default.html')
DEFAULT_SETTINGS_TEMPLATE = os.path.join(HTML_DIR, 'resources/settings.html')
DEFAULT_ICON_IMAGE = { 'thumbnail': os.path.join(HTML_DIR, 'resources/pedals/default-thumbnail.png'),
                       'screenshot': os.path.join(HTML_DIR, 'resources/pedals/default-screenshot.png')
                       }

LOCAL_REPOSITORY_DIR = os.environ.get('MOD_LOCAL_REPOSITORY_DIR', '/pkgs')
BLUETOOTH_PIN = os.environ.get('MOD_BLUETOOTH_PIN', join(DATA_DIR, 'bluetooth.pin'))

PHANTOM_BINARY = os.path.join(ROOT, 'phantomjs-1.9.0-linux-x86_64/bin/phantomjs')
PHANTOM_BINARY = os.environ.get('MOD_PHANTOM_BINARY', PHANTOM_BINARY)

SCREENSHOT_JS = os.environ.get('MOD_SCREENSHOT_JS', join(ROOT, 'screenshot.js'))

MAX_THUMB_HEIGHT = 350
MAX_THUMB_WIDTH = 350
MAX_SCREENSHOT_HEIGHT = 1024
MAX_SCREENSHOT_WIDTH = 1024

DEFAULT_PACKAGE_SERVER_PORT = 8889
# If environment variable is not set, then the address will be built by javascript,
# using current host and default port above
PACKAGE_SERVER_ADDRESS = os.environ.get('MOD_PACKAGE_SERVER_ADDRESS')
PACKAGE_REPOSITORY = os.environ.get('MOD_PACKAGE_REPOSITORY', 'http://packages.portalmod.com/api')

CLIPMETER_URI = "http://portalmod.com/plugins/MOD/clipmeter"
CLIPMETER_IN = 9990
CLIPMETER_OUT = 9991
CLIPMETER_L = "inl"
CLIPMETER_R = "inr"
CLIPMETER_MON_L = "clipl"
CLIPMETER_MON_R = "clipr"

PEAKMETER_URI = "http://portalmod.com/plugins/MOD/peakmeter"
PEAKMETER_IN = 9992
PEAKMETER_OUT = 9993
PEAKMETER_L = "inl"
PEAKMETER_R = "inr"
PEAKMETER_MON_L = "meteroutl"
PEAKMETER_MON_R = "meteroutr"

TUNER_URI = "http://guitarix.sourceforge.net/plugins/gxtuner#tuner"
TUNER = 9994
TUNER_PORT = "in"
TUNER_MON_PORT = "FREQ"

for dirname in (PEDALBOARD_BINARY_DIR,
                PLUGIN_INSTALLATION_TMP_DIR,
		HARDWARE_DIR):
    if not os.path.exists(dirname):
        os.makedirs(dirname)
