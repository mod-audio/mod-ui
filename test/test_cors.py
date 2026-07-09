#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Characterization tests for CORS headers.

Pins the constraint that shapes the Tone3000 download design: ordinary
JsonRequestHandler routes (e.g. /files/list) send no
Access-Control-Allow-Origin at all, while RemoteRequestHandler subclasses
(e.g. Hello, at /hello) echo it back only for the mod.audio/moddevices.com
allow-list (mod/webserver.py:279-292).
"""

from base import ModUITestCase


class TestFilesListCors(ModUITestCase):
    __test__ = True

    def test_files_list_has_no_cors_header(self):
        response = self.fetch("/files/list?types=bogus")
        self.assertEqual(response.code, 200)
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)


class TestHelloCors(ModUITestCase):
    __test__ = True

    def test_hello_echoes_allowed_origin(self):
        response = self.fetch("/hello", headers={"Origin": "https://mod.audio"})
        self.assertEqual(response.code, 200)
        self.assertEqual(
            response.headers.get("Access-Control-Allow-Origin"),
            "https://mod.audio",
        )

    def test_hello_omits_header_for_foreign_origin(self):
        response = self.fetch("/hello", headers={"Origin": "https://evil.example"})
        self.assertEqual(response.code, 200)
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)
