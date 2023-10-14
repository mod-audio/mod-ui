#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later
from typing import List

from mod.controller.dto.snapshot_dto import SnapshotDTO
from mod.exception import InvalidSnapshotIdentifierException
from mod.session import SESSION
from mod.settings import DEFAULT_SNAPSHOT_NAME


class SnapshotService:

    @staticmethod
    def get_all() -> List[SnapshotDTO]:
        """
        Get all valid snapshots

        :return: Snapshot successfully saved
        """
        snapshots = SESSION.host.pedalboard_snapshots
        return [
            SnapshotDTO(id=i, name=snapshots[i]['name'])
            for i in range(len(snapshots)) if snapshots[i] is not None  # TODO: when snapshot is None?
        ]

    @staticmethod
    def get(identifier: int) -> SnapshotDTO:
        """
        :param identifier: Snapshot identifier

        :return: Snapshot name if it refers to a valid snapshot, else, returns the default snapshot name
        """

        snapshot_name = SESSION.host.snapshot_name(identifier) or DEFAULT_SNAPSHOT_NAME
        snapshot_id = identifier if snapshot_name is not None else None

        return SnapshotDTO(id=snapshot_id, name=snapshot_name)

    @staticmethod
    def rename(identifier: int, name: str) -> SnapshotDTO:
        """
        Rename the snapshot of ``identifier`` with the suggested ``name``.

        If there is a snapshot with the same title, the name will be
        slightly changed with a number suffix.

        :raises InvalidSnapshotIdentifierException: when the suggested refers to a non-existent snapshot

        :param identifier: Snapshot identifier
        :param name: Snapshot new name

        :return: Snapshot renamed
        """
        ok = SESSION.host.snapshot_rename(identifier, name)

        if not ok:
            raise InvalidSnapshotIdentifierException(identifier)

        return SnapshotDTO(
            identifier,
            SESSION.host.snapshot_name(identifier)
        )

    @staticmethod
    def save() -> bool:
        """
        :return: Snapshot successfully saved
        """
        return SESSION.host.snapshot_save()

    @staticmethod
    def save_as(name: str) -> SnapshotDTO:
        """
        Create a new snapshot with the suggested ``name`` based on the current pedalboard status.

        If there is a snapshot with the same title, the name of the new snapshot will be
        slightly changed with a number suffix.

        :param name: suggested title
        :return: information of the snapshot created
        """
        id = SESSION.host.snapshot_saveas(name)
        name = SESSION.host.snapshot_name(id)

        return SnapshotDTO(id=id, name=name)

    @staticmethod
    def delete(identifier: int) -> bool:
        """
        Delete snapshot of `identifier` if it exists

        :param identifier: Identifier of snapshot that was requested to be deleted

        :return: Snapshot successfully deleted
        """
        return SESSION.host.snapshot_remove(identifier)
