#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Characterization tests for GET / (mod/webserver.py:TemplateHandler).

This is the page a future Tone3000-tab edit will touch (the #main-menu
trigger-icon cluster). We pin the redirect-without-?v= behavior and, if the
dev-fake environment can render the full page without JACK/hardware, that
the rendered HTML still contains the anchor points the future edit needs.
"""

from base import ModUITestCase


class TestIndexRedirect(ModUITestCase):
    __test__ = True

    def test_bare_get_redirects_with_version_query_arg(self):
        response = self.fetch("/", follow_redirects=False)
        self.assertEqual(response.code, 302)
        location = response.headers.get("Location", "")
        self.assertIn("v=", location)


class TestIndexRender(ModUITestCase):
    __test__ = True

    # TemplateHandler.get (mod/webserver.py) is a gen.coroutine that awaits
    # SESSION.wait_for_hardware_if_needed -- if that never calls back under
    # the dev-fake environment, this test would hang. self.fetch(...)
    # applies AsyncTestCase's own timeout (ASYNC_TEST_TIMEOUT env var,
    # default 5s) as a guard; conftest/CI can raise it if 5s is too tight.

    def test_get_with_version_renders_index_html(self):
        response = self.fetch("/?v=1")
        self.assertEqual(response.code, 200)
        self.assertIn("text/html", response.headers.get("Content-Type", ""))

        body = response.body.decode("utf-8")
        self.assertIn('id="main-menu"', body)
        self.assertIn('id="mod-file-manager"', body)
