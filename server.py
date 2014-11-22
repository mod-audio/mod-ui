#!/usr/bin/env python3

# FOR DEVELOPMENT PURPOSES ONLY

import os, sys
from os.path import join

ROOT = "/usr/share/mod-ui/"
DATA_DIR = os.path.expanduser("~/.local/share/mod-data/")

os.environ['MOD_DEV_HOST'] = "0"
os.environ['MOD_DEV_ENVIRONMENT'] = os.environ.get("MOD_DEV_ENVIRONMENT", '1')
os.environ['MOD_DATA_DIR'] = DATA_DIR
os.environ['MOD_LOG'] = "1"
os.environ['MOD_PLUGIN_LIBRARY_DIR'] = join(DATA_DIR, 'lib')
os.environ['MOD_KEY_PATH'] = join(ROOT, 'keys')
os.environ['MOD_HTML_DIR'] = join(ROOT, 'html')
os.environ['MOD_DEVICE_WEBSERVER_PORT'] = '8888'
os.environ['MOD_PHANTOM_BINARY'] = "/usr/bin/phantomjs"
os.environ['MOD_SCREENSHOT_JS'] = join(ROOT, 'screenshot.js')

sys.path = [ ROOT ] + sys.path

from mod import webserver

webserver.run()
