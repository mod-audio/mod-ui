#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

"""The desktop-app seam must not reach a MOD device's browser at all.

MOD hardware is slow to parse and slow to fetch, and none of the seam does
anything there: the panels only render when DesktopApp.setup() has run, which
only happens under MOD Desktop. So GET / omits both asset tags and
/js/templates.js omits the desktop_app_* entries, all keyed on
mod.webserver.DESKTOP.

DESKTOP is read from the environment at mod.settings import time and bound
into mod.webserver's namespace, so these flip the module global -- that is the
name both TemplateHandler.index() and BulkTemplateLoader actually read at
request time. The default under the test environment is False (a device),
which is the case that matters most here.
"""

from base import ModUITestCase

CSS_TAG = "css/desktop-app.css"
JS_TAG = "js/desktop-app.js"


class _DesktopFlag:
    """Flip mod.webserver.DESKTOP for the duration of a test."""

    def set_desktop(self, value):
        import mod.webserver

        self.addCleanup(setattr, mod.webserver, "DESKTOP", mod.webserver.DESKTOP)
        mod.webserver.DESKTOP = value


class TestIndexOmitsDesktopAppAssetsOnDevice(ModUITestCase, _DesktopFlag):
    __test__ = True

    def _index(self):
        response = self.fetch("/?v=1")
        self.assertEqual(response.code, 200)
        return response.body.decode("utf-8")

    def test_device_page_links_neither_asset(self):
        self.set_desktop(False)
        body = self._index()

        self.assertNotIn(CSS_TAG, body)
        self.assertNotIn(JS_TAG, body)

    def test_device_page_carries_the_inline_stub_instead(self):
        # Shared files (desktop.js, cloudplugin.js, hardware.js) call
        # DesktopApp unconditionally on paths that run on a device. Without
        # the script there is no object, so the page defines a stub that
        # answers "not desktop". test/js/desktop-app.test.js pins the stub
        # against the set of calls those files actually make.
        self.set_desktop(False)
        body = self._index()

        self.assertIn("var DesktopApp = {", body)
        self.assertIn("isActive", body)

    def test_desktop_page_links_both_assets_and_drops_the_stub(self):
        self.set_desktop(True)
        body = self._index()

        self.assertIn(CSS_TAG, body)
        self.assertIn(JS_TAG, body)
        self.assertNotIn("var DesktopApp = {", body)


class TestBulkTemplateLoaderSkipsDesktopAppTemplates(ModUITestCase, _DesktopFlag):
    __test__ = True

    def _templates(self):
        response = self.fetch("/js/templates.js")
        self.assertEqual(response.code, 200)
        return response.body.decode("utf-8")

    def test_device_bundle_has_no_desktop_app_templates(self):
        self.set_desktop(False)
        body = self._templates()

        self.assertNotIn("TEMPLATES['desktop_app_", body)
        # The shared templates are untouched by the skip.
        self.assertIn("TEMPLATES['pedalboard']", body)

    def test_desktop_bundle_has_them(self):
        self.set_desktop(True)
        body = self._templates()

        self.assertIn("TEMPLATES['desktop_app_exclusive_panel']", body)
        self.assertIn("TEMPLATES['pedalboard']", body)
