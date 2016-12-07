
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

from datetime import datetime
from functools import wraps
import os, re, json, shutil

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
        if not result is None:
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(result, default=json_handler))
        else:
            self.set_header('Content-Type', 'text/plain')
            self.set_status(204)
    return wrapper

def json_handler(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    #print(type(obj), obj)
    return None

def check_environment():
    from mod.settings import (LV2_PEDALBOARDS_DIR,
                              DEFAULT_PEDALBOARD, DEFAULT_PEDALBOARD_COPY,
                              DATA_DIR, DOWNLOAD_TMP_DIR, KEYS_PATH,
                              BANKS_JSON_FILE, FAVORITES_JSON_FILE, UPDATE_FILE,
                              CAPTURE_PATH, PLAYBACK_PATH)

    # create temp dirs
    if not os.path.exists(DOWNLOAD_TMP_DIR):
        os.makedirs(DOWNLOAD_TMP_DIR)

    # remove temp files
    for path in (CAPTURE_PATH, PLAYBACK_PATH):
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

    if not os.path.exists(BANKS_JSON_FILE):
        with open(BANKS_JSON_FILE, 'w') as fh:
            fh.write("[]")

    if not os.path.exists(FAVORITES_JSON_FILE):
        with open(FAVORITES_JSON_FILE, 'w') as fh:
            fh.write("[]")

    # remove previous update file
    if os.path.exists(UPDATE_FILE):
        os.remove(UPDATE_FILE)

    return True

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
    name = re.sub("[^_a-zA-Z0-9]+", "_", name)
    if name[0].isdigit():
        name = "_" + name
    return name

def get_hardware_actuators():
    mod_hw = safe_json_load("/etc/mod-hardware-descriptor.json", dict)

    return mod_hw.get('actuators', [])
