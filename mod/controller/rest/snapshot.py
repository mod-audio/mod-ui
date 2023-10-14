#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later
from tornado import web, gen

from mod.controller.handler.json_request_handler import JsonRequestHandler
from mod.exception import InvalidSnapshotIdentifierException
from mod.service.snapshot_service import SnapshotService
from mod.session import SESSION


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
        snapshot = SnapshotService.get(idx)

        self.write({
            'ok': bool(snapshot.name),  # FIXME: Always true
            'name': snapshot.name
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
        snapshot_names = {
            snapshot.id: snapshot.name
            for snapshot in SnapshotService.get_all()
        }

        self.write(snapshot_names)


class SnapshotSave(JsonRequestHandler):

    # TODO: Replace GET /snapshot/save
    #            to SAVE /pedalboards/current/snapshots/current
    def post(self):
        """
        Update the current snapshot status

        :return: `true` if it was successfully deleted
        """
        ok = SnapshotService.save()
        self.write(ok)


class SnapshotSaveAs(JsonRequestHandler):

    # TODO: Replace GET /snapshot/saveas
    #            to SAVE /pedalboards/current/snapshots
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

        snapshot = SnapshotService.save_as(title)

        # FIXME: Use HMI Service instead of SESSION
        yield gen.Task(SESSION.host.hmi_report_ss_name_if_current, snapshot.id)

        self.write({
            'ok': snapshot.id is not None,  # FIXME: Always true
            'id': snapshot.id,
            'title': snapshot.name,
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
        ok = SnapshotService.delete(idx)

        self.write(ok)


class SnapshotRename(JsonRequestHandler):

    # TODO: Replace GET /snapshot/rename?id=<snapshot id>&?name=<snapshot name>
    #            to PATCH /pedalboards/<pedalboard id>/snapshots/<snapshot id>
    @web.asynchronous
    @gen.engine
    def get(self):
        """
        Rename the snapshot of ``ìd`` identifier with the suggested ``name``.

        .. code-block:: json

            {
                "ok": true,
                "title": "Snapshot name"
            }

        :return: new snapshot name
        """
        idx = int(self.get_argument('id'))
        title = self.get_argument('title')

        ok = True
        try:
            snapshot = SnapshotService.rename(idx, title)
            title = snapshot.name
        except InvalidSnapshotIdentifierException:
            ok = False

        # TODO: Why report when is ok false?
        # FIXME: Use HMI Service instead of SESSION
        yield gen.Task(SESSION.host.hmi_report_ss_name_if_current, idx)

        self.write({
            'ok': ok,
            'title': title,
        })
