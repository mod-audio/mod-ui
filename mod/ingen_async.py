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
from mod.lilvlib import get_bundle_dirname

import os
import rdflib
import socket
import sys

try:
    import StringIO.StringIO as StringIO
except ImportError:
    from io import StringIO as StringIO

class NS:
    ingen       = rdflib.Namespace('http://drobilla.net/ns/ingen#')
    ingerr      = rdflib.Namespace('http://drobilla.net/ns/ingen/errors#')
    lv2         = rdflib.Namespace('http://lv2plug.in/ns/lv2core#')
    patch       = rdflib.Namespace('http://lv2plug.in/ns/ext/patch#')
    rdf         = rdflib.Namespace('http://www.w3.org/1999/02/22-rdf-syntax-ns#')
    xsd         = rdflib.Namespace('http://www.w3.org/2001/XMLSchema#')
    presets     = rdflib.Namespace('http://lv2plug.in/ns/ext/presets#')
    parameters  = rdflib.Namespace('http://lv2plug.in/ns/ext/parameters#')
    midi        = rdflib.Namespace('http://lv2plug.in/ns/ext/midi#')

class Error(Exception):
    def __init__(self, msg, cause):
        Exception.__init__(self, '%s; cause: %s' % (msg, cause))

def lv2_path():
    path = os.getenv('LV2_PATH')
    if path:
        return path
    elif sys.platform == 'darwin':
        return os.pathsep.join(['~/Library/Audio/Plug-Ins/LV2',
                                '~/.lv2',
                                '/usr/local/lib/lv2',
                                '/usr/lib/lv2',
                                '/Library/Audio/Plug-Ins/LV2'])
    elif sys.platform == 'haiku':
        return os.pathsep.join(['~/.lv2',
                                '/boot/common/add-ons/lv2'])
    elif sys.platform == 'win32':
        return os.pathsep.join([
                os.path.join(os.getenv('APPDATA'), 'LV2'),
                os.path.join(os.getenv('COMMONPROGRAMFILES'), 'LV2')])
    else:
        return os.pathsep.join(['~/.lv2',
                                '/usr/lib/lv2',
                                '/usr/local/lib/lv2'])

def ingen_bundle_path():
    for d in lv2_path().split(os.pathsep):
        bundle = os.path.abspath(os.path.join(d, 'ingen.lv2'))
        if os.path.exists(bundle):
            return bundle
    return None

