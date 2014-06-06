# -*- coding: utf-8 -*-

# Copyright 2012-2013 AGR Audio, Industria e Comercio LTDA. <contato@portalmod.com>
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

"""
This module works as an interface for mod-host, it uses a socket to communicate
with mod-host, the protocol is described in <http://github.com/portalmod/mod-host>

The module relies on tornado.ioloop stuff, but you need to start the ioloop
by yourself:

>>> from tornado import ioloop
>>> ioloop.IOLoop.instance().start()

This will start the mainloop and will handle the callbacks and the async functions
"""

from tornado import iostream, ioloop

from mod.protocol import ProtocolError, process_resp

import socket, logging

class Host(object):
    def __init__(self, port, address="localhost", callback=lambda:None):
        self.port = port
        self.address = address
        self.queue = []
        self.latest_callback = None
        self.open_connection(callback)

    def open_connection(self, callback=None):
        self.socket_idle = False

        if (self.latest_callback):
            # There's a connection waiting, let's just send an error
            # for it to finish properly
            try:
                self.latest_callback('finish\xe3')
            except Exception, e:
                logging.warn("[host] latest callback failed: %s" % str(e))

        self.latest_callback = None

        def check_response():
            if callback is not None:
                callback()
            if len(self.queue):
                self.process_queue()
            else:
                self.socket_idle = True
            #self.setup_monitor()

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s = iostream.IOStream(s)
        self.s.set_close_callback(self.open_connection)

        ioloop.IOLoop.instance().add_callback(lambda: self.s.connect((self.address, self.port), check_response))

    def send(self, msg, callback, datatype='int'):
        self.queue.append((msg, callback, datatype))
        if self.socket_idle:
            self.process_queue()

    def process_queue(self):
        try:
            msg, callback, datatype = self.queue.pop(0)
            logging.info("[host] popped from queue: %s" % msg)
        except IndexError:
            self.socket_idle = True
            return

        def check_response(resp):
            logging.info("[host] received <- %s" % repr(resp))
            if not resp.startswith("resp"):
                logging.error("[host] protocol error: %s" % ProtocolError(resp)) # TODO: proper error handling

            r = resp.replace("resp ", "").replace("\xe3", "").strip()
            callback(process_resp(r, datatype))
            self.process_queue()

        self.socket_idle = False
        logging.info("[host] sending -> %s" % msg)

        self.s.write('%s\xe3' % str(msg))
        self.s.read_until('\xe3', check_response)

        self.latest_callback = check_response

    def add(self, uri, instance_id, callback=lambda result: None):
        self.send("add %s %d" % (uri, instance_id), callback)

    def remove(self, instance_id, callback=lambda result: None):
        self.send("remove %d" % instance_id, callback, datatype='boolean')

    def connect(self, origin_port, destination_port, callback=lambda result: None):
        self.send("connect %s %s" % (origin_port, destination_port), callback, datatype='boolean')

    def disconnect(self, origin_port, destination_port, callback=lambda result: None):
        self.send("disconnect %s %s" % (origin_port, destination_port), callback, datatype='boolean')

    def param_set(self, instance_id, symbol, value, callback=lambda result: None):
        self.send("param_set %d %s %f" % (instance_id, symbol, value), callback, datatype='boolean')

    def param_get(self, instance_id, symbol, callback=lambda result: None):
        self.send("param_get %d %s" % (instance_id, symbol), callback, datatype='float_structure')

    def param_monitor(self, instance_id, symbol, op, value, callback=lambda result: None):
        self.send("param_monitor %d %s %s %f" % (instance_id, symbol, op, value), callback, datatype='boolean')

    def monitor(self, addr, port, status, callback=lambda result: None):
        self.send("monitor %s %d %d" % (addr, port, status), callback, datatype='boolean')

    def bypass(self, instance_id, value, callback=lambda result: None):
        self.send("bypass %d %d" % (instance_id, value), callback, datatype='boolean')
