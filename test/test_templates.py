#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Characterization tests for the template/static-file loaders and the
header conventions shared by every handler base class in mod/webserver.py:

- TemplateLoader (/load_template/<name>.html)
- BulkTemplateLoader (/js/templates.js)
- TimelessStaticFileHandler (any static file, e.g. /js/desktop.js)
- header pinning: JsonRequestHandler (no Date, no cache headers) vs
  CachedJsonRequestHandler (Cache-Control + fixed Expires)

None of these write anything, so no snapshot/restore fixture is needed.
"""

from base import ModUITestCase


class TestTemplateLoader(ModUITestCase):
    __test__ = True

    def test_loads_known_template_from_html_include(self):
        response = self.fetch("/load_template/pedalboard.html")
        self.assertEqual(response.code, 200)
        self.assertIn("text/plain", response.headers.get("Content-Type", ""))
        self.assertTrue(len(response.body) > 0)

    def test_unknown_template_is_500(self):
        # TemplateLoader.get() open()s the file directly with no
        # os.path.exists guard, so a missing template surfaces as an
        # uncaught FileNotFoundError -> tornado 500, not a 404.
        response = self.fetch("/load_template/does_not_exist.html")
        self.assertEqual(response.code, 500)


class TestBulkTemplateLoader(ModUITestCase):
    __test__ = True

    def test_bundles_html_include_into_templates_object(self):
        response = self.fetch("/js/templates.js")
        self.assertEqual(response.code, 200)
        self.assertIn("text/javascript", response.headers.get("Content-Type", ""))

        body = response.body.decode("utf-8")
        self.assertIn("TEMPLATES['pedalboard']", body)

    def test_has_cache_control_and_expires_headers(self):
        # BulkTemplateLoader can't subclass CachedJsonRequestHandler (it's
        # not JSON), so it sets the same two headers by hand -- pin that
        # both routes converge on the same cache contract.
        response = self.fetch("/js/templates.js")
        self.assertEqual(
            response.headers.get("Cache-Control"), "public, max-age=31536000"
        )
        self.assertEqual(
            response.headers.get("Expires"), "Mon, 31 Dec 2035 12:00:00 gmt"
        )
        self.assertNotIn("Date", response.headers)


class TestTimelessStaticFileHandler(ModUITestCase):
    __test__ = True

    def test_static_file_has_no_date_header(self):
        response = self.fetch("/js/desktop.js")
        self.assertEqual(response.code, 200)
        self.assertNotIn("Date", response.headers)
        self.assertEqual(
            response.headers.get("Cache-Control"), "public, max-age=31536000"
        )
        self.assertEqual(
            response.headers.get("Expires"), "Mon, 31 Dec 2035 12:00:00 gmt"
        )


class TestJsonRequestHandlerHeaders(ModUITestCase):
    __test__ = True

    def test_plain_json_route_has_no_date_and_no_cache_headers(self):
        response = self.fetch("/files/list?types=bogus")
        self.assertEqual(response.code, 200)
        self.assertNotIn("Date", response.headers)
        self.assertNotIn("Cache-Control", response.headers)
        self.assertNotIn("Expires", response.headers)


class TestCachedJsonRequestHandlerHeaders(ModUITestCase):
    __test__ = True

    def test_pedalboard_image_check_has_cache_headers(self):
        # PedalboardImageCheck (CachedJsonRequestHandler) is filesystem-only
        # (SESSION.screenshot_generator.check_screenshot just stats a
        # thumbnail.png next to the given bundlepath) -- safe to call
        # without lilv/JACK, unlike the /effect/* routes on the NEVER-CALL
        # list. The other CachedJsonRequestHandler route, EffectGet, does
        # need the global lilv world and is skipped (see NEVER-CALL list).
        response, body = self.fetch_json(
            "/pedalboard/image/check?bundlepath=/nonexistent/thing.pedalboard"
        )
        self.assertEqual(response.code, 200)
        self.assertEqual(body["status"], -1)

        self.assertEqual(
            response.headers.get("Cache-Control"), "public, max-age=31536000"
        )
        self.assertEqual(
            response.headers.get("Expires"), "Mon, 31 Dec 2035 12:00:00 gmt"
        )
        self.assertNotIn("Date", response.headers)
