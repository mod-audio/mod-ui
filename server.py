#!/usr/bin/env python3

# FOR DEVELOPMENT PURPOSES ONLY

import os, sys
from datetime import datetime
from os.path import join
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

ROOT = os.path.dirname(os.path.realpath(__file__))
DATA_DIR = join(ROOT, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

os.environ['MOD_DEV_ENVIRONMENT'] = os.environ.get("MOD_DEV_ENVIRONMENT", '1')
os.environ['MOD_DATA_DIR'] = DATA_DIR
os.environ['MOD_LOG'] = os.environ.get("MOD_LOG", '1')
os.environ['MOD_KEY_PATH'] = join(DATA_DIR, 'keys')
os.environ['MOD_DEVICE_WEBSERVER_PORT'] = '8888'
os.environ['MOD_HTML_DIR'] = join(ROOT, 'html')
os.environ['MOD_DEFAULT_PEDALBOARD'] = join(ROOT, 'default.pedalboard')
os.environ['MOD_DEVICE_KEY'] = join(DATA_DIR, 'rsa')
os.environ['MOD_DEVICE_TAG'] = join(DATA_DIR, 'tag')
os.environ['MOD_DEVICE_UID'] = join(DATA_DIR, 'uid')
os.environ['MOD_API_KEY'] = join(DATA_DIR, 'mod_api_key.pub')

create_dummy_credentials()

if not os.path.isfile(os.environ['MOD_API_KEY']):
    print('WARN: Missing file {0} with the public API KEY'.format(os.environ['MOD_API_KEY']))

sys.path = [ os.path.dirname(os.path.realpath(__file__)) ] + sys.path

from mod import webserver

webserver.run()
