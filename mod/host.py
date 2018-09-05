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

from base64 import b64encode
from collections import OrderedDict
from random import randint
from shutil import rmtree
from tornado import gen, iostream, ioloop
import os, json, socket, time, logging

from mod import safe_json_load, symbolify, TextFileFlusher
from mod.addressings import Addressings
from mod.bank import list_banks, get_last_bank_and_pedalboard, save_last_bank_and_pedalboard
from mod.protocol import Protocol, ProtocolError, process_resp
from modtools.utils import (
    charPtrToString, is_bundle_loaded, add_bundle_to_lilv_world, remove_bundle_from_lilv_world, rescan_plugin_presets,
    get_plugin_info, get_plugin_control_inputs_and_monitored_outputs, get_pedalboard_info, get_state_port_values,
    list_plugins_in_bundle, get_all_pedalboards, get_pedalboard_plugin_values, init_jack, close_jack, get_jack_data,
    init_bypass, get_jack_port_alias, get_jack_hardware_ports, has_serial_midi_input_port, has_serial_midi_output_port,
    connect_jack_ports, disconnect_jack_ports, get_truebypass_value, set_util_callbacks, kPedalboardTimeAvailableBPB,
    kPedalboardTimeAvailableBPM, kPedalboardTimeAvailableRolling
)
from mod.settings import (
    APP, LOG, DEFAULT_PEDALBOARD, LV2_PEDALBOARDS_DIR, PEDALBOARD_INSTANCE, PEDALBOARD_INSTANCE_ID, PEDALBOARD_URI,
    TUNER_URI, TUNER_INSTANCE_ID, TUNER_INPUT_PORT, TUNER_MONITOR_PORT
)
from mod.tuner import find_freqnotecents

BANK_CONFIG_NOTHING         = 0
BANK_CONFIG_TRUE_BYPASS     = 1
BANK_CONFIG_PEDALBOARD_UP   = 2
BANK_CONFIG_PEDALBOARD_DOWN = 3

# Special URI for non-addressed controls
kNullAddressURI = "null"

# Special URIs for midi-learn
kMidiLearnURI = "/midi-learn"
kMidiUnlearnURI = "/midi-unlearn"
kMidiCustomPrefixURI = "/midi-custom_" # to show current one

# Limits
kMaxAddressableScalepoints = 50

# TODO: check pluginData['designations'] when doing addressing
# TODO: hmi_save_current_pedalboard does not send browser msgs, needed?
# TODO: finish presets, testing

def get_all_good_pedalboards():
    allpedals  = get_all_pedalboards()
    goodpedals = []

    for pb in allpedals:
        if not pb['broken']:
            goodpedals.append(pb)

    return goodpedals

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

        self.id_map[PEDALBOARD_INSTANCE_ID] = PEDALBOARD_INSTANCE
        self.instance_map[PEDALBOARD_INSTANCE] = PEDALBOARD_INSTANCE_ID

    # get a numeric id from a string instance
    def get_id(self, instance):
        # check if it already exists
        if instance in self.instance_map.keys():
            return self.instance_map[instance]

        # increment last id
        idx = self.last_id
        self.last_id += 1

        # create mapping
        self.instance_map[instance] = idx
        self.id_map[idx] = instance

        # ready
        return self.instance_map[instance]

    def get_id_without_creating(self, instance):
        return self.instance_map[instance]

    # get a string instance from a numeric id
    def get_instance(self, id):
        return self.id_map[id]

