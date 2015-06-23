
# Copyright 2012-2013 AGR Audio, Industria e Comercio LTDA. <contato@portalmod.com>
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

from datetime import datetime, timedelta
from functools import wraps
from tornado import ioloop
import os, re, json, logging, shutil

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

def _json_or_remove(path):
    try:
        return json.loads(open(path).read())
    except ValueError:
        logging.warning("not JSON, removing: %s", path)
        os.remove(path)
        return None

def check_environment(callback):
    from mod.settings import (HARDWARE_DIR,
                              DEVICE_SERIAL, DEVICE_MODEL,
                              DOWNLOAD_TMP_DIR, BANKS_JSON_FILE, HTML_DIR)
    from mod import indexing
    from mod.session import SESSION

    for dirname in (HARDWARE_DIR, DOWNLOAD_TMP_DIR):
        if not os.path.exists(dirname):
            os.makedirs(dirname)

    if not os.path.exists(BANKS_JSON_FILE):
        fh = open(BANKS_JSON_FILE, 'w')
        fh.write("[]")
        fh.close()

    # TEMPORARIO, APENAS NO DESENVOLVIMENTO
    if os.path.exists(DEVICE_SERIAL) and not os.path.exists(DEVICE_MODEL):
        serial = open(DEVICE_SERIAL).read()
        model = re.search('^[A-Z]+').group()
        open(DEVICE_MODEL, 'w').write(model)

    def ping_callback(ok):
        if ok:
            pass
        else:
            # calls ping again every one second
            ioloop.IOLoop.instance().add_timeout(timedelta(seconds=1), lambda:SESSION.ping(ping_callback))
    SESSION.ping(ping_callback)

# Turn any string into a LV2 compatible symbol
def symbolify(name):
    # TODO
    return name
