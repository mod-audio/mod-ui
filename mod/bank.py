#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

import os
import json
from mod import get_unique_name, safe_json_load, TextFileFlusher
from mod.settings import USER_BANKS_JSON_FILE, FACTORY_BANKS_JSON_FILE, LAST_STATE_JSON_FILE

# return list of banks
def list_banks(brokenpedalbundles = [], userBanks = True, shouldSave = True):
    banks = safe_json_load(USER_BANKS_JSON_FILE if userBanks else FACTORY_BANKS_JSON_FILE, list)

    if len(banks) == 0:
        return []

    changed     = False
    checkbroken = len(brokenpedalbundles) > 0
    ubanknames  = []

    for bank in banks:
        # check for unique names in user banks
        if userBanks:
            ntitle = get_unique_name(bank['title'], ubanknames)
            if ntitle is not None:
                bank['title'] = ntitle
                changed = True
            ubanknames.append(bank['title'])

        # check for valid pedalboards
        validpedals = []

        for pb in bank['pedalboards']:
            if 'bundle' not in pb or not pb['bundle']:
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

    if userBanks and changed and shouldSave:
        save_banks(banks)

    return banks

# save user banks to disk
def save_banks(banks):
    with TextFileFlusher(USER_BANKS_JSON_FILE) as fh:
        json.dump(banks, fh, indent=4)

# save last bank id and pedalboard path to disk
def save_last_bank_and_pedalboard(bank, pedalboard):
    if bank is None:
        return

    try:
        with TextFileFlusher(LAST_STATE_JSON_FILE) as fh:
            json.dump({
                'bank': bank - 2,
                'pedalboard': pedalboard,
                'supportsDividers': True
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

    return (data['bank'] + (2 if data.get('supportsDividers', False) else 1), data['pedalboard'])

# Remove a pedalboard from user banks
def remove_pedalboard_from_banks(pedalboard):
    newbanks = []
    banks = safe_json_load(USER_BANKS_JSON_FILE, list)

    for bank in banks:
        newpedalboards = []

        for oldpedalboard in bank['pedalboards']:
            if os.path.abspath(oldpedalboard['bundle']) != os.path.abspath(pedalboard):
                newpedalboards.append(oldpedalboard)

        if len(newpedalboards) == 0:
            title = bank['title'].encode("ascii", "ignore").decode("ascii")
            print("NOTE: bank with name '%s' does not contain any pedalboards" % title)

        bank['pedalboards'] = newpedalboards
        newbanks.append(bank)

    save_banks(newbanks)
