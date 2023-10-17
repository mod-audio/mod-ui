#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later
# This test uses coroutine style.
import json
from uuid import uuid4

from tornado.httpclient import HTTPRequest
from tornado.testing import AsyncHTTPTestCase

from mod.webserver import application


class SnapshotLoadTestCase(AsyncHTTPTestCase):

    def get_app(self):
        return application

    def test_load_invalid_index(self):
        response = self.fetch("/snapshot/load?id=" + str(-1))
        self.assertEqual(response.code, 200)
        self.assertFalse(json.loads(response.body))

        response = self.fetch("/snapshot/load?id=" + str(1000))
        self.assertEqual(response.code, 200)
        self.assertFalse(json.loads(response.body))

    # TODO Test load valid snapshot
    #      but it is probably better to test host.py directly

    def test_load_invalid_index(self):
        # Create a snapshot
        name = str(uuid4())
        snapshot_index = self._save_as(name)

        response = self.fetch("/snapshot/load?id=" + str(snapshot_index))

        # Assert is loaded
        self.assertEqual(response.code, 200)
        self.assertTrue(json.loads(response.body))

        # Clean
        self.fetch("/snapshot/remove?id=" + str(snapshot_index))

    def _save_as(self, name):
        response = json.loads(self.fetch("/snapshot/saveas?title=" + name).body)
        return response['id']
