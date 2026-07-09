#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
Layer-1 characterization test harness bootstrap.

This module runs at collection time, BEFORE any test module gets a chance to
``import mod.webserver`` (and transitively ``mod.settings``, which reads every
``MOD_*`` env var at import time). So all environment setup below is plain
module-level code, not a fixture -- fixtures would run too late.

These tests exercise the real ``mod.webserver.application`` (the module-level
tornado ``web.Application`` built at import time) against a throwaway on-disk
tree. Nothing here calls ``mod.webserver.run()`` or ``prepare()`` -- those pull
in real hardware / mod-host / JACK setup that isn't available in this dev
environment.
"""

import atexit
import os
import shutil
import sys
import tempfile

import pytest

# ----------------------------------------------------------------------------
# 0. Fail fast if the native extension mod.webserver depends on isn't built.
# ----------------------------------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LIBMOD_UTILS_SO = os.path.join(REPO_ROOT, "utils", "libmod_utils.so")

if not os.path.isfile(_LIBMOD_UTILS_SO):
    pytest.exit(
        "libmod_utils.so not found at {0}.\n"
        "Build it first: `make -C utils` (from the repo root). See "
        "mod-ui/CLAUDE.md for one-time environment setup.".format(_LIBMOD_UTILS_SO),
        returncode=1,
    )

# ----------------------------------------------------------------------------
# 1. Build a throwaway data/user-files tree and point every MOD_* env var
#    that mod.settings reads at it, BEFORE mod.webserver (and mod.settings)
#    is ever imported by a test module.
# ----------------------------------------------------------------------------

_TEST_ROOT = tempfile.mkdtemp(prefix="modui-test-")

_DATA_DIR = os.path.join(_TEST_ROOT, "data")
_USER_FILES_DIR = os.path.join(_TEST_ROOT, "user-files")

os.makedirs(_DATA_DIR, exist_ok=True)
os.makedirs(_USER_FILES_DIR, exist_ok=True)

# Replicate the bits of mod.check_environment() that handlers rely on but
# that we never call (check_environment() only runs inside prepare()).
with open(os.path.join(_DATA_DIR, "banks.json"), "w") as fh:
    fh.write("[]")
with open(os.path.join(_DATA_DIR, "favorites.json"), "w") as fh:
    fh.write("[]")

os.environ["MOD_DEV_ENVIRONMENT"] = "1"
os.environ["MOD_LOG"] = "0"
os.environ["MOD_DATA_DIR"] = _DATA_DIR
os.environ["MOD_USER_FILES_DIR"] = _USER_FILES_DIR
os.environ["MOD_HTML_DIR"] = os.path.join(REPO_ROOT, "html")
os.environ["MOD_DEFAULT_PEDALBOARD"] = os.path.join(REPO_ROOT, "default.pedalboard")

# Make the repo importable the same way server.py does (test/ is not on
# sys.path by default under some pytest invocations).
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _cleanup_test_root():
    shutil.rmtree(_TEST_ROOT, ignore_errors=True)


atexit.register(_cleanup_test_root)

# ----------------------------------------------------------------------------
# 2. Fixtures
# ----------------------------------------------------------------------------


class _UserFilesHelper(object):
    """Exposes USER_FILES_DIR plus a seed() helper to test modules."""

    def __init__(self, root):
        self.root = root

    def seed(self, relpath, content=b"data"):
        """Create USER_FILES_DIR/<relpath> (and any parent dirs) with content."""
        fullpath = os.path.join(self.root, relpath)
        os.makedirs(os.path.dirname(fullpath), exist_ok=True)
        mode = "wb" if isinstance(content, bytes) else "w"
        with open(fullpath, mode) as fh:
            fh.write(content)
        return fullpath


def _reset_user_files_dir():
    if os.path.isdir(_USER_FILES_DIR):
        shutil.rmtree(_USER_FILES_DIR)
    os.makedirs(_USER_FILES_DIR, exist_ok=True)


@pytest.fixture(autouse=True)
def user_files():
    """Function-scoped, autouse: wipe and recreate USER_FILES_DIR around
    every test, so tests never see leftovers from one another.

    USER_FILES_DIR itself is fixed for the whole process (mod.settings reads
    MOD_USER_FILES_DIR once, at import time), so we can't swap directories
    per-test -- instead we clear its contents.

    autouse=True (rather than requiring tests to depend on it explicitly)
    because our test classes are unittest.TestCase subclasses
    (tornado.testing.AsyncHTTPTestCase) -- pytest applies autouse fixtures'
    setup/teardown around unittest-style tests too, but does NOT support
    injecting a fixture's return value as a test-method parameter for them.
    Tests that need to seed files use ModUITestCase.seed() (test/base.py)
    instead, which points at this same directory.
    """
    _reset_user_files_dir()
    yield _UserFilesHelper(_USER_FILES_DIR)
    _reset_user_files_dir()
