#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

# Plugin preset files (.modpreset) for the Export / Import buttons of the preset bar.
#
# A .modpreset is a tar.gz with:
#   modpreset.json            what the preset is for (plugin URI, versions, name)
#   <name>.lv2/manifest.ttl   the LV2 preset bundle, as mod-host saves it
#   <name>.lv2/<name>.ttl
#
# Only .ttl files go in: files a preset points to (NAM models, IRs, samples) are left out.
# Must stay Python 3.4 compatible (device image).

import io
import json
import os
import posixpath
import tarfile
import time
import zlib

FORMAT_VERSION = 1
EXTENSION = ".modpreset"
HEADER_NAME = "modpreset.json"
MANIFEST_NAME = "manifest.ttl"

# a preset is a few KB; anything near these limits is not a preset
MAX_FILE_SIZE = 1024 * 1024
MAX_MEMBERS = 8

class PresetFileError(Exception):
    pass

def make_header(plugin_uri, plugin_version, name, os_version, platform):
    return {
        'format': FORMAT_VERSION,
        'plugin_uri': plugin_uri,
        'plugin_version': plugin_version,
        'name': name,
        'os_version': os_version,
        'platform': platform,
        'created': time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

def _add_bytes(tar, name, data):
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mtime = int(time.time())
    info.mode = 0o644
    tar.addfile(info, io.BytesIO(data))

def pack(bundlepath, header):
    """Pack a preset bundle. Returns (data, left_out), left_out = names that were not .ttl files."""
    bundlename = os.path.basename(bundlepath.rstrip("/"))
    ttlfiles = []
    left_out = []

    for name in sorted(os.listdir(bundlepath)):
        path = os.path.join(bundlepath, name)
        if name.endswith(".ttl") and os.path.isfile(path) and not os.path.islink(path):
            ttlfiles.append(name)
        else:
            left_out.append(name)

    if MANIFEST_NAME not in ttlfiles or len(ttlfiles) < 2:
        raise PresetFileError("The saved preset is incomplete")

    header = dict(header)
    header['files_left_out'] = left_out

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        _add_bytes(tar, HEADER_NAME, json.dumps(header, indent=2, sort_keys=True).encode("utf-8"))
        for name in ttlfiles:
            with open(os.path.join(bundlepath, name), 'rb') as fh:
                _add_bytes(tar, "%s/%s" % (bundlename, name), fh.read())

    return buf.getvalue(), left_out

def unpack(data, plugin_uri):
    """
    Read and check a .modpreset (untrusted: it comes from someone else's unit).
    Nothing is written to disk here. Returns a dict with:
      header, preset_file (name of the preset .ttl), files ({name: bytes}, manifest included)
    Raises PresetFileError with a message for the user.
    """
    if len(data) > MAX_FILE_SIZE:
        raise PresetFileError("This file is too big to be a preset")

    header = None
    bundlename = None
    files = {}
    total = 0

    try:
        tar = tarfile.open(fileobj=io.BytesIO(data), mode="r:gz")
    except (tarfile.TarError, OSError, EOFError, zlib.error):
        raise PresetFileError("This is not a %s file" % EXTENSION)

    try:
        count = 0
        for member in tar:
            count += 1
            if count > MAX_MEMBERS:
                raise PresetFileError("This file has too many entries to be a preset")
            if not member.isfile():
                raise PresetFileError("This file contains something other than a preset")

            name = member.name
            if "\\" in name or name.startswith("/") or posixpath.normpath(name) != name:
                raise PresetFileError("This file contains an invalid path")

            total += member.size
            if total > MAX_FILE_SIZE:
                raise PresetFileError("This file is too big to be a preset")

            content = tar.extractfile(member).read(MAX_FILE_SIZE + 1)
            parts = name.split("/")

            if parts == [HEADER_NAME]:
                try:
                    header = json.loads(content.decode("utf-8"))
                except ValueError:
                    raise PresetFileError("This preset file is damaged")
                continue

            if len(parts) != 2 or not parts[0].endswith(".lv2") or not parts[1].endswith(".ttl"):
                raise PresetFileError("This file contains something other than a preset")
            if parts[1].startswith("."):
                raise PresetFileError("This file contains an invalid path")
            if bundlename is None:
                bundlename = parts[0]
            elif bundlename != parts[0]:
                raise PresetFileError("This file contains more than one preset")

            files[parts[1]] = content

    except (tarfile.TarError, OSError, EOFError, zlib.error):
        raise PresetFileError("This preset file is damaged")
    finally:
        tar.close()

    if not isinstance(header, dict):
        raise PresetFileError("This is not a %s file" % EXTENSION)

    fmt = header.get('format')
    if not isinstance(fmt, int):
        raise PresetFileError("This preset file is damaged")
    if fmt > FORMAT_VERSION:
        raise PresetFileError("This preset was made by a newer MOD OS, please update")

    if header.get('plugin_uri') != plugin_uri:
        raise PresetFileError("This preset is for another plugin (%s)" % header.get('plugin_uri'))

    presetfiles = [name for name in files if name != MANIFEST_NAME]
    if MANIFEST_NAME not in files or len(presetfiles) != 1:
        raise PresetFileError("This preset file is damaged")

    if not isinstance(header.get('name'), str) or not header['name'].strip():
        header['name'] = presetfiles[0][:-4]

    return {
        'header': header,
        'preset_file': presetfiles[0],
        'files': files,
    }
