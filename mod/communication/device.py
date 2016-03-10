import os


def get_uid():
    # replace with code that retrieves UID from MOD's i2c chip
    # probably a good idea to cache that value in disk
    return os.environ.get('MOD_UID')


def get_tag():
    # replace with code that retrieves TAG (serial number) from MOD's i2c chip
    # probably a good idea to cache that value in disk
    return os.environ.get('MOD_TAG')


def get_device_key():
    # replace with code that reads the path to device private key
    # the first time it runs it should read it from MOD's i2c chip
    # probably a good idea to cache that value in disk
    return os.environ.get('MOD_DEVICE_KEY')


def get_server_key():
    # replace with code that return the path to server public key
    # that key is written by mod-build-system in the image
    # the path should go to settings if makes sense
    return os.environ.get('MOD_SERVER_KEY')