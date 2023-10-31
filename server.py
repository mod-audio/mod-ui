#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

# FOR DEVELOPMENT PURPOSES ONLY

import os, sys
from datetime import datetime
from random import randint


def create_dummy_credentials():
    if not os.path.isfile(os.environ['MOD_DEVICE_TAG']):
        with open(os.environ['MOD_DEVICE_TAG'], 'w') as fh:
            tag = 'MDS-{0}-0-00-000-{1}'.format(datetime.utcnow().strftime('%Y%m%d'), randint(9000, 9999))
            fh.write(tag)
    if not os.path.isfile(os.environ['MOD_DEVICE_UID']):
        with open(os.environ['MOD_DEVICE_UID'], 'w') as fh:
            uid = ':'.join(['{0}{1}'.format(randint(0, 9), randint(0, 9)) for i in range(0, 16)])
            fh.write(uid)
    if not os.path.isfile(os.environ['MOD_DEVICE_KEY']):
        try:
            from Cryptodome.PublicKey import RSA
            key = RSA.generate(2048)
            with open(os.environ['MOD_DEVICE_KEY'], 'wb') as fh:
                fh.write(key.exportKey('PEM'))
            with open(os.environ['MOD_DEVICE_KEY'] + '.pub', 'wb') as fh:
                fh.write(key.publickey().exportKey('PEM'))
        except Exception as ex:
            print('Can\'t create a device key: {0}'.format(ex))

if os.path.isfile(sys.argv[0]):
    # running through cx-freeze, do an early import of everything we need
    import json
    import uuid
    from tornado import gen, iostream, web, websocket
    ROOT = os.path.dirname(sys.argv[0])
else:
    ROOT = os.path.dirname(os.path.realpath(__file__))
    sys.path = [ os.path.dirname(os.path.realpath(__file__)) ] + sys.path

DATA_DIR = os.environ.get("MOD_DATA_DIR", os.path.join(ROOT, 'data'))

os.makedirs(DATA_DIR, exist_ok=True)

os.environ['MOD_DEV_ENVIRONMENT'] = os.environ.get("MOD_DEV_ENVIRONMENT", '1')
os.environ['MOD_DATA_DIR'] = DATA_DIR
os.environ['MOD_LOG'] = os.environ.get("MOD_LOG", '1')
os.environ['MOD_KEY_PATH'] = os.path.join(DATA_DIR, 'keys')
os.environ['MOD_DEVICE_WEBSERVER_PORT'] = '8888'
os.environ['MOD_HTML_DIR'] = os.path.join(ROOT, 'html')
os.environ['MOD_DEFAULT_PEDALBOARD'] = os.path.join(ROOT, 'default.pedalboard')
os.environ['MOD_DEVICE_KEY'] = os.path.join(DATA_DIR, 'rsa')
os.environ['MOD_DEVICE_TAG'] = os.path.join(DATA_DIR, 'tag')
os.environ['MOD_DEVICE_UID'] = os.path.join(DATA_DIR, 'uid')
os.environ['MOD_API_KEY'] = os.path.join(DATA_DIR, 'mod_api_key.pub')

create_dummy_credentials()

if not os.path.isfile(os.environ['MOD_API_KEY']):
    print('WARN: Missing file {0} with the public API KEY'.format(os.environ['MOD_API_KEY']))

from mod import webserver

webserver.run()
