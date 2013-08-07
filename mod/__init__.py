
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

from datetime import timedelta
from tornado import ioloop
import os, re, json, logging

def _json_or_remove(path):
    try:
        serialized = open(path).read()
        json.loads(open(path).read())
    except ValueError:
        logging.warning("not JSON, removing: %s", path)
        os.remove(path)
        return False
    return True

# Check that all objects in index are in filesystem and vice-versa
def ensure_index_sync(index, dirname):
    try:
        for obj in index.every():
            path = os.path.join(dirname, obj['id'])
            assert os.path.exists(path)
            _json_or_remove(path)
        for obj_id in os.listdir(dirname):
            path = os.path.join(dirname, obj_id)
            if os.path.isdir(path):
                continue
            if _json_or_remove(path):
                index.find(id=obj_id).next()
    except:
        # This is usually AssertionError, StopIteration or AttributeError, but let's just capture anything
        index.reindex()

def check_environment(callback):
    from mod.settings import (EFFECT_DIR, PEDALBOARD_DIR, FAVORITES_DIR,
                              HARDWARE_DIR, INDEX_PATH,
                              PEDALBOARD_INDEX_PATH, DEVICE_SERIAL, DEVICE_MODEL,
                              DOWNLOAD_TMP_DIR, PLUGIN_LIBRARY_DIR, BANKS_JSON_FILE)
    from mod import indexing
    from mod.pedalboard import save_pedalboard
    from mod.session import SESSION

    for dirname in (EFFECT_DIR, PEDALBOARD_DIR, FAVORITES_DIR,
                    HARDWARE_DIR, DOWNLOAD_TMP_DIR,
                    PLUGIN_LIBRARY_DIR):
        if not os.path.exists(dirname):
            os.makedirs(dirname)
    
    if not os.path.exists(BANKS_JSON_FILE):
        fh = open(BANKS_JSON_FILE, 'w')
        fh.write("[]")
        fh.close()

    # Index creation will check consistency and rebuild index if necessary
    effect_index = indexing.EffectIndex()
    pedal_index = indexing.PedalboardIndex()

    # TODO check banks.json vs banks.bin
    # TODO check if all pedalboards in banks database really exist, otherwise remove them from banks

    ensure_index_sync(effect_index, EFFECT_DIR)
    ensure_index_sync(pedal_index, PEDALBOARD_DIR)

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
