
# Copyright 2012-2013 AGR Audio, Industria e Comercio LTDA. <contato@moddevices.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import re
import json
import shutil

from datetime import datetime
from functools import wraps
from unicodedata import normalize

from mod.settings import HARDWARE_DESC_FILE


def jsoncall(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        body = self.request.body
        self.request.jsoncall = True
        if body is not None:
            decoded = body.decode()
            if decoded:
                self.request.body = json.loads(decoded)
        result = method(self, *args, **kwargs)
        if result is not None:
            self.set_header('Content-Type', 'application/json; charset=UTF-8')
            self.write(json.dumps(result, default=json_handler))
        else:
            self.set_header('Content-Type', 'text/plain; charset=UTF-8')
            self.set_status(204)
    return wrapper


def json_handler(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    return None


def check_environment():
    from mod.settings import (LV2_PEDALBOARDS_DIR,
                              DEFAULT_PEDALBOARD, DEFAULT_PEDALBOARD_COPY,
                              DATA_DIR, DOWNLOAD_TMP_DIR, PEDALBOARD_TMP_DIR,
                              KEYS_PATH, USER_BANKS_JSON_FILE, FAVORITES_JSON_FILE,
                              UPDATE_CC_FIRMWARE_FILE, UPDATE_MOD_OS_FILE,
                              CAPTURE_PATH, PLAYBACK_PATH)

    # create temp dirs
    if not os.path.exists(DOWNLOAD_TMP_DIR):
        os.makedirs(DOWNLOAD_TMP_DIR)
    if os.path.exists(PEDALBOARD_TMP_DIR):
        shutil.rmtree(PEDALBOARD_TMP_DIR)
    os.makedirs(PEDALBOARD_TMP_DIR)

    # remove temp files
    for path in (CAPTURE_PATH, PLAYBACK_PATH, UPDATE_CC_FIRMWARE_FILE):
        if os.path.exists(path):
            os.remove(path)

    # check RW access
    if os.path.exists(DATA_DIR):
        if not os.access(DATA_DIR, os.W_OK):
            print("ERROR: No write access to data dir '%s'" % DATA_DIR)
            return False
    else:
        try:
            os.makedirs(DATA_DIR)
        except OSError:
            print("ERROR: Cannot create data dir '%s'" % DATA_DIR)
            return False

    # create needed dirs and files
    if not os.path.exists(KEYS_PATH):
        os.makedirs(KEYS_PATH)

    if not os.path.exists(LV2_PEDALBOARDS_DIR):
        os.makedirs(LV2_PEDALBOARDS_DIR)

    if os.path.exists(DEFAULT_PEDALBOARD_COPY) and not os.path.exists(DEFAULT_PEDALBOARD):
        shutil.copytree(DEFAULT_PEDALBOARD_COPY, DEFAULT_PEDALBOARD)

    if not os.path.exists(USER_BANKS_JSON_FILE):
        with open(USER_BANKS_JSON_FILE, 'w') as fh:
            fh.write("[]")

    if not os.path.exists(FAVORITES_JSON_FILE):
        with open(FAVORITES_JSON_FILE, 'w') as fh:
            fh.write("[]")

    # remove previous update file
    if os.path.exists(UPDATE_MOD_OS_FILE) and not os.path.exists("/root/check-upgrade-system"):
        os.remove(UPDATE_MOD_OS_FILE)
        os.sync()

    return True


def get_nearest_valid_scalepoint_value(value, options):
    if not options:
        return value

    # find a value that matches
    for i, (ovalue, _) in enumerate(options):
        if ovalue == value:
            ivalue = i
            return (i, ovalue)

    # find a value within a small range
    for i, (ovalue, _) in enumerate(options):
        if abs(ovalue - value) <= 0.0001:
            ivalue = i
            return (i, ovalue)

    # find closest match
    smallestdiff = None
    smallestpos = 0
    for i, (ovalue, _) in enumerate(options):
        diff = abs(ovalue - value)
        if smallestdiff is None or diff < smallestdiff:
            smallestdiff = diff
            smallestpos = i

    return (smallestpos, options[smallestpos][0])


def get_unique_name(name, names):
    if name not in names:
        return None

    regex = r'^.* \(([0-9]*)\)$'
    match = re.match(regex, name)

    if match is None:
        name += ' (2)'
        if name in names:
            match = re.match(regex, name)

    while match is not None:
        num = int(match.groups()[0])
        name = name[:name.rfind('(')] + '({})'.format(num + 1)
        if name not in names:
            return name
        match = re.match(regex, name)

    return name


def normalize_for_hw(string, limit = 31):
    return '"%s"' % (
        normalize('NFKD',string).encode('ascii','ignore').decode('ascii','ignore').replace('"','')[:limit].upper()
    )


def safe_json_load(path, objtype):
    if not os.path.exists(path):
        return objtype()

    try:
        with open(path, 'r') as fh:
            data = json.load(fh)
    except:
        return objtype()

    if not isinstance(data, objtype):
        return objtype()

    return data


def symbolify(name):
    if len(name) == 0:
        return "_"
    name = normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii', 'ignore')
    name = re.sub("[^_a-zA-Z0-9]+", "_", name)
    if name[0].isdigit():
        name = "_" + name
    return name


def get_hardware_descriptor():
    return safe_json_load(HARDWARE_DESC_FILE, dict)


def get_hardware_actuators():
    return get_hardware_descriptor().get('actuators', [])


def read_file_contents(fh, fallback):
    if fh is None:
        return fallback
    fh.seek(0)
    return fh.read().strip() or fallback


class DummyFile(object):
    def write(self, _):
        return
    def flush(self):
        return
    def close(self):
        return


class TextFileFlusher(object):
    def __init__(self, filename):
        self.filename = filename
        self.filehandle = None

    def __enter__(self):
        try:
            self.filehandle = open(self.filename+".tmp", 'w', 1)
        except OSError:
            print("ERROR: failed to open", self.filename)
            self.filehandle = DummyFile()

        return self.filehandle

    def __exit__(self, typ, val, tb):
        if self.filehandle is None or isinstance(self.filehandle, DummyFile):
            return
        self.filehandle.flush()
        os.fsync(self.filehandle)
        self.filehandle.close()
        os.rename(self.filename+".tmp", self.filename)
