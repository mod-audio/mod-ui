#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

import unittest
from uuid import uuid4

from mod.development import FakeHost, FakeHMI
from mod.protocol import Protocol
from mod.session import UserPreferences
from mod.settings import DEFAULT_SNAPSHOT_NAME


def create_host():
    # Avoid to except "Command is already registered"
    Protocol.COMMANDS_USED = []

    callback_hmi = lambda: None
    callback_host = lambda: None

    hmi = FakeHMI(callback_hmi)
    return FakeHost(hmi, UserPreferences(), callback_host)


class HostSnapshotTestCase(unittest.TestCase):
    # OK
    # host.snapshot_name()
    # host.snapshot_rename()
    # host.snapshot_save()
    # host.snapshot_saveas()
    # host.snapshot_remove()
    # host.snapshot_clear()

    # Private methods
    # host._snapshot_unique_name()

    # Doing
    # host.snapshot_make()
    # host.snapshot_load()

    # Consider change them to private method
    # host.load_pb_snapshots()
    # host.save_state_snapshots()
    # host.readdress_snapshots()

    def test_empty_state(self):
        host = create_host()
        self.assertListEqual([], host.pedalboard_snapshots)
        self.assertEqual(-1, host.current_pedalboard_snapshot_id)

        self.assertListEqual([None, None, None], host.hmi_snapshots)

    def test__snapshot_unique_name(self):
        host = create_host()

        name = str(uuid4())
        self.assertEqual(name, host._snapshot_unique_name(name))

        host.pedalboard_snapshots.append({'name': name})
        self.assertEqual(name + " (2)", host._snapshot_unique_name(name))
        host.pedalboard_snapshots.append({'name': name + " (2)"})
        self.assertEqual(name + " (3)", host._snapshot_unique_name(name))

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

    def test_snapshot_save_empty_snapshot_list(self):
        host = create_host()

        # Ensure non empty for improve test quality
        self.assertEqual(0, len(host.pedalboard_snapshots))
        self.assertEqual(-1, host.current_pedalboard_snapshot_id)

        self.assertFalse(host.pedalboard_modified)

        self.assertFalse(host.snapshot_save())
        self.assertFalse(host.pedalboard_modified)

    def test_snapshot_save(self):
        host = create_host()

        # Create at least one snapshot for enable saving
        host.snapshot_saveas("Test")
        host.pedalboard_modified = False

        self.assertTrue(host.snapshot_save())
        self.assertTrue(host.pedalboard_modified)

    def test_snapshot_save_as_empty(self):
        """
        The snapshot creation is based on current pedalboard status.
        So, there isn't any problem if there are any snapshots
        """
        host = create_host()

        self.assertListEqual([], host.pedalboard_snapshots)

        snapshot_1 = str(uuid4())

        self.assertEqual(0, host.snapshot_saveas(snapshot_1))

    def test_snapshot_save_as(self):
        host = create_host()

        snapshot_1 = str(uuid4())
        snapshot_2 = str(uuid4())
        snapshot_3 = str(uuid4())

        self.assertEqual(0, host.snapshot_saveas(snapshot_1))
        self.assertEqual(1, host.snapshot_saveas(snapshot_2))
        self.assertEqual(2, host.snapshot_saveas(snapshot_3))

    def test_snapshot_saveas_duplicated_name(self):
        host = create_host()

        common_name = str(uuid4())

        self.assertEqual(0, host.snapshot_saveas(common_name))
        self.assertEqual(1, host.snapshot_saveas(common_name))
        self.assertEqual(2, host.snapshot_saveas(common_name))

        self.assertEqual(common_name, host.snapshot_name(0))
        self.assertEqual(common_name + " (2)", host.snapshot_name(1))
        self.assertEqual(common_name + " (3)", host.snapshot_name(2))

    def test_snapshot_make_empty_pedalboard(self):
        host = create_host()

        name = str(uuid4())
        snapshot = host.snapshot_make(name)

        self.assertEqual(name, snapshot["name"])
        self.assertTrue("data" in snapshot)

        self.assertDictEqual({}, snapshot['data'])

    def test_snapshot_make(self):
        # FIXME
        pass

    def test_snapshot_load_invalid_index(self):
        host = create_host()

        expected_true = lambda it: self.assertTrue(it)
        expected_false = lambda it: self.assertFalse(it)

        # FIXME
        host.snapshot_load(-1, from_hmi=False, abort_catcher={}, callback=expected_false)
        host.snapshot_load(1000, from_hmi=False, abort_catcher={}, callback=expected_false)

    def test_snapshot_load_idx_in_hmi_snapshot(self):
        host = create_host()
        # TODO

    def test_snapshot_load_abort_catcher_is_true(self):
        host = create_host()
        # TODO

    def test_snapshot_remove_invalid_index(self):
        host = create_host()

        # Ensure non empty for improve test quality
        self.assertEqual(0, host.snapshot_saveas("test"))

        host.pedalboard_modified = False

        self.assertFalse(host.snapshot_remove(-1))
        self.assertFalse(host.pedalboard_modified)
        self.assertFalse(host.snapshot_remove(100))
        self.assertFalse(host.pedalboard_modified)

    def test_snapshot_dont_remove_unique_snapshot(self):
        host = create_host()

        # Ensure non empty for improve test quality
        self.assertEqual(0, host.snapshot_saveas("test"))
        self.assertEqual(1, host.snapshot_saveas("test 2"))

        self.assertEqual(2, len(host.pedalboard_snapshots))

        host.pedalboard_modified = False

        self.assertTrue(host.snapshot_remove(0))
        self.assertTrue(host.pedalboard_modified)

        host.pedalboard_modified = False

        # Assert non delete unique snapshot
        self.assertFalse(host.snapshot_remove(0))
        self.assertFalse(host.pedalboard_modified)

        self.assertEqual(1, len(host.pedalboard_snapshots))

    def test_snapshot_remove_mark_pedalboard_as_modified(self):
        host = create_host()

        # Ensure non empty for improve test quality
        self.assertEqual(0, host.snapshot_saveas("test"))
        self.assertEqual(1, host.snapshot_saveas("test 2"))

        self.assertEqual(2, len(host.pedalboard_snapshots))
        host.pedalboard_modified = False

        self.assertTrue(host.snapshot_remove(0))
        self.assertTrue(host.pedalboard_modified)

    def test_snapshot_clear(self):
        host = create_host()

        # Ensure non empty for improve test quality
        self.assertEqual(0, len(host.pedalboard_snapshots))
        self.assertEqual(-1, host.current_pedalboard_snapshot_id)

        self.assertFalse(host.pedalboard_modified)
        host.snapshot_clear()
        self.assertTrue(host.pedalboard_modified)

        self.assertEqual(1, len(host.pedalboard_snapshots))
        self.assertEqual(0, host.current_pedalboard_snapshot_id)

        self.assertEqual(DEFAULT_SNAPSHOT_NAME, host.snapshot_name(0))
