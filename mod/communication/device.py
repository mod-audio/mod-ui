import os
from mod import settings


def get_uid():
    uid = settings.DEVICE_UID
    if not uid:
        raise Exception('Missing device uid')
    return uid


def get_tag():
    tag = settings.DEVICE_TAG
    if not tag:
        raise Exception('Missing device tag')
    return tag


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
