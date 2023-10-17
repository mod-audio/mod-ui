#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later
# This test uses coroutine style.
import json
from uuid import uuid4

from tornado.testing import AsyncHTTPTestCase

from mod.settings import DEFAULT_SNAPSHOT_NAME
from mod.webserver import application


class SnapshotNameTestCase(AsyncHTTPTestCase):
    def get_app(self):
        return application

    def test_name_missing_snapshot(self):
        response = self.fetch("/snapshot/name?id=1000")

        self.assertEqual(response.code, 200)
        self.assert_equal(DEFAULT_SNAPSHOT_NAME, response.body)

    def test_name_negative_snapshot(self):
        response = self.fetch("/snapshot/name?id=-1")

        self.assertEqual(response.code, 200)
        self.assert_equal(DEFAULT_SNAPSHOT_NAME, response.body)

    def test_name(self):
        expected_name_0 = str(uuid4())
        expected_name_1 = str(uuid4())

        self.fetch("/snapshot/saveas?title=" + expected_name_0)
        self.fetch("/snapshot/saveas?title=" + expected_name_1)

        snapshots = self.saved_items()

        response_0 = self.fetch("/snapshot/name?id=" + snapshots[expected_name_0])
        response_1 = self.fetch("/snapshot/name?id=" + snapshots[expected_name_1])

        self.assert_equal(expected_name_0, response_0.body)
        self.assert_equal(expected_name_1, response_1.body)

        for index in reversed(range(len(snapshots), 0)):
            self.fetch("/snapshot/remove?id=" + str(index))

    def assert_equal(self, name, body):
        self.assertDictEqual(
            {
                'ok': True,  # FIXME: Always true
                'name': name
            },
            json.loads(body)
        )

    def saved_items(self):
        items = self.fetch("/snapshot/list")

        return {
            value: key
            for key, value in json.loads(items.body).items()
        }
