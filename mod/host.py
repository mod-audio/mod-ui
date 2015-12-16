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

from tornado import gen, iostream, ioloop
from shutil import rmtree
import os, json, socket, logging

from mod import get_hardware, symbolify
from mod.bank import list_banks, save_last_bank_and_pedalboard
from mod.jacklib_helpers import jacklib, charPtrToString, charPtrPtrToStringList
from mod.protocol import Protocol, ProtocolError, process_resp
from mod.utils import is_bundle_loaded, add_bundle_to_lilv_world, remove_bundle_from_lilv_world, rescan_plugin_presets
from mod.utils import get_plugin_info, get_plugin_control_input_ports, get_pedalboard_info, get_state_port_values

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
        self.hasSerialMidiIn = False
        self.hasSerialMidiOut = False
        self.pedalboard_name = ""
        self.pedalboard_size = [0,0]

        self.jack_client = None
        self.xrun_count = 0
        self.xrun_count2 = 0

        self.cputimerok = True
        self.cputimer = ioloop.PeriodicCallback(self.cputimer_callback, 1000)

        if os.path.exists("/proc/meminfo"):
            self.memfile  = open("/proc/meminfo", 'r')
            self.memtotal = 0.0
            self.memfseek = 0

            for line in self.memfile.readlines():
                if line.startswith("MemTotal:"):
                    self.memtotal = float(int(line.replace("MemTotal:","",1).replace("kB","",1).strip()))
                elif line.startswith("MemFree:"):
                    break
                self.memfseek += len(line)
            else:
                self.memfseek = 0

            if self.memtotal != 0.0 and self.memfseek != 0:
                self.memtimer = ioloop.PeriodicCallback(self.memtimer_callback, 5000)

        else:
            self.memtimer = None

        self.msg_callback = lambda msg:None

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
        self.open_connection_if_needed(None, lambda ws:None)

    def open_connection_if_needed(self, websocket, callback):
        if self.sock is not None:
            callback(websocket)
            return

        self.sock = iostream.IOStream(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
        self._idle = False

        def check_response():
            self.connected = True
            callback(websocket)
            self.cputimerok = True
            self.cputimer_callback()
            self.cputimer.start()

            if self.memtimer is not None:
                self.memtimer_callback()
                self.memtimer.start()

            if len(self._queue):
                self.process_queue()
            else:
                self._idle = True

        self.sock.set_close_callback(self.connection_closed)
        self.sock.connect(self.addr, check_response)

    def connection_closed(self):
        self.sock = None
        self.crashed = True
        self.cputimer.stop()

        if self.memtimer is not None:
            self.memtimer.stop()

        self.msg_callback("disconnected")

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

            if datatype == 'string':
                r = resp
            elif not resp.startswith("resp"):
                logging.error("[host] protocol error: %s" % ProtocolError(resp))
                r = None
            else:
                r = resp.replace("resp ", "").replace("\0", "").strip()

            callback(process_resp(r, datatype))
            self.process_queue()

        self._idle = False
        logging.info("[host] sending -> %s" % msg)

        if self.sock is None:
            return

        encmsg = "%s\0" % str(msg)
        self.sock.write(encmsg.encode("utf-8"))
        self.sock.read_until(b"\0", check_response)

    def send(self, msg, callback, datatype='int'):
        self._queue.append((msg, callback, datatype))
        if self._idle:
            self.process_queue()

    # -----------------------------------------------------------------------------------------------------------------
    # Host stuff

    def initial_setup(self, callback):
        self.send("remove -1", callback, datatype='boolean')

    def report_current_state(self, websocket):
        if websocket is None:
            return

        websocket.write_message("wait_start")

        crashed = self.crashed
        self.crashed = False

        if crashed:
            self.init_jack()

        # Audio In
        for i in range(len(self.audioportsIn)):
            name  = self.audioportsIn[i]
            title = name.title().replace(" ","_")
            websocket.write_message("add_hw_port /graph/%s audio 0 %s %i" % (name, title, i+1))

        # Audio Out
        for i in range(len(self.audioportsOut)):
            name  = self.audioportsOut[i]
            title = name.title().replace(" ","_")
            websocket.write_message("add_hw_port /graph/%s audio 1 %s %i" % (name, title, i+1))

        if self.jack_client is not None:
            midiports = []
            for port in self.midiports:
                if ";" in port:
                    inp, outp = port.split(";",1)
                    midiports.append(inp)
                    midiports.append(outp)
                else:
                    midiports.append(port)

            self.hasSerialMidiIn  = bool(jacklib.port_by_name(self.jack_client, "ttymidi:MIDI_in"))
            self.hasSerialMidiOut = bool(jacklib.port_by_name(self.jack_client, "ttymidi:MIDI_out"))

            # MIDI In
            if self.hasSerialMidiIn:
                websocket.write_message("add_hw_port /graph/serial_midi_in midi 0 Serial_MIDI_In 0")

            ports = charPtrPtrToStringList(jacklib.get_ports(self.jack_client, "system:", jacklib.JACK_DEFAULT_MIDI_TYPE, jacklib.JackPortIsPhysical|jacklib.JackPortIsOutput))
            for i in range(len(ports)):
                name = ports[i]
                if name not in midiports:
                    continue
                ret, alias1, alias2 = jacklib.port_get_aliases(jacklib.port_by_name(self.jack_client, name))
                if ret == 1 and alias1:
                    title = alias1.split("-",5)[-1].replace("-","_")
                else:
                    title = name.replace("system:","",1).title().replace(" ","_")
                websocket.write_message("add_hw_port /graph/%s midi 0 %s %i" % (name.replace("system:","",1), title, i+1))

            # MIDI Out
            if self.hasSerialMidiOut:
                websocket.write_message("add_hw_port /graph/serial_midi_out midi 1 Serial_MIDI_Out 0")

            ports = charPtrPtrToStringList(jacklib.get_ports(self.jack_client, "system:", jacklib.JACK_DEFAULT_MIDI_TYPE, jacklib.JackPortIsPhysical|jacklib.JackPortIsInput))
            for i in range(len(ports)):
                name = ports[i]
                if name not in midiports:
                    continue
                ret, alias1, alias2 = jacklib.port_get_aliases(jacklib.port_by_name(self.jack_client, name))
                if ret == 1 and alias1:
                    title = alias1.split("-",5)[-1].replace("-","_")
                else:
                    title = name.replace("system:","",1).title().replace(" ","_")
                websocket.write_message("add_hw_port /graph/%s midi 1 %s %i" % (name.replace("system:","",1), title, i+1))

        for instance_id, plugin in self.plugins.items():
            websocket.write_message("add %s %s %.1f %.1f %d" % (plugin['instance'], plugin['uri'], plugin['x'], plugin['y'], int(plugin['bypassed'])))

            if crashed:
                self.send("add %s %d" % (plugin['uri'], instance_id), lambda r:None, datatype='int')
                if plugin['bypassed']:
                    self.send("bypass %d 1" % (instance_id,), lambda r:None, datatype='boolean')

            badports = plugin['badports']

            for symbol, value in plugin['ports'].items():
                if symbol not in badports:
                    websocket.write_message("param_set %s %s %f" % (plugin['instance'], symbol, value))

                if crashed:
                    self.send("param_set %d %s %f" % (instance_id, symbol, value), lambda r:None, datatype='boolean')

        for port_from, port_to in self.connections:
            websocket.write_message("connect %s %s" % (port_from, port_to))

            if crashed:
                self.send("connect %s %s" % (self._fix_host_connection_port(port_from),
                                             self._fix_host_connection_port(port_to)), lambda r:None, datatype='boolean')

        websocket.write_message("wait_end")

    # -----------------------------------------------------------------------------------------------------------------
    # Host stuff - add & remove bundles

    def add_bundle(self, bundlepath, callback):
        if is_bundle_loaded(bundlepath):
            print("SKIPPED add_bundle, already in world")
            callback([])
            return

        def host_callback(ok):
            plugins = add_bundle_to_lilv_world(bundlepath)
            callback(plugins)

        self.send("bundle_add \"%s\"" % bundlepath.replace('"','\\"'), host_callback, datatype='boolean')

    def remove_bundle(self, bundlepath, callback):
        if not is_bundle_loaded(bundlepath):
            print("SKIPPED remove_bundle, not in world")
            callback([])
            return

        def host_callback(ok):
            plugins = remove_bundle_from_lilv_world(bundlepath)
            callback(plugins)

        self.send("bundle_remove \"%s\"" % bundlepath.replace('"','\\"'), host_callback, datatype='boolean')

    # -----------------------------------------------------------------------------------------------------------------
    # Host stuff - reset, add, remove

    def reset(self, callback, resetBanks=True):
        if resetBanks:
            self.banks = []

        self.plugins = {}
        self.connections = []
        self.mapper.clear()
        self._init_addressings()

        def host_callback(ok):
            callback(ok)
            self.msg_callback("remove :all")

        save_last_bank_and_pedalboard(-1, "")
        self.send("remove -1", host_callback, datatype='boolean')

    def add_plugin(self, instance, uri, x, y, callback):
        instance_id = self.mapper.get_id(instance)

        def host_callback(resp):
            if resp < 0:
                callback(resp)
                return
            bypassed = False

            allports = get_plugin_control_input_ports(uri)
            badports = []
            valports = {}

            for port in allports:
                valports[port['symbol']] = port['ranges']['default']

                # skip notOnGUI controls
                if "notOnGUI" in port['properties']:
                    badports.append(port['symbol'])

                # skip special designated controls
                elif port['designation'] in ("http://lv2plug.in/ns/lv2core#freeWheeling",
                                             "http://lv2plug.in/ns/lv2core#latency",
                                             "http://lv2plug.in/ns/ext/parameters#sampleRate"):
                    badports.append(port['symbol'])

            self.plugins[instance_id] = {
                "instance"  : instance,
                "uri"       : uri,
                "bypassed"  : bypassed,
                "x"         : x,
                "y"         : y,
                "addressing": {}, # symbol: addressing
                "ports"     : valports,
                "badports"  : badports,
            }

            callback(resp)
            self.msg_callback("add %s %s %.1f %.1f %d" % (instance, uri, x, y, int(bypassed)))

        self.send("add %s %d" % (uri, instance_id), host_callback, datatype='int')

    @gen.coroutine
    def remove_plugin(self, instance, callback):
        instance_id = self.mapper.get_id_without_creating(instance)

        try:
            data = self.plugins.pop(instance_id)
        except KeyError:
            callback(False)
            return

        used_actuators = []
        for symbol in [symbol for symbol in data['addressing'].keys()]:
            actuator_uri = self._unaddress(data, symbol)

            if actuator_uri is not None and actuator_uri not in used_actuators:
                used_actuators.append(actuator_uri)

        for actuator_uri in used_actuators:
            actuator_hw = self._uri2hw_map[actuator_uri]
            yield gen.Task(self._address_next, actuator_hw)

        def host_callback(ok):
            callback(ok)
            removed_connections = []
            for ports in self.connections:
                if ports[0].startswith(instance) or ports[1].startswith(instance):
                    removed_connections.append(ports)
            for ports in removed_connections:
                self.connections.remove(ports)
                self.msg_callback("disconnect %s %s" % (ports[0], ports[1]))

            self.msg_callback("remove %s" % (instance))

        def hmi_callback(ok):
            self.send("remove %d" % instance_id, host_callback, datatype='boolean')

        self.hmi.control_rm(instance_id, ":all", hmi_callback)

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

    def preset_load(self, instance, uri, callback):
        instance_id = self.mapper.get_id_without_creating(instance)

        @gen.coroutine
        def preset_callback(state):
            if not state:
                callback(False)
                return

            portValues = get_state_port_values(state)
            self.plugins[instance_id]['ports'].update(portValues)

            badports = self.plugins[instance_id]['badports']
            used_actuators = []

            for symbol, value in self.plugins[instance_id]['ports'].items():
                if symbol in badports:
                    continue

                self.msg_callback("param_set %s %s %f" % (instance, symbol, value))

                addressing = self.plugins[instance_id]['addressing'].get(symbol, None)
                if addressing is not None and addressing['actuator_uri'] not in used_actuators:
                    used_actuators.append(addressing['actuator_uri'])

            for actuator_uri in used_actuators:
                actuator_hw = self._uri2hw_map[actuator_uri]
                yield gen.Task(self._address_next, actuator_hw)

            callback(True)

        def host_callback(ok):
            if not ok:
                callback(False)
                return
            self.send("preset_show %s" % uri, preset_callback, datatype='string')

        print("preset_load %d %s" % (instance_id, uri))
        self.send("preset_load %d %s" % (instance_id, uri), host_callback, datatype='boolean')

    def preset_save(self, instance, label, callback):
        instance_id  = self.mapper.get_id_without_creating(instance)
        labelsymbol  = symbolify(label)
        presetbundle = os.path.expanduser("~/.lv2/%s-%s.lv2") % (instance.replace("/graph/","",1), labelsymbol)
        plugin_uri   = self.plugins[instance_id]['uri']

        def host_callback(ok):
            if not ok:
                callback({
                    'ok': False,
                })
                return

            def preset_callback(ok):
                callback({
                    'ok' : True,
                    'uri': "file://%s.ttl" % os.path.join(presetbundle, labelsymbol)
                })
                print("uri saved as 'file://%s.ttl'" % os.path.join(presetbundle, labelsymbol))

            self.add_bundle(presetbundle, preset_callback)

            # rescan presets next time the plugin is loaded
            rescan_plugin_presets(plugin_uri)

        def start(ok):
            if os.path.exists(presetbundle):
                rmtree(presetbundle)

            print("preset_save %d \"%s\" %s %s.ttl" % (instance_id, label.replace('"','\\"'), presetbundle, labelsymbol))
            self.send("preset_save %d \"%s\" %s %s.ttl" % (instance_id, label.replace('"','\\"'), presetbundle, labelsymbol), host_callback, datatype='boolean')

        if os.path.exists(presetbundle):
            self.remove_bundle(presetbundle, start)

            # if presetbundle already exists, generate a new random bundle path
            #from random import randint
            #while True:
                #presetbundle = os.path.expanduser("~/.lv2/%s-%s-%i.lv2" % (instance.replace("/graph/","",1), labelsymbol, randint(1,99999)))
                #if os.path.exists(presetbundle):
                    #continue
                #break
        else:
            start(True)

    def set_position(self, instance, x, y):
        instance_id = self.mapper.get_id_without_creating(instance)

        self.plugins[instance_id]['x'] = x
        self.plugins[instance_id]['y'] = y

    # -----------------------------------------------------------------------------------------------------------------
    # Host stuff - connections

    def _fix_host_connection_port(self, port):
        data = port.split("/")

        if len(data) == 3:
            if data[2] == "serial_midi_in":
                return "ttymidi:MIDI_in"
            if data[2] == "serial_midi_out":
                return "ttymidi:MIDI_out"
            return "system:%s" % data[2]

        instance    = "/graph/%s" % data[2]
        portsymbol  = data[3]
        instance_id = self.mapper.get_id_without_creating(instance)
        return "effect_%d:%s" % (instance_id, portsymbol)

    def connect(self, port_from, port_to, callback):
        def host_callback(ok):
            callback(ok)
            if ok:
                self.connections.append((port_from, port_to))
                self.msg_callback("connect %s %s" % (port_from, port_to))

        self.send("connect %s %s" % (self._fix_host_connection_port(port_from),
                                     self._fix_host_connection_port(port_to)), host_callback, datatype='boolean')

    def disconnect(self, port_from, port_to, callback):
        def host_callback(ok):
            callback(ok)
            if ok:
                try:
                    self.connections.remove((port_from, port_to))
                except:
                    pass
                self.msg_callback("disconnect %s %s" % (port_from, port_to))

        self.send("disconnect %s %s" % (self._fix_host_connection_port(port_from),
                                        self._fix_host_connection_port(port_to)), host_callback, datatype='boolean')

    # -----------------------------------------------------------------------------------------------------------------
    # Host stuff - load & save

    def load(self, bundlepath, bank_id):
        self.msg_callback("wait_start")

        pb = get_pedalboard_info(bundlepath)

        for p in pb['plugins']:
            instance    = "/graph/%s" % p['instance']
            instance_id = self.mapper.get_id(instance)

            self.send("add %s %d" % (p['uri'], instance_id), lambda r:None)

            if p['bypassed']:
                self.send("bypass %d 1" % (instance_id,), lambda r:None)

            allports = get_plugin_control_input_ports(p['uri'])
            badports = []
            valports = {}

            for port in allports:
                valports[port['symbol']] = port['ranges']['default']

                # skip notOnGUI controls
                if "notOnGUI" in port['properties']:
                    badports.append(port['symbol'])

                # skip special designated controls
                elif port['designation'] in ("http://lv2plug.in/ns/lv2core#freeWheeling",
                                             "http://lv2plug.in/ns/lv2core#latency",
                                             "http://lv2plug.in/ns/ext/parameters#sampleRate"):
                    badports.append(port['symbol'])

            self.plugins[instance_id] = {
                "instance"  : instance,
                "uri"       : p['uri'],
                "bypassed"  : p['bypassed'],
                "x"         : p['x'],
                "y"         : p['y'],
                "addressing": {}, # filled in later in _load_addressings()
                "ports"     : valports,
                "badports"  : badports,
            }
            self.msg_callback("add %s %s %.1f %.1f %d" % (instance, p['uri'], p['x'], p['y'], int(p['bypassed'])))

            for port in p['ports']:
                symbol = port['symbol']
                value  = port['value']
                self.plugins[instance_id]['ports'][symbol] = value

                self.send("param_set %d %s %f" % (instance_id, symbol, value), lambda r:None)

                if symbol not in badports:
                    self.msg_callback("param_set %s %s %f" % (instance, symbol, value))

        for c in pb['connections']:
            port_from = "/graph/%s" % c['source']
            port_to   = "/graph/%s" % c['target']
            self.send("connect %s %s" % (self._fix_host_connection_port(port_from), self._fix_host_connection_port(port_to)), lambda r:None)

            self.connections.append((port_from, port_to))
            self.msg_callback("connect %s %s" % (port_from, port_to))

        self._load_addressings(bundlepath)

        self.msg_callback("wait_end")

        save_last_bank_and_pedalboard(bank_id, bundlepath)

        return pb['title']

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
    lv2:name "Control In" ;
    lv2:portProperty lv2:connectionOptional ;
    lv2:symbol "control_in" ;
    <http://lv2plug.in/ns/ext/resize-port#minimumSize> 4096 ;
    a atom:AtomPort ,
        lv2:InputPort .

<control_out>
    atom:bufferType atom:Sequence ;
    lv2:index 1 ;
    lv2:name "Control Out" ;
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
""" % (port, index, port.title().replace("_"," "), port)

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
""" % (port, index, port.title().replace("_"," "), port)

        # Ports (MIDI In)
        for port in midiportsIn:
            sname  = port.replace("system:","",1)
            index += 1
            ports += """
<%s>
    atom:bufferType atom:Sequence ;
    atom:supports midi:MidiEvent ;
    lv2:index %i ;
    lv2:name "%s" ;
    lv2:portProperty lv2:connectionOptional ;
    lv2:symbol "%s" ;
    <http://lv2plug.in/ns/ext/resize-port#minimumSize> 4096 ;
    a atom:AtomPort ,
        lv2:InputPort .
""" % (sname, index, self.get_port_name_alias(port), sname)

        # Ports (MIDI Out)
        for port in midiportsOut:
            sname  = port.replace("system:","",1)
            index += 1
            ports += """
<%s>
    atom:bufferType atom:Sequence ;
    atom:supports midi:MidiEvent ;
    lv2:index %i ;
    lv2:name "%s" ;
    lv2:portProperty lv2:connectionOptional ;
    lv2:symbol "%s" ;
    <http://lv2plug.in/ns/ext/resize-port#minimumSize> 4096 ;
    a atom:AtomPort ,
        lv2:OutputPort .
""" % (sname, index, self.get_port_name_alias(port), sname)

        # Serial MIDI In
        if self.hasSerialMidiIn:
            index += 1
            ports += """
<serial_midi_in>
    atom:bufferType atom:Sequence ;
    atom:supports midi:MidiEvent ;
    lv2:index %i ;
    lv2:name "Serial MIDI In" ;
    lv2:portProperty lv2:connectionOptional ;
    lv2:symbol "serial_midi_in" ;
    <http://lv2plug.in/ns/ext/resize-port#minimumSize> 4096 ;
    a atom:AtomPort ,
        lv2:InputPort .
""" % index

        # Serial MIDI Out
        if self.hasSerialMidiOut:
            index += 1
            ports += """
<serial_midi_out>
    atom:bufferType atom:Sequence ;
    atom:supports midi:MidiEvent ;
    lv2:index %i ;
    lv2:name "Serial MIDI In" ;
    lv2:portProperty lv2:connectionOptional ;
    lv2:symbol "serial_midi_out" ;
    <http://lv2plug.in/ns/ext/resize-port#minimumSize> 4096 ;
    a atom:AtomPort ,
        lv2:OutputPort .
""" % index

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
        portsyms = ["control_in","control_out"]
        if self.hasSerialMidiIn:
            portsyms.append("serial_midi_in")
        if self.hasSerialMidiOut:
            portsyms.append("serial_midi_out")
        portsyms += [p.replace("system:","",1) for p in midiportsIn ]
        portsyms += [p.replace("system:","",1) for p in midiportsOut]
        pbdata += "    lv2:port <%s> ;\n" % ("> ,\n             <".join(portsyms+self.audioportsIn+self.audioportsOut))

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
                self.cputimer.stop()
                return
            self.msg_callback("cpu_load %0.1f" % resp['value'])
            self.cputimerok = True

        self.cputimerok = False
        self.send("cpu_load", cpu_callback, datatype='float_structure')

    def memtimer_callback(self):
        if not self.memfile:
            return

        self.memfile.seek(self.memfseek)
        memfree  = float(int(self.memfile.readline().replace("MemFree:","",1).replace("kB","",1).strip()))
        memfree += float(int(self.memfile.readline().replace("Buffers:","",1).replace("kB","",1).strip()))
        memfree += float(int(self.memfile.readline().replace("Cached:" ,"",1).replace("kB","",1).strip()))

        self.msg_callback("mem_load %0.1f" % ((self.memtotal-memfree)/self.memtotal*100.0))

    # -----------------------------------------------------------------------------------------------------------------
    # Addressing (public stuff)

    def address(self, instance, port, actuator_uri, label, maximum, minimum, value, steps, callback, skipLoad=False):
        instance_id = self.mapper.get_id(instance)

        data = self.plugins.get(instance_id, None)
        if data is None:
            callback(False)
            return

        old_actuator_uri = self._unaddress(data, port)

        if actuator_uri and actuator_uri != "null":
            # we're addressing
            options = []

            if port == ":bypass":
                ctype = ADDRESSING_CTYPE_BYPASS
                unit  = "none"

            else:
                for port_info in get_plugin_control_input_ports(data["uri"]):
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

                # FIXME: make fw accept scalepoints without enumeration
                if len(port_info["scalePoints"]) > 0 and "enumeration" in pprops:
                    ctype |= ADDRESSING_CTYPE_SCALE_POINTS|ADDRESSING_CTYPE_ENUMERATION

                    #if len(port_info["scalePoints"]) > 1 and "enumeration" in pprops:
                        #ctype |= ADDRESSING_CTYPE_ENUMERATION

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

            #if old_actuator_uri is not None:
                #def nextStepAddressing(ok):
                    #self._addressing_load(actuator_uri, callback)
                #self._addressing_load(old_actuator_uri, nextStepAddressing)

            #else:
            if not skipLoad:
                self._addressing_load(actuator_uri, callback, value)

        else:
            # we're unaddressing
            if old_actuator_uri is not None:
                def nextStepUnaddressing(ok):
                    old_actuator_hw = self._uri2hw_map[old_actuator_uri]
                    self._address_next(old_actuator_hw, callback)
                self.hmi.control_rm(instance_id, port, nextStepUnaddressing)

            else:
                self.hmi.control_rm(instance_id, port, callback)

    def get_addressings(self):
        if len(self.addressings) == 0:
            return {}
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

    def _addressing_load(self, actuator_uri, callback, value=None):
        addressings       = self.addressings[actuator_uri]
        addressings_addrs = addressings['addrs']
        addressings_idx   = addressings['idx']

        try:
            addressing = addressings_addrs[addressings_idx]
        except IndexError:
            return

        actuator_hw = self._uri2hw_map[actuator_uri]

        if value is not None:
            curvalue = value
        elif addressing['port'] == ":bypass":
            curvalue = 1.0 if self.plugins[addressing['instance_id']]['bypassed'] else 0.0
        else:
            curvalue = self.plugins[addressing['instance_id']]['ports'][addressing['port']]

        self.hmi.control_add(addressing['instance_id'], addressing['port'],
                             addressing['label'], addressing['type'], addressing['unit'],
                             curvalue, addressing['maximum'], addressing['minimum'], addressing['steps'],
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
            self._addressing_load(actuator_uri, callback)
        else:
            self.hmi.control_clean(actuator_hw[0], actuator_hw[1], actuator_hw[2], actuator_hw[3], callback)

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

    @gen.coroutine
    def _load_addressings(self, bundlepath):
        datafile = os.path.join(bundlepath, "addressings.json")
        if not os.path.exists(datafile):
            return

        with open(datafile, 'r') as fh:
            data = fh.read()
        data = json.loads(data)

        used_actuators = []

        for actuator_uri in data:
            for addr in data[actuator_uri]:
                instance_id = self.mapper.get_id_without_creating(addr['instance'])
                if addr['port'] == ":bypass":
                    curvalue = 1.0 if self.plugins[instance_id]['bypassed'] else 0.0
                else:
                    curvalue = self.plugins[instance_id]['ports'][addr['port']]

                self.address(addr["instance"], addr["port"], actuator_uri, addr["label"], addr["maximum"], addr["minimum"], curvalue, addr["steps"], lambda r:None, True)

                if actuator_uri not in used_actuators:
                    used_actuators.append(actuator_uri)

        for actuator_uri in used_actuators:
            actuator_hw = self._uri2hw_map[actuator_uri]
            yield gen.Task(self._address_next, actuator_hw)

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
        banks = " ".join('"%s" %d' % (bank['title'], i) for i, bank in enumerate(self.banks))
        callback(True, banks)

    def hmi_list_bank_pedalboards(self, bank_id, callback):
        logging.info("hmi list bank pedalboards")
        if bank_id < len(self.banks):
            pedalboards = " ".join('"%s" "%s"' % (pb['title'], pb['bundle']) for pb in self.banks[bank_id]['pedalboards'])
        else:
            pedalboards = ""
        callback(True, pedalboards)

    def hmi_load_bank_pedalboard(self, bank_id, bundlepath, callback):
        logging.info("hmi load bank pedalboard")
        def clear_callback(ok):
            self.load(bundlepath, bank_id)
            callback(True)

        def reset_callback(ok):
            self.hmi.clear(clear_callback)

        self.reset(reset_callback, False)

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
                callback(ok)
                self.msg_callback("param_set %s :bypass %f" % (instance, 1.0 if bypassed else 0.0))

            self.send("bypass %d %d" % (instance_id, int(bypassed)), host_callback, datatype='boolean')

        else:
            self.plugins[instance_id]['ports'][portsymbol] = value

            def host_callback(ok):
                callback(ok)
                self.msg_callback("param_set %s %s %f" % (instance, portsymbol, value))

            self.send("param_set %d %s %f" % (instance_id, portsymbol, value), host_callback, datatype='boolean')

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

    def get_port_name_alias(self, portname):
        if self.jack_client is not None:
            ret, alias1, alias2 = jacklib.port_get_aliases(jacklib.port_by_name(self.jack_client, portname))
            if ret == 1 and alias1:
                return alias1.split("-",5)[-1].replace("-"," ")

        return portname.replace("system:","",1).title()

    # Set the selected MIDI devices
    # Will remove or add new JACK ports (in mod-ui) as needed
    def set_midi_devices(self, newDevs):
        def add_port(name, isOutput):
            index = int(name[-1])
            title = self.get_port_name_alias(name).replace("-","_").replace(" ","_")

            self.msg_callback("add_hw_port /graph/%s midi %i %s %i" % (name.replace("system:","",1), int(isOutput), title, index))

        def remove_port(name):
            removed_ports = []

            for ports in self.connections:
                jackports = (self._fix_host_connection_port(ports[0]), self._fix_host_connection_port(ports[1]))
                if name not in jackports:
                    continue
                self.send("disconnect %s %s" % (jackports[0], jackports[1]), lambda r:None, datatype='boolean')
                removed_ports.append(ports)

            for ports in removed_ports:
                self.connections.remove(ports)
                self.msg_callback("disconnect %s %s" % (ports[0], ports[1]))

            self.msg_callback("remove_hw_port /graph/%s" % (name.replace("system:","",1)))

        # remove
        for port in self.midiports:
            if port in newDevs:
                continue

            if ";" in port:
                inp, outp = port.split(";",1)
                remove_port(inp)
                remove_port(outp)
            else:
                remove_port(port)

            self.midiports.remove(port)

        # add
        for port in newDevs:
            if port in self.midiports:
                continue

            if ";" in port:
                inp, outp = port.split(";",1)
                add_port(inp, False)
                add_port(outp, True)
            else:
                add_port(port, False)

            self.midiports.append(port)

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
