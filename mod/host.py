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

from mod import get_hardware_descriptor, read_file_contents, safe_json_load, symbolify, TextFileFlusher
from mod.addressings import Addressings, HMI_ADDRESSING_TYPE_ENUMERATION, HMI_ADDRESSING_TYPE_REVERSE_ENUM
from mod.bank import list_banks, get_last_bank_and_pedalboard, save_last_bank_and_pedalboard
from mod.hmi import Menu
from mod.profile import Profile
from mod.protocol import Protocol, ProtocolError, process_resp
from modtools.utils import (
    charPtrToString,
    is_bundle_loaded, add_bundle_to_lilv_world, remove_bundle_from_lilv_world, rescan_plugin_presets,
    get_plugin_info, get_plugin_control_inputs_and_monitored_outputs, get_pedalboard_info, get_state_port_values,
    list_plugins_in_bundle, get_all_pedalboards, get_pedalboard_plugin_values,
    init_jack, close_jack, get_jack_data,
    init_bypass, get_jack_port_alias, get_jack_hardware_ports,
    has_serial_midi_input_port, has_serial_midi_output_port,
    has_midi_merger_output_port, has_midi_broadcaster_input_port,
    has_midi_beat_clock_sender_port,
    connect_jack_ports, disconnect_jack_ports,
    get_truebypass_value, set_truebypass_value, get_master_volume,
    set_util_callbacks, kPedalboardTimeAvailableBPB,
    kPedalboardTimeAvailableBPM, kPedalboardTimeAvailableRolling
)
from modtools.tempo import (
    convert_seconds_to_port_value_equivalent,
    get_divider_options,
    get_port_value
)
from mod.settings import (
    APP, LOG, DEFAULT_PEDALBOARD, LV2_PEDALBOARDS_DIR, PEDALBOARD_INSTANCE, PEDALBOARD_INSTANCE_ID, PEDALBOARD_URI,
    TUNER_URI, TUNER_INSTANCE_ID, TUNER_INPUT_PORT, TUNER_MONITOR_PORT, UNTITLED_PEDALBOARD_NAME,
    MIDI_BEAT_CLOCK_SENDER_URI, MIDI_BEAT_CLOCK_SENDER_INSTANCE_ID, MIDI_BEAT_CLOCK_SENDER_OUTPUT_PORT
)
from mod.tuner import find_freqnotecents

BANK_CONFIG_NOTHING         = 0
BANK_CONFIG_TRUE_BYPASS     = 1
BANK_CONFIG_PEDALBOARD_UP   = 2
BANK_CONFIG_PEDALBOARD_DOWN = 3

DISPLAY_BRIGHTNESS_0   = 0
DISPLAY_BRIGHTNESS_25  = 1
DISPLAY_BRIGHTNESS_50  = 2
DISPLAY_BRIGHTNESS_75  = 3
DISPLAY_BRIGHTNESS_100 = 4
DISPLAY_BRIGHTNESS_VALUES = (
    DISPLAY_BRIGHTNESS_0,
    DISPLAY_BRIGHTNESS_25,
    DISPLAY_BRIGHTNESS_50,
    DISPLAY_BRIGHTNESS_75,
    DISPLAY_BRIGHTNESS_100)

QUICK_BYPASS_MODE_1    = 0
QUICK_BYPASS_MODE_2    = 1
QUICK_BYPASS_MODE_BOTH = 2
QUICK_BYPASS_MODE_VALUES = (
    QUICK_BYPASS_MODE_1,
    QUICK_BYPASS_MODE_2,
    QUICK_BYPASS_MODE_BOTH)

DEFAULT_DISPLAY_BRIGHTNESS = DISPLAY_BRIGHTNESS_50
DEFAULT_QUICK_BYPASS_MODE  = QUICK_BYPASS_MODE_BOTH

# Special URI for non-addressed controls
kNullAddressURI = "null"

# Special URIs for midi-learn
kMidiLearnURI = "/midi-learn"
kMidiUnlearnURI = "/midi-unlearn"
kMidiCustomPrefixURI = "/midi-custom_" # to show current one

