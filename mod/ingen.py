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

import os
import rdflib
import socket
import sys

try:
    import StringIO.StringIO as StringIO
except ImportError:
    from io import StringIO as StringIO

class NS:
    ingen  = rdflib.Namespace('http://drobilla.net/ns/ingen#')
    ingerr = rdflib.Namespace('http://drobilla.net/ns/ingen/errors#')
    lv2    = rdflib.Namespace('http://lv2plug.in/ns/lv2core#')
    patch  = rdflib.Namespace('http://lv2plug.in/ns/ext/patch#')
    rdf    = rdflib.Namespace('http://www.w3.org/1999/02/22-rdf-syntax-ns#')
    xsd    = rdflib.Namespace('http://www.w3.org/2001/XMLSchema#')

class Interface:
    'The core Ingen interface'
    def put(self, path, body):
        pass

    def set(self, path, body):
        pass

    def connect(self, tail, head):
        pass

    def disconnect(self, tail, head):
        pass

    def delete(self, path):
        pass

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

class Host(Interface):
    def __init__(self, uri='unix:///tmp/ingen.sock', callback=lambda:None):
        self.msg_id      = 1
        self.server_base = uri + '/'
        self.uri = uri
        self.model       = rdflib.Graph()
        self.ns_manager  = rdflib.namespace.NamespaceManager(self.model)
        self.ns_manager.bind('server', self.server_base)
        self._queue = []

        for (k, v) in NS.__dict__.items():
            self.ns_manager.bind(k, v)

        # Parse error description from Ingen bundle for pretty printing
        bundle = ingen_bundle_path()
        if bundle:
            self.model.parse(os.path.join(bundle, 'errors.ttl'), format='n3')
        self.open_connection(callback)

    def open_connection(self, callback=None):
        self.socket_idle = False
        def check_response():
            if callback is not None:
                callback()
            if len(self._queue):
                self.process_queue()
            else:
                self.socket_idle = True
            #self.setup_monitor()

        if self.uri.startswith('unix://'):
            self.sock = iostream.IOStream(socket.socket(socket.AF_UNIX, socket.SOCK_STREAM))
            ioloop.IOLoop.instance().add_callback(lambda: self.sock.connect(self.uri[len('unix://'):], check_response))
        elif self.uri.startswith('tcp://'):
            self.sock = iostream.IOStream(socket.AF_INET, socket.SOCK_STREAM)
            parsed = re.split('[:/]', self.uri[len('tcp://'):])
            addr = (parsed[0], int(parsed[1]))
            ioloop.IOLoop.instance().add_callback(lambda: self.sock.connect(addr, check_response))
        else:
            raise Exception('Unsupported server URI `%s' % self.uri)

    def _send(self, msg, callback=lambda:None, datatype='int'):
        self._queue.append((msg, callback, datatype))
        if self.socket_idle:
            self.process_queue()

    def __del__(self):
        self.sock.close()

    def msgencode(self, msg):
        if sys.version_info[0] == 3:
            return bytes(msg, 'utf-8')
        else:
            return msg.encode("utf-8")

    def update_model(self, update):
        for i in update.triples([None, NS.rdf.type, NS.patch.Put]):
            put     = i[0]
            subject = update.value(put, NS.patch.subject, None)
            body    = update.value(put, NS.patch.body, None)
            desc    = {}
            for i in update.triples([body, None, None]):
                self.model.add([subject, i[1], i[2]])
        return update

    def uri_to_path(self, uri):
        path = uri
        if uri.startswith(self.server_base):
            return uri[len(self.server_base)-1:]
        return uri

    def blank_closure(self, graph, node):
        def blank_walk(node, g):
            for i in g.triples([node, None, None]):
                if type(i[2]) == rdflib.BNode and i[2] != node:
                    yield i[2]
                    blank_walk(i[2], g)

        closure = [node]
        for b in graph.transitiveClosure(blank_walk, node):
            closure += [b]

        return closure

    def raise_error(self, code, cause):
        klass = self.model.value(None, NS.ingerr.errorCode, rdflib.Literal(code))
        if not klass:
            raise Error('error %d' % code, cause)

        fmt = self.model.value(klass, NS.ingerr.formatString, None)
        if not fmt:
            raise Error('%s' % klass, cause)

        raise Error(fmt, cause)

    def process_queue(self):
        # Send message to server
        try:
            msg, callback, datatype = self._queue.pop(0)
        except IndexError:
            self.socket_idle = True
            return

        self.sock.write(self.msgencode(msg))

        def receive(response_str):
            print "called RECEIVE WITH:"
            response_str = response_str.replace("\0", "")
            if not response_str:
                callback("")
                self.process_queue()
            # Receive response and parse into a model
            response_model = rdflib.Graph()
            response_model.namespace_manager = self.ns_manager
            response_model.parse(StringIO(response_str.decode('utf-8')), self.server_base, format='n3')

            # Handle response (though there should be only one)
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
            callback(self.update_model(response_model))
            self.process_queue()
        self.sock.read_until("\0", receive)

    def get(self, path, callback=lambda r:r):
        return self._send('''
[]
 	a patch:Get ;
 	patch:subject <ingen:/root%s> .
''' % path, callback)

    def put(self, path, body, callback=lambda r:r):
        return self._send('''
[]
 	a patch:Put ;
 	patch:subject <ingen:/root%s> ;
 	patch:body [
%s
	] .
''' % (path, body), callback)

    def set(self, path, body, callback=lambda r: r):
        return self._send('''
[]
	a patch:Set ;
	patch:subject <ingen:/root%s> ;
	patch:body [
%s
	] .
''' % (path, body), callback)

    def connecti(self, tail, head, callback=lambda r: r):
        return self._send('''
[]
	a patch:Put ;
	patch:subject <ingen:/root%s> ;
	patch:body [
		a ingen:Arc ;
		ingen:tail <ingen:/root%s> ;
		ingen:head <ingen:/root%s> ;
	] .
''' % (os.path.commonprefix([tail, head]), tail, head))

    def disconnecti(self, tail, head, callback=lambda r: r):
        return self._send('''
[]
	a patch:Delete ;
	patch:body [
		a ingen:Arc ;
		ingen:tail <ingen:/root%s> ;
		ingen:head <ingen:/root%s> ;
	] .
''' % (tail, head), callback)

    def delete(self, path, callback=lambda r: r):
        return self._send('''
[]
	a patch:Delete ;
	patch:subject <ingen:/root%s> .
''' % path, callback)

    def parse_port(self, port):
        r = port
        if "mod-host-effect_" in port:
            instance, port = port.split(":")
            instance = instance.replace("mod-host-effect_", "")
            r = "/instance%s/%s" % (instance, port)
        elif "system" in port:
            _, port = port.split(":")
            r = "/system/%s" % port
        return r

    def add(self, uri, instance_id, callback=lambda r: r):
        self.put("/instance%d" % instance_id, "a ingen:Block ; ingen:prototype <%s>" % uri, callback)

    def connect(self, origin_port, destination_port, callback=lambda r: r):
        self.connecti(self.parse_port(origin_port), self.parse_port(destination_port), callback)

    def cpu_load(self, callback=lambda r:r):
        callback({'ok': True, 'value': 50})

    def monitor(self, addr, port, status, callback=lambda r:r):
        callback(True)

    def bypass(self, instance, value, callback=lambda r:r):
        callback(True)
