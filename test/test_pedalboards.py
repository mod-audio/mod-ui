#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Characterization tests for the pedalboard lifecycle: list, save, info,
remove, load_bundle (mod/webserver.py: PedalboardList, PedalboardSave,
PedalboardInfo, PedalboardRemove, PedalboardLoadBundle).

CRITICAL, spec-overriding finding (see docs/characterization-phase-3.md,
which claimed /pedalboard/list and /banks/ are "self-contained lilv calls"
and safe): **GET /pedalboard/list and GET /banks/ SEGFAULT the whole test
process the moment the sandboxed pedalboards dir contains a real, on-disk
pedalboard bundle** (one written by POST /pedalboard/save). Root cause,
confirmed with faulthandler/gdb: modtools.utils.get_all_pedalboards()
(mod/webserver.py:1316 for PedalboardList, :1685 for BankLoad) invalidates
its Python-side cache and calls into utils.get_all_pedalboards() (the
libmod_utils.so C extension), which crashes inside
``NamespaceDefinitions::init(LilvWorldImpl*)`` -> ``lilv_new_uri()`` while
building its lilv world over a *real* bundle -- reproduced identically via
both PedalboardList and BankLoad, deterministically, every time, and
independent of how many times /pedalboard/list was called before (repeated
calls against an *empty* dir never crash; a *single* call against a dir
containing one real saved bundle crashes every time). By contrast,
GET /pedalboard/info/ (single-bundle parse via get_pedalboard_info(), a
different C entry point) and GET /pedalboard/remove/ are safe with a real
bundle present -- confirmed by direct probing with faulthandler enabled.

Consequence for this suite: no test here calls GET /pedalboard/list or
GET /banks/ while a real bundle exists in the sandboxed pedalboards dir.
The "list now includes TestBoard" step from the phase-3 spec's core
round-trip is NOT executed as a live HTTP call; the bundle's presence is
instead verified directly on disk (os.path), which is what a real GET
/pedalboard/list would enumerate. The bundle is always removed via
GET /pedalboard/remove/ before any subsequent GET /pedalboard/list call in
the same test.

