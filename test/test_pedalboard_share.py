#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Pedalboard files (.modpedalboard): packing, the checks on an untrusted file, user-file paths.

Run with:  python3 -m unittest discover -s test -p 'test_*.py'
"""

import io
import json
import os
import shutil
import sys
import tarfile
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from mod import pedalboard_share as ps


def make_tar(entries, header=None):
    "entries: list of (name, bytes or None for a dir, type)"
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        if header is not False:
            data = json.dumps(header or {'format': 1, 'title': "T"}).encode()
            info = tarfile.TarInfo(ps.HEADER_NAME)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        for name, data, kind in entries:
            info = tarfile.TarInfo(name)
            if kind == "dir":
                info.type = tarfile.DIRTYPE
                tar.addfile(info)
            elif kind == "symlink":
                info.type = tarfile.SYMTYPE
                info.linkname = "/etc/passwd"
                tar.addfile(info)
            else:
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


class PedalboardShareTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bundle = os.path.join(self.tmp, "src", "My_Board.pedalboard")
        os.makedirs(os.path.join(self.bundle, "effect-1"))
        with open(os.path.join(self.bundle, "manifest.ttl"), "w") as fh:
            fh.write("manifest")
        with open(os.path.join(self.bundle, "My_Board.ttl"), "w") as fh:
            fh.write('<x> <y> "/data/user-files/NAM Models/amp.nam" .\n<a> <b> "/data/user-files/Speaker Cabinets IRs/cab.wav" .\n')
        with open(os.path.join(self.bundle, "effect-1", "state.ttl"), "w") as fh:
            fh.write('<s> <p> "/data/user-files/NAM Models/amp.nam" .\n')
        self.dest = os.path.join(self.tmp, "dest")
        os.makedirs(self.dest)

    def tearDown(self):
        shutil.rmtree(self.tmp, True)

    def test_round_trip(self):
        files = ps.find_user_files(self.bundle, "/data/user-files")
        self.assertEqual(files, ["NAM Models/amp.nam", "Speaker Cabinets IRs/cab.wav"])
        header = ps.make_header("My Board", [{'uri': "urn:x"}], files, "v1.15.0.1", "dwarf")
        data = ps.pack(self.bundle, header)
        got, bundlepath = ps.unpack(data, self.dest)
        self.assertEqual(got['title'], "My Board")
        self.assertEqual(got['files'], files)
        self.assertTrue(os.path.isfile(os.path.join(bundlepath, "effect-1", "state.ttl")))
        self.assertEqual(os.path.basename(bundlepath), "My_Board.pedalboard")

    def test_relocate_user_files(self):
        ps.relocate_user_files(self.bundle, "/data/user-files", "/home/u/MOD Desktop/user-files")
        with open(os.path.join(self.bundle, "effect-1", "state.ttl")) as fh:
            self.assertIn("/home/u/MOD Desktop/user-files" + os.sep + "NAM Models" + os.sep + "amp.nam", fh.read())

    def assertRefused(self, data):
        with self.assertRaises(ps.PedalboardFileError):
            ps.unpack(data, self.dest)
        self.assertEqual(os.listdir(self.dest), [])

    def test_hostile_files(self):
        good = ("B.pedalboard/manifest.ttl", b"m", "file")
        self.assertRefused(b"random bytes")
        self.assertRefused(make_tar([good, ("../evil", b"x", "file")]))
        self.assertRefused(make_tar([good, ("/etc/evil", b"x", "file")]))
        self.assertRefused(make_tar([good, ("B.pedalboard/../../evil", b"x", "file")]))
        self.assertRefused(make_tar([good, ("B.pedalboard/.hidden", b"x", "file")]))
        self.assertRefused(make_tar([good, ("B.pedalboard/link", None, "symlink")]))
        self.assertRefused(make_tar([good, ("C.pedalboard/manifest.ttl", b"m", "file")]))
        self.assertRefused(make_tar([("B.pedalboard/x.ttl", b"m", "file")]))       # no manifest
        self.assertRefused(make_tar([good], header=False))                          # no header
        self.assertRefused(make_tar([good], header={'format': 2, 'title': "T"}))   # newer format
        self.assertRefused(make_tar([("notabundle/manifest.ttl", b"m", "file")]))

    def test_directories_are_fine(self):
        data = make_tar([("B.pedalboard/", None, "dir"), ("B.pedalboard/manifest.ttl", b"m", "file")])
        header, bundlepath = ps.unpack(data, self.dest)
        self.assertEqual(header['title'], "T")
        self.assertEqual(header['plugins'], [])


if __name__ == '__main__':
    unittest.main()
