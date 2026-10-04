#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Characterization tests for the /effect/* plugin-info handlers
(mod/webserver.py: EffectList, EffectGet, EffectGetNonCached, EffectBulk,
EffectAdd) that dereference the global lilv world (utils/utils_lilv.cpp
W/PLUGINS, initialized by modtools.utils.init()).

Phase 6 (docs/characterization-phase-6.md): this whole module is the
controlled, opt-in exception to the test/conftest.py NEVER-CALL LIST entry
for these exact routes. Every test here runs against an EMPTY lilv world
(LV2_PATH pointed at a dedicated empty sandbox dir in test/conftest.py) --
no real plugin is ever scanned, so every URI used below is, from lilv's
point of view, unknown/nonexistent.

Opt-in via the `lilv` pytest marker (see pytest.ini): `pytestmark` below
marks every test in this module, and pytest.ini's `addopts = -m "not lilv"`
excludes the whole module from the default `pytest` run. Run explicitly with
`pytest -m lilv`.

modtools.utils.init() is the exact function mod/webserver.py's lv2_init()
(aliased import at webserver.py:52, called inside prepare() at :2451) calls
-- confirmed by reading modtools/utils.py's init() (:708), which is a bare
`utils.init()` ctypes call into utils/utils_lilv.cpp init() (:3893:
lilv_world_free + lilv_world_new + lilv_world_load_all + namespace setup,
no JACK calls). This fixture calls the same modtools.utils.init(), skipping
the rest of webserver.prepare() (HMI/host/JACK setup), matching the spec's
guidance to call the same underlying function without the surrounding
production bootstrap.