The autouse `pedalboards_dir` fixture (test/conftest.py) wipes
LV2_PEDALBOARDS_DIR and resets SESSION around every test, so tests are
order-independent regarding on-disk bundles and SESSION.host state.
"""

import os
import urllib.parse

from base import ModUITestCase


def _quote(bundlepath):
    return urllib.parse.quote(bundlepath, safe="")


class TestPedalboardListBaseline(ModUITestCase):
    __test__ = True

    def test_list_on_empty_sandbox_is_empty_list(self):
        # Safe: the sandboxed pedalboards dir is always empty here (no save
        # has happened yet in this test).
        response, body = self.fetch_json("/pedalboard/list")
        self.assertEqual(response.code, 200)
        self.assertEqual(body, [])


class TestPedalboardSave(ModUITestCase):
    __test__ = True

    def test_save_missing_title_is_400(self):
        response = self.fetch("/pedalboard/save", method="POST", body="asNew=1")
        self.assertEqual(response.code, 400)

    def test_save_missing_asnew_is_400(self):
        response = self.fetch("/pedalboard/save", method="POST", body="title=X")
        self.assertEqual(response.code, 400)

    def test_save_creates_bundle_on_disk_with_expected_json_shape(self):
        import mod.settings as settings

        body = urllib.parse.urlencode({"title": "TestBoard", "asNew": "1"})
        response, payload = self.fetch_json(
            "/pedalboard/save", method="POST", body=body
        )
        self.assertEqual(response.code, 200)
        self.assertEqual(
            payload, {"ok": True, "bundlepath": payload["bundlepath"], "title": "TestBoard"}
        )

        bundlepath = payload["bundlepath"]
        self.assertTrue(bundlepath.startswith(settings.LV2_PEDALBOARDS_DIR))
        self.assertTrue(bundlepath.endswith(".pedalboard"))
        self.assertTrue(os.path.isdir(bundlepath))

        # A .ttl bundle got written (host.save_state_to_ttl), NOT observed
        # through /pedalboard/list (see module docstring -- that would
        # segfault) but directly on disk, which is exactly what a real
        # /pedalboard/list GET would enumerate.
        entries = os.listdir(bundlepath)
        self.assertTrue(any(name.endswith(".ttl") for name in entries))
        self.assertIn("manifest.ttl", entries)

        # cleanup: remove before this test method returns, so no real
        # bundle is left for the next test even though the autouse fixture
        # would also wipe it.
        remove_response = self.fetch(
            "/pedalboard/remove/?bundlepath=" + _quote(bundlepath)
        )
        self.assertEqual(remove_response.body, b"true")

    def test_save_asnew_0_over_fresh_session_behaves_like_asnew_1(self):
        # No pedalboard was ever loaded/saved in this session yet, so
        # host.pedalboard_path is "" -- host.save()'s "save over existing"
        # branch requires a truthy, on-disk, sandbox-rooted pedalboard_path,
        # so asNew=0 here takes the same "save new" branch as asNew=1.
        body = urllib.parse.urlencode({"title": "FreshBoard", "asNew": "0"})
        response, payload = self.fetch_json(
            "/pedalboard/save", method="POST", body=body
        )
        self.assertEqual(response.code, 200)
        self.assertTrue(payload["ok"])
        self.assertTrue(os.path.isdir(payload["bundlepath"]))

        self.fetch("/pedalboard/remove/?bundlepath=" + _quote(payload["bundlepath"]))

    def test_save_asnew_0_after_asnew_1_overwrites_same_bundle(self):
        body1 = urllib.parse.urlencode({"title": "TestBoard", "asNew": "1"})
        _, payload1 = self.fetch_json("/pedalboard/save", method="POST", body=body1)
        bundlepath1 = payload1["bundlepath"]

        body2 = urllib.parse.urlencode({"title": "TestBoard", "asNew": "0"})
        _, payload2 = self.fetch_json("/pedalboard/save", method="POST", body=body2)
        bundlepath2 = payload2["bundlepath"]

        self.assertEqual(bundlepath1, bundlepath2)

        import mod.settings as settings

        self.assertEqual(os.listdir(settings.LV2_PEDALBOARDS_DIR), [os.path.basename(bundlepath1)])

        self.fetch("/pedalboard/remove/?bundlepath=" + _quote(bundlepath1))


class TestPedalboardInfo(ModUITestCase):
    __test__ = True

    def test_info_on_bogus_bundlepath_is_500(self):
        # get_pedalboard_info() raises a bare Exception on failure
        # (modtools/utils.py); PedalboardInfo.get() does not catch it, so it
        # surfaces as tornado's generic uncaught-exception 500 HTML page --
        # NOT a JsonRequestHandler JSON error body.
        response = self.fetch(
            "/pedalboard/info/?bundlepath=" + _quote("/nonexistent/thing.pedalboard")
        )
        self.assertEqual(response.code, 500)
        self.assertIn("text/html", response.headers.get("Content-Type", ""))

    def test_info_on_real_bundle_matches_saved_title(self):
        save_body = urllib.parse.urlencode({"title": "TestBoard", "asNew": "1"})
        _, save_payload = self.fetch_json(
            "/pedalboard/save", method="POST", body=save_body
        )
        bundlepath = save_payload["bundlepath"]

        response, info = self.fetch_json(
            "/pedalboard/info/?bundlepath=" + _quote(bundlepath)
        )
        self.assertEqual(response.code, 200)
        self.assertEqual(info["title"], "TestBoard")
        self.assertIn("plugins", info)
        self.assertIn("width", info)
        self.assertIn("height", info)

        self.fetch("/pedalboard/remove/?bundlepath=" + _quote(bundlepath))


class TestPedalboardRemove(ModUITestCase):
    __test__ = True

    def test_remove_bogus_bundlepath_returns_false(self):
        response = self.fetch(
            "/pedalboard/remove/?bundlepath=" + _quote("/nonexistent/thing.pedalboard")
        )
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body, b"false")

    def test_remove_nonexistent_path_outside_sandbox_returns_false_and_touches_nothing(self):
        # PedalboardRemove gates on os.path.exists(bundlepath) before ever
        # calling shutil.rmtree -- a nonexistent path outside the sandbox is
        # therefore a safe no-op observation, not a real escape attempt.
        outside_path = "/tmp/modui-characterization-does-not-exist.pedalboard"
        self.assertFalse(os.path.exists(outside_path))

        response = self.fetch("/pedalboard/remove/?bundlepath=" + _quote(outside_path))
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body, b"false")


class TestPedalboardCoreRoundTrip(ModUITestCase):
    __test__ = True

    def test_save_info_remove_round_trip(self):
        """The highest-value test (spec's "core round-trip"), adapted for
        the /pedalboard/list segfault documented in the module docstring:
        the bundle's presence/absence is asserted via the filesystem and
        via /pedalboard/info/, never via a live /pedalboard/list call while
        the bundle exists.
        """
        import mod.settings as settings

        # 1. Baseline: safe, dir is empty (autouse fixture guarantees this).
        response, body = self.fetch_json("/pedalboard/list")
        self.assertEqual(body, [])

        # 2. Save.
        save_body = urllib.parse.urlencode({"title": "TestBoard", "asNew": "1"})
        save_response, save_payload = self.fetch_json(
            "/pedalboard/save", method="POST", body=save_body
        )
        self.assertEqual(save_response.code, 200)
        self.assertTrue(save_payload["ok"])
        bundlepath = save_payload["bundlepath"]
        self.assertEqual(save_payload["title"], "TestBoard")

        # 3. "List now includes TestBoard" -- verified on disk (this is
        # exactly what get_all_pedalboards() would scan), NOT via a live
        # GET /pedalboard/list call, which segfaults with a real bundle
        # present (see module docstring).
        self.assertTrue(os.path.isdir(bundlepath))
        self.assertEqual(
            os.listdir(settings.LV2_PEDALBOARDS_DIR),
            [os.path.basename(bundlepath)],
        )

        # 4. Info.
        info_response, info = self.fetch_json(
            "/pedalboard/info/?bundlepath=" + _quote(bundlepath)
        )
        self.assertEqual(info_response.code, 200)
        self.assertEqual(info["title"], "TestBoard")

        # 5. Remove.
        remove_response = self.fetch(
            "/pedalboard/remove/?bundlepath=" + _quote(bundlepath)
        )
        self.assertEqual(remove_response.code, 200)
        self.assertEqual(remove_response.body, b"true")
        self.assertFalse(os.path.exists(bundlepath))

        # Now the dir is empty again, so a live /pedalboard/list call is
        # safe once more (see module docstring: only a NON-empty dir
        # segfaults) and should be back to baseline.
        final_response, final_body = self.fetch_json("/pedalboard/list")
        self.assertEqual(final_response.code, 200)
        self.assertEqual(final_body, [])


class TestPedalboardLoadBundle(ModUITestCase):
    __test__ = True

    def test_load_bundle_on_bogus_bundlepath_returns_ok_false(self):
        body = urllib.parse.urlencode(
            {"bundlepath": "/nonexistent/thing.pedalboard", "isDefault": "0"}
        )
        response, payload = self.fetch_json(
            "/pedalboard/load_bundle/", method="POST", body=body
        )
        self.assertEqual(response.code, 200)
        self.assertEqual(payload, {"ok": False, "name": ""})

    def test_load_bundle_on_real_saved_bundle_returns_ok_true_with_name(self):
        save_body = urllib.parse.urlencode({"title": "TestBoard", "asNew": "1"})
        _, save_payload = self.fetch_json(
            "/pedalboard/save", method="POST", body=save_body
        )
        bundlepath = save_payload["bundlepath"]

        load_body = urllib.parse.urlencode(
            {"bundlepath": bundlepath, "isDefault": "0"}
        )
        response, payload = self.fetch_json(
            "/pedalboard/load_bundle/", method="POST", body=load_body
        )
        self.assertEqual(response.code, 200)
        self.assertEqual(payload, {"ok": True, "name": "TestBoard"})

        # Reset SESSION before cleanup, per phase-3 spec's order-dependence
        # warning: SESSION.host is a process-global singleton, so a test
        # that loads a pedalboard must reset afterwards.
        reset_response = self.fetch("/reset/")
        self.assertEqual(reset_response.code, 200)

        self.fetch("/pedalboard/remove/?bundlepath=" + _quote(bundlepath))
