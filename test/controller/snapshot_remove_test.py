#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later
# This test uses coroutine style.
import json
from uuid import uuid4

from tornado.httpclient import HTTPRequest
from tornado.testing import AsyncHTTPTestCase

from mod.webserver import application


class SnapshotRemoveTestCase(AsyncHTTPTestCase):

    def get_app(self):
        return application

    def test_remove_non_current_snapshot(self):
        # Create a default snapshot
        name = str(uuid4())
        snapshot_1_index = self._save_as(name)

        # Create a snapshot to be deleted
        name = str(uuid4())
        snapshot_2_index = self._save_as(name)

        # Delete snapshot
        response = self.fetch("/snapshot/remove?id=" + str(snapshot_2_index))
        self.assertEqual(response.code, 200)
        self.assertTrue(json.loads(response.body))

        # Clear
        self.fetch("/snapshot/remove?id=" + str(snapshot_1_index))

    def test_remove_invalid_snapshot(self):
        response = self.fetch("/snapshot/remove?id=" + str(-1))
        self.assertEqual(response.code, 200)
        self.assertFalse(json.loads(response.body))

        response = self.fetch("/snapshot/remove?id=" + str(1000))
        self.assertEqual(response.code, 200)
        self.assertFalse(json.loads(response.body))

    def test_remove_current_snapshot(self):
        """
        It's possible to delete current snapshot
        """
        # Create a default snapshot
        name = str(uuid4())
        snapshot_1_index = self._save_as(name)

        # Create a snapshot to be deleted
        name = str(uuid4())
        snapshot_2_index = self._save_as(name)

        # Load save snapshot to be deleted
        response = self.fetch("/snapshot/load?id=" + str(snapshot_2_index))

        # Assert is loaded
        self.assertEqual(response.code, 200)
        self.assertTrue(json.loads(response.body))

        # Delete loaded snapshot
        response = self.fetch("/snapshot/remove?id=" + str(snapshot_2_index))
        self.assertEqual(response.code, 200)
        self.assertTrue(json.loads(response.body))

        # Clear
        self.fetch("/snapshot/remove?id=" + str(snapshot_1_index))

    def test_remove_all_snapshots(self):
        for i in range(5):
            self._save_as("Snapshot-" + str(i))

        snapshots = json.loads(self.fetch("/snapshot/list").body)

        # Remove all snapshots except the last
        for i in range(len(snapshots) - 1):
            response = self.fetch("/snapshot/remove?id=0")
            self.assertEqual(response.code, 200)
            self.assertTrue(json.loads(response.body))

        # Try to remove the last snapshot without success, as expected
        for i in range(len(snapshots) - 1):
            response = self.fetch("/snapshot/remove?id=0")
            self.assertEqual(response.code, 200)
            self.assertFalse(json.loads(response.body))

    def post(self, url):
        self.http_client.fetch(HTTPRequest(self.get_url(url), "POST", allow_nonstandard_methods=True), self.stop)
        return self.wait()

    def _save_as(self, name):
        response = json.loads(self.fetch("/snapshot/saveas?title=" + name).body)
        return response['id']
