import os
from hashlib import sha1
from mod.settings import KEYS_PATH

LICENSE_INDEX = {}
NEW_LICENSES = []

def check_missing_licenses(licenses):
    # Compute a list of all licenses as revoking candidates
    revoked = set()
    for checksum in os.listdir(KEYS_PATH):
        revoked.add(checksum)

    # Check missing licenses and confirm the ones locally installed
    missing = []
    for plugin_license in licenses:
        uri = plugin_license['plugin_uri'].encode()
        LICENSE_INDEX[plugin_license['id']] = uri
        checksum = sha1(uri).hexdigest()
        if checksum in revoked:
            # license is still valid, let's unmark for revoking
            revoked.remove(checksum)
        key_path = os.path.join(KEYS_PATH, checksum)
        if not os.path.exists(key_path):
            missing.append(plugin_license['id'])

    # Delete revoked licenses
    for checksum in revoked:
        os.remove(os.path.join(KEYS_PATH, checksum))

    return missing

def save_license(lid, data):
    uri = LICENSE_INDEX[lid]
    checksum = sha1(uri).hexdigest()
    key_path = os.path.join(KEYS_PATH, checksum)
    fh = open(key_path, 'wb')
    fh.write(data)
    fh.close()
    NEW_LICENSES.append(uri)

def get_new_licenses_and_flush():
    licenses = []
    while len(NEW_LICENSES) > 0:
        licenses.append(NEW_LICENSES.pop())
    return licenses