class IngenAsync(object):
    def __init__(self, uri='unix:///tmp/ingen.sock', callback=lambda:None):
        self.msg_id      = 1
        self.server_base = uri + '/'
        self.proto_base = "mod://"
        self.uri = uri
        self.model       = rdflib.Graph()
        self.ns_manager  = rdflib.namespace.NamespaceManager(self.model)
        self.ns_manager.bind('server', self.server_base)
        self._queue = []
        self._idle = True

        self.msg_callback = lambda msg:None
        self.saved_callback = lambda bundlepath:None
        self.samplerate_callback = lambda srate:None
        self.plugin_added_callback = lambda instance,uri,x,y:None
        self.plugin_removed_callback = lambda instance:None
        self.plugin_position_callback = lambda instance,x,y:None
        self.port_value_callback = lambda port,value:None
        self.port_binding_callback = lambda port,cc:None
        self.connection_added_callback = lambda port1,port2:None
        self.connection_removed_callback = lambda port1,port2:None

        for (k, v) in NS.__dict__.items():
            if k.startswith("__") and k.endswith("__"):
                continue
            self.ns_manager.bind(k, v)

        # Parse error description from Ingen bundle for pretty printing
        bundle = ingen_bundle_path()
        if bundle:
            self.model.parse(os.path.join(bundle, 'errors.ttl'), format='n3')
        self.open_connection(callback)

    def open_connection(self, callback=None):
        def check_response():
            if callback is not None:
                callback()
            self.sock.read_until(b"\0", self.keep_reading)

        if self.uri.startswith('unix://'):
            self.sock = iostream.IOStream(socket.socket(socket.AF_UNIX, socket.SOCK_STREAM))
            ioloop.IOLoop.instance().add_callback(lambda: self.sock.connect(self.uri[len('unix://'):], check_response))
        elif self.uri.startswith('tcp://'):
            self.sock = iostream.IOStream(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
            parsed = re.split('[:/]', self.uri[len('tcp://'):])
            addr = (parsed[0], int(parsed[1]))
            ioloop.IOLoop.instance().add_callback(lambda: self.sock.connect(addr, check_response))
        else:
            raise Exception('Unsupported server URI `%s' % self.uri)

    def keep_reading(self, msg=None):
        self._reading = False

        msg_str = msg.decode("utf-8", errors="ignore").replace("\0", "") if msg else ""
        if msg_str:
            self.msg_callback(msg_str)
            msg_model = rdflib.Graph(namespace_manager=self.ns_manager)
            msg_model.parse(StringIO(msg_str), self.proto_base, format='n3')# self.server_base, format='n3')

            # Handle responses if any
            """"
            blanks        = []
            response_desc = []
            for i in response_model.triples([None, NS.rdf.type, NS.patch.Response]):
                response = i[0]
                subject  = response_model.value(response, NS.patch.subject, None)
                body     = response_model.value(response, NS.patch.body, None)

                response_desc += [i]
                blanks        += [response]
                if body != 0:
                    self.raise_error(int(body), msg)  # Raise exception on server error

            # Find the blank node closure of all responses
            blank_closure = []
            for b in blanks:
                blank_closure += self.blank_closure(response_model, b)

            # Remove response descriptions from model
            for b in blank_closure:
                for t in response_model.triples([b, None, None]):
                    response_model.remove(t)

            # Remove triples describing responses from response model
            for i in response_desc:
                response_model.remove(i)

            # Update model with remaining information, e.g. patch:Put updates
            #callback(self.update_model(response_model))
            self.update_model(response_model)
            """

            # Patch messages
            for i in msg_model.triples([None, NS.rdf.type, NS.patch.Patch]):
                bnode    = i[0]
                subject  = msg_model.value(bnode, NS.patch.subject)
                add_node = msg_model.value(bnode, NS.patch.add)

                # Is it setting a position?
                if NS.ingen.canvasX in msg_model.predicates(add_node) and NS.ingen.canvasY in msg_model.predicates(add_node):
                    x = msg_model.value(add_node, NS.ingen.canvasX).toPython()
                    y = msg_model.value(add_node, NS.ingen.canvasY).toPython()
                    self.plugin_position_callback(subject.partition(self.proto_base)[-1], x, y)

            # Checks for Copy messages
            for i in msg_model.triples([None, NS.rdf.type, NS.patch.Copy]):
                bnode   = i[0]
                subject = msg_model.value(bnode, NS.patch.subject).toPython().replace(self.proto_base,"",1)

                if subject in ("/graph", "/graph/"):
                    bundlepath = get_bundle_dirname(msg_model.value(bnode, NS.patch.destination).toPython())
                    self.saved_callback(bundlepath)

            # Checks for Set messages
            for i in msg_model.triples([None, NS.rdf.type, NS.patch.Set]):
                bnode    = i[0]
                subject  = msg_model.value(bnode, NS.patch.subject)
                property = msg_model.value(bnode, NS.patch.property)

                # Setting a port value
                if property == NS.ingen.value:
                    port  = subject.partition(self.proto_base)[-1]
                    value = msg_model.value(bnode, NS.patch.value).toPython()
                    self.port_value_callback(port, value)

                elif property == NS.parameters.sampleRate:
                    value = msg_model.value(bnode, NS.patch.value).toPython()
                    self.samplerate_callback(value)

                elif property == NS.midi.binding:
                    port = subject.partition(self.proto_base)[-1]
                    if msg_model.value(bnode, NS.rdf.type) == NS.midi.Controller:
                        cc = msg_model.value(msg_model.value(bnode, NS.patch.value), NS.midi.controllerNumber).toPython()
                        self.port_binding_callback(port, cc)

            # Put messages
            for i in msg_model.triples([None, NS.rdf.type, NS.patch.Put]):
                bnode    = i[0]
                subject  = msg_model.value(bnode, NS.patch.subject)
                body     = msg_model.value(bnode, NS.patch.body)
                msg_type = msg_model.value(body,  NS.rdf.type)

                # Put for port, we set the value
                if msg_type == NS.lv2.ControlPort:
                    value = msg_model.value(body, NS.ingen.value)
                    if value is None:
                        continue
                    port = subject.partition(self.proto_base)[-1]
                    self.port_value_callback(port, value.toPython())

                elif msg_type == NS.ingen.Block:
                    protouri = msg_model.value(body, NS.lv2.prototype)
                    if protouri is None:
                        continue
                    instance = subject.partition(self.proto_base)[-1]
                    x = msg_model.value(body, NS.ingen.canvasX)
                    y = msg_model.value(body, NS.ingen.canvasY)
                    self.plugin_added_callback(instance, protouri.toPython(), x or 0, y or 0)

                elif msg_type == NS.ingen.Arc:
                    head = msg_model.value(body, NS.ingen.head).partition(self.proto_base)[-1]
                    tail = msg_model.value(body, NS.ingen.tail).partition(self.proto_base)[-1]
                    self.connection_added_callback(head, tail)

            # Delete msgs
            for i in msg_model.triples([None, NS.rdf.type, NS.patch.Delete]):
                bnode   = i[0]
                subject = msg_model.value(bnode, NS.patch.subject)
                if subject:
                    self.plugin_removed_callback(subject.partition(self.proto_base)[-1])

        self._reading = True
        self.sock.read_until(self.msgencode(".\n"), self.keep_reading)

    def _send(self, msg, callback=lambda r:r, datatype='int'):
        self.sock.write(self.msgencode(msg), lambda: callback(True))

    def __del__(self):
        self.sock.close()

    def msgencode(self, msg):
        if sys.version_info[0] == 3:
            return bytes(msg, 'utf-8')
        else:
            return msg.encode("utf-8")

    def raise_error(self, code, cause):
        klass = self.model.value(None, NS.ingerr.errorCode, rdflib.Literal(code))
        if not klass:
            raise Error('error %d' % code, cause)

        fmt = self.model.value(klass, NS.ingerr.formatString, None)
        if not fmt:
            raise Error('%s' % klass, cause)

        raise Error(fmt, cause)

    # abstract methods

    def get(self, path, callback=lambda r:r):
        return self._send('''[]
        a patch:Get ;
        patch:subject <%s> .
''' % path, callback)

    def set(self, path, prop, value, callback=lambda r:r):
        return self._send('''[]
        a patch:Set ;
        patch:subject <%s> ;
        patch:property %s ;
        patch:value %s .
''' % (path, prop, value), callback)

    def put(self, path, body, callback=lambda r:r):
        return self._send('''[]
        a patch:Put ;
        patch:subject <%s> ;
        patch:body [ %s ] .
''' % (path, body), callback)

    def copy(self, source, target, callback=lambda r:r):
        return self._send('''[]
        a patch:Copy ;
        patch:subject <%s> ;
        patch:destination <%s> .
''' % (source, target), callback)

    def delete(self, path, callback=lambda r:r):
        return self._send('''[]
        a patch:Delete ;
        patch:subject <%s> .
''' % path, callback)

    def move(self, source, target, callback=lambda r:r):
        return self._send('''[]
        a patch:Move ;
        patch:subject <%s> ;
        patch:destination <%s> .
''' % (source, target), callback)

    def patch(self, path, remove, add, callback=lambda r:r):
        remove_str = ""
        add_str = ""
        for prop, value in remove:
            remove_str += "%s %s;\n" % (prop, value)

        for prop, value in add:
            add_str += "%s %s;\n" % (prop, value)

        return self._send('''[]
        a patch:Patch ;
        patch:subject <%s> ;
        patch:remove [ %s ] ;
        patch:add [ %s ] .
''' % (path, remove_str, add_str), callback)
