import os
from mod.settings import API_KEY, DEVICE_KEY, DEVICE_TAG, DEVICE_UID, IMAGE_VERSION, LABS_KEY

def get_uid():
    if DEVICE_UID is None:
        raise Exception('Missing device uid')
    if os.path.isfile(DEVICE_UID):
        with open(DEVICE_UID, 'r') as fh:
            return fh.read().strip()
    return DEVICE_UID

def get_tag():
    if DEVICE_TAG is None:
        raise Exception('Missing device tag')
    if os.path.isfile(DEVICE_TAG):
        with open(DEVICE_TAG, 'r') as fh:
            return fh.read().strip()
    return DEVICE_TAG

def get_device_key():
    if DEVICE_KEY is None:
        raise Exception('Missing device key')
    if os.path.isfile(DEVICE_KEY):
        with open(DEVICE_KEY, 'r') as fh:
            return fh.read().strip()
    return DEVICE_KEY

def get_labs_key():
    if LABS_KEY is None:
        raise Exception('Missing LABS key')
    if os.path.isfile(LABS_KEY):
        with open(LABS_KEY, 'r') as fh:
            return fh.read().strip()
    return LABS_KEY

def get_server_key():
    if API_KEY is None:
        raise Exception('Missing API key')
    if os.path.isfile(API_KEY):
        with open(API_KEY, 'r') as fh:
            return fh.read().strip()
    return API_KEY

def get_image_version():
    if IMAGE_VERSION is not None:
        return IMAGE_VERSION
    return 'none'
