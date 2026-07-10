#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Characterization tests for GET /files/list (mod/webserver.py:FilesList).

These pin the *current* behavior of the pipeline the Tone3000 download
feature will rely on: a fresh os.walk per request, recursion into
subfolders (needed for zip-pack downloads), sort-by-fullname ordering, and
the exact JSON entry shape.
"""

from base import ModUITestCase


class TestFilesList(ModUITestCase):
    __test__ = True

    def test_missing_types_param_is_501(self):
        response = self.fetch("/files/list")
        self.assertEqual(response.code, 501)

    def test_unknown_type_is_empty_ok(self):
        response, body = self.fetch_json("/files/list?types=bogus")
        self.assertEqual(response.code, 200)
        self.assertEqual(body, {"ok": True, "files": []})

    def test_nammodel_missing_folder_is_empty_ok(self):
        # No NAM Models folder exists at all under USER_FILES_DIR.
        response, body = self.fetch_json("/files/list?types=nammodel")
        self.assertEqual(response.code, 200)
        self.assertEqual(body, {"ok": True, "files": []})

    def test_nammodel_lists_nam_files_and_excludes_decoys(self):
        self.seed("NAM Models/amp.nam")
        self.seed("NAM Models/readme.txt")
        self.seed("NAM Models/ir.wav")

        response, body = self.fetch_json("/files/list?types=nammodel")
        self.assertEqual(response.code, 200)
        self.assertTrue(body["ok"])

        basenames = [f["basename"] for f in body["files"]]
        self.assertEqual(basenames, ["amp.nam"])

        entry = body["files"][0]
        self.assertEqual(entry["filetype"], "nammodel")
        self.assertTrue(entry["fullname"].endswith("NAM Models/amp.nam"))
        self.assertTrue(entry["fullname"].startswith("/"), "fullname should be absolute")

    def test_nammodel_extension_match_is_case_insensitive(self):
        self.seed("NAM Models/AMP.NAM")

        response, body = self.fetch_json("/files/list?types=nammodel")
        self.assertEqual(response.code, 200)
        basenames = [f["basename"] for f in body["files"]]
        self.assertEqual(basenames, ["AMP.NAM"])

    def test_nammodel_recurses_into_subfolders(self):
        # Pins DP1: a zip pack unzipped into NAM Models/<packname>/ will list fine.
        self.seed("NAM Models/top.nam")
        self.seed("NAM Models/MyPack/clean.nam")
        self.seed("NAM Models/MyPack/Nested/deep.nam")

        response, body = self.fetch_json("/files/list?types=nammodel")
        self.assertEqual(response.code, 200)
        basenames = sorted(f["basename"] for f in body["files"])
        self.assertEqual(basenames, ["clean.nam", "deep.nam", "top.nam"])

    def test_nammodel_results_sorted_by_full_path(self):
        # Pins DP2's findability baseline: ordering is decided by full path.
        self.seed("NAM Models/zzz.nam")
        self.seed("NAM Models/aaa.nam")
        self.seed("NAM Models/MyPack/mmm.nam")

        response, body = self.fetch_json("/files/list?types=nammodel")
        self.assertEqual(response.code, 200)
        fullnames = [f["fullname"] for f in body["files"]]
        self.assertEqual(fullnames, sorted(fullnames))

    def test_nammodel_walk_is_fresh_every_request(self):
        # Pins that /files/list is NOT cached server-side: a file dropped in
        # between two requests is visible on the second request with no
        # extra signal needed (the staleness the Tone3000 feature must
        # solve is 100% client-side).
        self.seed("NAM Models/first.nam")

        _, body1 = self.fetch_json("/files/list?types=nammodel")
        self.assertEqual([f["basename"] for f in body1["files"]], ["first.nam"])

        self.seed("NAM Models/second.nam")

        _, body2 = self.fetch_json("/files/list?types=nammodel")
        self.assertEqual(
            sorted(f["basename"] for f in body2["files"]),
            ["first.nam", "second.nam"],
        )

    def test_multiple_types_are_unioned_with_own_filetype_tag(self):
        self.seed("NAM Models/amp.nam")
        self.seed("Reverb IRs/hall.wav")

        response, body = self.fetch_json("/files/list?types=nammodel,ir")
        self.assertEqual(response.code, 200)

        by_basename = {f["basename"]: f for f in body["files"]}
        self.assertEqual(set(by_basename), {"amp.nam", "hall.wav"})
        self.assertEqual(by_basename["amp.nam"]["filetype"], "nammodel")
        self.assertEqual(by_basename["hall.wav"]["filetype"], "ir")
