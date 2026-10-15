#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
The trademark notice sentence lives in TRADEMARKS.md; the files below carry it verbatim.
If this test fails, TRADEMARKS.md was changed (or one of these files was): update the others.
"""

import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

COPIES = (
    'README.rst',
    'CONTRIBUTING.md',
    'html/img/README-TRADEMARKS.md',
    'html/desktop-tou.html',
)


def read(path):
    with open(os.path.join(ROOT, path), encoding='utf-8') as fh:
        return fh.read()


class TrademarkNoticeTest(unittest.TestCase):
    def canonical(self):
        match = re.search(r'^The MOD logo is a registered trademark \(.*\)\.$', read('TRADEMARKS.md'), re.M)
        self.assertIsNotNone(match, 'TRADEMARKS.md has no notice sentence')
        return match.group(0)

    def test_copies_match_trademarks_md(self):
        sentence = self.canonical()
        for path in COPIES:
            with self.subTest(path=path):
                self.assertIn(sentence, read(path))


if __name__ == '__main__':
    unittest.main()
