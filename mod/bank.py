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
from mod.settings import BANKS_JSON_FILE, LAST_STATE_JSON_FILE

def save_banks(banks):
    with open(BANKS_JSON_FILE, 'w') as fh:
        fh.write(json.dumps(banks))

def save_last_bank_and_pedalboard(bank, pedalboard):
    if bank is None:
        return

    with open(LAST_STATE_JSON_FILE, 'w') as fh:
        fh.write(json.dumps({
            'bank': bank,
            'pedalboard': pedalboard
        }))

def get_last_bank_and_pedalboard():
    if not os.path.exists(LAST_STATE_JSON_FILE):
        return (None, None)

    with open(LAST_STATE_JSON_FILE, 'r') as fh:
        state = json.loads(fh.read())

    return (state['bank'], state['pedalboard'])

# Remove from banks, and remove empty banks afterwards
def remove_pedalboard_from_banks(uri):
    newbanks = []

    with open(BANKS_JSON_FILE, 'r') as fh:
        oldbanks = json.loads(fh.read())

    for bank in oldbanks:
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