No de-init: modtools.utils.cleanup() exists but is deliberately not called
here -- it frees the global lilv world (W = nullptr), and any other test
process code that runs after it (including non-lilv tests, if ever run in
the same process) would then be back to square one, NULL-W, for any /effect/*
call. Leaving the world initialized-but-empty for the rest of the process
is the safer of two bad options and is exactly why this suite keeps these
tests opt-in/marker-gated rather than trying to isolate them automatically.

The stretch-goal hand-written-.lv2-bundle tests (docs/characterization-
phase-6.md) live in a SEPARATE file, test/test_effects_lilv_fixture.py,
under a SEPARATE marker (`lilv_fixture`), run as its own invocation
(`pytest -m lilv_fixture`) -- NEVER combined in the same process as this
module's `lilv_world` fixture. Reason (load-bearing finding, see that
file's docstring): modtools.utils.init() is safe to call once per process,
but calling it a SECOND time (e.g. to reload with a bundle present) does
not correctly reset lilv's NamespaceDefinitions::getStaticInstance()
singleton (utils/utils_lilv.cpp ~:540), which is a process-global object
independent of the LilvWorld it was last init()ed with. A second init()
call left get_plugin_info()'s ports/category silently empty (instead of
the real data) and reliably crashed the interpreter on process exit
(SIGSEGV during native static/global teardown) -- confirmed by direct
reproduction, not a guess. One init() per process is a hard constraint of
this C extension as used here.
"""

import json

from base import ModUITestCase

import pytest

pytestmark = pytest.mark.lilv


@pytest.fixture(scope="module", autouse=True)
def lilv_world():
    from modtools import utils
    utils.init()
    yield
    # Deliberately no cleanup()/de-init -- see module docstring.


class TestEffectList(ModUITestCase):
    __test__ = True

    def test_empty_world_returns_empty_list(self):
        response = self.fetch("/effect/list")
        self.assertEqual(response.code, 200)
        content_type = response.headers.get("Content-Type", "")
        self.assertIn("application/json", content_type)
        self.assertEqual(json.loads(response.body.decode("utf-8")), [])


class TestEffectGet(ModUITestCase):
    __test__ = True

    def test_unknown_uri_is_404(self):
        # get_plugin_info() (modtools/utils.py) raises when the C lookup
        # returns NULL for an unknown URI; EffectGet's bare `except:` around
        # it turns that into web.HTTPError(404). CachedJsonRequestHandler
        # does not override write_error, so this is tornado's default HTML
        # error page, NOT a JSON body -- unlike every other handler in this
        # suite, do not decode this response as JSON.
        response = self.fetch("/effect/get?uri=urn:nonexistent")
        self.assertEqual(response.code, 404)


class TestEffectGetNonCached(ModUITestCase):
    __test__ = True

    def test_unknown_uri_is_404(self):
        # Same shape as EffectGet: get_non_cached_plugin_info() raises for
        # an unknown URI, caught by the handler's bare `except:`, re-raised
        # as web.HTTPError(404) -> tornado's default HTML error page.
        response = self.fetch("/effect/get_non_cached?uri=urn:nonexistent")
        self.assertEqual(response.code, 404)


class TestEffectBulk(ModUITestCase):
    __test__ = True

    def _post_bulk(self, uris):
        return self.fetch(
            "/effect/bulk/",
            method="POST",
            headers={"Content-Type": "application/json"},
            body=json.dumps(uris),
        )

    def test_empty_list_returns_empty_object(self):
        response = self._post_bulk([])
        self.assertEqual(response.code, 200)
        content_type = response.headers.get("Content-Type", "")
        self.assertIn("application/json", content_type)
        self.assertEqual(json.loads(response.body.decode("utf-8")), {})

    def test_unknown_uris_are_silently_skipped(self):
        # EffectBulk.post() calls get_plugin_info(uri) per URI inside a bare
        # try/except that `continue`s on failure -- an unknown URI simply
        # never makes it into the result dict, no error surfaced at all.
        response = self._post_bulk(["urn:nonexistent-1", "urn:nonexistent-2"])
        self.assertEqual(response.code, 200)
        self.assertEqual(json.loads(response.body.decode("utf-8")), {})

    def test_missing_content_type_is_501(self):
        # EffectBulk.prepare() requires "application/json" in Content-Type,
        # else raises web.HTTPError(501) before post() ever runs.
        response = self.fetch("/effect/bulk/", method="POST", body=json.dumps([]))
        self.assertEqual(response.code, 501)


class TestEffectAdd(ModUITestCase):
    __test__ = True

    def test_unknown_uri_ends_in_404_not_false(self):
        # SPEC DEVIATION (docs/characterization-phase-6.md guessed "false?"):
        # observed behavior is HTTP 404, not a JSON `false` body. Traced:
        #   1. EffectAdd.get() does `ok = yield gen.Task(SESSION.web_add, ...)`.
        #   2. web_add -> Host.add_plugin -> FakeHost.send_modified(msg, host_callback)
        #      (mod/development.py) calls host_callback(True) unconditionally
        #      and synchronously -- no real mod-host round trip.
        #   3. Inside add_plugin's host_callback, `resp` is `True`; the guard
        #      is `if resp < 0`, and `True < 0` is False in Python, so it does
        #      NOT bail out early despite the URI being unknown.
        #   4. It then calls get_plugin_info_essentials(uri) (modtools/utils.py),
        #      which is NULL-safe: an unknown URI returns a defaults dict
        #      (`{'error': True, 'controlInputs': [], ...}`) instead of
        #      raising. So add_plugin finishes normally, registers a fake
        #      plugin instance in SESSION.host.plugins, and calls
        #      callback(True) -- i.e. `ok` is True back in EffectAdd.get().
        #   5. Because ok is truthy, EffectAdd.get() proceeds to
        #      `data = get_plugin_info(uri)` (NOT get_plugin_info_essentials)
        #      -- this one DOES raise for an unknown URI (see TestEffectGet
        #      above), caught by EffectAdd's own bare `except:`, which raises
        #      web.HTTPError(404).
        # Net effect: an unknown-URI add is NOT rejected up front; it silently
        # registers bookkeeping state on SESSION.host before failing late,
        # with a 404 (tornado's default HTML error page) as the only visible
        # signal to the caller -- no JSON, no `false`.
        response = self.fetch(
            "/effect/add/lilv_phase6_unknown?uri=urn:nonexistent&x=0&y=0"
        )
        self.assertEqual(response.code, 404)
