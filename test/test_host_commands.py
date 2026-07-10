#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Characterization tests for the handlers that route into
SESSION.host/SESSION.hmi (mod/webserver.py: EffectConnect, EffectDisconnect,
EffectParameterSet, EffectParameterAddress, DashboardClean, SetBufferSize,
ResetXruns, JackGetMidiDevices, JackSetMidiDevices, TrueBypass,
PedalboardTransportSetSyncMode, PedalboardCvAddressingPluginPortAdd).

Honest caveat: these tests pin the behavior of the mod/webserver.py handler
code under FakeHost/FakeHMI (mod/development.py), NOT the production
mod-host protocol. They are a regression net for webserver.py edits,
nothing more.

CRITICAL, spec-overriding finding: GET /effect/remove/<instance> HANGS (does
not error, does not time out server-side -- the HTTP response is simply
never sent) when <instance> was never registered with SESSION.host.mapper,
which is true of *every* instance name in this sandbox since we cannot call
POST /effect/add (banned -- dereferences the uninitialized global lilv
world, see test/conftest.py NEVER-CALL LIST). Root cause, confirmed by
direct probing with a 4s client-side request_timeout (got HTTP 599 after
the timeout, not a fast response): Host.remove_plugin (mod/host.py:2604,
decorated @gen.coroutine) calls self.mapper.get_id_without_creating(instance)
*before* its own try/except KeyError guard around self.plugins.pop(...). A
nonexistent instance means that lookup itself raises KeyError, which the
@gen.coroutine machinery captures into the returned (never awaited-on)
Future instead of propagating synchronously -- so the handler's
`callback(False)` line is never reached, gen.Task in EffectRemove never
resolves, and the request hangs until the HTTP client's own timeout. This
class does not call GET /effect/remove/* at all; the route has been added to
the test/conftest.py NEVER-CALL LIST with this reasoning.

Every test below that mutates SESSION.host state relies on the autouse
`pedalboards_dir` fixture (test/conftest.py) to call SESSION.reset() before
and after each test method, EXCEPT sync-mode: SESSION.reset() does not touch
SESSION.host.profile, so the sync-mode test explicitly restores the default
("/none") at the end.
"""

import json
import urllib.parse

from base import ModUITestCase


class TestEffectConnectDisconnect(ModUITestCase):
    __test__ = True

    def test_connect_between_system_ports_returns_true_and_is_idempotent(self):
        # "/graph/capture_1" and "/graph/playback_1" are hardware-port
        # shortcuts handled entirely inside Host._fix_host_connection_port
        # (mod/host.py) without touching the plugin mapper, so they are safe
        # "syntactically valid but nonexistent instance" stand-ins per the
        # spec's guidance. FakeHost.send_modified (mod/development.py)
        # invokes its callback immediately with True regardless of whether
        # the ports are real JACK ports -- there is no validation under the
        # fakes.
        response, body = self.fetch_json(
            "/effect/connect/graph/capture_1,/graph/playback_1"
        )
        self.assertEqual(response.code, 200)
        self.assertIs(body, True)

        # Second call: (port_from, port_to) is now already in
        # self.connections, so Host.connect short-circuits to callback(True)
        # without going through send_modified again -- still True.
        response2, body2 = self.fetch_json(
            "/effect/connect/graph/capture_1,/graph/playback_1"
        )
        self.assertEqual(response2.code, 200)
        self.assertIs(body2, True)

        # Clean up: disconnect so SESSION.host.connections is restored to
        # empty (belt-and-braces -- the autouse fixture would clear it too).
        response3, body3 = self.fetch_json(
            "/effect/disconnect/graph/capture_1,/graph/playback_1"
        )
        self.assertEqual(response3.code, 200)
        self.assertIs(body3, True)

    def test_disconnect_with_no_active_connections_returns_true(self):
        # Spec guessed this might be `false`. Observed: Host.disconnect's
        # inner host_callback(ok) *always* calls callback(True) regardless
        # of ok (mod/host.py:3422-3436, "always return true" per its own
        # comment) -- even the len(self.connections) == 0 short-circuit
        # path (host_callback(False)) ends up reporting True to the client.
        response, body = self.fetch_json(
            "/effect/disconnect/graph/capture_1,/graph/playback_1"
        )
        self.assertEqual(response.code, 200)
        self.assertIs(body, True)


class TestEffectParameterSet(ModUITestCase):
    __test__ = True

    def test_parameter_set_short_circuits_true_when_hmi_uninitialized(self):
        # FakeHMI.initialized is always False (mod/development.py), so
        # EffectParameterSet.post's `if not SESSION.hmi.initialized:
        # self.write(True); return` guard fires before the request body is
        # even parsed -- an empty body is fine.
        response, body = self.fetch_json(
            "/effect/parameter/set/", method="POST", body=b""
        )
        self.assertEqual(response.code, 200)
        self.assertIs(body, True)


class TestEffectParameterAddress(ModUITestCase):
    __test__ = True

    def test_address_nonexistent_instance_returns_false(self):
        # Unlike EffectRemove, Host.address (mod/host.py:4795) uses
        # self.mapper.get_id(instance) -- the *creating* variant, which
        # never raises -- so a never-seen instance safely resolves to
        # pluginData is None and callback(False) fires synchronously.
        body_json = json.dumps(
            {"uri": "https://example.org/actuator", "minimum": 0, "maximum": 1, "value": 0.5}
        ).encode("utf-8")
        response, body = self.fetch_json(
            "/effect/parameter/address/graph/nonexistent/gain",
            method="POST",
            body=body_json,
        )
        self.assertEqual(response.code, 200)
        self.assertIs(body, False)

    def test_address_missing_uri_is_404(self):
        # EffectParameterAddress.post checks `data.get('uri', None) is
        # None` before anything else and raises web.HTTPError(404).
        response = self.fetch(
            "/effect/parameter/address/graph/nonexistent/gain",
            method="POST",
            body=b"{}",
        )
        self.assertEqual(response.code, 404)


class TestReset(ModUITestCase):
    __test__ = True

    def test_reset_returns_true(self):
        # SESSION.reset under FakeHMI (never initialized) takes the
        # synchronous reset_host(True) branch straight to Host.reset, and
        # FakeHost invokes every send_notmodified callback immediately with
        # True.
        response, body = self.fetch_json("/reset/")
        self.assertEqual(response.code, 200)
        self.assertIs(body, True)


class TestSetBufferSize(ModUITestCase):
    __test__ = True

    def test_128_and_256_return_ok_false_size_zero(self):
        # Matches the spec's own prediction: under MOD_DEV_ENVIRONMENT,
        # IMAGE_VERSION is None so the /data/jack-buffer-size write is
        # skipped, and set_jack_buffer_size (utils/utils_jack.cpp) is a
        # null-guarded no-op that returns 0 without a JACK client -- so
        # newsize (0) never equals the requested size, and 'ok' is always
        # False.
        for size in ("128", "256"):
            response, body = self.fetch_json(
                "/set_buffersize/%s" % size, method="POST", body=b""
            )
            self.assertEqual(response.code, 200)
            self.assertEqual(body, {"ok": False, "size": 0})


class TestResetXruns(ModUITestCase):
    __test__ = True

    def test_reset_xruns_returns_true(self):
        response, body = self.fetch_json("/reset_xruns/", method="POST", body=b"")
        self.assertEqual(response.code, 200)
        self.assertIs(body, True)


class TestJackMidiDevices(ModUITestCase):
    __test__ = True

    def test_get_midi_devices_shape_under_fake_host(self):
        # No JACK client -> Host.get_midi_ports() (backing
        # web_get_midi_device_list) reports no devices; midiAggregatedMode
        # defaults to True (mod/host.py:368, Host.__init__).
        response, body = self.fetch_json("/jack/get_midi_devices")
        self.assertEqual(response.code, 200)
        self.assertEqual(
            body,
            {
                "devsInUse": [],
                "devList": [],
                "names": {},
                "midiAggregatedMode": True,
            },
        )

    def test_set_midi_devices_matching_current_state_is_a_true_noop(self):
        # devs=[], midiAggregatedMode=True, midiLoopback=False exactly match
        # Host.__init__'s defaults (mod/host.py:368-369), so both the
        # "mode changed" and "loopback changed" branches inside
        # Host.set_midi_devices are skipped -- a side-effect-free call that
        # still returns True (the handler always writes True on success).
        body_json = json.dumps(
            {"devs": [], "midiAggregatedMode": True, "midiLoopback": False}
        ).encode("utf-8")
        response, body = self.fetch_json(
            "/jack/set_midi_devices", method="POST", body=body_json
        )
        self.assertEqual(response.code, 200)
        self.assertIs(body, True)

    def test_set_midi_devices_missing_key_is_500(self):
        # Spec guessed "echo/true -- observe". Observed: JackSetMidiDevices
        # .post does three unguarded dict subscripts (data['devs'],
        # data['midiAggregatedMode'], data['midiLoopback']) with no
        # try/except -- a body missing any of them raises an uncaught
        # KeyError before any yield, which tornado turns into a plain 500,
        # not a JSON error shape.
        body_json = json.dumps({"devs": []}).encode("utf-8")
        response = self.fetch(
            "/jack/set_midi_devices", method="POST", body=body_json
        )
        self.assertEqual(response.code, 500)


class TestTrueBypass(ModUITestCase):
    __test__ = True

    def test_truebypass_returns_false_under_fake_jack(self):
        # Matches the spec's own guess. set_truebypass_value (utils_jack)
        # is null-guarded without a JACK client and its C-side setter
        # reports failure, so the handler always writes False under the
        # fakes, both channels, both requested states.
        response, body = self.fetch_json("/truebypass/Left/true")
        self.assertEqual(response.code, 200)
        self.assertIs(body, False)

        response2, body2 = self.fetch_json("/truebypass/Right/false")
        self.assertEqual(response2.code, 200)
        self.assertIs(body2, False)


class TestTransportSetSyncMode(ModUITestCase):
    __test__ = True

    def test_known_modes_return_true_then_restore_default(self):
        # SESSION.reset() does NOT touch SESSION.host.profile, so this test
        # explicitly restores the "/none" (internal/default) mode at the
        # end to avoid leaking Profile state into later tests.
        try:
            for mode in ("/none", "/midi_clock_slave", "/link"):
                response, body = self.fetch_json(
                    "/pedalboard/transport/set_sync_mode%s" % mode,
                    method="POST",
                    body=b"",
                )
                self.assertEqual(response.code, 200)
                self.assertIs(body, True)
        finally:
            self.fetch_json(
                "/pedalboard/transport/set_sync_mode/none", method="POST", body=b""
            )

    def test_invalid_mode_returns_false_not_error(self):
        response, body = self.fetch_json(
            "/pedalboard/transport/set_sync_mode/bogus", method="POST", body=b""
        )
        self.assertEqual(response.code, 200)
        self.assertIs(body, False)


class TestCVAddressingPluginPortAdd(ModUITestCase):
    __test__ = True

    def test_add_500s_without_an_existing_addressed_plugin_instance(self):
        # Spec said "observe". Observed: PedalboardCvAddressingPluginPortAdd
        # calls SESSION.web_cv_addressing_plugin_port_add synchronously
        # (not yielded), which ends up in
        # Host.addr_task_get_plugin_cv_port_op_mode (mod/host.py:970),
        # which does self.mapper.get_id_without_creating(instance) on the
        # instance embedded in the uri. Since no plugin instance can exist
        # in this sandbox (POST /effect/add is banned -- see
        # test/conftest.py NEVER-CALL LIST), this *always* raises KeyError
        # and always 500s -- there is no well-formed uri that succeeds here
        # without lilv. Unlike EffectRemove this is NOT a hang: the
        # exception is raised synchronously (no @gen.coroutine boundary
        # swallows it), so tornado's normal error path returns a fast 500.
        body = urllib.parse.urlencode(
            {"uri": "/cv/graph/nonexistent/cvout", "name": "test"}
        )
        response = self.fetch(
            "/pedalboard/cv_addressing_plugin_port/add", method="POST", body=body
        )
        self.assertEqual(response.code, 500)
