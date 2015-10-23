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
import socket, logging

from mod import get_hardware
from mod.bank import list_banks
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
        self.connected = False
        self._queue = []
        self._idle = True
        self.mapper = InstanceIdMapper()
        self.banks = []
        self.connections = []
        self.plugins = {}
        self.pedalboard_name = ""
        self.pedalboard_size = [0,0]

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

        ioloop.IOLoop.instance().add_callback(self.init_connection)

    # -----------------------------------------------------------------------------------------------------------------
    # Initialization

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
        callback(True)

    def get(self, subject):
        if subject == "/graph":
            #def get_port(type, isInput, name):
                #if type == "midi":
                    #types = "<http://lv2plug.in/ns/ext/atom#bufferType> <http://lv2plug.in/ns/ext/atom#Sequence> ;\n"
                    #types += "a <http://lv2plug.in/ns/ext/atom#AtomPort> ,\n"
                #elif type == "audio":
                    #types = "a <http://lv2plug.in/ns/lv2core#AudioPort> ,\n"
                #elif type == "cv":
                    #types = "a <http://lv2plug.in/ns/lv2core#CVPort> ,\n"
                #else:
                    #return
                #if isInput:
                    #types += "<http://lv2plug.in/ns/lv2core#OutputPort>\n"
                #else:
                    #types += "<http://lv2plug.in/ns/lv2core#InputPort>\n"
                #msg = """[]
                #a <http://lv2plug.in/ns/ext/patch#Put> ;
                #<http://lv2plug.in/ns/ext/patch#subject> </graph/system/%s> ;
                #<http://lv2plug.in/ns/ext/patch#body> [
                    #<http://lv2plug.in/ns/lv2core#index> "0"^^<http://www.w3.org/2001/XMLSchema#int> ;
                    #<http://lv2plug.in/ns/lv2core#name> "%s" ;
                    #%s
                #] .
                #""" % (name, name.title().replace("_", " "), types)
                #return msg

            #self.msg_callback(get_port("audio", False, "capture_1"))
            #self.msg_callback(get_port("audio", False, "capture_2"))
            #self.msg_callback(get_port("audio", True, "playback_1"))
            #self.msg_callback(get_port("audio", True, "playback_2"))
            #self.msg_callback(get_port("midi", False, "midi_capture_1"))
            #self.msg_callback(get_port("midi", True, "midi_playback_1"))

            for instance_id, plugin in self.plugins.items():
                self.msg_callback("add %s %s %.1f %.1f %d" % (plugin['instance'], plugin['uri'], plugin['x'], plugin['y'], int(plugin['bypassed'])))

                for symbol, value in plugin['ports'].items():
                    self.msg_callback("param_set %s %s %f" % (plugin['instance'], symbol, value))

            for port_from, port_to in self.connections:
                self.msg_callback("connect %s %s" % (port_from, port_to))

            return

    # -----------------------------------------------------------------------------------------------------------------
    # Host stuff - reset, add, remove

    def reset(self, callback):
        self.banks = []
        self.plugins = {}
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
        if port.startswith("/graph/system/"):
            return port.replace("/graph/system/","system:")

        instance, portsymbol = port.rsplit("/", 1)
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
    # Host stuff - misc

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

    # -----------------------------------------------------------------------------------------------------------------
    # Host stuff - timers

    def cputimer_callback(self):
        if not self.cputimerok:
            return

        #def cpu_callback(resp):
            #if not resp['ok']:
                #return
            #self.msg_callback("cpu_load %0.1f" % resp['value'])
            #self.cputimerok = True

        #self.cputimerok = False
        #self.send("cpu_load", cpu_callback, datatype='float_structure')

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
    # ...

    # -----------------------------------------------------------------------------------------------------------------
    # ...
