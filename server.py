#!/usr/bin/env python3

# FOR DEVELOPMENT PURPOSES ONLY

import os, sys
from os.path import join

ROOT = os.path.dirname(os.path.realpath(__file__))
DATA_DIR = join(ROOT, 'dados')

os.environ['MOD_DEV_ENVIRONMENT'] = os.environ.get("MOD_DEV_ENVIRONMENT", '1')
os.environ['MOD_DATA_DIR'] = DATA_DIR
os.environ['MOD_LOG'] = "1"
os.environ['MOD_KEY_PATH'] = join(ROOT, 'keys')
os.environ['MOD_DEVICE_WEBSERVER_PORT'] = '8888'

path_phantom = join(ROOT, 'phantomjs-1.9.0-linux-x86_64/bin/phantomjs')
if os.path.exists(path_phantom):
    os.environ['MOD_PHANTOM_BINARY'] = path_phantom

sys.path = [ os.path.dirname(os.path.realpath(__file__)) ] + sys.path

from mod import webserver

webserver.run()
