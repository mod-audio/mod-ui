#!/usr/bin/env python

# FOR DEVELOPMENT PURPOSES ONLY

import os, sys
os.environ['MOD_DEV_ENVIRONMENT'] = os.environ.get("MOD_DEV_ENVIRONMENT", '1')
os.environ['MOD_UNITS_TTL_PATH'] = os.environ.get('MOD_UNITS_TTL_PATH', '/usr/lib/lv2/units.lv2/units.ttl')

sys.path = [ os.path.dirname(os.path.realpath(__file__)) ] + sys.path

from mod import webserver

webserver.run()
