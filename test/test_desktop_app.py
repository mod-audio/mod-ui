#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

"""The MOD Desktop seam, Python side.

Two things are pinned here:

1. mod.settings.TONE3000_CLIENT_ID precedence. A frozen MOD Desktop build has
   no shell environment when launched from Finder/Explorer, so cx_Freeze bakes
   the id in as BUILD_CONSTANTS.MOD_TONE3000_CLIENT_ID (fed from the
   environment at freeze time, never committed). The environment still wins
   when it is set, and a device -- no BUILD_CONSTANTS at all -- is unchanged.

2. html/index.html rendered with desktop_app off carries nothing of the seam:
   no js/desktop-app.js, no css/desktop-app.css, no DesktopApp call, no
   desktop_app_templates cache key. Rendered with it on, it carries all four.
   This renders the template directly with tornado, the way TemplateHandler
   does; it needs tornado importable and is skipped otherwise.

Run with:  python3 -m unittest discover -s test -p 'test_*.py'
"""

import importlib
import os
import re
import sys
import types
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_DIR = os.path.join(REPO_ROOT, 'html')

if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


class TestTone3000ClientIdPrecedence(unittest.TestCase):

    def setUp(self):
        self._environ = dict(os.environ)
        self._modules = {k: v for k, v in sys.modules.items()
                         if k in ('BUILD_CONSTANTS', 'mod.settings')}
        # Keep the import side effects (key paths, data dirs) inside a sandbox
        # whatever this machine's environment says.
        os.environ['MOD_DATA_DIR'] = os.path.join(REPO_ROOT, 'test', '.tmp-data')

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._environ)
        for name in ('BUILD_CONSTANTS', 'mod.settings'):
            sys.modules.pop(name, None)
        sys.modules.update(self._modules)

    def _settings(self, env, frozen):
        """Import mod.settings afresh with MOD_TONE3000_CLIENT_ID = `env` (None
        = unset) and BUILD_CONSTANTS.MOD_TONE3000_CLIENT_ID = `frozen` (None =
        no BUILD_CONSTANTS module, i.e. a device or a source checkout)."""
        os.environ.pop('MOD_TONE3000_CLIENT_ID', None)
        if env is not None:
            os.environ['MOD_TONE3000_CLIENT_ID'] = env

        sys.modules.pop('BUILD_CONSTANTS', None)
        if frozen is not None:
            constants = types.ModuleType('BUILD_CONSTANTS')
            constants.MOD_TONE3000_CLIENT_ID = frozen
            sys.modules['BUILD_CONSTANTS'] = constants

        sys.modules.pop('mod.settings', None)
        return importlib.import_module('mod.settings')

    def test_device_without_build_constants_reads_the_environment(self):
        self.assertEqual(self._settings('t3k_pub_env', None).TONE3000_CLIENT_ID, 't3k_pub_env')

    def test_device_without_anything_has_no_id(self):
        self.assertIsNone(self._settings(None, None).TONE3000_CLIENT_ID)

    def test_frozen_build_falls_back_to_the_build_constant(self):
        self.assertEqual(self._settings(None, 't3k_pub_frozen').TONE3000_CLIENT_ID, 't3k_pub_frozen')

    def test_environment_wins_over_the_build_constant(self):
        self.assertEqual(self._settings('t3k_pub_env', 't3k_pub_frozen').TONE3000_CLIENT_ID, 't3k_pub_env')

    def test_an_empty_environment_value_does_not_shadow_the_build_constant(self):
        self.assertEqual(self._settings('', 't3k_pub_frozen').TONE3000_CLIENT_ID, 't3k_pub_frozen')

    def test_the_environment_variable_is_consumed(self):
        # As before: popped, so no child process inherits it.
        self._settings('t3k_pub_env', None)
        self.assertNotIn('MOD_TONE3000_CLIENT_ID', os.environ)


try:
    import tornado.template
except ImportError:  # pragma: no cover - depends on the host
    tornado = None


@unittest.skipIf(tornado is None, 'tornado is not importable here')
class TestIndexTemplateKeepsTheSeamOffDevices(unittest.TestCase):

    SEAM = ('js/desktop-app.js', 'css/desktop-app.css', 'DesktopApp', 'desktop_app_templates=1')

    def _render(self, desktop):
        with open(os.path.join(HTML_DIR, 'index.html'), 'r') as fh:
            source = fh.read()

        # Every {{name}} the page substitutes, as TemplateHandler.index() would
        # hand them over; the values do not matter here, only the branches.
        context = dict.fromkeys(re.findall(r'\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}', source), '')
        context.update({
            'version': '1',
            'using_desktop': 'true' if desktop else 'false',
            'using_mod': 'false' if desktop else 'true',
            'desktop_app': desktop,
            'factory_pedalboards': False,
            'codec_truebypass': 'false',
            'preferences': '{}',
            'favorites': '[]',
            'addressing_pages': '[]',
        })
        template = tornado.template.Template(source, name='index.html', autoescape=None)
        return template.generate(**context).decode('utf-8')

    def test_device_page_carries_nothing_of_the_seam(self):
        page = self._render(desktop=False)
        for needle in self.SEAM:
            self.assertNotIn(needle, page)
        self.assertIn('js/templates.js?v=1"', page)
        self.assertIn("enable_dev_mode(true)", page)

    def test_desktop_page_carries_all_of_it(self):
        page = self._render(desktop=True)
        for needle in self.SEAM:
            self.assertIn(needle, page)
        self.assertIn('DesktopApp.setup(desktop)', page)
        self.assertIn('js/templates.js?v=1&desktop_app_templates=1"', page)
        self.assertNotIn("enable_dev_mode(true)", page)


if __name__ == '__main__':
    unittest.main()
