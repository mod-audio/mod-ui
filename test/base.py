#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Shared base class for layer-1 characterization tests.

Uses tornado 4.3's tornado.testing.AsyncHTTPTestCase (unittest-based, plain
tornado-4 idioms -- no async/await) against the real module-level
mod.webserver.application. conftest.py has already set every MOD_* env var
before this module (or any test module) imports mod.webserver.
"""

import json

from tornado.testing import AsyncHTTPTestCase

from conftest import _UserFilesHelper, _USER_FILES_DIR


class ModUITestCase(AsyncHTTPTestCase):
    # Every test_*.py imports this class directly (`from base import
    # ModUITestCase`) so it can subclass it -- which also puts it in each
    # test module's globals. pytest's unittest integration collects *any*
    # TestCase subclass it finds at module scope, regardless of name (the
    # usual python_classes="Test*" filter does not apply to TestCase
    # subclasses), so without this it would try to collect ModUITestCase
    # itself as a test in every module that imports it and fail with
    # "no attribute 'runTest'" (it defines no test_* methods of its own).
    # Concrete subclasses below must set __test__ = True to opt back in,
    # since __test__ is looked up via normal attribute inheritance.
    __test__ = False

    def runTest(self):
        # Never actually invoked as a real test (real test_* methods are
        # collected and run individually by pytest). Exists only because
        # modern pytest (9.x) instantiates every unittest.TestCase subclass
        # once with methodName="runTest" during collection, to register
        # fixture factories (_pytest.unittest.UnitTestCase.newinstance()).
        # tornado 4.3's own AsyncTestCase.__init__ (tornado/testing.py)
        # unconditionally does getattr(self, methodName) -- unlike stdlib
        # unittest.TestCase, it does not special-case a missing "runTest" --
        # so without this method that probe instantiation raises
        # AttributeError and collection fails for every test class.
        pass

    def get_app(self):
        # Imported lazily (not at module top-level) so that conftest.py's
        # env-var setup is guaranteed to have already run before mod.webserver
        # -- and mod.settings, which reads MOD_* env vars at import time --
        # is ever imported.
        import mod.webserver
        return mod.webserver.application

    def seed(self, relpath, content=b"data"):
        """Write USER_FILES_DIR/<relpath> (creating parent dirs) for a test.

        Thin wrapper around conftest's user_files fixture helper, exposed
        here because pytest fixture return values can't be injected as
        parameters into unittest.TestCase test methods (which is what these
        AsyncHTTPTestCase-derived tests are). The autouse `user_files`
        fixture in conftest.py still handles wiping USER_FILES_DIR between
        tests.
        """
        return _UserFilesHelper(_USER_FILES_DIR).seed(relpath, content=content)

    def fetch_json(self, path, **kwargs):
        """GET/POST/etc. `path` and decode the response body as JSON.

        Asserts the response declares a JSON content type, matching the
        JsonRequestHandler.write() convention used across mod/webserver.py.
        """
        response = self.fetch(path, **kwargs)
        content_type = response.headers.get("Content-Type", "")
        assert "application/json" in content_type, (
            "expected JSON content type for %s, got %r (body: %r)"
            % (path, content_type, response.body)
        )
        return response, json.loads(response.body.decode("utf-8"))