# URI for BPM sync (for non-addressed control ports)
kBpmURI ="/bpm"

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

    # HMI snapshots, reusing the same code for pedalboard snapshots but with reserved negative numbers
    HMI_SNAPSHOTS_OFFSET = 100
    HMI_SNAPSHOTS_LEFT   = 0 - (HMI_SNAPSHOTS_OFFSET + 0)
    HMI_SNAPSHOTS_RIGHT  = 0 - (HMI_SNAPSHOTS_OFFSET + 1)

    def __init__(self, hmi, prefs, msg_callback):
        if False:
            from mod.hmi import HMI
            hmi = HMI()

        self.hmi = hmi
        self.prefs = prefs
        self.msg_callback = msg_callback

        self.addr = ("localhost", 5555)
        self.readsock = None
        self.writesock = None
        self.crashed = False
        self.connected = False
        self._queue = []
        self._idle = True
        self.profile_applied = False

        self.addressings = Addressings()
        self.mapper = InstanceIdMapper()
        self.profile = Profile(self.profile_apply)
        self.banks = list_banks()
        self.descriptor = get_hardware_descriptor()

        self.current_tuner_port = 1
        self.current_tuner_mute = self.prefs.get("tuner-mutes-outputs", False, bool)

        self.allpedalboards = None
        self.bank_id = 0
        self.connections = []
        self.audioportsIn = []
        self.audioportsOut = []
        self.midiports = [] # [symbol, alias, pending-connections]
        self.midi_aggregated_mode = True
        self.hasSerialMidiIn = False
        self.hasSerialMidiOut = False
        self.pedalboard_empty    = True
        self.pedalboard_modified = False
        self.pedalboard_name     = ""
        self.pedalboard_path     = ""
        self.pedalboard_size     = [0,0]
        self.pedalboard_version  = 0
        self.current_pedalboard_snapshot_id = -1
        self.pedalboard_snapshots  = []
        self.next_hmi_pedalboard = None
        self.hmi_snapshots = [None, None]
        self.transport_rolling = False
        self.transport_bpb     = 4.0
        self.transport_bpm     = 120.0
        self.transport_sync    = "none"
        self.last_data_finish_msg = 0.0
        self.abort_progress_catcher = {}
        self.processing_pending_flag = False
        self.page_load_request_number = 0
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

                if os.path.exists("/sys/class/thermal/thermal_zone0/temp"):
                    self.thermalfile = open("/sys/class/thermal/thermal_zone0/temp", 'r')
                else:
                    self.thermalfile = None

                if os.path.exists("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"):
                    self.cpufreqfile = open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq", 'r')
                else:
                    self.cpufreqfile = None

        else:
            self.memtimer = None

        set_util_callbacks(self.jack_bufsize_changed,
                           self.jack_port_appeared,
                           self.jack_port_deleted,
                           self.true_bypass_changed)

        # Setup addressing callbacks
        self.addressings._task_addressing = self.addr_task_addressing
        self.addressings._task_unaddressing = self.addr_task_unaddressing
        self.addressings._task_set_value = self.addr_task_set_value
        self.addressings._task_get_plugin_data = self.addr_task_get_plugin_data
        self.addressings._task_get_plugin_presets = self.addr_task_get_plugin_presets
        self.addressings._task_get_port_value = self.addr_task_get_port_value
        self.addressings._task_store_address_data = self.addr_task_store_address_data
        self.addressings._task_hw_added = self.addr_task_hw_added
        self.addressings._task_hw_removed = self.addr_task_hw_removed
        self.addressings._task_act_added = self.addr_task_act_added
        self.addressings._task_act_removed = self.addr_task_act_removed

        # Register HMI protocol callbacks (they are without arguments here)
        Protocol.register_cmd_callback("hw_con", self.hmi_hardware_connected)
        Protocol.register_cmd_callback("hw_dis", self.hmi_hardware_disconnected)
        Protocol.register_cmd_callback("banks", self.hmi_list_banks)
        Protocol.register_cmd_callback("pedalboards", self.hmi_list_bank_pedalboards)
        Protocol.register_cmd_callback("pb", self.hmi_load_bank_pedalboard)
        Protocol.register_cmd_callback("g", self.hmi_parameter_get)
        Protocol.register_cmd_callback("s", self.hmi_parameter_set)
        Protocol.register_cmd_callback("n", self.hmi_parameter_addressing_next)
        Protocol.register_cmd_callback("pbs", self.hmi_save_current_pedalboard)
        Protocol.register_cmd_callback("pbr", self.hmi_reset_current_pedalboard)
        Protocol.register_cmd_callback("tu", self.hmi_tuner)
        Protocol.register_cmd_callback("tu_i", self.hmi_tuner_input)
        Protocol.register_cmd_callback("fn", self.hmi_footswitch_navigation)

        Protocol.register_cmd_callback("g_bp", self.hmi_get_truebypass_value)
        Protocol.register_cmd_callback("s_bp", self.hmi_set_truebypass_value)
        Protocol.register_cmd_callback("g_qbp", self.hmi_get_quick_bypass_mode)
        Protocol.register_cmd_callback("s_qbp", self.hmi_set_quick_bypass_mode)

        Protocol.register_cmd_callback("g_bpm", self.hmi_get_tempo_bpm)
        Protocol.register_cmd_callback("s_bpm", self.hmi_set_tempo_bpm)
        Protocol.register_cmd_callback("g_bpb", self.hmi_get_tempo_bpb)
        Protocol.register_cmd_callback("s_bpb", self.hmi_set_tempo_bpb)

        Protocol.register_cmd_callback("g_ssc", self.hmi_get_snapshot_prgch)
        Protocol.register_cmd_callback("s_ssc", self.hmi_set_snapshot_prgch)
        Protocol.register_cmd_callback("g_pbc", self.hmi_get_pedalboard_prgch)
        Protocol.register_cmd_callback("s_pbc", self.hmi_set_pedalboard_prgch)

        Protocol.register_cmd_callback("g_cls", self.hmi_get_clk_src)
        Protocol.register_cmd_callback("s_cls", self.hmi_set_clk_src)

        Protocol.register_cmd_callback("g_mclk", self.hmi_get_send_midi_clk)
        Protocol.register_cmd_callback("s_mclk", self.hmi_set_send_midi_clk)

        Protocol.register_cmd_callback("g_p", self.hmi_get_current_profile)
        Protocol.register_cmd_callback("r_p", self.hmi_retrieve_profile)
        Protocol.register_cmd_callback("s_p", self.hmi_store_profile)

        Protocol.register_cmd_callback("g_ex", self.hmi_get_exp_cv)
        Protocol.register_cmd_callback("s_ex", self.hmi_set_exp_cv)
        Protocol.register_cmd_callback("g_hp", self.hmi_get_hp_cv)
        Protocol.register_cmd_callback("s_hp", self.hmi_set_hp_cv)

        Protocol.register_cmd_callback("g_ex_m", self.hmi_get_exp_mode)
        Protocol.register_cmd_callback("s_ex_m", self.hmi_set_exp_mode)
        Protocol.register_cmd_callback("g_cvb", self.hmi_get_control_voltage_bias)
        Protocol.register_cmd_callback("s_cvb", self.hmi_set_control_voltage_bias)

        Protocol.register_cmd_callback("g_il", self.hmi_get_in_chan_link)
        Protocol.register_cmd_callback("s_il", self.hmi_set_in_chan_link)
        Protocol.register_cmd_callback("g_ol", self.hmi_get_out_chan_link)
        Protocol.register_cmd_callback("s_ol", self.hmi_set_out_chan_link)

        Protocol.register_cmd_callback("g_br", self.hmi_get_display_brightness)
        Protocol.register_cmd_callback("s_br", self.hmi_set_display_brightness)

        Protocol.register_cmd_callback("g_mv_c", self.hmi_get_master_volume_channel_mode)
        Protocol.register_cmd_callback("s_mv_c", self.hmi_set_master_volume_channel_mode)

        Protocol.register_cmd_callback("g_ps", self.hmi_get_play_status)
        Protocol.register_cmd_callback("s_ps", self.hmi_set_play_status)

        Protocol.register_cmd_callback("g_tum", self.hmi_get_tuner_mute)
        Protocol.register_cmd_callback("s_tum", self.hmi_set_tuner_mute)

        Protocol.register_cmd_callback("sl", self.hmi_snapshot_load)
        Protocol.register_cmd_callback("ss", self.hmi_snapshot_save)
        Protocol.register_cmd_callback("lp", self.hmi_page_load)

        # not used
        #Protocol.register_cmd_callback("get_pb_name", self.hmi_get_pb_name)

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
            name = name.replace(self.jack_slave_prefix+":","")
            if name.startswith("midi_"):
                ptype = "midi"
            elif name.startswith("cv_"):
                ptype = "cv"
            else:
                ptype = "audio"

            index = 100 + int(name.rsplit("_",1)[-1])
            title = name.title().replace(" ","_")
            self.msg_callback("add_hw_port /graph/%s %s %i %s %i" % (name, ptype, int(isOutput), title, index))
            return

        if self.midi_aggregated_mode:
            # new ports are ignored under midi aggregated mode
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
                elif isOutput:
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
        removed_conns = self.remove_port_from_connections(name)

        for port_symbol, port_alias, port_conns in self.midiports:
            if name == port_symbol or (";" in port_symbol and name in port_symbol.split(";",1)):
                port_conns += removed_conns
                break

        self.msg_callback("remove_hw_port /graph/%s" % (name.split(":",1)[-1]))

    def true_bypass_changed(self, left, right):
        self.msg_callback("truebypass %i %i" % (left, right))

    def remove_port_from_connections(self, name):
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

        return removed_conns

    # -----------------------------------------------------------------------------------------------------------------
    # Addressing callbacks

    def addr_task_addressing(self, atype, actuator, data, callback, send_hmi=True):
        if atype == Addressings.ADDRESSING_TYPE_HMI:
            if send_hmi:
                actuator_uri = self.addressings.hmi_hw2uri_map[actuator]
                return self.hmi.control_add(data, actuator, actuator_uri, callback)
            else:
                if callback is not None:
                    callback(True)
                return

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
                                                                                      actuator[0], # device id
                                                                                      actuator[1], # actuator id
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
        if atype == Addressings.ADDRESSING_TYPE_BPM:
            if callback is not None:
                callback(True)
            return

        print("ERROR: Invalid addressing requested for", actuator)
        callback(False)
        return

    def addr_task_unaddressing(self, atype, instance_id, portsymbol, callback, send_hmi=True, hw_ids=None):
        if atype == Addressings.ADDRESSING_TYPE_HMI:
            self.pedalboard_modified = True
            if send_hmi:
                return self.hmi.control_rm(hw_ids, callback)
            else:
                if callback is not None:
                    callback(True)
                return

        if atype == Addressings.ADDRESSING_TYPE_CC:
            return self.send_modified("cc_unmap %d %s" % (instance_id, portsymbol), callback, datatype='boolean')

        if atype == Addressings.ADDRESSING_TYPE_MIDI:
            return self.send_modified("midi_unmap %d %s" % (instance_id, portsymbol), callback, datatype='boolean')

        if atype == Addressings.ADDRESSING_TYPE_BPM:
            if callback is not None:
                callback(True)
            return

        print("ERROR: Invalid unaddressing requested")
        callback(False)
        return

    def addr_task_set_value(self, atype, actuator, data, callback):
        if atype == Addressings.ADDRESSING_TYPE_HMI:
            if data['hmitype'] & HMI_ADDRESSING_TYPE_ENUMERATION:
                options = tuple(o[0] for o in data['options'])
                try:
                    value = options.index(data['value'])
                except ValueError:
                    logging.error("[host] address set value not in list %f", data['value'])
                    callback(False)
                    return
            else:
                value = data['value']
            return self.hmi.control_set(actuator, value, callback)

        if atype == Addressings.ADDRESSING_TYPE_CC:
            # FIXME not supported yet, this line never gets reached
            pass

        # Everything else has nothing
        callback(True)

    def addr_task_get_plugin_data(self, instance_id):
        return self.plugins[instance_id]

    def addr_task_get_plugin_presets(self, uri):
        if uri == PEDALBOARD_URI:
            if self.current_pedalboard_snapshot_id < 0 or len(self.pedalboard_snapshots) == 0:
                return []
            self.plugins[PEDALBOARD_INSTANCE_ID]['preset'] = "file:///%i" % self.current_pedalboard_snapshot_id
            presets = self.pedalboard_snapshots
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

    def ping_hmi(self):
        ioloop.IOLoop.instance().call_later(2, self.ping_hmi)
        self.hmi.ping(None)

    def wait_hmi_initialized(self, callback):
        if (self.hmi.initialized or self.hmi.isFake()) and self.profile_applied:
            print("HMI initialized right away")
            callback(True)
            return

        def retry():
            if ((self.hmi.initialized or self.hmi.isFake()) and self.profile_applied) or self._attemptNumber >= 20:
                print("HMI initialized FINAL", self._attemptNumber, self.hmi.initialized)
                del self._attemptNumber
                #ioloop.IOLoop.instance().call_later(5, self.ping_hmi)
                callback(self.hmi.initialized)
            else:
                self._attemptNumber += 1
                ioloop.IOLoop.instance().call_later(0.1, retry)
                print("HMI initialized waiting", self._attemptNumber)

        self._attemptNumber = 0
        retry()

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

        # current aggregated mode
        self.midi_aggregated_mode = has_midi_broadcaster_input_port() and has_midi_merger_output_port()

        # load everything
        if self.allpedalboards is None:
            self.allpedalboards = get_all_good_pedalboards()

        bank_id, pedalboard = get_last_bank_and_pedalboard()

        # ensure HMI is initialized by now
        yield gen.Task(self.wait_hmi_initialized)

        if pedalboard and os.path.exists(pedalboard):
            self.bank_id = bank_id
            self.load(pedalboard)

        else:
            self.bank_id = 0

            if os.path.exists(DEFAULT_PEDALBOARD):
                self.load(DEFAULT_PEDALBOARD, True)

        # Setup MIDI program navigation
        midi_pb_prgch, midi_ss_prgch = self.profile.get_midi_prgch_channels()
        if midi_pb_prgch >= 1 and midi_pb_prgch <= 16:
            self.send_notmodified("monitor_midi_program %d 1" % (midi_pb_prgch-1))
        if midi_ss_prgch >= 1 and midi_ss_prgch <= 16:
            self.send_notmodified("monitor_midi_program %d 1" % (midi_ss_prgch-1))

        # Wait for all mod-host messages to be processed
        yield gen.Task(self.send_notmodified, "feature_enable processing 2", datatype='boolean')

        # After all is set, update the HMI
        if self.hmi.initialized:
            yield gen.Task(self.send_hmi_boot)

        # All set, disable HW bypass now
        init_bypass()

    def init_jack(self):
        self.audioportsIn  = []
        self.audioportsOut = []

        if not init_jack():
            self.hasSerialMidiIn = False
            self.hasSerialMidiOut = False
            return

        for port in get_jack_hardware_ports(True, False):
            self.audioportsIn.append(port.split(":",1)[-1])

        for port in get_jack_hardware_ports(True, True):
            self.audioportsOut.append(port.split(":",1)[-1])

        self.hasSerialMidiIn = has_serial_midi_input_port()
        self.hasSerialMidiOut = has_serial_midi_output_port()

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
                "ranges"      : {},
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

    def send_hmi_boot(self, callback):
        display_brightness = self.prefs.get("display-brightness", DEFAULT_DISPLAY_BRIGHTNESS, int, DISPLAY_BRIGHTNESS_VALUES)
        quick_bypass_mode = self.prefs.get("quick-bypass-mode", DEFAULT_QUICK_BYPASS_MODE, int, QUICK_BYPASS_MODE_VALUES)
        master_chan_mode = self.profile.get_master_volume_channel_mode()
        master_chan_is_mode_2 = master_chan_mode == Profile.MASTER_VOLUME_CHANNEL_MODE_2
        pb_name = self.pedalboard_name or UNTITLED_PEDALBOARD_NAME

        def send_boot(_):
            self.hmi.send("boot {} {} {} {} {} {} {}".format(display_brightness,
                                                              quick_bypass_mode,
                                                              int(self.current_tuner_mute),
                                                              self.profile.get_index(),
                                                              master_chan_mode,
                                                              get_master_volume(master_chan_is_mode_2),
                                                              pb_name), callback)
        if self.isBankFootswitchNavigationOn():
            self.hmi.send("mc {} 1".format(Menu.FOOTSWITCH_NAVEG_ID), send_boot)
        else:
            send_boot(True)

    @gen.coroutine
    def reconnect_hmi(self, hmi):
        abort_catcher = self.abort_previous_loading_progress("reconnect_hmi")
        self.hmi = hmi

        # Wait for init
        yield gen.Task(self.wait_hmi_initialized)

        if not self.hmi.initialized:
            return

        self.profile.apply_first()
        self.send_hmi_boot()

        actuators = [actuator['uri'] for actuator in self.descriptor.get('actuators', [])]
        self.addressings.current_page = 0
        self.addressings.load_current(actuators, (None, None), False, abort_catcher)

    # -----------------------------------------------------------------------------------------------------------------

    def isBankFootswitchNavigationOn(self):
        return (
            self.descriptor.get("hmi_bank_navigation", False) and
            self.prefs.get("bank-footswitch-navigation", False)
        )

    def setNavigateWithFootswitches(self, enabled, callback):
        def foot2_callback(_):
            acthw  = self.addressings.hmi_uri2hw_map["/hmi/footswitch2"]
            cfgact = BANK_CONFIG_PEDALBOARD_UP if enabled else BANK_CONFIG_NOTHING
            self.hmi.bank_config(acthw, cfgact, callback)

        acthw  = self.addressings.hmi_uri2hw_map["/hmi/footswitch1"]
        cfgact = BANK_CONFIG_PEDALBOARD_DOWN if enabled else BANK_CONFIG_NOTHING
        self.hmi.bank_config(acthw, cfgact, foot2_callback)

    # -----------------------------------------------------------------------------------------------------------------

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

        else:
            if self.allpedalboards is None:
                self.allpedalboards = get_all_good_pedalboards()
            bank_id = 0
            pedalboards = self.allpedalboards

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

        def cb_migi_ss_prgch(_):
            midi_ss_prgch = self.profile.get_midi_prgch_channel("snapshot")
            if midi_ss_prgch >= 1 and midi_ss_prgch <= 16:
                self.send_notmodified("monitor_midi_program %d 1" % (midi_ss_prgch-1),
                                      callback, datatype='boolean')
            else:
                callback(True)

        def cb_migi_pb_prgch(_):
            midi_pb_prgch = self.profile.get_midi_prgch_channel("pedalboard")
            if midi_pb_prgch >= 1 and midi_pb_prgch <= 16:
                self.send_notmodified("monitor_midi_program %d 1" % (midi_pb_prgch-1),
                                      cb_migi_ss_prgch, datatype='boolean')
            else:
                cb_migi_ss_prgch(True)

        def cb_footswitches(_):
            self.setNavigateWithFootswitches(True, cb_migi_pb_prgch)

        def cb_set_initial_state(_):
            cb = cb_footswitches if self.isBankFootswitchNavigationOn() else cb_migi_pb_prgch
            self.hmi.initial_state(bank_id, pedalboard_id, pedalboards, cb)

        if self.hmi.initialized:
            self.setNavigateWithFootswitches(False, cb_set_initial_state)
        else:
            cb_migi_pb_prgch(True)

    def start_session(self, callback):
        midi_pb_prgch, midi_ss_prgch = self.profile.get_midi_prgch_channels()
        if midi_pb_prgch >= 1 and midi_pb_prgch <= 16:
            self.send_notmodified("monitor_midi_program %d 0" % (midi_pb_prgch-1))
        if midi_ss_prgch >= 1 and midi_ss_prgch <= 16:
            self.send_notmodified("monitor_midi_program %d 0" % (midi_ss_prgch-1))

        self.banks = []
        self.allpedalboards = []

        if not self.hmi.initialized:
            callback(True)
            return

        def footswitch_addr2_callback(_):
            self.addressings.hmi_load_first("/hmi/footswitch2", callback)

        def footswitch_addr1_callback(_):
            self.addressings.hmi_load_first("/hmi/footswitch1", footswitch_addr2_callback)

        def footswitch_bank_callback(_):
            self.setNavigateWithFootswitches(False, footswitch_addr1_callback)

        self.hmi.ui_con(footswitch_bank_callback)

    def end_session(self, callback):
        self.banks = list_banks()
        self.allpedalboards = get_all_good_pedalboards()

        if not self.hmi.initialized:
            callback(True)
            return

        def initialize_callback(_):
            self.initialize_hmi(False, callback)

        self.hmi.ui_dis(initialize_callback)

    # -----------------------------------------------------------------------------------------------------------------
    # Message handling

    def process_read_message(self, msg):
        msg = msg[:-1].decode("utf-8", errors="ignore")
        logging.debug("[host] received <- %s", repr(msg))

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
                    abort_catcher = self.abort_previous_loading_progress("process_read_message_body")
                    value = int(value)
                    if value < 0 or value >= len(pluginData['mapPresets']):
                        return

                    try:
                        if instance_id == PEDALBOARD_INSTANCE_ID:
                            value = int(pluginData['mapPresets'][value].replace("file:///",""))
                            yield gen.Task(self.snapshot_load_gen_helper, value, False, abort_catcher)
                        else:
                            yield gen.Task(self.preset_load, instance, pluginData['mapPresets'][value], abort_catcher)
                    except Exception as e:
                        logging.exception(e)

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

        elif cmd == "midi_program_change":
            msg_data = msg[len(cmd)+1:].split(" ", 2)
            program  = int(msg_data[0])
            channel  = int(msg_data[1])+1

            if channel == self.profile.get_midi_prgch_channel("pedalboard"):
                bank_id = self.bank_id
                if self.bank_id > 0 and self.bank_id <= len(self.banks):
                    pedalboards = self.banks[self.bank_id-1]['pedalboards']
                else:
                    pedalboards = self.allpedalboards

                if program >= 0 and program < len(pedalboards):
                    try:
                        yield gen.Task(self.hmi_load_bank_pedalboard, bank_id, program)
                    except Exception as e:
                        logging.exception(e)

            elif channel == self.profile.get_midi_prgch_channel("snapshot"):
                abort_catcher = self.abort_previous_loading_progress("midi_program_change")
                try:
                    yield gen.Task(self.snapshot_load_gen_helper, program, False, abort_catcher)
                except Exception as e:
                    logging.exception(e)

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

            if self.hmi.initialized:
                try:
                    yield gen.Task(self.hmi.set_profile_value, Menu.TEMPO_BPM_ID, bpm)
                except Exception as e:
                    logging.exception(e)

        elif cmd == "data_finish":
            now  = time.clock()
            diff = now-self.last_data_finish_msg

            if diff >= 0.5:
                self.send_output_data_ready(now)

            else:
                diff = (0.5-diff)/0.5*0.064
                ioloop.IOLoop.instance().call_later(diff, self.send_output_data_ready)

        else:
            logging.error("[host] unrecognized command: %s", cmd)

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
            logging.debug("[host] popped from queue: %s", msg)
        except IndexError:
            self._idle = True
            return

        if self.writesock is None:
            self.process_write_queue()
            return

        def check_response(resp):
            if callback is not None:
                resp = resp.decode("utf-8", errors="ignore")
                logging.debug("[host] received <- %s", repr(resp))

                if datatype == 'string':
                    r = resp
                elif not resp.startswith("resp"):
                    logging.error("[host] protocol error: %s (for msg: '%s')", ProtocolError(resp), msg)
                    r = None
                else:
                    r = resp.replace("resp ", "").replace("\0", "").strip()

                callback(process_resp(r, datatype))

            self.process_write_queue()

        self._idle = False
        logging.debug("[host] sending -> %s", msg)

        encmsg = "%s\0" % str(msg)
        self.writesock.write(encmsg.encode("utf-8"))
        self.writesock.read_until(b"\0", check_response)

    # send data to host, set modified flag to true
    def send_modified(self, msg, callback=None, datatype='int'):
        self.pedalboard_modified = True

        if self.crashed:
            if callback is not None:
                callback(process_resp(None, datatype))
            return

        self._queue.append((msg, callback, datatype))
        if self._idle:
            self.process_write_queue()

    # send data to host, don't change modified flag
    def send_notmodified(self, msg, callback=None, datatype='int'):
        if self.crashed:
            if callback is not None:
                callback(process_resp(None, datatype))
            return

        self._queue.append((msg, callback, datatype))
        logging.debug("[host] idle? -> %i", self._idle)
        if self._idle:
            self.process_write_queue()

    # -----------------------------------------------------------------------------------------------------------------
    # Host stuff

    def abort_previous_loading_progress(self, caller):
        p = self.abort_progress_catcher
        self.abort_progress_catcher = {}
        p['abort'] = True
        p['caller'] = caller
        return self.abort_progress_catcher

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
        websocket.write_message(self.get_system_stats_message())
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
                self.set_link_enabled()
            elif self.transport_sync == "midi_clock_slave":
                self.set_midi_clock_slave_enabled()

        midiports = []
        for port_id, port_alias, _ in self.midiports:
            if ";" in port_id:
                inp, outp = port_id.split(";",1)
                midiports.append(inp)
                midiports.append(outp)
            else:
                midiports.append(port_id)

        # Control Voltage or Audio In
        for i in range(len(self.audioportsIn)):
            name  = self.audioportsIn[i]
            title = name.title().replace(" ","_")
            if name.startswith("cv_"):
                websocket.write_message("add_hw_port /graph/%s cv 0 %s %i" % (name, title, i+1))
            else:
                websocket.write_message("add_hw_port /graph/%s audio 0 %s %i" % (name, title, i+1))

        # Control Voltage or Audio Out
        for i in range(len(self.audioportsOut)):
            name  = self.audioportsOut[i]
            title = name.title().replace(" ","_")
            if name.startswith("cv_"):
                websocket.write_message("add_hw_port /graph/%s cv 1 %s %i" % (name, title, i+1))
            else:
                websocket.write_message("add_hw_port /graph/%s audio 1 %s %i" % (name, title, i+1))

        # MIDI In
        if self.midi_aggregated_mode:
            if has_midi_merger_output_port():
                websocket.write_message("add_hw_port /graph/midi_merger_out midi 0 All_MIDI_In 1")

        else: # 'legacy' mode until version 1.6
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
        if self.midi_aggregated_mode:
            if has_midi_broadcaster_input_port():
                websocket.write_message("add_hw_port /graph/midi_broadcaster_in midi 1 All_MIDI_Out 1")

        else:
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

        websocket.write_message("loading_end %d" % self.current_pedalboard_snapshot_id)

    # -----------------------------------------------------------------------------------------------------------------
    # Host stuff - add & remove bundles

    def add_bundle(self, bundlepath, callback):
        if is_bundle_loaded(bundlepath):
            print("NOTE: Skipped add_bundle, already in world")
            callback((False, "Bundle already loaded"))
            return

        def host_callback(_):
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

        def host_callback(_):
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
        self.snapshot_clear()

        self.pedalboard_empty    = True
        self.pedalboard_modified = False
        self.pedalboard_name     = ""
        self.pedalboard_path     = ""
        self.pedalboard_size     = [0,0]
        self.pedalboard_version  = 0

        save_last_bank_and_pedalboard(0, "")
        self.init_plugins_data()
        self.send_notmodified("remove -1", host_callback, datatype='boolean')

    def paramhmi_set(self, instance, portsymbol, value, callback):
        if instance == 'pedalboard':
            test = '/' + instance
        elif instance.startswith('/graph'):
            test = instance
        else:
            test =  '/graph/' + instance
        instance_id = self.mapper.get_id_without_creating(test)
        plugin_data = self.plugins.get(instance_id, None)

        if plugin_data is None:
            print("ERROR: Trying to set param for non-existing plugin instance %i: '%s'" % (instance_id, instance))
            if callback is not None:
                callback(False)
            return

        current_addressing = plugin_data['addressings'].get(portsymbol, None)
        # Not addressed, not need to send control_set to the HMI
        if current_addressing is None:
            if callback is not None:
                callback(True)
            return

        actuator_uri = current_addressing['actuator_uri']
        if self.addressings.get_actuator_type(actuator_uri) != Addressings.ADDRESSING_TYPE_HMI:
            if callback is not None:
                callback(True)
            return

        addressings = self.addressings.hmi_addressings[actuator_uri]
        addressings_addrs = addressings['addrs']

        if self.addressings.pages_cb:
            if current_addressing.get('page', None) == self.addressings.current_page:
                hw_id = self.addressings.hmi_uri2hw_map[actuator_uri]
                self.hmi.control_set(hw_id, float(value), callback)

            elif callback is not None:
                callback(True)

        else:
            current_index = addressings['idx']
            current_port_index = addressings_addrs.index(current_addressing)

            # If currently displayed on HMI screen, then we need to set the new value on the screen
            if current_index == current_port_index:
                hw_id = self.addressings.hmi_uri2hw_map[actuator_uri]
                self.hmi.control_set(hw_id, float(value), callback)

            elif callback is not None:
                callback(True)

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
            ranges = {}

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
                "ranges"      : ranges,
                "badports"    : badports,
                "designations": (enabled_symbol, freewheel_symbol, bpb_symbol, bpm_symbol, speed_symbol),
                "outputs"     : dict((symbol, None) for symbol in allports['monitoredOutputs']),
                "preset"      : "",
                "mapPresets"  : []
            }

            for output in allports['monitoredOutputs']:
                self.send_notmodified("monitor_output %d %s" % (instance_id, output))

            if len(self.pedalboard_snapshots) > 0:
                self.plugins_added.append(instance_id)

            callback(True)
            self.msg_callback("add %s %s %.1f %.1f %d" % (instance, uri, x, y, int(bypassed)))

        self.send_modified("add %s %d" % (uri, instance_id), host_callback, datatype='int')

    def add_used_actuators(self, actuator_uri, used_hmi_actuators, used_hw_ids):
        used_hmi_actuators.append(actuator_uri)
        hw_id = self.addressings.hmi_uri2hw_map[actuator_uri]
        used_hw_ids.append(hw_id)

    @gen.coroutine
    def remove_plugin(self, instance, callback):
        instance_id = self.mapper.get_id_without_creating(instance)

        try:
            pluginData = self.plugins.pop(instance_id)
        except KeyError:
            callback(False)
            return

        if len(self.pedalboard_snapshots) > 0:
            self.plugins_removed.append(instance)
            if instance_id in self.plugins_added:
                self.plugins_added.remove(instance_id)

        used_hmi_actuators = []
        used_hw_ids = []

        for symbol in [symbol for symbol in pluginData['addressings'].keys()]:
            addressing    = pluginData['addressings'].pop(symbol)
            actuator_uri  = addressing['actuator_uri']
            actuator_type = self.addressings.get_actuator_type(actuator_uri)
            was_active = self.addressings.remove(addressing)
            if actuator_type == Addressings.ADDRESSING_TYPE_HMI:
                if actuator_uri not in used_hmi_actuators and was_active:
                    group_actuators = self.addressings.get_group_actuators(actuator_uri)
                    if group_actuators:
                        for i in range(len(group_actuators)):
                            self.add_used_actuators(group_actuators[i], used_hmi_actuators, used_hw_ids)
                    else:
                        self.add_used_actuators(actuator_uri, used_hmi_actuators, used_hw_ids)

            elif actuator_type == Addressings.ADDRESSING_TYPE_CC:
                try:
                    yield gen.Task(self.addr_task_unaddressing, actuator_type,
                                                                addressing['instance_id'],
                                                                addressing['port'])
                except Exception as e:
                    logging.exception(e)

        def host_callback(ok):
            removed_connections = []
            for ports in self.connections:
                if ports[0].rsplit("/",1)[0] == instance or ports[1].rsplit("/",1)[0] == instance:
                    removed_connections.append(ports)
            for ports in removed_connections:
                self.connections.remove(ports)
                self.msg_callback("disconnect %s %s" % (ports[0], ports[1]))

            self.msg_callback("remove %s" % (instance))
            callback(ok)

        def hmi_callback(_):
            self.send_modified("remove %d" % instance_id, host_callback, datatype='boolean')

        @gen.coroutine
        def hmi_control_rm_callback(_):
            for actuator_uri in used_hmi_actuators:
                try:
                    yield gen.Task(self.addressings.hmi_load_current, actuator_uri)
                except Exception as e:
                    logging.exception(e)
            hmi_callback(True)

        if self.hmi.initialized and len(used_hw_ids) > 0:
            # Remove active addressed port from HMI
            self.hmi.control_rm(used_hw_ids, hmi_control_rm_callback)
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
        # mod-host is supposed to take care of this one
        # self.send_notmodified("param_set %d %s %f" % (instance_id, enabled_symbol, value))

    def param_set(self, port, value, callback):
        instance, symbol = port.rsplit("/", 1)
        instance_id = self.mapper.get_id_without_creating(instance)
        pluginData  = self.plugins[instance_id]

        if symbol in pluginData['designations']:
            print("ERROR: Trying to modify a specially designated port '%s', stop!" % symbol)
            callback(False)
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

    def preset_load(self, instance, uri, abort_catcher, callback):
        instance_id = self.mapper.get_id_without_creating(instance)
        current_pedal = self.pedalboard_path
        pluginData = self.plugins[instance_id]
        pluginData['nextPreset'] = uri

        def preset_callback(state):
            if not state:
                callback(False)
                return
            if self.pedalboard_path != current_pedal:
                print("WARNING: Pedalboard changed during preset_show request")
                callback(False)
                return
            if pluginData['nextPreset'] != uri:
                print("WARNING: Preset changed during preset_load request")
                callback(False)
                return
            if abort_catcher.get('abort', False):
                print("WARNING: Abort triggered during preset_load request, caller:", abort_catcher['caller'])
                callback(False)
                return

            pluginData['preset'] = uri
            self.msg_callback("preset %s %s" % (instance, uri))

            used_actuators = []

            for symbol, value in get_state_port_values(state).items():
                if symbol in pluginData['designations'] or pluginData['ports'].get(symbol, None) in (value, None):
                    continue

                minimum, maximum = pluginData['ranges'][symbol]
                if value < minimum:
                    print("ERROR: preset_load with value below minimum: symbol '%s', value %f" % (symbol, value))
                    value = minimum
                elif value > maximum:
                    print("ERROR: preset_load with value above maximum: symbol '%s', value %f" % (symbol, value))
                    value = maximum

                pluginData['ports'][symbol] = value

                self.msg_callback("param_set %s %s %f" % (instance, symbol, value))

                addressing = pluginData['addressings'].get(symbol, None)
                if addressing is not None:
                    addressing['value'] = value
                    if addressing['actuator_uri'] not in used_actuators:
                        used_actuators.append(addressing['actuator_uri'])

            self.addressings.load_current(used_actuators, (instance_id, ":presets"), True, abort_catcher)

            # callback must be last action
            callback(True)

        def host_callback(ok):
            if not ok:
                callback(False)
                return
            if self.pedalboard_path != current_pedal:
                print("WARNING: Pedalboard changed during preset_load request")
                callback(False)
                return
            if pluginData['nextPreset'] != uri:
                print("WARNING: Preset changed during preset_load request")
                callback(False)
                return
            if abort_catcher.get('abort', False):
                print("WARNING: Abort triggered during preset_load request, caller:", abort_catcher['caller'])
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

        def start(_):
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

        def start(_):
            rmtree(bundlepath)
            rescan_plugin_presets(plugin_uri)
            pluginData['preset'] = ""
            self.msg_callback("preset %s null" % instance)
            callback(True)

        self.remove_bundle(bundlepath, False, start)

    # -----------------------------------------------------------------------------------------------------------------
    # Host stuff - pedalboard snapshots

    def snapshot_make(self, name):
        self.pedalboard_modified = True

        snapshot = {
            "name": name,
            "data": {},
        }

        for instance_id, pluginData in self.plugins.items():
            if instance_id == PEDALBOARD_INSTANCE_ID:
                continue
            instance = pluginData['instance'].replace("/graph/","",1)
            snapshot['data'][instance] = {
                "bypassed": pluginData['bypassed'],
                "ports"   : pluginData['ports'].copy(),
                "preset"  : pluginData['preset'],
            }

        return snapshot

    def snapshot_name(self, idx=None):
        if idx is None:
            idx = self.current_pedalboard_snapshot_id
        if idx < 0 or idx >= len(self.pedalboard_snapshots) or self.pedalboard_snapshots[idx] is None:
            return None
        return self.pedalboard_snapshots[idx]['name']

    def snapshot_init(self):
        snapshot = self.snapshot_make("Default")
        self.plugins_added   = []
        self.plugins_removed = []
        self.current_pedalboard_snapshot_id = 0
        self.pedalboard_snapshots = [snapshot]

    def snapshot_clear(self):
        self.plugins_added   = []
        self.plugins_removed = []
        self.current_pedalboard_snapshot_id = -1
        self.pedalboard_snapshots = []

    def snapshot_disable(self, callback):
        self.snapshot_clear()
        self.pedalboard_modified = True
        self.address(PEDALBOARD_INSTANCE, ":presets", None, "", 0, 0, 0, 0, None, callback)

    def snapshot_save(self):
        idx = self.current_pedalboard_snapshot_id

        if idx < 0 or idx >= len(self.pedalboard_snapshots) or self.pedalboard_snapshots[idx] is None:
            return False

        name   = self.pedalboard_snapshots[idx]['name']
        snapshot = self.snapshot_make(name)
        self.pedalboard_snapshots[idx] = snapshot
        return True

    def snapshot_saveas(self, name):
        if len(self.pedalboard_snapshots) == 0:
            self.snapshot_init()

        preset = self.snapshot_make(name)
        self.pedalboard_snapshots.append(preset)

        self.current_pedalboard_snapshot_id = len(self.pedalboard_snapshots)-1
        return self.current_pedalboard_snapshot_id

    def snapshot_rename(self, idx, title):
        if idx < 0 or idx >= len(self.pedalboard_snapshots) or self.pedalboard_snapshots[idx] is None:
            return False

        self.pedalboard_modified = True
        self.pedalboard_snapshots[idx]['name'] = title
        return True

    def snapshot_remove(self, idx):
        if idx < 0 or idx >= len(self.pedalboard_snapshots) or self.pedalboard_snapshots[idx] is None:
            return False

        self.pedalboard_modified = True
        self.pedalboard_snapshots[idx] = None
        return True

    # helper function for gen.Task, which has troubles calling into a coroutine directly
    def snapshot_load_gen_helper(self, idx, from_hmi, abort_catcher, callback):
        self.snapshot_load(idx, from_hmi, abort_catcher, callback)

    @gen.coroutine
    def snapshot_load(self, idx, from_hmi, abort_catcher, callback):
        if idx in (self.HMI_SNAPSHOTS_LEFT, self.HMI_SNAPSHOTS_RIGHT):
            snapshot = self.hmi_snapshots[abs(idx + self.HMI_SNAPSHOTS_OFFSET)]
            is_hmi_snapshot = True

        else:
            if idx < 0 or idx >= len(self.pedalboard_snapshots):
                callback(False)
                return

            snapshot = self.pedalboard_snapshots[idx]
            is_hmi_snapshot = False

            if snapshot is None:
                print("ERROR: Asked to load an invalid pedalboard preset, number", idx)
                callback(False)
                return

            self.current_pedalboard_snapshot_id = idx
            self.plugins[PEDALBOARD_INSTANCE_ID]['preset'] = "file:///%i" % idx

        used_actuators = []

        for instance, data in snapshot['data'].items():
            if abort_catcher.get('abort', False):
                print("WARNING: Abort triggered during snapshot_load request, caller:", abort_catcher['caller'])
                callback(False)
                return

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
                try:
                    yield gen.Task(self.bypass, instance, True)
                except Exception as e:
                    logging.exception(e)

            if data['preset'] and data['preset'] != pluginData['preset']:
                self.msg_callback("preset %s %s" % (instance, data['preset']))
                try:
                    yield gen.Task(self.preset_load, instance, data['preset'], abort_catcher)
                except Exception as e:
                    logging.exception(e)

                addressing = pluginData['addressings'].get(":presets", None)
                if addressing is not None:
                    addressing['value'] = pluginData['mapPresets'].index(data['preset'])
                    if addressing['actuator_uri'] not in used_actuators:
                        used_actuators.append(addressing['actuator_uri'])

            for symbol, value in data['ports'].items():
                if symbol in pluginData['designations'] or pluginData['ports'].get(symbol, None) in (value, None):
                    continue

                self.msg_callback("param_set %s %s %f" % (instance, symbol, value))
                try:
                    yield gen.Task(self.param_set, "%s/%s" % (instance, symbol), value)
                except Exception as e:
                    logging.exception(e)

                addressing = pluginData['addressings'].get(symbol, None)
                if addressing is not None:
                    addressing['value'] = value
                    if addressing['actuator_uri'] not in used_actuators:
                        used_actuators.append(addressing['actuator_uri'])

            # if not bypassed (enabled), do it at the end
            if diffBypass and not data['bypassed']:
                self.msg_callback("param_set %s :bypass 0.0" % (instance,))
                try:
                    yield gen.Task(self.bypass, instance, False)
                except Exception as e:
                    logging.exception(e)

        if abort_catcher.get('abort', False):
            callback(False)
            return

        if is_hmi_snapshot or not from_hmi:
            skippedPort = (None, None)
        else:
            skippedPort = (PEDALBOARD_INSTANCE_ID, ":presets")
        self.addressings.load_current(used_actuators, skippedPort, True, abort_catcher)

        if not is_hmi_snapshot:
            # TODO: change to pedal_snapshot?
            self.msg_callback("pedal_preset %d" % idx)

        # callback must be last action
        callback(True)

    @gen.coroutine
    def page_load(self, idx, abort_catcher, callback):
        if not self.addressings.pages_cb:
            print("ERROR: hmi next page not supported")
            callback(False)
            return

        # If a pedalboard is loading (via MIDI program messsage), wait for it to finish
        while self.next_hmi_pedalboard is not None:
            yield gen.sleep(0.5)

        for uri, addressings in self.addressings.hmi_addressings.items():
            if abort_catcher.get('abort', False):
                print("WARNING: Abort triggered during page_load request, caller:", abort_catcher['caller'])
                callback(False)
                return

            hw_id = self.addressings.hmi_uri2hw_map[uri]
            addrs = addressings['addrs']

            # Nothing assigned to current actuator on any pages, nothing to do
            if len(addrs) == 0:
                continue

            page_to_load_assigned = self.addressings.is_page_assigned(addrs, idx)

            # Nothing assigned to current actuator on page to load
            if not page_to_load_assigned:
                continue

            # Else, send control_add with new data
            try:
                next_addressing_data = self.addressings.get_addressing_for_page(addrs, idx)
            except StopIteration:
                continue

            next_addressing_data['value'] = self.addr_task_get_port_value(next_addressing_data['instance_id'],
                                                                          next_addressing_data['port'])

            try:
                yield gen.Task(self.hmi.control_add, next_addressing_data, hw_id, uri)
            except Exception as e:
                logging.exception(e)

        self.addressings.current_page = idx % self.addressings.pages_nb

        # callback must be last action
        callback(True)

    # -----------------------------------------------------------------------------------------------------------------
    # Host stuff - connections

    def _fix_host_connection_port(self, port):
        """Map URL style port names to Jack port names."""

        data = port.split("/")
        # For example, "/graph/capture_2" becomes ['', 'graph',
        # 'capture_2']. Plugin paths can be longer, e.g.  ['', 'graph',
        # 'BBCstereo', 'inR']

        if len(data) == 3:
            # Handle special cases
            if data[2] == "serial_midi_in":
                return "ttymidi:MIDI_in"
            if data[2] == "serial_midi_out":
                return "ttymidi:MIDI_out"
            if data[2] == "midi_merger_out":
                return "mod-midi-merger:out"
            if data[2] == "midi_broadcaster_in":
                return "mod-midi-broadcaster:in"
            if data[2].startswith("playback_"):
                num = data[2].replace("playback_","",1)
                if num in ("1", "2"):
                    return self.jack_hwin_prefix + num

            if data[2].startswith(("audio_from_slave_",
                                   "audio_to_slave_",
                                   "midi_from_slave_",
                                   "midi_to_slave_",
                                   "USB_Audio_Capture_",
                                   "USB_Audio_Playback_")):
                return "%s:%s" % (self.jack_slave_prefix, data[2])

            if data[2].startswith("nooice_capture_"):
                num = data[2].replace("nooice_capture_","",1)
                return "nooice%s:nooice_capture_%s" % (num, num)

            # Handle the Control Voltage faker
            if data[2].startswith("cv_capture_"):
                num = data[2].replace("cv_capture_", "", 1)
                return "mod-fake-control-voltage:cv_capture_{0}".format(num)
            if data[2].startswith("cv_playback_"):
                num = data[2].replace("cv_playback_", "", 1)
                return "mod-fake-control-voltage:cv_playback_{0}".format(num)

            # Default guess
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
        try:
            pb = get_pedalboard_info(bundlepath)
        except:
            self.bank_id = 0
            try:
                pb = get_pedalboard_info(DEFAULT_PEDALBOARD)
            except:
                pb = {
                    'title': "",
                    'width': 0,
                    'height': 0,
                    'midi_legacy_mode': False,
                    'connections': [],
                    'plugins': [],
                    'timeInfo': {
                        'available': False,
                    },
                    'version': 0,
                }

        self.msg_callback("loading_start %i 0" % int(isDefault))
        self.msg_callback("size %d %d" % (pb['width'],pb['height']))

        midi_aggregated_mode = not pb.get('midi_legacy_mode', True)

        if self.midi_aggregated_mode != midi_aggregated_mode:
            self.send_notmodified("feature_enable aggregated-midi {}".format(int(midi_aggregated_mode)))
            self.set_midi_devices_change_mode(midi_aggregated_mode)

        if not self.midi_aggregated_mode:
            # MIDI Devices might change port names at anytime
            # To properly restore MIDI HW connections we need to map the "old" port names (from project)
            mappedOldMidiIns   = dict((p['symbol'], p['name']) for p in pb['hardware']['midi_ins'])
            mappedOldMidiOuts  = dict((p['symbol'], p['name']) for p in pb['hardware']['midi_outs'])
            mappedOldMidiOuts2 = dict((p['name'], p['symbol']) for p in pb['hardware']['midi_outs'])
            mappedNewMidiIns   = OrderedDict((get_jack_port_alias(p).split("-",5)[-1].replace("-"," ").replace(";","."),
                                            p.split(":",1)[-1]) for p in get_jack_hardware_ports(False, False))
            mappedNewMidiOuts  = OrderedDict((get_jack_port_alias(p).split("-",5)[-1].replace("-"," ").replace(";","."),
                                            p.split(":",1)[-1]) for p in get_jack_hardware_ports(False, True))

        else:
            mappedOldMidiIns  = {}
            mappedOldMidiOuts = {}
            mappedNewMidiIns  = {}
            mappedNewMidiOuts = {}

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
        if self.transport_sync != "none":
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
                self.set_transport_bpb(pb['timeInfo']['bpb'], False, True, False)

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
                self.set_transport_bpm(pb['timeInfo']['bpm'], False, True, False)

            if timeAvailable & kPedalboardTimeAvailableRolling:
                ccData = pb['timeInfo']['rollingCC']
                if ccData['channel'] >= 0 and ccData['channel'] < 16:
                    pluginData['midiCCs'][':rolling'] = (ccData['channel'], ccData['control'], 0.0, 1.0)
                    pluginData['addressings'][':rolling'] = self.addressings.add_midi(PEDALBOARD_INSTANCE_ID,
                                                                                      ':rolling',
                                                                                      ccData['channel'],
                                                                                      ccData['control'],
                                                                                      0.0, 1.0)
                self.set_transport_rolling(pb['timeInfo']['rolling'], False, True, False)

        self.send_notmodified("transport %i %f %f" % (self.transport_rolling,
                                                      self.transport_bpb,
                                                      self.transport_bpm))

        self.msg_callback("transport %i %f %f %s" % (self.transport_rolling,
                                                     self.transport_bpb,
                                                     self.transport_bpm,
                                                     self.transport_sync))

        self.load_pb_snapshots(pb['plugins'], bundlepath)
        self.load_pb_plugins(pb['plugins'], instances, rinstances)
        self.load_pb_connections(pb['connections'], mappedOldMidiIns, mappedOldMidiOuts,
                                                    mappedNewMidiIns, mappedNewMidiOuts)

        self.addressings.load(bundlepath, instances, skippedPortAddressings)
        self.addressings.registerMappings(self.msg_callback, rinstances)

        self.msg_callback("loading_end %d" % self.current_pedalboard_snapshot_id)

        if isDefault:
            self.pedalboard_empty    = True
            self.pedalboard_modified = False
            self.pedalboard_name     = ""
            self.pedalboard_path     = ""
            self.pedalboard_size     = [0,0]
            self.pedalboard_version  = 0
            self.midi_aggregated_mode = True
            #save_last_bank_and_pedalboard(0, "")
        else:
            self.pedalboard_empty    = False
            self.pedalboard_modified = False
            self.pedalboard_name     = pb['title']
            self.pedalboard_path     = bundlepath
            self.pedalboard_size     = [pb['width'],pb['height']]
            self.pedalboard_version  = pb['version']

            if bundlepath.startswith(LV2_PEDALBOARDS_DIR):
                save_last_bank_and_pedalboard(self.bank_id, bundlepath)
            else:
                save_last_bank_and_pedalboard(0, "")

            os.sync()

        return self.pedalboard_name

    def load_pb_snapshots(self, plugins, bundlepath):
        self.snapshot_clear()

        # NOTE: keep the filename "presets.json" for backwards compatibility.
        snapshots = safe_json_load(os.path.join(bundlepath, "presets.json"), list)

        if len(snapshots) == 0:
            return

        self.current_pedalboard_snapshot_id = 0
        self.pedalboard_snapshots = snapshots

        initial_snapshot = snapshots[0]['data']

        for p in plugins:
            pdata = initial_snapshot.get(p['instance'], None)

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
                "ranges"      : ranges,
                "badports"    : badports,
                "designations": (enabled_symbol, freewheel_symbol, bpb_symbol, bpm_symbol, speed_symbol),
                "outputs"     : dict((symbol, None) for symbol in allports['monitoredOutputs']),
                "preset"      : p['preset'],
                "mapPresets"  : [],
                "nextPreset"  : "",
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
            newPedalboard = False

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
            newPedalboard = True

        # save
        self.pedalboard_name     = title
        self.pedalboard_empty    = False
        self.pedalboard_modified = False
        self.save_state_to_ttl(bundlepath, title, titlesym)

        save_last_bank_and_pedalboard(0, bundlepath)
        os.sync()

        return bundlepath, newPedalboard

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
        # Write presets.json. NOTE: keep the filename for backwards
        # compatibility. TODO: Add to global settings.
        snapshots_filepath = os.path.join(bundlepath, "presets.json")

        if len(self.pedalboard_snapshots) > 1:
            for instance in self.plugins_removed:
                for snapshot in self.pedalboard_snapshots:
                    if snapshot is None:
                        continue
                    try:
                        snapshot['data'].pop(instance.replace("/graph/","",1))
                    except KeyError:
                        pass

            for instance_id in self.plugins_added:
                for snapshot in self.pedalboard_snapshots:
                    if snapshot is None:
                        continue
                    pluginData = self.plugins[instance_id]
                    instance   = pluginData['instance'].replace("/graph/","",1)
                    snapshot['data'][instance] = {
                        "bypassed": pluginData['bypassed'],
                        "ports"   : pluginData['ports'].copy(),
                        "preset"  : pluginData['preset'],
                    }

            snapshots = [p for p in self.pedalboard_snapshots if p is not None]
            with TextFileFlusher(snapshots_filepath) as fh:
                json.dump(snapshots, fh)

        elif os.path.exists(snapshots_filepath):
            os.remove(snapshots_filepath)

        self.plugins_added   = []
        self.plugins_removed = []

    def save_state_mainfile(self, bundlepath, title, titlesym):
        self.pedalboard_version += 1

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
    lv2:name "DIN MIDI In" ;
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
    lv2:name "DIN MIDI In" ;
    lv2:portProperty lv2:connectionOptional ;
    lv2:symbol "serial_midi_out" ;
    <http://lv2plug.in/ns/ext/resize-port#minimumSize> 4096 ;
    a atom:AtomPort ,
        lv2:OutputPort .
