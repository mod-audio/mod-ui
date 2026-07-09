#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Characterization tests for /tokens/save, /tokens/get, /tokens/delete
(mod/webserver.py:TokensSave/TokensGet/TokensDelete).

These read/write DATA_DIR/tokens.conf directly (not via mod.settings, the
handlers build the path from the DATA_DIR global inline), so this module
snapshots/restores that file around every test to stay order-independent.
"""

import json
import os

import pytest

from base import ModUITestCase


@pytest.fixture(autouse=True)
def _snapshot_tokens_conf():
    from mod import settings

    tokens_conf = os.path.join(settings.DATA_DIR, "tokens.conf")
    existed = os.path.exists(tokens_conf)
    before = None
    if existed:
        with open(tokens_conf, "r") as fh:
            before = fh.read()

    yield

    if existed:
        with open(tokens_conf, "w") as fh:
            fh.write(before)
    elif os.path.exists(tokens_conf):
        os.remove(tokens_conf)


class TestTokensGetMissing(ModUITestCase):
    __test__ = True

    def test_get_with_no_file_returns_ok_false(self):
        response, body = self.fetch_json("/tokens/get")
        self.assertEqual(response.code, 200)
        self.assertEqual(body, {"ok": False})


class TestTokensDeleteMissing(ModUITestCase):
    __test__ = True

    def test_delete_with_no_file_is_a_noop_returning_true(self):
        response = self.fetch("/tokens/delete")
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body, b"true")


class TestTokensRoundTrip(ModUITestCase):
    __test__ = True

    def _payload(self):
        return {
            "user_id": "u1",
            "access_token": "at1",
            "refresh_token": "rt1",
            "expires_in_days": 30,
        }

    def test_save_then_get_returns_saved_payload_minus_expires(self):
        save_response = self.fetch(
            "/tokens/save", method="POST", body=json.dumps(self._payload())
        )
        self.assertEqual(save_response.code, 200)
        self.assertEqual(save_response.body, b"true")

        from mod import settings

        tokens_conf = os.path.join(settings.DATA_DIR, "tokens.conf")
        with open(tokens_conf, "r") as fh:
            on_disk = json.load(fh)
        # TokensSave pops "expires_in_days" before writing to disk.
        self.assertEqual(
            on_disk, {"user_id": "u1", "access_token": "at1", "refresh_token": "rt1"}
        )

        get_response, body = self.fetch_json("/tokens/get")
        self.assertEqual(get_response.code, 200)
        self.assertEqual(
            body,
            {
                "user_id": "u1",
                "access_token": "at1",
                "refresh_token": "rt1",
                "ok": True,
            },
        )

    def test_save_missing_expires_in_days_is_500_and_does_not_write(self):
        # TokensSave unconditionally data.pop("expires_in_days") before
        # writing -- a payload that omits it raises an uncaught KeyError
        # (500), and nothing is written to tokens.conf.
        partial = {"user_id": "u1", "access_token": "at1", "refresh_token": "rt1"}
        response = self.fetch(
            "/tokens/save", method="POST", body=json.dumps(partial)
        )
        self.assertEqual(response.code, 500)

        get_response, body = self.fetch_json("/tokens/get")
        self.assertEqual(get_response.code, 200)
        self.assertEqual(body, {"ok": False})

    def test_get_missing_a_required_key_is_ok_false(self):
        partial = {"user_id": "u1", "access_token": "at1", "expires_in_days": 30}
        save_response = self.fetch(
            "/tokens/save", method="POST", body=json.dumps(partial)
        )
        self.assertEqual(save_response.body, b"true")

        response, body = self.fetch_json("/tokens/get")
        self.assertEqual(response.code, 200)
        self.assertEqual(body["ok"], False)
        self.assertEqual(body["user_id"], "u1")
        self.assertEqual(body["access_token"], "at1")
        self.assertNotIn("refresh_token", body)

    def test_save_then_delete_then_get_is_ok_false_again(self):
        self.fetch("/tokens/save", method="POST", body=json.dumps(self._payload()))

        delete_response = self.fetch("/tokens/delete")
        self.assertEqual(delete_response.code, 200)
        self.assertEqual(delete_response.body, b"true")

        from mod import settings

        tokens_conf = os.path.join(settings.DATA_DIR, "tokens.conf")
        self.assertFalse(os.path.exists(tokens_conf))

        get_response, body = self.fetch_json("/tokens/get")
        self.assertEqual(get_response.code, 200)
        self.assertEqual(body, {"ok": False})
