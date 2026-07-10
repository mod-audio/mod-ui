#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Characterization tests for the /websocket connect-time handshake
(mod/webserver.py:ServerWebSocket, mod/session.py:Session.websocket_opened,
mod/host.py:Host.report_current_state -- all wired through
mod/development.py:FakeHost.open_connection_if_needed in this dev harness).

Pins the message-PUSH sequence a client sees right after connecting: this is
the ``msg_callback`` broadcast path a future Tone3000 "file added" push
notification would ride.

Exploratory findings (see docs/characterization-phase-5.md, verified against
this sandbox -- FakeHMI uninitialized, empty pedalboard, no CC devices, no
hardware ports, /proc/meminfo present so Host.memtimer is armed):

- The connect-time push on the FIRST socket of the process is exactly 7
  ordered messages, by PREFIX (first whitespace-delimited word):
      sys_stats, stats, transport, truebypass, loading_start, size, loading_end
  The spec's sketch guessed a "stop"/ready-ish closing token; the real
  ready-marker is ``loading_end <snapshot_id>``
  (mod/host.py:Host.report_current_state, last line before the per-plugin
  addressing/HW sections, which are all empty in this sandbox).
- Immediately AFTER that 7-message burst, the first socket receives one
  EXTRA ``sys_stats ...`` message. This is not part of
  report_current_state's own push -- it is
  FakeHost.open_connection_if_needed (mod/development.py) calling
  ``self.memtimer_callback()`` synchronously, once, right after
  ``report_current_state()`` returns, on the branch where
  ``self.readsock``/``self.writesock`` were previously None (i.e. only for
  the connection that actually "establishes" the fake host link). This is a
  detail the spec's sketch did not anticipate; tests below treat it as an
  unpinned trailing message (present in practice in this sandbox, but not
  asserted on) rather than pin an exact total message count, per the phase's
  "pin prefixes/arg-counts, not volatile detail" and "consume/ignore extra
  stats messages" guidance.
- A SECOND, concurrent connection (opened while the first is still open)
  gets the exact same 7-message report_current_state burst (every new
  websocket gets its own full state dump -- Session.websocket_opened's
  first-vs-not-first branch, session.py:236, only decides whether
  Host.start_session runs first; it does not change what gets pushed to the
  new socket). The observable difference is narrower than "first socket
  session branch": it is FakeHost.open_connection_if_needed's *own* branch
  on ``self.readsock is not None and self.writesock is not None`` -- true
  for every connection after the first -- which skips
  statstimer.start()/memtimer_callback() entirely. So only the very first
  socket of the process gets the extra trailing sys_stats; the second socket
  does not, even though both get an identical initial 7-message burst.
- PeriodicCallback (mod/host.py Host.statstimer/memtimer) binds
  ``IOLoop.current()`` at construction time (tornado 4.3
  ioloop.py:PeriodicCallback.__init__), and SESSION.host is a process-level
  singleton constructed at ``mod.webserver`` import time -- before any
  per-test IOLoop exists. So ``statstimer.start()``/``memtimer.start()``
  schedule ticks on a *different*, never-pumped IOLoop; in practice no
  additional "stats ..."/"sys_stats ..." messages arrive during a test's own
  ~2s collection window. Tests still avoid asserting exact trailing counts,
  since this is an artifact of import ordering, not a documented guarantee.
