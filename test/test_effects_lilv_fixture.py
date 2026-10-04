#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Phase 6 (docs/characterization-phase-6.md) STRETCH GOAL: a minimal
hand-written .lv2 bundle (test/fixtures/phase6-fixture.lv2/ -- manifest.ttl
+ phase6-fixture.ttl, deliberately NO binary/.so file), scanned into its own
lilv world, to pin one real /effect/list entry shape and one real
/effect/get field set -- as opposed to test_effects_lilv.py, which only
exercises an empty world / unknown URIs.

Confirmed: lilv does NOT need the plugin binary to exist on disk for
metadata listing or get_plugin_info(). lilv_world_load_all() only RDF-parses
manifest.ttl and the rdfs:seeAlso'd turtle file; it never dlopen()s
lv2:binary at scan time (only real audio instantiation would). manifest.ttl
here points lv2:binary at "phase6-fixture.so", a file that is never created
anywhere -- the scan and both endpoints below work anyway. So the spec's
"if lilv refuses a binaryless bundle, drop the stretch" escape hatch was not
needed for the *lilv* half of this stretch goal.

THIS FILE MUST BE RUN AS ITS OWN INVOCATION: `pytest -m lilv_fixture`, never
combined with `-m lilv` (test_effects_lilv.py) in the same process, and
never via a marker expression that would pull both in (e.g. do NOT run
`pytest -m "lilv or lilv_fixture"`). This is a hard constraint, not
caution for its own sake -- it is the actual reason the stretch goal ended
up in its own file instead of a second test class inside
test_effects_lilv.py (which is where it lived during development).

What went wrong when it *was* a second class in the same file/process,
reproduced directly: that class's setUpClass copied the fixture bundle into
a fresh directory, repointed LV2_PATH, and called modtools.utils.init() a
SECOND time in the process (the module-scoped `lilv_world` fixture in
test_effects_lilv.py having already called it once for the empty world).
modtools/utils.py init() is a bare ctypes call into utils/utils_lilv.cpp
init() (:3893), which does free the previous LilvWorld and build a new one
-- but it also re-runs `NamespaceDefinitions::getStaticInstance(W).init(W)`
(:3898). getStaticInstance() (~:540) is a process-wide C++ singleton
(function-local `static`), NOT reset or freed between the two init() calls
(cleanup() -- the only code path that calls
`NamespaceDefinitions::...cleanup()` -- is, per the phase-6 spec, never
called in this suite). The result, reproduced directly: the second world's
plugin was found and get_all_plugins()/get_plugin_info() returned it, but
its `ports` and `category` fields were silently empty (`[]`) instead of the
real port/category data -- no exception, no crash at that point, just wrong
data, because the namespace lookups the C++ code uses to classify ports/
categories were resolved against the FIRST (already-freed) world's nodes.
Worse, the process then reliably SIGSEGV'd during native static/global
destructor teardown at interpreter exit (after pytest had already printed
its full PASSED/FAILED summary -- so a naive glance at "tests passed" would
have missed it; `timeout ... ; echo $?` showed "dumped core"). This is
exactly the DANGER-level failure mode the phase-6 spec's NEVER-CALL-LIST
reasoning warns about, just triggered by a second init() instead of a
pre-init call.

The fix applied: this module now calls modtools.utils.init() exactly ONCE,
as the ONLY init() call in its own process, matching the one-call invariant
that makes test_effects_lilv.py itself safe.
"""

import json
import os
import shutil

from base import ModUITestCase

import pytest

pytestmark = pytest.mark.lilv_fixture

_FIXTURE_BUNDLE_SRC = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "fixtures", "phase6-fixture.lv2"
)
_FIXTURE_PLUGIN_URI = "http://example.org/plugins/phase6-fixture"


@pytest.fixture(scope="module", autouse=True)
def lilv_world_with_fixture_bundle():
    from conftest import _TEST_ROOT
    from modtools import utils

    scan_dir = os.path.join(_TEST_ROOT, "lv2-path-fixture-bundle")
    if os.path.isdir(scan_dir):
        shutil.rmtree(scan_dir)
    os.makedirs(scan_dir)
    shutil.copytree(_FIXTURE_BUNDLE_SRC, os.path.join(scan_dir, "phase6-fixture.lv2"))

    # See module docstring: os.environ["LV2_PATH"] is read by lilv itself,
    # inside init(), at call time (test/conftest.py sets an initial empty-dir
    # value for test_effects_lilv.py; here we override it before this
    # module's ONE AND ONLY init() call in this process).
    os.environ["LV2_PATH"] = scan_dir
    utils.init()
    yield
    # No cleanup()/de-init -- same reasoning as test_effects_lilv.py, and
    # moot here since this is the last thing this process ever does.


class TestEffectListWithFixtureBundle(ModUITestCase):
    __test__ = True

    def test_effect_list_contains_fixture_plugin_mini_shape(self):
        response = self.fetch("/effect/list")
        self.assertEqual(response.code, 200)
        plugins = json.loads(response.body.decode("utf-8"))

        by_uri = {p["uri"]: p for p in plugins}
        self.assertIn(_FIXTURE_PLUGIN_URI, by_uri)

        entry = by_uri[_FIXTURE_PLUGIN_URI]
        # Pin the PluginInfo_Mini field set (get_all_plugins), not the full
        # PluginInfo shape (that's EffectGet, checked separately below).
        self.assertEqual(entry["name"], "Phase 6 Fixture")
        self.assertEqual(entry["label"], "Phase 6 Fixture")
        self.assertEqual(entry["category"], ["Utility"])
        self.assertEqual(
            set(entry.keys()),
            {
                "uri", "name", "brand", "label", "comment", "buildEnvironment",
                "category", "microVersion", "minorVersion", "release",
                "builder", "licensed", "iotype", "gui",
            },
        )


class TestEffectGetWithFixtureBundle(ModUITestCase):
    __test__ = True

    def test_effect_get_returns_full_info_for_fixture_plugin(self):
        response = self.fetch("/effect/get?uri=" + _FIXTURE_PLUGIN_URI)
        self.assertEqual(response.code, 200)
        content_type = response.headers.get("Content-Type", "")
        self.assertIn("application/json", content_type)

        data = json.loads(response.body.decode("utf-8"))
        self.assertTrue(data["valid"])
        self.assertEqual(data["uri"], _FIXTURE_PLUGIN_URI)
        self.assertEqual(data["name"], "Phase 6 Fixture")
        # lv2:binary in manifest.ttl points at a .so that was never created
        # on disk -- confirms the binary is not required for full plugin
        # info (only real audio instantiation would need it).
        self.assertEqual(data["binary"], "")
        self.assertEqual(
            [p["symbol"] for p in data["ports"]["audio"]["input"]], ["in"]
        )
        self.assertEqual(
            [p["symbol"] for p in data["ports"]["audio"]["output"]], ["out"]
        )
