#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

# Pedalboard files (.modpedalboard) for Export / Import in the Pedalboards Library.
#
# A .modpedalboard is a tar.gz with:
#   modpedalboard.json     what the pedalboard is (title, plugins, OS version, files it uses)
#   <name>.pedalboard/...  the pedalboard bundle as saved on the unit (ttl files, addressings,
#                          snapshots, plugin state folders, screenshot, thumbnail)
#
# User files the pedalboard uses (NAM models, IRs, samples) are not included; their names are
# listed in the header. Packed and unpacked in Python (no shell tools: also runs on Windows).
# Must stay Python 3.4 compatible (device image).

import io
import json
import os
import posixpath
import re
import tarfile
import time
import zlib

FORMAT_VERSION = 1
EXTENSION = ".modpedalboard"
HEADER_NAME = "modpedalboard.json"

# a pedalboard bundle is usually well under 1 MB; plugin state folders can add some
MAX_PACKED_SIZE = 32 * 1024 * 1024
MAX_UNPACKED_SIZE = 128 * 1024 * 1024
MAX_MEMBERS = 2000

class PedalboardFileError(Exception):
    pass

def make_header(title, plugins, files, os_version, platform):
    return {
        'format': FORMAT_VERSION,
        'title': title,
        'plugins': plugins,
        'files': files,
        'os_version': os_version,
        'platform': platform,
        'created': time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

def _bundle_files(bundlepath):
    "Regular files of a bundle, relative paths with '/', symlinks skipped."
    result = []
    for root, dirs, files in os.walk(bundlepath):
        dirs[:] = sorted(d for d in dirs if not os.path.islink(os.path.join(root, d)))
        for name in sorted(files):
            path = os.path.join(root, name)
            if os.path.islink(path) or not os.path.isfile(path):
                continue
            result.append(os.path.relpath(path, bundlepath).replace(os.sep, "/"))
    return result

def find_user_files(bundlepath, user_files_dir):
    """
    Names of user files a pedalboard points to, relative to the user files folder
    (e.g. "NAM Models/amp.nam"), read from the paths in its ttl files.
    """
    found = set()
    prefixes = set([user_files_dir.rstrip("/\\")])
    if os.sep != "/":
        prefixes.add(user_files_dir.rstrip("/\\").replace(os.sep, "/"))

    for relpath in _bundle_files(bundlepath):
        if not relpath.endswith(".ttl"):
            continue
        try:
            with open(os.path.join(bundlepath, relpath), 'r', encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
        except (IOError, OSError):
            continue
        for prefix in prefixes:
            for match in re.finditer(re.escape(prefix) + r'[/\\]([^"<>\n]+)', text):
                name = match.group(1).replace("\\", "/").strip()
                if name:
                    found.add(name)

    return sorted(found)

def _add_bytes(tar, name, data, mtime=None):
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mtime = int(mtime if mtime is not None else time.time())
    info.mode = 0o644
    tar.addfile(info, io.BytesIO(data))

def pack(bundlepath, header):
    "Pack a saved pedalboard bundle. Returns the file contents."
    bundlename = os.path.basename(bundlepath.rstrip("/\\"))
    relpaths = _bundle_files(bundlepath)

    if "manifest.ttl" not in relpaths:
        raise PedalboardFileError("The saved pedalboard is incomplete")

    total = sum(os.path.getsize(os.path.join(bundlepath, p)) for p in relpaths)
    if total > MAX_UNPACKED_SIZE or len(relpaths) + 1 > MAX_MEMBERS:
        raise PedalboardFileError("This pedalboard is too big to export")

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        _add_bytes(tar, HEADER_NAME, json.dumps(header, indent=2, sort_keys=True).encode("utf-8"))
        for relpath in relpaths:
            path = os.path.join(bundlepath, relpath)
            with open(path, 'rb') as fh:
                _add_bytes(tar, "%s/%s" % (bundlename, relpath), fh.read(), os.path.getmtime(path))

    data = buf.getvalue()
    if len(data) > MAX_PACKED_SIZE:
        raise PedalboardFileError("This pedalboard is too big to export")
    return data

def _check_name(name):
    if not name or "\\" in name or name.startswith("/") or posixpath.normpath(name) != name.rstrip("/"):
        raise PedalboardFileError("This file contains an invalid path")
    for part in name.rstrip("/").split("/"):
        if part in ("", ".", "..") or part.startswith("."):
            raise PedalboardFileError("This file contains an invalid path")

def unpack(data, destdir):
    """
    Read and check a .modpedalboard (untrusted: it comes from another unit or someone else) and
    write its bundle into destdir, which must exist and be empty.
    Returns (header, bundlepath). Raises PedalboardFileError with a message for the user.
    """
    if len(data) > MAX_PACKED_SIZE:
        raise PedalboardFileError("This file is too big to be a pedalboard")

    try:
        tar = tarfile.open(fileobj=io.BytesIO(data), mode="r:gz")
    except (tarfile.TarError, OSError, EOFError, zlib.error):
        raise PedalboardFileError("This is not a %s file" % EXTENSION)

    header = None
    bundlename = None
    contents = []
    total = 0

    try:
        count = 0
        for member in tar:
            count += 1
            if count > MAX_MEMBERS:
                raise PedalboardFileError("This file has too many entries to be a pedalboard")

            name = member.name
            _check_name(name)

            if member.isdir():
                continue
            if not member.isfile():
                raise PedalboardFileError("This file contains something other than a pedalboard")

            total += member.size
            if total > MAX_UNPACKED_SIZE:
                raise PedalboardFileError("This file is too big to be a pedalboard")

            content = tar.extractfile(member).read(member.size + 1)
            if len(content) != member.size:
                raise PedalboardFileError("This pedalboard file is damaged")

            if name == HEADER_NAME:
                try:
                    header = json.loads(content.decode("utf-8"))
                except ValueError:
                    raise PedalboardFileError("This pedalboard file is damaged")
                continue

            parts = name.split("/")
            if len(parts) < 2 or not parts[0].endswith(".pedalboard"):
                raise PedalboardFileError("This file contains something other than a pedalboard")
            if bundlename is None:
                bundlename = parts[0]
            elif bundlename != parts[0]:
                raise PedalboardFileError("This file contains more than one pedalboard")

            contents.append((parts[1:], content))

    except (tarfile.TarError, OSError, EOFError, zlib.error):
        raise PedalboardFileError("This pedalboard file is damaged")
    finally:
        tar.close()

    if not isinstance(header, dict):
        raise PedalboardFileError("This is not a %s file" % EXTENSION)

    fmt = header.get('format')
    if not isinstance(fmt, int):
        raise PedalboardFileError("This pedalboard file is damaged")
    if fmt > FORMAT_VERSION:
        raise PedalboardFileError("This pedalboard was made by a newer MOD OS, please update")

    if bundlename is None or ["manifest.ttl"] not in [parts for parts, _ in contents]:
        raise PedalboardFileError("This pedalboard file is damaged")

    if not isinstance(header.get('title'), str) or not header['title'].strip():
        header['title'] = bundlename[:-len(".pedalboard")]
    for key in ('plugins', 'files'):
        if not isinstance(header.get(key), list):
            header[key] = []

    bundlepath = os.path.join(destdir, bundlename)
    for parts, content in contents:
        path = os.path.join(bundlepath, *parts)
        folder = os.path.dirname(path)
        if not os.path.isdir(folder):
            os.makedirs(folder)
        with open(path, 'wb') as fh:
            fh.write(content)

    return header, bundlepath

def relocate_user_files(bundlepath, source_dir, local_dir):
    """
    Point the user-file paths of an imported pedalboard at this unit's user files folder
    (a Dwarf keeps them in /data/user-files, MOD Desktop in the user's documents).
    Only the ttl files of the bundle are touched.
    """
    if not isinstance(source_dir, str) or not source_dir:
        return
    source = source_dir.rstrip("/\\")
    local = local_dir.rstrip("/\\")
    if source == local:
        return

    for relpath in _bundle_files(bundlepath):
        if not relpath.endswith(".ttl"):
            continue
        path = os.path.join(bundlepath, *relpath.split("/"))
        with open(path, 'r', encoding="utf-8", errors="surrogateescape") as fh:
            text = fh.read()
        if source not in text:
            continue

        def repl(match):
            return local + os.sep + match.group(1).replace("\\", "/").replace("/", os.sep)

        text = re.sub(re.escape(source) + r'[/\\]([^"<>\n]+)', repl, text)
        with open(path, 'w', encoding="utf-8", errors="surrogateescape") as fh:
            fh.write(text)
