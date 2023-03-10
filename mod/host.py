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
with mod-host, the protocol is described in <http://github.com/moddevices/mod-host>

The module relies on tornado.ioloop stuff, but you need to start the ioloop
by yourself:

>>> from tornado import ioloop
>>> ioloop.IOLoop.instance().start()

This will start the mainloop and will handle the callbacks and the async functions
"""

from base64 import b64encode
from collections import OrderedDict
from datetime import timedelta
from random import randint
from tornado import gen, iostream
from tornado.ioloop import IOLoop, PeriodicCallback
from PIL import Image
import os, json, socket, time, logging
import shutil

from mod import (
    TextFileFlusher,
    get_hardware_descriptor, get_nearest_valid_scalepoint_value, get_unique_name,
    read_file_contents, safe_json_load, normalize_for_hw, symbolify
)
from mod.addressings import Addressings
from mod.bank import (
    list_banks, save_banks, get_last_bank_and_pedalboard, save_last_bank_and_pedalboard,
)
from mod.control_chain import (
    CC_MODE_TRIGGER,
    CC_MODE_OPTIONS,
    CC_MODE_MOMENTARY
)
from mod.mod_protocol import (
    CMD_BANKS,
    CMD_BANK_NEW,
    CMD_BANK_DELETE,
    CMD_ADD_PBS_TO_BANK,
    CMD_REORDER_PBS_IN_BANK,
    CMD_PEDALBOARDS,
    CMD_PEDALBOARD_LOAD,
    CMD_PEDALBOARD_RESET,
    CMD_PEDALBOARD_SAVE,
    CMD_PEDALBOARD_SAVE_AS,
    CMD_PEDALBOARD_DELETE,
    CMD_REORDER_SSS_IN_PB,
    CMD_SNAPSHOTS,
    CMD_SNAPSHOTS_LOAD,
    CMD_SNAPSHOTS_SAVE,
    CMD_SNAPSHOT_SAVE_AS,
    CMD_SNAPSHOT_DELETE,
    CMD_CONTROL_GET,
    CMD_CONTROL_SET,
    CMD_CONTROL_PAGE,
    CMD_MENU_ITEM_CHANGE,
    CMD_TUNER_ON,
    CMD_TUNER_OFF,
    CMD_TUNER_INPUT,
    CMD_PROFILE_LOAD,
    CMD_PROFILE_STORE,
    CMD_NEXT_PAGE,
    CMD_SCREENSHOT,
    CMD_DUO_FOOT_NAVIG,
    CMD_DUO_CONTROL_NEXT,
    CMD_DUOX_SNAPSHOT_LOAD,
    CMD_DUOX_SNAPSHOT_SAVE,
    CMD_DWARF_CONTROL_SUBPAGE,
    BANK_FUNC_NONE,
    BANK_FUNC_PEDALBOARD_NEXT,
    BANK_FUNC_PEDALBOARD_PREV,
    FLAG_NAVIGATION_FACTORY,
    FLAG_NAVIGATION_READ_ONLY,
    FLAG_NAVIGATION_DIVIDER,
    FLAG_NAVIGATION_TRIAL_PLUGINS,
    FLAG_CONTROL_ENUMERATION,
    FLAG_CONTROL_TRIGGER,
    FLAG_CONTROL_REVERSE,
    FLAG_CONTROL_MOMENTARY,
    FLAG_PAGINATION_PAGE_UP,
    FLAG_PAGINATION_WRAP_AROUND,
    FLAG_PAGINATION_INITIAL_REQ,
    FLAG_SCALEPOINT_PAGINATED,
    FLAG_SCALEPOINT_WRAP_AROUND,
    FLAG_SCALEPOINT_END_PAGE,
    FLAG_SCALEPOINT_ALT_LED_COLOR,
    MENU_ID_SL_IN,
    MENU_ID_SL_OUT,
    MENU_ID_TUNER_MUTE,
    MENU_ID_QUICK_BYPASS,
    MENU_ID_PLAY_STATUS,
    MENU_ID_MIDI_CLK_SOURCE,
    MENU_ID_MIDI_CLK_SEND,
    MENU_ID_SNAPSHOT_PRGCHGE,
    MENU_ID_PB_PRGCHNGE,
    MENU_ID_TEMPO,
    MENU_ID_BEATS_PER_BAR,
    MENU_ID_BYPASS1,
    MENU_ID_BYPASS2,
    MENU_ID_BRIGHTNESS,
    MENU_ID_CURRENT_PROFILE,
    MENU_ID_FOOTSWITCH_NAV,
    MENU_ID_EXP_CV_INPUT,
    MENU_ID_HP_CV_OUTPUT,
    MENU_ID_MASTER_VOL_PORT,
    MENU_ID_EXP_MODE,
    MENU_ID_TOP,
    menu_item_id_to_str,
)
from mod.profile import (
    Profile,
    apply_mixer_values,
)
from mod.protocol import (
    PLUGIN_LOG_TRACE, PLUGIN_LOG_NOTE, PLUGIN_LOG_WARNING, PLUGIN_LOG_ERROR,
    Protocol, ProtocolError, process_resp,
)
from mod.settings import (
    APP, LOG, DEFAULT_PEDALBOARD,
    DATA_DIR, LV2_PEDALBOARDS_DIR, LV2_FACTORY_PEDALBOARDS_DIR, USER_FILES_DIR,
    PEDALBOARD_INSTANCE, PEDALBOARD_INSTANCE_ID, PEDALBOARD_URI, PEDALBOARD_TMP_DIR,
    TUNER_URI, TUNER_INSTANCE_ID, TUNER_INPUT_PORT, TUNER_MONITOR_PORT, HMI_TIMEOUT, MODEL_TYPE,
    UNTITLED_PEDALBOARD_NAME, DEFAULT_SNAPSHOT_NAME,
    MIDI_BEAT_CLOCK_SENDER_URI, MIDI_BEAT_CLOCK_SENDER_INSTANCE_ID, MIDI_BEAT_CLOCK_SENDER_OUTPUT_PORT,
)
from mod.tuner import (
    find_freqnotecents,
)
from modtools.utils import (
    charPtrToString,
    kPedalboardInfoUserOnly, kPedalboardInfoFactoryOnly,
    is_bundle_loaded, add_bundle_to_lilv_world, remove_bundle_from_lilv_world,
    is_plugin_preset_valid, rescan_plugin_presets,
    get_plugin_info, get_plugin_info_essentials, get_pedalboard_info, get_state_port_values,
    list_plugins_in_bundle, get_all_pedalboards, get_all_user_pedalboard_names, get_pedalboard_plugin_values,
    init_jack, close_jack, get_jack_data,
    init_bypass, get_jack_port_alias, get_jack_hardware_ports,
    has_serial_midi_input_port, has_serial_midi_output_port,
    has_midi_merger_output_port, has_midi_broadcaster_input_port,
    has_midi_beat_clock_sender_port, has_duox_split_spdif,
    connect_jack_ports, connect_jack_midi_output_ports, disconnect_jack_ports, disconnect_all_jack_ports,
    set_truebypass_value, get_master_volume,
    set_util_callbacks, set_extra_util_callbacks, kPedalboardTimeAvailableBPB,
    kPedalboardTimeAvailableBPM, kPedalboardTimeAvailableRolling
)
from modtools.tempo import (
    convert_port_value_to_seconds_equivalent,
    convert_seconds_to_port_value_equivalent,
    get_divider_value,
    get_port_value,
)

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

# CV related constants
CV_PREFIX = 'cv_'
CV_OPTION = '/cv'
HW_CV_PREFIX = CV_OPTION + '/graph/' + CV_PREFIX

# TODO: check pluginData['designations'] when doing addressing
# TODO: hmi_save_current_pedalboard does not send browser msgs, needed?
# TODO: finish presets, testing

def midi_port_alias_to_name(alias, withSpaces):
    space = " " if withSpaces else "_"
    if False:
        # for alsa-raw midi option
        return alias.split("-",5)[-1].replace("-",space).replace(";",".")
    else:
        # for alsa-seq midi option
        return alias.split(":",1)[-1].replace("-",space).replace(";",".")\
          .replace("/midi_capture_",space+"MIDI"+space)\
          .replace("/midi_playback_",space+"MIDI"+space)

def get_all_good_and_bad_pedalboards(ptype):
    allpedals  = get_all_pedalboards(ptype)
    goodpedals = []
    badbundles = []

    for pb in allpedals:
        if pb['broken']:
            badbundles.append(pb['bundle'])
        else:
            goodpedals.append(pb)

    if len(goodpedals) == 0:
        goodpedals.append({
            'broken': False,
            'factory': False,
            'hasTrialPlugins': False,
            'uri': "file://" + DEFAULT_PEDALBOARD,
            'bundle': DEFAULT_PEDALBOARD,
            'title': UNTITLED_PEDALBOARD_NAME,
            'version': 0,
        })

    return goodpedals, badbundles

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
        return idx

    # get a numeric id from a string instance
    # Tries to use a pre-defined id first if possible
    def get_id_by_number(self, instance, instanceNumber):
        if instanceNumber < 0:
            return self.get_id(instance)

        if instanceNumber in self.id_map.keys():
            return self.get_id(instance)

        self.last_id = max(self.last_id, instanceNumber+1)
        self.instance_map[instance] = instanceNumber
        self.id_map[instanceNumber] = instance

        # ready
        return instanceNumber

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
    HMI_SNAPSHOTS_1      = 0 - (HMI_SNAPSHOTS_OFFSET + 0)
    HMI_SNAPSHOTS_2      = 0 - (HMI_SNAPSHOTS_OFFSET + 1)
    HMI_SNAPSHOTS_3      = 0 - (HMI_SNAPSHOTS_OFFSET + 2)

    def __init__(self, hmi, prefs, msg_callback):
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
        self.hmi_ping_io = None

        self.addressings = Addressings()
        self.mapper = InstanceIdMapper()
        self.descriptor = get_hardware_descriptor()
        self.profile = Profile(self.profile_apply, self.descriptor)

        self.swapped_audio_channels = self.descriptor.get('swapped_audio_channels', False)
        self.current_tuner_port = 2 if self.swapped_audio_channels else 1
        self.current_tuner_mute = self.prefs.get("tuner-mutes-outputs", False, bool)

        if self.descriptor.get('factory_pedalboards', False):
            self.supports_factory_banks = True
            self.pedalboard_index_offset = 0
            self.userbanks_offset = 2
            self.first_user_bank = 1
        else:
            self.supports_factory_banks = False
            self.pedalboard_index_offset = 1
            self.userbanks_offset = 1
            self.first_user_bank = 0

        self.web_connected = False
        self.web_data_ready_counter = 0
        self.web_data_ready_ok = True

        self.alluserpedalboards = None
        self.allfactorypedalboards = None
        self.userbanks = None
        self.factorybanks = None

        self.bank_id = self.first_user_bank
        self.connections = []
        self.audioportsIn = []
        self.audioportsOut = []
        self.cvportsIn = []
        self.cvportsOut = []
        self.midiports = [] # [symbol, alias, pending-connections]
        self.midi_aggregated_mode = True
        self.midi_loopback_enabled = False
        self.midi_loopback_port = None
        self.hasSerialMidiIn = False
        self.hasSerialMidiOut = False
        self.first_pedalboard    = True
        self.pedalboard_empty    = True
        self.pedalboard_modified = False
        self.pedalboard_name     = ""
        self.pedalboard_path     = ""
        self.pedalboard_size     = [0,0]
        self.pedalboard_version  = 0
        self.current_pedalboard_snapshot_id = -1
        self.pedalboard_snapshots = []
        self.next_hmi_pedalboard_to_load = None
        self.next_hmi_pedalboard_loading = False
        self.next_hmi_bpb = [0, False, False]
        self.next_hmi_bpm = [0, False, False]
        self.next_hmi_play = [False, False, False]
        self.hmi_snapshots = [None, None, None]
        self.hmi_screenshot_data = [None]*8
        self.transport_rolling = False
        self.transport_bpb     = 4.0
        self.transport_bpm     = 120.0
        self.transport_sync    = "none"
        self.last_data_finish_msg = 0.0
        self.last_data_finish_handle = None
        self.last_true_bypass_left = True
        self.last_true_bypass_right = True
        self.last_cv_exp_mode = False
        self.abort_progress_catcher = {}
        self.processing_pending_flag = False
        self.init_plugins_data()

        # clients at the end of the chain, all managed by mod-host
        self.jack_hw_capture_prefix = "mod-host:out" if self.descriptor.get('has_noisegate', False) else "system:capture_"

        # used for network-manager
        self.jack_slave_prefix = "mod-slave"

        # used for usb gadget, MUST have "c" or "p" after this prefix
        self.jack_usbgadget_prefix = "mod-usbgadget_"

        self.statstimer = PeriodicCallback(self.statstimer_callback, 1000)

        self.memfile  = None
        self.memtimer = None
        self.cpufreqfile = None
        self.thermalfile = None

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
                self.memtimer = PeriodicCallback(self.memtimer_callback, 5000)

                if os.path.exists("/sys/class/thermal/thermal_zone0/temp"):
                    self.thermalfile = open("/sys/class/thermal/thermal_zone0/temp", 'r')
                else:
                    self.thermalfile = None

                if os.path.exists("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"):
                    self.cpufreqfile = open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq", 'r')
                else:
                    self.cpufreqfile = None

        set_util_callbacks(self.jack_bufsize_changed,
                           self.jack_port_appeared,
                           self.jack_port_deleted,
                           self.true_bypass_changed)
        set_extra_util_callbacks(self.cv_exp_mode_changed)

        # Setup addressing callbacks
        self.addressings._task_addressing = self.addr_task_addressing
        self.addressings._task_unaddressing = self.addr_task_unaddressing
        self.addressings._task_set_value = self.addr_task_set_value
        self.addressings._task_get_plugin_cv_port_op_mode = self.addr_task_get_plugin_cv_port_op_mode
        self.addressings._task_get_plugin_data = self.addr_task_get_plugin_data
        self.addressings._task_get_plugin_presets = self.addr_task_get_plugin_presets
        self.addressings._task_get_port_value = self.addr_task_get_port_value
        self.addressings._task_get_tempo_divider = self.addr_task_get_tempo_divider
        self.addressings._task_store_address_data = self.addr_task_store_address_data
        self.addressings._task_hw_added = self.addr_task_hw_added
        self.addressings._task_hw_removed = self.addr_task_hw_removed
        self.addressings._task_act_added = self.addr_task_act_added
        self.addressings._task_act_removed = self.addr_task_act_removed
        self.addressings._task_set_available_pages = self.addr_task_set_available_pages
        self.addressings._task_host_hmi_map = self.addr_host_hmi_map
        self.addressings._task_host_hmi_unmap = self.addr_host_hmi_unmap

        # Register HMI protocol callbacks (they are without arguments here)
        Protocol.register_cmd_callback('ALL', CMD_BANKS, self.hmi_list_banks)
        Protocol.register_cmd_callback('ALL', CMD_PEDALBOARDS, self.hmi_list_bank_pedalboards)
        Protocol.register_cmd_callback('ALL', CMD_SNAPSHOTS, self.hmi_list_pedalboard_snapshots)

        Protocol.register_cmd_callback('ALL', CMD_BANK_NEW, self.hmi_bank_new)
        Protocol.register_cmd_callback('ALL', CMD_BANK_DELETE, self.hmi_bank_delete)
        Protocol.register_cmd_callback('ALL', CMD_ADD_PBS_TO_BANK, self.hmi_bank_add_pedalboards_or_banks)
        Protocol.register_cmd_callback('ALL', CMD_REORDER_PBS_IN_BANK, self.hmi_bank_reorder_pedalboards)

        Protocol.register_cmd_callback('ALL', CMD_PEDALBOARD_LOAD, self.hmi_load_bank_pedalboard)
        Protocol.register_cmd_callback('ALL', CMD_PEDALBOARD_RESET, self.hmi_reset_current_pedalboard)
        Protocol.register_cmd_callback('ALL', CMD_PEDALBOARD_SAVE, self.hmi_save_current_pedalboard)
        Protocol.register_cmd_callback('ALL', CMD_PEDALBOARD_SAVE_AS, self.hmi_pedalboard_save_as)
        Protocol.register_cmd_callback('ALL', CMD_PEDALBOARD_DELETE, self.hmi_pedalboard_remove_from_bank)
        Protocol.register_cmd_callback('ALL', CMD_REORDER_SSS_IN_PB, self.hmi_pedalboard_reorder_snapshots)

        Protocol.register_cmd_callback('ALL', CMD_SNAPSHOTS_LOAD, self.hmi_pedalboard_snapshot_load)
        Protocol.register_cmd_callback('ALL', CMD_SNAPSHOTS_SAVE, self.hmi_pedalboard_snapshot_save)
        Protocol.register_cmd_callback('ALL', CMD_SNAPSHOT_SAVE_AS, self.hmi_pedalboard_snapshot_save_as)
        Protocol.register_cmd_callback('ALL', CMD_SNAPSHOT_DELETE, self.hmi_pedalboard_snapshot_delete)

        Protocol.register_cmd_callback('ALL', CMD_CONTROL_GET, self.hmi_parameter_get)
        Protocol.register_cmd_callback('ALL', CMD_CONTROL_SET, self.hmi_parameter_set)

        Protocol.register_cmd_callback('ALL', CMD_SCREENSHOT, self.hmi_screenshot)

        # TODO support on duo and duox
        if self.descriptor.get('platform', None) != "dwarf":
            Protocol.register_cmd_callback('DUO', CMD_CONTROL_PAGE, self.hmi_next_control_page_compat)
        else:
            Protocol.register_cmd_callback('ALL', CMD_CONTROL_PAGE, self.hmi_next_control_page)

        Protocol.register_cmd_callback('ALL', CMD_TUNER_ON, self.hmi_tuner_on)
        Protocol.register_cmd_callback('ALL', CMD_TUNER_OFF, self.hmi_tuner_off)
        Protocol.register_cmd_callback('ALL', CMD_TUNER_INPUT, self.hmi_tuner_input)

        Protocol.register_cmd_callback('ALL', CMD_MENU_ITEM_CHANGE, self.hmi_menu_item_change)

        Protocol.register_cmd_callback('ALL', CMD_PROFILE_LOAD, self.hmi_retrieve_profile)
        Protocol.register_cmd_callback('ALL', CMD_PROFILE_STORE, self.hmi_store_profile)

        Protocol.register_cmd_callback('ALL', CMD_NEXT_PAGE, self.hmi_page_load)

        Protocol.register_cmd_callback('DUO', CMD_DUO_FOOT_NAVIG, self.hmi_footswitch_navigation)
        Protocol.register_cmd_callback('DUO', CMD_DUO_CONTROL_NEXT, self.hmi_parameter_addressing_next)

        Protocol.register_cmd_callback('DUOX', CMD_DUOX_SNAPSHOT_LOAD, self.hmi_snapshot_load)
        Protocol.register_cmd_callback('DUOX', CMD_DUOX_SNAPSHOT_SAVE, self.hmi_snapshot_save)

        Protocol.register_cmd_callback('DWARF', CMD_DWARF_CONTROL_SUBPAGE, self.hmi_parameter_load_subpage)

        if not APP:
            IOLoop.instance().add_callback(self.init_host)

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
            elif name.startswith(CV_PREFIX):
                ptype = "cv"
            else:
                ptype = "audio"

            index = 100 + int(name.rsplit("_",1)[-1])
            title = name.title().replace(" ","_")
            self.msg_callback("add_hw_port /graph/%s %s %i %s %i" % (name, ptype, int(isOutput), title, index))
            return

        if name.startswith(self.jack_usbgadget_prefix):
            name = name[len(self.jack_usbgadget_prefix+2):]
            ptype = "audio"
            index = 200 + int(name.rsplit("_",1)[-1])
            title = name.title().replace(" ","_")
            self.msg_callback("add_hw_port /graph/%s %s %i %s %i" % (name, ptype, int(isOutput), title, index))
            return

        if self.midi_aggregated_mode:
            # new ports are ignored under midi aggregated mode
            return

        alias = get_jack_port_alias(name)
        if not alias:
            return
        alias = midi_port_alias_to_name(alias, True)

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

        if self.hmi.initialized:
            if self.last_true_bypass_left != left:
                self.hmi.set_profile_value(MENU_ID_BYPASS1, int(left), None)
            if self.last_true_bypass_right != right:
                self.hmi.set_profile_value(MENU_ID_BYPASS2, int(right), None)

        self.last_true_bypass_left = left
        self.last_true_bypass_right = right

    #TODO, This message should be handled by mod-system-control once in place
    def cv_exp_mode_changed(self, expMode):
        if self.last_cv_exp_mode != expMode:
            self.last_cv_exp_mode = expMode

            if self.hmi.initialized and self.profile_applied and not expMode:
                self.hmi.expression_overcurrent(None)

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

    def addr_host_hmi_map(self, instance_id, portsymbol, hw_id, page, subpage, caps, flags, label, min, max, steps):
        self.send_notmodified("hmi_map %i %s %i %i %i %i %i %s %f %f %i" % (instance_id, portsymbol,
                                                                            hw_id, page, subpage,
                                                                            caps, flags, label, min, max, steps))

    def addr_host_hmi_unmap(self, instance_id, portsymbol):
        self.send_notmodified("hmi_unmap %i %s" % (instance_id, portsymbol))

    def addr_task_addressing(self, atype, actuator, data, callback, send_hmi=True):
        if atype == Addressings.ADDRESSING_TYPE_HMI:
            if send_hmi and self.hmi.initialized:
                actuator_uri = self.addressings.hmi_hw2uri_map[actuator]
                self.hmi.control_add(data, actuator, actuator_uri, callback)
                return
            else:
                if callback is not None:
                    callback(True)
                return

        if atype == Addressings.ADDRESSING_TYPE_CC:
            label = normalize_for_hw(data['label'], 15)
            unit  = normalize_for_hw(data['unit'], 15)

            rmaximum    = data['maximum']
            rvalue      = data['value']
            extraflags  = data.get('cctype', 0x0)
            optionsData = []

            if data['options']:
                currentNum = 0
                numBytesFree = 1024-128

                for o in data['options']:
                    if currentNum > 50:
                        if rvalue >= currentNum:
                            rvalue = 0
                        rmaximum = currentNum
                        break

                    optdata    = '%s %f' % (normalize_for_hw(o[1], 15), float(o[0]))
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

            device_id, actuator_id = actuator
            if not isinstance(actuator_id, int):
                actuator_id = actuator_id[0]

            self.send_notmodified("cc_map %d %s %d %d %s %f %f %f %i %i %s %s" % (data['instance_id'],
                                                                                  data['port'],
                                                                                  device_id,
                                                                                  actuator_id,
                                                                                  label,
                                                                                  rvalue,
                                                                                  data['minimum'],
                                                                                  rmaximum,
                                                                                  data['steps'],
                                                                                  extraflags,
                                                                                  unit,
                                                                                  options
                                                                                  ), callback, datatype='boolean')
            return

        if atype == Addressings.ADDRESSING_TYPE_MIDI:
            self.send_notmodified("midi_map %d %s %i %i %f %f" % (data['instance_id'],
                                                                  data['port'],
                                                                  data['midichannel'],
                                                                  data['midicontrol'],
                                                                  data['minimum'],
                                                                  data['maximum'],
                                                                  ), callback, datatype='boolean')
            return

        if atype == Addressings.ADDRESSING_TYPE_BPM:
            if callback is not None:
                callback(True)
            return

        if atype == Addressings.ADDRESSING_TYPE_CV:
            source_port_name = self.get_jack_source_port_name(actuator)
            self.send_notmodified("cv_map %d %s %s %f %f %s" % (data['instance_id'],
                                                                data['port'],
                                                                source_port_name,
                                                                data['minimum'],
                                                                data['maximum'],
                                                                data['operational_mode']
                                                                ), callback, datatype='boolean')
            return

        print("ERROR: Invalid addressing requested for", actuator)
        callback(False)
        return

    def addr_task_unaddressing(self, atype, instance_id, portsymbol, callback, send_hmi=True, hw_ids=None):
        if atype == Addressings.ADDRESSING_TYPE_HMI:
            self.pedalboard_modified = True
            if send_hmi:
                self.hmi.control_rm(hw_ids, callback)
            elif callback is not None:
                callback(True)
            return

        if atype == Addressings.ADDRESSING_TYPE_CC:
            self.send_modified("cc_unmap %d %s" % (instance_id, portsymbol), callback, datatype='boolean')
            return

        if atype == Addressings.ADDRESSING_TYPE_MIDI:
            self.send_modified("midi_unmap %d %s" % (instance_id, portsymbol), callback, datatype='boolean')
            return

        if atype == Addressings.ADDRESSING_TYPE_CV:
            self.send_modified("cv_unmap %d %s" % (instance_id, portsymbol), callback, datatype='boolean')
            return

        if atype == Addressings.ADDRESSING_TYPE_BPM:
            if callback is not None:
                callback(True)
            return

        print("ERROR: Invalid unaddressing requested")
        callback(False)
        return

    def addr_task_set_value(self, atype, actuator, data, callback, send_hmi=True):
        if atype == Addressings.ADDRESSING_TYPE_HMI:
            if not self.hmi.initialized:
                callback(False)
                return

            if data['hmitype'] & FLAG_CONTROL_ENUMERATION:
                options = tuple(o[0] for o in data['options'])
                try:
                    value = options.index(data['value'])
                except ValueError:
                    logging.error("[host] address set value not in list %f", data['value'])
                    callback(False)
                    return
                # NOTE the following code does a control_add instead of control_set in case of big enums
                # Making it work on HMI with pagination could be tricky, so work around this for now
                if not data.get('tempo', False):
                    actuator_uri = data['actuator_uri']
                    logging.error("[host] addr_task_set_value called with an enumeration %s", actuator_uri)
                    self.addressings.hmi_load_current(actuator_uri, callback)
                    return
            else:
                value = data['value']

            if send_hmi:
                self.hmi.control_set(actuator, value, callback)
            elif callback is not None:
                callback(True)

            return

        if atype == Addressings.ADDRESSING_TYPE_CC:
            if data['cctype'] & CC_MODE_OPTIONS:
                options = tuple(o[0] for o in data['options'])
                try:
                    value = options.index(data['value'])
                except ValueError:
                    logging.error("[host] address set value not in list %f", data['value'])
                    callback(False)
                    return
                # FIXME maybe, this likely will never work
                logging.error("[host] addr_task_set_value called with an enumeration %s", data['actuator_uri'])
                callback(False)
                return

            self.send_modified("cc_value_set %d %s %f" % (data['instance_id'], data['port'], data['value']),
                               callback, datatype='boolean')
            return

        # Everything else has nothing
        callback(True)

    def addr_task_get_plugin_data(self, instance_id):
        return self.plugins[instance_id]

    def addr_task_get_plugin_presets(self, uri):
        if uri == PEDALBOARD_URI:
            self.plugins[PEDALBOARD_INSTANCE_ID]['preset'] = "file:///%i" % self.current_pedalboard_snapshot_id
            snapshots = self.pedalboard_snapshots
            presets = [{'uri': 'file:///%i'%i,
                        'label': snapshots[i]['name']} for i in range(len(snapshots)) if snapshots[i] is not None]
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

    def addr_task_get_tempo_divider(self, instance_id, portsymbol):
        pluginData = self.plugins[instance_id]
        return pluginData['addressings'][portsymbol]['dividers']

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

    def addr_task_set_available_pages(self, pages, callback):
        if self.hmi.initialized:
            self.hmi.set_available_pages(pages, callback)
            return
        print("WARNING: Trying to send available pages, HMI not initialized")
        callback(False)

    def addr_task_get_plugin_cv_port_op_mode(self, actuator_uri):
        instance, port = actuator_uri.split(CV_OPTION,1)[1].rsplit("/", 1)
        instance_id = self.mapper.get_id_without_creating(instance)
        plugin_data = self.plugins[instance_id]
        plugin_info = get_plugin_info(plugin_data['uri'])
        port_info = next((p for p in plugin_info['ports']['cv']['output'] if p['symbol'] == port), None)
        if port_info:
            maximum = port_info['ranges']['maximum']
            minimum = port_info['ranges']['minimum']
            if minimum < 0 and maximum <= 0: # unipolar-
                return "-"
            if minimum < 0 and maximum > 0: # bipolar
                return "b"
            if minimum >= 0 and maximum > 0: # unipolar+
                return "+"
        return "+"

    # -----------------------------------------------------------------------------------------------------------------
    # HMI messages postponed for later

    @gen.coroutine
    def process_postponed_messages(self):
        if self.next_hmi_pedalboard_loading:
            return

        if self.next_hmi_bpb[1] or self.next_hmi_bpb[2]:
            bpb, sendHMI, sendHMIAddressing = self.next_hmi_bpb
            self.next_hmi_bpb[1] = self.next_hmi_bpb[2] = False

            if sendHMIAddressing:
                try:
                    yield gen.Task(self.paramhmi_set, 'pedalboard', ":bpb", bpb)
                except Exception as e:
                    logging.exception(e)

            if sendHMI:
                try:
                    yield gen.Task(self.hmi.set_profile_value, MENU_ID_BEATS_PER_BAR, bpb)
                except Exception as e:
                    logging.exception(e)

        if self.next_hmi_bpm[1] or self.next_hmi_bpm[2]:
            bpm, sendHMI, sendHMIAddressing = self.next_hmi_bpm
            self.next_hmi_bpm[1] = self.next_hmi_bpm[2] = False

            if sendHMIAddressing:
                try:
                    yield gen.Task(self.paramhmi_set, 'pedalboard', ":bpm", bpm)
                except Exception as e:
                    logging.exception(e)

            if sendHMI:
                try:
                    yield gen.Task(self.hmi.set_profile_value, MENU_ID_TEMPO, bpm)
                except Exception as e:
                    logging.exception(e)

            for actuator_uri in self.addressings.hmi_addressings:
                addrs = self.addressings.hmi_addressings[actuator_uri]['addrs']
                for addr in addrs:
                    try:
                        yield gen.Task(self.set_param_from_bpm, addr, bpm)
                    except Exception as e:
                        logging.exception(e)

        if self.next_hmi_play[1] or self.next_hmi_play[2]:
            rolling, sendHMI, sendHMIAddressing = self.next_hmi_play
            self.next_hmi_play[1] = self.next_hmi_play[2] = False

            if sendHMIAddressing:
                try:
                    yield gen.Task(self.paramhmi_set, 'pedalboard', ":rolling", int(rolling))
                except Exception as e:
                    logging.exception(e)

            if sendHMI:
                try:
                    yield gen.Task(self.hmi.set_profile_value, MENU_ID_PLAY_STATUS, int(rolling))
                except Exception as e:
                    logging.exception(e)

    # -----------------------------------------------------------------------------------------------------------------
    # Initialization

    def ping_hmi(self):
        if self.hmi_ping_io is not None:
            IOLoop.instance().remove_timeout(self.hmi_ping_io)
        self.hmi_ping_io = IOLoop.instance().call_later(5, self.ping_hmi)
        self.hmi.ping(None)

    def ping_hmi_start(self):
        if self.hmi_ping_io is None:
            self.hmi_ping_io = IOLoop.instance().call_later(5, self.ping_hmi)

    def ping_hmi_stop(self):
        if self.hmi_ping_io is not None:
            IOLoop.instance().remove_timeout(self.hmi_ping_io)
            self.hmi_ping_io = None

    def wait_hmi_initialized(self, callback):
        if (self.hmi.initialized and self.profile_applied) or self.hmi.isFake():
            print("HMI initialized right away")
            callback(True)
            return

        def retry():
            if (self.hmi.initialized and self.profile_applied) or self._attemptNumber >= 20:
                print("HMI initialized FINAL", self._attemptNumber, self.hmi.initialized)
                del self._attemptNumber
                if HMI_TIMEOUT > 0:
                    self.ping_hmi_start()
                callback(self.hmi.initialized)
            else:
                self._attemptNumber += 1
                IOLoop.instance().call_later(0.25, retry)
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

        # Set directory for temporary data
        self.send_notmodified("state_tmpdir {}".format(PEDALBOARD_TMP_DIR))

        # get current transport data
        data = get_jack_data(True)
        self.transport_rolling = data['rolling']
        self.transport_bpm     = data['bpm']
        self.transport_bpb     = data['bpb']

        # load everything
        userpedals, baduserbundles = get_all_good_and_bad_pedalboards(kPedalboardInfoUserOnly)
        factorypedals, badfactorybundles = get_all_good_and_bad_pedalboards(kPedalboardInfoFactoryOnly)

        self.alluserpedalboards = userpedals
        self.allfactorypedalboards = factorypedals

        self.userbanks = list_banks(baduserbundles, True, True)

        if self.supports_factory_banks:
            self.factorybanks = list_banks(badfactorybundles, False, False)
        else:
            self.factorybanks = []

        bank_id, pedalboard = get_last_bank_and_pedalboard()

        # ensure HMI is initialized by now
        yield gen.Task(self.wait_hmi_initialized)

        if pedalboard and os.path.exists(pedalboard):
            self.bank_id = bank_id
            self.load(pedalboard)

        else:
            self.bank_id = self.first_user_bank

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
        self.cvportsIn  = []
        self.cvportsOut = []

        if not init_jack():
            self.hasSerialMidiIn = False
            self.hasSerialMidiOut = False
            return False

        for port in get_jack_hardware_ports(True, False):
            client_name, port_name = port.split(":",1)
            if client_name == "mod-spi2jack":
                cv_port_name = CV_PREFIX + port_name
                self.cvportsIn.append(cv_port_name)
                self.addressings.add_hw_cv_port('/cv/graph/' + cv_port_name)
            else:
                self.audioportsIn.append(port_name)

        for port in get_jack_hardware_ports(True, True):
            client_name, port_name = port.split(":",1)
            if client_name == "mod-jack2spi":
                self.cvportsOut.append(CV_PREFIX + port_name)
            else:
                self.audioportsOut.append(port_name)

        for port in get_jack_hardware_ports(False, True):
            if not port.startswith("system:midi_"):
                continue
            alias = get_jack_port_alias(port)
            if not alias:
                continue
            if alias == "alsa_pcm:Midi-Through/midi_capture_1":
                self.midi_loopback_port = port
                self.midi_loopback_enabled = False
                disconnect_all_jack_ports(port)
                break
        else:
            self.midi_loopback_port = None
            self.midi_loopback_enabled = False

        self.hasSerialMidiIn = has_serial_midi_input_port()
        self.hasSerialMidiOut = has_serial_midi_output_port()
        self.midi_aggregated_mode = has_midi_merger_output_port() or has_midi_broadcaster_input_port()

        return True

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
                "mapPresets"  : [],
                "nextPreset"  : "",
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
                self.process_postponed_messages()

        self._idle = False
        self._queue = []

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
        self.connected = False
        self.statstimer.stop()

        if self.memtimer is not None:
            self.memtimer.stop()

        self.msg_callback("stop")

        while True:
            try:
                msg, callback, datatype = self._queue.pop(0)
                logging.debug("[host] popped from queue: %s", msg)
            except IndexError:
                self._idle = True
                break

            if callback is not None:
                callback(process_resp(None, datatype))

        IOLoop.instance().call_later(5, self.reconnect_jack)

    def send_hmi_boot(self, callback):
        display_brightness = self.prefs.get("display-brightness", DEFAULT_DISPLAY_BRIGHTNESS, int, DISPLAY_BRIGHTNESS_VALUES)
        quick_bypass_mode = self.prefs.get("quick-bypass-mode", DEFAULT_QUICK_BYPASS_MODE, int, QUICK_BYPASS_MODE_VALUES)

        bootdata = "{} {} {} {}".format(display_brightness,
                                        quick_bypass_mode,
                                        int(self.current_tuner_mute),
                                        self.profile.get_index())

        if self.descriptor.get('hmi_set_master_vol', False):
            master_chan_mode = self.profile.get_master_volume_channel_mode()
            master_chan_is_mode_2 = master_chan_mode == Profile.MASTER_VOLUME_CHANNEL_MODE_2
            bootdata += " {} {}".format(master_chan_mode, get_master_volume(master_chan_is_mode_2))

        # we will dispatch all messages in reverse order, terminating in "boot"
        msgs = [(self.hmi.boot, [bootdata])]

        if self.descriptor.get('hmi_set_pb_name', False):
            pbname = self.pedalboard_name or UNTITLED_PEDALBOARD_NAME
            msgs.append((self.hmi.set_pedalboard_name, [pbname]))

        if self.descriptor.get('hmi_set_ss_name', False):
            ssname = self.snapshot_name() or DEFAULT_SNAPSHOT_NAME
            msgs.append((self.hmi.set_snapshot_name, [self.current_pedalboard_snapshot_id, ssname]))

        if self.descriptor.get('addressing_pages', 0):
            pages = self.addressings.get_available_pages()
            msgs.append((self.hmi.set_available_pages, [pages]))

        if self.isBankFootswitchNavigationOn():
            msgs.append((self.hmi.set_profile_value, [MENU_ID_FOOTSWITCH_NAV, 1])) # FIXME profile as name is wrong

        def send_boot_msg(_):
            try:
                func, args = msgs.pop(len(msgs)-1)
            except IndexError:
                callback(True)
                return
            else:
                args.append(send_boot_msg)
                func(*args)

        send_boot_msg(None)

    @gen.coroutine
    def reconnect_hmi(self, hmi):
        abort_catcher = self.abort_previous_loading_progress("reconnect_hmi")
        self.hmi = hmi
        self.next_hmi_pedalboard_to_load = None
        self.next_hmi_pedalboard_loading = False
        self.next_hmi_bpb = [0, False, False]
        self.next_hmi_bpm = [0, False, False]
        self.next_hmi_play = [False, False, False]
        self.hmi_snapshots = [None, None, None]
        self.processing_pending_flag = False
        self.open_connection_if_needed(None)

        # Wait for init
        yield gen.Task(self.wait_hmi_initialized)

        if not self.hmi.initialized:
            return

        self.profile.apply_first()
        yield gen.Task(self.send_hmi_boot)
        yield gen.Task(self.initialize_hmi, False)

        actuators = [actuator['uri'] for actuator in self.descriptor.get('actuators', [])]
        self.addressings.current_page = 0
        self.addressings.load_current(actuators, (None, None), False, True, abort_catcher)

    def reconnect_jack(self):
        if not self.init_jack():
            return
        self.open_connection_if_needed(None)

    # -----------------------------------------------------------------------------------------------------------------

    def isBankFootswitchNavigationOn(self):
        return (
            self.descriptor.get("hmi_bank_navigation", False) and
            self.prefs.get("bank-footswitch-navigation", False)
        )

    def setNavigateWithFootswitches(self, enabled, callback):
        def foot2_callback(_):
            acthw  = self.addressings.hmi_uri2hw_map["/hmi/footswitch2"]
            cfgact = BANK_FUNC_PEDALBOARD_NEXT if enabled else BANK_FUNC_NONE
            self.hmi.bank_config(acthw, cfgact, callback)

        acthw  = self.addressings.hmi_uri2hw_map["/hmi/footswitch1"]
        cfgact = BANK_FUNC_PEDALBOARD_PREV if enabled else BANK_FUNC_NONE
        self.hmi.bank_config(acthw, cfgact, foot2_callback)

    # -----------------------------------------------------------------------------------------------------------------

    def initialize_hmi(self, uiConnected, callback):
        # If UI is already connected, do nothing
        if uiConnected:
            callback(True)
            return

        userpedals, baduserbundles = get_all_good_and_bad_pedalboards(kPedalboardInfoUserOnly)
        factorypedals, badfactorybundles = get_all_good_and_bad_pedalboards(kPedalboardInfoFactoryOnly)

        self.alluserpedalboards = userpedals
        self.allfactorypedalboards = factorypedals

        self.userbanks = list_banks(baduserbundles, True, False)

        if self.supports_factory_banks:
            self.factorybanks = list_banks(badfactorybundles, False, False)
        else:
            self.factorybanks = []

        numUserBanks = len(self.userbanks)
        numFactoryBanks = len(self.factorybanks)
        numBanks = numUserBanks + numFactoryBanks + 1

        if self.supports_factory_banks:
            numBanks += 3

        bank_id, pedalboard = get_last_bank_and_pedalboard()

        validpedalboard = False
        first_valid_bank = 1 if self.supports_factory_banks else 0

        # out of bounds
        if bank_id < first_valid_bank or bank_id >= numBanks:
            bank_id = first_valid_bank
        # divider
        elif self.supports_factory_banks and bank_id in (0, numUserBanks + 2):
            bank_id = first_valid_bank

        if pedalboard:
            if os.path.exists(pedalboard):
                validpedalboard = True
            else:
                bank_id = first_valid_bank
                pedalboard = ""

        # user PBs
        if bank_id >= self.userbanks_offset and bank_id - self.userbanks_offset < numUserBanks:
            bankflags = 0
            pedalflags = 0
            pedalboards = self.userbanks[bank_id - self.userbanks_offset]['pedalboards']

        # all factory PBs
        elif self.supports_factory_banks and bank_id == numUserBanks + 3:
            bankflags = FLAG_NAVIGATION_FACTORY|FLAG_NAVIGATION_READ_ONLY
            pedalflags = FLAG_NAVIGATION_FACTORY|FLAG_NAVIGATION_READ_ONLY
            pedalboards = self.allfactorypedalboards

        # factory PBs
        elif self.supports_factory_banks and bank_id > numUserBanks + 2:
            bankflags = FLAG_NAVIGATION_FACTORY|FLAG_NAVIGATION_READ_ONLY
            pedalflags = FLAG_NAVIGATION_FACTORY|FLAG_NAVIGATION_READ_ONLY
            pedalboards = self.factorybanks[bank_id - numUserBanks - 3]['pedalboards']

        # all user PBs (fallback)
        else:
            bank_id = first_valid_bank
            bankflags = FLAG_NAVIGATION_READ_ONLY
            pedalflags = 0
            pedalboards = self.alluserpedalboards

            if not validpedalboard:
                pedalboard = DEFAULT_PEDALBOARD if os.path.exists(DEFAULT_PEDALBOARD) else ""
                pedalflags = FLAG_NAVIGATION_READ_ONLY

        if pedalboard:
            for num, pb in enumerate(pedalboards):
                if pb['bundle'] == pedalboard:
                    pedalboard_index = num
                    break
            else:
                # we loaded a pedalboard that is not in the bank, try loading from "All User Pedalboards" bank
                bank_id = first_valid_bank
                bankflags = FLAG_NAVIGATION_READ_ONLY
                pedalboards = self.alluserpedalboards

                for num, pb in enumerate(pedalboards):
                    if pb['bundle'] == pedalboard:
                        pedalboard_index = num
                        break
                else:
                    # well, shit
                    pedalboard_index = 0
                    pedalboard = ""

        else:
            pedalboard_index = 0

        numPedals = len(pedalboards)

        if numPedals <= 9 or pedalboard_index < 4:
            startIndex = 0
        elif pedalboard_index + 4 >= numPedals:
            startIndex = numPedals - 9
        else:
            startIndex = pedalboard_index - 4

        startIndex = max(startIndex, 0)
        endIndex = min(startIndex + 9, numPedals)

        if self.supports_factory_banks:
            initial_state_data = '%d %d %d %d %d %d' % (
                numPedals, startIndex, endIndex, bank_id, bankflags, pedalboard_index
            )
            for i in range(startIndex, endIndex):
                initial_state_data += ' %d %d %s' % (i,
                    pedalflags|(FLAG_NAVIGATION_TRIAL_PLUGINS if pedalboards[i].get('hasTrialPlugins', False) else 0),
                    normalize_for_hw(pedalboards[i]['title'])
                )
        else:
            initial_state_data = '%d %d %d %d %d' % (
                numPedals, startIndex, endIndex, bank_id, pedalboard_index
            )
            for i in range(startIndex, endIndex):
                initial_state_data += ' %s %d' % (normalize_for_hw(pedalboards[i]['title']), i + self.pedalboard_index_offset)

        def cb_migi_pb_prgch(_):
            midi_pb_prgch = self.profile.get_midi_prgch_channel("pedalboard")
            if midi_pb_prgch >= 1 and midi_pb_prgch <= 16:
                self.send_notmodified("monitor_midi_program %d 1" % (midi_pb_prgch-1),
                                      callback, datatype='boolean')
            else:
                callback(True)

        def cb_footswitches(_):
            self.setNavigateWithFootswitches(True, cb_migi_pb_prgch)

        def cb_set_initial_state(_):
            cb = cb_footswitches if self.isBankFootswitchNavigationOn() else cb_migi_pb_prgch
            self.hmi.initial_state(initial_state_data, cb)

        if self.hmi.initialized:
            if self.descriptor.get("hmi_bank_navigation", False):
                self.setNavigateWithFootswitches(False, cb_set_initial_state)
            else:
                self.hmi.initial_state(initial_state_data, cb_migi_pb_prgch)
        else:
            cb_migi_pb_prgch(True)

    def start_session(self, callback):
        midi_pb_prgch, midi_ss_prgch = self.profile.get_midi_prgch_channels()
        if midi_pb_prgch >= 1 and midi_pb_prgch <= 16:
            self.send_notmodified("monitor_midi_program %d 0" % (midi_pb_prgch-1))

        self.web_connected = True
        self.web_data_ready_counter = 0
        self.web_data_ready_ok = True
        self.send_output_data_ready(None, None)

        self.alluserpedalboards = []
        self.userbanks = []

        if not self.hmi.initialized:
            callback(True)
            return
        if self.hmi.connected:
            callback(True)
            return

        self.hmi.connected = True
        self.ping_hmi_stop()

        def footswitch_addr2_callback(_):
            self.addressings.hmi_load_first("/hmi/footswitch2", callback)

        def footswitch_addr1_callback(_):
            self.addressings.hmi_load_first("/hmi/footswitch1", footswitch_addr2_callback)

        def footswitch_bank_callback(_):
            self.setNavigateWithFootswitches(False, footswitch_addr1_callback)

        cb = footswitch_bank_callback if self.descriptor.get("hmi_bank_navigation", False) else callback
        self.hmi.ui_con(cb)

    def end_session(self, callback):
        userpedals, baduserbundles = get_all_good_and_bad_pedalboards(kPedalboardInfoUserOnly)
        self.alluserpedalboards = userpedals
        self.userbanks = list_banks(baduserbundles, True, False)

        self.web_connected = False
        if not self.web_data_ready_ok:
            self.web_data_ready_ok = True
            self.send_output_data_ready(None, None)

        if not self.hmi.initialized:
            callback(True)
            return
        if not self.hmi.connected:
            callback(True)
            return

        def initialize_callback(_):
            self.initialize_hmi(False, callback)

        self.hmi.connected = False
        self.hmi.ui_dis(initialize_callback)

        if HMI_TIMEOUT > 0:
            self.ping_hmi_start()

    # -----------------------------------------------------------------------------------------------------------------
    # Message handling

    def process_read_message(self, msg):
        msg = msg[:-1].decode("utf-8", errors="ignore")
        if LOG >= 2 or (LOG and msg[:msg.find(' ')] not in ("data_finis","output_set")):
            logging.debug("[host] received <- %s", repr(msg))

        self.process_read_message_body(msg)
        self.process_read_queue()

    @gen.coroutine
    def process_read_message_body(self, msg):
        ioloop = IOLoop.instance()

        if msg == "data_finish":
            if self.web_connected:
                self.web_data_ready_ok = False
                self.web_data_ready_counter += 1
                self.msg_callback("data_ready %i" % self.web_data_ready_counter)
                return

            now  = ioloop.time()
            diff = now-self.last_data_finish_msg

            if diff >= 0.5:
                try:
                    yield gen.Task(self.send_output_data_ready, now)
                except Exception as e:
                    logging.exception(e)

            elif self.last_data_finish_handle is None:
                if diff < 0.2:
                    diff = 0.2
                else:
                    diff = 0.5-diff
                self.last_data_finish_handle = ioloop.call_later(diff, self.send_output_data_ready_later)

            else:
                logging.warning("[host] data_finish ignored")

            return

        cmd, data = msg.split(" ",1)

        if cmd == "param_set":
            msg_data    = data.split(" ",3)
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
                            yield gen.Task(self.preset_load_gen_helper, instance, pluginData['mapPresets'][value], False, abort_catcher)
                    except Exception as e:
                        logging.exception(e)

                else:
                    pluginData['ports'][portsymbol] = value

                    if instance_id == PEDALBOARD_INSTANCE_ID:
                        self.process_read_message_pedal_changed(portsymbol, value)

                self.pedalboard_modified = True
                self.msg_callback("param_set %s %s %f" % (instance, portsymbol, value))

        elif cmd == "output_set":
            msg_data    = data.split(" ",3)
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

        elif cmd == "patch_set":
            msg_data     = data.split(" ",3)
            instance_id  = int(msg_data[0])
            parameteruri = msg_data[1]
            valuetype    = msg_data[2]
            valuedata    = msg_data[3]

            try:
                instance   = self.mapper.get_instance(instance_id)
                pluginData = self.plugins[instance_id]
            except:
                pass
            else:
                parameter = pluginData['parameters'].get(parameteruri, None)
                if parameter is not None:
                    if valuetype == 'p' and not valuedata.startswith(USER_FILES_DIR) and os.path.islink(valuedata):
                        valuedata = os.path.realpath(valuedata)
                    parameter[0] = valuedata
                    writable = 1
                else:
                    writable = 0
                self.msg_callback("patch_set %s %d %s %s %s" % (instance, writable, parameteruri, valuetype, valuedata))

        elif cmd == "midi_mapped":
            msg_data    = data.split(" ",7)
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
            msg_data = data.split(" ", 2)
            program  = int(msg_data[0])
            channel  = int(msg_data[1])+1

            if channel == self.profile.get_midi_prgch_channel("pedalboard"):
                bank_id = self.bank_id
                if bank_id >= self.userbanks_offset and bank_id - self.userbanks_offset <= len(self.userbanks):
                    pedalboards = self.userbanks[bank_id - self.userbanks_offset]['pedalboards']
                else:
                    pedalboards = self.alluserpedalboards

                if program >= 0 and program < len(pedalboards):
                    while self.next_hmi_pedalboard_loading:
                        yield gen.sleep(0.25)
                    try:
                        yield gen.Task(self.hmi_load_bank_pedalboard, bank_id, program, from_hmi=False)
                    except Exception as e:
                        logging.exception(e)

            elif channel == self.profile.get_midi_prgch_channel("snapshot"):
                abort_catcher = self.abort_previous_loading_progress("midi_program_change")
                try:
                    yield gen.Task(self.snapshot_load_gen_helper, program, False, abort_catcher)
                except Exception as e:
                    logging.exception(e)
                else:
                    if self.descriptor.get('hmi_set_ss_name', False) and self.current_pedalboard_snapshot_id == program:
                        name = self.snapshot_name() or DEFAULT_SNAPSHOT_NAME
                        try:
                            yield gen.Task(self.hmi.set_snapshot_name, program, name)
                        except Exception as e:
                            logging.exception(e)

        elif cmd == "transport":
            msg_data = data.split(" ",3)
            rolling  = bool(int(msg_data[0]))
            bpb      = float(msg_data[1])
            bpm      = float(msg_data[2])
            speed    = 1.0 if rolling else 0.0

            rolling_changed = self.transport_rolling != rolling
            bpb_changed     = self.transport_bpb != bpb
            bpm_changed     = self.transport_bpm != bpm

            for pluginData in self.plugins.values():
                _, _2, bpb_symbol, bpm_symbol, speed_symbol = pluginData['designations']

                if bpb_symbol is not None and bpb_changed:
                    pluginData['ports'][bpb_symbol] = bpb
                    self.msg_callback("param_set %s %s %f" % (pluginData['instance'], bpb_symbol, bpb))

                if bpm_symbol is not None and bpm_changed:
                    pluginData['ports'][bpm_symbol] = bpm
                    self.msg_callback("param_set %s %s %f" % (pluginData['instance'], bpm_symbol, bpm))

                if speed_symbol is not None and rolling_changed:
                    pluginData['ports'][speed_symbol] = speed
                    self.msg_callback("param_set %s %s %f" % (pluginData['instance'], speed_symbol, speed))

            self.transport_rolling = rolling
            self.transport_bpb     = bpb
            self.transport_bpm     = bpm

            self.msg_callback("transport %i %f %f %s" % (rolling, bpb, bpm, self.transport_sync))

            if self.hmi.initialized:
                if rolling_changed:
                    self.next_hmi_play[0] = rolling
                    self.next_hmi_play[1] = self.next_hmi_play[2] = True

                if bpb_changed:
                    self.next_hmi_bpb[0] = bpb
                    self.next_hmi_bpb[1] = self.next_hmi_bpb[2] = True

                if bpm_changed:
                    self.next_hmi_bpm[0] = bpm
                    self.next_hmi_bpm[1] = self.next_hmi_bpm[2] = True

                    for actuator_uri in self.addressings.virtual_addressings:
                        addrs = self.addressings.virtual_addressings[actuator_uri]
                        for addr in addrs:
                            try:
                                yield gen.Task(self.set_param_from_bpm, addr, bpm)
                            except Exception as e:
                                logging.exception(e)

        elif cmd == "log":
            ltype, lmsg = data.split(" ", 1)
            self.msg_callback("log " + data)

            if ltype == PLUGIN_LOG_TRACE:
                logging.debug("[plugin] %s", lmsg)
            elif ltype == PLUGIN_LOG_NOTE:
                logging.info("[plugin] %s", lmsg)
            elif ltype == PLUGIN_LOG_WARNING:
                logging.warning("[plugin] %s", lmsg)
            elif ltype == PLUGIN_LOG_ERROR:
                logging.error("[plugin] %s", lmsg)

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

    def send_output_data_ready(self, now, callback):
        ioloop = IOLoop.instance()
        self.last_data_finish_msg = ioloop.time() if now is None else now

        if self.last_data_finish_handle is not None:
            ioloop.remove_timeout(self.last_data_finish_handle)
            self.last_data_finish_handle = None

        self.send_notmodified("output_data_ready", callback)

    @gen.coroutine
    def send_output_data_ready_later(self):
        yield gen.Task(self.send_output_data_ready, None)

    def process_write_queue(self):
        try:
            msg, callback, datatype = self._queue.pop(0)
            withlog = LOG >= 2 or (LOG and msg not in ("output_data_ready",))
            if withlog:
                logging.debug("[host] popped from queue: %s", msg)
        except IndexError:
            self._idle = True
            self.process_postponed_messages()
            return

        if self.writesock is None:
            self.process_write_queue()
            return

        def check_response(resp):
            if callback is not None:
                resp = resp.decode("utf-8", errors="ignore")
                if withlog:
                    logging.debug("[host] received as response <- %s", repr(resp))

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
        if withlog:
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

        if LOG >= 2:
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
        if self.swapped_audio_channels:
            disconnect_jack_ports("mod-monitor:out_1", "system:playback_2")
            disconnect_jack_ports("mod-monitor:out_2", "system:playback_1")
        else:
            disconnect_jack_ports("mod-monitor:out_1", "system:playback_1")
            disconnect_jack_ports("mod-monitor:out_2", "system:playback_2")
        disconnect_jack_ports("mod-monitor:out_1", "mod-peakmeter:in_3")
        disconnect_jack_ports("mod-monitor:out_2", "mod-peakmeter:in_4")

    def unmute(self):
        if self.swapped_audio_channels:
            connect_jack_ports("mod-monitor:out_1", "system:playback_2")
            connect_jack_ports("mod-monitor:out_2", "system:playback_1")
        else:
            connect_jack_ports("mod-monitor:out_1", "system:playback_1")
            connect_jack_ports("mod-monitor:out_2", "system:playback_2")
        connect_jack_ports("mod-monitor:out_1", "mod-peakmeter:in_3")
        connect_jack_ports("mod-monitor:out_2", "mod-peakmeter:in_4")

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
        websocket.write_message("truebypass %i %i" % (self.last_true_bypass_left, self.last_true_bypass_right))
        websocket.write_message("loading_start %d %d" % (int(self.pedalboard_empty), int(self.pedalboard_modified)))
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
            # Setup a few things as done in `init_host`, but without waiting
            midi_pb_prgch, midi_ss_prgch = self.profile.get_midi_prgch_channels()
            if midi_pb_prgch >= 1 and midi_pb_prgch <= 16:
                self.send_notmodified("monitor_midi_program %d 1" % (midi_pb_prgch-1))
            if midi_ss_prgch >= 1 and midi_ss_prgch <= 16:
                self.send_notmodified("monitor_midi_program %d 1" % (midi_ss_prgch-1))
            self.send_notmodified("state_tmpdir {}".format(PEDALBOARD_TMP_DIR))
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

        # Audio In
        for i in range(len(self.audioportsIn)):
            name  = self.audioportsIn[i]
            title = name.title().replace(" ","_")
            websocket.write_message("add_hw_port /graph/%s audio 0 %s %i" % (name, title, i+1))

        # Control Voltage In
        for i in range(len(self.cvportsIn)):
            name  = self.cvportsIn[i]
            title = name.title().replace(" ","_")
            websocket.write_message("add_hw_port /graph/%s cv 0 %s %i" % (name, title, i+1))

        # Audio Out
        for i in range(len(self.audioportsOut)):
            name  = self.audioportsOut[i]
            title = name.title().replace(" ","_")
            websocket.write_message("add_hw_port /graph/%s audio 1 %s %i" % (name, title, i+1))

        # Control Voltage Out
        for i in range(len(self.cvportsOut)):
            name  = self.cvportsOut[i]
            title = name.title().replace(" ","_")
            websocket.write_message("add_hw_port /graph/%s cv 1 %s %i" % (name, title, i+1))

        # MIDI In
        if self.midi_aggregated_mode:
            if has_midi_merger_output_port():
                websocket.write_message("add_hw_port /graph/midi_merger_out midi 0 All_MIDI_In 1")

        else:
            if self.hasSerialMidiIn:
                websocket.write_message("add_hw_port /graph/serial_midi_in midi 0 Serial_MIDI_In 0")

            ports = get_jack_hardware_ports(False, False)
            for i in range(len(ports)):
                name = ports[i]
                if name not in midiports and not name.startswith("%s:midi_" % self.jack_slave_prefix):
                    continue
                alias = get_jack_port_alias(name)

                if alias:
                    title = midi_port_alias_to_name(alias, False)
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
                    title = midi_port_alias_to_name(alias, False)
                else:
                    title = name.split(":",1)[-1].title()
                title = title.replace(" ","_")
                websocket.write_message("add_hw_port /graph/%s midi 1 %s %i" % (name.split(":",1)[-1], title, i+1))

        if self.midi_loopback_enabled:
            websocket.write_message("add_hw_port /graph/midi_loopback midi 1 MIDI_Loopback 42")

        rinstances = {
            PEDALBOARD_INSTANCE_ID: PEDALBOARD_INSTANCE
        }

        # load plugins first
        for instance_id, pluginData in self.plugins.items():
            if instance_id == PEDALBOARD_INSTANCE_ID:
                continue

            rinstances[instance_id] = pluginData['instance']

            websocket.write_message("add %s %s %.1f %.1f %d %s %d" % (pluginData['instance'], pluginData['uri'],
                                                                      pluginData['x'], pluginData['y'],
                                                                      int(pluginData['bypassed']),
                                                                      pluginData['sversion'],
                                                                      int(bool(pluginData['buildEnv']))))

            if crashed:
                self.send_notmodified("add %s %d" % (pluginData['uri'], instance_id))

        # load plugin state if relevant
        if crashed and self.pedalboard_path:
            self.send_notmodified("state_load {}".format(self.pedalboard_path))

        # now load plugin parameters and addressings
        for instance_id, pluginData in self.plugins.items():
            if instance_id == PEDALBOARD_INSTANCE_ID:
                continue

            if -1 not in pluginData['bypassCC']:
                mchnnl, mctrl = pluginData['bypassCC']
                websocket.write_message("midi_map %s :bypass %i %i 0.0 1.0" % (pluginData['instance'], mchnnl, mctrl))

            if pluginData['preset']:
                websocket.write_message("preset %s %s" % (pluginData['instance'], pluginData['preset']))

            if crashed:
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

            for paramuri, parameter in pluginData['parameters'].items():
                websocket.write_message("patch_set %s 1 %s %c %s" % (pluginData['instance'],
                                                                     paramuri,
                                                                     parameter[1],
                                                                     parameter[0]))

                if crashed:
                    self.send_notmodified("patch_set %d %s \"%s\"" % (instance_id,
                                                                      paramuri,
                                                                      str(parameter[0]).replace('"','\\"')))

            if crashed:
                for symbol, data in pluginData['midiCCs'].items():
                    mchnnl, mctrl, minimum, maximum = data
                    if -1 not in (mchnnl, mctrl):
                        self.send_notmodified("midi_map %d %s %i %i %f %f" % (instance_id, symbol,
                                                                              mchnnl, mctrl, minimum, maximum))

                for portsymbol, addressing in pluginData['addressings'].items():
                    actuator_type = self.addressings.get_actuator_type(addressing['actuator_uri'])
                    if actuator_type == Addressings.ADDRESSING_TYPE_CV:
                        source_port_name = self.get_jack_source_port_name(addressing['actuator_uri'])
                        self.send_notmodified("cv_map %d %s %s %f %f %s" % (instance_id,
                                                                            portsymbol,
                                                                            source_port_name,
                                                                            addressing['minimum'],
                                                                            addressing['maximum'],
                                                                            addressing['operational_mode']))
                    elif actuator_type == Addressings.ADDRESSING_TYPE_HMI and not addressing.get('tempo', False):
                        hw_id = self.addressings.hmi_uri2hw_map[addressing['actuator_uri']]
                        self.addressings.remap_host_hmi(hw_id, addressing)

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

    def remove_bundle(self, bundlepath, isPluginBundle, resource, callback):
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
            plugins = remove_bundle_from_lilv_world(bundlepath, resource)
            callback((True, plugins))

        self.send_notmodified("bundle_remove \"%s\" %s" % (bundlepath.replace('"','\\"'), resource or '""'),
                              host_callback, datatype='boolean')

    def refresh_bundle(self, bundlepath, plugin_uri):
        if not is_bundle_loaded(bundlepath):
            return (False, "Bundle not loaded")

        plugins = list_plugins_in_bundle(bundlepath)

        if plugin_uri not in plugins:
            return (False, "Requested plugin URI does not exist inside the bundle")

        remove_bundle_from_lilv_world(bundlepath, None)
        add_bundle_to_lilv_world(bundlepath)
        return (True, "")

    # -----------------------------------------------------------------------------------------------------------------
    # Host stuff - reset, add, remove

    def reset(self, bank_id, callback):
        def host_callback(ok):
            self.msg_callback("remove :all")
            if os.path.exists(PEDALBOARD_TMP_DIR):
                shutil.rmtree(PEDALBOARD_TMP_DIR)
            os.makedirs(PEDALBOARD_TMP_DIR)
            callback(ok)

        self.bank_id = bank_id if bank_id is not None else self.first_user_bank
        self.connections = []
        self.addressings.clear()
        self.mapper.clear()
        self.init_plugins_data()
        self.snapshot_clear()
        self.hmi_snapshots = [None, None, None]

        self.pedalboard_empty    = True
        self.pedalboard_modified = False
        self.pedalboard_name     = ""
        self.pedalboard_path     = ""
        self.pedalboard_size     = [0,0]
        self.pedalboard_version  = 0

        if bank_id is None:
            save_last_bank_and_pedalboard(0, "")

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

        # Not addressed, no need to go further
        if current_addressing is None:
            if callback is not None:
                callback(True)
            return

        actuator_uri  = current_addressing['actuator_uri']
        actuator_type = self.addressings.get_actuator_type(actuator_uri)

        # update value
        value = float(value)
        current_addressing['value'] = value

        if actuator_type == Addressings.ADDRESSING_TYPE_CC:
            if current_addressing['cctype'] & CC_MODE_OPTIONS:
                def readdress(_):
                    self.addr_task_addressing(Addressings.ADDRESSING_TYPE_CC,
                                              self.addressings.cc_metadata[actuator_uri]['hw_id'],
                                              current_addressing, callback)
                self.send_modified("cc_unmap %d %s" % (instance_id, portsymbol), readdress)
            else:
                self.send_modified("cc_value_set %d %s %f" % (instance_id, portsymbol, current_addressing['value']),
                                  callback, datatype='boolean')
            return

        if actuator_type != Addressings.ADDRESSING_TYPE_HMI or not self.hmi.initialized:
            if callback is not None:
                callback(True)
            return

        addressings       = self.addressings.hmi_addressings[actuator_uri]
        addressings_addrs = addressings['addrs']
        group_actuators   = self.addressings.get_group_actuators(actuator_uri)

        # If not currently displayed on HMI screen, then we do not need to set the new value
        if self.addressings.addressing_pages:
            if current_addressing.get('page', None) != self.addressings.current_page:
                if callback is not None:
                    callback(True)
                return
            hw_id = self.addressings.hmi_uri2hw_map[actuator_uri]
            subpage = self.addressings.hmi_hwsubpages[hw_id]
            if current_addressing.get('subpage', None) != subpage:
                if callback is not None:
                    callback(True)
                return

        elif group_actuators is None:
            current_index = addressings['idx']
            for i, addr in enumerate(addressings_addrs):
                if current_addressing['actuator_uri'] != addr['actuator_uri']:
                    continue
                if current_addressing['instance_id'] != addr['instance_id']:
                    continue
                if current_addressing['port'] != addr['port']:
                    continue
                if current_index == i:
                    break
            else:
                if callback is not None:
                    callback(True)
                return

        if current_addressing.get('tempo', False):
            valueseconds = convert_port_value_to_seconds_equivalent(current_addressing['value'],
                                                                    current_addressing['unit'])
            if valueseconds is None:
                if callback is not None:
                    callback(True)
                return

            dividers = get_divider_value(self.transport_bpm, valueseconds)
            dividers = get_nearest_valid_scalepoint_value(dividers, current_addressing['options'])[1]

            if current_addressing['dividers'] == dividers:
                if callback is not None:
                    callback(True)
                return

            current_addressing['dividers'] = dividers

            if group_actuators is not None:
                def set_2nd_group_actuators_hmi_value(ok):
                    if not ok:
                        if callback is not None:
                            callback(False)
                        return
                    hw_id2 = self.addressings.hmi_uri2hw_map[group_actuators[1]]
                    self.hmi.control_set(hw_id2, dividers, callback)

                hw_id1 = self.addressings.hmi_uri2hw_map[group_actuators[0]]
                self.hmi.control_set(hw_id1, dividers, set_2nd_group_actuators_hmi_value)

            else:
                hw_id = self.addressings.hmi_uri2hw_map[actuator_uri]
                self.hmi.control_set(hw_id, dividers, callback)
            return

        # FIXME the following code does a control_add instead of control_set in case of enums
        # Making it work on HMI with pagination could be tricky, so work around this for now
        if group_actuators is not None:
            if len(group_actuators) != 2:
                logging.error("paramhmi_set has len(group_actuators) != 2")
                if callback is not None:
                    callback(False)
                return

            def set_2nd_hmi_value(ok):
                if not ok:
                    if callback is not None:
                        callback(False)
                    return
                hw_id2 = self.addressings.hmi_uri2hw_map[group_actuators[1]]
                #self.hmi.control_set(hw_id2, float(value), callback)
                #self.hmi.control_add(current_addressing, hw_id2, group_actuators[1], callback)
                self.addressings.hmi_load_current(group_actuators[1], callback, newValue=value)

            hw_id1 = self.addressings.hmi_uri2hw_map[group_actuators[0]]
            #self.hmi.control_set(hw_id1, float(value), set_2nd_hmi_value)
            #self.hmi.control_add(current_addressing, hw_id1, group_actuators[0], set_2nd_hmi_value)
            self.addressings.hmi_load_current(group_actuators[0], set_2nd_hmi_value, newValue=value)

        else:
            hw_id = self.addressings.hmi_uri2hw_map[actuator_uri]
            if current_addressing['hmitype'] & FLAG_CONTROL_ENUMERATION:
                self.addressings.hmi_load_current(actuator_uri, callback, newValue=value)
            else:
                self.hmi.control_set(hw_id, current_addressing['value'], callback)

    def add_plugin(self, instance, uri, x, y, callback):
        instance_id = self.mapper.get_id(instance)

        def host_callback(resp):
            if resp < 0:
                callback(False)
                return
            bypassed = False

            extinfo  = get_plugin_info_essentials(uri)
            badports = []
            valports = {}
            params = {}
            ranges = {}

            enabled_symbol = None
            freewheel_symbol = None
            bpb_symbol = None
            bpm_symbol = None
            speed_symbol = None

            for port in extinfo['controlInputs']:
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

            for param in extinfo['parameters']:
                if param['ranges'] is None:
                    continue
                if param['type'] == "http://lv2plug.in/ns/ext/atom#Bool":
                    paramtype = 'b'
                elif param['type'] == "http://lv2plug.in/ns/ext/atom#Int":
                    paramtype = 'i'
                elif param['type'] == "http://lv2plug.in/ns/ext/atom#Long":
                    paramtype = 'l'
                elif param['type'] == "http://lv2plug.in/ns/ext/atom#Float":
                    paramtype = 'f'
                elif param['type'] == "http://lv2plug.in/ns/ext/atom#Double":
                    paramtype = 'g'
                elif param['type'] == "http://lv2plug.in/ns/ext/atom#String":
                    paramtype = 's'
                elif param['type'] == "http://lv2plug.in/ns/ext/atom#Path":
                    paramtype = 'p'
                elif param['type'] == "http://lv2plug.in/ns/ext/atom#URI":
                    paramtype = 'u'
                else:
                    continue
                if paramtype not in ('s','p','u') and param['ranges']['minimum'] == param['ranges']['maximum']:
                    continue
                paramuri = param['uri']
                params[paramuri] = [param['ranges']['default'], paramtype]
                ranges[paramuri] = (param['ranges']['minimum'], param['ranges']['maximum'])


            sversion = "_".join(str(v) for v in (extinfo['builder'],
                                                 extinfo['microVersion'],
                                                 extinfo['minorVersion'],
                                                 extinfo['release']))
            self.plugins[instance_id] = {
                "instance"    : instance,
                "uri"         : uri,
                "bypassed"    : bypassed,
                "bypassCC"    : (-1,-1),
                "x"           : x,
                "y"           : y,
                "addressings" : {}, # symbol: addressing
                "midiCCs"     : dict((p['symbol'], (-1,-1,0.0,1.0)) for p in extinfo['controlInputs']),
                "ports"       : valports,
                "parameters"  : params,
                "ranges"      : ranges,
                "badports"    : badports,
                "designations": (enabled_symbol, freewheel_symbol, bpb_symbol, bpm_symbol, speed_symbol),
                "outputs"     : dict((symbol, None) for symbol in extinfo['monitoredOutputs']),
                "preset"      : "",
                "mapPresets"  : [],
                "nextPreset"  : "",
                "buildEnv"    : extinfo['buildEnvironment'],
                "sversion"    : sversion,
            }

            for output in extinfo['monitoredOutputs']:
                self.send_notmodified("monitor_output %d %s" % (instance_id, output))

            for snapshot in self.pedalboard_snapshots:
                if snapshot is None:
                    continue
                if 'plugins_added' not in snapshot:
                    snapshot['plugins_added'] = [instance_id]
                else:
                    snapshot['plugins_added'].append(instance_id)

            callback(True)
            self.msg_callback("add %s %s %.1f %.1f %d %s %d" % (instance, uri, x, y,
                                                                int(bypassed),
                                                                sversion,
                                                                int(bool(extinfo['buildEnvironment']))))

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

        # Remove any addressing made to plugin's cv ports
        info = get_plugin_info(pluginData['uri'])
        if 'cv' in info['ports']:
            for port in info['ports']['cv']['output']:
                cv_port_uri = CV_OPTION + instance + '/' + port['symbol']
                try:
                    yield gen.Task(self.cv_addressing_plugin_port_remove_gen_helper, cv_port_uri)
                except Exception as e:
                    logging.exception(e)

        snapshot_instance_name = instance.replace("/graph/","",1)
        for snapshot in self.pedalboard_snapshots:
            if snapshot is None:
                continue
            if instance_id not in snapshot.get('plugins_added', []):
                continue
            snapshot['plugins_added'].remove(instance_id)
            try:
                snapshot['data'].pop(snapshot_instance_name)
            except KeyError:
                pass

        used_hmi_actuators = []
        used_hw_ids = []

        for symbol in [symbol for symbol in pluginData['addressings'].keys()]:
            addressing    = pluginData['addressings'].pop(symbol)
            actuator_uri  = addressing['actuator_uri']
            actuator_type = self.addressings.get_actuator_type(actuator_uri)
            was_active    = self.addressings.remove(addressing)
            if actuator_type == Addressings.ADDRESSING_TYPE_HMI:
                if actuator_uri not in used_hmi_actuators and was_active:
                    group_actuators = self.addressings.get_group_actuators(actuator_uri)
                    if group_actuators is not None:
                        for real_actuator_uri in group_actuators:
                            self.add_used_actuators(real_actuator_uri, used_hmi_actuators, used_hw_ids)
                    else:
                        self.add_used_actuators(actuator_uri, used_hmi_actuators, used_hw_ids)

            elif actuator_type == Addressings.ADDRESSING_TYPE_CC or actuator_type == Addressings.ADDRESSING_TYPE_CV:
                try:
                    yield gen.Task(self.addr_task_unaddressing, actuator_type,
                                                                addressing['instance_id'],
                                                                addressing['port'])
                except Exception as e:
                    logging.exception(e)

        # Send new available pages to hmi if needed
        send_hmi_available_pages = False
        if self.addressings.addressing_pages:
            for page in range(self.addressings.addressing_pages):
                send_hmi_available_pages |= self.check_available_pages(page)

        # Send everything that HMI needs
        if self.hmi.initialized:
            if send_hmi_available_pages:
                try:
                    yield gen.Task(self.hmi.set_available_pages, self.addressings.get_available_pages())
                except Exception as e:
                    logging.exception(e)

            if len(used_hw_ids) > 0:
                try:
                    yield gen.Task(self.hmi.control_rm, used_hw_ids)
                except Exception as e:
                    logging.exception(e)

            for actuator_uri in used_hmi_actuators:
                try:
                    yield gen.Task(self.addressings.hmi_load_current, actuator_uri)
                except Exception as e:
                    logging.exception(e)

        ok = yield gen.Task(self.send_modified, "remove %d" % instance_id, datatype='boolean')

        removed_connections = []
        for ports in self.connections:
            if ports[0].rsplit("/",1)[0] == instance or ports[1].rsplit("/",1)[0] == instance:
                removed_connections.append(ports)
        for ports in removed_connections:
            self.connections.remove(ports)
            self.msg_callback("disconnect %s %s" % (ports[0], ports[1]))

        self.msg_callback("remove %s" % (instance))
        callback(ok)

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
            if callback is not None:
                callback(False)
            return

        pluginData['ports'][symbol] = value
        self.send_modified("param_set %d %s %f" % (instance_id, symbol, value), callback, datatype='boolean')

    def patch_get(self, instance, paramuri, callback):
        instance_id = self.mapper.get_id_without_creating(instance)

        self.send_modified("patch_get %d %s" % (instance_id, paramuri), callback, datatype='boolean')

    def patch_set(self, instance, paramuri, value, callback):
        instance_id = self.mapper.get_id_without_creating(instance)
        pluginData  = self.plugins[instance_id]
        parameter   = pluginData['parameters'].get(paramuri, None)

        if parameter is not None:
            parameter[0] = value

        self.send_modified("patch_set %d %s \"%s\"" % (instance_id, paramuri, str(value).replace('"','\\"')),
                           callback, datatype='boolean')
        return parameter is not None

    def set_position(self, instance, x, y):
        instance_id = self.mapper.get_id_without_creating(instance)
        pluginData  = self.plugins[instance_id]

        pluginData['x'] = x
        pluginData['y'] = y

    # check if addressing is momentary or trigger, in which case we do not want to save current/changed value
    def should_save_addressing_value(self, addressing, value):
        if addressing is None:
            return True

        cctype = addressing.get('cctype', 0x0)
        hmitype = addressing.get('hmitype', 0x0)

        # do not save triggers, their value is reset on the next audio cycle
        if (hmitype & FLAG_CONTROL_TRIGGER) or (cctype & CC_MODE_TRIGGER):
            return False

        # do not save momentary toggles with their current value being the temporary one
        if (hmitype & FLAG_CONTROL_MOMENTARY) or (cctype & CC_MODE_MOMENTARY):
            if addressing['port'] == ":bypass":
                m1v = addressing['minimum']
                m2v = addressing['maximum']
            else:
                m1v = addressing['maximum']
                m2v = addressing['minimum']

            if addressing['momentary'] == 1 and m1v == value:
                return False
            if addressing['momentary'] == 2 and m2v == value:
                return False

        # fallback is true
        return True

    def reload_pedalboard(self, affected_uris):
        # Reload pedalboard if any effect in affected_uris is in use
        # Reloading works by saving and loading current pedalboard to a tmp path
        running_uris = dict([ (p['uri'], 1) for p in self.plugins.values() ])
        affected = False
        for uri in affected_uris:
            if running_uris.get(uri.decode()):
                affected = True
                break
        if not affected:
            return
        bundlepath = '/tmp/reloaded.pedalboard'
        if os.path.exists(bundlepath):
            shutil.rmtree(bundlepath)
        os.mkdir(bundlepath)
        self.save_state_to_ttl(bundlepath, self.pedalboard_name, 'tmp')
        def load(ok):
            if ok:
                self.load(bundlepath)
            shutil.rmtree(bundlepath)
        self.reset(None, load)

    # -----------------------------------------------------------------------------------------------------------------
    # Host stuff - plugin presets

    # helper function for gen.Task, which has troubles calling into a coroutine directly
    def preset_load_gen_helper(self, instance, uri, from_hmi, abort_catcher, callback):
        self.preset_load(instance, uri, from_hmi, abort_catcher, callback)

    @gen.coroutine
    def preset_load(self, instance, uri, from_hmi, abort_catcher, callback):
        instance_id = self.mapper.get_id_without_creating(instance)
        current_pedal = self.pedalboard_path
        pluginData = self.plugins[instance_id]
        pluginData['nextPreset'] = uri

        try:
            ok = yield gen.Task(self.send_modified, "preset_load %d %s" % (instance_id, uri), datatype='boolean')
        except Exception as e:
            callback(False)
            logging.exception(e)
            return

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

        try:
            state = yield gen.Task(self.send_notmodified, "preset_show %s" % uri, datatype='string')
        except Exception as e:
            callback(False)
            logging.exception(e)
            return

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

        try:
            yield gen.Task(self.addressings.load_current_with_callback, used_actuators, (instance_id, ":presets"), True, from_hmi, abort_catcher)
        except Exception as e:
            callback(False)
            logging.exception(e)
            return

        callback(True)

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

    def preset_save_replace(self, instance, olduri, presetbundle, name, callback):
        instance_id = self.mapper.get_id_without_creating(instance)
        pluginData  = self.plugins[instance_id]

        if pluginData['preset'] != olduri or not os.path.exists(presetbundle):
            callback({
                'ok': False,
            })
            return

        plugin_uri   = pluginData['uri']
        symbolname   = symbolify(name)[:32]

        def add_bundle_callback(ok):
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
            self.add_bundle(presetbundle, add_bundle_callback)

        def start(_):
            shutil.rmtree(presetbundle)
            rescan_plugin_presets(plugin_uri)
            pluginData['preset'] = ""
            self.send_notmodified("preset_save %d \"%s\" %s %s.ttl" % (instance_id,
                                                                       name.replace('"','\\"'),
                                                                       presetbundle,
                                                                       symbolname), host_callback, datatype='boolean')

        self.remove_bundle(presetbundle, False, olduri, start)

    def preset_delete(self, instance, uri, bundlepath, callback):
        instance_id = self.mapper.get_id_without_creating(instance)
        pluginData  = self.plugins[instance_id]
        plugin_uri  = pluginData['uri']

        if pluginData['preset'] != uri or not os.path.exists(bundlepath):
            callback(False)
            return

        def start(_):
            shutil.rmtree(bundlepath)
            rescan_plugin_presets(plugin_uri)
            pluginData['preset'] = ""
            self.msg_callback("preset %s null" % instance)
            callback(True)

        self.remove_bundle(bundlepath, False, uri, start)

    # -----------------------------------------------------------------------------------------------------------------
    # Host stuff - pedalboard snapshots

    def _snapshot_unique_name(self, name):
        names = tuple(pbss['name'] for pbss in self.pedalboard_snapshots)
        return get_unique_name(name, names) or name

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
                "bypassed"  : pluginData['bypassed'],
                "parameters": dict((k,v.copy()) for k,v in pluginData['parameters'].items()),
                "ports"     : pluginData['ports'].copy(),
                "preset"    : pluginData['preset'],
            }

        return snapshot

    def snapshot_name(self, idx = None):
        if idx is None:
            idx = self.current_pedalboard_snapshot_id
        if idx < 0 or idx >= len(self.pedalboard_snapshots) or self.pedalboard_snapshots[idx] is None:
            return None
        return self.pedalboard_snapshots[idx]['name']

    def snapshot_clear(self):
        self.current_pedalboard_snapshot_id = 0
        self.pedalboard_snapshots = [self.snapshot_make(DEFAULT_SNAPSHOT_NAME)]

    def snapshot_save(self):
        idx = self.current_pedalboard_snapshot_id

        if idx < 0 or idx >= len(self.pedalboard_snapshots) or self.pedalboard_snapshots[idx] is None:
            return False

        name     = self.pedalboard_snapshots[idx]['name']
        snapshot = self.snapshot_make(name)
        self.pedalboard_snapshots[idx] = snapshot
        return True

    def snapshot_saveas(self, name):
        snapshot = self.snapshot_make(self._snapshot_unique_name(name))
        self.pedalboard_snapshots.append(snapshot)
        self.current_pedalboard_snapshot_id = len(self.pedalboard_snapshots)-1
        return self.current_pedalboard_snapshot_id

    def snapshot_rename(self, idx, name):
        if idx < 0 or idx >= len(self.pedalboard_snapshots) or self.pedalboard_snapshots[idx] is None:
            return False

        if self.pedalboard_snapshots[idx]['name'] == name:
            return True

        self.pedalboard_modified = True
        self.pedalboard_snapshots[idx]['name'] = self._snapshot_unique_name(name)
        return True

    def snapshot_remove(self, idx):
        if idx < 0 or idx >= len(self.pedalboard_snapshots) or self.pedalboard_snapshots[idx] is None:
            return False
        if len(self.pedalboard_snapshots) == 1:
            return False

        snapshot_to_remove = self.pedalboard_snapshots[idx]
        self.pedalboard_modified = True
        self.pedalboard_snapshots.remove(snapshot_to_remove)

        if self.current_pedalboard_snapshot_id == idx:
            self.current_pedalboard_snapshot_id = -1

        return True

    # helper function for gen.Task, which has troubles calling into a coroutine directly
    def snapshot_load_gen_helper(self, idx, from_hmi, abort_catcher, callback):
        self.snapshot_load(idx, from_hmi, abort_catcher, callback)

    @gen.coroutine
    def snapshot_load(self, idx, from_hmi, abort_catcher, callback):
        if idx in (self.HMI_SNAPSHOTS_1, self.HMI_SNAPSHOTS_2, self.HMI_SNAPSHOTS_3):
            idx = abs(idx + self.HMI_SNAPSHOTS_OFFSET)
            snapshot = self.hmi_snapshots[idx]
            is_hmi_snapshot = True

            if snapshot is None:
                print("ERROR: Asked to load an invalid HMI preset, number", idx)
                callback(False)
                return

        else:
            if idx < 0 or idx >= len(self.pedalboard_snapshots):
                callback(False)
                return

            snapshot = self.pedalboard_snapshots[idx]
            is_hmi_snapshot = False

            if snapshot is None:
                print("ERROR: Asked to load an invalid pedalboard snapshot, number", idx)
                callback(False)
                return

            self.current_pedalboard_snapshot_id = idx
            self.plugins[PEDALBOARD_INSTANCE_ID]['preset'] = "file:///%i" % idx

        was_aborted = self.addressings.was_last_load_current_aborted()
        used_actuators = []

        for instance, data in snapshot['data'].items():
            if abort_catcher.get('abort', False):
                print("WARNING: Abort triggered during snapshot_load request, caller:", abort_catcher['caller'])
                callback(False)
                return

            instance = "/graph/%s" % instance

            try:
                instance_id = self.mapper.get_id_without_creating(instance)
                pluginData = self.plugins[instance_id]
            except KeyError:
                continue

            addressing = pluginData['addressings'].get(":bypass", None)
            diffBypass = (self.should_save_addressing_value(addressing, pluginData['bypassed']) and
                          pluginData['bypassed'] != data['bypassed'])
            diffPreset = data['preset'] and data['preset'] != pluginData['preset']

            if was_aborted or diffBypass:
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

            if was_aborted or diffPreset:
                try:
                    index = pluginData['mapPresets'].index(data['preset'])
                except ValueError:
                    pass
                else:
                    if diffPreset:
                        self.msg_callback("preset %s %s" % (instance, data['preset']))
                        try:
                            yield gen.Task(self.preset_load_gen_helper, instance, data['preset'], from_hmi, abort_catcher)
                        except Exception as e:
                            logging.exception(e)

                    addressing = pluginData['addressings'].get(":presets", None)
                    if addressing is not None:
                        addressing['value'] = index
                        if addressing['actuator_uri'] not in used_actuators:
                            used_actuators.append(addressing['actuator_uri'])

                            group_actuators = self.addressings.get_group_actuators(addressing['actuator_uri'])
                            if group_actuators is not None:
                                for actuator_uri in group_actuators:
                                    if actuator_uri not in used_actuators:
                                        used_actuators.append(actuator_uri)

            for symbol, value in data['ports'].items():
                if symbol in pluginData['designations']:
                    continue

                addressing = pluginData['addressings'].get(symbol, None)

                if not self.should_save_addressing_value(addressing, value):
                    continue

                equal = pluginData['ports'].get(symbol, None) in (value, None)

                if equal and not was_aborted and not diffPreset:
                    continue

                if not equal or diffPreset:
                    self.msg_callback("param_set %s %s %f" % (instance, symbol, value))
                    try:
                        yield gen.Task(self.param_set, "%s/%s" % (instance, symbol), value)
                    except Exception as e:
                        logging.exception(e)

                if addressing is not None:
                    addressing['value'] = value
                    if addressing['actuator_uri'] not in used_actuators:
                        used_actuators.append(addressing['actuator_uri'])

                        group_actuators = self.addressings.get_group_actuators(addressing['actuator_uri'])
                        if group_actuators is not None:
                            for actuator_uri in group_actuators:
                                if actuator_uri not in used_actuators:
                                    used_actuators.append(actuator_uri)

            for uri, param in data.get('parameters', {}).items():
                if pluginData['parameters'].get(uri, None) in (param, None):
                    continue
                self.msg_callback("patch_set %s 1 %s %s %s" % (instance, uri, param[1], param[0]))
                try:
                    yield gen.Task(self.patch_set, instance, uri, param[0])
                except Exception as e:
                    logging.exception(e)

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

        self.addressings.load_current(used_actuators, skippedPort, True, from_hmi, abort_catcher)

        if not is_hmi_snapshot:
            name = self.snapshot_name() or DEFAULT_SNAPSHOT_NAME
            self.msg_callback("pedal_snapshot %d %s" % (idx, name))

            if not from_hmi:
                try:
                    yield gen.Task(self.paramhmi_set, 'pedalboard', ":presets", idx)
                except Exception as e:
                    logging.exception(e)

            if self.descriptor.get('hmi_set_ss_name', False):
                if from_hmi:
                    self.hmi.set_snapshot_name(self.current_pedalboard_snapshot_id, name, None)
                else:
                    try:
                        yield gen.Task(self.hmi.set_snapshot_name, self.current_pedalboard_snapshot_id, name)
                    except Exception as e:
                        logging.exception(e)

        # callback must be last action
        callback(True)

    @gen.coroutine
    def page_load(self, idx, abort_catcher, callback):
        if not self.addressings.addressing_pages:
            print("ERROR: hmi next page not supported")
            callback(False)
            return

        # If a pedalboard is loading (via MIDI program messsage), wait for it to finish
        while self.next_hmi_pedalboard_to_load is not None:
            yield gen.sleep(0.25)

        if self.addressings.has_hmi_subpages:
            # Move all subpages to 0
            subpage = 0
            for hw_id in self.addressings.hmi_hwsubpages:
                self.addressings.hmi_hwsubpages[hw_id] = 0
        else:
            subpage = None

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

            page_to_load_assigned = self.addressings.is_page_assigned(addrs, idx, subpage)

            # Nothing assigned to current actuator on page to load
            if not page_to_load_assigned:
                continue

            # Else, send control_add with new data
            try:
                next_addressing_data = self.addressings.get_addressing_for_page(addrs, idx, subpage)
            except StopIteration:
                continue

            next_addressing_data['value'] = self.addr_task_get_port_value(next_addressing_data['instance_id'],
                                                                          next_addressing_data['port'])

            # NOTE: ignoring callback here, as HMI is handling a request right now
            self.hmi.control_add(next_addressing_data, hw_id, uri, None)

        self.addressings.current_page = idx % self.addressings.addressing_pages

        # callback must be last action
        callback(True)

    # -----------------------------------------------------------------------------------------------------------------
    # Host stuff - connections

    def _fix_host_connection_port(self, port):
        """Map URL style port names to Jack port names."""
        data = port.split("/")
        # For example, "/graph/capture_2" becomes ['', 'graph', 'capture_2'].
        # Plugin paths can be longer, e.g.  ['', 'graph', 'BBCstereo', 'inR']

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
            if data[2] == "midi_loopback":
                return self.midi_loopback_port
            if data[2].startswith("playback_"):
                num = data[2].replace("playback_","",1)
                monitorportnums = ("1","2","3","4") if has_duox_split_spdif() else ("1","2")
                if num in monitorportnums:
                    return "mod-monitor:in_" + num

            if data[2].startswith(("audio_from_slave_",
                                   "audio_to_slave_",
                                   "midi_from_slave_",
                                   "midi_to_slave_")):
                return "%s:%s" % (self.jack_slave_prefix, data[2])

            if data[2].startswith("USB_Audio_Capture_"):
                return "%s:%s" % (self.jack_usbgadget_prefix+"c", data[2])

            if data[2].startswith("USB_Audio_Playback_"):
                return "%s:%s" % (self.jack_usbgadget_prefix+"p", data[2])

            if data[2].startswith("nooice_capture_"):
                num = data[2].replace("nooice_capture_","",1)
                return "nooice%s:nooice_capture_%s" % (num, num)

            # Handle fake input
            if data[2].startswith("fake_capture_"):
                num = data[2].replace("fake_capture_", "", 1)
                return "fake-input:fake_capture_{0}".format(num)

            # Handle the Control Voltage ports
            if data[2].startswith("cv_capture_"):
                num = data[2].replace("cv_capture_", "", 1)
                return "mod-spi2jack:capture_{0}".format(num)
            if data[2].startswith("cv_playback_"):
                num = data[2].replace("cv_playback_", "", 1)
                return "mod-jack2spi:playback_{0}".format(num)
            if data[2] == "cv_exp_pedal":
                return "mod-spi2jack:exp_pedal"

            # Handle global input (for noisegate control)
            if data[2] == "capture_1":
                return self.jack_hw_capture_prefix + "1"
            if data[2] == "capture_2":
                return self.jack_hw_capture_prefix + "2"

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

    def load(self, bundlepath, isDefault=False, abort_catcher=None):
        first_pedalboard = self.first_pedalboard
        self.first_pedalboard = False

        try:
            pb = get_pedalboard_info(bundlepath)
        except:
            self.bank_id = self.first_user_bank
            try:
                bundlepath = DEFAULT_PEDALBOARD
                isDefault = True
                pb = get_pedalboard_info(bundlepath)
            except:
                bundlepath = ""
                pb = {
                    'title': "",
                    'width': 0,
                    'height': 0,
                    'midi_separated_mode': False,
                    'midi_loopback': False,
                    'connections': [],
                    'plugins': [],
                    'timeInfo': {
                        'available': False,
                    },
                    'version': 0,
                }

        if bundlepath == DEFAULT_PEDALBOARD:
            pb['title'] = "" if isDefault else "Default"

        self.msg_callback("loading_start %i 0" % int(isDefault))
        self.msg_callback("size %d %d" % (pb['width'],pb['height']))

        midi_aggregated_mode = not pb.get('midi_separated_mode', True)
        midi_loopback = pb.get('midi_loopback', False)

        if self.midi_aggregated_mode != midi_aggregated_mode:
            self.send_notmodified("feature_enable aggregated-midi {}".format(int(midi_aggregated_mode)))
            self.set_midi_devices_change_mode(midi_aggregated_mode)

        if self.midi_loopback_enabled != midi_loopback:
            self.set_midi_devices_loopback_enabled(midi_loopback)

        if not self.midi_aggregated_mode:
            # MIDI Devices might change port names at anytime
            # To properly restore MIDI HW connections we need to map the "old" port names (from project)
            mappedOldMidiIns   = dict((p['symbol'], p['name']) for p in pb['hardware']['midi_ins'])
            mappedOldMidiOuts  = dict((p['symbol'], p['name']) for p in pb['hardware']['midi_outs'])
            mappedOldMidiOuts2 = dict((p['name'], p['symbol']) for p in pb['hardware']['midi_outs'])
            mappedNewMidiIns   = OrderedDict((midi_port_alias_to_name(get_jack_port_alias(p), True),
                                            p.split(":",1)[-1]) for p in get_jack_hardware_ports(False, False))
            mappedNewMidiOuts  = OrderedDict((midi_port_alias_to_name(get_jack_port_alias(p), True),
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

        timeAvailable = pb['timeInfo']['available'] if first_pedalboard or self.transport_sync == "none" else 0

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
                self.set_transport_bpb(pb['timeInfo']['bpb'], False, True, False, False)

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
                self.set_transport_bpm(pb['timeInfo']['bpm'], False, True, False, False)

            if timeAvailable & kPedalboardTimeAvailableRolling:
                ccData = pb['timeInfo']['rollingCC']
                if ccData['channel'] >= 0 and ccData['channel'] < 16:
                    pluginData['midiCCs'][':rolling'] = (ccData['channel'], ccData['control'], 0.0, 1.0)
                    pluginData['addressings'][':rolling'] = self.addressings.add_midi(PEDALBOARD_INSTANCE_ID,
                                                                                      ':rolling',
                                                                                      ccData['channel'],
                                                                                      ccData['control'],
                                                                                      0.0, 1.0)
                self.set_transport_rolling(pb['timeInfo']['rolling'], False, True, False, False)

        else: # time not available
            self.set_transport_bpb(self.transport_bpb, False, True, False, False)
            self.set_transport_bpm(self.transport_bpm, False, True, False, False)
            self.set_transport_rolling(self.transport_rolling, False, True, False, False)

        if abort_catcher is not None and abort_catcher.get('abort', False):
            print("WARNING: Abort triggered during PB load request 1, caller:", abort_catcher['caller'])
            return

        self.send_notmodified("transport %i %f %f" % (self.transport_rolling,
                                                      self.transport_bpb,
                                                      self.transport_bpm))

        self.msg_callback("transport %i %f %f %s" % (self.transport_rolling,
                                                     self.transport_bpb,
                                                     self.transport_bpm,
                                                     self.transport_sync))

        if bundlepath:
            motos = self.addressings.peek_for_momentary_toggles(bundlepath)
        else:
            motos = {}

        self.load_pb_plugins(pb['plugins'], instances, rinstances, motos)
        self.load_pb_connections(pb['connections'], mappedOldMidiIns, mappedOldMidiOuts,
                                                    mappedNewMidiIns, mappedNewMidiOuts)

        if bundlepath:
            self.load_pb_snapshots(bundlepath)
            self.send_notmodified("state_load {}".format(bundlepath))
            self.addressings.load(bundlepath, instances, skippedPortAddressings, abort_catcher)

        if abort_catcher is not None and abort_catcher.get('abort', False):
            print("WARNING: Abort triggered during PB load request 2, caller:", abort_catcher['caller'])
            return

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

            if bundlepath and (bundlepath.startswith(LV2_PEDALBOARDS_DIR) or
                               bundlepath.startswith(LV2_FACTORY_PEDALBOARDS_DIR)):
                save_last_bank_and_pedalboard(self.bank_id, bundlepath)
            else:
                save_last_bank_and_pedalboard(0, "")

            os.sync()

        return self.pedalboard_name

    def load_pb_snapshots(self, bundlepath):
        if os.path.exists(os.path.join(bundlepath, "snapshots.json")):
            # New file with correct name, loads as dict
            data = safe_json_load(os.path.join(bundlepath, "snapshots.json"), dict)
            self.pedalboard_snapshots = data.get('snapshots', [])
            try:
                current = int(data.get('current', 0))
                if current < -1:
                    raise ValueError
                if current >= len(self.pedalboard_snapshots):
                    raise ValueError
            except:
                current = 0
            self.current_pedalboard_snapshot_id = current
        else:
            # Old backwards compatible file, loads as list
            self.pedalboard_snapshots = safe_json_load(os.path.join(bundlepath, "presets.json"), list)
            self.current_pedalboard_snapshot_id = 0

        if self.pedalboard_snapshots:
            # make sure names are unique
            names = []
            for pbss in self.pedalboard_snapshots:
                nname = get_unique_name(pbss['name'], names)
                if nname is not None:
                    pbss['name'] = nname
                names.append(pbss['name'])
        else:
            self.snapshot_clear()

    def load_pb_plugins(self, plugins, instances, rinstances, motos):
        for p in plugins:
            extinfo = get_plugin_info_essentials(p['uri'])

            if 'error' in extinfo and extinfo['error']:
                continue

            instance    = "/graph/%s" % p['instance']
            instance_id = self.mapper.get_id_by_number(instance, p['instanceNumber'])

            instances[p['instance']] = (instance_id, p['uri'])
            rinstances[instance_id]  = instance

            badports = []
            valports = {}
            params = {}
            ranges = {}

            enabled_symbol = None
            freewheel_symbol = None
            bpb_symbol = None
            bpm_symbol = None
            speed_symbol = None

            for port in extinfo['controlInputs']:
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

            for param in extinfo['parameters']:
                if param['ranges'] is None:
                    continue
                if param['type'] == "http://lv2plug.in/ns/ext/atom#Bool":
                    paramtype = 'b'
                elif param['type'] == "http://lv2plug.in/ns/ext/atom#Int":
                    paramtype = 'i'
                elif param['type'] == "http://lv2plug.in/ns/ext/atom#Long":
                    paramtype = 'l'
                elif param['type'] == "http://lv2plug.in/ns/ext/atom#Float":
                    paramtype = 'f'
                elif param['type'] == "http://lv2plug.in/ns/ext/atom#Double":
                    paramtype = 'g'
                elif param['type'] == "http://lv2plug.in/ns/ext/atom#String":
                    paramtype = 's'
                elif param['type'] == "http://lv2plug.in/ns/ext/atom#Path":
                    paramtype = 'p'
                elif param['type'] == "http://lv2plug.in/ns/ext/atom#URI":
                    paramtype = 'u'
                else:
                    continue
                if paramtype not in ('s','p','u') and param['ranges']['minimum'] == param['ranges']['maximum']:
                    continue
                paramuri = param['uri']
                params[paramuri] = [param['ranges']['default'], paramtype]
                ranges[paramuri] = (param['ranges']['minimum'], param['ranges']['maximum'])

            # make sure preset is valid
            if p['preset'] and not is_plugin_preset_valid(p['uri'], p['preset']):
                print("WARNING: preset '%s' was not valid" % p['preset'])
                p['preset'] = ""

            self.plugins[instance_id] = pluginData = {
                "instance"    : instance,
                "uri"         : p['uri'],
                "bypassed"    : p['bypassed'],
                "bypassCC"    : (p['bypassCC']['channel'], p['bypassCC']['control']),
                "x"           : p['x'],
                "y"           : p['y'],
                "addressings" : {}, # symbol: addressing
                "midiCCs"     : dict((p['symbol'], (-1,-1,0.0,1.0)) for p in extinfo['controlInputs']),
                "ports"       : valports,
                "parameters"  : params,
                "ranges"      : ranges,
                "badports"    : badports,
                "designations": (enabled_symbol, freewheel_symbol, bpb_symbol, bpm_symbol, speed_symbol),
                "outputs"     : dict((symbol, None) for symbol in extinfo['monitoredOutputs']),
                "preset"      : p['preset'],
                "mapPresets"  : [],
                "nextPreset"  : "",
                "buildEnv"    : extinfo['buildEnvironment'],
                "sversion"    : "_".join(str(v) for v in (extinfo['builder'],
                                                          extinfo['microVersion'],
                                                          extinfo['minorVersion'],
                                                          extinfo['release'])),
            }

            self.send_notmodified("add %s %d" % (p['uri'], instance_id))

            if p['bypassed']:
                self.send_notmodified("bypass %d 1" % (instance_id,))

            self.msg_callback("add %s %s %.1f %.1f %d %s %d" % (instance,
                                                                p['uri'], p['x'], p['y'],
                                                                int(p['bypassed']),
                                                                pluginData['sversion'],
                                                                int(bool(extinfo['buildEnvironment']))))

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

                oldValue = pluginData['ports'].get(symbol, None)

                if oldValue is None:
                    continue

                if instance in motos:
                    for motoSymbol, motoValue in motos[instance].items():
                        if motoSymbol == symbol:
                            value = motoValue
                            break

                if oldValue != value:
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

            for output in extinfo['monitoredOutputs']:
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

    def save(self, title, asNew, callback):
        # Save over existing bundlepath
        if self.pedalboard_path and not asNew and \
            os.path.isdir(self.pedalboard_path) and self.pedalboard_path.startswith(LV2_PEDALBOARDS_DIR):
            bundlepath = self.pedalboard_path
            titlesym = symbolify(title)[:16]
            newTitle = None

        # Save new
        else:
            # ensure unique title
            newTitle = title = get_unique_name(title, get_all_user_pedalboard_names()) or title
            titlesym = symbolify(title)[:16]

            # Special handling for saving factory pedalboards
            if self.pedalboard_path and self.pedalboard_path.startswith(LV2_FACTORY_PEDALBOARDS_DIR) and not asNew:
                trypath = os.path.join(LV2_PEDALBOARDS_DIR, os.path.basename(self.pedalboard_path))
            else:
                trypath = os.path.join(LV2_PEDALBOARDS_DIR, "%s.pedalboard" % titlesym)

            # if trypath already exists, generate a random bundlepath based on title
            if os.path.exists(trypath):
                while True:
                    trypath = os.path.join(LV2_PEDALBOARDS_DIR, "%s-%i.pedalboard" % (titlesym, randint(1,99999)))
                    if os.path.exists(trypath):
                        continue
                    bundlepath = trypath
                    break

            # trypath doesn't exist yet, use it
            else:
                bundlepath = trypath

                # just in case..
                if not os.path.exists(LV2_PEDALBOARDS_DIR):
                    os.mkdir(LV2_PEDALBOARDS_DIR)

            # create bundle path
            os.mkdir(bundlepath)
            self.pedalboard_path = bundlepath

        # save ttl
        self.pedalboard_name     = title
        self.pedalboard_empty    = False
        self.pedalboard_modified = False
        self.save_state_to_ttl(bundlepath, title, titlesym)
        save_last_bank_and_pedalboard(0, bundlepath)

        def state_saved_cb(ok):
            os.sync()
            callback(True)

        # ask host to save any needed extra state
        self.send_notmodified("state_save {}".format(bundlepath), state_saved_cb, datatype='boolean')

        return bundlepath, newTitle

    def save_state_to_ttl(self, bundlepath, title, titlesym):
        self.save_state_manifest(bundlepath, titlesym)
        self.save_state_addressings(bundlepath)
        self.save_state_snapshots(bundlepath)
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

    def save_state_snapshots(self, bundlepath):
        for snapshot in self.pedalboard_snapshots:
            if snapshot is None:
                continue
            if 'plugins_added' not in snapshot:
                continue
            for instance_id in snapshot.pop('plugins_added'):
                pluginData = self.plugins[instance_id]
                instance   = pluginData['instance'].replace("/graph/","",1)
                snapshot['data'][instance] = {
                    "bypassed"  : pluginData['bypassed'],
                    "parameters": dict((k,v.copy()) for k,v in pluginData['parameters'].items()),
                    "ports"     : pluginData['ports'].copy(),
                    "preset"    : pluginData['preset'],
                }

        data = {
            'current': self.current_pedalboard_snapshot_id,
            'snapshots': [p for p in self.pedalboard_snapshots if p is not None],
        }

        with TextFileFlusher(os.path.join(bundlepath, "snapshots.json")) as fh:
            json.dump(data, fh, indent=4)

        # delete old file if present
        if os.path.exists(os.path.join(bundlepath, "presets.json")):
            os.remove(os.path.join(bundlepath, "presets.json"))

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
    pedal:instanceNumber %i ;
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
       pluginData['uri'], instance_id, pluginData['preset'])

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

        # Ports (CV In)
        for port in self.cvportsIn:
            index += 1
            ports += """
