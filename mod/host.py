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

from mod.protocol import ProtocolError, process_resp
from tornado import iostream, ioloop
import socket, logging

# class to map between numeric ids and string instances
class InstanceIdMapper(object):
    def __init__(self):
        # last used id, always incrementing
        self.last_id = 0
        # map id <-> instances
        self.id_map = {}
        # map instances <-> ids
        self.instance_map = {}

    # get a numeric id from a string instance
    def get_id(self, instance):
        # check if it already exists
        if instance in self.instance_map.keys():
            return self.instance_map[instance]

        # increment last id
        id = self.last_id
        self.last_id += 1

        # create mapping
        self.instance_map[instance] = id
        self.id_map[id] = instance

        # ready
        return self.instance_map[instance]

    def get_id_without_creating(self, instance):
        return self.instance_map[instance]

    # get a string instance from a numeric id
    def get_instance(self, id):
        return self.id_map[id]

class Host(object):
    def __init__(self):
        self.addr = ("localhost", 5555)
        self.sock = None
        self.connected = False
        self._queue = []
        self._idle = True
        self.mapper = InstanceIdMapper()
        self.plugins = {}
        self.pedalboard_name = ""
        self.pedalboard_size = [0,0]

        self.cputimerok = True
        self.cputimer = ioloop.PeriodicCallback(self.cputimer_callback, 1000)

        self.msg_callback = lambda msg:None
        self.saved_callback = lambda bundlepath:None
        self.loaded_callback = lambda bundlepath:None
        self.plugin_added_callback = lambda instance,uri,enabled,x,y:None
        self.plugin_removed_callback = lambda instance:None
        self.plugin_enabled_callback = lambda instance,enabled:None
        self.plugin_position_callback = lambda instance,x,y:None
        self.port_value_callback = lambda port,value:None
        self.port_binding_callback = lambda port,cc:None
        self.connection_added_callback = lambda port1,port2:None
        self.connection_removed_callback = lambda port1,port2:None

        ioloop.IOLoop.instance().add_callback(self.init_connection)

    def init_connection(self):
        self.open_connection_if_needed(lambda:None)

    def open_connection_if_needed(self, callback):
        if self.sock is not None:
            callback()
            return

        self.sock = iostream.IOStream(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
        self._idle = False

        def check_response():
            self.connected = True
            callback()
            self.cputimer.start()
            if len(self._queue):
                self.process_queue()
            else:
                self._idle = True

        def closed():
            self.sock = None

        self.sock.set_close_callback(closed)
        self.sock.connect(self.addr, check_response)

    def process_queue(self):
        try:
            msg, callback, datatype = self._queue.pop(0)
            logging.info("[host] popped from queue: %s" % msg)
        except IndexError:
            self._idle = True
            return

        def check_response(resp):
            resp = resp.decode("utf-8", errors="ignore")

            logging.info("[host] received <- %s" % repr(resp))
            if not resp.startswith("resp"):
                logging.error("[host] protocol error: %s" % ProtocolError(resp)) # TODO: proper error handling

            r = resp.replace("resp ", "").replace("\0", "").strip()
            callback(process_resp(r, datatype))
            self.process_queue()

        self._idle = False
        logging.info("[host] sending -> %s" % msg)

        encmsg = "%s\0" % str(msg)
        self.sock.write(encmsg.encode("utf-8"))
        self.sock.read_until("\0".encode("utf-8"), check_response)

    def send(self, msg, callback, datatype='int'):
        self._queue.append((msg, callback, datatype))
        if self._idle:
            self.process_queue()

    # host stuff
    def initial_setup(self, callback):
        callback(True)

    def get(self, subject):
        if subject == "/graph":
            def get_port(type, isInput, name):
                if type == "midi":
                    types = "<http://lv2plug.in/ns/ext/atom#bufferType> <http://lv2plug.in/ns/ext/atom#Sequence> ;\n"
                    types += "a <http://lv2plug.in/ns/ext/atom#AtomPort> ,\n"
                elif type == "audio":
                    types = "a <http://lv2plug.in/ns/lv2core#AudioPort> ,\n"
                elif type == "cv":
                    types = "a <http://lv2plug.in/ns/lv2core#CVPort> ,\n"
                else:
                    return
                if isInput:
                    types += "<http://lv2plug.in/ns/lv2core#OutputPort>\n"
                else:
                    types += "<http://lv2plug.in/ns/lv2core#InputPort>\n"
                msg = """[]
                a <http://lv2plug.in/ns/ext/patch#Put> ;
                <http://lv2plug.in/ns/ext/patch#subject> </graph/system/%s> ;
                <http://lv2plug.in/ns/ext/patch#body> [
                    <http://lv2plug.in/ns/lv2core#index> "0"^^<http://www.w3.org/2001/XMLSchema#int> ;
                    <http://lv2plug.in/ns/lv2core#name> "%s" ;
                    %s
                ] .
                """ % (name, name.title().replace("_", " "), types)
                return msg
            self.msg_callback(get_port("audio", False, "capture_1"))
            self.msg_callback(get_port("audio", False, "capture_2"))
            self.msg_callback(get_port("audio", True, "playback_1"))
            self.msg_callback(get_port("audio", True, "playback_2"))
            self.msg_callback(get_port("midi", False, "midi_capture_1"))
            self.msg_callback(get_port("midi", True, "midi_playback_1"))

            for plugin in self.plugins.values():
                x, y = plugin['pos']
                msg = """[]
                a <http://lv2plug.in/ns/ext/patch#Put> ;
                <http://lv2plug.in/ns/ext/patch#subject> <%s> ;
                <http://lv2plug.in/ns/ext/patch#body> [
                    <http://drobilla.net/ns/ingen#canvasX> "%.1f"^^<http://www.w3.org/2001/XMLSchema#float> ;
                    <http://drobilla.net/ns/ingen#canvasY> "%.1f"^^<http://www.w3.org/2001/XMLSchema#float> ;
                    <http://drobilla.net/ns/ingen#enabled> %s ;
                    <http://lv2plug.in/ns/lv2core#prototype> <%s> ;
                    a <http://drobilla.net/ns/ingen#Block> ;
                ] .
                """ % (plugin['instance'], x, y, "false" if plugin['bypass'] else "true", plugin['uri'])
                self.plugin_added_callback(plugin['instance'], plugin['uri'], plugin['bypass'], x, y)
                self.msg_callback(msg)
            return

    def add_plugin(self, instance, uri, enabled, x, y, callback):
        instance_id = self.mapper.get_id(instance)
        x = float(x)
        y = float(y)

        def ingen_callback(ok):
            if not ok:
                callback(False)
                return
            msg = """[]
            a <http://lv2plug.in/ns/ext/patch#Put> ;
            <http://lv2plug.in/ns/ext/patch#subject> <%s> ;
            <http://lv2plug.in/ns/ext/patch#body> [
                <http://drobilla.net/ns/ingen#canvasX> "%.1f"^^<http://www.w3.org/2001/XMLSchema#float> ;
                <http://drobilla.net/ns/ingen#canvasY> "%.1f"^^<http://www.w3.org/2001/XMLSchema#float> ;
                <http://drobilla.net/ns/ingen#enabled> true ;
                <http://lv2plug.in/ns/lv2core#prototype> <%s> ;
                a <http://drobilla.net/ns/ingen#Block> ;
            ] .
            """ % (instance, x, y, uri)

            self.plugins[instance_id] = {
                "instance": instance,
                "uri"     : uri,
                "bypass"  : not enabled,
                "pos"     : [x,y],
                "values"  : {},
            }

            self.plugin_added_callback(instance, uri, False, x, y)
            self.msg_callback(msg)
            callback(True)

        self.send("add %s %d" % (uri, instance_id), ingen_callback, datatype='boolean')

    def remove_plugin(self, instance, callback):
        instance_id = self.mapper.get_id_without_creating(instance)
        self.plugins.pop(instance_id)

        def ingen_callback(ok):
            if not ok:
                callback(False)
                return
            msg = """[]
            a <http://lv2plug.in/ns/ext/patch#Delete> ;
            <http://lv2plug.in/ns/ext/patch#subject> <%s> .
            """ % instance
            self.plugin_removed_callback(instance)
            self.msg_callback(msg)
            callback(True)

        self.send("remove %d" % instance_id, ingen_callback, datatype='boolean')

    def enable(self, instance, enabled, callback):
        instance_id = self.mapper.get_id_without_creating(instance)
        self.plugins[instance_id]['bypass'] = not enabled

        self.send("bypass %d %d" % (instance_id, 0 if enabled else 1), callback, datatype='boolean')

    def param_set(self, port, value, callback):
        instance, symbol = port.rsplit("/", 1)
        instance_id = self.mapper.get_id_without_creating(instance)
        self.plugins[instance_id]['values'][symbol] = value

        self.send("param_set %d %s %f" % (instance_id, symbol, value), callback, datatype='boolean')

    def set_position(self, instance, x, y, callback):
        instance_id = self.mapper.get_id_without_creating(instance)

        self.plugins[instance_id]['pos'] = float(x), float(y)
        callback(True)

    def connect(self, port_from, port_to, callback):
        if port_from.startswith("/graph/system/"):
            host_port_from = port_from.replace("/graph/system/","system:")
        else:
            instance, symbol = port_from.rsplit("/", 1)
            instance_id = self.mapper.get_id_without_creating(instance)
            host_port_from = "effect_%d:%s" % (instance_id, symbol)

        if port_to.startswith("/graph/system/"):
            host_port_to = port_to.replace("/graph/system/","system:")
        else:
            instance, symbol = port_to.rsplit("/", 1)
            instance_id = self.mapper.get_id_without_creating(instance)
            host_port_to = "effect_%d:%s" % (instance_id, symbol)

        def ingen_callback(ok):
            if not ok:
                callback(False)
                return
            msg = """[]
            a <http://lv2plug.in/ns/ext/patch#Put> ;
            <http://lv2plug.in/ns/ext/patch#subject> </graph/> ;
            <http://lv2plug.in/ns/ext/patch#body> [
                    a <http://drobilla.net/ns/ingen#Arc> ;
                    <http://drobilla.net/ns/ingen#tail> <%s> ;
                    <http://drobilla.net/ns/ingen#head> <%s>
            ] .""" % (port_from, port_to)
            self.msg_callback(msg)
            callback(True)

        self.send("connect %s %s" % (host_port_from, host_port_to), ingen_callback, datatype='boolean')

    def disconnect(self, port_from, port_to, callback):
        if port_from.startswith("/graph/system/"):
            host_port_from = port_from.replace("/graph/system/","system:")
        else:
            instance, symbol = port_from.rsplit("/", 1)
            instance_id = self.mapper.get_id_without_creating(instance)
            host_port_from = "effect_%d:%s" % (instance_id, symbol)

        if port_to.startswith("/graph/system/"):
            host_port_to = port_to.replace("/graph/system/","system:")
        else:
            instance, symbol = port_to.rsplit("/", 1)
            instance_id = self.mapper.get_id_without_creating(instance)
            host_port_to = "effect_%d:%s" % (instance_id, symbol)

        def ingen_callback(ok):
            if not ok:
                callback(False)
                return
            msg = """[]
            a <http://lv2plug.in/ns/ext/patch#Delete> ;
            <http://lv2plug.in/ns/ext/patch#body> [
                    a <http://drobilla.net/ns/ingen#Arc> ;
                    <http://drobilla.net/ns/ingen#tail> <%s> ;
                    <http://drobilla.net/ns/ingen#head> <%s>
            ] .""" % (port_from, port_to)
            self.msg_callback(msg)
            callback(True)

        self.send("disconnect %s %s" % (host_port_from, host_port_to), ingen_callback, datatype='boolean')

    def set_pedalboard_name(self, title, callback):
        self.pedalboard_name = title
        callback(True)

    def set_pedalboard_size(self, width, height, callback):
        self.pedalboard_size = [width, height]
        callback(True)

    def add_external_port(self, name, mode, typ, callback):
        # ignored
        callback(True)

    def remove_external_port(self, name, callback):
        # ignored
        callback(True)

    def cputimer_callback(self):
        if not self.cputimerok:
            return

        def cpu_callback(resp):
            if not resp['ok']:
                return
            msg = """[]
            a <http://lv2plug.in/ns/ext/patch#Set> ;
            <http://lv2plug.in/ns/ext/patch#subject> </engine/> ;
            <http://lv2plug.in/ns/ext/patch#property> <http://moddevices/ns/modpedal#cpuload> ;
            <http://lv2plug.in/ns/ext/patch#value> "%0.1f" .""" % resp['value']
            self.msg_callback(msg)
            self.cputimerok = True

        self.cputimerok = False
        self.send("cpu_load", cpu_callback, datatype='float_structure')
