#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Characterization tests for the small config/user-data POST endpoints:
favorites (mod/webserver.py:FavoritesAdd/FavoritesRemove), /config/set
(SaveSingleConfigValue), /save_user_id/ (SaveUserId) and /auth/nonce
(AuthNonce).

These all mutate either an in-process singleton (gState.favorites) or a
DATA_DIR JSON file (favorites.json, prefs.json, user-id.json). Since
conftest.py's autouse `user_files` fixture only resets USER_FILES_DIR, this
module snapshots/restores gState.favorites and the DATA_DIR files itself so
tests stay order-independent (per characterization-phase-2.md ground rule 5).
"""

import json
import os

import pytest

from base import ModUITestCase


def _read_or_none(path):
    if not os.path.exists(path):
        return None
    with open(path, "r") as fh:
        return fh.read()


def _restore(path, original):
    if original is None:
        if os.path.exists(path):
            os.remove(path)
    else:
        with open(path, "w") as fh:
            fh.write(original)


@pytest.fixture(autouse=True)
def _snapshot_data_dir_state():
    import mod.webserver as webserver
    from mod import settings

    favorites_snapshot = list(webserver.gState.favorites)
    prefs_before = _read_or_none(settings.PREFERENCES_JSON_FILE)
    user_id_before = _read_or_none(settings.USER_ID_JSON_FILE)
    favorites_file_before = _read_or_none(settings.FAVORITES_JSON_FILE)

    yield

    webserver.gState.favorites[:] = favorites_snapshot
    _restore(settings.PREFERENCES_JSON_FILE, prefs_before)
    _restore(settings.USER_ID_JSON_FILE, user_id_before)
    _restore(settings.FAVORITES_JSON_FILE, favorites_file_before)


class TestFavoritesAdd(ModUITestCase):
    __test__ = True

    def test_add_writes_favorites_json_and_returns_true(self):
        response = self.fetch(
            "/favorites/add", method="POST", body="uri=http%3A%2F%2Fexample.org%2Ffx"
        )
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body, b"true")

        from mod import settings

        with open(settings.FAVORITES_JSON_FILE, "r") as fh:
            data = json.load(fh)
        self.assertEqual(data, ["http://example.org/fx"])

    def test_add_duplicate_returns_false_and_does_not_duplicate(self):
        body = "uri=http%3A%2F%2Fexample.org%2Ffx"
        first = self.fetch("/favorites/add", method="POST", body=body)
        self.assertEqual(first.body, b"true")

        second = self.fetch("/favorites/add", method="POST", body=body)
        self.assertEqual(second.code, 200)
        self.assertEqual(second.body, b"false")

        from mod import settings

        with open(settings.FAVORITES_JSON_FILE, "r") as fh:
            data = json.load(fh)
        self.assertEqual(data, ["http://example.org/fx"])

    def test_add_missing_uri_argument_is_400(self):
        response = self.fetch("/favorites/add", method="POST", body="")
        self.assertEqual(response.code, 400)


class TestFavoritesRemove(ModUITestCase):
    __test__ = True

    def test_add_then_remove_empties_favorites_json(self):
        body = "uri=http%3A%2F%2Fexample.org%2Ffx"
        self.fetch("/favorites/add", method="POST", body=body)

        response = self.fetch("/favorites/remove", method="POST", body=body)
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body, b"true")

        from mod import settings

        with open(settings.FAVORITES_JSON_FILE, "r") as fh:
            data = json.load(fh)
        self.assertEqual(data, [])

    def test_remove_unknown_uri_returns_false(self):
        response = self.fetch(
            "/favorites/remove",
            method="POST",
            body="uri=http%3A%2F%2Fnever-added.example%2Ffx",
        )
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body, b"false")


class TestSaveSingleConfigValue(ModUITestCase):
    __test__ = True

    def test_set_writes_prefs_json_and_returns_true(self):
        response = self.fetch(
            "/config/set", method="POST", body="key=some-key&value=some-value"
        )
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body, b"true")

        from mod import settings

        with open(settings.PREFERENCES_JSON_FILE, "r") as fh:
            data = json.load(fh)
        # Values are stored verbatim as whatever get_argument() returned:
        # tornado decodes form params to str, so both key and value land as
        # plain strings in prefs.json (no int/bool coercion happens here).
        self.assertEqual(data["some-key"], "some-value")
        self.assertIsInstance(data["some-key"], str)

    def test_set_missing_key_argument_is_400(self):
        response = self.fetch("/config/set", method="POST", body="value=x")
        self.assertEqual(response.code, 400)


class TestSaveUserId(ModUITestCase):
    __test__ = True

    def test_save_writes_user_id_json_and_returns_true(self):
        response = self.fetch(
            "/save_user_id/",
            method="POST",
            body="name=Ada&email=ada%40example.org",
        )
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body, b"true")

        from mod import settings

        with open(settings.USER_ID_JSON_FILE, "r") as fh:
            data = json.load(fh)
        self.assertEqual(data, {"name": "Ada", "email": "ada@example.org"})

    def test_save_missing_name_argument_is_400(self):
        response = self.fetch(
            "/save_user_id/", method="POST", body="email=ada%40example.org"
        )
        self.assertEqual(response.code, 400)


class TestAuthNonce(ModUITestCase):
    __test__ = True

    def test_auth_nonce_observed_behavior(self):
        # Spec: "if the crypto `token` module is None -> {}; otherwise may
        # error -- OBSERVE and pin actual." In this dev sandbox
        # mod.communication.token imports fine (no exception at import
        # time), so `token` is NOT None; but MOD_DEVICE_KEY / MOD_DEVICE_TAG
        # are unset (conftest.py never sets them), so
        # mod.communication.device.get_tag() raises "Missing device tag"
        # once AuthNonce actually calls token.create_token_message(). That
        # exception is uncaught by the handler, so tornado turns it into a
        # 500.
        response = self.fetch(
            "/auth/nonce", method="POST", body=json.dumps({"nonce": "abc123"})
        )
        self.assertEqual(response.code, 500)