""" % index

        # MIDI Aggregated Mode
        index += 1
        ports += """
<midi_legacy_mode>
    ingen:value %i ;
    lv2:index %i ;
    a atom:AtomPort ,
        lv2:InputPort .
""" % (int(not self.midi_aggregated_mode), index)

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
    pedal:unitName "%s" ;
    pedal:unitModel "%s" ;
    pedal:width %i ;
    pedal:height %i ;
    pedal:addressings <addressings.json> ;
    pedal:screenshot <screenshot.png> ;
    pedal:thumbnail <thumbnail.png> ;
    pedal:version %i ;
    ingen:polyphony 1 ;
""" % (arcs, blocks, ports,
       title.replace('"','\\"'),
       self.descriptor.get('name', 'Unknown').replace('"','\\"'),
       self.descriptor.get('model', 'Unknown').replace('"','\\"'),
       self.pedalboard_size[0], self.pedalboard_size[1], self.pedalboard_version)

        # Arcs (connections)
        if len(self.connections) > 0:
            args = (" ,\n              _:b".join(tuple(str(i+1) for i in range(len(self.connections)))))
            pbdata += "    ingen:arc _:b%s ;\n" % args

        # Blocks (plugins)
        if len(self.plugins) > 0:
            args = ("> ,\n                <".join(tuple(p['instance'].replace("/graph/","",1) for i, p in self.plugins.items() if i != PEDALBOARD_INSTANCE_ID)))
            pbdata += "    ingen:block <%s> ;\n" % args

        # Ports
        portsyms = [":bpb",":bpm",":rolling","midi_legacy_mode","control_in","control_out"]
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

    # Set new param value after bpm change
    def set_param_from_bpm(self, addr, bpm, callback):
        if not addr.get('tempo', False):
            callback(False)
            return

        # compute new port value based on new bpm
        port_value_sec = get_port_value(bpm, addr['dividers'])
        port_value = convert_seconds_to_port_value_equivalent(port_value_sec, addr['unit'])

        instance_id = addr['instance_id']
        portsymbol   = addr['port']
        instance = self.mapper.get_instance(instance_id)
        pluginData  = self.plugins.get(instance_id, None)
        if pluginData is None:
            callback(False)
            return

        self.host_and_web_parameter_set(pluginData, instance, instance_id, port_value, portsymbol, callback)

    def set_sync_mode(self, mode, sendHMI, sendWeb, setProfile, callback):
        if setProfile:
            if not self.profile.set_sync_mode(mode):
                callback(False)
                return

        def host_callback(ok):
            if not ok:
                callback(False)
                return

            if sendWeb:
                self.msg_callback("transport %i %f %f %s" % (self.transport_rolling,
                                                             self.transport_bpb,
                                                             self.transport_bpm,
                                                             self.transport_sync))
            if sendHMI and self.hmi.initialized:
                self.hmi.set_profile_value(Menu.SYS_CLK_SOURCE_ID, self.profile.get_transport_source(), callback)
            else:
                callback(True)

        def unaddress_bpm_callback(ok):
            # Then set new sync mode and send to host
            if not ok:
                callback(False)
                return
            elif mode == Profile.TRANSPORT_SOURCE_INTERNAL:
                self.transport_sync = "none"
                self.send_notmodified("transport_sync none", host_callback, datatype='boolean')
            elif mode == Profile.TRANSPORT_SOURCE_MIDI_SLAVE:
                self.transport_sync = "midi_clock_slave"
                self.send_notmodified("transport_sync midi", host_callback, datatype='boolean')
            elif mode == Profile.TRANSPORT_SOURCE_ABLETON_LINK:
                self.transport_sync = "link"
                self.send_notmodified("transport_sync link", host_callback, datatype='boolean')
            else:
                callback(False)
                return

        # First, unadress BPM port if switching to Link or MIDI sync mode
        if mode in (Profile.TRANSPORT_SOURCE_MIDI_SLAVE, Profile.TRANSPORT_SOURCE_ABLETON_LINK):
            self.address("/pedalboard", ":bpm", kNullAddressURI, "---", 0.0, 0.0, 0.0, 0, False, None, None, unaddress_bpm_callback)
        else:
            unaddress_bpm_callback(True)

    @gen.coroutine
    def set_link_enabled(self):
        if self.plugins[PEDALBOARD_INSTANCE_ID]['addressings'].get(":bpm", None) is not None:
            print("ERROR: link enabled while BPM is still addressed")

        self.send_notmodified("transport_sync link")

        self.transport_sync = "link"
        self.profile.set_sync_mode(Profile.TRANSPORT_SOURCE_ABLETON_LINK)

        if self.hmi.initialized:
            try:
                yield gen.Task(self.hmi.set_profile_value, Menu.SYS_CLK_SOURCE_ID, Profile.TRANSPORT_SOURCE_ABLETON_LINK)
            except Exception as e:
                logging.exception(e)

    @gen.coroutine
    def set_midi_clock_slave_enabled(self):
        if self.plugins[PEDALBOARD_INSTANCE_ID]['addressings'].get(":bpm", None) is not None:
            print("ERROR: MIDI Clock Slave enabled while BPM is still addressed")

        self.send_notmodified("transport_sync midi")

        self.transport_sync = "midi_clock_slave"
        self.profile.set_sync_mode(Profile.TRANSPORT_SOURCE_MIDI_SLAVE)

        if self.hmi.initialized:
            try:
                yield gen.Task(self.hmi.set_profile_value, Menu.SYS_CLK_SOURCE_ID, Profile.TRANSPORT_SOURCE_MIDI_SLAVE)
            except Exception as e:
                logging.exception(e)

    @gen.coroutine
    def set_internal_transport_source(self):
        self.send_notmodified("feature_enable link 0")
        self.send_notmodified("feature_enable midi_clock_slave 0")

        self.transport_sync = "none"
        self.profile.set_sync_mode(Profile.TRANSPORT_SOURCE_INTERNAL)

        if self.hmi.initialized:
            try:
                yield gen.Task(self.hmi.set_profile_value, Menu.SYS_CLK_SOURCE_ID, Profile.TRANSPORT_SOURCE_INTERNAL)
            except Exception as e:
                logging.exception(e)

    @gen.coroutine
    def set_transport_bpb(self, bpb, sendHost, sendHMI, sendWeb, callback=None, datatype='int'):
        self.transport_bpb = bpb
        self.profile.set_tempo_bpb(bpb)

        if sendHost:
            self.send_modified("transport %i %f %f" % (self.transport_rolling,
                                                       self.transport_bpb,
                                                       self.transport_bpm), callback, datatype)

        for pluginData in self.plugins.values():
            bpb_symbol = pluginData['designations'][self.DESIGNATIONS_INDEX_BPB]

            if bpb_symbol is not None:
                pluginData['ports'][bpb_symbol] = bpb
                if sendHost:
                    self.msg_callback("param_set %s %s %f" % (pluginData['instance'], bpb_symbol, bpb))

        if sendHMI and self.hmi.initialized:
            try:
                yield gen.Task(self.hmi.set_profile_value, Menu.TEMPO_BPB_ID, bpb)
            except Exception as e:
                logging.exception(e)

        if sendWeb:
            self.msg_callback("transport %i %f %f %s" % (self.transport_rolling,
                                                         self.transport_bpb,
                                                         self.transport_bpm,
                                                         self.transport_sync))

    @gen.coroutine
    def set_transport_bpm(self, bpm, sendHost, sendHMI, sendWeb, callback=None, datatype='int'):
        self.transport_bpm = bpm
        self.profile.set_tempo_bpm(bpm)

        for actuator_uri in self.addressings.virtual_addressings:
            addrs = self.addressings.virtual_addressings[actuator_uri]
            for addr in addrs:
                try:
                    yield gen.Task(self.set_param_from_bpm, addr, bpm)
                except Exception as e:
                    logging.exception(e)

        for actuator_uri in self.addressings.hmi_addressings:
            addrs = self.addressings.hmi_addressings[actuator_uri]['addrs']
            for addr in addrs:
                try:
                    yield gen.Task(self.set_param_from_bpm, addr, bpm)
                except Exception as e:
                    logging.exception(e)

        if sendHost:
            self.send_modified("transport %i %f %f" % (self.transport_rolling,
                                                       self.transport_bpb,
                                                       self.transport_bpm), callback, datatype)

        for pluginData in self.plugins.values():
            bpm_symbol = pluginData['designations'][self.DESIGNATIONS_INDEX_BPM]

            if bpm_symbol is not None:
                pluginData['ports'][bpm_symbol] = bpm
                if sendHost:
                    self.msg_callback("param_set %s %s %f" % (pluginData['instance'], bpm_symbol, bpm))

        if sendHMI and self.hmi.initialized:
            try:
                yield gen.Task(self.hmi.set_profile_value, Menu.TEMPO_BPM_ID, bpm)
            except Exception as e:
                logging.exception(e)

        if sendWeb:
            self.msg_callback("transport %i %f %f %s" % (self.transport_rolling,
                                                         self.transport_bpb,
                                                         self.transport_bpm,
                                                         self.transport_sync))

    @gen.coroutine
    def set_transport_rolling(self, rolling, sendHost, sendHMI, sendWeb, callback=None, datatype='int'):
        self.transport_rolling = rolling

        if sendHost:
            self.send_notmodified("transport %i %f %f" % (self.transport_rolling,
                                                          self.transport_bpb,
                                                          self.transport_bpm), callback, datatype)

        speed = 1.0 if rolling else 0.0

        for pluginData in self.plugins.values():
            speed_symbol = pluginData['designations'][self.DESIGNATIONS_INDEX_SPEED]

            if speed_symbol is not None:
                pluginData['ports'][speed_symbol] = speed
                if sendHost:
                    self.msg_callback("param_set %s %s %f" % (pluginData['instance'], speed_symbol, speed))

        if sendHMI and self.hmi.initialized:
            try:
                yield gen.Task(self.hmi.set_profile_value, Menu.PLAY_STATUS_ID, int(rolling))
            except Exception as e:
                logging.exception(e)

        if sendWeb:
            self.msg_callback("transport %i %f %f %s" % (self.transport_rolling,
                                                         self.transport_bpb,
                                                         self.transport_bpm,
                                                         self.transport_sync))

    #def set_midi_program_change_pedalboard_bank_channel(self, channel):
        #if self.profile.set_midi_prgch_channel("bank", channel):
            #self.send_notmodified("set_midi_program_change_pedalboard_bank_channel 1 %d" % channel)

    #def set_midi_program_change_pedalboard_snapshot_channel(self, channel):
        #if self.profile.set_midi_prgch_channel("snapshot", channel):
            #self.send_notmodified("set_midi_program_change_pedalboard_snapshot_channel 1 %d" % channel)

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

    def get_system_stats_message(self):
        memload = self.get_free_memory_value()
        cpufreq = read_file_contents(self.cpufreqfile, "0")
        cputemp = read_file_contents(self.thermalfile, "0")
        return "sys_stats %s %s %s" % (memload, cpufreq, cputemp)

    def memtimer_callback(self):
        self.msg_callback(self.get_system_stats_message())

    # -----------------------------------------------------------------------------------------------------------------
    # Addressing (public stuff)

    @gen.coroutine
    def address(self, instance, portsymbol, actuator_uri, label, minimum, maximum, value, steps, tempo, dividers, page, callback, not_param_set=False, send_hmi=True):
        instance_id = self.mapper.get_id(instance)
        pluginData  = self.plugins.get(instance_id, None)

        if pluginData is None:
            print("ERROR: Trying to address non-existing plugin instance %i: '%s'" % (instance_id, instance))
            callback(False)
            return

        # MIDI learn is not saved until a MIDI controller is moved.
        # So we need special casing for unlearn.
        if actuator_uri == kMidiUnlearnURI:
            self.send_modified("midi_unmap %d %s" % (instance_id, portsymbol), callback, datatype='boolean')
            return

        old_addressing = pluginData['addressings'].pop(portsymbol, None)

        if old_addressing is not None:
            # Need to remove old addressings for that port first
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

                        self.send_modified("midi_map %d %s %i %i %f %f" % (instance_id,
                                                                           portsymbol,
                                                                           channel,
                                                                           controller,
                                                                           minimum,
                                                                           maximum), callback, datatype='boolean')
                        return

            self.addressings.remove(old_addressing)
            self.pedalboard_modified = True

            try:
                if old_actuator_type == Addressings.ADDRESSING_TYPE_HMI:
                    old_hw_ids = []
                    old_group_actuators = self.addressings.get_group_actuators(old_actuator_uri)
                    # Unadress all actuators in group
                    if old_group_actuators:
                        old_hw_ids = [self.addressings.hmi_uri2hw_map[actuator_uri] for actuator_uri in old_group_actuators]
                    else:
                        old_hw_ids = [self.addressings.hmi_uri2hw_map[old_actuator_uri]]
                    yield gen.Task(self.addr_task_unaddressing, old_actuator_type,
                                                                old_addressing['instance_id'],
                                                                old_addressing['port'],
                                                                send_hmi=send_hmi,
                                                                hw_ids=old_hw_ids)
                    yield gen.Task(self.addressings.hmi_load_current, old_actuator_uri, send_hmi=send_hmi)
                else:
                    yield gen.Task(self.addr_task_unaddressing, old_actuator_type,
                                                                old_addressing['instance_id'],
                                                                old_addressing['port'],
                                                                send_hmi=send_hmi)
            except Exception as e:
                logging.exception(e)

        if not actuator_uri or actuator_uri == kNullAddressURI:
            callback(True)
            return

        if self.addressings.is_hmi_actuator(actuator_uri) and not self.hmi.initialized:
            print("WARNING: Cannot address to HMI at this point")
            callback(False)
            return

        # MIDI learn is not an actual addressing
        if actuator_uri == kMidiLearnURI:
            self.send_notmodified("midi_learn %d %s %f %f" % (instance_id,
                                                              portsymbol,
                                                              minimum,
                                                              maximum), callback, datatype='boolean')
            return

        needsValueChange = False
        has_strict_bounds = True

        # Retrieve port infos
        if instance_id != PEDALBOARD_INSTANCE_ID:
            pluginInfo = get_plugin_info(pluginData['uri'])
            if pluginInfo:
                controlPorts = pluginInfo['ports']['control']['input']
                ports = [p for p in controlPorts if p['symbol'] == portsymbol]
                if ports:
                    port = ports[0]
                    has_strict_bounds = "hasStrictBounds" in port['properties']
                    # Set min and max to min and max value among dividers
                    if tempo:
                        divider_options = get_divider_options(port, 20.0, 280.0) # XXX min and max bpm hardcoded
                        options_list = [opt['value'] for opt in divider_options]
                        minimum = min(options_list)
                        maximum = max(options_list)

        if not tempo and has_strict_bounds:
            if value < minimum:
                value = minimum
                needsValueChange = True
            elif value > maximum:
                value = maximum
                needsValueChange = True

        if tempo and not not_param_set:
            needsValueChange = True

        group_actuators = self.addressings.get_group_actuators(actuator_uri)
        if group_actuators:
            for i in range(len(group_actuators)):
                group_actuator_uri = group_actuators[i]
                group_addressing = self.addressings.add(instance_id, pluginData['uri'], portsymbol, group_actuator_uri,
                                              label, minimum, maximum, steps, value, tempo, dividers, page, actuator_uri)
                                              # group=[a for a in group_actuators if a != group_actuator_uri])
                if group_addressing is None:
                    callback(False)
                    return

                if needsValueChange:
                    hw_id = self.addressings.hmi_uri2hw_map[group_actuator_uri]
                    try:
                        yield gen.Task(self.hmi_parameter_set, hw_id, value)
                    except Exception as e:
                        logging.exception(e)
                try:
                    yield gen.Task(self.addressings.load_addr, group_actuator_uri, group_addressing, send_hmi=send_hmi)
                except Exception as e:
                    logging.exception(e)
            addressing = group_addressing.copy()
            addressing['actuator_uri'] = actuator_uri
        else:
            addressing = self.addressings.add(instance_id, pluginData['uri'], portsymbol, actuator_uri,
                                              label, minimum, maximum, steps, value, tempo, dividers, page)

            if addressing is None:
                callback(False)
                return
            if needsValueChange:
                if actuator_uri != kBpmURI:
                    hw_id = self.addressings.hmi_uri2hw_map[actuator_uri]
                    try:
                        yield gen.Task(self.hmi_parameter_set, hw_id, value)
                    except Exception as e:
                        logging.exception(e)
                elif tempo:
                    try:
                        yield gen.Task(self.host_and_web_parameter_set, pluginData, instance, instance_id, value, portsymbol)
                    except Exception as e:
                        logging.exception(e)

        pluginData['addressings'][portsymbol] = addressing

        self.pedalboard_modified = True
        if not group_actuators: # group actuator addressing has already been loaded previously
            self.addressings.load_addr(actuator_uri, addressing, callback, send_hmi=send_hmi)
        else:
            callback(True)

    def host_and_web_parameter_set(self, pluginData, instance, instance_id, port_value, portsymbol, callback):
        pluginData['ports'][portsymbol] = port_value
        self.send_modified("param_set %d %s %f" % (instance_id, portsymbol, port_value), callback, datatype='boolean')
        self.msg_callback("param_set %s %s %f" % (instance, portsymbol, port_value))

    # -----------------------------------------------------------------------------------------------------------------
    # HMI callbacks, called by HMI via serial

    def hmi_hardware_connected(self, hardware_type, hardware_id, callback):
        logging.debug("hmi hardware connected")
        callback(True)

    def hmi_hardware_disconnected(self, hardware_type, hardware_id, callback):
        logging.debug("hmi hardware disconnected")
        callback(True)

    def hmi_list_banks(self, callback):
        logging.debug("hmi list banks")

        if len(self.allpedalboards) == 0:
            callback(True, "")
            return

        banks = '"All Pedalboards" 0'

        if len(self.banks) > 0:
            banks += " "
            banks += " ".join('"%s" %d' % (bank['title'], i+1) for i, bank in enumerate(self.banks))

        callback(True, banks)

    def hmi_list_bank_pedalboards(self, bank_id, callback):
        logging.debug("hmi list bank pedalboards")

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
        logging.debug("hmi load bank pedalboard")

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
        else:
            bank        = self.banks[bank_id-1]
            pedalboards = bank['pedalboards']

        if pedalboard_id < 0 or pedalboard_id >= len(pedalboards):
            print("ERROR: Trying to load pedalboard using out of bounds pedalboard id %i" % (pedalboard_id))
            callback(False)
            return

        self.next_hmi_pedalboard = (bank_id, pedalboard_id)
        callback(True)

        bundlepath = pedalboards[pedalboard_id]['bundle']

        def load_different_callback(ok):
            if self.next_hmi_pedalboard is None:
                print("ERROR: Delayed loading is in corrupted state")
                return
            if ok:
                print("NOTE: Delayed loading of %i:%i has started" % self.next_hmi_pedalboard)
            else:
                print("ERROR: Delayed loading of %i:%i failed!" % self.next_hmi_pedalboard)

        def hmi_loaded_callback(_):
            print("NOTE: Loading of %i:%i finished" % (bank_id, pedalboard_id))

            # Check if there's a pending pedalboard to be loaded
            next_pedalboard = self.next_hmi_pedalboard
            self.next_hmi_pedalboard = None

            if next_pedalboard != (bank_id, pedalboard_id):
                self.hmi_load_bank_pedalboard(next_pedalboard[0], next_pedalboard[1], load_different_callback)
            else:
                self.processing_pending_flag = False
                self.send_notmodified("feature_enable processing 1")

        def host_loaded_callback(_):
            # Update the title in HMI
            self.hmi.send("s_pbn {0}".format(self.pedalboard_name), hmi_loaded_callback)

        def load_callback(_):
            self.bank_id = bank_id
            self.load(bundlepath)

            # Dummy host call, just to receive callback when all other host messages finish
            self.send_notmodified("cpu_load", host_loaded_callback, datatype='float_structure')

        def footswitch_callback(_):
            self.setNavigateWithFootswitches(self.isBankFootswitchNavigationOn(), load_callback)

        def hmi_clear_callback(_):
            self.hmi.clear(footswitch_callback)

        if not self.processing_pending_flag:
            self.processing_pending_flag = True
            self.send_notmodified("feature_enable processing 0")

        self.reset(hmi_clear_callback)

    def get_addressed_port_info(self, hw_id):
        try:
            actuator_uri = self.addressings.hmi_hw2uri_map[hw_id]
            addressings = self.addressings.hmi_addressings[actuator_uri]
        except KeyError:
            return (None, None)

        addressings_addrs = addressings['addrs']

        if self.addressings.pages_cb: # device supports pages
            try:
                addressing_data = self.addressings.get_addressing_for_page(addressings_addrs,
                                                                           self.addressings.current_page)
            except StopIteration:
                return (None, None)

        else:
            addressing_data = addressings_addrs[addressings['idx']]

        instance_id = addressing_data['instance_id']
        portsymbol = addressing_data['port']

        return instance_id, portsymbol

    def hmi_parameter_get(self, hw_id, callback):
        logging.debug("hmi parameter get")
        instance_id, portsymbol = self.get_addressed_port_info(hw_id)
        callback(self.addr_task_get_port_value(instance_id, portsymbol))

    # def hmi_parameter_set(self, instance_id, portsymbol, value, callback):
    def hmi_parameter_set(self, hw_id, value, callback):
        logging.debug("hmi parameter set")
        abort_catcher = self.abort_previous_loading_progress("hmi_parameter_set")

        instance_id, portsymbol = self.get_addressed_port_info(hw_id)
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
                try:
                    self.snapshot_load(value, True, abort_catcher, callback)
                except Exception as e:
                    callback(False)
                    logging.exception(e)
            else:
                port_addressing = pluginData['addressings'].get(portsymbol, None)
                try:
                    if port_addressing:
                        group_actuators = self.addressings.get_group_actuators(port_addressing['actuator_uri'])
                        if group_actuators:
                            def group_callback(ok):
                                if not ok:
                                    callback(False)
                                    return
                                self.preset_load(instance, pluginData['mapPresets'][value], abort_catcher, callback)
                            # Update value on the HMI for the other actuator in the group
                            self.control_set_other_group_actuator(group_actuators, hw_id, value, group_callback)
                        else:
                            self.preset_load(instance, pluginData['mapPresets'][value], abort_catcher, callback)

                except Exception as e:
                    callback(False)
                    logging.exception(e)

        elif instance_id == PEDALBOARD_INSTANCE_ID:
            # NOTE do not use try/except to send callback here, since the callback is not the last action
            if portsymbol == ":bpb":
                self.set_transport_bpb(value, True, False, True, callback)
            elif portsymbol == ":bpm":
                self.set_transport_bpm(value, True, False, True, callback)
            elif portsymbol == ":rolling":
                rolling = bool(value > 0.5)
                self.set_transport_rolling(rolling, True, False, True, callback)
            else:
                print("ERROR: Trying to set value for the wrong pedalboard port:", portsymbol)
                callback(False)
                return

        else:
            oldvalue = pluginData['ports'].get(portsymbol, None)
            if oldvalue is None:
                print("WARNING: hmi_parameter_set requested for non-existing port", portsymbol)
                callback(False)
                return

            port_addressing = pluginData['addressings'].get(portsymbol, None)
            if port_addressing:

                group_actuators = self.addressings.get_group_actuators(port_addressing['actuator_uri'])
                if group_actuators:
                    def group_callback(ok):
                        if not ok:
                            callback(False)
                            return
                        pluginData['ports'][portsymbol] = value
                        self.send_modified("param_set %d %s %f" % (instance_id, portsymbol, value), callback, datatype='boolean')
                        self.msg_callback("param_set %s %s %f" % (instance, portsymbol, value))
                    self.control_set_other_group_actuator(group_actuators, hw_id, value, group_callback)
                    return

                if port_addressing.get('tempo', None):
                    # compute new port value based on received divider value
                    pluginInfo = get_plugin_info(pluginData['uri'])

                    if not pluginInfo:
                        callback(False)
                        return

                    controlPorts = pluginInfo['ports']['control']['input']
                    ports        = [p for p in controlPorts if p['symbol'] == portsymbol]

                    if not ports:
                        callback(False)
                        return
                    port = ports[0]
                    port_value_sec = get_port_value(self.transport_bpm, value)
                    port_value = convert_seconds_to_port_value_equivalent(port_value_sec, port['units']['symbol'])

                    def address_callback(ok):
                        if not ok:
                            callback(False)
                            return
                        pluginData['ports'][portsymbol] = port_value
                        self.send_modified("param_set %d %s %f" % (instance_id, portsymbol, port_value), callback, datatype='boolean')
                        self.msg_callback("param_set %s %s %f" % (instance, portsymbol, port_value))

                    actuator_uri = port_addressing['actuator_uri']
                    label = port_addressing['label']
                    minimum = port_addressing['minimum']
                    maximum = port_addressing['maximum']
                    steps = port_addressing['steps']
                    tempo = port_addressing['tempo']
                    dividers = value
                    page = port_addressing['page']
                    self.address(instance, portsymbol, actuator_uri, label, minimum, maximum, port_value, steps, tempo, dividers, page, address_callback, not_param_set=True, send_hmi=False)
                    return

            pluginData['ports'][portsymbol] = value
            self.send_modified("param_set %d %s %f" % (instance_id, portsymbol, value), callback, datatype='boolean')
            self.msg_callback("param_set %s %s %f" % (instance, portsymbol, value))

    def control_set_other_group_actuator(self, group_actuators, hw_id, value, callback):
        for group_actuator_uri in group_actuators:
            group_hw_id = self.addressings.hmi_uri2hw_map[group_actuator_uri]
            if group_hw_id != hw_id:
                self.hmi.control_set(group_hw_id, float(value), callback)
                return
        callback(True)

    def hmi_parameter_addressing_next(self, hw_id, callback):
        logging.debug("hmi parameter addressing next")
        self.addressings.hmi_load_next_hw(hw_id, callback)

    def hmi_save_current_pedalboard(self, callback):
        logging.debug("hmi save current pedalboard")
        titlesym = symbolify(self.pedalboard_name)[:16]
        self.save_state_mainfile(self.pedalboard_path, self.pedalboard_name, titlesym)
        os.sync()
        callback(True)

    def hmi_reset_current_pedalboard(self, callback):
        logging.debug("hmi reset current pedalboard")
        try:
            yield gen.Task(self.hmi_reset_current_pedalboard_real)
        except Exception as e:
            callback(False)
            logging.exception(e)

    @gen.coroutine
    def hmi_reset_current_pedalboard_real(self, callback):
        abort_catcher = self.abort_previous_loading_progress("hmi_reset_current_pedalboard")
        pb_values = get_pedalboard_plugin_values(self.pedalboard_path)

        used_actuators = []

        for p in pb_values:
            if abort_catcher.get('abort', False):
                print("WARNING: Abort triggered during reset_current_pedalboard request, caller:", abort_catcher['caller'])
                callback(False)
                return

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
                #self.msg_callback("param_set %s :bypass 1.0" % (instance,))
                try:
                    yield gen.Task(self.bypass, instance, True)
                except Exception as e:
                    logging.exception(e)

            if p['preset'] and pluginData['preset'] != p['preset']:
                pluginData['preset'] = p['preset']
                #self.msg_callback("preset %s %s" % (instance, p['preset']))
                try:
                    yield gen.Task(self.send_notmodified, "preset_load %d %s" % (instance_id, p['preset']))
                except Exception as e:
                    logging.exception(e)

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
                #self.msg_callback("param_set %s %s %f" % (instance, symbol, value))
                try:
                    yield gen.Task(self.send_notmodified, "param_set %d %s %f" % (instance_id, symbol, value))
                except Exception as e:
                    logging.exception(e)

                addressing = pluginData['addressings'].get(symbol, None)
                if addressing is not None:
                    addressing['value'] = value
                    if addressing['actuator_uri'] not in used_actuators:
                        used_actuators.append(addressing['actuator_uri'])

            # if not bypassed (enabled), do it at the end
            if diffBypass and not bypassed:
                #self.msg_callback("param_set %s :bypass 0.0" % (instance,))
                try:
                    yield gen.Task(self.bypass, instance, False)
                except Exception as e:
                    logging.exception(e)

        self.pedalboard_modified = False
        self.addressings.load_current(used_actuators, (None, None), False, abort_catcher)
        callback(True)

    def hmi_tuner(self, status, callback):
        if status == "on":
            self.hmi_tuner_on(callback)
        else:
            self.hmi_tuner_off(callback)

    def hmi_tuner_on(self, callback):
        logging.debug("hmi tuner on")

        def operation_failed(ok):
            callback(False)

        def monitor_added(ok):
            if not ok or not connect_jack_ports("system:capture_%d" % self.current_tuner_port,
                                                "effect_%d:%s" % (TUNER_INSTANCE_ID, TUNER_INPUT_PORT)):
                self.send_notmodified("remove %d" % TUNER_INSTANCE_ID, operation_failed)
                return

            if self.current_tuner_mute:
                self.mute()

            callback(True)

        def tuner_added(resp):
            if resp not in (0, -2, TUNER_INSTANCE_ID): # -2 means already loaded
                callback(False)
                return
            self.send_notmodified("monitor_output %d %s" % (TUNER_INSTANCE_ID, TUNER_MONITOR_PORT), monitor_added)

        self.send_notmodified("add %s %d" % (TUNER_URI, TUNER_INSTANCE_ID), tuner_added)

    def hmi_tuner_off(self, callback):
        logging.debug("hmi tuner off")

        def tuner_removed(_):
            if self.current_tuner_mute:
                self.unmute()
            callback(True)

        self.send_notmodified("remove %d" % TUNER_INSTANCE_ID, tuner_removed)

    def hmi_tuner_input(self, input_port, callback):
        logging.debug("hmi tuner input")

        if input_port not in (1, 2):
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
        try:
            yield gen.Task(self.hmi.tuner, freq, note, cents)
        except Exception as e:
            logging.exception(e)

    @gen.coroutine
    def hmi_footswitch_navigation(self, value, callback):
        enabled = bool(value)
        self.prefs.setAndSave("bank-footswitch-navigation", enabled)
        callback(True)

        try:
            yield gen.Task(self.setNavigateWithFootswitches, enabled)
        except Exception as e:
            logging.exception(e)

        if enabled:
            return

        try:
            yield gen.Task(self.addressings.hmi_load_current, "/hmi/footswitch1")
        except Exception as e:
            logging.exception(e)

        try:
            yield gen.Task(self.addressings.hmi_load_current, "/hmi/footswitch2")
        except Exception as e:
            logging.exception(e)

    def hmi_get_truebypass_value(self, value, callback):
        """Query the True Bypass setting of the given channel."""
        logging.debug("hmi true bypass get (%i)", value)

        bypassed = get_truebypass_value(value == QUICK_BYPASS_MODE_2)
        callback(True, int(bypassed))

    def hmi_set_truebypass_value(self, value, bypassed, callback):
        """Change the True Bypass setting of the given channel."""
        logging.debug("hmi true bypass set to (%i, %i)", value, bypassed)

        if value == QUICK_BYPASS_MODE_1:
            supported = True
            set_truebypass_value(False, bypassed)

        elif value == QUICK_BYPASS_MODE_2:
            supported = True
            set_truebypass_value(True, bypassed)

        elif value == QUICK_BYPASS_MODE_BOTH:
            supported = True
            set_truebypass_value(False, bypassed)
            set_truebypass_value(True, bypassed)

        else:
            supported = False

        callback(supported)

    def hmi_get_quick_bypass_mode(self, callback):
        """Query the Quick Bypass Mode setting."""
        logging.debug("hmi quick bypass mode get")

        result = self.prefs.get("quick-bypass-mode", QUICK_BYPASS_MODE_BOTH, int, QUICK_BYPASS_MODE_VALUES)
        callback(True, result)

    def hmi_set_quick_bypass_mode(self, mode, callback):
        """Change the Quick Bypass Mode setting to `mode`."""
        logging.debug("hmi quick bypass mode set to `%i`", mode)

        if mode in QUICK_BYPASS_MODE_VALUES:
            self.prefs.setAndSave("quick-bypass-mode", mode)
            callback(True)
        else:
            callback(False)

    def hmi_get_tempo_bpm(self, callback):
        """Get the Jack BPM."""
        bpm = get_jack_data(True)['bpm']
        logging.debug("hmi get tempo bpm: %.1f", bpm)
        callback(True, bpm)

    def hmi_set_tempo_bpm(self, bpm, callback):
        """Set the Jack BPM."""
        logging.debug("hmi tempo bpm set to %f", float(bpm))
        self.set_transport_bpm(bpm, True, False, True, callback)

    def hmi_get_tempo_bpb(self, callback):
        """Get the Jack Beats Per Bar."""
        logging.debug("hmi tempo bpb get")
        bpb = int(get_jack_data(True)['bpb'])
        callback(True, bpb)

    def hmi_set_tempo_bpb(self, bpb, callback):
        """Set the Jack Beats Per Bar."""
        logging.debug("hmi tempo bpb set to %f", float(bpb))
        self.set_transport_bpb(bpb, True, False, True, callback)

    def hmi_get_snapshot_prgch(self, callback):
        """Query the MIDI channel for selecting a snapshot via Program Change."""
        logging.debug("hmi get snapshot channel")

        # NOTE: Assume this value is always the same as in mod-host
        result = self.profile.get_midi_prgch_channel("snapshot")
        callback(True, result)

    @gen.coroutine
    def hmi_set_snapshot_prgch(self, channel, callback):
        """Set the MIDI channel for selecting a snapshot via Program Change."""
        logging.debug("hmi set snapshot channel %i", channel)

        midi_pb_prgch, midi_ss_prgch = self.profile.get_midi_prgch_channels()

        if midi_ss_prgch == channel:
            callback(True)
            return

        if not self.profile.set_midi_prgch_channel("snapshot", channel):
            callback(False)
            return

        # NOTE: The range in mod-host is [0, 15]

        # if nothing is using old snapshot channel, disable monitoring
        if midi_pb_prgch != channel and midi_ss_prgch >= 1 and midi_ss_prgch <= 16:
            yield gen.Task(self.send_notmodified, "monitor_midi_program %d 1" % (midi_ss_prgch-1))

        # enable monitoring for this channel
        if channel >= 1 and channel <= 16:
            self.send_notmodified("monitor_midi_program %d 1" % (channel-1), callback)
        else:
            callback(True)

    def hmi_get_pedalboard_prgch(self, callback):
        """Query the MIDI channel for selecting a pedalboard in a bank via Program Change."""
        logging.debug("hmi get pedalboard channel")

        result = self.profile.get_midi_prgch_channel("pedalboard")
        callback(True, result)

    @gen.coroutine
    def hmi_set_pedalboard_prgch(self, channel, callback):
        """Set the MIDI channel for selecting a pedalboard in a bank via Program Change."""
        logging.debug("hmi set pedalboard channel %i", channel)

        midi_pb_prgch, midi_ss_prgch = self.profile.get_midi_prgch_channels()

        if midi_pb_prgch == channel:
            callback(True)
            return

        if not self.profile.set_midi_prgch_channel("pedalboard", channel):
            callback(False)
            return

        # NOTE: The range in mod-host is [0, 15]

        # if nothing is using old pedalboard channel, disable monitoring
        if midi_ss_prgch != channel and midi_pb_prgch >= 1 and midi_pb_prgch <= 16:
            yield gen.Task(self.send_notmodified, "monitor_midi_program %d 1" % (midi_pb_prgch-1))

        # enable monitoring for this channel
        if channel >= 1 and channel <= 16:
            self.send_notmodified("monitor_midi_program %d 1" % (channel-1), callback)
        else:
            callback(True)

    def hmi_get_clk_src(self, callback):
        """Query the tempo and transport sync mode."""
        logging.debug("hmi get clock source")

        # NOTE: We assume the state in mod-host will only change if
        # `hmi_set_clk_src()` is called!
        result = self.profile.get_transport_source()
        callback(True, result)

    def hmi_set_clk_src(self, mode, callback):
        """Set the tempo and transport sync mode."""
        logging.debug("hmi set clock source %i", mode)

        self.set_sync_mode(mode, False, True, True, callback)

    # There is a plug-in for that. But Jesse does not find it usable.
    def hmi_get_send_midi_clk(self, callback):
        """Query the status of sending MIDI Beat Clock."""
        logging.debug("hmi get midi beat clock status")

        # TODO: This uses the `utils/utils_jack.cpp` module with
        # hardcoded values for instance ID and port symbol!
        result = has_midi_beat_clock_sender_port()
        callback(True, int(result))

    def hmi_set_send_midi_clk_on(self, callback):
        def operation_failed(ok):
            callback(False)

        def midi_beat_clock_sender_added(ok):
            if ok != MIDI_BEAT_CLOCK_SENDER_INSTANCE_ID:
                callback(False)
                return

            # Connect the plug-in to the MIDI output.
            source_port = "effect_%d:%s" % (MIDI_BEAT_CLOCK_SENDER_INSTANCE_ID, MIDI_BEAT_CLOCK_SENDER_OUTPUT_PORT)
            if self.midi_aggregated_mode:
                target_port = "mod-midi-broadcaster:in"
            else: # TODO: connect to USB MIDI device as well
                target_port = "ttymidi:MIDI_in"
            if not connect_jack_ports(source_port, target_port):
                self.send_notmodified("remove %d" % MIDI_BEAT_CLOCK_SENDER_INSTANCE_ID, operation_failed)
                return

            callback(True)

        self.send_notmodified("add %s %d" % (MIDI_BEAT_CLOCK_SENDER_URI,
                                             MIDI_BEAT_CLOCK_SENDER_INSTANCE_ID), midi_beat_clock_sender_added)

    def hmi_set_send_midi_clk_off(self, callback):
        logging.debug("hmi set midi beat clock OFF")
        # Just remove the plug-in without disconnecting gracefully
        self.send_notmodified("remove %d" % MIDI_BEAT_CLOCK_SENDER_INSTANCE_ID, callback)

    def hmi_set_send_midi_clk(self, onoff, callback):
        """Query the status of sending MIDI Beat Clock."""
        logging.debug("hmi set midi beat clock status to %i", onoff)

        if onoff == 0:
            self.hmi_set_send_midi_clk_off(callback)
        elif onoff == 1:
            self.hmi_set_send_midi_clk_on(callback)
        else:
            callback(False)

    def hmi_get_current_profile(self, callback):
        """Return the index of the currently loaded profile. This is a string."""
        logging.debug("hmi get current profile")
        index, changed = self.profile.get_last_stored_profile_index()
        # TODO: This is bad, because it is not decoupled from the protocol syntax
        callback(True, "{0} {1}".format(index, int(changed)))

    def hmi_retrieve_profile(self, index, callback):
        """Trigger loading profile with `index`."""
        logging.debug("hmi retrieve profile")
        result = self.profile.retrieve(index)
        callback(result)

    def hmi_store_profile(self, index, callback):
        """Trigger storing current profile to `index`."""
        logging.debug("hmi store profile")
        result = self.profile.store(index)
        callback(result)

    def hmi_get_exp_cv(self, callback):
        """Get the mode of the configurable input."""
        logging.debug("hmi get exp/cv mode")
        mode = self.profile.get_configurable_input_mode()
        callback(True, mode)

    def hmi_set_exp_cv(self, mode, callback):
        """Set the mode of the configurable input."""
        logging.debug("hmi set exp/cv mode to %i", mode)
        result = self.profile.set_configurable_input_mode(mode)
        callback(result)

    def hmi_get_hp_cv(self, callback):
        """Get the mode of the configurable output."""
        logging.debug("hmi get hp/cv mode")
        mode = self.profile.get_configurable_output_mode()
        callback(True, mode)

    def hmi_set_hp_cv(self, mode, callback):
        """Set the mode of the configurable output."""
        logging.debug("hmi set hp/cv mode to %i", mode)
        result = self.profile.set_configurable_output_mode(mode)
        callback(result)

    def hmi_get_in_chan_link(self, callback):
        """Get the link state of the input channel pair."""
        result = int(self.profile.get_stereo_link("input"))
        callback(True, result)

    def hmi_set_in_chan_link(self, enabled, callback):
        """Set the link state of the input channel pair."""
        result = self.profile.set_stereo_link("input", bool(enabled))
        callback(result)

    def hmi_get_out_chan_link(self, callback):
        """Get the link state of the output channel pair."""
        result = int(self.profile.get_stereo_link("output"))
        callback(True, result)

    def hmi_set_out_chan_link(self, enabled, callback):
        """Set the link state of the output channel pair."""
        result = self.profile.set_stereo_link("output", bool(enabled))
        callback(result)

    def hmi_get_display_brightness(self, callback):
        """Get the brightness of the display."""
        logging.debug("hmi get display brightness")
        result = self.prefs.get("display-brightness", DEFAULT_DISPLAY_BRIGHTNESS, int, DISPLAY_BRIGHTNESS_VALUES)
        callback(True, result)

    def hmi_set_display_brightness(self, brightness, callback):
        """Set the display_brightness."""
        logging.debug("hmi set display brightness to %i", brightness)
        if brightness in DISPLAY_BRIGHTNESS_VALUES:
            self.prefs.setAndSave("display-brightness", brightness)
            callback(True)
        else:
            callback(False)

    def hmi_get_master_volume_channel_mode(self, callback):
        """Get the mode how the master volume is linked to the channel output volumes."""
        logging.debug("hmi get master volume channel mode")

        result = self.profile.get_master_volume_channel_mode()
        callback(True, result)

    def hmi_set_master_volume_channel_mode(self, mode, callback):
        """Set the mode how the master volume is linked to the channel output volumes."""
        logging.debug("hmi set master volume channel mode to %i", mode)
        result = self.profile.set_master_volume_channel_mode(mode)
        callback(result)

    def hmi_get_play_status(self, callback):
        """Return if the transport is rolling (1) or not (0)."""
        state = get_jack_data(True)['rolling']
        callback(True, int(state))

    def hmi_set_play_status(self, play_status, callback):
        """Set the transport state."""
        self.set_transport_rolling(bool(play_status), True, False, True, callback)

    def hmi_get_tuner_mute(self, callback):
        """Return if the tuner lets audio through or not."""
        callback(True, int(self.current_tuner_mute))

    def hmi_set_tuner_mute(self, mute, callback):
        """Set if the tuner lets audio through or not."""
        if mute:
            self.mute()
        else:
            self.unmute()
        self.current_tuner_mute = mute
        self.prefs.setAndSave("tuner-mutes-outputs", bool(mute))
        callback(True)

    def hmi_get_pb_name(self, callback):
        """Return the name of the currently loaded pedalboard."""
        callback(True, self.pedalboard_name)

    def hmi_get_exp_mode(self, callback):
        """Return, if the expression pedal signal is on tip or sleeve."""
        result = self.profile.get_exp_mode()
        callback(True, result)

    def hmi_set_exp_mode(self, mode, callback):
        """Set the mode mode for the expression pedal input. That is, if the signal is on tip or sleeve."""
        result = self.profile.set_exp_mode(mode)
        callback(result)

    def hmi_get_control_voltage_bias(self, callback):
        """Get the setting of the control voltage bias."""
        result = self.profile.get_control_voltage_bias()
        callback(True, result)

    def hmi_set_control_voltage_bias(self, bias_mode, callback):
        """Set the setting of the control voltage bias."""
        result = self.profile.set_control_voltage_bias(bias_mode)
        callback(result)

    def hmi_snapshot_save(self, idx, callback):
        if idx not in (0, 1):
            return callback(False)

        self.hmi_snapshots[idx] = self.snapshot_make("HMI")
        callback(True)

    def hmi_snapshot_load(self, idx, callback):
        abort_catcher = self.abort_previous_loading_progress("hmi_snapshot_load")
        # Use negative numbers for HMI snapshots
        try:
            self.snapshot_load(0 - (self.HMI_SNAPSHOTS_OFFSET + idx), True, abort_catcher, callback)
        except Exception as e:
            callback(False)
            logging.exception(e)

    def hmi_page_load(self, idx, callback):
        abort_catcher = self.abort_previous_loading_progress("hmi_page_load")
        try:
            self.page_load(idx, abort_catcher, callback)
        except Exception as e:
            callback(False)
            logging.exception(e)

    # -----------------------------------------------------------------------------------------------------------------
    # JACK stuff

    # Get list of Hardware MIDI devices
    # returns (devsInUse, devList, names, midi_aggregated_mode)
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
        return (devsInUse, devList, names, self.midi_aggregated_mode)

    def get_port_name_alias(self, portname):
        alias = get_jack_port_alias(portname)

        if alias:
            return alias.split("-",5)[-1].replace("-"," ").replace(";",".")

        return portname.split(":",1)[-1].title()

    # Set the selected MIDI devices and aggregated mode
    @gen.coroutine
    def set_midi_devices(self, newDevs, midi_aggregated_mode):
        # Change modes first
        if self.midi_aggregated_mode != midi_aggregated_mode:
            try:
                yield gen.Task(self.send_notmodified,
                               "feature_enable aggregated-midi {}".format(int(midi_aggregated_mode)))
            except Exception as e:
                raise e
            self.set_midi_devices_change_mode(midi_aggregated_mode)

        # If MIDI aggregated mode is off, we can handle device changes
        if not midi_aggregated_mode:
            self.set_midi_devices_legacy(newDevs)

    def set_midi_devices_change_mode(self, midi_aggregated_mode):
        # from legacy to aggregated mode
        if midi_aggregated_mode:
            # Remove Serial MIDI ports
            if self.hasSerialMidiIn:
                self.remove_port_from_connections("ttymidi:MIDI_in")
                self.msg_callback("remove_hw_port /graph/serial_midi_in")
            if self.hasSerialMidiOut:
                self.remove_port_from_connections("ttymidi:MIDI_out")
                self.msg_callback("remove_hw_port /graph/serial_midi_out")

            # Remove USB MIDI ports
            for port_symbol, port_alias, port_conns in self.midiports:
                self.remove_port_from_connections(port_symbol)

                if ";" in port_symbol:
                    inp, outp = port_symbol.split(";",1)
                    self.msg_callback("remove_hw_port /graph/%s" % (inp.split(":",1)[-1]))
                    self.msg_callback("remove_hw_port /graph/%s" % (outp.split(":",1)[-1]))
                else:
                    self.msg_callback("remove_hw_port /graph/%s" % (port_symbol.split(":",1)[-1]))

            self.midiports = []

            # Add "All MIDI In/Out" ports
            #if has_midi_broadcaster_input_port():
            self.msg_callback("add_hw_port /graph/midi_broadcaster_in midi 1 All_MIDI_Out 1")
            #if has_midi_merger_output_port():
            self.msg_callback("add_hw_port /graph/midi_merger_out midi 0 All_MIDI_In 1")

        # from aggregated to legacy mode
        else:
            # Remove "All MIDI In/Out" ports
            #if has_midi_broadcaster_input_port():
            self.remove_port_from_connections("mod-midi-broadcaster:in")
            self.msg_callback("remove_hw_port /graph/midi_broadcaster_in")
            #if has_midi_merger_output_port():
            self.remove_port_from_connections("mod-midi-merger:out")
            self.msg_callback("remove_hw_port /graph/midi_merger_out")

            # Add Serial MIDI ports
            if self.hasSerialMidiIn:
                self.msg_callback("add_hw_port /graph/serial_midi_in midi 0 Serial_MIDI_In 0")
            if self.hasSerialMidiOut:
                self.msg_callback("add_hw_port /graph/serial_midi_out midi 1 Serial_MIDI_Out 0")

        self.midi_aggregated_mode = midi_aggregated_mode

    # Will remove or add new JACK ports (in mod-ui) as needed
    def set_midi_devices_legacy(self, newDevs):
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
    # Profile stuff

    @gen.coroutine
    def profile_apply(self, values, isIntermediate):
        try:
            yield gen.Task(self.set_transport_bpb, values['transportBPB'], True, True, True)
            yield gen.Task(self.set_transport_bpm, values['transportBPM'], True, True, True)
        except Exception as e:
            logging.exception(e)

        self.set_sync_mode(values['transportSource'], True, True, False, lambda r:None)

        self.hmi_set_send_midi_clk(values['midiClockSend'], lambda r:None)

        # skip alsamixer related things on intermediate/boot
        if not isIntermediate:
            os.system("mod-amixer in 1 xvol %f" % values['input1volume'])
            os.system("mod-amixer in 2 xvol %f" % values['input2volume'])
            os.system("mod-amixer out 1 xvol %f" % values['output1volume'])
            os.system("mod-amixer out 2 xvol %f" % values['output2volume'])
            os.system("mod-amixer hp xvol %f" % values['headphoneVolume'])
            # TODO
            #'cvBias'
            #'expressionPedalMode'
            #'inputMode' (exp, cv)
            #'outputMode' (hp, cv)

        try:
            yield gen.Task(self.hmi.set_profile_values, self.transport_rolling, values)
        except Exception as e:
            logging.exception(e)

        self.profile_applied = True

    # -----------------------------------------------------------------------------------------------------------------
