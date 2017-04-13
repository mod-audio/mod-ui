#!/usr/bin/env python3

# FOR DEVELOPMENT PURPOSES ONLY

import os, sys
from os.path import join

ROOT = os.path.dirname(os.path.realpath(__file__))
DATA_DIR = join(ROOT, 'dados')

os.environ['MOD_DEV_ENVIRONMENT'] = os.environ.get("MOD_DEV_ENVIRONMENT", '1')
os.environ['MOD_DATA_DIR'] = DATA_DIR
os.environ['MOD_LOG'] = os.environ.get("MOD_LOG", '1')
os.environ['MOD_KEY_PATH'] = join(ROOT, 'keys')
os.environ['MOD_DEVICE_WEBSERVER_PORT'] = os.environ.get("MOD_DEVICE_WEBSERVER_PORT", '8888')
os.environ['MOD_HTML_DIR'] = join(ROOT, 'html')
os.environ['MOD_DEFAULT_PEDALBOARD'] = join(ROOT, 'default.pedalboard')
os.environ['MOD_PHANTOM_BINARY'] = os.environ.get("MOD_PHANTOM_BINARY", '/usr/local/bin/phantomjs')

sys.path = [ os.path.dirname(os.path.realpath(__file__)) ] + sys.path

from mod import webserver

webserver.run()
