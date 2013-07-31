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

clean(settings.PLUGIN_LIBRARY_DIR)
clean(settings.EFFECT_DIR)

if os.path.exists(settings.INDEX_PATH):
    shutil.rmtree(settings.INDEX_PATH)
    
