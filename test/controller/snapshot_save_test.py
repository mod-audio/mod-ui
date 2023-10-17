#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later
# This test uses coroutine style.
import json
from uuid import uuid4

from tornado.httpclient import HTTPRequest
from tornado.testing import AsyncHTTPTestCase

from mod.webserver import application


class SnapshotSaveTestCase(AsyncHTTPTestCase):
    def get_app(self):
        return application

    def test_save(self):
        # Create a snapshot
        name = str(uuid4())
        snapshot_index = self._save_as(name)

        # Load and save snapshot created
        self.fetch("/snapshot/load?id=" + str(snapshot_index))
        response = self.post("/snapshot/save")

        # Assert is saved
        self.assertEqual(response.code, 200)
        self.assertTrue(json.loads(response.body))

        # Clear
        self.fetch("/snapshot/remove?id=" + str(snapshot_index))

    def test_save_deleted_snapshot(self):
        # Create two snapshots
        # because it is necessary to exists at least one
        snapshot_1 = str(uuid4())
        snapshot_2 = str(uuid4())

        snapshot_1_index = self._save_as(snapshot_1)
        snapshot_2_index = self._save_as(snapshot_2)

        # Save snapshot created
        self.fetch("/snapshot/load?id=" + str(snapshot_2_index))
        response = self.post("/snapshot/save")

        # Assert is saved
        self.assertEqual(response.code, 200)
        self.assertTrue(json.loads(response.body))

        # Delete created snapshot
        self.fetch("/snapshot/remove?id=" + str(snapshot_2_index))

        # Try to save deleted snapshot
        response = self.post("/snapshot/save")
        self.assertEqual(response.code, 200)
        self.assertFalse(json.loads(response.body))

        # Clear
        self.fetch("/snapshot/remove?id=" + str(snapshot_1_index))

    def post(self, url):
        self.http_client.fetch(HTTPRequest(self.get_url(url), "POST", allow_nonstandard_methods=True), self.stop)
        return self.wait()

    def _save_as(self, name):
        response = json.loads(self.fetch("/snapshot/saveas?title=" + name).body)
        return response['id']
