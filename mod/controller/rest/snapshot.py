#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later
from mod.controller.handler.json_request_handler import JsonRequestHandler
from mod.session import SESSION
from mod.settings import DEFAULT_SNAPSHOT_NAME


class SnapshotName(JsonRequestHandler):

    # TODO: Replace GET /snapshot/name
    #            to GET /pedalboards/<pedalboard id>/snapshots/
    def get(self):
        """
        Remove the snapshot name of identifier ``id`` of the loaded pedalboard;
        If is requested by an invalid ``id``, will be returned the default snapshot name.

        .. code-block:: json

            {
                "ok": true,
                "name": "Pedalboard name"
            }

        :return: Snapshot name
        """
        idx = int(self.get_argument('id'))
        name = SESSION.host.snapshot_name(idx) or DEFAULT_SNAPSHOT_NAME
        self.write({
            'ok': bool(name),   # FIXME: Always true
            'name': name
        })


class SnapshotList(JsonRequestHandler):

    # TODO: Replace GET /snapshot/list
    #            to GET /pedalboards/<pedalboard id>/snapshots/
    def get(self):
        """
        Get snapshots name of the loaded pedalboard

        .. code-block:: json

            {
                0: "First snapshot",
                1: "Second snapshot"
            }

        :return: names of the current pedalboard snapshots
        """
        snapshots = SESSION.host.pedalboard_snapshots
        snapshots = dict((i, snapshots[i]['name']) for i in range(len(snapshots)) if snapshots[i] is not None)
        self.write(snapshots)
