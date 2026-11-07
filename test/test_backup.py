#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Settings -> Backup & Restore: the options passed to mod-backup and its messages.

Run with:  python3 -m unittest discover -s test -p 'test_*.py'
"""

import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from mod.backup import backup_flags, backup_message


class BackupFlagsTest(unittest.TestCase):
    def test_three_values(self):
        self.assertEqual(backup_flags("0,0,0"), [])
        self.assertEqual(backup_flags("1,0,0"), ["-d"])
        self.assertEqual(backup_flags("0,1,0"), ["-p"])
        self.assertEqual(backup_flags("0,0,1"), ["-u"])
        self.assertEqual(backup_flags("1,1,1"), ["-d", "-p", "-u"])

    def test_two_values_from_an_older_page(self):
        self.assertEqual(backup_flags("1,1"), ["-d", "-p"])
        self.assertEqual(backup_flags("0,1"), ["-p"])

    def test_nothing_else_reaches_the_command(self):
        self.assertEqual(backup_flags("yes,-rf,1;reboot"), [])
        self.assertEqual(backup_flags(""), [])


class BackupMessageTest(unittest.TestCase):
    def test_sentence(self):
        self.assertEqual(backup_message(b"no USB stick found\n"), "No USB stick found.")
        self.assertEqual(backup_message(b"Done."), "Done.")
        self.assertEqual(backup_message(b""), "")


if __name__ == '__main__':
    unittest.main()
