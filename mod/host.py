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
import os, json, socket, logging

from mod import get_hardware
from mod.bank import list_banks
from mod.jacklib_helpers import jacklib, charPtrToString, charPtrPtrToStringList
from mod.lilvlib import get_pedalboard_info
from mod.protocol import Protocol, ProtocolError, process_resp

try:
    from mod.utils import get_plugin_info
except:
    from mod.lv2 import get_plugin_info

ADDRESSING_CTYPE_LINEAR       = 0
ADDRESSING_CTYPE_BYPASS       = 1
ADDRESSING_CTYPE_TAP_TEMPO    = 2
ADDRESSING_CTYPE_ENUMERATION  = 4 # implies scalepoints
ADDRESSING_CTYPE_SCALE_POINTS = 8
ADDRESSING_CTYPE_TRIGGER      = 16
ADDRESSING_CTYPE_TOGGLED      = 32
ADDRESSING_CTYPE_LOGARITHMIC  = 64
ADDRESSING_CTYPE_INTEGER      = 128

ACTUATOR_TYPE_FOOTSWITCH = 1
ACTUATOR_TYPE_KNOB       = 2
ACTUATOR_TYPE_POT        = 3

HARDWARE_TYPE_MOD    = 0
HARDWARE_TYPE_PEDAL  = 1
HARDWARE_TYPE_TOUCH  = 2
HARDWARE_TYPE_ACCEL  = 3
HARDWARE_TYPE_CUSTOM = 4