- Closing the client side of the connection is NOT synchronously reflected
  server-side: right after ``conn.close()`` returns, GET /hello still
  reports ``online: true`` (SESSION.websockets still has the entry) because
  ``ServerWebSocket.on_close`` -> ``SESSION.websocket_closed`` only runs
  once the server's IOLoop actually polls and processes the close frame.
  This turned out FLAKY to observe deterministically: a bounded number of
  ``gen.moment`` spins (pure callback-queue turns, no real I/O wait) is
  sometimes enough and sometimes not. Per the phase spec's own guidance
  ("count may update asynchronously; drop the assertion rather than
  sleep-loop if flaky"), the close test below does not assert on the
  post-close ``online`` value -- it only pins that the server tolerates the
  close without erroring and keeps answering HTTP requests.
"""

from tornado import gen, websocket
from tornado.testing import gen_test

from base import ModUITestCase

# Generous but bounded -- nothing here should ever legitimately take this
# long; a real hang (behavior regression) fails fast instead of hanging the
# whole suite.
_READ_TIMEOUT = 5.0

# Exact pinned prefix sequence of the connect-time report_current_state
# burst in this sandbox (empty pedalboard, no CC devices, no HW ports).
_EXPECTED_PREFIXES = [
    "sys_stats",
    "stats",
    "transport",
    "truebypass",
    "loading_start",
    "size",
    "loading_end",
]

_READY_MARKER_PREFIX = "loading_end"


class WebSocketTestCase(ModUITestCase):
    """Shared helpers. Not collected directly (__test__ stays False)."""

    __test__ = False

    def ws_url(self):
        return self.get_url("/websocket").replace("http://", "ws://")

    @gen.coroutine
    def read_one(self, conn, timeout=_READ_TIMEOUT):
        """Read a single message with a hard timeout so a behavior change
        (e.g. the ready marker disappearing) fails fast instead of hanging.
        """
        msg = yield gen.with_timeout(self.io_loop.time() + timeout, conn.read_message())
        raise gen.Return(msg)

    @gen.coroutine
    def drain_until_ready(self, conn, timeout=_READ_TIMEOUT):
        """Collect messages up to and including the ready marker
        (``loading_end ...``). Returns the list of messages, ready marker
        included. Raises (via with_timeout / assertion) if the marker never
        arrives or the socket closes first.
        """
        messages = []
        while True:
            msg = yield self.read_one(conn, timeout=timeout)
            if msg is None:
                self.fail(
                    "server closed the websocket before the ready marker "
                    "(%r) arrived; messages so far: %r"
                    % (_READY_MARKER_PREFIX, messages)
                )
            messages.append(msg)
            if msg.split(" ", 1)[0] == _READY_MARKER_PREFIX:
                break
        raise gen.Return(messages)


class TestWebSocketConnectSequence(WebSocketTestCase):
    __test__ = True

    @gen_test(timeout=10)
    def test_connect_pushes_pinned_prefix_sequence(self):
        conn = yield websocket.websocket_connect(self.ws_url())
        try:
            messages = yield self.drain_until_ready(conn)
            prefixes = [m.split(" ", 1)[0] for m in messages]
            self.assertEqual(prefixes, _EXPECTED_PREFIXES)
        finally:
            conn.close()

    @gen_test(timeout=10)
    def test_transport_message_shape(self):
        conn = yield websocket.websocket_connect(self.ws_url())
        try:
            messages = yield self.drain_until_ready(conn)
            transport_msgs = [m for m in messages if m.split(" ", 1)[0] == "transport"]
            self.assertEqual(len(transport_msgs), 1)

            parts = transport_msgs[0].split(" ")
            # "transport %i %f %f %s" -- prefix + 4 fields.
            self.assertEqual(len(parts), 5)
            rolling, bpb, bpm, sync = parts[1:]

            # arg-count + parseability is the load-bearing assertion; the
            # concrete defaults below are deterministic Profile() config
            # (not volatile like cpu%/timestamps), so pinning them is safe
            # in this fresh-sandbox harness.
            self.assertEqual(int(rolling), 0)
            self.assertEqual(float(bpb), 4.0)
            self.assertEqual(float(bpm), 120.0)
            self.assertEqual(sync, "none")
        finally:
            conn.close()

    @gen_test(timeout=10)
    def test_truebypass_message_reflects_defaults(self):
        conn = yield websocket.websocket_connect(self.ws_url())
        try:
            messages = yield self.drain_until_ready(conn)
            tb_msgs = [m for m in messages if m.split(" ", 1)[0] == "truebypass"]
            self.assertEqual(len(tb_msgs), 1)

            parts = tb_msgs[0].split(" ")
            # "truebypass %i %i" -- prefix + 2 fields.
            self.assertEqual(len(parts), 3)
            left, right = int(parts[1]), int(parts[2])
            # Observed default (Host.last_true_bypass_left/right initial
            # state in this dev sandbox): both channels report "true bypass
            # on".
            self.assertEqual((left, right), (1, 1))
        finally:
            conn.close()

    @gen_test(timeout=10)
    def test_size_message_present_with_two_numeric_args(self):
        conn = yield websocket.websocket_connect(self.ws_url())
        try:
            messages = yield self.drain_until_ready(conn)
            size_msgs = [m for m in messages if m.split(" ", 1)[0] == "size"]
            self.assertEqual(len(size_msgs), 1)

            parts = size_msgs[0].split(" ")
            # "size %d %d" -- prefix + 2 fields.
            self.assertEqual(len(parts), 3)
            width, height = int(parts[1]), int(parts[2])
            # Empty/default pedalboard in a fresh sandbox -> zero size.
            self.assertEqual((width, height), (0, 0))
        finally:
            conn.close()

    @gen_test(timeout=10)
    def test_second_concurrent_connection_gets_full_burst_but_no_trailing_extra(self):
        conn1 = yield websocket.websocket_connect(self.ws_url())
        try:
            messages1 = yield self.drain_until_ready(conn1)
            prefixes1 = [m.split(" ", 1)[0] for m in messages1]
            self.assertEqual(prefixes1, _EXPECTED_PREFIXES)

            # The first socket also gets one extra trailing sys_stats
            # (FakeHost.open_connection_if_needed's memtimer_callback()
            # kick, see module docstring). Consume it so it can't bleed
            # into the second connection's read below; don't fail if it
            # doesn't show up (it is an unpinned, environment-dependent
            # detail).
            try:
                extra = yield self.read_one(conn1, timeout=1.0)
                if extra is not None:
                    self.assertEqual(extra.split(" ", 1)[0], "sys_stats")
            except gen.TimeoutError:
                pass

            # Second connection, opened while the first is still open --
            # exercises Session.websocket_opened's "not the first socket"
            # branch (session.py:236).
            conn2 = yield websocket.websocket_connect(self.ws_url())
            try:
                messages2 = yield self.drain_until_ready(conn2)
                prefixes2 = [m.split(" ", 1)[0] for m in messages2]
                # Same full report_current_state burst as the first socket.
                self.assertEqual(prefixes2, _EXPECTED_PREFIXES)

                # But NOT the extra trailing sys_stats: FakeHost's
                # readsock/writesock are already set by the time the second
                # socket connects, so open_connection_if_needed takes the
                # early-return branch (report_current_state only, no
                # statstimer/memtimer kick).
                with self.assertRaises(gen.TimeoutError):
                    yield self.read_one(conn2, timeout=1.0)
            finally:
                conn2.close()
        finally:
            conn1.close()


class TestWebSocketClose(WebSocketTestCase):
    __test__ = True

    @gen_test(timeout=10)
    def test_clean_close_no_server_error_and_hello_reflects_it(self):
        conn = yield websocket.websocket_connect(self.ws_url())
        yield self.drain_until_ready(conn)

        response = yield self.http_client.fetch(self.get_url("/hello/"))
        self.assertEqual(response.code, 200)
        self.assertIn(b'"online": true', response.body)

        conn.close()

        # DROPPED (per phase-5 spec §6: "count may update asynchronously;
        # drop the assertion rather than sleep-loop if flaky"): a strict
        # assertion that /hello's `online` flips to false shortly after
        # close. websocket_closed (session.py) only runs once the server's
        # IOLoop actually polls and processes the close frame -- draining a
        # bounded number of `gen.moment`s (pure callback-queue turns, no
        # real I/O wait) was NOT enough to observe it in this harness
        # (confirmed flaky: failed after 10 moments in a run where the
        # exploratory script's 5-moments-after-two-fetches version happened
        # to see it flip). A real wait would require an actual sleep/poll,
        # which the spec explicitly says not to add. So this test only pins
        # what's reliable: the server tolerates a client-initiated close
        # without erroring, and a subsequent HTTP request still succeeds
        # (well-formed JSON, 200) -- it does not assert on the `online`
        # value after close.
        response = yield self.http_client.fetch(self.get_url("/hello/"))
        self.assertEqual(response.code, 200)
        self.assertIn(b'"online"', response.body)
