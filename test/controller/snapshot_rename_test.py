#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later
# This test uses coroutine style.
import json
from uuid import uuid4

from tornado.testing import AsyncHTTPTestCase

from mod.webserver import application


class SnapshotRenameTestCase(AsyncHTTPTestCase):
    def get_app(self):
        return application

    def test_rename_unique_name(self):
        original_name = str(uuid4())
        new_name = str(uuid4())

        other = str(uuid4())

        self.assertNotEqual(original_name, new_name)

        snapshot_1_index = self._save_as(original_name)
        snapshot_2_index = self._save_as(other)

        # Assert rename works
        snapshot = self._rename(snapshot_1_index, new_name)
        self.assertDictEqual(
            {
                'ok': True,
                'title': new_name
            },
            snapshot
        )

        # Assert rename doesn't change snapshot's order
        snapshot = self.fetch("/snapshot/name?id=" + str(snapshot_1_index))
        self.assertEqual(new_name, json.loads(snapshot.body)['name'])

        self.fetch("/snapshot/remove?id=" + str(snapshot_2_index))
        self.fetch("/snapshot/remove?id=" + str(snapshot_1_index))

    def test_rename_to_the_same_name(self):
        name = str(uuid4())

        self.assertEqual(name, name)

        snapshot_index = self._save_as(name)

        # Assert rename
        snapshot = self._rename(snapshot_index, name)
        self.assertDictEqual(
            {
                'ok': True,
                'title': name
            },
            snapshot
        )

        self.fetch("/snapshot/remove?id=" + str(snapshot_index))

    def test_rename_invalid_snapshot(self):
        name = str(uuid4())

        snapshot = self._rename(-1, name)
        self.assertDictEqual(
            {'ok': False, 'title': name},
            snapshot
        )

        snapshot = self._rename(1000, name)
        self.assertDictEqual(
            {'ok': False, 'title': name},
            snapshot
        )

    def test_rename_duplicated_name(self):
        snapshot_sample_1 = str(uuid4())
        snapshot_sample_2 = str(uuid4())
        snapshot_sample_3 = str(uuid4())

        snapshot_1_index = self._save_as(snapshot_sample_1)
        snapshot_2_index = self._save_as(snapshot_sample_2)
        snapshot_3_index = self._save_as(snapshot_sample_3)

        snapshot = self._rename(snapshot_1_index, snapshot_sample_3)
        self.assertDictEqual(
            {
                'ok': True,
                'title': snapshot_sample_3 + " (2)"
            },
            snapshot
        )

        snapshot = self._rename(snapshot_2_index, snapshot_sample_3)
        self.assertDictEqual(
            {
                'ok': True,
                'title': snapshot_sample_3 + " (3)"
            },
            snapshot
        )

        self.fetch("/snapshot/remove?id=" + str(snapshot_3_index))
        self.fetch("/snapshot/remove?id=" + str(snapshot_2_index))
        self.fetch("/snapshot/remove?id=" + str(snapshot_1_index))

    def _rename(self, index, name):
        response = self.fetch("/snapshot/rename?id=" + str(index) + "&title=" + name)
        self.assertEqual(response.code, 200)
        return json.loads(response.body)

    def _save_as(self, name):
        response = json.loads(self.fetch("/snapshot/saveas?title=" + name).body)
        return response['id']
