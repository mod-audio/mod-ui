import os
from hashlib import sha1
from mod.settings import KEYS_PATH

LICENSE_INDEX = {}

def check_missing_licenses(licenses):
    missing = []
    for plugin_license in licenses:
        uri = plugin_license['plugin_uri'].encode()
        checksum = sha1(uri).hexdigest()
        LICENSE_INDEX[plugin_license['id']] = checksum
        key_path = os.path.join(KEYS_PATH, checksum)
        if not os.path.exists(key_path):
            missing.append(plugin_license['id'])
    return missing

def save_license(lid, data):
    checksum = LICENSE_INDEX[lid]
    key_path = os.path.join(KEYS_PATH, checksum)
    fh = open(key_path, 'wb')
    fh.write(data)
    fh.close()
