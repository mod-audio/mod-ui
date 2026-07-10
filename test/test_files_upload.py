#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Tests for POST /files/upload/<filetype> (mod/webserver.py:FilesUpload).

The route is the one server-side piece of the Tone3000 download: a browser
page fetches the model bytes itself and hands them here to be written under
USER_FILES_DIR. Everything it refuses, it refuses with a plain 400 *before*
touching the disk -- these tests pin both the happy path and each refusal.
"""

import json
import os
from urllib.parse import urlencode

from base import ModUITestCase
from conftest import _USER_FILES_DIR


def upload_url(filetype="nammodel", folder="My Tone (12)", name="model.nam"):
    return "/files/upload/%s?%s" % (filetype, urlencode({"folder": folder, "name": name}))


class TestFilesUpload(ModUITestCase):
    __test__ = True

    def upload(self, body=b"nam-bytes", content_type="application/octet-stream", **kwargs):
        headers = {"Content-Type": content_type} if content_type is not None else None
        return self.fetch(upload_url(**kwargs), method="POST", body=body, headers=headers)

    def user_files(self):
        found = []
        for root, _, files in os.walk(str(_USER_FILES_DIR)):
            found.extend(os.path.join(root, f) for f in files)
        return found

    def test_happy_path_writes_and_reports_the_fullname_files_list_shows(self):
        response = self.upload(folder="Clean Amp (7)", name="Clean Amp - Standard.nam")
        self.assertEqual(response.code, 200)

        body = json.loads(response.body.decode("utf-8"))
        self.assertTrue(body["ok"])
        self.assertTrue(body["fullname"].endswith("NAM Models/Clean Amp (7)/Clean Amp - Standard.nam"))

        with open(body["fullname"], "rb") as fh:
            self.assertEqual(fh.read(), b"nam-bytes")

        # The reported fullname is byte-for-byte what /files/list will show,
        # so a caller can find its own upload in the list.
        _, listing = self.fetch_json("/files/list?types=nammodel")
        self.assertEqual([f["fullname"] for f in listing["files"]], [body["fullname"]])

    def test_extension_check_is_case_insensitive_like_files_list(self):
        response = self.upload(name="AMP.NAM")
        self.assertEqual(response.code, 200)

    def test_unknown_filetype_is_400(self):
        self.assertEqual(self.upload(filetype="bogus").code, 400)

    def test_unmapped_filetype_is_400(self):
        # "nam" is a real mod:fileTypes value the NAM plugin declares, but the
        # category map deliberately returns no folder for it -- only "nammodel"
        # (and "aidadspmodel") map to a directory.
        self.assertEqual(self.upload(filetype="nam").code, 400)

    def test_wrong_content_type_is_400(self):
        # Anything except application/octet-stream is refused; among other
        # things this keeps every cross-origin POST behind a CORS preflight
        # that mod-ui never answers.
        self.assertEqual(self.upload(content_type="text/plain").code, 400)
        self.assertEqual(self.upload(content_type="multipart/form-data").code, 400)

    def test_wrong_extension_is_400(self):
        self.assertEqual(self.upload(name="model.wav").code, 400)
        self.assertEqual(self.upload(name="model").code, 400)

    def test_traversal_in_name_or_folder_is_400_and_writes_nothing(self):
        for folder, name in (
            ("..",   "model.nam"),    # parent dir as the folder
            ("a/b",  "model.nam"),    # separator smuggled into folder
            ("pack", "../evil.nam"),  # separator smuggled into name
        ):
            response = self.upload(folder=folder, name=name)
            self.assertEqual(response.code, 400, "folder=%r name=%r" % (folder, name))

        self.assertEqual(self.user_files(), [], "a refused upload must write nothing")

    def test_empty_or_dot_components_are_400(self):
        for folder, name in (("", "model.nam"), (".", "model.nam"),
                             ("pack", ""), ("pack", "."), ("pack", "..")):
            response = self.upload(folder=folder, name=name)
            self.assertEqual(response.code, 400, "folder=%r name=%r" % (folder, name))

        self.assertEqual(self.user_files(), [])