class Host(object):
    DESIGNATIONS_INDEX_ENABLED   = 0
    DESIGNATIONS_INDEX_FREEWHEEL = 1
    DESIGNATIONS_INDEX_BPB       = 2
    DESIGNATIONS_INDEX_BPM       = 3
    DESIGNATIONS_INDEX_SPEED     = 4

    def __init__(self, hmi, prefs, msg_callback):
        if False:
            from mod.hmi import HMI
            hmi = HMI()

        self.hmi = hmi
        self.prefs = prefs

        self.addr = ("localhost", 5555)
        self.readsock = None
        self.writesock = None
        self.crashed = False
        self.connected = False
        self.current_tuner_port = 1
        self._queue = []
        self._idle = True
        self.addressings = Addressings()
        self.mapper = InstanceIdMapper()
        self.banks = list_banks()
        self.allpedalboards = None
        self.bank_id = 0
        self.connections = []
        self.audioportsIn = []
        self.audioportsOut = []
        self.midiports = [] # [symbol, alias, pending-connections]
        self.hasSerialMidiIn = False
        self.hasSerialMidiOut = False
        self.pedalboard_empty    = True
        self.pedalboard_modified = False
        self.pedalboard_name     = ""
        self.pedalboard_path     = ""
        self.pedalboard_size     = [0,0]
        self.pedalboard_preset   = -1
        self.pedalboard_presets  = []
        self.next_hmi_pedalboard = None
        self.transport_rolling   = False
        self.transport_bpb       = 4.0
        self.transport_bpm       = 120.0
        self.transport_sync      = "none"
        self.last_data_finish_msg = 0.0
        self.first_transport_rolling = False
        self.processing_pending_flag = False
        self.init_plugins_data()

        if APP and os.getenv("MOD_LIVE_ISO") is not None:
            self.jack_hwin_prefix  = "system:playback_"
            self.jack_hwout_prefix = "system:capture_"
        else:
            self.jack_hwin_prefix  = "mod-monitor:in_"
            self.jack_hwout_prefix = "mod-monitor:out_"

        self.jack_slave_prefix = "mod-slave"

        # checked when saving pedal presets
        self.plugins_added = []
        self.plugins_removed = []

        self.statstimer = ioloop.PeriodicCallback(self.statstimer_callback, 1000)

        if os.path.exists("/proc/meminfo"):
            self.memfile  = open("/proc/meminfo", 'r')
            self.memtotal = 0.0

            self.memfseek_free    = 0
            self.memfseek_buffers = 0
            self.memfseek_cached  = 0
            self.memfseek_shmmem  = 0
            self.memfseek_reclaim = 0

            memfseek = 0

            for line in self.memfile.readlines():
                if line.startswith("MemTotal:"):
                    self.memtotal = float(int(line.replace("MemTotal:","",1).replace("kB","",1).strip()))
                elif line.startswith("MemFree:"):
                    self.memfseek_free = memfseek+9
                elif line.startswith("Buffers:"):
                    self.memfseek_buffers = memfseek+9
                elif line.startswith("Cached:"):
                    self.memfseek_cached = memfseek+8
                elif line.startswith("Shmem:"):
                    self.memfseek_shmmem = memfseek+7
                elif line.startswith("SReclaimable:"):
                    self.memfseek_reclaim = memfseek+14
                memfseek += len(line)

            if self.memtotal != 0.0 and 0 not in (self.memfseek_free,
                                                  self.memfseek_buffers,
                                                  self.memfseek_cached,
                                                  self.memfseek_shmmem,
                                                  self.memfseek_reclaim):
                self.memtimer = ioloop.PeriodicCallback(self.memtimer_callback, 5000)

        else:
            self.memtimer = None

        self.msg_callback = msg_callback

        set_util_callbacks(self.jack_bufsize_changed,
                           self.jack_port_appeared,
                           self.jack_port_deleted,
                           self.true_bypass_changed)

        # Setup addressing callbacks
        self.addressings._task_addressing = self.addr_task_addressing
        self.addressings._task_unaddressing = self.addr_task_unaddressing
        self.addressings._task_get_plugin_data = self.addr_task_get_plugin_data
        self.addressings._task_get_plugin_presets = self.addr_task_get_plugin_presets
        self.addressings._task_get_port_value = self.addr_task_get_port_value
        self.addressings._task_store_address_data = self.addr_task_store_address_data
        self.addressings._task_hw_added = self.addr_task_hw_added
        self.addressings._task_hw_removed = self.addr_task_hw_removed
        self.addressings._task_act_added = self.addr_task_act_added
        self.addressings._task_act_removed = self.addr_task_act_removed

        # Register HMI protocol callbacks
        Protocol.register_cmd_callback("hw_con", self.hmi_hardware_connected)
        Protocol.register_cmd_callback("hw_dis", self.hmi_hardware_disconnected)
        Protocol.register_cmd_callback("banks", self.hmi_list_banks)
        Protocol.register_cmd_callback("pedalboards", self.hmi_list_bank_pedalboards)
        Protocol.register_cmd_callback("pedalboard", self.hmi_load_bank_pedalboard)
        Protocol.register_cmd_callback("control_get", self.hmi_parameter_get)
        Protocol.register_cmd_callback("control_set", self.hmi_parameter_set)
        Protocol.register_cmd_callback("control_next", self.hmi_parameter_addressing_next)
        Protocol.register_cmd_callback("pedalboard_save", self.hmi_save_current_pedalboard)
        Protocol.register_cmd_callback("pedalboard_reset", self.hmi_reset_current_pedalboard)
        Protocol.register_cmd_callback("tuner", self.hmi_tuner)
        Protocol.register_cmd_callback("tuner_input", self.hmi_tuner_input)

        Protocol.register_cmd_callback("get_truebypass_value", self.hmi_get_truebypass_value)
        Protocol.register_cmd_callback("set_truebypass_value", self.hmi_set_truebypass_value)

        Protocol.register_cmd_callback("get_tempo_bpm", self.hmi_get_tempo_bpm)
        Protocol.register_cmd_callback("set_tempo_bpm", self.hmi_set_tempo_bpm)
        Protocol.register_cmd_callback("get_tempo_bpb", self.hmi_get_tempo_bpb)
        Protocol.register_cmd_callback("set_tempo_bpb", self.hmi_set_tempo_bpb)
        
        ioloop.IOLoop.instance().add_callback(self.init_host)

    def __del__(self):
        self.msg_callback("stop")
        self.close_jack()

    def jack_bufsize_changed(self, bufSize):
        self.msg_callback("bufsize %i" % bufSize)

    def jack_port_appeared(self, name, isOutput):
        name = charPtrToString(name)
        isOutput = bool(isOutput)

        if name.startswith(self.jack_slave_prefix+":"):
            name  = name.replace(self.jack_slave_prefix+":","")
            ptype = "midi" if name.startswith("midi_") else "audio"
            index = 100 + int(name.rsplit("_",1)[-1])
            title = name.title().replace(" ","_")
            self.msg_callback("add_hw_port /graph/%s %s %i %s %i" % (name, ptype, int(isOutput), title, index))
            return

        alias = get_jack_port_alias(name)
        if not alias:
            return
        alias = alias.split("-",5)[-1].replace("-"," ").replace(";",".")

        if not isOutput:
            connect_jack_ports(name, "mod-host:midi_in")

        for i in range(len(self.midiports)):
            port_symbol, port_alias, port_conns = self.midiports[i]
            if alias == port_alias or (";" in port_alias and alias in port_alias.split(";",1)):
                split = port_symbol.split(";")

                if len(split) == 1:
                    oldnode = "/graph/" + port_symbol.split(":",1)[-1]
                    port_symbol = name
                else:
                    if isOutput:
                        oldnode = "/graph/" + split[1].split(":",1)[-1]
                        split[1] = name
                    else:
                        oldnode = "/graph/" + split[0].split(":",1)[-1]
                        split[0] = name
                    port_symbol = ";".join(split)

                self.midiports[i][0] = port_symbol
                break
        else:
            return

        index = int(name[-1])
        title = self.get_port_name_alias(name).replace("-","_").replace(" ","_")
        newnode = "/graph/" + name.split(":",1)[-1]

        if name.startswith("nooice"):
            index += 100

        self.msg_callback("add_hw_port /graph/%s midi %i %s %i" % (name.split(":",1)[-1], int(isOutput), title, index))

        for i in reversed(range(len(port_conns))):
            if port_conns[i][0] == oldnode:
                port_conns[i] = (newnode, port_conns[i][1])
            elif port_conns[i][1] == oldnode:
                port_conns[i] = (port_conns[i][0], newnode)
            connection = port_conns[i]

            if newnode not in connection:
                continue
            if not connect_jack_ports(self._fix_host_connection_port(connection[0]),
                                      self._fix_host_connection_port(connection[1])):
                continue

            self.connections.append(connection)
            self.msg_callback("connect %s %s" % (connection[0], connection[1]))
            port_conns.pop(i)

    def jack_port_deleted(self, name):
        name = charPtrToString(name)
        removed_conns = []

        for ports in self.connections:
            jackports = (self._fix_host_connection_port(ports[0]), self._fix_host_connection_port(ports[1]))
            if name not in jackports:
                continue
            disconnect_jack_ports(jackports[0], jackports[1])
            removed_conns.append(ports)

        for ports in removed_conns:
            self.connections.remove(ports)
            disconnect_jack_ports(ports[0], ports[1])

        for port_symbol, port_alias, port_conns in self.midiports:
            if name == port_symbol or (";" in port_symbol and name in port_symbol.split(";",1)):
                port_conns += removed_conns
                break

        self.msg_callback("remove_hw_port /graph/%s" % (name.split(":",1)[-1]))

    def true_bypass_changed(self, left, right):
        self.msg_callback("truebypass %i %i" % (left, right))

    # -----------------------------------------------------------------------------------------------------------------
    # Addressing callbacks

    def addr_task_addressing(self, atype, actuator, data, callback):
        if atype == Addressings.ADDRESSING_TYPE_HMI:
            return self.hmi.control_add(data['instance_id'],
                                        data['port'],
                                        data['label'],
                                        data['hmitype'],
                                        data['unit'],
                                        data['value'],
                                        data['minimum'],
                                        data['maximum'],
                                        data['steps'],
                                        actuator[0], actuator[1], actuator[2], actuator[3],
                                        data['addrs_max'], # num controllers
                                        data['addrs_idx'], # index
                                        data['options'],
                                        callback)

        if atype == Addressings.ADDRESSING_TYPE_CC:
            label = '"%s"' % data['label'].replace('"', '')
            unit  = '"%s"' % data['unit'].replace('"', '')
            optionsData = []

            rmaximum = data['maximum']
            rvalue   = data['value']

            if data['options']:
                currentNum = 0
                numBytesFree = 1024-128

                for o in data['options']:
                    if currentNum > 50:
                        if rvalue >= currentNum:
                            rvalue = 0
                        rmaximum = currentNum
                        break

                    optdata    = '"%s" %f' % (o[1].replace('"', ''), float(o[0]))
                    optdataLen = len(optdata)

                    if numBytesFree-optdataLen-2 < 0:
                        print("WARNING: Preventing sending too many options to addressing (stopped at %i)" % currentNum)
                        if rvalue >= currentNum:
                            rvalue = 0.0
                        rmaximum = currentNum
                        break

                    currentNum += 1
                    numBytesFree -= optdataLen+1
                    optionsData.append(optdata)

            options = "%d %s" % (len(optionsData), " ".join(optionsData))
            options = options.strip()

            return self.send_notmodified("cc_map %d %s %d %d %s %f %f %f %i %s %s" % (data['instance_id'],
                                                                                      data['port'],
                                                                                      actuator[0], actuator[1],
                                                                                      label,
                                                                                      rvalue,
                                                                                      data['minimum'],
                                                                                      rmaximum,
                                                                                      data['steps'],
                                                                                      unit,
                                                                                      options
                                                                                      ), callback, datatype='boolean')

        if atype == Addressings.ADDRESSING_TYPE_MIDI:
            return self.send_notmodified("midi_map %d %s %i %i %f %f" % (data['instance_id'],
                                                                         data['port'],
                                                                         data['midichannel'],
                                                                         data['midicontrol'],
                                                                         data['minimum'],
                                                                         data['maximum'],
                                                                         ), callback, datatype='boolean')

        print("ERROR: Invalid addressing requested for", actuator)
        callback(False)
        return

    def addr_task_unaddressing(self, atype, instance_id, portsymbol, callback):
        if atype == Addressings.ADDRESSING_TYPE_HMI:
            self.pedalboard_modified = True
            return self.hmi.control_rm(instance_id, portsymbol, callback)

        if atype == Addressings.ADDRESSING_TYPE_CC:
            return self.send_modified("cc_unmap %d %s" % (instance_id, portsymbol), callback, datatype='boolean')

        if atype == Addressings.ADDRESSING_TYPE_MIDI:
            return self.send_modified("midi_unmap %d %s" % (instance_id, portsymbol), callback, datatype='boolean')

        print("ERROR: Invalid unaddressing requested")
        callback(False)
        return

    def addr_task_get_plugin_data(self, instance_id):
        return self.plugins[instance_id]

    def addr_task_get_plugin_presets(self, uri):
        if uri == PEDALBOARD_URI:
            if self.pedalboard_preset < 0 or len(self.pedalboard_presets) == 0:
                return []
            self.plugins[PEDALBOARD_INSTANCE_ID]['preset'] = "file:///%i" % self.pedalboard_preset
            presets = self.pedalboard_presets
            presets = [{'uri': 'file:///%i'%i,
                        'label': presets[i]['name']} for i in range(len(presets)) if presets[i] is not None]
            return presets
        return get_plugin_info(uri)['presets']

    def addr_task_get_port_value(self, instance_id, portsymbol):
        if instance_id == PEDALBOARD_INSTANCE_ID:
            if portsymbol == ":bpb":
                return self.transport_bpb
            if portsymbol == ":bpm":
                return self.transport_bpm
            if portsymbol == ":rolling":
                return 1.0 if self.transport_rolling else 0.0

        pluginData = self.plugins[instance_id]

        if portsymbol == ":bypass":
            return 1.0 if pluginData['bypassed'] else 0.0

        if portsymbol == ":presets":
            if len(pluginData['mapPresets']) == 0 or not pluginData['preset']:
                return 0.0
            return float(pluginData['mapPresets'].index(pluginData['preset']))

        return pluginData['ports'][portsymbol]

    def addr_task_store_address_data(self, instance_id, portsymbol, data):
        pluginData = self.plugins[instance_id]
        pluginData['addressings'][portsymbol] = data

    def addr_task_hw_added(self, dev_uri, label, labelsuffix, version):
        self.msg_callback("hw_add %s %s %s %s" % (dev_uri,
                                                  label.replace(" ","_"),
                                                  labelsuffix.replace(" ","_"),
                                                  version))

    def addr_task_hw_removed(self, dev_uri, label, version):
        self.msg_callback("hw_rem %s %s %s" % (dev_uri, label.replace(" ","_"), version))

    def addr_task_act_added(self, metadata):
        self.msg_callback("act_add " + b64encode(json.dumps(metadata).encode("utf-8")).decode("utf-8"))

    def addr_task_act_removed(self, uri):
        for instance_id, pluginData in self.plugins.items():
            relevant_ports = []
            for portsymbol, addressing in pluginData['addressings'].items():
                if addressing['actuator_uri'] == uri:
                    self.pedalboard_modified = True
                    relevant_ports.append(portsymbol)

            for portsymbol in relevant_ports:
                pluginData['addressings'].pop(portsymbol)

        self.msg_callback("act_del %s" % uri)

    # -----------------------------------------------------------------------------------------------------------------
    # Initialization

    @gen.coroutine
    def init_host(self):
        self.init_jack()
        self.open_connection_if_needed(None)

        # Disable plugin processing while initializing
        yield gen.Task(self.send_notmodified, "feature_enable processing 0", datatype='boolean')

        # Remove all plugins, non-waiting
        self.send_notmodified("remove -1")

        # get current transport data
        data = get_jack_data(True)
        self.transport_rolling = data['rolling']
        self.transport_bpm     = data['bpm']
        self.transport_bpb     = data['bpb']

        # load user prefs
        if self.prefs.get("transport-rolling-at-boot", "false") == "true":
            self.first_transport_rolling = True

        link_enabled = self.prefs.get("link-enabled-at-boot", "false") == "true"
        self.set_link_enabled(link_enabled)

        # load everything
        if self.allpedalboards is None:
            self.allpedalboards = get_all_good_pedalboards()

        bank_id, pedalboard = get_last_bank_and_pedalboard()

        # FIXME: ensure HMI is initialized by now

        if pedalboard and os.path.exists(pedalboard):
            self.bank_id = bank_id
            self.load(pedalboard)

        else:
            self.bank_id = 0

            if os.path.exists(DEFAULT_PEDALBOARD):
                self.load(DEFAULT_PEDALBOARD, True)

        # Setup MIDI program navigation
        navigateFootswitches = False
        navigateChannel      = 15

        if self.bank_id > 0 and pedalboard and self.bank_id <= len(self.banks):
            bank = self.banks[self.bank_id-1]
            navigateFootswitches = bank['navigateFootswitches']
            if "navigateChannel" in bank.keys() and not navigateFootswitches:
                navigateChannel  = int(bank['navigateChannel'])-1

        self.send_notmodified("midi_program_listen %d %d" % (int(not navigateFootswitches), navigateChannel))

        # Wait for all mod-host messages to be processed
        yield gen.Task(self.send_notmodified, "feature_enable processing 2", datatype='boolean')

        # All set, disable HW bypass now
        init_bypass()

    def init_jack(self):
        self.audioportsIn  = []
        self.audioportsOut = []

        if not init_jack():
            return

        for port in get_jack_hardware_ports(True, False):
            self.audioportsIn.append(port.split(":",1)[-1])

        for port in get_jack_hardware_ports(True, True):
            self.audioportsOut.append(port.split(":",1)[-1])

    def close_jack(self):
        close_jack()

    def init_plugins_data(self):
        self.plugins = {
            PEDALBOARD_INSTANCE_ID: {
                "instance"    : PEDALBOARD_INSTANCE,
                "uri"         : PEDALBOARD_URI,
                "addressings" : {},
                "midiCCs"     : {
                    ":bpb"    : (-1,-1,0.0,1.0),
                    ":bpm"    : (-1,-1,0.0,1.0),
                    ":rolling": (-1,-1,0.0,1.0),
                },
                "ports"       : {},
                "designations": (None,None,None,None,None),
                "preset"      : "",
                "mapPresets"  : []
            }
        }

    def open_connection_if_needed(self, websocket):
        if self.readsock is not None and self.writesock is not None:
            self.report_current_state(websocket)
            return

        def reader_check_response():
            self.process_read_queue()

        def writer_check_response():
            self.connected = True
            self.report_current_state(websocket)
            self.statstimer.start()

            if self.memtimer is not None:
                self.memtimer_callback()
                self.memtimer.start()

            if len(self._queue):
                self.process_write_queue()
            else:
                self._idle = True

        self._idle = False

        # Main socket, used for sending messages
        self.writesock = iostream.IOStream(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
        self.writesock.set_close_callback(self.writer_connection_closed)
        self.writesock.set_nodelay(True)
        self.writesock.connect(self.addr, writer_check_response)

        # Extra socket, used for receiving messages
        self.readsock = iostream.IOStream(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
        self.readsock.set_close_callback(self.reader_connection_closed)
        self.readsock.set_nodelay(True)
        self.readsock.connect((self.addr[0], self.addr[1]+1), reader_check_response)

    def reader_connection_closed(self):
        self.readsock = None

    def writer_connection_closed(self):
        self.writesock = None
        self.crashed = True
        self.statstimer.stop()

        if self.memtimer is not None:
            self.memtimer.stop()

        self.msg_callback("stop")

    # -----------------------------------------------------------------------------------------------------------------

    def setNavigateWithFootswitches(self, enabled, callback):
        def foot2_callback(ok):
            acthw  = self.addressings.hmi_uri2hw_map["/hmi/footswitch2"]
            cfgact = BANK_CONFIG_PEDALBOARD_UP if enabled else BANK_CONFIG_NOTHING
            self.hmi.bank_config(acthw[0], acthw[1], acthw[2], acthw[3], cfgact, callback)

        acthw  = self.addressings.hmi_uri2hw_map["/hmi/footswitch1"]
        cfgact = BANK_CONFIG_PEDALBOARD_DOWN if enabled else BANK_CONFIG_NOTHING
        self.hmi.bank_config(acthw[0], acthw[1], acthw[2], acthw[3], cfgact, foot2_callback)

    def initialize_hmi(self, uiConnected, callback):
        # If UI is already connected, do nothing
        if uiConnected:
            callback(True)
            return

        bank_id, pedalboard = get_last_bank_and_pedalboard()

        # report pedalboard and banks
        if bank_id > 0 and pedalboard and bank_id <= len(self.banks):
            bank = self.banks[bank_id-1]
            pedalboards = bank['pedalboards']
            navigateFootswitches = bank['navigateFootswitches']
            if "navigateChannel" in bank.keys() and not navigateFootswitches:
                navigateChannel = int(bank['navigateChannel'])-1
            else:
                navigateChannel = 15

        else:
            if self.allpedalboards is None:
                self.allpedalboards = get_all_good_pedalboards()
            bank_id = 0
            pedalboard = DEFAULT_PEDALBOARD
            pedalboards = self.allpedalboards
            navigateFootswitches = False
            navigateChannel = 15

        num = 0
        for pb in pedalboards:
            if pb['bundle'] == pedalboard:
                pedalboard_id = num
                break
            num += 1

        else:
            bank_id = 0
            pedalboard_id = 0
            pedalboard = ""
            pedalboards = []

        def footswitch_callback(ok):
            self.setNavigateWithFootswitches(True, callback)

        def midi_prog_callback(ok):
            self.send_notmodified("midi_program_listen 1 %d" % navigateChannel, callback, datatype='boolean')

        def initial_state_callback(ok):
            cb = footswitch_callback if navigateFootswitches else midi_prog_callback
            self.hmi.initial_state(bank_id, pedalboard_id, pedalboards, cb)

        self.setNavigateWithFootswitches(False, initial_state_callback)

    def start_session(self, callback):
        if not self.hmi.initialized:
            callback(True)
            return

        def footswitch_addr2_callback(ok):
            self.addressings.hmi_load_first("/hmi/footswitch2", callback)

        def footswitch_addr1_callback(ok):
            self.addressings.hmi_load_first("/hmi/footswitch1", footswitch_addr2_callback)

        def footswitch_bank_callback(ok):
            self.setNavigateWithFootswitches(False, footswitch_addr1_callback)

        self.send_notmodified("midi_program_listen 0 -1")

        self.banks = []
        self.allpedalboards = []
        self.hmi.ui_con(footswitch_bank_callback)

    def end_session(self, callback):
        if not self.hmi.initialized:
            callback(True)
            return

        def initialize_callback(ok):
            self.initialize_hmi(False, callback)

        self.banks = list_banks()
        self.allpedalboards = get_all_good_pedalboards()
        self.hmi.ui_dis(initialize_callback)

    # -----------------------------------------------------------------------------------------------------------------
    # Message handling

    def process_read_message(self, msg):
        msg = msg[:-1].decode("utf-8", errors="ignore")
        if LOG: logging.info("[host] received <- %s" % repr(msg))

        self.process_read_message_body(msg)
        self.process_read_queue()

    @gen.coroutine
    def process_read_message_body(self, msg):
        cmd = msg.split(" ",1)[0]

        if cmd == "param_set":
            msg_data    = msg[len(cmd)+1:].split(" ",3)
            instance_id = int(msg_data[0])
            portsymbol  = msg_data[1]
            value       = float(msg_data[2])

            try:
                instance   = self.mapper.get_instance(instance_id)
                pluginData = self.plugins[instance_id]
            except:
                pass
            else:
                if portsymbol == ":bypass":
                    pluginData['bypassed'] = bool(value)

                elif portsymbol == ":presets":
                    print("presets changed by backend", value)
                    value = int(value)
                    if value < 0 or value >= len(pluginData['mapPresets']):
                        return

                    if instance_id == PEDALBOARD_INSTANCE_ID:
                        value = int(pluginData['mapPresets'][value].replace("file:///",""))
                        yield gen.Task(self.pedalpreset_load, value)
                    else:
                        yield gen.Task(self.preset_load, instance, pluginData['mapPresets'][value])

                else:
                    pluginData['ports'][portsymbol] = value

                    if instance_id == PEDALBOARD_INSTANCE_ID:
                        self.process_read_message_pedal_changed(portsymbol, value)

                self.pedalboard_modified = True
                self.msg_callback("param_set %s %s %f" % (instance, portsymbol, value))

        elif cmd == "output_set":
            msg_data    = msg[len(cmd)+1:].split(" ",3)
            instance_id = int(msg_data[0])
            portsymbol  = msg_data[1]
            value       = float(msg_data[2])

            if instance_id == TUNER_INSTANCE_ID:
                self.set_tuner_value(value)

            else:
                try:
                    instance   = self.mapper.get_instance(instance_id)
                    pluginData = self.plugins[instance_id]
                except:
                    pass
                else:
                    pluginData['outputs'][portsymbol] = value
                    self.msg_callback("output_set %s %s %f" % (instance, portsymbol, value))

        elif cmd == "atom":
            msg_data    = msg[len(cmd)+1:].split(" ",3)
            instance_id = int(msg_data[0])
            portsymbol  = msg_data[1]
            atomjson    = msg_data[2]

            try:
                instance   = self.mapper.get_instance(instance_id)
                pluginData = self.plugins[instance_id]
            except:
                pass
            else:
                #pluginData['outputs'][portsymbol] = atomjson
                self.msg_callback("output_atom %s %s %s" % (instance, portsymbol, atomjson))

        elif cmd == "midi_mapped":
            msg_data    = msg[len(cmd)+1:].split(" ",7)
            instance_id = int(msg_data[0])
            portsymbol  = msg_data[1]
            channel     = int(msg_data[2])
            controller  = int(msg_data[3])
            value       = float(msg_data[4])
            minimum     = float(msg_data[5])
            maximum     = float(msg_data[6])

            instance   = self.mapper.get_instance(instance_id)
            pluginData = self.plugins[instance_id]

            if portsymbol == ":bypass":
                pluginData['bypassCC'] = (channel, controller)
                pluginData['bypassed'] = bool(value)
            else:
                pluginData['midiCCs'][portsymbol] = (channel, controller, minimum, maximum)
                pluginData['ports'][portsymbol] = value

            self.pedalboard_modified = True
            pluginData['addressings'][portsymbol] = self.addressings.add_midi(instance_id,
                                                                              portsymbol,
                                                                              channel, controller,
                                                                              minimum, maximum)

            self.msg_callback("midi_map %s %s %i %i %f %f" % (instance, portsymbol,
                                                              channel, controller,
                                                              minimum, maximum))
            self.msg_callback("param_set %s %s %f" % (instance, portsymbol, value))

        elif cmd == "midi_program":
            msg_data = msg[len(cmd)+1:].split(" ",1)
            program  = int(msg_data[0])
            bank_id  = self.bank_id

            if self.bank_id > 0 and self.bank_id <= len(self.banks):
                pedalboards = self.banks[self.bank_id-1]['pedalboards']
            else:
                pedalboards = self.allpedalboards

            if program >= 0 and program < len(pedalboards):
                bundlepath = pedalboards[program]['bundle']

                def load_callback(ok):
                    self.bank_id = bank_id
                    self.load(bundlepath)
                    self.send_notmodified("feature_enable processing 1")

                def hmi_clear_callback(ok):
                    self.hmi.clear(load_callback)

                self.send_notmodified("feature_enable processing 0")
                self.reset(hmi_clear_callback)

        elif cmd == "transport":
            msg_data = msg[len(cmd)+1:].split(" ",3)
            rolling  = bool(int(msg_data[0]))
            bpb      = float(msg_data[1])
            bpm      = float(msg_data[2])
            speed    = 1.0 if rolling else 0.0

            for pluginData in self.plugins.values():
                _, _2, bpb_symbol, bpm_symbol, speed_symbol = pluginData['designations']

                if bpb_symbol is not None:
                    pluginData['ports'][bpb_symbol] = bpb
                    self.msg_callback("param_set %s %s %f" % (pluginData['instance'], bpb_symbol, bpb))

                elif bpm_symbol is not None:
                    pluginData['ports'][bpm_symbol] = bpm
                    self.msg_callback("param_set %s %s %f" % (pluginData['instance'], bpm_symbol, bpm))

                elif speed_symbol is not None:
                    pluginData['ports'][speed_symbol] = speed
                    self.msg_callback("param_set %s %s %f" % (pluginData['instance'], speed_symbol, speed))

            self.transport_rolling = rolling
            self.transport_bpb     = bpb
            self.transport_bpm     = bpm

            self.msg_callback("transport %i %f %f %s" % (rolling, bpb, bpm, self.transport_sync))

        elif cmd == "data_finish":
            now  = time.clock()
            diff = now-self.last_data_finish_msg

            if diff >= 0.5:
                self.send_output_data_ready(now)

            else:
                diff = (0.5-diff)/0.5*0.064
                ioloop.IOLoop.instance().call_later(diff, self.send_output_data_ready)

        else:
            logging.error("[host] unrecognized command: %s" % cmd)

    def process_read_message_pedal_changed(self, portsymbol, value):
        if portsymbol == ":bpb":
            self.transport_bpb = value
            designation_index  = self.DESIGNATIONS_INDEX_BPB

        elif portsymbol == ":bpm":
            self.transport_bpm = value
            designation_index  = self.DESIGNATIONS_INDEX_BPM

        elif portsymbol == ":rolling":
            self.transport_rolling = bool(int(value))
            designation_index      = self.DESIGNATIONS_INDEX_SPEED

        else:
            return

        for pluginData in self.plugins.values():
            des_symbol = pluginData['designations'][designation_index]
            if des_symbol is None:
                continue
            pluginData['ports'][des_symbol] = value
            self.msg_callback("param_set %s %s %f" % (pluginData['instance'], des_symbol, value))

        self.msg_callback("transport %i %f %f %s" % (self.transport_rolling,
                                                     self.transport_bpb,
                                                     self.transport_bpm,
                                                     self.transport_sync))
    def process_read_queue(self):
        if self.readsock is None:
            return
        self.readsock.read_until(b"\0", self.process_read_message)

    @gen.coroutine
    def send_output_data_ready(self, now = None):
        self.last_data_finish_msg = time.clock() if now is None else now
        yield gen.Task(self.send_notmodified, "output_data_ready", datatype='boolean')

    def process_write_queue(self):
        try:
            msg, callback, datatype = self._queue.pop(0)
            logging.info("[host] popped from queue: %s" % msg)
        except IndexError:
            self._idle = True
            return

        if self.writesock is None:
            self.process_write_queue()
            return

        def check_response(resp):
            if callback is not None:
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

            self.process_write_queue()

        self._idle = False
        logging.info("[host] sending -> %s" % msg)

        encmsg = "%s\0" % str(msg)
        self.writesock.write(encmsg.encode("utf-8"))
        self.writesock.read_until(b"\0", check_response)

    # send data to host, set modified flag to true
    def send_modified(self, msg, callback=None, datatype='int'):
        self.pedalboard_modified = True
        self._queue.append((msg, callback, datatype))
        if self._idle:
            self.process_write_queue()

    # send data to host, don't change modified flag
    def send_notmodified(self, msg, callback=None, datatype='int'):
        self._queue.append((msg, callback, datatype))
        if self._idle:
            self.process_write_queue()

    # -----------------------------------------------------------------------------------------------------------------
    # Host stuff

    def mute(self):
        disconnect_jack_ports(self.jack_hwout_prefix + "1", "system:playback_1")
        disconnect_jack_ports(self.jack_hwout_prefix + "2", "system:playback_2")
        disconnect_jack_ports(self.jack_hwout_prefix + "1", "mod-peakmeter:in_3")
        disconnect_jack_ports(self.jack_hwout_prefix + "2", "mod-peakmeter:in_4")

    def unmute(self):
        connect_jack_ports(self.jack_hwout_prefix + "1", "system:playback_1")
        connect_jack_ports(self.jack_hwout_prefix + "2", "system:playback_2")
        connect_jack_ports(self.jack_hwout_prefix + "1", "mod-peakmeter:in_3")
        connect_jack_ports(self.jack_hwout_prefix + "2", "mod-peakmeter:in_4")

    def report_current_state(self, websocket):
        if websocket is None:
            return

        data = get_jack_data(False)
        websocket.write_message("mem_load " + self.get_free_memory_value())
        websocket.write_message("stats %0.1f %i" % (data['cpuLoad'], data['xruns']))
        websocket.write_message("transport %i %f %f %s" % (self.transport_rolling,
                                                           self.transport_bpb,
                                                           self.transport_bpm,
                                                           self.transport_sync))
        websocket.write_message("truebypass %i %i" % (get_truebypass_value(False), get_truebypass_value(True)))
        websocket.write_message("loading_start %d %d" % (self.pedalboard_empty, self.pedalboard_modified))
        websocket.write_message("size %d %d" % (self.pedalboard_size[0], self.pedalboard_size[1]))

        for dev_uri, label, labelsuffix, version in self.addressings.cchain.hw_versions.values():
            websocket.write_message("hw_add %s %s %s %s" % (dev_uri,
                                                            label.replace(" ","_"),
                                                            labelsuffix.replace(" ","_"),
                                                            version))

        crashed = self.crashed
        self.crashed = False

        if crashed:
            self.init_jack()
            self.send_notmodified("transport %i %f %f" % (self.transport_rolling, self.transport_bpb, self.transport_bpm))
            self.addressings.cchain.restart_if_crashed()

            if self.transport_sync == "link":
                self.set_link_enabled(True)

        midiports = []
        for port_id, port_alias, _ in self.midiports:
            if ";" in port_id:
                inp, outp = port_id.split(";",1)
                midiports.append(inp)
                midiports.append(outp)
            else:
                midiports.append(port_id)

        self.hasSerialMidiIn  = has_serial_midi_input_port()
        self.hasSerialMidiOut = has_serial_midi_output_port()

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

        # MIDI In
        if self.hasSerialMidiIn:
            websocket.write_message("add_hw_port /graph/serial_midi_in midi 0 Serial_MIDI_In 0")

        ports = get_jack_hardware_ports(False, False)
        for i in range(len(ports)):
            name = ports[i]
            if name not in midiports and not name.startswith("%s:midi_" % self.jack_slave_prefix):
                continue
            alias = get_jack_port_alias(name)
            if alias:
                title = alias.split("-",5)[-1].replace("-","_").replace(";",".")
            else:
                title = name.split(":",1)[-1].title()
            title = title.replace(" ","_")
            websocket.write_message("add_hw_port /graph/%s midi 0 %s %i" % (name.split(":",1)[-1], title, i+1))

        # MIDI Out
        if self.hasSerialMidiOut:
            websocket.write_message("add_hw_port /graph/serial_midi_out midi 1 Serial_MIDI_Out 0")

        ports = get_jack_hardware_ports(False, True)
        for i in range(len(ports)):
            name = ports[i]
            if name not in midiports and not name.startswith("%s:midi_" % self.jack_slave_prefix):
                continue
            alias = get_jack_port_alias(name)
            if alias:
                title = alias.split("-",5)[-1].replace("-","_").replace(";",".")
            else:
                title = name.split(":",1)[-1].title()
            title = title.replace(" ","_")
            websocket.write_message("add_hw_port /graph/%s midi 1 %s %i" % (name.split(":",1)[-1], title, i+1))

        rinstances = {
            PEDALBOARD_INSTANCE_ID: PEDALBOARD_INSTANCE
        }

        for instance_id, pluginData in self.plugins.items():
            if instance_id == PEDALBOARD_INSTANCE_ID:
                continue

            rinstances[instance_id] = pluginData['instance']

            websocket.write_message("add %s %s %.1f %.1f %d" % (pluginData['instance'], pluginData['uri'],
                                                                pluginData['x'], pluginData['y'],
                                                                int(pluginData['bypassed'])))

            if -1 not in pluginData['bypassCC']:
                mchnnl, mctrl = pluginData['bypassCC']
                websocket.write_message("midi_map %s :bypass %i %i 0.0 1.0" % (pluginData['instance'], mchnnl, mctrl))

            if pluginData['preset']:
                websocket.write_message("preset %s %s" % (pluginData['instance'], pluginData['preset']))

            if crashed:
                self.send_notmodified("add %s %d" % (pluginData['uri'], instance_id))
                if pluginData['bypassed']:
                    self.send_notmodified("bypass %d 1" % (instance_id,))
                if -1 not in pluginData['bypassCC']:
                    mchnnl, mctrl = pluginData['bypassCC']
                    self.send_notmodified("midi_map %d :bypass %i %i 0.0 1.0" % (instance_id, mchnnl, mctrl))
                if pluginData['preset']:
                    self.send_notmodified("preset_load %d %s" % (instance_id, pluginData['preset']))

            for symbol, value in pluginData['ports'].items():
                websocket.write_message("param_set %s %s %f" % (pluginData['instance'], symbol, value))

                if crashed:
                    self.send_notmodified("param_set %d %s %f" % (instance_id, symbol, value))

            for symbol, value in pluginData['outputs'].items():
                if value is None:
                    continue
                websocket.write_message("output_set %s %s %f" % (pluginData['instance'], symbol, value))

                if crashed:
                    self.send_notmodified("monitor_output %d %s" % (instance_id, symbol))

            if crashed:
                for symbol, data in pluginData['midiCCs'].items():
                    mchnnl, mctrl, minimum, maximum = data
                    if -1 not in (mchnnl, mctrl):
                        self.send_notmodified("midi_map %d %s %i %i %f %f" % (instance_id, symbol,
                                                                              mchnnl, mctrl, minimum, maximum))

        for port_from, port_to in self.connections:
            websocket.write_message("connect %s %s" % (port_from, port_to))

            if crashed:
                self.send_notmodified("connect %s %s" % (self._fix_host_connection_port(port_from),
                                                         self._fix_host_connection_port(port_to)))

        self.addressings.registerMappings(lambda msg: websocket.write_message(msg), rinstances)

        # TODO: restore HMI and CC addressings if crashed

        websocket.write_message("loading_end %d" % self.pedalboard_preset)

    # -----------------------------------------------------------------------------------------------------------------
    # Host stuff - add & remove bundles

    def add_bundle(self, bundlepath, callback):
        if is_bundle_loaded(bundlepath):
            print("NOTE: Skipped add_bundle, already in world")
            callback((False, "Bundle already loaded"))
            return

        def host_callback(ok):
            plugins = add_bundle_to_lilv_world(bundlepath)
            callback((True, plugins))

        self.send_notmodified("bundle_add \"%s\"" % bundlepath.replace('"','\\"'), host_callback, datatype='boolean')

    def remove_bundle(self, bundlepath, isPluginBundle, callback):
        if not is_bundle_loaded(bundlepath):
            print("NOTE: Skipped remove_bundle, not in world")
            callback((False, "Bundle not loaded"))
            return

        if isPluginBundle and len(self.plugins) > 0:
            plugins = list_plugins_in_bundle(bundlepath)

            for plugin in self.plugins.values():
                if plugin['uri'] in plugins:
                    callback((False, "Plugin is currently in use, cannot remove"))
                    return

        def host_callback(ok):
            plugins = remove_bundle_from_lilv_world(bundlepath)
            callback((True, plugins))

        self.send_notmodified("bundle_remove \"%s\"" % bundlepath.replace('"','\\"'), host_callback, datatype='boolean')

    def refresh_bundle(self, bundlepath, plugin_uri):
        if not is_bundle_loaded(bundlepath):
            return (False, "Bundle not loaded")

        plugins = list_plugins_in_bundle(bundlepath)

        if plugin_uri not in plugins:
            return (False, "Requested plugin URI does not exist inside the bundle")

        remove_bundle_from_lilv_world(bundlepath)
        add_bundle_to_lilv_world(bundlepath)
        return (True, "")

    # -----------------------------------------------------------------------------------------------------------------
    # Host stuff - reset, add, remove

    def reset(self, callback):
        def host_callback(ok):
            self.msg_callback("remove :all")
            callback(ok)

        self.bank_id = 0
        self.connections = []
        self.addressings.clear()
        self.mapper.clear()
        self.pedalpreset_clear()

        self.pedalboard_empty    = True
        self.pedalboard_modified = False
        self.pedalboard_name     = ""
        self.pedalboard_path     = ""
        self.pedalboard_size     = [0,0]

        save_last_bank_and_pedalboard(0, "")
        self.init_plugins_data()
        self.send_notmodified("remove -1", host_callback, datatype='boolean')

    def add_plugin(self, instance, uri, x, y, callback):
        instance_id = self.mapper.get_id(instance)

        def host_callback(resp):
            if resp < 0:
                callback(False)
                return
            bypassed = False

            allports = get_plugin_control_inputs_and_monitored_outputs(uri)
            badports = []
            valports = {}

            enabled_symbol = None
            freewheel_symbol = None
            bpb_symbol = None
            bpm_symbol = None
            speed_symbol = None

            for port in allports['inputs']:
                symbol = port['symbol']
                valports[symbol] = port['ranges']['default']

                # skip notOnGUI controls
                if "notOnGUI" in port['properties']:
                    badports.append(symbol)

                # skip special designated controls
                elif port['designation'] == "http://lv2plug.in/ns/lv2core#enabled":
                    enabled_symbol = symbol
                    badports.append(symbol)
                    valports[symbol] = 0.0 if bypassed else 1.0

                elif port['designation'] == "http://lv2plug.in/ns/lv2core#freeWheeling":
                    freewheel_symbol = symbol
                    badports.append(symbol)
                    valports[symbol] = 0.0

                elif port['designation'] == "http://lv2plug.in/ns/ext/time#beatsPerBar":
                    bpb_symbol = symbol
                    badports.append(symbol)
                    valports[symbol] = self.transport_bpb

                elif port['designation'] == "http://lv2plug.in/ns/ext/time#beatsPerMinute":
                    bpm_symbol = symbol
                    badports.append(symbol)
                    valports[symbol] = self.transport_bpm

                elif port['designation'] == "http://lv2plug.in/ns/ext/time#speed":
                    speed_symbol = symbol
                    badports.append(symbol)
                    valports[symbol] = 1.0 if self.transport_rolling else 0.0

            self.plugins[instance_id] = {
                "instance"    : instance,
                "uri"         : uri,
                "bypassed"    : bypassed,
                "bypassCC"    : (-1,-1),
                "x"           : x,
                "y"           : y,
                "addressings" : {}, # symbol: addressing
                "midiCCs"     : dict((p['symbol'], (-1,-1,0.0,1.0)) for p in allports['inputs']),
                "ports"       : valports,
                "badports"    : badports,
                "designations": (enabled_symbol, freewheel_symbol, bpb_symbol, bpm_symbol, speed_symbol),
                "outputs"     : dict((symbol, None) for symbol in allports['monitoredOutputs']),
                "preset"      : "",
                "mapPresets"  : []
            }

            for output in allports['monitoredOutputs']:
                self.send_notmodified("monitor_output %d %s" % (instance_id, output))

            if len(self.pedalboard_presets) > 0:
                self.plugins_added.append(instance_id)

            callback(True)
            self.msg_callback("add %s %s %.1f %.1f %d" % (instance, uri, x, y, int(bypassed)))

        self.send_modified("add %s %d" % (uri, instance_id), host_callback, datatype='int')

    @gen.coroutine
    def remove_plugin(self, instance, callback):
        instance_id = self.mapper.get_id_without_creating(instance)

        try:
            pluginData = self.plugins.pop(instance_id)
        except KeyError:
            callback(False)
            return

        if len(self.pedalboard_presets) > 0:
            self.plugins_removed.append(instance)
            if instance_id in self.plugins_added:
                self.plugins_added.remove(instance_id)

        used_hmi_actuators = []

        for symbol in [symbol for symbol in pluginData['addressings'].keys()]:
            addressing    = pluginData['addressings'].pop(symbol)
            actuator_uri  = addressing['actuator_uri']
            actuator_type = self.addressings.get_actuator_type(actuator_uri)

            self.addressings.remove(addressing)

            if actuator_type == Addressings.ADDRESSING_TYPE_HMI:
                if actuator_uri not in used_hmi_actuators:
                    used_hmi_actuators.append(actuator_uri)

            elif actuator_type == Addressings.ADDRESSING_TYPE_CC:
                yield gen.Task(self.addr_task_unaddressing, actuator_type,
                                                            addressing['instance_id'],
                                                            addressing['port'])

        for actuator_uri in used_hmi_actuators:
            yield gen.Task(self.addressings.hmi_load_current, actuator_uri)

        def host_callback(ok):
            callback(ok)
            removed_connections = []
            for ports in self.connections:
                if ports[0].rsplit("/",1)[0] == instance or ports[1].rsplit("/",1)[0] == instance:
                    removed_connections.append(ports)
            for ports in removed_connections:
                self.connections.remove(ports)
                self.msg_callback("disconnect %s %s" % (ports[0], ports[1]))

            self.msg_callback("remove %s" % (instance))

        def hmi_callback(ok):
            self.send_modified("remove %d" % instance_id, host_callback, datatype='boolean')

        if self.hmi.initialized:
            self.hmi.control_rm(instance_id, ":all", hmi_callback)
        else:
            hmi_callback(True)

    # -----------------------------------------------------------------------------------------------------------------
    # Host stuff - plugin values

    def bypass(self, instance, bypassed, callback):
        instance_id = self.mapper.get_id_without_creating(instance)
        pluginData  = self.plugins[instance_id]

        pluginData['bypassed'] = bypassed
        self.send_modified("bypass %d %d" % (instance_id, int(bypassed)), callback, datatype='boolean')

        enabled_symbol = pluginData['designations'][self.DESIGNATIONS_INDEX_ENABLED]
        if enabled_symbol is None:
            return

        value = 0.0 if bypassed else 1.0
        pluginData['ports'][enabled_symbol] = value
        self.send_modified("param_set %d %s %f" % (instance_id, enabled_symbol, value), callback, datatype='boolean')

    def param_set(self, port, value, callback):
        instance, symbol = port.rsplit("/", 1)
        instance_id = self.mapper.get_id_without_creating(instance)
        pluginData  = self.plugins[instance_id]

        if symbol in pluginData['designations']:
            print("ERROR: Trying to modify a specially designated port '%s', stop!" % symbol)
            return

        pluginData['ports'][symbol] = value
        self.send_modified("param_set %d %s %f" % (instance_id, symbol, value), callback, datatype='boolean')

    def set_position(self, instance, x, y):
        instance_id = self.mapper.get_id_without_creating(instance)
        pluginData  = self.plugins[instance_id]

        pluginData['x'] = x
        pluginData['y'] = y

    # -----------------------------------------------------------------------------------------------------------------
    # Host stuff - plugin presets

    def preset_load(self, instance, uri, callback):
        instance_id = self.mapper.get_id_without_creating(instance)
        current_pedal = self.pedalboard_path

        def preset_callback(state):
            if not state:
                callback(False)
                return
            if self.pedalboard_path != current_pedal:
                print("WARNING: Pedalboard changed during preset_show request")
                callback(False)
                return

            pluginData = self.plugins[instance_id]

            pluginData['preset'] = uri
            self.msg_callback("preset %s %s" % (instance, uri))

            used_actuators = []

            for symbol, value in get_state_port_values(state).items():
                if symbol in pluginData['designations'] or pluginData['ports'].get(symbol, None) in (value, None):
                    continue

                pluginData['ports'][symbol] = value

                self.msg_callback("param_set %s %s %f" % (instance, symbol, value))

                addressing = pluginData['addressings'].get(symbol, None)
                if addressing is not None:
                    addressing['value'] = value
                    if addressing['actuator_uri'] not in used_actuators:
                        used_actuators.append(addressing['actuator_uri'])

            self.addressings.load_current(used_actuators, (instance_id, ":presets"))
            callback(True)

        def host_callback(ok):
            if not ok:
                callback(False)
                return
            if self.pedalboard_path != current_pedal:
                print("WARNING: Pedalboard changed during preset_load request")
                callback(False)
                return
            self.send_notmodified("preset_show %s" % uri, preset_callback, datatype='string')

        self.send_modified("preset_load %d %s" % (instance_id, uri), host_callback, datatype='boolean')

    def preset_save_new(self, instance, name, callback):
        instance_id  = self.mapper.get_id_without_creating(instance)
        pluginData   = self.plugins[instance_id]
        plugin_uri   = pluginData['uri']
        symbolname   = symbolify(name)[:32]
        presetbundle = os.path.expanduser("~/.lv2/%s-%s.lv2") % (instance.replace("/graph/","",1), symbolname)

        if os.path.exists(presetbundle):
            # if presetbundle already exists, generate a new random bundle path
            while True:
                presetbundle = os.path.expanduser("~/.lv2/%s-%s-%i.lv2" % (instance.replace("/graph/","",1),
                                                                           symbolname,
                                                                           randint(1,99999)))
                if os.path.exists(presetbundle):
                    continue
                break

        def add_bundle_callback(ok):
            # done
            preseturi = "file://%s.ttl" % os.path.join(presetbundle, symbolname)
            pluginData['preset'] = preseturi

            os.sync()
            callback({
                'ok'    : True,
                'bundle': presetbundle,
                'uri'   : preseturi
            })

        def host_callback(ok):
            if not ok:
                os.sync()
                callback({
                    'ok': False,
                })
                return
            rescan_plugin_presets(plugin_uri)
            self.add_bundle(presetbundle, add_bundle_callback)

        self.send_notmodified("preset_save %d \"%s\" %s %s.ttl" % (instance_id,
                                                                   name.replace('"','\\"'),
                                                                   presetbundle,
                                                                   symbolname), host_callback, datatype='boolean')

    def preset_save_replace(self, instance, uri, bundlepath, name, callback):
        instance_id = self.mapper.get_id_without_creating(instance)
        pluginData  = self.plugins[instance_id]
        plugin_uri  = pluginData['uri']
        symbolname  = symbolify(name)[:32]

        if pluginData['preset'] != uri or not os.path.exists(bundlepath):
            callback({
                'ok': False,
            })
            return

        def add_bundle_callback(ok):
            preseturi = "file://%s.ttl" % os.path.join(bundlepath, symbolname)
            pluginData['preset'] = preseturi
            os.sync()
            callback({
                'ok'    : True,
                'bundle': bundlepath,
                'uri'   : preseturi
            })

        def host_callback(ok):
            if not ok:
                os.sync()
                callback({
                    'ok': False,
                })
                return
            self.add_bundle(bundlepath, add_bundle_callback)

        def start(ok):
            rmtree(bundlepath)
            rescan_plugin_presets(plugin_uri)
            pluginData['preset'] = ""
            self.send_notmodified("preset_save %d \"%s\" %s %s.ttl" % (instance_id,
                                                                       name.replace('"','\\"'),
                                                                       bundlepath,
                                                                       symbolname), host_callback, datatype='boolean')

        self.remove_bundle(bundlepath, False, start)

    def preset_delete(self, instance, uri, bundlepath, callback):
        instance_id = self.mapper.get_id_without_creating(instance)
        pluginData  = self.plugins[instance_id]
        plugin_uri  = pluginData['uri']

        if pluginData['preset'] != uri or not os.path.exists(bundlepath):
            callback(False)
            return

        def start(ok):
            rmtree(bundlepath)
            rescan_plugin_presets(plugin_uri)
            pluginData['preset'] = ""
            self.msg_callback("preset %s null" % instance)
            callback(True)

        self.remove_bundle(bundlepath, False, start)

    # -----------------------------------------------------------------------------------------------------------------
    # Host stuff - pedalboard presets

    def pedalpreset_make(self, name):
        self.pedalboard_modified = True

        pedalpreset = {
            "name": name,
            "data": {},
        }

        for instance_id, pluginData in self.plugins.items():
            if instance_id == PEDALBOARD_INSTANCE_ID:
                continue
            instance = pluginData['instance'].replace("/graph/","",1)
            pedalpreset['data'][instance] = {
                "bypassed": pluginData['bypassed'],
                "ports"   : pluginData['ports'].copy(),
                "preset"  : pluginData['preset'],
            }

        return pedalpreset

    def pedalpreset_name(self, idx=None):
        if idx is None:
            idx = self.pedalboard_preset
        if idx < 0 or idx >= len(self.pedalboard_presets) or self.pedalboard_presets[idx] is None:
            return None
        return self.pedalboard_presets[idx]['name']

    def pedalpreset_init(self):
        preset = self.pedalpreset_make("Default")
        self.plugins_added   = []
        self.plugins_removed = []
        self.pedalboard_preset = 0
        self.pedalboard_presets = [preset]

    def pedalpreset_clear(self):
        self.plugins_added   = []
        self.plugins_removed = []
        self.pedalboard_preset = -1
        self.pedalboard_presets = []

    def pedalpreset_disable(self, callback):
        self.pedalpreset_clear()
        self.pedalboard_modified = True
        self.address(PEDALBOARD_INSTANCE, ":presets", None, "", 0, 0, 0, 0, callback)

    def pedalpreset_save(self):
        idx = self.pedalboard_preset

        if idx < 0 or idx >= len(self.pedalboard_presets) or self.pedalboard_presets[idx] is None:
            return False

        name   = self.pedalboard_presets[idx]['name']
        preset = self.pedalpreset_make(name)
        self.pedalboard_presets[idx] = preset
        return True

    def pedalpreset_saveas(self, name):
        if len(self.pedalboard_presets) == 0:
            self.pedalpreset_init()

        preset = self.pedalpreset_make(name)
        self.pedalboard_presets.append(preset)

        self.pedalboard_preset = len(self.pedalboard_presets)-1
        return self.pedalboard_preset

    def pedalpreset_rename(self, idx, title):
        if idx < 0 or idx >= len(self.pedalboard_presets) or self.pedalboard_presets[idx] is None:
            return False

        self.pedalboard_modified = True
        self.pedalboard_presets[idx]['name'] = title
        return True

    def pedalpreset_remove(self, idx):
        if idx < 0 or idx >= len(self.pedalboard_presets) or self.pedalboard_presets[idx] is None:
            return False

        self.pedalboard_modified = True
        self.pedalboard_presets[idx] = None
        return True

    @gen.coroutine
    def pedalpreset_load(self, idx, callback=lambda r:None):
        if idx < 0 or idx >= len(self.pedalboard_presets):
            callback(False)
            return

        pedalpreset = self.pedalboard_presets[idx]

        if pedalpreset is None:
            print("ERROR: Asked to load an invalid pedalboard preset, number", idx)
            callback(False)
            return

        self.pedalboard_preset = idx

        used_actuators = []

        for instance, data in pedalpreset['data'].items():
            instance = "/graph/%s" % instance

            if instance in self.plugins_removed:
                continue

            instance_id = self.mapper.get_id_without_creating(instance)
            pluginData  = self.plugins[instance_id]
            diffBypass  = pluginData['bypassed'] != data['bypassed']

            if diffBypass:
                addressing = pluginData['addressings'].get(":bypass", None)
                if addressing is not None:
                    addressing['value'] = 1.0 if data['bypassed'] else 0.0
                    if addressing['actuator_uri'] not in used_actuators:
                        used_actuators.append(addressing['actuator_uri'])

            # if bypassed, do it now
            if diffBypass and data['bypassed']:
                self.msg_callback("param_set %s :bypass 1.0" % (instance,))
                self.bypass(instance, True, None)

            if data['preset'] and data['preset'] != pluginData['preset']:
                self.msg_callback("preset %s %s" % (instance, data['preset']))
                yield gen.Task(self.preset_load, instance, data['preset'])

                addressing = pluginData['addressings'].get(":presets", None)
                if addressing is not None:
                    addressing['value'] = pluginData['mapPresets'].index(data['preset'])
                    if addressing['actuator_uri'] not in used_actuators:
                        used_actuators.append(addressing['actuator_uri'])

            for symbol, value in data['ports'].items():
                if symbol in pluginData['designations'] or pluginData['ports'].get(symbol, None) in (value, None):
                    continue

                self.msg_callback("param_set %s %s %f" % (instance, symbol, value))
                self.param_set("%s/%s" % (instance, symbol), value, None)

                addressing = pluginData['addressings'].get(symbol, None)
                if addressing is not None:
                    addressing['value'] = value
                    if addressing['actuator_uri'] not in used_actuators:
                        used_actuators.append(addressing['actuator_uri'])

            # if not bypassed (enabled), do it at the end
            if diffBypass and not data['bypassed']:
                self.msg_callback("param_set %s :bypass 0.0" % (instance,))
                self.bypass(instance, False, None)

        self.addressings.load_current(used_actuators, (PEDALBOARD_INSTANCE_ID, ":presets"))
        callback(True)

        self.msg_callback("pedal_preset %d" % idx)

    # -----------------------------------------------------------------------------------------------------------------
    # Host stuff - connections

    def _fix_host_connection_port(self, port):
        data = port.split("/")

        if len(data) == 3:
            if data[2] == "serial_midi_in":
                return "ttymidi:MIDI_in"
            if data[2] == "serial_midi_out":
                return "ttymidi:MIDI_out"
            if data[2].startswith("playback_"):
                num = data[2].replace("playback_","",1)
                if num in ("1", "2"):
                    return self.jack_hwin_prefix + num
            if data[2].startswith(("audio_from_slave_", "audio_to_slave_", "midi_from_slave_", "midi_to_slave_")):
                return "%s:%s" % (self.jack_slave_prefix, data[2])
            if data[2].startswith("nooice_capture_"):
                num = data[2].replace("nooice_capture_","",1)
                return "nooice%s:nooice_capture_%s" % (num, num)
            return "system:%s" % data[2]

        instance    = "/graph/%s" % data[2]
        portsymbol  = data[3]
        instance_id = self.mapper.get_id_without_creating(instance)
        return "effect_%d:%s" % (instance_id, portsymbol)

    def connect(self, port_from, port_to, callback):
        if (port_from, port_to) in self.connections:
            print("NOTE: Requested connection already exists")
            callback(True)
            return

        def host_callback(ok):
            callback(ok)
            if ok:
                self.connections.append((port_from, port_to))
                self.msg_callback("connect %s %s" % (port_from, port_to))
            else:
                print("ERROR: backend failed to connect ports: '%s' => '%s'" % (port_from, port_to))

        self.send_modified("connect %s %s" % (self._fix_host_connection_port(port_from),
                                              self._fix_host_connection_port(port_to)),
                           host_callback, datatype='boolean')

    def disconnect(self, port_from, port_to, callback):
        def host_callback(ok):
            # always return true. disconnect failures are not fatal, but still print error for debugging
            callback(True)
            self.msg_callback("disconnect %s %s" % (port_from, port_to))

            if not ok:
                print("ERROR: disconnect '%s' => '%s' failed" % (port_from, port_to))

            self.pedalboard_modified = True

            try:
                self.connections.remove((port_from, port_to))
            except:
                print("NOTE: Requested '%s' => '%s' connection doesn't exist" % (port_from, port_to))

        if len(self.connections) == 0:
            return host_callback(False)

        # If the plugin or port don't exist, assume disconnected
        try:
            port_from_2 = self._fix_host_connection_port(port_from)
        except:
            print("NOTE: Requested '%s' source port doesn't exist, assume disconnected" % port_from)
            return host_callback(True)

        try:
            port_to_2 = self._fix_host_connection_port(port_to)
        except:
            print("NOTE: Requested '%s' target port doesn't exist, assume disconnected" % port_to)
            return host_callback(True)

        host_callback(disconnect_jack_ports(port_from_2, port_to_2))

    # -----------------------------------------------------------------------------------------------------------------
    # Host stuff - load & save

    def load(self, bundlepath, isDefault=False):
        pb = get_pedalboard_info(bundlepath)

        self.msg_callback("loading_start %i 0" % int(isDefault))
        self.msg_callback("size %d %d" % (pb['width'],pb['height']))

        # MIDI Devices might change port names at anytime
        # To properly restore MIDI HW connections we need to map the "old" port names (from project)
        mappedOldMidiIns   = dict((p['symbol'], p['name']) for p in pb['hardware']['midi_ins'])
        mappedOldMidiOuts  = dict((p['symbol'], p['name']) for p in pb['hardware']['midi_outs'])
        mappedOldMidiOuts2 = dict((p['name'], p['symbol']) for p in pb['hardware']['midi_outs'])
        mappedNewMidiIns   = OrderedDict((get_jack_port_alias(p).split("-",5)[-1].replace("-"," ").replace(";","."),
                                          p.split(":",1)[-1]) for p in get_jack_hardware_ports(False, False))
        mappedNewMidiOuts  = OrderedDict((get_jack_port_alias(p).split("-",5)[-1].replace("-"," ").replace(";","."),
                                          p.split(":",1)[-1]) for p in get_jack_hardware_ports(False, True))

        curmidisymbols = []
        for port_symbol, port_alias, _ in self.midiports:
            if ";" in port_symbol:
                ports = port_symbol.split(";", 1)
                curmidisymbols.append(ports[0].split(":",1)[-1])
                curmidisymbols.append(ports[1].split(":",1)[-1])
            else:
                curmidisymbols.append(port_symbol.split(":",1)[-1])

        # register devices
        index = 0
        for name, symbol in mappedNewMidiIns.items():
            index += 1
            if name not in mappedOldMidiIns.values():
                continue
            if symbol in curmidisymbols:
                continue
            self.msg_callback("add_hw_port /graph/%s midi 0 %s %i" % (symbol, name.replace(" ","_"), index))

            if name in mappedNewMidiOuts.keys():
                outsymbol    = mappedNewMidiOuts[name]
                storedtitle  = name+";"+name
                storedsymbol = "system:%s;system:%s" % (symbol, outsymbol)
            else:
                storedtitle = name
                if symbol.startswith("nooice_capture_"):
                    num = symbol.replace("nooice_capture_","",1)
                    storedsymbol = "nooice%s:nooice_capture_%s" % (num, num)
                else:
                    storedsymbol = "system:" + symbol
            curmidisymbols.append(symbol)
            self.midiports.append([storedsymbol, storedtitle, []])

        # try to find old devices that are not available right now
        for symbol, name in mappedOldMidiIns.items():
            if symbol.split(":",1)[-1] in curmidisymbols:
                continue
            if name in mappedNewMidiOuts.keys():
                continue
            # found it
            if name in mappedOldMidiOuts2.keys():
                outsymbol   = mappedOldMidiOuts2[name]
                storedtitle = name+";"+name
                if ":" in symbol:
                    storedsymbol = "%s;%s" % (symbol, outsymbol)
                else:
                    storedsymbol = "system:%s;system:%s" % (symbol, outsymbol)
            else:
                storedtitle = name
                if ":" in symbol:
                    storedsymbol = symbol
                else:
                    storedsymbol = "system:" + symbol
            self.midiports.append([storedsymbol, storedtitle, []])

        index = 0
        for name, symbol in mappedNewMidiOuts.items():
            index += 1
            if name not in mappedOldMidiOuts.values():
                continue
            if symbol in curmidisymbols:
                continue
            self.msg_callback("add_hw_port /graph/%s midi 1 %s %i" % (symbol, name.replace(" ","_"), index))

        instances = {
            PEDALBOARD_INSTANCE: (PEDALBOARD_INSTANCE_ID, PEDALBOARD_URI)
        }
        rinstances = {
            PEDALBOARD_INSTANCE_ID: PEDALBOARD_INSTANCE
        }

        skippedPortAddressings = []
        if self.transport_sync == "link":
            skippedPortAddressings.append(PEDALBOARD_INSTANCE+"/:bpm")

        timeAvailable = pb['timeInfo']['available']
        if timeAvailable != 0:
            pluginData = self.plugins[PEDALBOARD_INSTANCE_ID]
            if timeAvailable & kPedalboardTimeAvailableBPB:
                ccData = pb['timeInfo']['bpbCC']
                if ccData['channel'] >= 0 and ccData['channel'] < 16:
                    if ccData['hasRanges'] and ccData['maximum'] > ccData['minimum']:
                        minimum = ccData['minimum']
                        maximum = ccData['maximum']
                    else:
                        minimum = 1
                        maximum = 16
                    pluginData['midiCCs'][':bpb'] = (ccData['channel'], ccData['control'], minimum, maximum)
                    pluginData['addressings'][':bpb'] = self.addressings.add_midi(PEDALBOARD_INSTANCE_ID,
                                                                                  ':bpb',
                                                                                  ccData['channel'],
                                                                                  ccData['control'],
                                                                                  minimum, maximum)
                self.set_transport_bpb(pb['timeInfo']['bpb'], False)

            if timeAvailable & kPedalboardTimeAvailableBPM:
                ccData = pb['timeInfo']['bpmCC']
                if ccData['channel'] >= 0 and ccData['channel'] < 16:
                    if ccData['hasRanges'] and ccData['maximum'] > ccData['minimum']:
                        minimum = ccData['minimum']
                        maximum = ccData['maximum']
                    else:
                        minimum = 20
                        maximum = 280
                    pluginData['midiCCs'][':bpm'] = (ccData['channel'], ccData['control'], minimum, maximum)
                    pluginData['addressings'][':bpm'] = self.addressings.add_midi(PEDALBOARD_INSTANCE_ID,
                                                                                  ':bpm',
                                                                                  ccData['channel'],
                                                                                  ccData['control'],
                                                                                  minimum, maximum)
                self.set_transport_bpm(pb['timeInfo']['bpm'], False)

            if timeAvailable & kPedalboardTimeAvailableRolling:
                ccData = pb['timeInfo']['rollingCC']
                if ccData['channel'] >= 0 and ccData['channel'] < 16:
                    pluginData['midiCCs'][':rolling'] = (ccData['channel'], ccData['control'], 0.0, 1.0)
                    pluginData['addressings'][':rolling'] = self.addressings.add_midi(PEDALBOARD_INSTANCE_ID,
                                                                                      ':rolling',
                                                                                      ccData['channel'],
                                                                                      ccData['control'],
                                                                                      0.0, 1.0)
                self.set_transport_rolling(pb['timeInfo']['rolling'] or self.first_transport_rolling, False)

        elif self.first_transport_rolling:
            self.set_transport_rolling(True, False)

        self.first_transport_rolling = False

        self.send_notmodified("transport %i %f %f" % (self.transport_rolling,
                                                      self.transport_bpb,
                                                      self.transport_bpm))

        self.msg_callback("transport %i %f %f %s" % (self.transport_rolling,
                                                     self.transport_bpb,
                                                     self.transport_bpm,
                                                     self.transport_sync))

        self.load_pb_presets(pb['plugins'], bundlepath)
        self.load_pb_plugins(pb['plugins'], instances, rinstances)
        self.load_pb_connections(pb['connections'], mappedOldMidiIns, mappedOldMidiOuts,
                                                    mappedNewMidiIns, mappedNewMidiOuts)

        self.addressings.load(bundlepath, instances, skippedPortAddressings)
        self.addressings.registerMappings(self.msg_callback, rinstances)

        self.msg_callback("loading_end %d" % self.pedalboard_preset)

        if isDefault:
            self.pedalboard_empty    = True
            self.pedalboard_modified = False
            self.pedalboard_name     = ""
            self.pedalboard_path     = ""
            self.pedalboard_size     = [0,0]
            #save_last_bank_and_pedalboard(0, "")
        else:
            self.pedalboard_empty    = False
            self.pedalboard_modified = False
            self.pedalboard_name     = pb['title']
            self.pedalboard_path     = bundlepath
            self.pedalboard_size     = [pb['width'],pb['height']]

            if bundlepath.startswith(LV2_PEDALBOARDS_DIR):
                save_last_bank_and_pedalboard(self.bank_id, bundlepath)
            else:
                save_last_bank_and_pedalboard(0, "")

            os.sync()

        return self.pedalboard_name

    def load_pb_presets(self, plugins, bundlepath):
        self.pedalpreset_clear()

        pedal_presets = safe_json_load(os.path.join(bundlepath, "presets.json"), list)

        if len(pedal_presets) == 0:
            return

        self.pedalboard_preset  = 0
        self.pedalboard_presets = pedal_presets

        init_pedal_preset = pedal_presets[0]['data']

        for p in plugins:
            pdata = init_pedal_preset.get(p['instance'], None)

            if pdata is None:
                print("WARNING: Pedalboard preset missing data for instance name '%s'" % p['instance'])
                continue

            p['bypassed'] = pdata['bypassed']

            for port in p['ports']:
                port['value'] = pdata['ports'].get(port['symbol'], port['value'])

            p['preset'] = pdata['preset']

    def load_pb_plugins(self, plugins, instances, rinstances):
        for p in plugins:
            allports = get_plugin_control_inputs_and_monitored_outputs(p['uri'])

            if 'error' in allports.keys() and allports['error']:
                continue

            instance    = "/graph/%s" % p['instance']
            instance_id = self.mapper.get_id(instance)

            instances[p['instance']] = (instance_id, p['uri'])
            rinstances[instance_id]  = instance

            badports = []
            valports = {}
            ranges   = {}

            enabled_symbol = None
            freewheel_symbol = None
            bpb_symbol = None
            bpm_symbol = None
            speed_symbol = None

            for port in allports['inputs']:
                symbol = port['symbol']
                valports[symbol] = port['ranges']['default']
                ranges[symbol] = (port['ranges']['minimum'], port['ranges']['maximum'])

                # skip notOnGUI controls
                if "notOnGUI" in port['properties']:
                    badports.append(symbol)

                # skip special designated controls
                elif port['designation'] == "http://lv2plug.in/ns/lv2core#enabled":
                    enabled_symbol = symbol
                    badports.append(symbol)
                    valports[symbol] = 0.0 if p['bypassed'] else 1.0

                elif port['designation'] == "http://lv2plug.in/ns/lv2core#freeWheeling":
                    freewheel_symbol = symbol
                    badports.append(symbol)
                    valports[symbol] = 0.0

                elif port['designation'] == "http://lv2plug.in/ns/ext/time#beatsPerBar":
                    bpb_symbol = symbol
                    badports.append(symbol)
                    valports[symbol] = self.transport_bpb

                elif port['designation'] == "http://lv2plug.in/ns/ext/time#beatsPerMinute":
                    bpm_symbol = symbol
                    badports.append(symbol)
                    valports[symbol] = self.transport_bpm

                elif port['designation'] == "http://lv2plug.in/ns/ext/time#speed":
                    speed_symbol = symbol
                    badports.append(symbol)
                    valports[symbol] = 1.0 if self.transport_rolling else 0.0

            self.plugins[instance_id] = pluginData = {
                "instance"    : instance,
                "uri"         : p['uri'],
                "bypassed"    : p['bypassed'],
                "bypassCC"    : (p['bypassCC']['channel'], p['bypassCC']['control']),
                "x"           : p['x'],
                "y"           : p['y'],
                "addressings" : {}, # symbol: addressing
                "midiCCs"     : dict((p['symbol'], (-1,-1,0.0,1.0)) for p in allports['inputs']),
                "ports"       : valports,
                "badports"    : badports,
                "designations": (enabled_symbol, freewheel_symbol, bpb_symbol, bpm_symbol, speed_symbol),
                "outputs"     : dict((symbol, None) for symbol in allports['monitoredOutputs']),
                "preset"      : p['preset'],
                "mapPresets"  : []
            }

            self.send_notmodified("add %s %d" % (p['uri'], instance_id))

            if p['bypassed']:
                self.send_notmodified("bypass %d 1" % (instance_id,))

            self.msg_callback("add %s %s %.1f %.1f %d" % (instance, p['uri'], p['x'], p['y'], int(p['bypassed'])))

            if p['bypassCC']['channel'] >= 0 and p['bypassCC']['control'] >= 0:
                pluginData['addressings'][':bypass'] = self.addressings.add_midi(instance_id, ":bypass",
                                                                                 p['bypassCC']['channel'],
                                                                                 p['bypassCC']['control'],
                                                                                 0.0, 1.0)

            if p['preset']:
                self.send_notmodified("preset_load %d %s" % (instance_id, p['preset']))
                self.msg_callback("preset %s %s" % (instance, p['preset']))

            for port in p['ports']:
                symbol = port['symbol']
                value  = port['value']

                if pluginData['ports'][symbol] != value:
                    pluginData['ports'][symbol] = value
                    self.send_notmodified("param_set %d %s %f" % (instance_id, symbol, value))
                    self.msg_callback("param_set %s %s %f" % (instance, symbol, value))

                # don't address "bad" ports
                if symbol in badports:
                    continue

                mchnnl = port['midiCC']['channel']
                mctrl  = port['midiCC']['control']

                if mchnnl >= 0 and mchnnl < 16:
                    if port['midiCC']['hasRanges'] and port['midiCC']['maximum'] > port['midiCC']['minimum']:
                        minimum = port['midiCC']['minimum']
                        maximum = port['midiCC']['maximum']
                    else:
                        minimum, maximum = ranges[symbol]

                    pluginData['midiCCs'][symbol] = (mchnnl, mctrl, minimum, maximum)
                    pluginData['addressings'][symbol] = self.addressings.add_midi(instance_id, symbol,
                                                                                  mchnnl, mctrl, minimum, maximum)

            for output in allports['monitoredOutputs']:
                self.send_notmodified("monitor_output %d %s" % (instance_id, output))

    def load_pb_connections(self, connections, mappedOldMidiIns, mappedOldMidiOuts,
                                               mappedNewMidiIns, mappedNewMidiOuts):
        for c in connections:
            doConnectionNow = True
            aliasname1 = aliasname2 = None

            if c['source'] in mappedOldMidiIns.keys():
                aliasname1 = mappedOldMidiIns[c['source']]
                try:
                    portname = mappedNewMidiIns[aliasname1]
                except:
                    doConnectionNow = False
                else:
                    c['source'] = portname

            if c['target'] in mappedOldMidiOuts.keys():
                aliasname2 = mappedOldMidiOuts[c['target']]
                try:
                    portname = mappedNewMidiOuts[aliasname2]
                except:
                    doConnectionNow = False
                else:
                    c['target'] = portname

            port_from = "/graph/%s" % c['source']
            port_to   = "/graph/%s" % c['target']

            if doConnectionNow:
                try:
                    port_from_2 = self._fix_host_connection_port(port_from)
                    port_to_2   = self._fix_host_connection_port(port_to)
                except:
                    continue
                self.send_notmodified("connect %s %s" % (port_from_2, port_to_2))
                self.connections.append((port_from, port_to))
                self.msg_callback("connect %s %s" % (port_from, port_to))

            elif aliasname1 is not None or aliasname2 is not None:
                for port_symbol, port_alias, port_conns in self.midiports:
                    port_alias = port_alias.split(";",1) if ";" in port_alias else [port_alias]
                    if aliasname1 in port_alias or aliasname2 in port_alias:
                        port_conns.append((port_from, port_to))

    def save(self, title, asNew):
        titlesym = symbolify(title)[:16]

        # Save over existing bundlepath
        if self.pedalboard_path and os.path.exists(self.pedalboard_path) and os.path.isdir(self.pedalboard_path) and \
            self.pedalboard_path.startswith(LV2_PEDALBOARDS_DIR) and not asNew:
            bundlepath = self.pedalboard_path

        # Save new
        else:
            lv2path = os.path.expanduser("~/.pedalboards/")
            trypath = os.path.join(lv2path, "%s.pedalboard" % titlesym)

            # if trypath already exists, generate a random bundlepath based on title
            if os.path.exists(trypath):
                while True:
                    trypath = os.path.join(lv2path, "%s-%i.pedalboard" % (titlesym, randint(1,99999)))
                    if os.path.exists(trypath):
                        continue
                    bundlepath = trypath
                    break

            # trypath doesn't exist yet, use it
            else:
                bundlepath = trypath

                # just in case..
                if not os.path.exists(lv2path):
                    os.mkdir(lv2path)

            os.mkdir(bundlepath)
            self.pedalboard_path = bundlepath

        # save
        self.pedalboard_name     = title
        self.pedalboard_empty    = False
        self.pedalboard_modified = False
        self.save_state_to_ttl(bundlepath, title, titlesym)

        save_last_bank_and_pedalboard(0, bundlepath)
        os.sync()

        return bundlepath

    def save_state_to_ttl(self, bundlepath, title, titlesym):
        self.save_state_manifest(bundlepath, titlesym)
        self.save_state_addressings(bundlepath)
        self.save_state_presets(bundlepath)
        self.save_state_mainfile(bundlepath, title, titlesym)

    def save_state_manifest(self, bundlepath, titlesym):
        # Write manifest.ttl
        with TextFileFlusher(os.path.join(bundlepath, "manifest.ttl")) as fh:
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

    def save_state_addressings(self, bundlepath):
        instances = {
            PEDALBOARD_INSTANCE_ID: PEDALBOARD_INSTANCE
        }

        for instance_id, plugin in self.plugins.items():
            instances[instance_id] = plugin['instance']

        self.addressings.save(bundlepath, instances)

    def save_state_presets(self, bundlepath):
        # Write presets.json
        presets_path = os.path.join(bundlepath, "presets.json")

        if len(self.pedalboard_presets) > 1:
            for instance in self.plugins_removed:
                for pedalpreset in self.pedalboard_presets:
                    if pedalpreset is None:
                        continue
                    try:
                        pedalpreset['data'].pop(instance.replace("/graph/","",1))
                    except KeyError:
                        pass

            for instance_id in self.plugins_added:
                for pedalpreset in self.pedalboard_presets:
                    if pedalpreset is None:
                        continue
                    pluginData = self.plugins[instance_id]
                    instance   = pluginData['instance'].replace("/graph/","",1)
                    pedalpreset['data'][instance] = {
                        "bypassed": pluginData['bypassed'],
                        "ports"   : pluginData['ports'].copy(),
                        "preset"  : pluginData['preset'],
                    }

            presets = [p for p in self.pedalboard_presets if p is not None]
            with TextFileFlusher(presets_path) as fh:
                json.dump(presets, fh)

        elif os.path.exists(presets_path):
            os.remove(presets_path)

        self.plugins_added   = []
        self.plugins_removed = []

    def save_state_mainfile(self, bundlepath, title, titlesym):
        # Create list of midi in/out ports
        midiportsIn   = []
        midiportsOut  = []
        midiportAlias = {}

        for port_symbol, port_alias, _ in self.midiports:
            if ";" in port_symbol:
                inp, outp = port_symbol.split(";",1)
                midiportsIn.append(inp)
                midiportsOut.append(outp)
                title_in, title_out = port_alias.split(";",1)
                midiportAlias[inp]  = title_in
                midiportAlias[outp] = title_out
            else:
                midiportsIn.append(port_symbol)
                midiportAlias[port_symbol] = port_alias

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
        for instance_id, pluginData in self.plugins.items():
            if instance_id == PEDALBOARD_INSTANCE_ID:
                continue

            info = get_plugin_info(pluginData['uri'])
            instance = pluginData['instance'].replace("/graph/","",1)
            blocks += """
<%s>
    ingen:canvasX %.1f ;
    ingen:canvasY %.1f ;
    ingen:enabled %s ;
    ingen:polyphonic false ;
    lv2:microVersion %i ;
    lv2:minorVersion %i ;
    mod:builderVersion %i ;
    mod:releaseNumber %i ;
    lv2:port <%s> ;
    lv2:prototype <%s> ;
    pedal:preset <%s> ;
    a ingen:Block .
""" % (instance, pluginData['x'], pluginData['y'], "false" if pluginData['bypassed'] else "true",
       info['microVersion'], info['minorVersion'], info['builder'], info['release'],
       "> ,\n             <".join(tuple("%s/%s" % (instance, port['symbol']) for port in (info['ports']['audio']['input']+
                                                                                          info['ports']['audio']['output']+
                                                                                          info['ports']['control']['input']+
                                                                                          info['ports']['control']['output']+
                                                                                          info['ports']['cv']['input']+
                                                                                          info['ports']['cv']['output']+
                                                                                          info['ports']['midi']['input']+
                                                                                          info['ports']['midi']['output']+
                                                                                          [{'symbol': ":bypass"}]))),
       pluginData['uri'],
       pluginData['preset'])

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
            for symbol, value in pluginData['ports'].items():
                blocks += """
<%s/%s>
    ingen:value %f ;%s
    a lv2:ControlPort ,
        lv2:InputPort .
""" % (instance, symbol, value,
       ("""
    midi:binding [
        midi:channel %i ;
        midi:controllerNumber %i ;
        lv2:minimum %f ;
        lv2:maximum %f ;
        a midi:Controller ;
    ] ;""" % pluginData['midiCCs'][symbol]) if -1 not in pluginData['midiCCs'][symbol][0:2] else "")

            # control output
            for port in info['ports']['control']['output']:
                blocks += """
<%s/%s>
    a lv2:ControlPort ,
        lv2:OutputPort .
""" % (instance, port['symbol'])

            blocks += """
<%s/:bypass>
    ingen:value %i ;%s
    a lv2:ControlPort ,
        lv2:InputPort .
""" % (instance, 1 if pluginData['bypassed'] else 0,
       ("""
    midi:binding [
        midi:channel %i ;
        midi:controllerNumber %i ;
        a midi:Controller ;
    ] ;""" % pluginData['bypassCC']) if -1 not in pluginData['bypassCC'] else "")

        # Globak Ports
        pluginData = self.plugins[PEDALBOARD_INSTANCE_ID]

        # BeatsPerBar
        ports = """
<:bpb>
    ingen:value %f ;%s
    lv2:index 0 ;
    a lv2:ControlPort ,
        lv2:InputPort .
""" % (self.transport_bpb,
       ("""
    midi:binding [
        midi:channel %i ;
        midi:controllerNumber %i ;
        lv2:minimum %f ;
        lv2:maximum %f ;
        a midi:Controller ;
    ] ;""" % pluginData['midiCCs'][':bpb']) if -1 not in pluginData['midiCCs'][':bpb'][0:2] else "")

        # BeatsPerMinute
        index += 1
        ports += """
<:bpm>
    ingen:value %f ;%s
    lv2:index 1 ;
    a lv2:ControlPort ,
        lv2:InputPort .
""" % (self.transport_bpm,
       ("""
    midi:binding [
        midi:channel %i ;
        midi:controllerNumber %i ;
        lv2:minimum %f ;
        lv2:maximum %f ;
        a midi:Controller ;
    ] ;""" % pluginData['midiCCs'][':bpm']) if -1 not in pluginData['midiCCs'][':bpm'][0:2] else "")

        # Rolling
        ports += """
<:rolling>
    ingen:value %i ;%s
    lv2:index 2 ;
    a lv2:ControlPort ,
        lv2:InputPort .
""" % (int(self.transport_rolling),
       ("""
    midi:binding [
        midi:channel %i ;
        midi:controllerNumber %i ;
        a midi:Controller ;
    ] ;""" % pluginData['midiCCs'][':rolling'][0:2]) if -1 not in pluginData['midiCCs'][':rolling'][0:2] else "")

        # Control In/Out
        ports += """
<control_in>
    atom:bufferType atom:Sequence ;
    lv2:index 3 ;
    lv2:name "Control In" ;
    lv2:portProperty lv2:connectionOptional ;
    lv2:symbol "control_in" ;
    <http://lv2plug.in/ns/ext/resize-port#minimumSize> 4096 ;
    a atom:AtomPort ,
        lv2:InputPort .

<control_out>
    atom:bufferType atom:Sequence ;
    lv2:index 4 ;
    lv2:name "Control Out" ;
    lv2:portProperty lv2:connectionOptional ;
    lv2:symbol "control_out" ;
    <http://lv2plug.in/ns/ext/resize-port#minimumSize> 4096 ;
    a atom:AtomPort ,
        lv2:OutputPort .
"""
        index = 4

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
""" % (sname, index, midiportAlias[port], sname)

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
""" % (sname, index, midiportAlias[port], sname)

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
@prefix mod:   <http://moddevices.com/ns/mod#> .
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
""" % (arcs, blocks, ports, title.replace('"','\\"'), self.pedalboard_size[0], self.pedalboard_size[1])

        # Arcs (connections)
        if len(self.connections) > 0:
            args = (" ,\n              _:b".join(tuple(str(i+1) for i in range(len(self.connections)))))
            pbdata += "    ingen:arc _:b%s ;\n" % args

        # Blocks (plugins)
        if len(self.plugins) > 0:
            args = ("> ,\n                <".join(tuple(p['instance'].replace("/graph/","",1) for i, p in self.plugins.items() if i != PEDALBOARD_INSTANCE_ID)))
            pbdata += "    ingen:block <%s> ;\n" % args

        # Ports
        portsyms = [":bpb",":bpm",":rolling","control_in","control_out"]
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
        with TextFileFlusher(os.path.join(bundlepath, "%s.ttl" % titlesym)) as fh:
            fh.write(pbdata)

    # -----------------------------------------------------------------------------------------------------------------
    # Host stuff - misc

    def set_pedalboard_size(self, width, height):
        self.pedalboard_size = [width, height]

    def set_link_enabled(self, enabled, saveConfig = False):
        if enabled and self.plugins[PEDALBOARD_INSTANCE_ID]['addressings'].get(":bpm", None) is not None:
            print("ERROR: link enabled while BPM is still addressed")

        self.transport_sync = "link" if enabled else "none"
        self.send_notmodified("feature_enable link %i" % int(enabled))

    def set_transport_bpb(self, bpb, sendMsg, callback=None, datatype='int'):
        self.transport_bpb = bpb

        if sendMsg:
            self.send_modified("transport %i %f %f" % (self.transport_rolling,
                                                       self.transport_bpb,
                                                       self.transport_bpm), callback, datatype)

        for pluginData in self.plugins.values():
            bpb_symbol = pluginData['designations'][self.DESIGNATIONS_INDEX_BPB]

            if bpb_symbol is not None:
                pluginData['ports'][bpb_symbol] = bpb
                if sendMsg:
                    self.msg_callback("param_set %s %s %f" % (pluginData['instance'], bpb_symbol, bpb))

    def set_transport_bpm(self, bpm, sendMsg, callback=None, datatype='int'):
        self.transport_bpm = bpm

        if sendMsg:
            self.send_modified("transport %i %f %f" % (self.transport_rolling,
                                                       self.transport_bpb,
                                                       self.transport_bpm), callback, datatype)

        for pluginData in self.plugins.values():
            bpm_symbol = pluginData['designations'][self.DESIGNATIONS_INDEX_BPM]

            if bpm_symbol is not None:
                pluginData['ports'][bpm_symbol] = bpm
                if sendMsg:
                    self.msg_callback("param_set %s %s %f" % (pluginData['instance'], bpm_symbol, bpm))

    def set_transport_rolling(self, rolling, sendMsg, callback=None, datatype='int'):
        self.transport_rolling = rolling

        if sendMsg:
            self.send_notmodified("transport %i %f %f" % (self.transport_rolling,
                                                          self.transport_bpb,
                                                          self.transport_bpm), callback, datatype)

        speed = 1.0 if rolling else 0.0

        for pluginData in self.plugins.values():
            speed_symbol = pluginData['designations'][self.DESIGNATIONS_INDEX_SPEED]

            if speed_symbol is not None:
                pluginData['ports'][speed_symbol] = speed
                if sendMsg:
                    self.msg_callback("param_set %s %s %f" % (pluginData['instance'], speed_symbol, speed))

    # -----------------------------------------------------------------------------------------------------------------
    # Host stuff - timers

    def statstimer_callback(self):
        data = get_jack_data(False)
        self.msg_callback("stats %0.1f %i" % (data['cpuLoad'], data['xruns']))

    def get_free_memory_value(self):
        if not self.memfile:
            return "??"

        self.memfile.seek(self.memfseek_free)
        memfree = float(int(self.memfile.readline().replace("kB","",1).strip()))

        self.memfile.seek(self.memfseek_buffers)
        memcached  = int(self.memfile.readline().replace("kB","",1).strip())

        self.memfile.seek(self.memfseek_cached)
        memcached += int(self.memfile.readline().replace("kB","",1).strip())

        self.memfile.seek(self.memfseek_shmmem)
        memcached -= int(self.memfile.readline().replace("kB","",1).strip())

        self.memfile.seek(self.memfseek_reclaim)
        memcached += int(self.memfile.readline().replace("kB","",1).strip())

        return "%0.1f" % ((self.memtotal-memfree-float(memcached))/self.memtotal*100.0)

    def memtimer_callback(self):
        self.msg_callback("mem_load " + self.get_free_memory_value())

    # -----------------------------------------------------------------------------------------------------------------
    # Addressing (public stuff)

    @gen.coroutine
    def address(self, instance, portsymbol, actuator_uri, label, minimum, maximum, value, steps, callback):
        instance_id = self.mapper.get_id(instance)
        pluginData  = self.plugins.get(instance_id, None)

        if pluginData is None:
            print("ERROR: Trying to address non-existing plugin instance %i: '%s'" % (instance_id, instance))
            callback(False)
            return

        # MIDI learn is not saved until a MIDI controller is moved.
        # So we need special casing for unlearn.
        if actuator_uri == kMidiUnlearnURI:
            return self.send_modified("midi_unmap %d %s" % (instance_id, portsymbol), callback, datatype='boolean')

        old_addressing = pluginData['addressings'].pop(portsymbol, None)

        if old_addressing is not None:
            # Need to remove old addressings first
            old_actuator_uri  = old_addressing['actuator_uri']
            old_actuator_type = self.addressings.get_actuator_type(old_actuator_uri)

            if old_actuator_type == Addressings.ADDRESSING_TYPE_MIDI:
                channel, controller = self.addressings.get_midi_cc_from_uri(old_actuator_uri)

                if actuator_uri != old_actuator_uri:
                    # Removing MIDI addressing
                    if portsymbol == ":bypass":
                        pluginData['bypassCC'] = (-1, -1)
                    else:
                        pluginData['midiCCs'][portsymbol] = (-1, -1, 0.0, 1.0)

                else:
                    # Changing ranges without changing MIDI CC
                    if -1 in (channel, controller):
                        # error
                        actuator_uri = None

                    else:
                        if portsymbol == ":bypass":
                            pluginData['bypassCC'] = (channel, controller)
                        else:
                            pluginData['midiCCs'][portsymbol] = (channel, controller, minimum, maximum)

                        pluginData['addressings'][portsymbol] = self.addressings.add_midi(instance_id,
                                                                                          portsymbol,
                                                                                          channel, controller,
                                                                                          minimum, maximum)

                        return self.send_modified("midi_map %d %s %i %i %f %f" % (instance_id,
                                                                                  portsymbol,
                                                                                  channel,
                                                                                  controller,
                                                                                  minimum,
                                                                                  maximum), callback, datatype='boolean')

            self.addressings.remove(old_addressing)
            self.pedalboard_modified = True

            yield gen.Task(self.addr_task_unaddressing, old_actuator_type,
                                                        old_addressing['instance_id'],
                                                        old_addressing['port'])

        if not actuator_uri or actuator_uri == kNullAddressURI:
            callback(True)
            return

        if self.addressings.is_hmi_actuator(actuator_uri) and not self.hmi.initialized:
            print("WARNING: Cannot address to HMI at this point")
            callback(False)
            return

        # MIDI learn is not an actual addressing
        if actuator_uri == kMidiLearnURI:
            return self.send_notmodified("midi_learn %d %s %f %f" % (instance_id,
                                                                     portsymbol,
                                                                     minimum,
                                                                     maximum), callback, datatype='boolean')

        if value < minimum:
            value = minimum
            needsValueChange = True
        elif value > maximum:
            value = maximum
            needsValueChange = True
        else:
            needsValueChange = False

        addressing = self.addressings.add(instance_id, pluginData['uri'], portsymbol, actuator_uri,
                                          label, minimum, maximum, steps, value)
        if addressing is None:
            callback(False)
            return

        if needsValueChange:
            yield gen.Task(self.hmi_parameter_set, instance_id, portsymbol, value)

        pluginData['addressings'][portsymbol] = addressing

        self.pedalboard_modified = True
        self.addressings.load_addr(actuator_uri, addressing, callback)

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

        if len(self.allpedalboards) == 0:
            callback(True, "")
            return

        banks = "All 0"

        if len(self.banks) > 0:
            banks += " "
            banks += " ".join('"%s" %d' % (bank['title'], i+1) for i, bank in enumerate(self.banks))

        callback(True, banks)

    def hmi_list_bank_pedalboards(self, bank_id, callback):
        logging.info("hmi list bank pedalboards")

        if bank_id < 0 or bank_id > len(self.banks):
            print("ERROR: Trying to list pedalboards using out of bounds bank id %i" % (bank_id))
            callback(False, "")
            return

        if bank_id == 0:
            pedalboards = self.allpedalboards
        else:
            pedalboards = self.banks[bank_id-1]['pedalboards']

        numBytesFree = 1024-64
        pedalboardsData = None

        num = 0
        for pb in pedalboards:
            if num > 50:
                break

            title   = pb['title'].replace('"', '').upper()[:31]
            data    = '"%s" %i' % (title, num)
            dataLen = len(data)

            if numBytesFree-dataLen-2 < 0:
                print("ERROR: Controller out of memory when listing pedalboards (stopping at %i)" % num)
                break

            num += 1

            if pedalboardsData is None:
                pedalboardsData = ""
            else:
                pedalboardsData += " "

            numBytesFree -= dataLen+1
            pedalboardsData += data

        if pedalboardsData is None:
            pedalboardsData = ""

        callback(True, pedalboardsData)

    def hmi_load_bank_pedalboard(self, bank_id, pedalboard_id, callback):
        logging.info("hmi load bank pedalboard")

        if bank_id < 0 or bank_id > len(self.banks):
            print("ERROR: Trying to load pedalboard using out of bounds bank id %i" % (bank_id))
            callback(False)
            return

        try:
            pedalboard_id = int(pedalboard_id)
        except:
            print("ERROR: Trying to load pedalboard using invalid pedalboard_id '%s'" % (pedalboard_id))
            callback(False)
            return

        if self.next_hmi_pedalboard is not None:
            print("NOTE: Delaying loading of %i:%i" % (bank_id, pedalboard_id))
            self.next_hmi_pedalboard = (bank_id, pedalboard_id)
            callback(False)
            return

        if bank_id == 0:
            pedalboards = self.allpedalboards
            navigateFootswitches = False
            navigateChannel      = 15
        else:
            bank        = self.banks[bank_id-1]
            pedalboards = bank['pedalboards']
            navigateFootswitches = bank['navigateFootswitches']

            if "navigateChannel" in bank.keys() and not navigateFootswitches:
                navigateChannel = int(bank['navigateChannel'])-1
            else:
                navigateChannel = 15

        if pedalboard_id < 0 or pedalboard_id >= len(pedalboards):
            print("ERROR: Trying to load pedalboard using out of bounds pedalboard id %i" % (pedalboard_id))
            callback(False)
            return

        self.next_hmi_pedalboard = (bank_id, pedalboard_id)
        callback(True)

        bundlepath = pedalboards[pedalboard_id]['bundle']

        def loaded2_callback(ok):
            if self.next_hmi_pedalboard is None:
                print("ERROR: Delayed loading is in corrupted state")
                return
            if ok:
                print("NOTE: Delayed loading of %i:%i has started" % self.next_hmi_pedalboard)
            else:
                print("ERROR: Delayed loading of %i:%i failed!" % self.next_hmi_pedalboard)

        def loaded_callback(ok):
            print("NOTE: Loading of %i:%i finished" % (bank_id, pedalboard_id))

            # Check if there's a pending pedalboard to be loaded
            next_pedalboard = self.next_hmi_pedalboard
            self.next_hmi_pedalboard = None

            if next_pedalboard != (bank_id, pedalboard_id):
                self.hmi_load_bank_pedalboard(next_pedalboard[0], next_pedalboard[1], loaded2_callback)
            else:
                self.processing_pending_flag = False
                self.send_notmodified("feature_enable processing 1")

        def load_callback(ok):
            self.bank_id = bank_id
            self.load(bundlepath)
            self.send_notmodified("midi_program_listen %d %d" % (int(not navigateFootswitches), navigateChannel),
                                  loaded_callback, datatype='boolean')

        def footswitch_callback(ok):
            self.setNavigateWithFootswitches(navigateFootswitches, load_callback)

        def hmi_clear_callback(ok):
            self.hmi.clear(footswitch_callback)

        if not self.processing_pending_flag:
            self.processing_pending_flag = True
            self.send_notmodified("feature_enable processing 0")

        self.reset(hmi_clear_callback)

    def hmi_parameter_get(self, instance_id, portsymbol, callback):
        logging.info("hmi parameter get")
        callback(self.addr_task_get_port_value(instance_id, portsymbol))

    def hmi_parameter_set(self, instance_id, portsymbol, value, callback):
        logging.info("hmi parameter set")
        try:
            instance = self.mapper.get_instance(instance_id)
        except KeyError:
            print("WARNING: hmi_parameter_set requested for non-existing plugin")
            callback(False)
            return

        pluginData = self.plugins[instance_id]

        if portsymbol == ":bypass":
            bypassed = bool(value)
            pluginData['bypassed'] = bypassed

            self.send_modified("bypass %d %d" % (instance_id, int(bypassed)), callback, datatype='boolean')
            self.msg_callback("param_set %s :bypass %f" % (instance, 1.0 if bypassed else 0.0))

            enabled_symbol = pluginData['designations'][self.DESIGNATIONS_INDEX_ENABLED]
            if enabled_symbol is None:
                return

            value = 0.0 if bypassed else 1.0
            pluginData['ports'][enabled_symbol] = value
            self.msg_callback("param_set %s %s %f" % (instance, enabled_symbol, value))

        elif portsymbol == ":presets":
            value = int(value)
            if value < 0 or value >= len(pluginData['mapPresets']):
                callback(False)
                return
            if instance_id == PEDALBOARD_INSTANCE_ID:
                value = int(pluginData['mapPresets'][value].replace("file:///",""))
                self.pedalpreset_load(value, callback)
            else:
                self.preset_load(instance, pluginData['mapPresets'][value], callback)

        elif instance_id == PEDALBOARD_INSTANCE_ID:
            if portsymbol == ":bpb":
                self.set_transport_bpb(value, True, callback)
            elif portsymbol == ":bpm":
                self.set_transport_bpm(value, True, callback)
            elif portsymbol == ":rolling":
                rolling = bool(value > 0.5)
                self.set_transport_rolling(rolling, True, callback)
            else:
                print("ERROR: Trying to set value for the wrong pedalboard port:", portsymbol)
                callback(False)
                return

            self.msg_callback("transport %i %f %f %s" % (self.transport_rolling,
                                                         self.transport_bpb,
                                                         self.transport_bpm,
                                                         self.transport_sync))

        else:
            oldvalue = pluginData['ports'].get(portsymbol, None)
            if oldvalue is None:
                print("WARNING: hmi_parameter_set requested for non-existing port", portsymbol)
                callback(False)
                return
            pluginData['ports'][portsymbol] = value
            self.send_modified("param_set %d %s %f" % (instance_id, portsymbol, value), callback, datatype='boolean')
            self.msg_callback("param_set %s %s %f" % (instance, portsymbol, value))

    def hmi_parameter_addressing_next(self, hardware_type, hardware_id, actuator_type, actuator_id, callback):
        logging.info("hmi parameter addressing next")
        actuator_hw = (hardware_type, hardware_id, actuator_type, actuator_id)
        self.addressings.hmi_load_next_hw(actuator_hw, callback)

    def hmi_save_current_pedalboard(self, callback):
        logging.info("hmi save current pedalboard")
        titlesym = symbolify(self.pedalboard_name)[:16]
        self.save_state_mainfile(self.pedalboard_path, self.pedalboard_name, titlesym)
        os.sync()
        callback(True)

    def hmi_reset_current_pedalboard(self, callback):
        logging.info("hmi reset current pedalboard")
        pb_values = get_pedalboard_plugin_values(self.pedalboard_path)
        callback(True)

        used_actuators = []

        for p in pb_values:
            instance    = "/graph/%s" % p['instance']
            instance_id = self.mapper.get_id(instance)
            pluginData  = self.plugins[instance_id]

            bypassed    = bool(p['bypassed'])
            diffBypass  = pluginData['bypassed'] != p['bypassed']

            if diffBypass:
                addressing = pluginData['addressings'].get(":bypass", None)
                if addressing is not None:
                    addressing['value'] = 1.0 if bypassed else 0.0
                    if addressing['actuator_uri'] not in used_actuators:
                        used_actuators.append(addressing['actuator_uri'])

            # if bypassed, do it now
            if diffBypass and bypassed:
                self.bypass(instance, True, None)
                #self.msg_callback("param_set %s :bypass 1.0" % (instance,))

            if p['preset'] and pluginData['preset'] != p['preset']:
                pluginData['preset'] = p['preset']
                self.send_notmodified("preset_load %d %s" % (instance_id, p['preset']))
                #self.msg_callback("preset %s %s" % (instance, p['preset']))

                addressing = pluginData['addressings'].get(":presets", None)
                if addressing is not None:
                    addressing['value'] = pluginData['mapPresets'].index(p['preset'])
                    if addressing['actuator_uri'] not in used_actuators:
                        used_actuators.append(addressing['actuator_uri'])

            for port in p['ports']:
                symbol = port['symbol']
                value  = port['value']

                if pluginData['ports'][symbol] == value:
                    continue

                pluginData['ports'][symbol] = value
                self.send_notmodified("param_set %d %s %f" % (instance_id, symbol, value))
                #self.msg_callback("param_set %s %s %f" % (instance, symbol, value))

                addressing = pluginData['addressings'].get(symbol, None)
                if addressing is not None:
                    addressing['value'] = value
                    if addressing['actuator_uri'] not in used_actuators:
                        used_actuators.append(addressing['actuator_uri'])

            # if not bypassed (enabled), do it at the end
            if diffBypass and not bypassed:
                self.bypass(instance, False, None)
                #self.msg_callback("param_set %s :bypass 0.0" % (instance,))

        self.pedalboard_modified = False
        self.addressings.load_current(used_actuators, (None, None))

    def hmi_tuner(self, status, callback):
        if status == "on":
            self.hmi_tuner_on(callback)
        else:
            self.hmi_tuner_off(callback)

    def hmi_tuner_on(self, callback):
        logging.info("hmi tuner on")

        def monitor_added(ok):
            if not ok or not connect_jack_ports("system:capture_%d" % self.current_tuner_port,
                                                "effect_%d:%s" % (TUNER_INSTANCE_ID, TUNER_INPUT_PORT)):
                self.send_notmodified("remove %d" % TUNER_INSTANCE_ID)
                callback(False)
                return

            if self.prefs.get("tuner-mutes-outputs", "true") != "false":
                self.mute()

            callback(True)

        def tuner_added(ok):
            if not ok:
                callback(False)
                return
            self.send_notmodified("monitor_output %d %s" % (TUNER_INSTANCE_ID, TUNER_MONITOR_PORT), monitor_added)

        self.send_notmodified("add %s %d" % (TUNER_URI, TUNER_INSTANCE_ID), tuner_added)

    def hmi_tuner_off(self, callback):
        logging.info("hmi tuner off")

        def tuner_removed(ok):
            self.unmute()
            callback(True)

        self.send_notmodified("remove %d" % TUNER_INSTANCE_ID, tuner_removed)

    def hmi_tuner_input(self, input_port, callback):
        logging.info("hmi tuner input")

        if 0 <= input_port > 2:
            callback(False)
            return

        disconnect_jack_ports("system:capture_%s" % self.current_tuner_port,
                              "effect_%d:%s" % (TUNER_INSTANCE_ID, TUNER_INPUT_PORT))

        connect_jack_ports("system:capture_%s" % input_port,
                           "effect_%d:%s" % (TUNER_INSTANCE_ID, TUNER_INPUT_PORT))

        self.current_tuner_port = input_port
        callback(True)

    @gen.coroutine
    def set_tuner_value(self, value):
        if value == 0.0:
            return

        freq, note, cents = find_freqnotecents(value)
        yield gen.Task(self.hmi.tuner, freq, note, cents)

    def hmi_get_truebypass_value(self, right, callback):
        """Query the True Bypass setting of the given channel."""
        logging.info("hmi true bypass get ({0})".format(right))
        
        bypassed = get_truebypass_value(right)
        callback(True, bypassed)

    def hmi_set_truebypass_value(self, right, bypassed, callback):
        """Change the True Bypass setting of the given channel."""
        logging.info("hmi true bypass set to ({0}, {1})".format(right, bypassed))

        set_truebypass_value(right, bypassed)
        
        # TODO should it return some more status?
        callback(True)

    def hmi_get_tempo_bpm(self, callback):
        """Get the Jack BPM."""
        logging.info("hmi tempo bpm get")
        bpm = get_jack_data(True)['bpm']
        callback(True, bpm)
        
    def hmi_set_tempo_bpm(self, bpm, callback):
        """Set the Jack BPM."""
        logging.info("hmi tempo bpm set to {0}".format(bpm))

        # Forward to mod-host. It will check assertions.
        self.send_notmodified("set_bpm {:f}".format(bpm))
        callback(True)

    def hmi_get_tempo_bpb(self, callback):
        """Get the Jack Beats Per Bar."""
        logging.info("hmi tempo bpb get")
        bpb = get_jack_data(True)['bpb']
        callback(True, bpb)
        
    def hmi_set_tempo_bpb(self, bpb, callback):
        """Set the Jack Beats Per Bar."""
        logging.info("hmi tempo bpb set to {0}".format(bpb))

        # Forward to mod-host. It will check assertions.
        self.send_notmodified("set_bpb {:f}".format(bpb))
        callback(True)
        
        
    # -----------------------------------------------------------------------------------------------------------------
    # JACK stuff

    # Get list of Hardware MIDI devices
    # returns (devsInUse, devList, names)
    def get_midi_ports(self):
        out_ports = {}
        full_ports = {}

        # Current setup
        for port_symbol, port_alias, _ in self.midiports:
            port_aliases = port_alias.split(";",1)
            port_alias   = port_aliases[0]
            if len(port_aliases) != 1:
                out_ports[port_alias] = port_symbol
            full_ports[port_symbol] = port_alias

        # Extra MIDI Outs
        ports = get_jack_hardware_ports(False, True)
        for port in ports:
            if not port.startswith(("system:midi_", "nooice")):
                continue
            alias = get_jack_port_alias(port)
            if not alias:
                continue
            title = alias.split("-",5)[-1].replace("-"," ").replace(";",".")
            out_ports[title] = port

        # Extra MIDI Ins
        ports = get_jack_hardware_ports(False, False)
        for port in ports:
            if not port.startswith(("system:midi_", "nooice")):
                continue
            alias = get_jack_port_alias(port)
            if not alias:
                continue
            title = alias.split("-",5)[-1].replace("-"," ").replace(";",".")
            if title in out_ports.keys():
                port = "%s;%s" % (port, out_ports[title])
            full_ports[port] = title

        devsInUse = []
        devList = []
        names = {}
        midiportIds = tuple(i[0] for i in self.midiports)
        for port_id, port_alias in full_ports.items():
            devList.append(port_id)
            if port_id in midiportIds:
                devsInUse.append(port_id)
            names[port_id] = port_alias + (" (in+out)" if port_alias in out_ports else " (in)")

        devList.sort()
        return (devsInUse, devList, names)

    def get_port_name_alias(self, portname):
        alias = get_jack_port_alias(portname)

        if alias:
            return alias.split("-",5)[-1].replace("-"," ").replace(";",".")

        return portname.split(":",1)[-1].title()

    # Set the selected MIDI devices
    # Will remove or add new JACK ports (in mod-ui) as needed
    def set_midi_devices(self, newDevs):
        def add_port(name, title, isOutput):
            index = int(name[-1])
            title = title.replace("-","_").replace(" ","_")

            if name.startswith("nooice"):
                index += 100

            self.msg_callback("add_hw_port /graph/%s midi %i %s %i" % (name.split(":",1)[-1], int(isOutput), title, index))

        def remove_port(name):
            removed_conns = []

            for ports in self.connections:
                jackports = (self._fix_host_connection_port(ports[0]), self._fix_host_connection_port(ports[1]))
                if name not in jackports:
                    continue
                disconnect_jack_ports(jackports[0], jackports[1])
                removed_conns.append(ports)

            for ports in removed_conns:
                self.connections.remove(ports)
                self.msg_callback("disconnect %s %s" % (ports[0], ports[1]))

            self.msg_callback("remove_hw_port /graph/%s" % (name.split(":",1)[-1]))

        midiportIds = tuple(i[0] for i in self.midiports)

        # remove
        for i in reversed(range(len(self.midiports))):
            port_symbol, port_alias, _ = self.midiports[i]
            if port_symbol in newDevs:
                continue

            if ";" in port_symbol:
                inp, outp = port_symbol.split(";",1)
                remove_port(inp)
                remove_port(outp)
            else:
                remove_port(port_symbol)

            self.midiports.pop(i)

        # add
        for port_symbol in newDevs:
            if port_symbol in midiportIds:
                continue

            if ";" in port_symbol:
                inp, outp = port_symbol.split(";",1)
                title_in  = self.get_port_name_alias(inp)
                title_out = self.get_port_name_alias(outp)
                title     = title_in + ";" + title_out
                add_port(inp, title_in, False)
                add_port(outp, title_out, True)
            else:
                title = self.get_port_name_alias(port_symbol)
                add_port(port_symbol, title, False)

            self.midiports.append([port_symbol, title, []])

    # -----------------------------------------------------------------------------------------------------------------
