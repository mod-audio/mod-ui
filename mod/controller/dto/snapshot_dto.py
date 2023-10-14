#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later
from dataclasses import dataclass


@dataclass
class SnapshotDTO:
    id: int
    name: str
