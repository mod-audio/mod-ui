#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

import unittest
from uuid import uuid4

from mod.development import FakeHost, FakeHMI
from mod.protocol import Protocol
from mod.session import UserPreferences, SESSION


def create_host():
    # return SESSION.host

    # Avoid to except "Command is already registered"
    Protocol.COMMANDS_USED = []

    callback_hmi = lambda: None
    callback_host = lambda: None

    hmi = FakeHMI(callback_hmi)
    return FakeHost(hmi, UserPreferences(), callback_host)


class HostSnapshotTestCase(unittest.TestCase):

    def test_empty_state(self):
        host = create_host()
        self.assertListEqual([], host.pedalboard_snapshots)
        self.assertEqual(-1, host.current_pedalboard_snapshot_id)

        self.assertListEqual([None, None, None], host.hmi_snapshots)

    def test_initial_snapshot_name(self):
        host = create_host()

        self.assertEqual(None, host.snapshot_name())

    def test_invalid_index_snapshot_name(self):
        host = create_host()

        self.assertEqual(None, host.snapshot_name(-1))
        self.assertEqual(None, host.snapshot_name(1000))

    def test_snapshot_name(self):
        host = create_host()

        snapshot_0 = str(uuid4())
        snapshot_1 = str(uuid4())

        host.snapshot_saveas(snapshot_0)
        host.snapshot_saveas(snapshot_1)

        self.assertEqual(snapshot_0, host.snapshot_name(0))
        self.assertEqual(snapshot_1, host.snapshot_name(1))

    def test_snapshot_rename_invalid_index(self):
        host = create_host()

        name = "MOD"

        self.assertEqual(False, host.snapshot_rename(-1, name))
        self.assertEqual(False, host.snapshot_rename(1000, name))

        self.assertFalse(host.pedalboard_modified)

    def test_snapshot_rename(self):
        host = create_host()

        name = str(uuid4())
        new_name = str(uuid4())

        self.assertNotEqual(name, new_name)

        # Prepare
        host.snapshot_saveas(name)
        self.assertEqual(name, host.snapshot_name(0))

        host.pedalboard_modified = False

        # Rename
        self.assertTrue(host.snapshot_rename(0, new_name))
        self.assertEqual(new_name, host.snapshot_name(0))
        self.assertTrue(host.pedalboard_modified)

    def test_snapshot_rename_same_name(self):
        host = create_host()

        name = new_name = str(uuid4())
        self.assertEqual(name, new_name)

        # Prepare
        host.snapshot_saveas(name)
        self.assertEqual(name, host.snapshot_name(0))

        host.pedalboard_modified = False

        # Rename
        self.assertTrue(host.snapshot_rename(0, new_name))
        self.assertEqual(new_name, host.snapshot_name(0))
        self.assertFalse(host.pedalboard_modified)

    def test_snapshot_rename_duplicated_name(self):
        host = create_host()

        snapshot_1 = str(uuid4())
        snapshot_2 = str(uuid4())
        snapshot_3 = str(uuid4())

        # Prepare
        host.snapshot_saveas(snapshot_1)
        host.snapshot_saveas(snapshot_2)
        host.snapshot_saveas(snapshot_3)

        # Rename
        self.assertTrue(host.snapshot_rename(0, snapshot_3))
        self.assertTrue(host.snapshot_rename(1, snapshot_3))

        self.assertEqual(snapshot_3 + " (2)", host.snapshot_name(0))
        self.assertEqual(snapshot_3 + " (3)", host.snapshot_name(1))

    def methods_to_test(self):
        host = create_host()

        # OK
        # host.snapshot_name()
        # host.snapshot_rename()

        # TODO
        # host._snapshot_unique_name()
        # host.snapshot_make()
        # host.snapshot_save()
        # host.snapshot_saveas()
        # host.snapshot_remove()
        # host.snapshot_load()
        # host.snapshot_clear()

        # To check if they are on scope
        # host.load_pb_snapshots()
        # host.save_state_snapshots()
        # host.readdress_snapshots()

        # Out of scope
        # host.hmi_list_pedalboard_snapshots()
        # host.hmi_pedalboard_reorder_snapshots()
        # host.hmi_pedalboard_snapshot_save()
        # host.hmi_pedalboard_snapshot_delete()
        # host.hmi_pedalboard_snapshot_load()
        # host.hmi_snapshot_save()
        # host.hmi_snapshot_load()
        # host.hmi_clear_ss_name()
        # host.hmi_report_ss_name_if_current()

