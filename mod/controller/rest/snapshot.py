#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later
from tornado import gen, web

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


class SnapshotSave(JsonRequestHandler):

    # TODO: Replace POST /snapshot/save
    #            to POST /pedalboards/current/snapshots/current
    def post(self):
        """
        Update the current snapshot status

        :return: `true` if it was successfully updated
        """
        ok = SESSION.host.snapshot_save()
        self.write(ok)


class SnapshotSaveAs(JsonRequestHandler):

    # TODO: Replace GET /snapshot/saveas
    #            to POST /pedalboards/current/snapshots/saveas
    @web.asynchronous
    @gen.engine
    def get(self):
        """
        Create a new snapshot with the suggested ``title`` based on the current pedalboard status;
        .. code-block:: json

            {
                "ok": true,
                "id": 1,
                "title": "Snapshot name"
            }

        :return: `true` if it was successfully deleted
        """
        title = self.get_argument('title')
        idx   = SESSION.host.snapshot_saveas(title)
        title = SESSION.host.snapshot_name(idx)

        yield gen.Task(SESSION.host.hmi_report_ss_name_if_current, idx)

        self.write({
            'ok': idx is not None,  # FIXME: Always true
            'id': idx,
            'title': title,
        })


class SnapshotRemove(JsonRequestHandler):

    # TODO: Replace GET /snapshot/remove?id=<snapshot id>
    #            to DELETE /pedalboards/<pedalboard id>/snapshots/<snapshot id>
    def get(self):
        """
        Remove the snapshot of identifier ``id`` of the loaded pedalboard

        :return: `true` if it was successfully deleted
        """
        idx = int(self.get_argument('id'))
        ok = SESSION.host.snapshot_remove(idx)

        self.write(ok)
