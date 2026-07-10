#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Characterization tests for /system/info (SystemInfo), /system/prefs
(SystemPreferences), /hello/ (Hello) and /ping/ (Ping), mod/webserver.py.

None of these write anything -- they only read read-only system paths
(/etc/mod-release/system, /data/*) that don't exist on a plain dev machine,
so no snapshot/restore fixture is needed here.
"""

from base import ModUITestCase


class TestSystemInfo(ModUITestCase):
    __test__ = True

    def test_info_defaults_when_no_hardware_descriptor(self):
        response, body = self.fetch_json("/system/info")
        self.assertEqual(response.code, 200)

        # /etc/mod-hardware-descriptor.json and /etc/mod-release/system
        # don't exist on this dev machine, so every hwdesc-derived field
        # falls back to "Unknown" and sysdate falls back to "Unknown".
        self.assertEqual(body["hwname"], "Unknown")
        self.assertEqual(body["architecture"], "Unknown")
        self.assertEqual(body["cpu"], "Unknown")
        self.assertEqual(body["platform"], "Unknown")
        self.assertEqual(body["bin_compat"], "Unknown")
        self.assertEqual(body["model"], "Unknown")
        self.assertEqual(body["sysdate"], "Unknown")

        self.assertIn("version", body["python"])
        self.assertIn("machine", body["uname"])
        self.assertIn("release", body["uname"])
        self.assertIn("sysname", body["uname"])
        self.assertIn("version", body["uname"])


class TestSystemPreferences(ModUITestCase):
    __test__ = True

    def test_prefs_defaults_when_no_data_files(self):
        response, body = self.fetch_json("/system/prefs")
        self.assertEqual(response.code, 200)

        # SystemPreferences reads hardcoded absolute "/data/..." paths (NOT
        # mod.settings.DATA_DIR -- these are never sandboxed by conftest.py,
        # but /data doesn't exist on this dev machine so every pref falls
        # back to its default).
        self.assertEqual(body["jack_buffer_size"], 128)
        self.assertEqual(body["jack_mono_copy"], False)
        self.assertEqual(body["jack_sync_mode"], False)
        self.assertEqual(body["separate_spdif_outs"], False)
        # "service_mod_peakmeter" is an OPTION_FILE_NOT_EXISTS pref, so it's
        # True exactly when the disable-flag file is absent.
        self.assertEqual(body["service_mod_peakmeter"], True)
        self.assertEqual(body["service_mod_sdk"], False)
        self.assertEqual(body["service_netmanager"], False)
        self.assertEqual(body["autorestart_hmi"], False)
        # bluetooth_name has no valdef override (defaults to None), so the
        # key is present with a JSON null, not omitted.
        self.assertIn("bluetooth_name", body)
        self.assertIsNone(body["bluetooth_name"])


class TestHello(ModUITestCase):
    __test__ = True

    def test_hello_shape(self):
        response, body = self.fetch_json("/hello/")
        self.assertEqual(response.code, 200)
        # No websocket ever connects in this test harness.
        self.assertEqual(body["online"], False)
        # IMAGE_VERSION is None in this dev sandbox (no /etc/mod-release/system).
        self.assertIsNone(body["version"])


class TestPing(ModUITestCase):
    __test__ = True

    def test_ping_reports_hmi_offline(self):
        response, body = self.fetch_json("/ping/")
        self.assertEqual(response.code, 200)
        # The fake HMI (mod.development.FakeHMI under MOD_DEV_ENVIRONMENT=1)
        # is never .initialized, so web_ping() calls back False synchronously
        # -- no 5s gen.with_timeout wait is actually exercised here.
        self.assertEqual(body["ihm_online"], False)
        self.assertEqual(body["ihm_time"], 0)
