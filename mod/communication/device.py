import os
from mod import settings


def get_uid():
    return settings.DEVICE_UID


def get_tag():
    return settings.DEVICE_TAG


def get_device_key():
    key = settings.DEVICE_KEY
    if not key:
        raise Exception('Missing device key')
    if os.path.isfile(key):
        with open(key, 'r') as fh:
            return fh.read()
    else:
        return key


def get_server_key():
    key = settings.API_KEY
    if not key:
        raise Exception('Missing API key')
    if os.path.isfile(key):
        with open(key, 'r') as fh:
            return fh.read()
    else:
        return key
