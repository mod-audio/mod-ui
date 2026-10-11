#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

"""mod.hostinfo: what "Report a problem" says about a computer.

Run with:  python3 -m unittest discover -s test -p 'test_*.py'
"""

import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from mod import hostinfo


class TestCollect(unittest.TestCase):

    def test_answers_without_launcher_log(self):
        info = hostinfo.collect(['/nonexistent-folder'])
        self.assertTrue(info['os'])
        self.assertIsNone(info['launcher'])

    def test_launcher_log_start_and_problems_since_last_start(self):
        with tempfile.TemporaryDirectory() as folder:
            with open(os.path.join(folder, 'launcher.log'), 'w') as fh:
                fh.write("2026-10-11 10:00:00 Starting jackd using: -d portaudio -P OLD\n"
                         "2026-10-11 10:00:01 Pa_OpenStream error = Invalid device\n"
                         "2026-10-11 11:00:00 Starting jackd using: -d portaudio -P /home/me/Spk\n"
                         "2026-10-11 11:00:01 \x1b[31mUnable to load model\x1b[0m\n"
                         "2026-10-11 11:00:02 all fine\n")
            log = hostinfo.launcher_log([folder], '/home/me')
        self.assertEqual(log['jackd'], '-d portaudio -P ~/Spk')
        self.assertEqual(log['problems'], ['2026-10-11 11:00:01 Unable to load model'])


if __name__ == '__main__':
    unittest.main()
