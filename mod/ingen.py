#!/usr/bin/env python
# Ingen Python Interface
# Copyright 2012 David Robillard <http://drobilla.net>
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THIS SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

from tornado import iostream, ioloop
from ingen_async import NS, Error, ingen_bundle_path, lv2_path, Host as AsyncHost
import os
import rdflib
import socket
import sys

try:
    import StringIO.StringIO as StringIO
except ImportError:
    from io import StringIO as StringIO

class Host(AsyncHost):
    def parse_port(self, port):
        r = port
        if "effect_" in port:
            instance, port = port.split(":")
            instance = instance.replace("effect_", "")
            r = "/instance%s/%s" % (instance, port)
        elif "system" in port:
            _, port = port.split(":")
            r = "/system_%s" % port
        return r

    def add(self, uri, instance_id, callback=lambda r: r):
        self.put("/instance%d" % instance_id, "a ingen:Block ; ingen:prototype <%s>" % uri, callback)

    def set_position(self, instance_id, x, y, callback=lambda r:r):
        remove = [("<http://drobilla.net/ns/ingen#canvasX>", "patch:wildcard"),
                  ("<http://drobilla.net/ns/ingen#canvasY>", "patch:wildcard")]
        add = [("<http://drobilla.net/ns/ingen#canvasX>", float(x)),
                  ("<http://drobilla.net/ns/ingen#canvasY>", float(y))]
        #self.patch("/instance%d" % instance_id, remove, add, callback)
        self.set("/instance%d" % instance_id, "<http://drobilla.net/ns/ingen#canvasX>", float(x), callback)
        self.set("/instance%d" % instance_id, "<http://drobilla.net/ns/ingen#canvasY>", float(y), callback)

    def connect(self, origin_port, destination_port, callback=lambda r: r):
        self.connecti(self.parse_port(origin_port), self.parse_port(destination_port), callback)

    def disconnect(self, origin_port, destination_port, callback=lambda r: r):
        self.disconnecti(self.parse_port(origin_port), self.parse_port(destination_port), callback)

    def param_set(self, instance_id, symbol, value, callback=lambda result: None):
        self.set("/instance%d/%s" % (instance_id, symbol), "ingen:value", value, callback)

    #def preset_load(self, instance_id, label, callback=lambda result: None):
    #    self.

    def cpu_load(self, callback=lambda r:r):
        callback({'ok': True, 'value': 50})

    def monitor(self, addr, port, status, callback=lambda r:r):
        callback(True)

    def bypass(self, instance, value, callback=lambda r:r):
        callback(True)
