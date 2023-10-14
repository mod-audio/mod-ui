#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

class ModException(Exception):
    pass


class InvalidSnapshotIdentifierException(ModException):
    def __init__(self, id: int):
        super().__init__(f'id: {id}')
