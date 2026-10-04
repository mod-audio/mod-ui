#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Characterization tests for the snapshot endpoints (mod/webserver.py:
SnapshotList, SnapshotName, SnapshotSave, SnapshotSaveAs).

Snapshots live entirely on SESSION.host (Python lists/dicts) -- unlike the
pedalboard endpoints in test_pedalboards.py, nothing here calls into lilv,
so there is no segfault risk (confirmed by direct probing).

SESSION.host is a process-global singleton (mod/session.py), and these
handlers mutate it (pedalboard_snapshots, current_pedalboard_snapshot_id).
The autouse `pedalboards_dir` fixture (test/conftest.py) calls
SESSION.reset() before and after every test, so each test method here
starts from a known-fresh state: pedalboard_snapshots == [], and
current_pedalboard_snapshot_id == -1 (mod/host.py Host.__init__ defaults;
SESSION.reset() restores current_pedalboard_snapshot_id to 0 with a single
"Default" snapshot via host.snapshot_clear() -- see the "after /reset"
tests below, which pin that distinction).
"""

import urllib.parse

from base import ModUITestCase


class TestSnapshotFreshSession(ModUITestCase):
    __test__ = True

    def test_list_after_fixture_reset_has_one_default_entry(self):
        # NOT {} -- host.snapshot_clear() (invoked by SESSION.reset(), which
        # the autouse pedalboards_dir fixture runs before every test) seeds
        # exactly one "Default" snapshot at index 0 (host.py:3052-3053).
        # See TestSnapshotSaveWithoutAnyReset below for the true "nothing at
        # all" shape ({}), reached only by clearing the list by hand.
        response, body = self.fetch_json("/snapshot/list")
        self.assertEqual(response.code, 200)
        self.assertEqual(body, {"0": "Default"})

    def test_name_with_default_id_after_reset(self):
        response, body = self.fetch_json("/snapshot/name?id=0")
        self.assertEqual(response.code, 200)
        self.assertEqual(body, {"ok": True, "name": "Default"})

    def test_name_with_out_of_range_id_falls_back_to_default_name(self):
        # snapshot_name(idx) returns None for an out-of-range idx, and the
        # handler falls back to DEFAULT_SNAPSHOT_NAME ("Default") -- so this
        # is NOT a 404/error shape, it's indistinguishable in its "ok": True
        # shape from a real snapshot named "Default".
        response, body = self.fetch_json("/snapshot/name?id=99")
        self.assertEqual(response.code, 200)
        self.assertEqual(body, {"ok": True, "name": "Default"})

    def test_save_after_reset_succeeds_since_reset_seeds_snapshot_0(self):
        # SESSION.reset() leaves current_pedalboard_snapshot_id == 0 with a
        # real snapshot at index 0 (see host.py snapshot_clear()), so
        # SnapshotSave succeeds here -- contrast with
        # TestSnapshotSaveWithoutAnyReset below, which pins the *true*
        # "nothing to save" shape (current_pedalboard_snapshot_id == -1).
        response = self.fetch("/snapshot/save", method="POST", body="")
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body, b"true")

    def test_saveas_creates_new_snapshot_and_appears_in_list(self):
        response, payload = self.fetch_json("/snapshot/saveas?title=Foo")
        self.assertEqual(response.code, 200)
        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["title"], "Foo")
        new_id = payload["id"]

        list_response, list_body = self.fetch_json("/snapshot/list")
        self.assertEqual(list_response.code, 200)
        self.assertEqual(list_body[str(new_id)], "Foo")
        # the pre-existing "Default" snapshot (seeded by SESSION.reset())
        # is still present alongside the new one.
        self.assertIn("0", list_body)


class TestSnapshotSaveWithoutAnyReset(ModUITestCase):
    __test__ = True

    def test_save_returns_false_when_current_snapshot_id_is_negative_one(self):
        # Pins the "truly nothing to save" shape from a session that has
        # never had snapshot_clear() run at all: Host.__init__ (mod/host.py)
        # defaults current_pedalboard_snapshot_id to -1, and snapshot_save()
        # returns False whenever that index is out of range. We reach this
        # state by resetting the underlying attribute directly (the HTTP
        # surface has no route that produces it, since even GET /reset
        # seeds a "Default" snapshot at id 0 -- see module docstring).
        from mod.webserver import SESSION

        SESSION.host.pedalboard_snapshots = []
        SESSION.host.current_pedalboard_snapshot_id = -1

        response = self.fetch("/snapshot/save", method="POST", body="")
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body, b"false")

    def test_list_is_empty_dict_when_snapshots_list_is_empty(self):
        from mod.webserver import SESSION

        SESSION.host.pedalboard_snapshots = []

        response, body = self.fetch_json("/snapshot/list")
        self.assertEqual(response.code, 200)
        self.assertEqual(body, {})


class TestSnapshotRoundTripWithRealPedalboard(ModUITestCase):
    __test__ = True

    def test_saveas_and_list_after_loading_a_real_pedalboard(self):
        # Save a real bundle, load it back (this reseeds
        # pedalboard_snapshots with a single "Default" snapshot via
        # host.load() -> save_state_snapshots()/snapshots.json handling),
        # then exercise snapshot/saveas + snapshot/list against it.
        save_body = urllib.parse.urlencode({"title": "TestBoard", "asNew": "1"})
        _, save_payload = self.fetch_json(
            "/pedalboard/save", method="POST", body=save_body
        )
        bundlepath = save_payload["bundlepath"]

        load_body = urllib.parse.urlencode(
            {"bundlepath": bundlepath, "isDefault": "0"}
        )
        load_response, load_payload = self.fetch_json(
            "/pedalboard/load_bundle/", method="POST", body=load_body
        )
        self.assertEqual(load_response.code, 200)
        self.assertTrue(load_payload["ok"])

        list_response, list_body = self.fetch_json("/snapshot/list")
        self.assertEqual(list_response.code, 200)
        self.assertEqual(list_body, {"0": "Default"})

        saveas_response, saveas_payload = self.fetch_json(
            "/snapshot/saveas?title=Verse"
        )
        self.assertEqual(saveas_response.code, 200)
        self.assertEqual(saveas_payload["ok"], True)
        self.assertEqual(saveas_payload["title"], "Verse")

        list_response2, list_body2 = self.fetch_json("/snapshot/list")
        self.assertEqual(list_body2, {"0": "Default", "1": "Verse"})

        # Order-dependence warning (phase-3 spec): reset SESSION.host before
        # removing the bundle, so later tests see a clean session -- not
        # via a live /pedalboard/list call (segfaults with a real bundle
        # present, see test_pedalboards.py's module docstring), so we go
        # straight to /reset/ then remove.
        reset_response = self.fetch("/reset/")
        self.assertEqual(reset_response.code, 200)

        self.fetch(
            "/pedalboard/remove/?bundlepath="
            + urllib.parse.quote(bundlepath, safe="")
        )
