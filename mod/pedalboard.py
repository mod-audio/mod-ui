
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

import os, json, struct
from binascii import crc32
from mod.settings import (PEDALBOARD_DIR, PEDALBOARD_INDEX_PATH,
                          INDEX_PATH, EFFECT_DIR, BANKS_JSON_FILE)

from modcommon import json_handler
from mod import indexing

def save_pedalboard(bank_id, pedalboard):
    fh = open(os.path.join(PEDALBOARD_DIR, str(pedalboard['_id'])), 'w')
    fh.write(json.dumps(pedalboard, default=json_handler))
    fh.close()
    index = indexing.PedalboardIndex()
    metadata = pedalboard['metadata']
    metadata['_id'] = pedalboard['_id']
    index.add(metadata)
    save_last_pedalboard(bank_id, pedalboard['_id'])

def load_pedalboard(pedalboard_id):
    fh = open(os.path.join(PEDALBOARD_DIR, str(pedalboard_id)))
    j = json.load(fh)
    fh.close()
    return j

def save_last_pedalboard(bank_id, pedalboard_id):
    fh = open(os.path.join(PEDALBOARD_DIR, '../last.json'), 'w')
    fh.write(json.dumps({'pedalboard':pedalboard_id, 'bank':bank_id}))
    fh.close()

def get_last_pedalboard():
    try:
        fh = open(os.path.join(PEDALBOARD_DIR, '../last.json'), 'r')
    except IOError:
        pid = None
        bid = None
    else:
        j = json.load(fh)
        fh.close()
        pid = j['pedalboard']
        bid = j['bank']
    return (bid, pid)

def list_pedalboards(bank_id):
    fh = open(BANKS_JSON_FILE, 'r')
    banks = json.load(fh)
    fh.close()
    if bank_id < len(banks):
        return ((pedalboard['title'],pedalboard['id']) for pedalboard in banks[bank_id]['pedalboards'])
    return False

def remove_pedalboard(uid):
    # Delete pedalboard file
    fname = os.path.join(PEDALBOARD_DIR, str(uid))
    if not os.path.exists(fname):
        return False
    os.remove(fname)

    # Remove from index
    index = indexing.PedalboardIndex()
    index.delete(uid)

    # Remove from banks, and remove empty banks afterwards
    banks = json.loads(open(BANKS_JSON_FILE).read())
    newbanks = []
    for bank in banks:
        pedalboards = []
        for pb in bank['pedalboards']:
            if not pb['id'] == uid:
                pedalboards.append(pb)
        if len(pedalboards) == 0:
            continue
        bank['pedalboards'] = pedalboards
        newbanks.append(bank)
    save_banks(newbanks)
    return True

def save_banks(banks):
    fh = open(BANKS_JSON_FILE, 'w')
    fh.write(json.dumps(banks))
    fh.close()

def list_banks():
    fh = open(BANKS_JSON_FILE, 'r')
    banks = json.load(fh)
    fh.close()
    return banks

def get_port_index(effect):
    index = indexing.EffectIndex()
    effect_data = index.find(url=effect['url']).next()
    effect_data = json.loads(open(os.path.join(EFFECT_DIR, effect_data['id'])).read())
    port_index = {}
    for port in effect_data['ports']['control']['input']:
        port_index[port['symbol']] = port
    return port_index

def get_default_options(port):
    options = []
    for option in sorted(port['scalePoints'], key=lambda x: x['value']):
        options.append([ option['value'], option['label'] ])
    return options
