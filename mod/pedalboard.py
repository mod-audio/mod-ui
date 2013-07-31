
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
from mod.settings import (PEDALBOARD_DIR, PEDALBOARD_BINARY_DIR, PEDALBOARD_INDEX_PATH,
                          INDEX_PATH, EFFECT_DIR, BANKS_BINARY_FILE, BANKS_JSON_FILE)

from modcommon import json_handler
from mod import indexing

def save_pedalboard(pedalboard):
    fh = open(os.path.join(PEDALBOARD_DIR, str(pedalboard['_id'])), 'w')
    fh.write(json.dumps(pedalboard, default=json_handler))
    fh.close()
    index = indexing.PedalboardIndex()
    metadata = pedalboard['metadata']
    metadata['_id'] = pedalboard['_id']
    index.add(metadata)
    #generate_pedalboard_binary(str(pedalboard['_id']))

def load_pedalboard(pedalboard_id):
    fh = open(os.path.join(PEDALBOARD_DIR, str(pedalboard_id)))
    j = json.load(fh)
    fh.close()
    return j

def generate_pedalboard_binary(pedalboard_file):
    path = os.path.join(PEDALBOARD_DIR, pedalboard_file)
    bin_path = os.path.join(PEDALBOARD_BINARY_DIR, '%s.bin' % pedalboard_file)
    binary = binary_pedalboard(json.loads(open(path).read()))
    fh = open(bin_path, 'w')
    fh.write(binary)
    fh.close()
    return bin_path

def remove_pedalboard(uid):
    # Delete pedalboard file
    fname = os.path.join(PEDALBOARD_DIR, str(uid))
    if not os.path.exists(fname):
        return False
    os.remove(fname)

    # Delete pedalboard binary
    fname = os.path.join(PEDALBOARD_BINARY_DIR, '%s.bin' % str(uid))
    if os.path.exists(fname):
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
    generate_bank_binary()

def generate_bank_binary():
    fh = open(BANKS_JSON_FILE)
    binary = binary_banks(json.loads(open(BANKS_JSON_FILE).read()))
    fh = open(BANKS_BINARY_FILE, 'w')
    fh.write(binary)
    fh.close()
    return BANKS_BINARY_FILE

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

def encode(string):
    res = []
    for c in string:
        if ord(c) < 128:
            res.append(c)
        else:
            res.append('?')
    return ''.join(res).encode()


def binary_pedalboard(pedalboard):
    binary = []

    binary.append(struct.pack('24s', str(pedalboard['_id'])) + '\x00')
    binary.append(struct.pack('24s', encode(pedalboard['metadata']['title'])) + '\x00')

    binary.append(struct.pack('B', len(pedalboard['effects'])))

    addressings = []

    for effect in pedalboard['effects']:
        binary.append(struct.pack('B', effect['instanceId']))
        binary.append(struct.pack('B', effect['bypass']))

        bpfs = effect.get('bypass_footswitch', None)
        if bpfs is not None:
            bpfs = bpfs.split("_")
            hwid = int(bpfs[1])
            fsid = int(bpfs[3])
            binary.append(struct.pack('B', hwid))
            binary.append(struct.pack('B', fsid))
        else:
            binary.append('\xff\xff')

        # bypass_label
        binary.append(struct.pack('24s', encode(effect['bypass_label'])) + '\x00')

        for parameter in effect['parameters']:
            if parameter['addressing']['actuator'][0] >= 0:
                addressings.append((effect, parameter, parameter['addressing']))

    binary.append(struct.pack('B', len(addressings)))

    for effect, param, addr in addressings:
        ports = get_port_index(effect)
        port = ports[param['symbol']]
        default_steps = 20
        scales = []

        # 0=linear, 1=logarithmic, 2=enumeration, 3=toggled, 4=trigger, 5=tap tempo
        if addr.get('addressing_type') == 'tap_tempo':
            prop = '\x05'
            default_steps = 0
        elif port.get('logarithmic'):
            prop = '\x01'
        elif port.get('toggled'):
            prop = '\x04' if port.get('trigger') else '\x03'
            default_steps = 2
        elif port.get('enumeration'):
            options = addr.get('options', [])
            if len(options) == 0:
                options = get_default_options(port)
            if addr.get('minimum') is None:
                addr['minimum'] = min([ opt[0] for opt in options ])
            if addr.get('maximum') is None:
                addr['maximum'] = max([ opt[0] for opt in options ])
            prop = '\x02'
            for option in options:
                scales.append([ option[1], option[0] ])
            default_steps = len(scales)
        else:
            prop = '\x00'

        bin_addr = []
        bin_addr.append(struct.pack('B', addr['actuator'][0]))
        bin_addr.append(struct.pack('B', addr['actuator'][1]))
        bin_addr.append(struct.pack('B', addr['actuator'][2]))
        bin_addr.append(struct.pack('B', addr['actuator'][3]))
        bin_addr.append(struct.pack('24s', encode(addr['label'])) + '\0')
        bin_addr.append(struct.pack('B', addr.get('steps', default_steps)))
        bin_addr.append(struct.pack('B', effect['instanceId']))
        bin_addr.append(struct.pack('24s', param['symbol'].encode()) + '\0')
        bin_addr.append(struct.pack('f', addr['value']))
        bin_addr.append(struct.pack('f', addr['minimum']))
        bin_addr.append(struct.pack('f', addr['maximum']))
        bin_addr.append(prop)
        bin_addr.append(struct.pack('8s', addr.get('unit', u"none").encode('utf-8')) + "\0") # unit
        bin_addr.append(struct.pack('B', len(scales)))
        for scale in scales:
            bin_addr.append(struct.pack('24s', encode(scale[0])) + '\0')
            bin_addr.append(struct.pack('f', scale[1]))

        binary.append(''.join(bin_addr))


    return ''.join(binary)

def binary_banks(banks):
    binary = [ struct.pack('B', len(banks)) ]
    for bank in banks:
        binary.append(struct.pack('24s', encode(bank.get('title', ''))) + '\x00')
        pedalboards = bank.get('pedalboards', [])
        binary.append(struct.pack('B', len(pedalboards)))
        for pedalboard in pedalboards:
            binary.append(struct.pack('24s', pedalboard['id'].encode()) + '\x00')
            binary.append(struct.pack('24s', pedalboard['title'].encode()) + '\x00')
    return ''.join(binary)


def calculate_binaries_checksum():
    # calculates checksum of all pedalboards and banks, to make sure
    # everything is ok

    banks_bin = open(generate_bank_binary()).read()
    if banks_bin == '\x00': return 'FFFFFFFF'

    crc = crc32(banks_bin)
    banks = json.loads(open(BANKS_JSON_FILE).read())
    for bank in banks:
        for pedalboard in bank['pedalboards']:
            path = os.path.join(PEDALBOARD_BINARY_DIR, '%s.bin' % str(pedalboard['id']))
            if os.path.exists(path):
                crc = crc32(open(path).read(), crc)
            else:
                remove_pedalboard(str(pedalboard['id']))
                calculate_binaries_checksum()

    crc = '%08X' % (crc & 0xffffffff)

    return crc
    
