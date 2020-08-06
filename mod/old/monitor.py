# -*- coding: utf-8 -*-

# Copyright 2012-2013 AGR Audio, Industria e Comercio LTDA. <contato@moddevices.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import socket

try:
    from tornado.tcpserver import TCPServer
except ImportError:
    # tornado 2.x
    from tornado.netutil import TCPServer

from mod.settings import TUNER

class MonitorServer(TCPServer):

    def _process_msg(self, msg):
        from mod.session import SESSION

        try:
            cmd, instance, port, value =  msg.replace("\x00", "").split()
            assert cmd == "monitor"
            instance = int(instance)
            value = float(value)
        except (ValueError, AssertionError) as e:
            # TODO: tratar error
            pass
        else:
            if instance == TUNER:
                SESSION.tuner(value)
        self._handle_conn()

    def handle_stream(self, s, addr):
        self._stream = s
        self._handle_conn()

    def _handle_conn(self):
        self._stream.read_until("\x00", self._process_msg)
