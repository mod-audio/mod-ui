# -*- coding: utf-8 -*-

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

import os, json
from mod.settings import BANKS_JSON_FILE

def save_banks(banks):
    fh = open(BANKS_JSON_FILE, 'w')
    fh.write(json.dumps(banks))
    fh.close()

def list_banks():
    try:
        fh = open(BANKS_JSON_FILE, 'r')
    except IOError:
        return []
    banks = json.load(fh)
    fh.close()
    return banks

def save_last_pedalboard(bank_id, pedalboard_number):
    return # TODO
    #if bank_id is not None:
        #fh = open(os.path.join(PEDALBOARD__DIR, '../last.json'), 'w')
        #fh.write(json.dumps({'pedalboard':pedalboard_number, 'bank':bank_id}))
        #fh.close()

def get_last_bank_and_pedalboard():
    return (None, None)

    #try:
        #fh = open(os.path.join(PEDALBOARD__DIR, '../last.json'), 'r')
    #except IOError:
        #return (None, None)

    #j = json.load(fh)
    #fh.close()
    #pid = j['pedalboard']
    #bid = j['bank']
    #try:
        #pid = int(pid)
    #except ValueError: 
        ## This will happen after upgrade, because last.json will have old structure
        #return (None, None)

    #return (bid, pid)

def remove_pedalboard_from_banks(uid):
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
