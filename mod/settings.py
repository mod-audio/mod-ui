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
DEV_HMI = bool(int(os.environ.get('MOD_DEV_HMI', DEV_ENVIRONMENT)))
DEV_HOST = bool(int(os.environ.get('MOD_DEV_HOST', DEV_ENVIRONMENT)))

LOG = bool(int(os.environ.get('MOD_LOG', True)))

DATA_DIR = os.environ.get('MOD_DATA_DIR', '/dados')
DEMO_DATA_DIR = os.environ.get('MOD_DEMO_DATA_DIR', DATA_DIR + '.demo')

HARDWARE_DIR = os.environ.get('MOD_HARDWARE_DIR', join(DATA_DIR, 'hardware'))

KEYPATH = os.environ.get('MOD_KEY_PATH', '/root/keys')

CLOUD_PUB = os.environ.get('MOD_CLOUD_PUB', join(KEYPATH, 'cloud_key.pub'))
DEVICE_KEY = os.environ.get('MOD_DEVICE_KEY', join(KEYPATH, 'device_key.pem'))
DEVICE_PUB = os.environ.get('MOD_DEVICE_PUB', join(KEYPATH, 'device_key.pub'))
DEVICE_SERIAL = os.environ.get('MOD_DEVICE_SERIAL', join(KEYPATH, 'serial'))
DEVICE_MODEL =  os.environ.get('MOD_DEVICE_MODEL', join(KEYPATH, 'model'))

PLUGIN_LIBRARY_DIR = os.environ.get('MOD_PLUGIN_LIBRARY_DIR', '/dados/plugins')
PLUGIN_INSTALLATION_TMP_DIR = os.environ.get('MOD_PLUGIN_INSTALLATION_DIR', join(DATA_DIR, 'lib_tmp'))
INDEX_PATH = os.environ.get('MOD_INDEX_PATH', join(DATA_DIR, 'effects.index'))
EFFECT_DIR = os.environ.get('MOD_EFFECT_DIR', join(DATA_DIR, 'effects'))
PEDALBOARD_DIR = os.environ.get('MOD_PEDALBOARD_DIR', join(DATA_DIR, 'pedalboards'))
PEDALBOARD_BINARY_DIR = join(PEDALBOARD_DIR, 'binary')
PEDALBOARD_INDEX_PATH = os.environ.get('MOD_PEDALBOARD_INDEX_PATH', join(DATA_DIR, 'pedalboards.index'))
BANKS_JSON_FILE = os.environ.get('MOD_BANKS_JSON', join(DATA_DIR, 'banks.json'))
BANKS_BINARY_FILE = os.environ.get('MOD_BANKS_BINARY', join(DATA_DIR, 'banks.bin'))
DOWNLOAD_TMP_DIR = os.environ.get('MOD_DOWNLOAD_TMP_DIR', join(DATA_DIR, 'tmp/effects'))

UNITS_TTL_PATH = os.environ.get('MOD_UNITS_TTL_PATH', '/usr/lib/lv2/units.lv2/units.ttl')

HMI_BAUD_RATE = os.environ.get('MOD_HMI_BAUD_RATE', 10000000)

def get_tty_acm():
    if DEV_HMI:
        return # doesn't matter, connection won't ever be made
    import glob, serial
    for tty in glob.glob("/dev/ttyACM*"):
        try:
            s = serial.Serial(tty, HMI_BAUD_RATE)
        except (serial.serialutil.SerialException, ValueError) as e:
            next
        else:
            s.close()
            return tty
    return  "/dev/ttyACM0"

HMI_SERIAL_PORT = os.environ.get('MOD_HMI_SERIAL_PORT', get_tty_acm())
MANAGER_PORT = 5555

EFFECT_DB_FILE = os.environ.get('MOD_EFFECT_DB_FILE', join(DATA_DIR, 'effects.json'))

DEVICE_WEBSERVER_PORT = int(os.environ.get('MOD_DEVICE_WEBSERVER_PORT', 80))

HTML_DIR = os.environ.get('MOD_HTML_DIR', '/usr/share/mod-ui/html/')

DEFAULT_ICON_TEMPLATE = join(HTML_DIR, 'resources/templates/pedal-default.html')
DEFAULT_SETTINGS_TEMPLATE = join(HTML_DIR, 'resources/settings.html')
DEFAULT_ICON_IMAGE = { 'thumbnail': join(HTML_DIR, 'resources/pedals/default-thumbnail.png'),
                       'screenshot': join(HTML_DIR, 'resources/pedals/default-screenshot.png')
                       }

LOCAL_REPOSITORY_DIR = os.environ.get('MOD_LOCAL_REPOSITORY_DIR', '/pkgs')
BLUETOOTH_PIN = os.environ.get('MOD_BLUETOOTH_PIN', join(DATA_DIR, 'bluetooth.pin'))

PHANTOM_BINARY = os.environ.get('MOD_PHANTOM_BINARY', '/usr/bin/phantomjs')

SCREENSHOT_JS = os.environ.get('MOD_SCREENSHOT_JS', '/usr/lib/mod-ui/screenshot.js')

MAX_THUMB_HEIGHT = 350
MAX_THUMB_WIDTH = 350
MAX_SCREENSHOT_HEIGHT = 1024
MAX_SCREENSHOT_WIDTH = 1024

DEFAULT_PACKAGE_SERVER_PORT = 8889
# If environment variable is not set, then the address will be built by javascript,
# using current host and default port above
PACKAGE_SERVER_ADDRESS = os.environ.get('MOD_PACKAGE_SERVER_ADDRESS')

if os.path.exists("/root/cloud"):
    fh = open("/root/cloud")
    default_cloud = fh.read().strip()
    fh.close()
else:
    default_cloud = 'http://cloud.portalmod.com/'
CLOUD_HTTP_ADDRESS = os.environ.get('MOD_CLOUD_HTTP_ADDRESS', default_cloud)
if not CLOUD_HTTP_ADDRESS.endswith('/'):
    CLOUD_HTTP_ADDRESS += '/'


if os.path.exists("/root/repository"):
    fh = open("/root/repository")
    default_repo = fh.read().strip()
    fh.close()
else:
    default_repo = 'http://packages.portalmod.com/api'
PACKAGE_REPOSITORY = os.environ.get('MOD_PACKAGE_REPOSITORY', default_repo)

if os.path.exists("/root/avatar"):
    fh = open("/root/avatar")
    default_avatar_url = fh.read().strip()
    fh.close()
else:    
    default_avatar_url = 'http://gravatar.com/avatar'
AVATAR_URL = os.environ.get('MOD_AVATAR_URL', default_avatar_url)

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
