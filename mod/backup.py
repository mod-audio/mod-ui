# SPDX-FileCopyrightText: 2026 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Helpers for Settings -> Backup & Restore, which runs the device's mod-backup tool."""

BACKUP_FLAGS = ("-d", "-p", "-u")

def backup_flags(cdata):
    """'<device configs>,<plugins>[,<user files>]', each '1' or '0' -> mod-backup options.
    Two values (pages before 1.15) still work."""
    flags = cdata.split(",")
    return [flag for index, flag in enumerate(BACKUP_FLAGS) if len(flags) > index and flags[index] == "1"]

def backup_message(stderr):
    """mod-backup's stderr as one sentence for the web interface."""
    msg = stderr.decode("utf-8", errors="ignore").strip()
    if len(msg) > 1:
        msg = msg[0].upper() + msg[1:]
        if not msg.endswith("."):
            msg += "."
    return msg
