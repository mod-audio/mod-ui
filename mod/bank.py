# -*- coding: utf-8 -*-

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

import os, json
from mod.settings import BANKS_JSON_FILE

def save_banks(banks):
    with open(BANKS_JSON_FILE, 'w') as fd:
        fd.write(json.dumps(banks))

def save_last_bank_and_pedalboard(bank_id, pedalboard):
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

# Remove from banks, and remove empty banks afterwards
def remove_pedalboard_from_banks(uri):
    with open(BANKS_JSON_FILE, 'r') as fd:
        banks = json.loads(fd.read())
    newbanks = []
    for bank in banks:
        newpedalboards = []
        for pedalboard in bank['pedalboards']:
            if pedalboard['uri'] != uri:
                newpedalboards.append(pedalboard)
        # if there's no pedalboards left ignore this bank (ie, delete it)
        if len(newpedalboards) == 0:
            continue
        bank['pedalboards'] = newpedalboards
        newbanks.append(bank)
    save_banks(newbanks)
