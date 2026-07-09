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

NEVER-CALL LIST -- routes no test in this suite may fetch. They run
subprocesses, write outside the sandboxed temp tree, or block forever:

- ``/system/cleanup``          deletes ``~/.pedalboards`` and ``~/.lv2``
- ``/system/exechange``        reboot/systemctl/mod-backup subprocesses
- ``/update/download/``, ``/update/begin``      writes under /data, /tmp
- ``/controlchain/download/``  firmware download, subprocess mv to /tmp
- ``/switch_cpu_freq/``        writes /sys/devices/system/cpu
- ``/recording/*``             needs JACK; ``play/wait`` long-polls forever
- ``/pedalboard/pack_bundle``, ``/pedalboard/load_web``,
  ``/pedalboard/factorycopy``, ``/pedalboard/image/generate``   subprocesses
- ``/effect/install``, ``/sdk/install``, ``/package/uninstall`` touch the
  plugin dir via subprocess tar / rmtree
- ``/effect/list``, ``/effect/get*``, ``/effect/bulk``, ``/effect/add``,
  ``/effect/image``, ``/effect/file``, ``/resources/(.*)?uri=``  dereference
  the global lilv world, which is NULL until ``modtools.utils.init()`` runs
  -- calling them without init SEGFAULTS the test process (see the phase-6
  spec in docs/ before touching these)
- ``/pedalboard/list``, ``/banks/`` while a real pedalboard bundle exists in
  the sandbox pedalboards dir -- get_all_pedalboards SEGFAULTS parsing it
  (NamespaceDefinitions::init / lilv_new_uri, needs the uninitialized global
  lilv world). Both are safe against an EMPTY pedalboards dir; save/remove a
  bundle within one test and only list after the dir is empty again
- ``/effect/remove/<instance>``    HANGS (no crash, no timeout server-side --
  the response is simply never sent) for any instance name not already
  registered in ``SESSION.host.mapper``, which is every instance name in
  this sandbox (``POST /effect/add`` is itself banned above, so no instance
  can ever be registered). Root cause: ``Host.remove_plugin``
  (``mod/host.py:2604``, ``@gen.coroutine``) calls
  ``self.mapper.get_id_without_creating(instance)`` *before* its own
  try/except KeyError guard around ``self.plugins.pop(...)`` a few lines
  down -- the KeyError from the lookup itself is swallowed into the
  coroutine's Future instead of propagating, so the handler's
  ``callback(False)`` is never reached and ``gen.Task`` in ``EffectRemove``
  never resolves. Confirmed by probing with a 4s client-side
  ``request_timeout``: HTTP 599 (client timeout), not a fast response. See
  ``test/test_host_commands.py`` module docstring (phase 4).
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
_PEDALBOARDS_DIR = os.path.join(_TEST_ROOT, "pedalboards")
_PLUGINS_DIR = os.path.join(_TEST_ROOT, "lv2")

os.makedirs(_DATA_DIR, exist_ok=True)
os.makedirs(_USER_FILES_DIR, exist_ok=True)
os.makedirs(_PEDALBOARDS_DIR, exist_ok=True)
os.makedirs(_PLUGINS_DIR, exist_ok=True)

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
# Without these two, mod.settings defaults LV2_PEDALBOARDS_DIR/LV2_PLUGIN_DIR
# to ~/.pedalboards and ~/.lv2 -- and pedalboard save/remove handlers would
# write into the REAL user home instead of the sandbox.
os.environ["MOD_USER_PEDALBOARDS_DIR"] = _PEDALBOARDS_DIR
os.environ["MOD_USER_PLUGINS_DIR"] = _PLUGINS_DIR

# ----------------------------------------------------------------------------
# 1b. Sandbox guard: every writable path mod.settings resolves must live
#     under the throwaway test root. mod.settings only reads env vars and
#     stdlib (importing it here is cheap and does NOT load libmod_utils.so),
#     so this catches a broken/renamed MOD_* env var before any test can
#     write outside the sandbox.
# ----------------------------------------------------------------------------

from mod import settings as _mod_settings  # noqa: E402  (needs env set above)

for _name in ("DATA_DIR", "USER_FILES_DIR", "LV2_PEDALBOARDS_DIR", "LV2_PLUGIN_DIR"):
    _path = os.path.realpath(getattr(_mod_settings, _name))
    if not _path.startswith(os.path.realpath(_TEST_ROOT) + os.sep):
        pytest.exit(
            "SANDBOX GUARD: mod.settings.{0} resolves to {1}, which is outside "
            "the test root {2}. Refusing to run -- tests could write into real "
            "user/system directories. Check the MOD_* env vars set in "
            "test/conftest.py against mod/settings.py.".format(_name, _path, _TEST_ROOT),
            returncode=1,
        )

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


def _reset_pedalboards_dir():
    if os.path.isdir(_PEDALBOARDS_DIR):
        shutil.rmtree(_PEDALBOARDS_DIR)
    os.makedirs(_PEDALBOARDS_DIR, exist_ok=True)


@pytest.fixture(autouse=True)
def pedalboards_dir():
    """Function-scoped, autouse: wipe/recreate LV2_PEDALBOARDS_DIR and reset
    the process-global SESSION around every test.

    Mirrors ``user_files`` above, for the same reason: LV2_PEDALBOARDS_DIR is
    fixed for the whole process (mod.settings reads MOD_USER_PEDALBOARDS_DIR
    once, at import time), so we clear its contents instead of swapping
    directories. Phase 3 (docs/characterization-phase-3.md) is the first
    phase whose tests write real pedalboard bundles to disk via
    ``SESSION.host.save()`` (through ``POST /pedalboard/save``) and mutate
    process-global state on ``SESSION.host`` (``pedalboard_path``,
    ``pedalboard_snapshots``, ``current_pedalboard_snapshot_id``, ...) via
    ``/pedalboard/load_bundle/`` and ``/snapshot/*``. Neither the on-disk
    bundles nor that in-memory state may leak between tests or modules.

    ``SESSION.reset(callback)`` (mod/session.py) runs its callback
    synchronously here: under ``MOD_DEV_ENVIRONMENT=1`` the FakeHMI is never
    "initialized" (see module docstring), so ``Session.reset`` takes its
    synchronous branch straight to ``Host.reset``, and ``FakeHost`` (see
    ``mod/development.py``) invokes every ``send_notmodified``/
    ``send_modified`` callback immediately with ``True`` -- no real
    mod-host, no IOLoop pump required.
    """
    _reset_pedalboards_dir()
    from mod.webserver import SESSION
    SESSION.reset(lambda ok: None)
    yield
    SESSION.reset(lambda ok: None)
    _reset_pedalboards_dir()
