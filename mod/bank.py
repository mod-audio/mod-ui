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

import os
import json
import re
from mod import safe_json_load, TextFileFlusher
from mod.settings import BANKS_JSON_FILE, LAST_STATE_JSON_FILE

# return list of banks
def list_banks(brokenpedalbundles = [], shouldSave = True):
    banks = safe_json_load(BANKS_JSON_FILE, list)

    if len(banks) == 0:
        return []

    changed     = False
    checkbroken = len(brokenpedalbundles) > 0
    banknames   = []

    for bank in banks:
        # check for unique names
        title = bank['title']
        if title in banknames:
            match = re.match(r'^.* \(([0-9]*)\)$', title)
            if match is None:
                title += ' (2)'
                if title in banknames:
                    match = re.match(r'^.* \(([0-9]*)\)$', title)
            while match is not None:
                num = int(match.groups()[0])
                title = title[:title.rfind('(')] + '({})'.format(num + 1)
                if title not in banknames:
                    break
                match = re.match(r'^.* \(([0-9]*)\)$', title)
            bank['title'] = title
            changed = True
        banknames.append(title)

        # check for valid pedalboards
        validpedals = []

        for pb in bank['pedalboards']:
            if 'bundle' not in pb.keys() or not pb['bundle']:
                title = pb['title'].encode("ascii", "ignore").decode("ascii")
                print("Auto-removing pedalboard '%s' from bank (missing bundle)" % title)
                changed = True
                continue
            if not os.path.exists(pb['bundle']):
                bundle = pb['bundle'].encode("ascii", "ignore").decode("ascii")
                print("ERROR in banks.py: referenced pedalboard does not exist:", bundle)
                changed = True
                continue
            if checkbroken and os.path.abspath(pb['bundle']) in brokenpedalbundles:
                title = pb['title'].encode("ascii", "ignore").decode("ascii")
                print("Auto-removing pedalboard '%s' from bank (it's broken)" % title)
                changed = True
                continue

            validpedals.append(pb)

        if len(validpedals) == 0:
            title = bank['title'].encode("ascii", "ignore").decode("ascii")
            print("NOTE: bank with name '%s' does not contain any pedalboards" % title)

        bank['pedalboards'] = validpedals

    if changed and shouldSave:
        save_banks(banks)

    return banks

# save banks to disk
def save_banks(banks):
    with TextFileFlusher(BANKS_JSON_FILE) as fh:
        json.dump(banks, fh, indent=4)

# save last bank id and pedalboard path to disk
def save_last_bank_and_pedalboard(bank, pedalboard):
    if bank is None:
        return

    try:
        with TextFileFlusher(LAST_STATE_JSON_FILE) as fh:
            json.dump({
                'bank': bank-1,
                'pedalboard': pedalboard
            }, fh)
    except OSError:
        return

# get last bank id and pedalboard path
def get_last_bank_and_pedalboard():
    data = safe_json_load(LAST_STATE_JSON_FILE, dict)
    keys = data.keys()

    if len(keys) == 0 or "bank" not in keys or "pedalboard" not in keys or not isinstance(data['bank'], int):
        print("last state file does not exist or is corrupt")
        return (-1, None)

    return (data['bank']+1, data['pedalboard'])

# Remove a pedalboard from banks, and banks that are or will become empty
def remove_pedalboard_from_banks(pedalboard):
    newbanks = []
    banks = safe_json_load(BANKS_JSON_FILE, list)

    for bank in banks:
        newpedalboards = []

        for oldpedalboard in bank['pedalboards']:
            if os.path.abspath(oldpedalboard['bundle']) != os.path.abspath(pedalboard):
                newpedalboards.append(oldpedalboard)

        # if there's no pedalboards left ignore this bank (ie, delete it)
        if len(newpedalboards) == 0:
            title = bank['title'].encode("ascii", "ignore").decode("ascii")
            print("NOTE: bank with name '%s' does not contain any pedalboards" % title)

        bank['pedalboards'] = newpedalboards
        newbanks.append(bank)

    save_banks(newbanks)
