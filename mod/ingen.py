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
from mod.ingen_async import NS, Error, ingen_bundle_path, lv2_path, IngenAsync
import os
import rdflib
import socket
import sys

try:
    import StringIO.StringIO as StringIO
except ImportError:
    from io import StringIO as StringIO

class Host(IngenAsync):
    def initial_setup(self, callback=lambda r:r):
        self.set("/graph", "<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>", "<http://moddevices.com/ns/modpedal#Pedalboard>", callback)
        self.set("/graph", "<http://moddevices.com/ns/modpedal#screenshot>", "<ingen:/screenshot.png>", callback)
        self.set("/graph", "<http://moddevices.com/ns/modpedal#thumbnail>", "<ingen:/thumbnail.png>", callback)

    def load(self, bundlepath, callback=lambda r:r):
        self.copy("file://%s" % bundlepath, "/graph", callback)

    def save(self, bundlepath, callback=lambda r:r):
        self.copy("/graph", "file://%s" % bundlepath, callback)

    def set_pedalboard_name(self, name, callback=lambda r:r):
        self.set("/graph", "doap:name", '"%s"' % name.replace('"','\\"'), callback)

    def set_pedalboard_size(self, width, height, callback=lambda r:r):
        self.set("/graph", "<http://moddevices.com/ns/modpedal#width>", width, callback)
        self.set("/graph", "<http://moddevices.com/ns/modpedal#height>", height, callback)

    def set_position(self, instance, x, y, callback=lambda r:r):
        self.set(instance, "<%s>" % NS.ingen.canvasX, float(x), callback)
        self.set(instance, "<%s>" % NS.ingen.canvasY, float(y), callback)

    def param_get(self, port, callback=lambda r:r):
        callback(1)

    def param_set(self, port, value, callback=lambda r:r):
        self.set(port, "ingen:value", value, callback)

    def preset_load(self, instance, uri, callback=lambda r:r):
        self.set(instance, "<%s>" % NS.presets.preset, "<%s>" % uri, callback)

    def remove(self, instance, callback=lambda r:r):
        self.delete(instance, callback)

    def cpu_load(self, callback=lambda r:r):
        callback({'ok': True, 'value': 50})

    def monitor(self, addr, port, status, callback=lambda r:r):
        callback(True)

    def bypass(self, instance, value, callback=lambda r:r):
        value = "true" if value == 0 else "false"
        self.set(instance, "ingen:enabled", value, callback)

    def add_external_port(self, name, mode, typ, callback=lambda r:r):
        # mode should be Input or Output
        if mode not in ("Input", "Output"):
            callback(False)
            return

        # type should be Audio, CV or MIDI
        if typ not in ("Audio", "CV", "MIDI"):
            callback(False)
            return

        from random import randint
        x = 5.0 if mode == "Input" else 2300.0
        y = randint(50,250)

        if typ == "MIDI":
            portyp = "<http://lv2plug.in/ns/ext/atom#AtomPort>"
            extra  = """
            <http://lv2plug.in/ns/ext/atom#bufferType> <http://lv2plug.in/ns/ext/atom#Sequence> ;
            <http://lv2plug.in/ns/ext/atom#supports> <http://lv2plug.in/ns/ext/midi#MidiEvent> ;
            """
        elif typ == "CV":
            portyp = "<http://lv2plug.in/ns/lv2core#CVPort>"
            extra  = ""
        else:
            portyp = "<http://lv2plug.in/ns/lv2core#AudioPort>"
            extra  = ""

        msg = """
        <http://drobilla.net/ns/ingen#canvasX> "%f"^^<http://www.w3.org/2001/XMLSchema#float> ;
        <http://drobilla.net/ns/ingen#canvasY> "%f"^^<http://www.w3.org/2001/XMLSchema#float> ;
        <http://lv2plug.in/ns/lv2core#name> "%s" ;
        a <http://lv2plug.in/ns/lv2core#%sPort> ;
        a %s ;
        %s
        """ % (x, y, name, mode, portyp, extra)

        self.put("/graph/%s" % name.replace(" ", "_").replace("-","_").lower(), msg, callback)
