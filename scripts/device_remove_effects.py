#!/usr/bin/env python

import os, sys, shutil
from os.path import join
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
DATA_DIR = join(ROOT, 'data')

os.environ['MOD_DEV_ENVIRONMENT'] = os.environ.get("MOD_DEV_ENVIRONMENT", '1')
os.environ['MOD_DATA_DIR'] = DATA_DIR
os.environ['MOD_KEY_PATH'] = join(ROOT, 'keys')
os.environ['MOD_HTML_DIR'] = join(ROOT, 'html')
os.environ['MOD_DEVICE_WEBSERVER_PORT'] = '8888'
os.environ['MOD_PHANTOM_BINARY'] = join(ROOT, 'phantomjs-1.9.0-linux-x86_64/bin/phantomjs')
os.environ['MOD_SCREENSHOT_JS'] = join(ROOT, 'screenshot.js')

from mod import settings

def clean(path):
    for fname in os.listdir(path):
        fname = os.path.join(path, fname)
        if os.path.isfile(fname):
            os.remove(fname)
        else:
            shutil.rmtree(fname)
