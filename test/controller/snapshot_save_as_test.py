#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later
# This test uses coroutine style.
import json
from uuid import uuid4

from tornado.httpclient import HTTPRequest
from tornado.testing import AsyncHTTPTestCase

from mod.webserver import application


class SnapshotSaveAsTestCase(AsyncHTTPTestCase):
    def get_app(self):
        return application

    def test_save_as(self):
        # Create a snapshot
        name = str(uuid4())
        snapshot = self._save_as(name)

        # Assert is saved
        self.assertDictEqual(
            {
                "ok": True,
                "id": snapshot['id'],
                "title": name
            },
            snapshot
        )

        # Clear
        self.fetch("/snapshot/remove?id=" + str(snapshot['id']))

    def test_save_as_deleted_snapshot(self):
        """
        It's possible, because the snapshot is created based on pedalboard's
        current state instead of a last snapshot loaded
        """
        # Create two snapshots
        # because it is necessary to exists at least one
        snapshot_1_name = str(uuid4())
        snapshot_2_name = str(uuid4())

        snapshot_1 = self._save_as(snapshot_1_name)
        snapshot_2 = self._save_as(snapshot_2_name)

        # Save snapshot created
        self.fetch("/snapshot/load?id=" + str(snapshot_2['id']))
        response = self.post("/snapshot/save")

        # Assert is saved
        self.assertTrue(json.loads(response.body))

        # Delete created snapshot
        self.fetch("/snapshot/remove?id=" + str(snapshot_2['id']))

        # Save as deleted snapshot
        snapshot_3_name = str(uuid4())
        snapshot_3 = self._save_as(snapshot_3_name)
        self.assertEqual(response.code, 200)
        self.assertDictEqual(
            {
                "ok": True,
                "id": snapshot_3['id'],
                "title": snapshot_3_name
            },
            snapshot_3
        )

        # Clear
        self.fetch("/snapshot/remove?id=" + str(snapshot_3['id']))
        self.fetch("/snapshot/remove?id=" + str(snapshot_1['id']))

    def test_save_duplicated_name(self):
        snapshot_1_name = snapshot_2_name = str(uuid4())

        self.assertEqual(snapshot_1_name, snapshot_2_name)

        snapshot_1 = self._save_as(snapshot_1_name)
        snapshot_2 = self._save_as(snapshot_2_name)

        self.assertNotEqual(snapshot_1['title'], snapshot_2['title'])
        self.assertTrue(snapshot_1['title'] < snapshot_2['title'])

        # Clear
        self.fetch("/snapshot/remove?id=" + str(snapshot_2['id']))
        self.fetch("/snapshot/remove?id=" + str(snapshot_1['id']))

    def post(self, url):
        self.http_client.fetch(HTTPRequest(self.get_url(url), "POST", allow_nonstandard_methods=True), self.stop)
        return self.wait()

    def _save_as(self, name):
        response = self.fetch("/snapshot/saveas?title=" + name)
        self.assertEqual(response.code, 200)

        return json.loads(response.body)
