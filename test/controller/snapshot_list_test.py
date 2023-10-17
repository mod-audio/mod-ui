#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later
# This test uses coroutine style.
import json
from uuid import uuid4

from tornado.testing import AsyncHTTPTestCase

from mod.settings import DEFAULT_SNAPSHOT_NAME
from mod.webserver import application


class SnapshotListTestCase(AsyncHTTPTestCase):
    def get_app(self):
        return application

    # Pedalboard starts empty, but after there is one, it isn't possible to exclude all of them
    # def test_empty(self):
    #     response = self.fetch("/snapshot/list")
    #
    #     self.assertEqual(response.code, 200)
    #     self.assert_equal([], response.body)

    def test_populated_name(self):
        original_snapshots = json.loads(self.fetch("/snapshot/list").body)

        # Populate
        expected_name_0 = str(uuid4())
        expected_name_1 = str(uuid4())

        self.fetch("/snapshot/saveas?title=" + expected_name_0)
        self.fetch("/snapshot/saveas?title=" + expected_name_1)

        response = self.fetch("/snapshot/list")

        # Assert list
        new_snapshots = self._names(original_snapshots) + [expected_name_0, expected_name_1]
        self.assert_equal(new_snapshots, response.body)

        # Clear created
        for index in reversed(range(len(original_snapshots), len(new_snapshots)+1)):
            self.fetch("/snapshot/remove?id=" + str(index))

    def assert_equal(self, lista, body):
        self.assertDictEqual(
            {str(index): item for index, item in enumerate(lista)},
            json.loads(body)
        )

    def _names(self, snapshots):
        return list(snapshots.values())