# class to map between numeric ids and string instances
class InstanceIdMapper(object):
    def __init__(self):
        self.clear()

    def clear(self):
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
    def __init__(self, hmi):
        self.hmi = hmi
        self.addr = ("localhost", 5555)
        self.sock = None
        self.crashed = False
        self.connected = False
        self._queue = []
        self._idle = True
        self.mapper = InstanceIdMapper()
        self.banks = []
        self.plugins = {}
        self.connections = []
        self.audioportsIn = []
        self.audioportsOut = []
        self.midiports = []
        self.pedalboard_name = ""
        self.pedalboard_size = [0,0]

        self.jack_client = None
        self.xrun_count = 0
        self.xrun_count2 = 0

        self.cputimerok = True
        self.cputimer = ioloop.PeriodicCallback(self.cputimer_callback, 1000)

        self.msg_callback = lambda msg:None
        self.saved_callback = lambda bundlepath:None
        #self.loaded_callback = lambda bundlepath:None
        #self.plugin_added_callback = lambda instance,uri,enabled,x,y:None
        #self.plugin_removed_callback = lambda instance:None
        #self.plugin_enabled_callback = lambda instance,enabled:None
        #self.plugin_position_callback = lambda instance,x,y:None
        #self.port_value_callback = lambda port,value:None
        #self.port_binding_callback = lambda port,cc:None
        #self.connection_added_callback = lambda port1,port2:None
        #self.connection_removed_callback = lambda port1,port2:None

        # Register HMI protocol callbacks
        self._init_addressings()
        Protocol.register_cmd_callback("hw_con", self.hmi_hardware_connected)
        Protocol.register_cmd_callback("hw_dis", self.hmi_hardware_disconnected)
        Protocol.register_cmd_callback("banks", self.hmi_list_banks)
        Protocol.register_cmd_callback("pedalboards", self.hmi_list_bank_pedalboards)
        Protocol.register_cmd_callback("pedalboard", self.hmi_load_bank_pedalboard)
        Protocol.register_cmd_callback("control_get", self.hmi_parameter_get)
        Protocol.register_cmd_callback("control_set", self.hmi_parameter_set)
        Protocol.register_cmd_callback("control_next", self.hmi_parameter_addressing_next)
        #Protocol.register_cmd_callback("peakmeter", self.peakmeter_set)
        #Protocol.register_cmd_callback("tuner", self.tuner_set)
        #Protocol.register_cmd_callback("tuner_input", self.tuner_set_input)
        #Protocol.register_cmd_callback("pedalboard_save", self.save_current_pedalboard)
        #Protocol.register_cmd_callback("pedalboard_reset", self.reset_current_pedalboard)
        #Protocol.register_cmd_callback("jack_cpu_load", self.jack_cpu_load)

        ioloop.IOLoop.instance().add_callback(self.init_jack)
        ioloop.IOLoop.instance().add_callback(self.init_connection)

    def __del__(self):
        self.msg_callback("stop")
        self.close_jack()

    # -----------------------------------------------------------------------------------------------------------------
    # Initialization

    def init_jack(self):
        if self.jack_client is not None:
            return

        self.jack_client = jacklib.client_open("mod-ui", jacklib.JackNoStartServer, None)
        self.xrun_count  = 0
        self.xrun_count2 = 0
        self.audioportsIn  = []
        self.audioportsOut = []

        if self.jack_client is None:
            return

        #jacklib.jack_set_port_registration_callback(self.jack_client, self.JackPortRegistrationCallback, None)
        #jacklib.set_property_change_callback(self.jack_client, self.JackPropertyChangeCallback, None)
        #jacklib.set_xrun_callback(self.jack_client, self.JackXRunCallback, None)
        jacklib.on_shutdown(self.jack_client, self.JackShutdownCallback, None)
        jacklib.activate(self.jack_client)
        print("jacklib client activated")

        for port in charPtrPtrToStringList(jacklib.get_ports(self.jack_client, "system:", jacklib.JACK_DEFAULT_AUDIO_TYPE, jacklib.JackPortIsPhysical|jacklib.JackPortIsOutput)):
            self.audioportsIn.append(port.replace("system:","",1))

        for port in charPtrPtrToStringList(jacklib.get_ports(self.jack_client, "system:", jacklib.JACK_DEFAULT_AUDIO_TYPE, jacklib.JackPortIsPhysical|jacklib.JackPortIsInput)):
            self.audioportsOut.append(port.replace("system:","",1))

    def close_jack(self):
        if self.jack_client is None:
            print("jacklib client deactivated NOT")
            return
        jacklib.deactivate(self.jack_client)
        jacklib.client_close(self.jack_client)
        self.jack_client = None
        print("jacklib client deactivated")

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
            self.cputimerok = True
            self.cputimer.start()
            if len(self._queue):
                self.process_queue()
            else:
                self._idle = True

        def closed():
            self.sock = None
            self.crashed = True
            self.msg_callback("disconnected")

        self.sock.set_close_callback(closed)
        self.sock.connect(self.addr, check_response)

    # -----------------------------------------------------------------------------------------------------------------
    # Message handling

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

        if self.sock is None:
            return

        encmsg = "%s\0" % str(msg)
        self.sock.write(encmsg.encode("utf-8"))
        self.sock.read_until("\0".encode("utf-8"), check_response)

    def send(self, msg, callback, datatype='int'):
        self._queue.append((msg, callback, datatype))
        if self._idle:
            self.process_queue()

    # -----------------------------------------------------------------------------------------------------------------
    # Host stuff

    def initial_setup(self, callback):
        self.send("remove -1", callback, datatype='boolean')

    def report_current_state(self):
        self.msg_callback("wait_start")

        crashed = self.crashed
        self.crashed = False

        # Audio In
        for i in range(len(self.audioportsIn)):
            name  = self.audioportsIn[i]
            title = name.title().replace(" ","_")
            self.msg_callback("add_hw_port /graph/%s audio 0 %s %i" % (name, title, i+1))

        # Audio Out
        for i in range(len(self.audioportsOut)):
            name  = self.audioportsOut[i]
            title = name.title().replace(" ","_")
            self.msg_callback("add_hw_port /graph/%s audio 1 %s %i" % (name, title, i+1))

        if self.jack_client is not None:
            # TODO midiports split(";")

            # MIDI In
            ports = charPtrPtrToStringList(jacklib.get_ports(self.jack_client, "system:", jacklib.JACK_DEFAULT_MIDI_TYPE, jacklib.JackPortIsPhysical|jacklib.JackPortIsOutput))
            for i in range(len(ports)):
                name = ports[i]
                if name not in self.midiports:
                    continue
                ret, alias1, alias2 = jacklib.port_get_aliases(jacklib.port_by_name(self.jack_client, name))
                if ret == 1 and alias1:
                    title = alias1.split("-",5)[-1].replace("-","_")
                else:
                    title = name.replace("system:","",1).title().replace(" ","_")
                self.msg_callback("add_hw_port /graph/%s midi 0 %s %i" % (name, title, i+1))

            # MIDI Out
            ports = charPtrPtrToStringList(jacklib.get_ports(self.jack_client, "system:", jacklib.JACK_DEFAULT_MIDI_TYPE, jacklib.JackPortIsPhysical|jacklib.JackPortIsInput))
            for i in range(len(ports)):
                name = ports[i]
                if name not in self.midiports:
                    continue
                ret, alias1, alias2 = jacklib.port_get_aliases(jacklib.port_by_name(self.jack_client, name))
                if ret == 1 and alias1:
                    title = alias1.split("-",5)[-1].replace("-","_")
                else:
                    title = name.replace("system:","",1).title().replace(" ","_")
                self.msg_callback("add_hw_port /graph/%s midi 1 %s %i" % (name, title, i+1))

        for instance_id, plugin in self.plugins.items():
            self.msg_callback("add %s %s %.1f %.1f %d" % (plugin['instance'], plugin['uri'], plugin['x'], plugin['y'], int(plugin['bypassed'])))

            if crashed:
                self.send("add %s %d" % (plugin['uri'], instance_id), lambda r:None, datatype='int')
                if plugin['bypassed']:
                    self.send("bypass %d 1" % (instance_id,), lambda r:None, datatype='boolean')

            for symbol, value in plugin['ports'].items():
                self.msg_callback("param_set %s %s %f" % (plugin['instance'], symbol, value))

                if crashed:
                    self.send("param_set %d %s %f" % (instance_id, symbol, value), lambda r:None, datatype='boolean')

        for port_from, port_to in self.connections:
            self.msg_callback("connect %s %s" % (port_from, port_to))

            if crashed:
                self.send("connect %s %s" % (self._fix_host_connection_port(port_from),
                                             self._fix_host_connection_port(port_to)), lambda r:None, datatype='boolean')

        # TODO - set addressings?

        self.msg_callback("wait_end")

    # -----------------------------------------------------------------------------------------------------------------
    # Host stuff - reset, add, remove

    def reset(self, callback):
        self.banks = []
        self.plugins = {}
        self.connections = []
        self.mapper.clear()
        self._init_addressings()

        def host_callback(ok):
            self.msg_callback("remove :all")
            callback(ok)

        self.send("remove -1", host_callback, datatype='boolean')

    def add_plugin(self, instance, uri, x, y, callback):
        instance_id = self.mapper.get_id(instance)

        try:
            info = get_plugin_info(uri)
        except:
            callback(-1)
            return

        def host_callback(resp):
            if resp < 0:
                callback(resp)
                return
            bypassed = False
            self.plugins[instance_id] = {
                "instance"  : instance,
                "uri"       : uri,
                "bypassed"  : bypassed,
                "x"         : x,
                "y"         : y,
                "addressing": {}, # symbol: addressing
                "ports"     : dict((port['symbol'], port['ranges']['default']) for port in info['ports']['control']['input']),
            }
            self.msg_callback("add %s %s %.1f %.1f %d" % (instance, uri, x, y, int(bypassed)))
            callback(resp)

        self.send("add %s %d" % (uri, instance_id), host_callback, datatype='int')

    def remove_plugin(self, instance, callback):
        instance_id = self.mapper.get_id_without_creating(instance)

        try:
            self.plugins.pop(instance_id)
        except KeyError:
            callback(False)
            return

        for actuator_uri, addressing in self.addressings.items():
            i = 0
            while i < len(addressing['addrs']):
                if addressing['addrs'][i].get('instance_id') == instance_id:
                    addressing['addrs'].pop(i)
                    if addressing['idx'] >= i:
                        addressing['idx'] -= 1
                else:
                    i += 1

        def host_callback(ok):
            removed_connections = []
            for ports in self.connections:
                if ports[0].startswith(instance) or ports[1].startswith(instance):
                    removed_connections.append(ports)
            for ports in removed_connections:
                self.connections.remove(ports)
                self.msg_callback("disconnect %s %s" % (ports[0], ports[1]))

            self.msg_callback("remove %s" % (instance))
            callback(ok)

        self.hmi.control_rm(instance_id, ":all")
        self.send("remove %d" % instance_id, host_callback, datatype='boolean')

    # -----------------------------------------------------------------------------------------------------------------
    # Host stuff - plugin values

    def bypass(self, instance, bypassed, callback):
        instance_id = self.mapper.get_id_without_creating(instance)

        self.plugins[instance_id]['bypassed'] = bypassed
        self.send("bypass %d %d" % (instance_id, int(bypassed)), callback, datatype='boolean')

    def param_set(self, port, value, callback):
        instance, symbol = port.rsplit("/", 1)
        instance_id = self.mapper.get_id_without_creating(instance)

        self.plugins[instance_id]['ports'][symbol] = value
        self.send("param_set %d %s %f" % (instance_id, symbol, value), callback, datatype='boolean')

    def set_position(self, instance, x, y):
        instance_id = self.mapper.get_id_without_creating(instance)

        self.plugins[instance_id]['x'] = x
        self.plugins[instance_id]['y'] = y

    # -----------------------------------------------------------------------------------------------------------------
    # Host stuff - connections

    def _fix_host_connection_port(self, port):
        data = port.split("/")

        if len(data) == 3:
            return "system:%s" % data[2]

        instance    = "/graph/%s" % data[2]
        portsymbol  = data[3]
        instance_id = self.mapper.get_id_without_creating(instance)
        return "effect_%d:%s" % (instance_id, portsymbol)

    def connect(self, port_from, port_to, callback):
        def host_callback(ok):
            if ok:
                self.connections.append((port_from, port_to))
                self.msg_callback("connect %s %s" % (port_from, port_to))
            callback(ok)

        self.send("connect %s %s" % (self._fix_host_connection_port(port_from),
                                     self._fix_host_connection_port(port_to)), host_callback, datatype='boolean')

    def disconnect(self, port_from, port_to, callback):
        def host_callback(ok):
            if ok:
                self.connections.remove((port_from, port_to))
                self.msg_callback("disconnect %s %s" % (port_from, port_to))
            callback(ok)

        self.send("disconnect %s %s" % (self._fix_host_connection_port(port_from),
                                        self._fix_host_connection_port(port_to)), host_callback, datatype='boolean')

    # -----------------------------------------------------------------------------------------------------------------
    # Host stuff - load & save

    def load(self, bundlepath):
        self.msg_callback("wait_start")

        pb = get_pedalboard_info(bundlepath)

        for p in pb['plugins']:
            instance    = "/graph/%s" % p['instance']
            instance_id = self.mapper.get_id(instance)
            bypassed    = not p['enabled']

            self.send("add %s %d" % (p['uri'], instance_id), lambda r:None)

            if bypassed:
                self.send("bypass %d 1" % (instance_id,), lambda r:None)

            self.plugins[instance_id] = {
                "instance"  : instance,
                "uri"       : p['uri'],
                "bypassed"  : bypassed,
                "x"         : p['x'],
                "y"         : p['y'],
                "addressing": {}, # symbol: addressing
                "ports"     : {}, # dict((port['symbol'], port['ranges']['default']) for port in info['ports']['control']['input']),
            }
            self.msg_callback("add %s %s %.1f %.1f %d" % (instance, p['uri'], p['x'], p['y'], int(bypassed)))

        for c in pb['connections']:
            port_from = "/graph/%s" % c['source']
            port_to   = "/graph/%s" % c['target']
            self.send("connect %s %s" % (self._fix_host_connection_port(port_from), self._fix_host_connection_port(port_to)), lambda r:None)

            self.connections.append((port_from, port_to))
            self.msg_callback("connect %s %s" % (port_from, port_to))

        self.msg_callback("wait_end")

    def save(self, bundlepath, title, titlesym):
        # Write manifest.ttl
        with open(os.path.join(bundlepath, "manifest.ttl"), 'w') as fh:
            fh.write("""\
@prefix ingen: <http://drobilla.net/ns/ingen#> .
@prefix lv2:   <http://lv2plug.in/ns/lv2core#> .
@prefix pedal: <http://moddevices.com/ns/modpedal#> .
@prefix rdfs:  <http://www.w3.org/2000/01/rdf-schema#> .

<%s.ttl>
    lv2:prototype ingen:GraphPrototype ;
    a lv2:Plugin ,
        ingen:Graph ,
        pedal:Pedalboard ;
    rdfs:seeAlso <%s.ttl> .
""" % (titlesym, titlesym))

        # Write addressings.json
        addressings = self.get_addressings()

        with open(os.path.join(bundlepath, "addressings.json"), 'w') as fh:
            json.dump(addressings, fh)

        # Create list of midi in/out ports
        midiportsIn  = []
        midiportsOut = []

        for port in self.midiports:
            if ";" in port:
                inp, outp = port.split(";",1)
                midiportsIn.append(inp)
                midiportsOut.append(outp)
            else:
                midiportsIn.append(port)

        # Arcs (connections)
        arcs = ""
        index = 0
        for port_from, port_to in self.connections:
            index += 1
            arcs += """
_:b%i
    ingen:tail <%s> ;
    ingen:head <%s> .
""" % (index, port_from.replace("/graph/","",1), port_to.replace("/graph/","",1))

        # Blocks (plugins)
        blocks = ""
        for plugin in self.plugins.values():
            info = get_plugin_info(plugin['uri'])
            instance = plugin['instance'].replace("/graph/","",1)
            blocks += """
<%s>
    ingen:canvasX %.1f ;
    ingen:canvasY %.1f ;
    ingen:enabled %s ;
    ingen:polyphonic false ;
    lv2:microVersion %i ;
    lv2:minorVersion %i ;
    lv2:port <%s> ;
    lv2:prototype <%s> ;
    a ingen:Block .
""" % (instance, plugin['x'], plugin['y'], "false" if plugin['bypassed'] else "true",
       info['microVersion'], info['microVersion'],
       "> ,\n             <".join(tuple("%s/%s" % (instance, port['symbol']) for port in (info['ports']['audio']['input']+
                                                                                          info['ports']['audio']['output']+
                                                                                          info['ports']['control']['input']+
                                                                                          info['ports']['control']['output']+
                                                                                          info['ports']['cv']['input']+
                                                                                          info['ports']['cv']['output']+
                                                                                          info['ports']['midi']['input']+
                                                                                          info['ports']['midi']['output']))),
       plugin['uri'],)

            # audio input
            for port in info['ports']['audio']['input']:
                blocks += """
<%s/%s>
    a lv2:AudioPort ,
        lv2:InputPort .
""" % (instance, port['symbol'])

            # audio output
            for port in info['ports']['audio']['input']:
                blocks += """
<%s/%s>
    a lv2:AudioPort ,
        lv2:OutputPort .
""" % (instance, port['symbol'])

            # cv input
            for port in info['ports']['cv']['input']:
                blocks += """
<%s/%s>
    a lv2:CVPort ,
        lv2:InputPort .
""" % (instance, port['symbol'])

            # cv output
            for port in info['ports']['cv']['output']:
                blocks += """
<%s/%s>
    a lv2:CVPort ,
        lv2:OutputPort .
""" % (instance, port['symbol'])

            # midi input
            for port in info['ports']['midi']['input']:
                blocks += """
<%s/%s>
    atom:bufferType atom:Sequence ;
    atom:supports midi:MidiEvent ;
    a atom:AtomPort ,
        lv2:InputPort .
""" % (instance, port['symbol'])

            # midi output
            for port in info['ports']['midi']['output']:
                blocks += """
<%s/%s>
    atom:bufferType atom:Sequence ;
    atom:supports midi:MidiEvent ;
    a atom:AtomPort ,
        lv2:OutputPort .
""" % (instance, port['symbol'])

            # control input, save values
            for symbol, value in plugin['ports'].items():
                blocks += """
<%s/%s>
    ingen:value %f ;
    a lv2:ControlPort ,
        lv2:InputPort .
""" % (instance, symbol, value)

            # control output
            for port in info['ports']['control']['output']:
                blocks += """
<%s/%s>
    a lv2:ControlPort ,
        lv2:OutputPort .
""" % (instance, port['symbol'])

        # Ports
        ports = """
<control_in>
    atom:bufferType atom:Sequence ;
    lv2:index 0 ;
    lv2:name "Control" ;
    lv2:portProperty lv2:connectionOptional ;
    lv2:symbol "control_in" ;
    <http://lv2plug.in/ns/ext/resize-port#minimumSize> 4096 ;
    a atom:AtomPort ,
        lv2:InputPort .

<control_out>
    atom:bufferType atom:Sequence ;
    lv2:index 1 ;
    lv2:name "Control" ;
    lv2:portProperty lv2:connectionOptional ;
    lv2:symbol "control_out" ;
    <http://lv2plug.in/ns/ext/resize-port#minimumSize> 4096 ;
    a atom:AtomPort ,
        lv2:OutputPort .
"""
        index = 1

        # Ports (Audio In)
        for port in self.audioportsIn:
            index += 1
            ports += """
<%s>
    lv2:index %i ;
    lv2:name "%s" ;
    lv2:portProperty lv2:connectionOptional ;
    lv2:symbol "%s" ;
    a lv2:AudioPort ,
        lv2:InputPort .
""" % (port, index, port, port)

        # Ports (Audio Out)
        for port in self.audioportsOut:
            index += 1
            ports += """
<%s>
    lv2:index %i ;
    lv2:name "%s" ;
    lv2:portProperty lv2:connectionOptional ;
    lv2:symbol "%s" ;
    a lv2:AudioPort ,
        lv2:OutputPort .
""" % (port, index, port, port)

        # Ports (MIDI In)
        for port in midiportsIn:
            index += 1
            ports += """
<%s>
    atom:bufferType atom:Sequence ;
    atom:supports midi:MidiEvent ;
    lv2:index %i ;
    lv2:name "%s" ;
    lv2:portProperty lv2:connectionOptional ;
    lv2:symbol "%s" ;
    a atom:AtomPort ,
        lv2:OutputPort .
""" % (port, index, port, port)

        # Ports (MIDI Out)
        for port in midiportsOut:
            index += 1
            ports += """
<%s>
    atom:bufferType atom:Sequence ;
    atom:supports midi:MidiEvent ;
    lv2:index %i ;
    lv2:name "%s" ;
    lv2:portProperty lv2:connectionOptional ;
    lv2:symbol "%s" ;
    a atom:AtomPort ,
        lv2:OutputPort .
""" % (port, index, port, port)

        # Write the main pedalboard file
        pbdata = """\
@prefix atom:  <http://lv2plug.in/ns/ext/atom#> .
@prefix doap:  <http://usefulinc.com/ns/doap#> .
@prefix ingen: <http://drobilla.net/ns/ingen#> .
@prefix lv2:   <http://lv2plug.in/ns/lv2core#> .
@prefix midi:  <http://lv2plug.in/ns/ext/midi#> .
@prefix pedal: <http://moddevices.com/ns/modpedal#> .
@prefix rdfs:  <http://www.w3.org/2000/01/rdf-schema#> .
%s%s%s
<>
    doap:name "%s" ;
    pedal:width %i ;
    pedal:height %i ;
    pedal:addressings <addressings.json> ;
    pedal:screenshot <screenshot.png> ;
    pedal:thumbnail <thumbnail.png> ;
    ingen:polyphony 1 ;
""" % (arcs, blocks, ports, title, self.pedalboard_size[0], self.pedalboard_size[1])

        # Arcs (connections)
        if len(self.connections) > 0:
            pbdata += "    ingen:arc _:b%s ;\n" % (" ,\n              _:b".join(tuple(str(i+1) for i in range(len(self.connections)))))

        # Blocks (plugins)
        if len(self.plugins) > 0:
            pbdata += "    ingen:block <%s> ;\n" % ("> ,\n                <".join(tuple(p['instance'].replace("/graph/","",1) for p in self.plugins.values())))

        # Ports
        pbdata += "    lv2:port <%s> ;\n" % ("> ,\n             <".join(["control_in","control_out"]+
                                                                         self.audioportsIn+
                                                                         self.audioportsOut))

        # End
        pbdata += """\
    lv2:extensionData <http://lv2plug.in/ns/ext/state#interface> ;
    a lv2:Plugin ,
        ingen:Graph ,
        pedal:Pedalboard .
"""

        # Write the main pedalboard file
        with open(os.path.join(bundlepath, "%s.ttl" % titlesym), 'w') as fh:
            fh.write(pbdata)

    # -----------------------------------------------------------------------------------------------------------------
    # Host stuff - misc

    def set_pedalboard_size(self, width, height):
        self.pedalboard_size = [width, height]

    def add_external_port(self, name, mode, typ, callback):
        # ignored
        callback(True)

    def remove_external_port(self, name, callback):
        # ignored
        callback(True)

    # -----------------------------------------------------------------------------------------------------------------
    # Host stuff - timers

    def cputimer_callback(self):
        if not self.cputimerok:
            return

        def cpu_callback(resp):
            if not resp['ok']:
                return
            self.msg_callback("cpu_load %0.1f" % resp['value'])
            self.cputimerok = True

        self.cputimerok = False
        self.send("cpu_load", cpu_callback, datatype='float_structure')

    # -----------------------------------------------------------------------------------------------------------------
    # Addressing (public stuff)

    def address(self, instance, port, actuator_uri, label, maximum, minimum, value, steps, callback):
        instance_id = self.mapper.get_id(instance)

        data = self.plugins.get(instance_id, None)
        if data is None:
            callback(False)
            return

        old_actuator_uri = self._unaddress(data, port)

        # we might have to unaddress first, so define a function as possible callback
        def address_now(ok):
            options = []

            if port == ":bypass":
                ctype = ADDRESSING_CTYPE_BYPASS
                unit  = "none"

            else:
                for port_info in get_plugin_info(data["uri"])["ports"]["control"]["input"]:
                    if port_info["symbol"] != port:
                        continue
                    break
                else:
                    callback(False)
                    return

                pprops = port_info["properties"]
                unit   = port_info["units"]["symbol"] if "symbol" in port_info["units"] else "none"

                if "toggled" in pprops:
                    ctype = ADDRESSING_CTYPE_TOGGLED
                elif "integer" in pprops:
                    ctype = ADDRESSING_CTYPE_INTEGER
                else:
                    ctype = ADDRESSING_CTYPE_LINEAR

                if "logarithmic" in pprops:
                    ctype |= ADDRESSING_CTYPE_LOGARITHMIC
                if "trigger" in pprops:
                    ctype |= ADDRESSING_CTYPE_TRIGGER
                if "tap_tempo" in pprops: # TODO
                    ctype |= ADDRESSING_CTYPE_TAP_TEMPO

                if len(port_info["scalePoints"]) >= 2: # and "enumeration" in pprops:
                    ctype |= ADDRESSING_CTYPE_SCALE_POINTS|ADDRESSING_CTYPE_ENUMERATION

                    if "enumeration" in pprops:
                        ctype |= ADDRESSING_CTYPE_ENUMERATION

                    for scalePoint in port_info["scalePoints"]:
                        options.append((scalePoint["value"], scalePoint["label"]))

                del port_info, pprops

            addressing = {
                'actuator_uri': actuator_uri,
                'instance_id': instance_id,
                'port': port,
                'label': label,
                'type': ctype,
                'unit': unit,
                'minimum': minimum,
                'maximum': maximum,
                'steps': steps,
                'options': options,
            }
            self.plugins[instance_id]['addressing'][port] = addressing
            self.addressings[actuator_uri]['addrs'].append(addressing)
            self.addressings[actuator_uri]['idx'] = len(self.addressings[actuator_uri]['addrs']) - 1

            if old_actuator_uri is not None:
                def nextStep(ok):
                    self._addressing_load(actuator_uri, callback)
                self._addressing_load(old_actuator_uri, nextStep)

            else:
                self._addressing_load(actuator_uri, callback)

        # starting point here
        if (not actuator_uri) or actuator_uri == "null":
            self.hmi.control_rm(instance_id, port) # FIXME, callback)
            if old_actuator_uri is not None:
                  old_actuator_hw = self._uri2hw_map[old_actuator_uri]
                  self._address_next(old_actuator_hw, address_now)
            return

        # if we reach this line there was no old actuator, we can just address now
        address_now(True)

    def get_addressings(self):
        addressings = {}
        for uri, addressing in self.addressings.items():
            addrs = []
            for addr in addressing['addrs']:
                addrs.append({
                    'instance': self.mapper.get_instance(addr['instance_id']),
                    'port'    : addr['port'],
                    'label'   : addr['label'],
                    'minimum' : addr['minimum'],
                    'maximum' : addr['maximum'],
                    'steps'   : addr['steps'],
                })
            addressings[uri] = addrs
        return addressings

    # -----------------------------------------------------------------------------------------------------------------
    # Addressing (private stuff)

    def _init_addressings(self):
        # 'self.addressings' uses a structure like this:
        # "/hmi/knob1": {'addrs': [], 'idx': 0}
        hw = get_hardware()

        if "actuators" not in hw.keys():
            self.addressings = {}
            self._hw2uri_map = {}
            self._uri2hw_map = {}
            return

        self.addressings = dict((act["uri"], {'idx': 0, 'addrs': []}) for act in hw["actuators"])

        # Store all possible hardcoded values
        self._hw2uri_map = {}
        self._uri2hw_map = {}

        for i in range(0, 4):
            knob_hw  = (HARDWARE_TYPE_MOD, 0, ACTUATOR_TYPE_KNOB,       i)
            foot_hw  = (HARDWARE_TYPE_MOD, 0, ACTUATOR_TYPE_FOOTSWITCH, i)
            knob_uri = "/hmi/knob%i"       % (i+1)
            foot_uri = "/hmi/footswitch%i" % (i+1)

            self._hw2uri_map[knob_hw]  = knob_uri
            self._hw2uri_map[foot_hw]  = foot_uri
            self._uri2hw_map[knob_uri] = knob_hw
            self._uri2hw_map[foot_uri] = foot_hw

    # -----------------------------------------------------------------------------------------------------------------

    def _addressing_load(self, actuator_uri, callback=None):
        addressings       = self.addressings[actuator_uri]
        addressings_addrs = addressings['addrs']
        addressings_idx   = addressings['idx']

        try:
            addressing = addressings_addrs[addressings_idx]
        except IndexError:
            return

        actuator_hw = self._uri2hw_map[actuator_uri]

        self.hmi.control_add(addressing['instance_id'], addressing['port'],
                             addressing['label'], addressing['type'], addressing['unit'],
                             addressing['value'], addressing['maximum'], addressing['minimum'], addressing['steps'],
                             actuator_hw[0], actuator_hw[1], actuator_hw[2], actuator_hw[3],
                             len(addressings_addrs), # num controllers
                             addressings_idx+1,      # index
                             addressing['options'], callback)

    def _address_next(self, actuator_hw, callback):
        actuator_uri = self._hw2uri_map[actuator_hw]

        addressings       = self.addressings[actuator_uri]
        addressings_addrs = addressings['addrs']
        addressings_idx   = addressings['idx']

        if len(addressings_addrs) > 0:
            addressings['idx'] = (addressings['idx'] + 1) % len(addressings_addrs)
            callback(True)
            self._addressing_load(actuator_uri)
        else:
            callback(True)
            self.hmi.control_clean(actuator_hw[0], actuator_hw[1], actuator_hw[2], actuator_hw[3])

    def _unaddress(self, pluginData, port):
        addressing = pluginData['addressing'].pop(port, None)
        if addressing is None:
            return None

        actuator_uri      = addressing['actuator_uri']
        addressings       = self.addressings[actuator_uri]
        addressings_addrs = addressings['addrs']
        addressings_idx   = addressings['idx']

        index = addressings_addrs.index(addressing)
        addressings_addrs.pop(index)

        # FIXME ?
        if addressings_idx >= index:
            addressings['idx'] -= 1
        #if index <= addressings_idx:
            #addressings['idx'] = addressings_idx - 1

        return actuator_uri

    # -----------------------------------------------------------------------------------------------------------------
    # HMI callbacks, called by HMI via serial

    def hmi_hardware_connected(self, hardware_type, hardware_id, callback):
        logging.info("hmi hardware connected")
        callback(True)

    def hmi_hardware_disconnected(self, hardware_type, hardware_id, callback):
        logging.info("hmi hardware disconnected")
        callback(True)

    def hmi_list_banks(self, callback):
        logging.info("hmi list banks")
        self.banks = list_banks()
        banks = " ".join('"%s" %d' % (bank['title'], i) for i,bank in enumerate(self.banks))
        callback(True, banks)

    def hmi_list_bank_pedalboards(self, bank_id, callback):
        logging.info("hmi list bank pedalboards")
        if bank_id < len(self.banks):
            #pedalboards = " ".join('"%s" %d' % (pb['title'], i) for i,pb in enumerate(self.banks[bank_id]['pedalboards']))
            pedalboards = " ".join('"%s" "%s"' % (pb['title'], pb['uri']) for pb in self.banks[bank_id]['pedalboards'])
        else:
            pedalboards = ""
        callback(True, pedalboards)

    def hmi_load_bank_pedalboard(self, bank_id, pedalboard_uri, callback):
        logging.info("hmi load bank pedalboard")

        ##if bank_id >= len(self.banks):
            ##print("ERROR in addressing.py: bank id out of bounds")
            ##return

        ##pedalboards = self.banks[bank_id]['pedalboards']
        ##if pedalboard_id >= len(pedalboards):
            ##print("ERROR in addressing.py: pedalboard id out of bounds")
            ##return

        ##uri = pedalboards[pedalboard_id]['uri']

        #self.host.load_uri(pedalboard_uri)

    def hmi_parameter_get(self, instance_id, portsymbol, callback):
        logging.info("hmi parameter get")
        callback(self.plugins[instance_id]['ports'][portsymbol])

    def hmi_parameter_set(self, instance_id, portsymbol, value, callback):
        logging.info("hmi parameter set")
        instance = self.mapper.get_instance(instance_id)

        if portsymbol == ":bypass":
            bypassed = bool(value)
            self.plugins[instance_id]['bypassed'] = bypassed

            def host_callback(ok):
                self.msg_callback("bypass %s %d" % (instance, int(bypassed)))
                callback(ok)

            self.send("bypass %d %d" % (instance_id, int(bypassed)), host_callback, datatype='boolean')

        else:
            self.plugins[instance_id]['ports'][portsymbol] = value

            def host_callback(ok):
                self.msg_callback("param_set %s %s %f" % (instance, portsymbol, value))
                callback(ok)

            self.send("param_set %d %s %f" % (instance_id, portsymbol, value), callback, datatype='boolean')

    def hmi_parameter_addressing_next(self, hardware_type, hardware_id, actuator_type, actuator_id, callback):
        logging.info("hmi parameter addressing next")
        actuator_hw = (hardware_type, hardware_id, actuator_type, actuator_id)
        self._address_next(actuator_hw, callback)

    # -----------------------------------------------------------------------------------------------------------------
    # JACK stuff

    def get_sample_rate(self):
        return float(jacklib.get_sample_rate(self.jack_client))

    # Get list of Hardware MIDI devices
    # returns (devsInUse, devList, names)
    def get_midi_ports(self):
        if self.jack_client is None:
            return ([], [], {})

        out_ports = {}
        full_ports = {}

        # MIDI Out
        ports = charPtrPtrToStringList(jacklib.get_ports(self.jack_client, "system:", jacklib.JACK_DEFAULT_MIDI_TYPE, jacklib.JackPortIsPhysical|jacklib.JackPortIsInput))
        for port in ports:
            ret, alias1, alias2 = jacklib.port_get_aliases(jacklib.port_by_name(self.jack_client, port))
            if ret == 1 and alias1:
                title = alias1.split("-",5)[-1].replace("-"," ")
                out_ports[title] = port

        # MIDI In
        ports = charPtrPtrToStringList(jacklib.get_ports(self.jack_client, "system:", jacklib.JACK_DEFAULT_MIDI_TYPE, jacklib.JackPortIsPhysical|jacklib.JackPortIsOutput))
        for port in ports:
            ret, alias1, alias2 = jacklib.port_get_aliases(jacklib.port_by_name(self.jack_client, port))
            if ret == 1 and alias1:
                title = alias1.split("-",5)[-1].replace("-"," ")
                if title in out_ports.keys():
                    port = "%s;%s" % (port, out_ports[title])
                full_ports[port] = title

        devsInUse = []
        devList = []
        names = {}
        for port, alias in full_ports.items():
            devList.append(port)
            if port in self.midiports:
                devsInUse.append(port)
            names[port] = alias + (" (in+out)" if alias in out_ports else " (in)")

        devList.sort()
        return (devsInUse, devList, names)

    # Set the selected MIDI devices
    # Will remove or add new JACK ports (in mod-ui) as needed
    def set_midi_devices(self, newDevs):
        if self.jack_client is None:
            return

        out_ports = {}
        full_ports = {}

        # MIDI Out
        ports = charPtrPtrToStringList(jacklib.get_ports(self.jack_client, "system:", jacklib.JACK_DEFAULT_MIDI_TYPE, jacklib.JackPortIsPhysical|jacklib.JackPortIsInput))
        for port in ports:
            ret, alias1, alias2 = jacklib.port_get_aliases(jacklib.port_by_name(self.jack_client, port))
            if ret == 1 and alias1:
                title = alias1.split("-",5)[-1].replace("-"," ")
                out_ports[title] = port

        # MIDI In
        ports = charPtrPtrToStringList(jacklib.get_ports(self.jack_client, "system:", jacklib.JACK_DEFAULT_MIDI_TYPE, jacklib.JackPortIsPhysical|jacklib.JackPortIsOutput))
        for port in ports:
            ret, alias1, alias2 = jacklib.port_get_aliases(jacklib.port_by_name(self.jack_client, port))
            if ret == 1 and alias1:
                title = alias1.split("-",5)[-1].replace("-"," ")
                if title in out_ports.keys():
                    port = "%s;%s" % (port, out_ports[title])
                full_ports[port] = title

        # remove
        #for port in self.midiports:
            #if port in newDevs:
                #continue
            #if dev.startswith("MIDI Port-"):
                #continue
            #dev, modes = dev.rsplit(" (",1)
            #jacklib.disconnect(self.jack_client, "alsa_midi:%s in" % dev, self.backend_client_name+":control_in")

            #def remove_external_port_in(callback):
                #self.host.remove_external_port(dev+" in")
                #callback(True)
            #def remove_external_port_out(callback):
                #self.host.remove_external_port(dev+" out")
                #callback(True)

            #yield gen.Task(remove_external_port_in)

            #if "out" in modes:
                #yield gen.Task(remove_external_port_out)

        ## add
        #for dev in newDevs:
            #if dev in curDevs:
                #continue
            #dev, modes = dev.rsplit(" (",1)

            #def add_external_port_in(callback):
                #self.host.add_external_port(dev+" in", "Input", "MIDI")
                #callback(True)
            #def add_external_port_out(callback):
                #self.host.add_external_port(dev+" out", "Output", "MIDI")
                #callback(True)

            #yield gen.Task(add_external_port_in)

            #if "out" in modes:
                #yield gen.Task(add_external_port_out)

    # Callback for when a port appears or disappears
    # We use this to trigger a auto-connect mode
    #def JackPortRegistrationCallback(self, port, registered, arg):
        #if self.jack_client is None:
            #return
        #if not registered:
            #return

    # Callback for when a client or port property changes.
    # We use this to know the full length name of ingen created ports.
    def JackPropertyChangeCallback(self, subject, key, change, arg):
        if self.jack_client is None:
            return
        if change != jacklib.PropertyCreated:
            return
        if key != jacklib.bJACK_METADATA_PRETTY_NAME:
            return

        self.mididevuuids.append(subject)
        self.ioloop.add_callback(self.jack_midi_devs_callback)

    # Callback for when an xrun occurs
    def JackXRunCallback(self, arg):
        self.xrun_count += 1
        return 0

    # Callback for when JACK has shutdown or our client zombified
    def JackShutdownCallback(self, arg):
        self.jack_client = None

    # -----------------------------------------------------------------------------------------------------------------
    # ...

    # -----------------------------------------------------------------------------------------------------------------
    # ...
