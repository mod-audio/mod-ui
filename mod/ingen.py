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
from ingen_async import NS, Error, ingen_bundle_path, lv2_path, IngenAsync
import os
import rdflib
import socket
import sys

try:
    import StringIO.StringIO as StringIO
except ImportError:
    from io import StringIO as StringIO

class Host(IngenAsync):
    def parse_port(self, port):
        # HACK
        r = port
        if "effect_" in port:
            instance, port = port.split(":")
            instance = instance.replace("effect_", "")
            r = "/instance%s/%s" % (instance, port)
        elif "system" in port:
            if "midi_capture_1" in port:
                r = "/control_in"
            else:
                p = port.split("_")[-1]
                typ = "in"
                if "playback" in port:
                    typ = "out"
                r = "/audio_%s_%s" % (typ, p)
        return r

    def add(self, uri, instance, x, y, callback=lambda r: r):
        self.put("/%s" % instance, """a ingen:Block ;
ingen:prototype <%s> ;
ingen:canvasX %f ;
ingen:canvasY %f
""" % (uri, float(x), float(y)), callback)

    def set_position(self, instance, x, y, callback=lambda r:r):
        self.set("/%s" % instance, "<%s>" % NS.ingen.canvasX, float(x), callback)
        self.set("/%s" % instance, "<%s>" % NS.ingen.canvasY, float(y), callback)

    def param_get(self, instance_id, symbol, callback=lambda result: None):
        callback(1)

    def param_set(self, instance_id, symbol, value, callback=lambda result: None):
        self.set("/instance%d/%s" % (instance_id, symbol), "ingen:value", value, callback)

    def preset_load(self, instance_id, uri, callback=lambda result: None):
        self.set("/instance%d" % instance_id, "<%s>" % NS.presets.preset, "<%s>" % uri, callback)

    def remove(self, instance_id, callback=lambda result: None):
        self.delete("/instance%d" % instance_id, callback)

    def cpu_load(self, callback=lambda r:r):
        callback({'ok': True, 'value': 50})

    def monitor(self, addr, port, status, callback=lambda r:r):
        callback(True)

    def bypass(self, instance, value, callback=lambda r:r):
        callback(True)

    def add_audio_port(self, name, typ, callback=lambda r:r):
        # typ should be Input or Output
        if typ is not "Input" and typ is not "Output":
            callback(False)
            return

        if typ is "Input":
            x = 5.0
        else:
            x = 900.0

        import random
        y = random.randint(50,250)

        self.put("/%s" % name.replace(" ", "_").lower(), """
            <http://drobilla.net/ns/ingen#canvasX> "%f"^^<http://www.w3.org/2001/XMLSchema#float> ;
            <http://drobilla.net/ns/ingen#canvasY> "%f"^^<http://www.w3.org/2001/XMLSchema#float> ;
            <http://lv2plug.in/ns/lv2core#name> "%s" ;
            a <http://lv2plug.in/ns/lv2core#AudioPort> ;
            a <http://lv2plug.in/ns/lv2core#%sPort>""" % (x, y, name, typ), callback)