<%s>
    lv2:index %i ;
    lv2:name "%s" ;
    lv2:portProperty lv2:connectionOptional ;
    lv2:symbol "%s" ;
    a lv2:CVPort ,
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

        # Ports (CV Out)
        for port in self.cvportsOut:
            index += 1
            ports += """
<%s>
    lv2:index %i ;
    lv2:name "%s" ;
    lv2:portProperty lv2:connectionOptional ;
    lv2:symbol "%s" ;
    a lv2:CVPort ,
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
<midi_separated_mode>
    ingen:value %i ;
    lv2:index %i ;
    a atom:AtomPort ,
        lv2:InputPort .
""" % (int(not self.midi_aggregated_mode), index)

        # MIDI Loopback
        index += 1
        ports += """
<midi_loopback>
    ingen:value %i ;
    lv2:index %i ;
    a atom:AtomPort ,
        lv2:InputPort .
""" % (int(self.midi_loopback_enabled), index)

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
       MODEL_TYPE,
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
        portsyms = [":bpb",":bpm",":rolling","midi_separated_mode","midi_loopback","control_in","control_out"]
        if self.hasSerialMidiIn:
            portsyms.append("serial_midi_in")
        if self.hasSerialMidiOut:
            portsyms.append("serial_midi_out")
        portsyms += [p.replace("system:","",1) for p in midiportsIn ]
        portsyms += [p.replace("system:","",1) for p in midiportsOut]
        portsyms += self.audioportsIn+self.cvportsIn+self.audioportsOut+self.cvportsOut
        pbdata += "    lv2:port <%s> ;\n" % ("> ,\n             <".join(portsyms))

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
            if callback is not None:
                callback(False)
            return

        # compute new port value based on new bpm
        port_value = get_port_value(bpm, addr['dividers'], addr['unit'])
        if addr['unit'] != 'BPM': # convert back into port unit if needed
            port_value = convert_seconds_to_port_value_equivalent(port_value, addr['unit'])

        instance_id = addr['instance_id']
        portsymbol  = addr['port']
        instance    = self.mapper.get_instance(instance_id)
        pluginData  = self.plugins.get(instance_id, None)
        if pluginData is None:
            if callback is not None:
                callback(False)
            return

        self.host_and_web_parameter_set(pluginData, instance, instance_id, port_value, portsymbol, callback)

    def set_sync_mode(self, mode, sendHMI, sendWeb, setProfile, callback):
        if setProfile:
            self.profile.set_sync_mode(mode)

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
                self.hmi.set_profile_value(MENU_ID_MIDI_CLK_SOURCE, self.profile.get_transport_source(), callback)
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
            self.unaddress(PEDALBOARD_INSTANCE, ":bpm", True, unaddress_bpm_callback)
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
                yield gen.Task(self.hmi.set_profile_value, MENU_ID_MIDI_CLK_SOURCE, Profile.TRANSPORT_SOURCE_ABLETON_LINK)
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
                yield gen.Task(self.hmi.set_profile_value, MENU_ID_MIDI_CLK_SOURCE, Profile.TRANSPORT_SOURCE_MIDI_SLAVE)
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
                yield gen.Task(self.hmi.set_profile_value, MENU_ID_MIDI_CLK_SOURCE, Profile.TRANSPORT_SOURCE_INTERNAL)
            except Exception as e:
                logging.exception(e)

    @gen.coroutine
    def set_transport_bpb(self, bpb, sendHost, sendHMI, sendWeb, sendHMIAddressing, callback=None, datatype='int'):
        self.transport_bpb = bpb
        self.profile.set_tempo_bpb(bpb)

        for pluginData in self.plugins.values():
            bpb_symbol = pluginData['designations'][self.DESIGNATIONS_INDEX_BPB]

            if bpb_symbol is not None:
                pluginData['ports'][bpb_symbol] = bpb
                if sendHost:
                    self.msg_callback("param_set %s %s %f" % (pluginData['instance'], bpb_symbol, bpb))

        # Changing HMI state from here is very problematic, we deal with this later
        if self.hmi.initialized and (sendHMI or sendHMIAddressing):
            self.next_hmi_bpb[0] = bpb
            if sendHMI:
                self.next_hmi_bpb[1] = True
            if sendHMIAddressing:
                self.next_hmi_bpb[2] = True

        if sendWeb:
            self.msg_callback("transport %i %f %f %s" % (self.transport_rolling,
                                                         self.transport_bpb,
                                                         self.transport_bpm,
                                                         self.transport_sync))

        if sendHost:
            self.send_modified("transport %i %f %f" % (self.transport_rolling,
                                                       self.transport_bpb,
                                                       self.transport_bpm), callback, datatype)

    @gen.coroutine
    def set_transport_bpm(self, bpm, sendHost, sendHMI, sendWeb, sendHMIAddressing, callback=None, datatype='int'):
        self.transport_bpm = bpm
        self.profile.set_tempo_bpm(bpm)

        for pluginData in self.plugins.values():
            bpm_symbol = pluginData['designations'][self.DESIGNATIONS_INDEX_BPM]

            if bpm_symbol is not None:
                pluginData['ports'][bpm_symbol] = bpm
                if sendHost:
                    self.msg_callback("param_set %s %s %f" % (pluginData['instance'], bpm_symbol, bpm))

        for actuator_uri in self.addressings.virtual_addressings:
            addrs = self.addressings.virtual_addressings[actuator_uri]
            for addr in addrs:
                try:
                    yield gen.Task(self.set_param_from_bpm, addr, bpm)
                except Exception as e:
                    logging.exception(e)

        # Changing HMI state from here is very problematic, we deal with this later
        if self.hmi.initialized and (sendHMI or sendHMIAddressing):
            self.next_hmi_bpm[0] = bpm
            if sendHMI:
                self.next_hmi_bpm[1] = True
            if sendHMIAddressing:
                self.next_hmi_bpm[2] = True

        if sendWeb:
            self.msg_callback("transport %i %f %f %s" % (self.transport_rolling,
                                                         self.transport_bpb,
                                                         self.transport_bpm,
                                                         self.transport_sync))

        if sendHost:
            self.send_modified("transport %i %f %f" % (self.transport_rolling,
                                                       self.transport_bpb,
                                                       self.transport_bpm), callback, datatype)

    @gen.coroutine
    def set_transport_rolling(self, rolling, sendHost, sendHMI, sendWeb, sendHMIAddressing, callback=None, datatype='int'):
        self.transport_rolling = rolling

        speed = 1.0 if rolling else 0.0

        for pluginData in self.plugins.values():
            speed_symbol = pluginData['designations'][self.DESIGNATIONS_INDEX_SPEED]

            if speed_symbol is not None:
                pluginData['ports'][speed_symbol] = speed
                if sendHost:
                    self.msg_callback("param_set %s %s %f" % (pluginData['instance'], speed_symbol, speed))

        # Changing HMI state from here is very problematic, we deal with this later
        if self.hmi.initialized and (sendHMI or sendHMIAddressing):
            self.next_hmi_play[0] = rolling
            if sendHMI:
                self.next_hmi_play[1] = True
            if sendHMIAddressing:
                self.next_hmi_play[2] = True

        if sendWeb:
            self.msg_callback("transport %i %f %f %s" % (self.transport_rolling,
                                                         self.transport_bpb,
                                                         self.transport_bpm,
                                                         self.transport_sync))

        if sendHost:
            self.send_notmodified("transport %i %f %f" % (self.transport_rolling,
                                                          self.transport_bpb,
                                                          self.transport_bpm), callback, datatype)

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
        try:
            cputemp = read_file_contents(self.thermalfile, "0")
        except OSError:
            cputemp = "0"
            self.thermalfile = None
        return "sys_stats %s %s %s" % (memload, cpufreq, cputemp)

    def memtimer_callback(self):
        self.msg_callback(self.get_system_stats_message())

    # -----------------------------------------------------------------------------------------------------------------
    # Addressing (public stuff)

    @gen.coroutine
    def address(self, instance, portsymbol, actuator_uri, label, minimum, maximum, value, steps, extras, callback,
                not_param_set=False, send_hmi=True):
        instance_id = self.mapper.get_id(instance)
        pluginData  = self.plugins.get(instance_id, None)

        tempo = extras.get('tempo', False)
        dividers = extras.get('dividers', None)
        page = extras.get('page', None)
        subpage = extras.get('subpage', None)
        coloured = bool(int(extras.get('coloured', None) or 0))
        momentary = int(extras.get('momentary', None) or 0)
        operational_mode = extras.get('operational_mode', '=')

        if page is not None and not self.addressings.addressing_pages:
            page = None
        if subpage is not None and not self.addressings.has_hmi_subpages:
            subpage = None

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
        send_hmi_available_pages = False

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

            if old_actuator_type == Addressings.ADDRESSING_TYPE_HMI:
                old_hw_ids = []
                old_group_actuators = self.addressings.get_group_actuators(old_actuator_uri)
                # Unadress all actuators in group
                if old_group_actuators is not None:
                    old_hw_ids = [self.addressings.hmi_uri2hw_map[actuator_uri] for actuator_uri in old_group_actuators]
                else:
                    old_hw_ids = [self.addressings.hmi_uri2hw_map[old_actuator_uri]]

                old_page = old_addressing['page']
                old_subpage = self.addressings.hmi_hwsubpages[old_hw_ids[0]]

                if not self.addressings.addressing_pages or (self.addressings.current_page == old_page and
                                                             old_addressing['subpage'] == old_subpage):
                    try:
                        yield gen.Task(self.addr_task_unaddressing, old_actuator_type,
                                                                    old_addressing['instance_id'],
                                                                    old_addressing['port'],
                                                                    send_hmi=send_hmi,
                                                                    hw_ids=old_hw_ids)
                        yield gen.Task(self.addressings.hmi_load_current, old_actuator_uri, send_hmi=send_hmi)
                    except Exception as e:
                        logging.exception(e)

                # Find out if old addressing page should not be available anymore:
                if self.addressings.addressing_pages:
                    send_hmi_available_pages = self.check_available_pages(old_page)

            else:
                try:
                    yield gen.Task(self.addr_task_unaddressing, old_actuator_type,
                                                                old_addressing['instance_id'],
                                                                old_addressing['port'],
                                                                send_hmi=send_hmi)
                except Exception as e:
                    logging.exception(e)

        if not actuator_uri or actuator_uri == kNullAddressURI:
            # while unaddressing, one page has become unavailable (without any addressings)
            if send_hmi_available_pages and self.hmi.initialized:
                self.hmi.set_available_pages(self.addressings.get_available_pages(), callback)
            else:
                callback(True)
            return

        is_hmi_actuator = self.addressings.is_hmi_actuator(actuator_uri)

        if is_hmi_actuator and not self.hmi.initialized:
            print("WARNING: Cannot address to HMI at this point")
            callback(False)
            return

        # Send pages now if new addressing is not for HMI (the HMI-specific case is handled later)
        if send_hmi_available_pages and self.hmi.initialized and not is_hmi_actuator:
            try:
                yield gen.Task(self.hmi.set_available_pages, self.addressings.get_available_pages())
            except Exception as e:
                logging.exception(e)

        # MIDI learn is not an actual addressing
        if actuator_uri == kMidiLearnURI:
            self.send_notmodified("midi_learn %d %s %f %f" % (instance_id,
                                                              portsymbol,
                                                              minimum,
                                                              maximum), callback, datatype='boolean')
            return

        needsValueChange = False
        hasStrictBounds = True

        if not tempo and hasStrictBounds:
            if value < minimum:
                value = minimum
                needsValueChange = True
            elif value > maximum:
                value = maximum
                needsValueChange = True

        if tempo and not not_param_set:
            needsValueChange = True

        # momentary on
        if momentary == 1:
            target = maximum if portsymbol == ":bypass" else minimum
            if value != target:
                value = target
                needsValueChange = True
        # momentary off
        elif momentary == 2:
            target = minimum if portsymbol == ":bypass" else maximum
            if value != target:
                value = target
                needsValueChange = True

        group_actuators = self.addressings.get_group_actuators(actuator_uri)
        if group_actuators is not None:
            for group_actuator_uri in group_actuators:
                group_addressing = self.addressings.add(instance_id, pluginData['uri'], portsymbol, group_actuator_uri,
                                                        label, minimum, maximum, steps, value,
                                                        tempo, dividers, page, subpage, actuator_uri,
                                                        coloured, momentary, operational_mode)
                                              # group=[a for a in group_actuators if a != group_actuator_uri])
                if group_addressing is None:
                    callback(False)
                    return

                if needsValueChange:
                    hw_id = self.addressings.hmi_uri2hw_map[group_actuator_uri]
                    try:
                        yield gen.Task(self.hmi_or_cc_parameter_set, instance_id, portsymbol, value, hw_id)
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
                                              label, minimum, maximum, steps, value, tempo, dividers, page, subpage, None,
                                              coloured, momentary, operational_mode)
            if addressing is None:
                callback(False)
                return

            if needsValueChange:
                if actuator_uri != kBpmURI:
                    hw_id = self.addressings.hmi_uri2hw_map[actuator_uri] if is_hmi_actuator else None
                    try:
                        yield gen.Task(self.hmi_or_cc_parameter_set, instance_id, portsymbol, value, hw_id)
                    except Exception as e:
                        logging.exception(e)
                elif tempo:
                    try:
                        yield gen.Task(self.host_and_web_parameter_set, pluginData, instance, instance_id, value, portsymbol)
                    except Exception as e:
                        logging.exception(e)

            try:
                yield gen.Task(self.addressings.load_addr, actuator_uri, addressing, send_hmi=send_hmi)
            except Exception as e:
                logging.exception(e)

        self.pedalboard_modified = True
        pluginData['addressings'][portsymbol] = addressing

        # Find out if new addressing page should become available
        if self.addressings.addressing_pages and is_hmi_actuator and self.hmi.initialized:
            if self.check_available_pages(page) or send_hmi_available_pages:
                try:
                    yield gen.Task(self.hmi.set_available_pages, self.addressings.get_available_pages())
                except Exception as e:
                    logging.exception(e)

        # The end
        callback(True)

    def unaddress(self, instance, portsymbol, send_hmi, callback):
        self.address(instance, portsymbol, kNullAddressURI, "---", 0.0, 0.0, 0.0, 0, {}, callback, True, send_hmi)

    def check_available_pages(self, page):
        send_hmi_available_pages = False
        available_pages = self.addressings.available_pages.copy()

        if page == 0:
            available_pages[0] = True
        else:
            available_pages[page] = False
            for uri, addrs in self.addressings.hmi_addressings.items():
                for addr in addrs['addrs']:
                    if addr['page'] == page:
                        available_pages[page] = True
                        break

        if self.addressings.available_pages != available_pages:
            send_hmi_available_pages = True
            self.addressings.available_pages = available_pages

        return send_hmi_available_pages

    def host_and_web_parameter_set(self, pluginData, instance, instance_id, port_value, portsymbol, callback):
        pluginData['ports'][portsymbol] = port_value
        self.send_modified("param_set %d %s %f" % (instance_id, portsymbol, port_value), callback, datatype='boolean')
        self.msg_callback("param_set %s %s %f" % (instance, portsymbol, port_value))

    def cv_addressing_plugin_port_add(self, uri, name):
        # Port already added, just change its name
        if uri in self.addressings.cv_addressings.keys():
            self.addressings.cv_addressings[uri]['name'] = name
        else:
            self.addressings.cv_addressings[uri] = { 'name': name, 'addrs': [] }
        return self.addr_task_get_plugin_cv_port_op_mode(uri)

    def cv_addressing_plugin_port_remove_gen_helper(self, uri, callback):
        self.cv_addressing_plugin_port_remove(uri, callback)

    @gen.coroutine
    def cv_addressing_plugin_port_remove(self, uri, callback):
        if uri not in self.addressings.cv_addressings:
            callback(False)
            return

        # Unadress everything that was assigned to this plugin cv port
        addressings_addrs = self.addressings.cv_addressings[uri]['addrs'].copy()

        if len(addressings_addrs) == 0:
            del self.addressings.cv_addressings[uri]
            callback(True)
            return

        for addressing in addressings_addrs:
            try:
                instance_id = addressing['instance_id']
                port        = addressing['port']
                instance    = self.mapper.get_instance(instance_id)
            except Exception as e:
                callback(False)
                logging.exception(e)
                return

            try:
                yield gen.Task(self.unaddress, instance, port, False)
            except Exception as e:
                callback(False)
                logging.exception(e)
                return

        del self.addressings.cv_addressings[uri]
        callback(True)

    # -----------------------------------------------------------------------------------------------------------------
    # HMI callbacks, called by HMI via serial

    def hmi_list_banks(self, dir_up, bank_id, callback):
        logging.debug("hmi list banks %d %d", dir_up, bank_id)

        numUserBanks = len(self.userbanks)
        numFactoryBanks = len(self.factorybanks)
        numBanks = numUserBanks + numFactoryBanks + 1

        if self.supports_factory_banks:
            numBanks += 3

        if dir_up in (0, 1):
            bank_id += 1 if dir_up else -1

        if bank_id < 0 or bank_id >= numBanks:
            logging.error("hmi wants out of bounds bank data (%d %d)", dir_up, bank_id)
            callback(True)
            return

        if numBanks <= 9 or bank_id < 4:
            startIndex = 0
        elif bank_id+4 >= numBanks:
            startIndex = numBanks - 9
        else:
            startIndex = bank_id - 4

        endIndex = min(startIndex+9, numBanks)
        banksData = '%d %d %d' % (numBanks, startIndex, endIndex)

        if self.supports_factory_banks:
            for bank_id in range(startIndex, endIndex):
                flags = 0
                if bank_id in (0, numUserBanks + 2):
                    title = ""
                    flags = FLAG_NAVIGATION_DIVIDER
                elif bank_id == 1:
                    title = "All User Pedalboards"
                    flags = FLAG_NAVIGATION_READ_ONLY
                elif bank_id < numUserBanks + 2:
                    title = self.userbanks[bank_id - 2]['title']
                elif bank_id == numUserBanks + 3:
                    title = "All Factory Pedalboards"
                    flags = FLAG_NAVIGATION_FACTORY|FLAG_NAVIGATION_READ_ONLY
                else:
                    title = self.factorybanks[bank_id - numUserBanks - 4]['title']
                    flags = FLAG_NAVIGATION_FACTORY|FLAG_NAVIGATION_READ_ONLY
                banksData += ' %d %d %s' % (bank_id, flags, normalize_for_hw(title))

        else:
            for bank_id in range(startIndex, endIndex):
                if bank_id == 0:
                    title = "All Pedalboards"
                else:
                    title = self.userbanks[bank_id - 1]['title']
                banksData += ' %s %d' % (normalize_for_hw(title), bank_id)

        callback(True, banksData)

    def hmi_list_bank_pedalboards(self, props, pedalboard_index, bank_id, callback):
        logging.debug("hmi list bank pedalboards %d %d %d", props, pedalboard_index, bank_id)

        numUserBanks = len(self.userbanks)
        numFactoryBanks = len(self.factorybanks)
        numBanks = numUserBanks + numFactoryBanks + 1

        if self.supports_factory_banks:
            numBanks += 3

        if bank_id < 0 or bank_id >= numBanks:
            logging.error("Trying to list pedalboards with an out of bounds bank id (%d %d %d)", props, pedalboard_index, bank_id)
            callback(False, "0 0 0")
            return

        if self.supports_factory_banks and bank_id in (0, numUserBanks + 2):
            logging.error("Trying to list pedalboards for a divider (%d %d %d)", props, pedalboard_index, bank_id)
            callback(False, "0 0 0")
            return

        dir_up  = props & FLAG_PAGINATION_PAGE_UP
        wrap    = props & FLAG_PAGINATION_WRAP_AROUND
        initial = props & FLAG_PAGINATION_INITIAL_REQ

        if not initial:
            pedalboard_index += 1 if dir_up else -1

        if self.supports_factory_banks:
            flags = 0
            if bank_id == 1:
                pedalboards = self.alluserpedalboards
            elif bank_id < numUserBanks + 2:
                pedalboards = self.userbanks[bank_id - 2]['pedalboards']
            elif bank_id == numUserBanks + 3:
                flags = FLAG_NAVIGATION_FACTORY|FLAG_NAVIGATION_READ_ONLY
                pedalboards = self.allfactorypedalboards
            else:
                flags = FLAG_NAVIGATION_FACTORY|FLAG_NAVIGATION_READ_ONLY
                pedalboards = self.factorybanks[bank_id - numUserBanks - 4]['pedalboards']
        else:
            flags = 0
            if bank_id == 0:
                pedalboards = self.alluserpedalboards
            else:
                pedalboards = self.userbanks[bank_id - 1]['pedalboards']

        numPedals = len(pedalboards)

        if pedalboard_index < 0 or pedalboard_index >= numPedals:
            if not wrap and pedalboard_index >= 0:
                logging.error("hmi wants out of bounds pedalboard data (%d %d %d)", props, pedalboard_index, bank_id)
                callback(False, "0 0 0")
                return

            # wrap around mode, neat
            if pedalboard_index < 0 and wrap:
                pedalboard_index = numPedals
            else:
                pedalboard_index = 0

        if numPedals <= 9 or pedalboard_index < 4:
            startIndex = 0
        elif pedalboard_index + 4 >= numPedals:
            startIndex = numPedals - 9
        else:
            startIndex = pedalboard_index - 4

        startIndex = max(startIndex, 0)
        endIndex = min(startIndex+9, numPedals)
        pedalboardsData = '%d %d %d' % (numPedals, startIndex, endIndex)

        if self.supports_factory_banks:
            for i in range(startIndex, endIndex):
                pedalboardFlags = flags | (FLAG_NAVIGATION_TRIAL_PLUGINS if pedalboards[i].get('hasTrialPlugins', False) else 0)
                pedalboardsData += ' %d %d %s' % (i + self.pedalboard_index_offset,
                                                  pedalboardFlags,
                                                  normalize_for_hw(pedalboards[i]['title']))
        else:
            for i in range(startIndex, endIndex):
                pedalboardsData += ' %s %d' % (normalize_for_hw(pedalboards[i]['title']),
                                               i + self.pedalboard_index_offset)

        callback(True, pedalboardsData)

    def hmi_list_pedalboard_snapshots(self, props, snapshot_id, callback):
        logging.debug("hmi list pedalboards snapshots %d %d", props, snapshot_id)

        dir_up  = props & FLAG_PAGINATION_PAGE_UP
        wrap    = props & FLAG_PAGINATION_WRAP_AROUND
        initial = props & FLAG_PAGINATION_INITIAL_REQ

        if not initial:
            snapshot_id += 1 if dir_up else -1

        numSnapshots = len(self.pedalboard_snapshots)

        if snapshot_id < 0 or snapshot_id >= numSnapshots:
            if not wrap and snapshot_id > 0:
                logging.error("hmi wants out of bounds pedalboard snapshot data (%d %d)", props, snapshot_id)
                callback(True)
                return

            # wrap around mode, neat
            if snapshot_id < 0 and wrap:
                snapshot_id = numSnapshots - 1
            else:
                snapshot_id = 0

        if numSnapshots <= 9 or snapshot_id < 4:
            startIndex = 0
        elif snapshot_id + 4 >= numSnapshots:
            startIndex = numSnapshots - 9
        else:
            startIndex = snapshot_id - 4

        endIndex = min(startIndex + 9, numSnapshots)
        snapshotData = '%d %d %d' % (numSnapshots, startIndex, endIndex)

        for i in range(startIndex, endIndex):
            snapshotData += ' %s %d' % (normalize_for_hw(self.pedalboard_snapshots[i]['name']), i)

        logging.debug("hmi list pedalboards snapshots %d %d -> data is '%s'", props, snapshot_id, snapshotData)
        callback(True, snapshotData)

    # -----------------------------------------------------------------------------------------------------------------

    def hmi_bank_new(self, title, callback):
        utitle = title.upper()
        if utitle in ("ALL PEDALBOARDS", "ALL USER PEDALBOARDS"):
            callback(False)
            return

        for bank in self.userbanks:
            if bank['title'].upper() == utitle:
                callback(-2)
                return

        self.userbanks.append({
            'title': title,
            'pedalboards': [],
        })
        save_banks(self.userbanks)
        callback(True, len(self.userbanks) + 1)

    def hmi_bank_delete(self, bank_id, callback):
        if bank_id < self.userbanks_offset or bank_id - self.userbanks_offset >= len(self.userbanks):
            print("ERROR: Trying to remove invalid bank id %i" % (bank_id))
            callback(False, -1)
            return

        # if we delete the current bank, current pedalboard no longer belongs to it
        # so this response says where it is located from within the "All User Pedalboards" bank
        pb_resp = -1

        # if bank-to-remove is the current one, reset to "All User Pedalboards"
        if self.bank_id == bank_id:
            self.bank_id = self.first_user_bank
            # find current pedalboard within "All User Pedalboards"
            pb_path = self.pedalboard_path or DEFAULT_PEDALBOARD
            for pbi in range(len(self.alluserpedalboards)):
                if self.alluserpedalboards[pbi]['bundle'] == pb_path:
                    pb_resp = pbi
                    break
            else:
                print("ERROR: Failed to find new pedalboard id to give from All")

        # if current bank is after or same as bank-to-remove, shift back by 1
        elif self.bank_id >= bank_id:
            self.bank_id -= 1

        self.userbanks.pop(bank_id - self.userbanks_offset)
        save_banks(self.userbanks)
        callback(True, pb_resp)

    def hmi_bank_add_pedalboards_or_banks(self, dst_bank_id, src_bank_id, pedalboards_or_banks, callback):
        if dst_bank_id < self.userbanks_offset or dst_bank_id - self.userbanks_offset >= len(self.userbanks):
            print("ERROR: Trying to add to invalid bank id %i" % (dst_bank_id))
            callback(False)
            return
        if not pedalboards_or_banks:
            print("ERROR: There are no banks/pedalboards to add, stop")
            callback(False)
            return

        if src_bank_id == -1:
            self.hmi_bank_add_banks(dst_bank_id, pedalboards_or_banks, callback)
        else:
            self.hmi_bank_add_pedalboards(dst_bank_id, src_bank_id, pedalboards_or_banks, callback)

    def hmi_bank_add_banks(self, dst_bank_id, banks, callback):
        dst_pedalboards = self.userbanks[dst_bank_id - self.userbanks_offset]['pedalboards']

        for bank_id_str in banks.split(' '):
            try:
                bank_id = int(bank_id_str)
            except ValueError:
                print("ERROR: bank with id %s is invalid, cannot convert to integer" % bank_id_str)
                continue
            if bank_id < self.userbanks_offset or bank_id - self.userbanks_offset >= len(self.userbanks):
                print("ERROR: Trying to add out of bounds bank id %i" % bank_id)
                continue
            # TODO remove this print after we verify that all works
            print("DEBUG: added bank", self.userbanks[bank_id - self.userbanks_offset]['title'])
            dst_pedalboards += self.userbanks[bank_id - self.userbanks_offset]['pedalboards']

        save_banks(self.userbanks)
        callback(True)

    def hmi_bank_add_pedalboards(self, dst_bank_id, src_bank_id, pedalboards, callback):
        first_valid_bank = 1 if self.supports_factory_banks else 0

        if src_bank_id < first_valid_bank or src_bank_id - self.userbanks_offset >= len(self.userbanks):
            print("ERROR: Trying to add pedalboard from invalid bank id %i" % (src_bank_id))
            callback(False)
            return

        dst_pedalboards = self.userbanks[dst_bank_id - self.userbanks_offset]['pedalboards']

        if src_bank_id == first_valid_bank:
            src_pedalboards = self.alluserpedalboards
        else:
            src_pedalboards = self.userbanks[src_bank_id - self.userbanks_offset]['pedalboards']

        for pedalboard_index_str in pedalboards.split(' '):
            try:
                pedalboard_index = int(pedalboard_index_str)
            except ValueError:
                print("ERROR: pedalboard with id %s is invalid, cannot convert to integer" % pedalboard_index_str)
                continue
            if pedalboard_index < 0 or pedalboard_index >= len(src_pedalboards):
                print("ERROR: Trying to add out of bounds pedalboard id %i" % pedalboard_index)
                continue
            # TODO remove this print after we verify that all works
            print("DEBUG: added pedalboard", src_pedalboards[pedalboard_index]['title'])
            dst_pedalboards.append(src_pedalboards[pedalboard_index])

        save_banks(self.userbanks)
        callback(True)

    def hmi_bank_reorder_pedalboards(self, bank_id, src, dst, callback):
        if bank_id < self.userbanks_offset or bank_id - self.userbanks_offset >= len(self.userbanks):
            print("ERROR: Trying to reorder pedalboards in invalid bank id %i" % (bank_id))
            callback(False)
            return

        pedalboards = self.userbanks[bank_id - self.userbanks_offset]['pedalboards']

        # NOTE src and dst are indexes, not ids
        if src < 0 or src >= len(pedalboards):
            callback(False)
            return
        if dst < 0 or dst >= len(pedalboards):
            callback(False)
            return

        pedalboard = pedalboards.pop(src)
        pedalboards.insert(dst, pedalboard)

        callback(True)

    # -----------------------------------------------------------------------------------------------------------------

    def hmi_pedalboard_save_as(self, title, callback):
        utitle = title.upper()
        if any(pedalboard['title'].upper() == utitle for pedalboard in self.alluserpedalboards):
            callback(-2)
            return

        bundlepath, _ = self.save(title, True, callback)
        print("hmi_pedalboard_save_as", title, "->", bundlepath)

        pedalboard = {
            'broken': False,
            'factory': False,
            'hasTrialPlugins': False,
            'uri': "file://" + bundlepath,
            'bundle': bundlepath,
            'title': title,
            'version': 0,
        }
        self.alluserpedalboards.append(pedalboard)

        if self.bank_id >= self.userbanks_offset and self.bank_id - self.userbanks_offset < len(self.userbanks):
            self.userbanks[self.bank_id - self.userbanks_offset]['pedalboards'].append(pedalboard)
            save_banks(self.userbanks)

    def hmi_pedalboard_remove_from_bank(self, bank_id, pedalboard_index, callback):
        if bank_id < self.userbanks_offset or bank_id - self.userbanks_offset >= len(self.userbanks):
            print("ERROR: Trying to remove pedalboard using out of bounds bank id %i" % (bank_id))
            callback(False, -1)
            return

        pedalboards = self.userbanks[bank_id - self.userbanks_offset]['pedalboards']

        if pedalboard_index < 0 or pedalboard_index >= len(pedalboards):
            print("ERROR: Trying to remove pedalboard using out of bounds pedalboard id %i" % (pedalboard_index))
            callback(False, -1)
            return

        removed_pb = pedalboards.pop(pedalboard_index)
        save_banks(self.userbanks)

        # find current pedalboard within "All User Pedalboards"
        pb_path = removed_pb['bundle']
        for pbi in range(len(self.alluserpedalboards)):
            if self.alluserpedalboards[pbi]['bundle'] == pb_path:
                pb_resp = pbi
                break
        else:
            print("ERROR: Failed to find removed pedalboard id to give from All")
            pb_resp = -1

        callback(True, pb_resp)

    def hmi_pedalboard_reorder_snapshots(self, src, dst, callback):
        # some safety checks first
        if src < 0 or src >= len(self.pedalboard_snapshots) or self.pedalboard_snapshots[src] is None:
            callback(False)
            return
        if dst < 0 or dst >= len(self.pedalboard_snapshots) or self.pedalboard_snapshots[dst] is None:
            callback(False)
            return

        # if dst and src match, there is nothing to do
        if dst == src:
            callback(True)
            return

        current = self.pedalboard_snapshots[self.current_pedalboard_snapshot_id]

        snapshot = self.pedalboard_snapshots.pop(src)
        self.pedalboard_snapshots.insert(dst, snapshot)

        self.current_pedalboard_snapshot_id = self.pedalboard_snapshots.index(current)

        callback(True)

        # update addressing as needed
        self.readdress_snapshots(self.current_pedalboard_snapshot_id)

    # -----------------------------------------------------------------------------------------------------------------

    def hmi_pedalboard_snapshot_save(self, callback):
        ok = self.snapshot_save()
        callback(ok)

    def hmi_pedalboard_snapshot_save_as(self, name, callback):
        uname = name.upper()
        if any(snapshot['name'].upper() == uname for snapshot in self.pedalboard_snapshots):
            callback(-2)
            return
        idx = self.snapshot_saveas(name)
        callback(True)

        # update snapshot title
        self.hmi.set_snapshot_name(idx, self.pedalboard_snapshots[idx]['name'], None)

        # update addressing as needed
        mapPresets = self.plugins[PEDALBOARD_INSTANCE_ID]['mapPresets']
        if mapPresets:
            mapPresets.append("file:///%i" % idx)
        self.readdress_snapshots(idx)

    def hmi_pedalboard_snapshot_delete(self, snapshot_id, callback):
        if snapshot_id < 0 or snapshot_id >= len(self.pedalboard_snapshots):
            callback(False)
            return
        if len(self.pedalboard_snapshots) == 1:
            callback(False)
            return

        self.pedalboard_snapshots.pop(snapshot_id)

        if self.current_pedalboard_snapshot_id == snapshot_id:
            self.current_pedalboard_snapshot_id = -1

        callback(True)

        # force snapshot title if current snapshot was deleted
        if self.current_pedalboard_snapshot_id == -1:
            self.hmi.set_snapshot_name(-1, DEFAULT_SNAPSHOT_NAME, None)

        # update addressing as needed
        mapPresets = self.plugins[PEDALBOARD_INSTANCE_ID]['mapPresets']
        if snapshot_id < len(mapPresets):
            mapPresets.pop(-1)
        self.readdress_snapshots(0)

    # -----------------------------------------------------------------------------------------------------------------

    def readdress_snapshots(self, idx):
        pluginData = self.plugins[PEDALBOARD_INSTANCE_ID]
        pluginData['preset'] = "file:///%i" % idx

        addressing = pluginData['addressings'].get(":presets", None)
        if addressing is None:
            return

        numsnapshots = len(self.pedalboard_snapshots)
        newdata = {
          'maximum': numsnapshots,
          'options': [(i,self.snapshot_name(i)) for i in range(numsnapshots)],
          'steps': numsnapshots - 1,
          'value': idx,
        }
        addressing.update(newdata)

        actuator_uri = addressing['actuator_uri']
        instance_id = addressing['instance_id']
        portsymbol = addressing['port']
        group_actuators = self.addressings.get_group_actuators(actuator_uri)

        abort_catcher = {}

        if group_actuators is not None:
            for group_actuator_uri in group_actuators:
                self.addressings.update_for_snapshots(group_actuator_uri, instance_id, portsymbol, newdata)
            self.addressings.load_current(group_actuators, (None, None), False, True, abort_catcher)

        else:
            self.addressings.update_for_snapshots(actuator_uri, instance_id, portsymbol, newdata)
            self.addressings.load_current([actuator_uri], (None, None), False, True, abort_catcher)

    # -----------------------------------------------------------------------------------------------------------------

    def bank_config_enabled_callback(self, _):
        print("NOTE: bank config done")

    def load_different_callback(self, ok):
        if self.next_hmi_pedalboard_to_load is None:
            return
        if ok:
            print("NOTE: Delayed loading of %i:%i has started" % self.next_hmi_pedalboard_to_load)
        else:
            print("ERROR: Delayed loading of %i:%i failed!" % self.next_hmi_pedalboard_to_load)

    def hmi_load_bank_pedalboard(self, bank_id, pedalboard_index, callback, from_hmi=True):
        logging.debug("hmi load bank pedalboard")

        numUserBanks = len(self.userbanks)
        numFactoryBanks = len(self.factorybanks)
        numBanks = numUserBanks + numFactoryBanks + 1

        if self.supports_factory_banks:
            numBanks += 3

        if bank_id < 0 or bank_id >= numBanks:
            logging.error("Trying to load pedalboard using out of bounds bank id (%d %s)", bank_id, pedalboard_index)
            callback(False)
            return

        if self.supports_factory_banks and bank_id in (0, numUserBanks + 2):
            logging.error("Trying to load pedalboard using divider bank id (%d %s)", bank_id, pedalboard_index)
            callback(False)
            return

        try:
            pedalboard_index = int(pedalboard_index)
        except:
            logging.error("Trying to load pedalboard using invalid pedalboard_index '%s'", pedalboard_index)
            callback(False)
            return

        if pedalboard_index < 0:
            logging.error("Trying to load pedalboard using out of bounds pedalboard id %d", pedalboard_index)
            callback(False)
            return

        if self.next_hmi_pedalboard_to_load is not None:
            logging.info("Delaying loading of %d:%d", bank_id, pedalboard_index)
            self.next_hmi_pedalboard_to_load = (bank_id, pedalboard_index)
            callback(True)
            return

        if self.supports_factory_banks:
            if bank_id == 1:
                pedalboards = self.alluserpedalboards
            elif bank_id < numUserBanks + 2:
                pedalboards = self.userbanks[bank_id - 2]['pedalboards']
            elif bank_id == numUserBanks + 3:
                pedalboards = self.allfactorypedalboards
            else:
                pedalboards = self.factorybanks[bank_id - numUserBanks - 4]['pedalboards']
        else:
            if bank_id == 0:
                pedalboards = self.alluserpedalboards
            else:
                pedalboards = self.userbanks[bank_id - 1]['pedalboards']

        if pedalboard_index >= len(pedalboards):
            logging.error("Trying to load pedalboard using out of bounds pedalboard id %d", pedalboard_index)
            callback(False)
            return

        bundlepath = pedalboards[pedalboard_index]['bundle']
        pbtitle = pedalboards[pedalboard_index]['title']
        abort_catcher = self.abort_previous_loading_progress("host PB load " + bundlepath)

        next_pb_to_load = (bank_id, pedalboard_index)
        self.next_hmi_pedalboard_to_load = next_pb_to_load
        self.next_hmi_pedalboard_loading = True
        callback(True)

        def load_finish_callback(_):
            self.processing_pending_flag = False
            self.send_notmodified("feature_enable processing 1")

            logging.info("Loading of %d:%d finished (2/2)", bank_id, pedalboard_index)
            next_pedalboard = self.next_hmi_pedalboard_to_load
            self.next_hmi_pedalboard_to_load = None
            self.next_hmi_pedalboard_loading = False

            if next_pedalboard is None:
                logging.error("ERROR: Inconsistent state detected when loading next pedalboard (will not activate audio)")
                return

            # Check if there's a pending pedalboard to be loaded
            if next_pedalboard != next_pb_to_load:
                self.hmi_load_bank_pedalboard(next_pedalboard[0],
                                              next_pedalboard[1],
                                              self.load_different_callback,
                                              from_hmi)

            elif self.descriptor.get("hmi_bank_navigation", False):
                self.setNavigateWithFootswitches(self.isBankFootswitchNavigationOn(),
                                                 self.bank_config_enabled_callback)

        def load_finish_with_ssname_callback(_):
            name = self.snapshot_name() or DEFAULT_SNAPSHOT_NAME
            self.hmi.set_snapshot_name(self.current_pedalboard_snapshot_id, name, load_finish_callback)

        def hmi_ready_callback(ok):
            if self.descriptor.get('hmi_set_pb_name', False):
                if self.descriptor.get('hmi_set_ss_name', False):
                    cb = load_finish_with_ssname_callback
                else:
                    cb = load_finish_callback
                self.hmi.set_pedalboard_name(pbtitle, cb)
            else:
                load_finish_callback(True)

        def pb_host_loaded_callback(_):
            logging.info("Loading of %d:%d finished (1/2)", next_pb_to_load[0], next_pb_to_load[1])
            # HMI call, works to notify of index change and also to know when all other HMI messages finish
            if from_hmi:
                self.hmi.ping(hmi_ready_callback)
            else:
                self.hmi.set_pedalboard_index(pedalboard_index, hmi_ready_callback)

        def load_callback(_):
            self.load(bundlepath, False, abort_catcher)
            # Dummy host call, just to receive callback when all other host messages finish
            self.send_notmodified("cpu_load", pb_host_loaded_callback, datatype='float_structure')

        def hmi_clear_callback(_):
            self.hmi.clear(load_callback)

        if not self.processing_pending_flag:
            self.processing_pending_flag = True
            self.send_notmodified("feature_enable processing 0")

        self.reset(bank_id, hmi_clear_callback)

    # -----------------------------------------------------------------------------------------------------------------

    def hmi_pedalboard_snapshot_load(self, snapshot_id, callback):
        logging.debug("hmi load pedalboard snapshot")

        if snapshot_id < 0 or snapshot_id >= len(self.pedalboard_snapshots):
            print("ERROR: Trying to load pedalboard using out of bounds pedalboard id %i" % (snapshot_id))
            callback(False)
            return

        abort_catcher = self.abort_previous_loading_progress("hmi_pedalboard_snapshot_load")
        callback(True)

        def load_finished(ok):
            logging.debug("[host] hmi_pedalboard_snapshot_load done for %d", snapshot_id)

        try:
            self.snapshot_load(snapshot_id, True, abort_catcher, load_finished)
        except Exception as e:
            logging.exception(e)

    # -----------------------------------------------------------------------------------------------------------------

    def get_addressed_port_info(self, hw_id):
        try:
            actuator_uri     = self.addressings.hmi_hw2uri_map[hw_id]
            actuator_subpage = self.addressings.hmi_hwsubpages[hw_id]
            addressings      = self.addressings.hmi_addressings[actuator_uri]
        except KeyError:
            return (None, None)

        addressings_addrs = addressings['addrs']

        if self.addressings.addressing_pages: # device supports pages
            try:
                addressing_data = self.addressings.get_addressing_for_page(addressings_addrs,
                                                                           self.addressings.current_page,
                                                                           actuator_subpage)
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

    def hmi_parameter_set(self, hw_id, value, callback):
        logging.debug("hmi parameter set")
        if self.next_hmi_pedalboard_loading:
            callback(False)
            logging.error("hmi_parameter_set, pedalboard loading is in progress")
            return
        instance_id, portsymbol = self.get_addressed_port_info(hw_id)
        self.hmi_or_cc_parameter_set(instance_id, portsymbol, value, hw_id, callback)

    def hmi_or_cc_parameter_set(self, instance_id, portsymbol, value, hw_id, callback):
        logging.debug("hmi_or_cc_parameter_set")

        if self.next_hmi_pedalboard_loading:
            callback(False)
            logging.error("hmi_or_cc_parameter_set, pedalboard loading is in progress")
            return

        abort_catcher = self.abort_previous_loading_progress("hmi_or_cc_parameter_set")

        try:
            instance = self.mapper.get_instance(instance_id)
        except KeyError:
            print("WARNING: hmi_or_cc_parameter_set requested for non-existing plugin")
            callback(False)
            return

        pluginData = self.plugins[instance_id]
        port_addressing = pluginData['addressings'].get(portsymbol, None)
        save_port_value = self.should_save_addressing_value(port_addressing, value)

        if portsymbol == ":bypass":
            bypassed = bool(value)
            if save_port_value:
                pluginData['bypassed'] = bypassed

            self.send_modified("bypass %d %d" % (instance_id, int(bypassed)), callback, datatype='boolean')
            self.msg_callback("param_set %s :bypass %f" % (instance, 1.0 if bypassed else 0.0))

            enabled_symbol = pluginData['designations'][self.DESIGNATIONS_INDEX_ENABLED]
            if enabled_symbol is None:
                return

            value = 0.0 if bypassed else 1.0
            self.msg_callback("param_set %s %s %f" % (instance, enabled_symbol, value))

            if save_port_value:
                pluginData['ports'][enabled_symbol] = value

        elif portsymbol == ":presets":
            value = int(value)
            if value < 0 or value >= len(pluginData['mapPresets']):
                callback(False)
                return

            if port_addressing is None:
                callback(False)
                return
            group_actuators = self.addressings.get_group_actuators(port_addressing['actuator_uri'])

            # Update value on the HMI for the other actuator in the group
            def group_callback(ok):
                if not ok:
                    callback(False)
                    return
                # NOTE: we cannot wait for HMI callback while giving a response to HMI
                self.control_set_other_group_actuator(group_actuators, hw_id, port_addressing, value, None)
                callback(True)

            cb = group_callback if group_actuators is not None else callback

            if instance_id == PEDALBOARD_INSTANCE_ID:
                value = int(pluginData['mapPresets'][value].replace("file:///",""))
                try:
                    self.snapshot_load(value, True, abort_catcher, cb)
                except Exception as e:
                    callback(False)
                    logging.exception(e)
            else:
                try:
                    self.preset_load(instance, pluginData['mapPresets'][value], True, abort_catcher, cb)
                except Exception as e:
                    callback(False)
                    logging.exception(e)

        elif instance_id == PEDALBOARD_INSTANCE_ID:
            if portsymbol in (":bpb", ":bpm", ":rolling"):
                try:
                    if portsymbol == ":bpb":
                        self.set_transport_bpb(value, True, True, True, False, callback)
                    elif portsymbol == ":bpm":
                        self.set_transport_bpm(value, True, True, True, False, callback)
                    elif portsymbol == ":rolling":
                        rolling = bool(value > 0.5)
                        self.set_transport_rolling(rolling, True, True, True, False, callback)
                    else:
                        callback(False)
                except Exception as e:
                    callback(False)
                    logging.exception(e)
            else:
                print("ERROR: Trying to set value for the wrong pedalboard port:", portsymbol)
                callback(False)
                return

        else:
            oldvalue = pluginData['ports'].get(portsymbol, None)
            if oldvalue is None:
                print("WARNING: hmi_or_cc_parameter_set requested for non-existing port", portsymbol)
                callback(False)
                return

            if port_addressing is not None:
                cctype = port_addressing.get('cctype', 0x0)
                hmitype = port_addressing.get('hmitype', 0x0)

                if hmitype & FLAG_CONTROL_ENUMERATION or cctype & CC_MODE_OPTIONS:
                    value = get_nearest_valid_scalepoint_value(value, port_addressing['options'])[1]

                group_actuators = self.addressings.get_group_actuators(port_addressing['actuator_uri'])

                if port_addressing.get('tempo', None):
                    # compute new port value based on received divider value
                    extinfo = get_plugin_info_essentials(pluginData['uri'])

                    if 'error' in extinfo.keys() and extinfo['error']:
                        callback(False)
                        return

                    ports = [p for p in extinfo['controlInputs'] if p['symbol'] == portsymbol]

                    if not ports:
                        callback(False)
                        return

                    port = ports[0]
                    port_value = get_port_value(self.transport_bpm, value, port['units']['symbol'])
                    if port['units']['symbol'] != 'BPM': # convert back into port unit if needed
                        port_value = convert_seconds_to_port_value_equivalent(port_value, port['units']['symbol'])

                    port_addressing['dividers'] = value
                    port_addressing['value'] = port_value

                    # NOTE: we cannot wait for HMI callback while giving a response to HMI
                    if group_actuators is not None:
                        for group_actuator_uri in group_actuators:
                            group_hw_id = self.addressings.hmi_uri2hw_map[group_actuator_uri]
                            if group_hw_id != hw_id:
                                self.hmi.control_set(group_hw_id, value, None)
                                break

                    if save_port_value:
                        pluginData['ports'][portsymbol] = port_value
                    self.send_modified("param_set %d %s %f" % (instance_id, portsymbol, port_value), callback, datatype='boolean')
                    self.msg_callback("param_set %s %s %f" % (instance, portsymbol, port_value))
                    return

                if group_actuators is not None:
                    # NOTE: we cannot wait for HMI callback while giving a response to HMI
                    self.control_set_other_group_actuator(group_actuators, hw_id, port_addressing, value, None)

            if save_port_value:
                pluginData['ports'][portsymbol] = value
            self.send_modified("param_set %d %s %f" % (instance_id, portsymbol, value), callback, datatype='boolean')
            self.msg_callback("param_set %s %s %f" % (instance, portsymbol, value))

    def control_set_other_group_actuator(self, group_actuators, hw_id, port_addressing, value, callback):
        for group_actuator_uri in group_actuators:
            group_hw_id = self.addressings.hmi_uri2hw_map[group_actuator_uri]
            if group_hw_id == hw_id:
                continue

            # Update value in addressing data sent to hmi
            addressing_data = port_addressing.copy()
            addressing_data['value'] = value

            # Set reverse enum type if re-addressing first actuator in group
            group_actuator = next((act for act in self.addressings.hw_actuators if act['uri'] == addressing_data['group']), None)
            if group_actuator is not None:
                if group_actuator['actuator_group'].index(group_actuator_uri) == 0:
                    addressing_data['hmitype'] |= FLAG_CONTROL_REVERSE
                else:
                    addressing_data['hmitype'] &= ~FLAG_CONTROL_REVERSE

            self.addressings.load_addr(group_actuator_uri, addressing_data, callback)
            return

        if callback is not None:
            callback(True)

    def hmi_screenshot(self, page, content, callback):
        self.hmi_screenshot_data[page] = content
        callback(True)

        if page != 7:
            return

        # size in pixels, increase as needed
        pixel_size = 8
        margin_size = 1
        border_spacing = 16

        # screen contrast, adjust as needed
        luminance_background = 220
        luminance_black = 0
        luminance_white = 200

        # screen size
        screen_width_in_pixels = 128
        screen_height_in_pixels = 64

        # actual image size
        target_width = border_spacing * 2 + margin_size + (margin_size + pixel_size) * screen_width_in_pixels
        target_height = border_spacing * 2 + margin_size  + (margin_size + pixel_size) * screen_height_in_pixels

        rawdata = ["0"]*screen_width_in_pixels*screen_height_in_pixels

        for i in range(len(self.hmi_screenshot_data)):
            o = self.hmi_screenshot_data[i]
            for j in range(screen_width_in_pixels):
                v = o[j*2:j*2+2]
                v = ("%08s" % bin(int(v,16)).replace("0b","")).replace(" ","0")
                v = "".join(reversed(v))

                x = j % screen_width_in_pixels
                y = i + int(j / screen_width_in_pixels)
                for z in range(8):
                    rawdata[x*screen_height_in_pixels + y*8 + z] = v[z]

        png = Image.new("L", (target_width, target_height), luminance_background)
        pixels = png.load()

        # draw pixels
        for w in range(screen_width_in_pixels):
            for h in range(screen_height_in_pixels):
                x = border_spacing + margin_size + w * (margin_size + pixel_size)
                y = border_spacing + margin_size + h * (margin_size + pixel_size)

                v = luminance_black if rawdata[w * screen_height_in_pixels + h] == '1' else luminance_white

                for ix in range(pixel_size):
                    for iy in range(pixel_size):
                        pixels[x+ix,y+iy] = v

        # draw grid, optional
        if luminance_background != luminance_white:
            for w in range(screen_width_in_pixels):
                for h in range(screen_height_in_pixels):
                    x = border_spacing + margin_size + w * (margin_size + pixel_size)
                    y = border_spacing + margin_size + h * (margin_size + pixel_size)

                    for ix in range(pixel_size + margin_size):
                        pixels[x+ix, y-margin_size] = luminance_background
                        pixels[x-margin_size, y+ix] = luminance_background

        counter = 0
        while True:
            counter += 1
            filename = os.path.join(DATA_DIR, "hmi-screenshot-%03d.png" % counter)
            if not os.path.exists(filename):
                break

        png.save(filename)

    def hmi_parameter_addressing_next(self, hw_id, callback):
        logging.debug("hmi parameter addressing next")
        self.addressings.hmi_load_next_hw(hw_id)
        callback(True)

    def hmi_parameter_load_subpage(self, hw_id, subpage, callback):
        logging.debug("hmi parameter load subpage")
        self.addressings.hmi_load_subpage(hw_id, subpage)
        callback(True)

    def hmi_next_control_page_compat(self, hw_id, props, callback):
        logging.debug("hmi next control page (compat) %d %d", hw_id, props)
        try:
            self.hmi_next_control_page_real(hw_id, props, None, callback)
        except Exception as e:
            callback(False)
            logging.exception(e)

    def hmi_next_control_page(self, hw_id, props, control_index, callback):
        logging.debug("hmi next control page %d %d %d", hw_id, props, control_index)
        try:
            self.hmi_next_control_page_real(hw_id, props, control_index, callback)
        except Exception as e:
            callback(False)
            logging.exception(e)

    @gen.coroutine
    def hmi_next_control_page_real(self, hw_id, props, control_index, callback):
        data = self.addressings.hmi_get_addr_data(hw_id)

        if data is None:
            callback(False)
            logging.error("hmi wants control data for invalid addressing (%d %d)", hw_id, props)
            return
        if data.get('tempo', False):
            # serious pain if we have to deal with it here...
            logging.debug("hmi wants control data for tempo addressing, no way (%d %d)", hw_id, props)
            callback(True)
            return

        instance_id, portsymbol = self.get_addressed_port_info(hw_id)
        if instance_id is None:
            logging.error("hmi wants control data for a non-existing plugin instance or port (%d %d)", hw_id, props)
            callback(False)
            return

        options = data['options']
        numOpts = len(options)
        value   = self.addr_task_get_port_value(instance_id, portsymbol)

        # old compat mode
        if control_index is None:
            dir_up = props & FLAG_PAGINATION_PAGE_UP
            ivalue, value = get_nearest_valid_scalepoint_value(value, options)
            ivalue += 1 if dir_up != 0 else -1
        # proper new mode
        else:
            ivalue = control_index

        wrap = props & FLAG_PAGINATION_WRAP_AROUND

        if ivalue < 0 or ivalue >= numOpts:
            if not wrap:
                logging.debug("hmi wants out of bounds control data (%d %d)", hw_id, props)
                callback(True)
                return
            # wrap around mode, neat
            if ivalue < 0:
                ivalue = numOpts - 1
            else:
                ivalue = 0

        if control_index is None:
            value = options[ivalue][0]

        # note: the code below matches hmi.py control_add
        optionsData = []

        if numOpts <= 5 or ivalue <= 2:
            startIndex = 0
        elif ivalue + 2 >= numOpts:
            startIndex = numOpts - 5
        else:
            startIndex = ivalue - 2
        endIndex = min(startIndex + 5, numOpts)

        flags = 0x0
        if startIndex != 0 or endIndex != numOpts:
            flags |= FLAG_SCALEPOINT_PAGINATED
        if data.get('group', None) is None:
            flags |= FLAG_SCALEPOINT_WRAP_AROUND
        if endIndex == numOpts:
            flags |= FLAG_SCALEPOINT_END_PAGE
        if data.get('coloured', False):
            flags |= FLAG_SCALEPOINT_ALT_LED_COLOR

        for i in range(startIndex, endIndex):
            option = options[i]
            xdata  = '%s %f' % (normalize_for_hw(option[1]), float(option[0]))
            optionsData.append(xdata)

        options = "%d %d %d %s" % (len(optionsData), flags, ivalue, " ".join(optionsData))
        options = options.strip()

        label = data['label']

        if data.get('group', None) is not None and self.descriptor.get('hmi_actuator_group_prefix', True):
            if data['hmitype'] & FLAG_CONTROL_REVERSE:
                prefix = "- "
            else:
                prefix = "+ "
            label = prefix + label

        callback(True, '%d %s %d %s %f %f %f %d %s' %
                  ( hw_id,
                    '%s' % normalize_for_hw(label),
                    data['hmitype'],
                    '%s' % normalize_for_hw(data['unit'], 7),
                    value,
                    data['maximum'],
                    data['minimum'],
                    data['steps'],
                    options,
                  ))

        if control_index is not None:
            return

        try:
            yield gen.Task(self.hmi_or_cc_parameter_set, instance_id, portsymbol, value, hw_id)
        except Exception as e:
            logging.exception(e)

    def hmi_save_current_pedalboard(self, callback):
        if not self.pedalboard_path:
            callback(True)
            return

        def host_callback(ok):
            os.sync()
            callback(True)

        logging.debug("hmi save current pedalboard")
        titlesym = symbolify(self.pedalboard_name)[:16]

        # if pedalboard was deleted by HMI management, recreate the whole deal
        if not os.path.exists(self.pedalboard_path):
            self.save_state_manifest(self.pedalboard_path, titlesym)
            self.save_state_addressings(self.pedalboard_path)

        self.save_state_snapshots(self.pedalboard_path)
        self.save_state_mainfile(self.pedalboard_path, self.pedalboard_name, titlesym)
        self.send_notmodified("state_save {}".format(self.pedalboard_path), host_callback)

    def hmi_reset_current_pedalboard(self, callback):
        logging.debug("hmi reset current pedalboard")
        try:
            self.hmi_reset_current_pedalboard_real(callback)
        except Exception as e:
            callback(False)
            logging.exception(e)

    @gen.coroutine
    def hmi_reset_current_pedalboard_real(self, callback):
        abort_catcher = self.abort_previous_loading_progress("hmi_reset_current_pedalboard")
        pb_values = get_pedalboard_plugin_values(self.pedalboard_path)

        used_actuators = []
        was_aborted = self.addressings.was_last_load_current_aborted()

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
            diffPreset  = p['preset'] and pluginData['preset'] != p['preset']

            if was_aborted or diffBypass:
                addressing = pluginData['addressings'].get(":bypass", None)
                if addressing is not None:
                    addressing['value'] = 1.0 if bypassed else 0.0
                    if addressing['actuator_uri'] not in used_actuators:
                        used_actuators.append(addressing['actuator_uri'])

            # if bypassed, do it now
            if diffBypass and bypassed:
                self.msg_callback("param_set %s :bypass 1.0" % (instance,))
                try:
                    yield gen.Task(self.bypass, instance, True)
                except Exception as e:
                    logging.exception(e)

            if was_aborted or diffPreset:
                if diffPreset:
                    pluginData['preset'] = p['preset']
                    self.msg_callback("preset %s %s" % (instance, p['preset']))
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
                equal  = pluginData['ports'][symbol] == value

                if not equal:
                    pluginData['ports'][symbol] = value
                    self.msg_callback("param_set %s %s %f" % (instance, symbol, value))
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
                self.msg_callback("param_set %s :bypass 0.0" % (instance,))
                try:
                    yield gen.Task(self.bypass, instance, False)
                except Exception as e:
                    logging.exception(e)

        self.pedalboard_modified = False
        self.addressings.load_current(used_actuators, (None, None), False, True, abort_catcher)

        callback(True)

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

        if self.swapped_audio_channels:
            if input_port == 1:
                input_port = 2
            else:
                input_port = 1

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

    def hmi_menu_item_change(self, item, value, callback):
        # check if this is a valid item
        try:
            item_str = menu_item_id_to_str(item)
        except ValueError:
            logging.error("hmi_menu_item_change - invalid item id `%i`", item)
            return

        logging.debug("hmi_menu_item_change %i:%s %i", item, item_str, value)

        if item == MENU_ID_SL_IN:
            self.hmi_menu_set_in_chan_link(value != 0, callback)
        elif item == MENU_ID_SL_OUT:
            self.hmi_menu_set_out_chan_link(value != 0, callback)
        elif item == MENU_ID_TUNER_MUTE:
            self.hmi_menu_set_tuner_mute(value != 0, callback)
        elif item == MENU_ID_QUICK_BYPASS:
            self.hmi_menu_set_quick_bypass_mode(value, callback)
        elif item == MENU_ID_PLAY_STATUS:
            self.hmi_menu_set_play_status(value != 0, callback)
        elif item == MENU_ID_MIDI_CLK_SOURCE:
            self.hmi_menu_set_clk_src(value, callback)
        elif item == MENU_ID_MIDI_CLK_SEND:
            self.hmi_menu_set_send_midi_clk(value != 0, callback)
        elif item == MENU_ID_SNAPSHOT_PRGCHGE:
            self.hmi_menu_set_snapshot_prgch(value, callback)
        elif item == MENU_ID_PB_PRGCHNGE:
            self.hmi_menu_set_pedalboard_prgch(value, callback)
        elif item == MENU_ID_TEMPO:
            self.hmi_menu_set_tempo_bpm(value, callback)
        elif item == MENU_ID_BEATS_PER_BAR:
            self.hmi_menu_set_tempo_bpb(value, callback)
        elif item == MENU_ID_BYPASS1:
            self.hmi_menu_set_truebypass_value(QUICK_BYPASS_MODE_1, value != 0, callback)
        elif item == MENU_ID_BYPASS2:
            self.hmi_menu_set_truebypass_value(QUICK_BYPASS_MODE_2, value != 0, callback)
        elif item == MENU_ID_BRIGHTNESS:
            self.hmi_menu_set_display_brightness(value, callback)
        #elif item == MENU_ID_CURRENT_PROFILE:
            #pass # TODO
        #elif item == MENU_ID_FOOTSWITCH_NAV:
            #pass # TODO
        elif item == MENU_ID_EXP_CV_INPUT:
            self.last_cv_exp_mode = bool(value)
            self.hmi_menu_set_exp_cv(value, callback)
        elif item == MENU_ID_HP_CV_OUTPUT:
            self.hmi_menu_set_hp_cv(value, callback)
        elif item == MENU_ID_MASTER_VOL_PORT:
            self.hmi_menu_set_master_volume_channel_mode(value, callback)
        elif item == MENU_ID_EXP_MODE:
            self.hmi_menu_set_exp_mode(value, callback)
        else:
            logging.error("hmi_menu_item_change %i:%s %i - unhandled", item, item_str, value)
            callback(False)

    def hmi_menu_set_in_chan_link(self, enabled, callback):
        """Set the link state of the input channel pair."""
        logging.debug("hmi menu set in chan link to `%i`", enabled)

        result = self.profile.set_stereo_link("input", bool(enabled))
        callback(result)

    def hmi_menu_set_out_chan_link(self, enabled, callback):
        """Set the link state of the output channel pair."""
        logging.debug("hmi menu set out chan link to `%i`", enabled)

        result = self.profile.set_stereo_link("output", bool(enabled))
        callback(result)

    def hmi_menu_set_tuner_mute(self, mute, callback):
        """Set if the tuner lets audio through or not."""
        logging.debug("hmi menu set tuner mute to `%i`", mute)

        if mute:
            self.mute()
        else:
            self.unmute()

        self.current_tuner_mute = mute
        self.prefs.setAndSave("tuner-mutes-outputs", bool(mute))
        callback(True)

    def hmi_menu_set_quick_bypass_mode(self, mode, callback):
        """Change the Quick Bypass Mode setting to `mode`."""
        logging.debug("hmi menu set quick bypass mode to `%i`", mode)

        if mode in QUICK_BYPASS_MODE_VALUES:
            self.prefs.setAndSave("quick-bypass-mode", mode)
            callback(True)
        else:
            callback(False)

    def hmi_menu_set_play_status(self, playing, callback):
        """Set the transport state."""
        logging.debug("hmi menu set play status to `%i`", playing)

        self.set_transport_rolling(bool(playing), True, False, True, True, callback)

    def hmi_menu_set_clk_src(self, mode, callback):
        """Set the tempo and transport sync mode."""
        logging.debug("hmi menu set clock source to `%i`", mode)

        self.set_sync_mode(mode, False, True, True, callback)

    def hmi_menu_set_send_midi_clk(self, onoff, callback):
        """Query the status of sending MIDI Beat Clock."""
        logging.debug("hmi menu set send midi clock to `%i`", onoff)

        if not self.profile.set_send_midi_clk(onoff):
            callback(False)
            return

        if onoff:
            self.hmi_menu_set_send_midi_clk_on(callback)
        else:
            self.hmi_menu_set_send_midi_clk_off(callback)

    def hmi_menu_set_send_midi_clk_on(self, callback):
        def operation_failed(ok):
            callback(False)

        def midi_beat_clock_sender_added(resp):
            if resp not in (0, -2, MIDI_BEAT_CLOCK_SENDER_INSTANCE_ID): # -2 means already loaded
                callback(False)
                return

            # Connect the plug-in to the MIDI output.
            source_port = "effect_%d:%s" % (MIDI_BEAT_CLOCK_SENDER_INSTANCE_ID, MIDI_BEAT_CLOCK_SENDER_OUTPUT_PORT)

            if not connect_jack_midi_output_ports(source_port):
                self.send_notmodified("remove %d" % MIDI_BEAT_CLOCK_SENDER_INSTANCE_ID, operation_failed)
                return

            callback(True)

        self.send_notmodified("add %s %d" % (MIDI_BEAT_CLOCK_SENDER_URI,
                                             MIDI_BEAT_CLOCK_SENDER_INSTANCE_ID), midi_beat_clock_sender_added)

    def hmi_menu_set_send_midi_clk_off(self, callback):
        # Just remove the plug-in without disconnecting gracefully
        self.send_notmodified("remove %d" % MIDI_BEAT_CLOCK_SENDER_INSTANCE_ID, callback)

    @gen.coroutine
    def hmi_menu_set_snapshot_prgch(self, channel, callback):
        """Set the MIDI channel for selecting a snapshot via Program Change."""
        logging.debug("hmi menu set snapshot MIDI program channel to `%i`", channel)

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

    @gen.coroutine
    def hmi_menu_set_pedalboard_prgch(self, channel, callback):
        """Set the MIDI channel for selecting a pedalboard in a bank via Program Change."""
        logging.debug("hmi menu set pedalboard MIDI program channel to `%i`", channel)

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

    def hmi_menu_set_tempo_bpm(self, bpm, callback):
        """Set the Jack BPM."""
        logging.debug("hmi menu set tempo bpm to `%i`", bpm)

        self.set_transport_bpm(bpm, True, False, True, True, callback)

    def hmi_menu_set_tempo_bpb(self, bpb, callback):
        """Set the Jack Beats Per Bar."""
        logging.debug("hmi menu set tempo bpb to `%i`", bpb)

        self.set_transport_bpb(bpb, True, False, True, True, callback)

    def hmi_menu_set_display_brightness(self, brightness, callback):
        """Set the display_brightness."""
        logging.debug("hmi menu set display brightness to `%i`", brightness)

        if brightness in DISPLAY_BRIGHTNESS_VALUES:
            self.prefs.setAndSave("display-brightness", brightness)
            callback(True)
        else:
            callback(False)

    def hmi_menu_set_truebypass_value(self, value, bypassed, callback):
        """Change the True Bypass setting of the given channel."""
        logging.debug("hmi menu set true bypass to `%i, %i`", value, bypassed)

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

    def hmi_menu_set_exp_cv(self, mode, callback):
        """Set the mode of the configurable input."""
        logging.debug("hmi menu set (input) exp/cv mode to `%i`", mode)

        result = self.profile.set_configurable_input_mode(mode)
        callback(result)

    def hmi_menu_set_hp_cv(self, mode, callback):
        """Set the mode of the configurable output."""
        logging.debug("hmi menu set (output) hp/cv mode to `%i`", mode)

        result = self.profile.set_configurable_output_mode(mode)
        callback(result)

    def hmi_menu_set_master_volume_channel_mode(self, mode, callback):
        """Set the mode how the master volume is linked to the channel output volumes."""
        logging.debug("hmi menu set master volume channel mode to %i", mode)

        result = self.profile.set_master_volume_channel_mode(mode)
        callback(result)

    def hmi_menu_set_exp_mode(self, mode, callback):
        """Set the mode mode for the expression pedal input. That is, if the signal is on tip or sleeve."""
        logging.debug("hmi menu set (input cv) expression pedal mode to `%i`", mode)

        result = self.profile.set_exp_mode(mode)
        callback(result)

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

    def hmi_snapshot_save(self, idx, callback):
        if idx not in (0, 1, 2):
            return callback(False)

        self.hmi_snapshots[idx] = self.snapshot_make("HMI")
        callback(True)

    def hmi_snapshot_load(self, idx, callback):
        # Use negative numbers for HMI snapshots
        snapshot_id = 0 - (self.HMI_SNAPSHOTS_OFFSET + idx)

        if snapshot_id not in (self.HMI_SNAPSHOTS_1, self.HMI_SNAPSHOTS_2, self.HMI_SNAPSHOTS_3):
            callback(False)
            logging.error("hmi_snapshot_load received with wrong index %d (snapshot id %d)",
                          idx, snapshot_id)
            return

        abort_catcher = self.abort_previous_loading_progress("hmi_snapshot_load")
        callback(True)

        def load_finished(ok):
            logging.debug("[host] hmi_snapshot_load done for %d", idx)

        try:
            self.snapshot_load(snapshot_id, True, abort_catcher, load_finished)
        except Exception as e:
            logging.exception(e)

    def hmi_page_load(self, idx, callback):
        abort_catcher = self.abort_previous_loading_progress("hmi_page_load")
        try:
            self.page_load(idx, abort_catcher, callback)
        except Exception as e:
            callback(False)
            logging.exception(e)

    def hmi_clear_ss_name(self, callback):
        if self.hmi.initialized and self.descriptor.get('hmi_set_ss_name', False):
            self.hmi.set_snapshot_name(self.current_pedalboard_snapshot_id, DEFAULT_SNAPSHOT_NAME, callback)
        else:
            callback(True)

    def hmi_report_ss_name_if_current(self, idx, callback):
        if (self.hmi.initialized and
            self.current_pedalboard_snapshot_id == idx and
            self.descriptor.get('hmi_set_ss_name', False)):
            name = self.snapshot_name() or DEFAULT_SNAPSHOT_NAME
            self.hmi.set_snapshot_name(self.current_pedalboard_snapshot_id, name, callback)
        else:
            callback(True)

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

    # -----------------------------------------------------------------------------------------------------------------
    # JACK stuff

    # Get list of Hardware MIDI devices
    # returns (devsInUse, devList, names, midiAggregatedMode)
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
            title = midi_port_alias_to_name(alias, True)
            out_ports[title] = port

        # Extra MIDI Ins
        ports = get_jack_hardware_ports(False, False)
        for port in ports:
            if not port.startswith(("system:midi_", "nooice")):
                continue
            alias = get_jack_port_alias(port)
            if not alias:
                continue
            title = midi_port_alias_to_name(alias, True)
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

        if self.midi_loopback_port is not None:
            devList.append(self.midi_loopback_port)
            names[self.midi_loopback_port] = "MIDI Loopback"
            if self.midi_loopback_enabled:
                devsInUse.append(self.midi_loopback_port)

        devList.sort()
        return (devsInUse, devList, names, self.midi_aggregated_mode)

    def get_port_name_alias(self, portname):
        alias = get_jack_port_alias(portname)

        if alias:
            return midi_port_alias_to_name(alias, True)

        return portname.split(":",1)[-1].title()

    # Set the selected MIDI devices, aggregated mode and loopback enabled
    @gen.coroutine
    def set_midi_devices(self, newDevs, midi_aggregated_mode, midi_loopback_enabled):
        # Change modes first
        if self.midi_aggregated_mode != midi_aggregated_mode:
            try:
                yield gen.Task(self.send_notmodified,
                               "feature_enable aggregated-midi {}".format(int(midi_aggregated_mode)))
            except Exception as e:
                raise e
            self.set_midi_devices_change_mode(midi_aggregated_mode)

        if self.midi_loopback_enabled != midi_loopback_enabled:
            self.set_midi_devices_loopback_enabled(midi_loopback_enabled)

        # If MIDI aggregated mode is off, we can handle device changes
        if not midi_aggregated_mode:
            self.set_midi_devices_separated(newDevs)

    def set_midi_devices_change_mode(self, midi_aggregated_mode):
        # from separated to aggregated mode
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

        # from aggregated to separated mode
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

    def set_midi_devices_loopback_enabled(self, midi_loopback_enabled):
        if self.midi_loopback_port is None:
            return

        self.midi_loopback_enabled = midi_loopback_enabled

        if midi_loopback_enabled:
            self.msg_callback("add_hw_port /graph/midi_loopback midi 1 MIDI_Loopback 42")
        else:
            self.remove_port_from_connections(self.midi_loopback_port)
            self.msg_callback("remove_hw_port /graph/midi_loopback")

    # Will remove or add new JACK ports (in mod-ui) as needed
    def set_midi_devices_separated(self, newDevs):
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

    def get_jack_source_port_name(self, actuator):
        if actuator.startswith(HW_CV_PREFIX):
            return "mod-spi2jack:" + actuator[len(HW_CV_PREFIX):]
        else:
            return self._fix_host_connection_port(actuator.split(CV_OPTION,1)[1])

    # -----------------------------------------------------------------------------------------------------------------
    # Profile stuff

    @gen.coroutine
    def profile_apply(self, values, isIntermediate):
        try:
            yield gen.Task(self.set_transport_bpb, values['transportBPB'], True, False, True, False)
            yield gen.Task(self.set_transport_bpm, values['transportBPM'], True, False, True, False)
        except Exception as e:
            logging.exception(e)

        if self.hmi.initialized:
            try:
                yield gen.Task(self.paramhmi_set, 'pedalboard', ":bpb", self.transport_bpb)
                yield gen.Task(self.paramhmi_set, 'pedalboard', ":bpm", self.transport_bpm)
            except Exception as e:
                logging.exception(e)

            try:
                yield gen.Task(self.hmi.set_profile_value, MENU_ID_BEATS_PER_BAR, self.transport_bpb)
                yield gen.Task(self.hmi.set_profile_value, MENU_ID_TEMPO, self.transport_bpm)
            except Exception as e:
                logging.exception(e)

        try:
            if values['midiClockSend']:
                yield gen.Task(self.hmi_menu_set_send_midi_clk_on)
            else:
                yield gen.Task(self.hmi_menu_set_send_midi_clk_off)
        except Exception as e:
            logging.exception(e)

        try:
            yield gen.Task(self.set_sync_mode, values['transportSource'], True, True, False)
        except Exception as e:
            logging.exception(e)

        # skip alsamixer related things on intermediate/boot
        if not isIntermediate:
            apply_mixer_values(values, self.descriptor.get("platform", None))

        if self.hmi.initialized:
            try:
                yield gen.Task(self.hmi.set_profile_values, self.transport_rolling, values)
            except Exception as e:
                logging.exception(e)

        if 'inputMode' in values:
            self.last_cv_exp_mode = bool(values['inputMode'])

        self.profile_applied = True

    # -----------------------------------------------------------------------------------------------------------------
