#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

import unittest

from mod.development import FakeHost, FakeHMI
from mod.protocol import Protocol
from mod.session import UserPreferences


def create_host():
    # return SESSION.host

    # Avoid to except "Command is already registered"
    Protocol.COMMANDS_USED = []

    callback_hmi = lambda: None
    callback_host = lambda: None

    hmi = FakeHMI(callback_hmi)
    return FakeHost(hmi, UserPreferences(), callback_host)


class HostHmiSnapshotTestCase(unittest.TestCase):

    def test(self):
        # TODO
        # host.hmi_list_pedalboard_snapshots()
        # host.hmi_pedalboard_reorder_snapshots()
        # host.hmi_pedalboard_snapshot_save()
        # host.hmi_pedalboard_snapshot_delete()
        # host.hmi_pedalboard_snapshot_load()
        # host.hmi_snapshot_save()
        # host.hmi_snapshot_load()
        # host.hmi_clear_ss_name()
        # host.hmi_report_ss_name_if_current()
        pass

