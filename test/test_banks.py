#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Characterization tests for /banks/save (BankSave) and /banks/ (BankLoad),
mod/webserver.py.

conftest.py pre-seeds DATA_DIR/banks.json with "[]" (mimicking
check_environment(), which real prepare() calls but this sandbox never
does). Both handlers use mod.settings.USER_BANKS_JSON_FILE, so this module
snapshots/restores that file around every test.
"""

import json
import os

import pytest

from base import ModUITestCase


@pytest.fixture(autouse=True)
def _snapshot_banks_json():
    from mod import settings

    with open(settings.USER_BANKS_JSON_FILE, "r") as fh:
        before = fh.read()

    yield

    with open(settings.USER_BANKS_JSON_FILE, "w") as fh:
        fh.write(before)


class TestBankLoadEmpty(ModUITestCase):
    __test__ = True

    def test_load_with_empty_banks_json_returns_empty_list(self):
        response, body = self.fetch_json("/banks/")
        self.assertEqual(response.code, 200)
        self.assertEqual(body, [])


class TestBankSave(ModUITestCase):
    __test__ = True

    def test_save_writes_banks_json_and_returns_true(self):
        banks = [{"title": "Bank 1", "pedalboards": []}]
        response = self.fetch("/banks/save", method="POST", body=json.dumps(banks))
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body, b"true")

        from mod import settings

        with open(settings.USER_BANKS_JSON_FILE, "r") as fh:
            on_disk = json.load(fh)
        self.assertEqual(on_disk, banks)


class TestBankRoundTripNonexistentPedalboard(ModUITestCase):
    __test__ = True

    def test_save_bank_referencing_missing_pedalboard_is_filtered_on_load(self):
        # DP1/round-trip case from the spec: does BankLoad filter out a
        # pedalboard whose bundle path doesn't exist in the sandboxed temp
        # pedalboards dir (which is always empty here)?
        banks = [
            {
                "title": "Bank 1",
                "pedalboards": [
                    {"bundle": "/nonexistent/thing.pedalboard", "title": "Ghost"}
                ],
            }
        ]
        save_response = self.fetch(
            "/banks/save", method="POST", body=json.dumps(banks)
        )
        self.assertEqual(save_response.body, b"true")

        load_response, body = self.fetch_json("/banks/")
        self.assertEqual(load_response.code, 200)

        # The bank itself survives, but its pedalboards list is filtered
        # empty: list_banks() (mod/bank.py) drops any pedalboard whose
        # 'bundle' path doesn't os.path.exists(), independent of whether it
        # is "broken" -- and the temp pedalboards dir is always empty in
        # this sandbox, so get_all_pedalboards() never repopulates it
        # either.
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["title"], "Bank 1")
        self.assertEqual(body[0]["pedalboards"], [])

        # Observed side effect: list_banks() auto-rewrites banks.json to
        # drop the now-filtered pedalboard entry as a side effect of a GET
        # request (mod/bank.py:58-59, changed=True + shouldSave=True by
        # default). So a plain GET /banks/ is not read-only on disk.
        from mod import settings

        with open(settings.USER_BANKS_JSON_FILE, "r") as fh:
            on_disk = json.load(fh)
        self.assertEqual(on_disk[0]["pedalboards"], [])
