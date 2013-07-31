#!/usr/bin/env python

import os, sys, shutil
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from mod import settings

def clean(path):
    for fname in os.listdir(path):
        fname = os.path.join(path, fname)
        if os.path.isfile(fname):
            os.remove(fname)
        else:
            shutil.rmtree(fname)

clean(settings.PEDALBOARD_DIR)

if os.path.exists(settings.PEDALBOARD_INDEX_PATH):
    shutil.rmtree(settings.PEDALBOARD_INDEX_PATH)

if os.path.exists(settings.BANKS_BINARY_FILE):
    os.remove(settings.BANKS_BINARY_FILE)

if not os.path.exists(settings.PEDALBOARD_BINARY_DIR):
    os.mkdir(settings.PEDALBOARD_BINARY_DIR)

    
