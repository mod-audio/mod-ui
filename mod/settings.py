#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

import os, sys
from os.path import join

DEV_ENVIRONMENT = bool(int(os.environ.get('MOD_DEV_ENVIRONMENT', False)))
DEV_HMI = bool(int(os.environ.get('MOD_DEV_HMI', DEV_ENVIRONMENT)))
DEV_HOST = bool(int(os.environ.get('MOD_DEV_HOST', DEV_ENVIRONMENT)))

# If on, use dev cloud API environment
DEV_API = bool(int(os.environ.get('MOD_DEV_API', False)))

APP = bool(int(os.environ.get('MOD_APP', False)))
LOG = int(os.environ.get('MOD_LOG', 0))

API_KEY = os.environ.pop('MOD_API_KEY', None)
DEVICE_KEY = os.environ.pop('MOD_DEVICE_KEY', None)
DEVICE_TAG = os.environ.pop('MOD_DEVICE_TAG', None)
DEVICE_UID = os.environ.pop('MOD_DEVICE_UID', None)
IMAGE_VERSION_PATH = os.environ.pop('MOD_IMAGE_VERSION_PATH', '/etc/mod-release/release')
HARDWARE_DESC_FILE = os.environ.pop('MOD_HARDWARE_DESC_FILE', '/etc/mod-hardware-descriptor.json')

if os.path.isfile(IMAGE_VERSION_PATH):
    with open(IMAGE_VERSION_PATH, 'r') as fh:
        IMAGE_VERSION = fh.read().strip() or None
else:
    IMAGE_VERSION = None

DATA_DIR = os.environ.get('MOD_DATA_DIR', os.path.expanduser('~/data'))
CACHE_DIR = os.path.join(DATA_DIR, '.cache')
USER_FILES_DIR = os.environ.get('MOD_USER_FILES_DIR', '/data/user-files')
KEYS_PATH = os.environ.get('MOD_KEYS_PATH', join(DATA_DIR, 'keys'))
FAVORITES_JSON_FILE = os.environ.get('MOD_FAVORITES_JSON', join(DATA_DIR, 'favorites.json'))
LAST_STATE_JSON_FILE = os.environ.get('MOD_LAST_STATE_JSON', join(DATA_DIR, 'last.json'))
PREFERENCES_JSON_FILE = os.environ.get('MOD_PREFERENCES_JSON', join(DATA_DIR, 'prefs.json'))
USER_ID_JSON_FILE = os.environ.get('MOD_USER_ID_JSON', join(DATA_DIR, 'user-id.json'))

USER_BANKS_JSON_FILE = os.environ.get('MOD_USER_BANKS_JSON', join(DATA_DIR, 'banks.json'))
FACTORY_BANKS_JSON_FILE = os.environ.get('MOD_FACTORY_BANKS_JSON', '/usr/share/mod/banks.json')

# It's mandatory KEYS_PATH ends with / and is in MOD_KEYS_PATH,
# so utils_lilv.so can properly access it
if not KEYS_PATH.endswith('/'):
    KEYS_PATH += '/'
os.environ['MOD_KEYS_PATH'] = KEYS_PATH

DOWNLOAD_TMP_DIR = os.environ.get('MOD_DOWNLOAD_TMP_DIR', '/tmp/mod-ui')
PEDALBOARD_TMP_DIR = os.environ.get('MOD_PEDALBOARD_TMP_DIR', join(DATA_DIR, 'pedalboard-tmp-data'))

LV2_PLUGIN_DIR = os.path.expanduser("~/.lv2/")
LV2_PEDALBOARDS_DIR = os.environ.get('MOD_USER_PEDALBOARDS_DIR', os.path.expanduser("~/.pedalboards/"))
LV2_FACTORY_PEDALBOARDS_DIR = os.environ.get('MOD_FACTORY_PEDALBOARDS_DIR', "/usr/share/mod/pedalboards/")

HMI_BAUD_RATE = os.environ.get('MOD_HMI_BAUD_RATE', 10000000)
HMI_SERIAL_PORT = os.environ.get('MOD_HMI_SERIAL_PORT', "/dev/ttyUSB0")
HMI_TIMEOUT = int(os.environ.get('MOD_HMI_TIMEOUT', 0))

MODEL_CPU = os.environ.get('MOD_MODEL_CPU', None)
MODEL_TYPE = os.environ.get('MOD_MODEL_TYPE', None)

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

# Cloud API addresses
CLOUD_HTTP_ADDRESS = os.environ.pop('MOD_CLOUD_HTTP_ADDRESS', "https://api-dev.mod.audio/v2")
CLOUD_LABS_HTTP_ADDRESS = os.environ.pop('MOD_CLOUD_LABS_HTTP_ADDRESS', "https://api-labs.mod.audio/v2")
PLUGINS_HTTP_ADDRESS = os.environ.pop('MOD_PLUGINS_HTTP_ADDRESS', "https://pedalboards.mod.audio/plugins")
PEDALBOARDS_HTTP_ADDRESS = os.environ.pop('MOD_PEDALBOARDS_HTTP_ADDRESS', "https://pedalboards-dev.mod.audio")
PEDALBOARDS_LABS_HTTP_ADDRESS = os.environ.pop('MOD_PEDALBOARDS_LABS_HTTP_ADDRESS', "https://pedalboards-labs.mod.audio")
CONTROLCHAIN_HTTP_ADDRESS = os.environ.pop('MOD_CONTROLCHAIN_HTTP_ADDRESS',
                                           "https://download.mod.audio/releases/cc-firmware/v2")

MIDI_BEAT_CLOCK_SENDER_URI = "urn:mod:mclk"
MIDI_BEAT_CLOCK_SENDER_INSTANCE_ID = 9993
MIDI_BEAT_CLOCK_SENDER_OUTPUT_PORT = "mclk" # This is the LV2 symbol of the plug-ins OutputPort

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

UNTITLED_PEDALBOARD_NAME="Untitled Pedalboard"
DEFAULT_SNAPSHOT_NAME="Default"

CAPTURE_PATH='/tmp/capture.ogg'
PLAYBACK_PATH='/tmp/playback.ogg'

UPDATE_MOD_OS_FILE='/data/{}'.format(os.environ.get('MOD_UPDATE_MOD_OS_FILE', 'modduo.tar').replace('*','cloud'))
UPDATE_MOD_OS_HERLPER_FILE='/data/boot-restore'
UPDATE_CC_FIRMWARE_FILE='/tmp/cc-firmware.bin'
USING_256_FRAMES_FILE='/data/using-256-frames'
