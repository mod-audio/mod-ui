#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

import json
import logging
import os

from tornado import gen
from mod import (
  get_hardware_descriptor,
  get_nearest_valid_scalepoint_value,
  normalize_for_hw,
  safe_json_load,
  TextFileFlusher
)
from mod.control_chain import (
  CC_MODE_TOGGLE,
  CC_MODE_TRIGGER,
  CC_MODE_OPTIONS,
  CC_MODE_TAP_TEMPO,
  CC_MODE_REAL,
  CC_MODE_INTEGER,
  CC_MODE_LOGARITHMIC,
  CC_MODE_COLOURED,
  CC_MODE_MOMENTARY,
  CC_MODE_REVERSE,
  CC_MODE_GROUP,
  ControlChainDeviceListener,
)
from mod.settings import PEDALBOARD_INSTANCE_ID
from modtools.tempo import get_divider_options
from modtools.utils import get_plugin_control_inputs
from mod.mod_protocol import (
    FLAG_CONTROL_BYPASS,
    FLAG_CONTROL_TAP_TEMPO,
    FLAG_CONTROL_ENUMERATION,
    FLAG_CONTROL_SCALE_POINTS,
    FLAG_CONTROL_TRIGGER,
    FLAG_CONTROL_TOGGLED,
    FLAG_CONTROL_LOGARITHMIC,
    FLAG_CONTROL_INTEGER,
    FLAG_CONTROL_REVERSE,
    FLAG_CONTROL_MOMENTARY,
)

# use pitchbend as midi cc, with an invalid MIDI controller number
MIDI_PITCHBEND_AS_CC = 131

# Special URI for non-addressed controls
kNullAddressURI = "null"

# Special URIs for midi-learn
kMidiLearnURI = "/midi-learn"
kMidiUnmapURI = "/midi-unmap"
kMidiCustomPrefixURI = "/midi-custom_" # to show current one

# URI for BPM sync (for non-addressed control ports)
kBpmURI ="/bpm"

# CV related constants
CV_PREFIX = 'cv_'
CV_OPTION = '/cv'
HW_CV_PREFIX = CV_OPTION + '/graph/' + CV_PREFIX

# definitions from lv2-hmi.h
# LV2_HMI_AddressingCapabilities
LV2_HMI_AddressingCapability_LED       = 1 << 0
LV2_HMI_AddressingCapability_Label     = 1 << 1
LV2_HMI_AddressingCapability_Value     = 1 << 2
LV2_HMI_AddressingCapability_Unit      = 1 << 3
LV2_HMI_AddressingCapability_Indicator = 1 << 4
# LV2_HMI_AddressingFlags
LV2_HMI_AddressingFlag_Coloured    = 1 << 0
LV2_HMI_AddressingFlag_Momentary   = 1 << 1
LV2_HMI_AddressingFlag_Reverse     = 1 << 2
LV2_HMI_AddressingFlag_TapTempo    = 1 << 3

class Addressings(object):
    ADDRESSING_TYPE_NONE = 0
    ADDRESSING_TYPE_HMI  = 1
    ADDRESSING_TYPE_CC   = 2
    ADDRESSING_TYPE_MIDI = 3
    ADDRESSING_TYPE_BPM  = 4
    ADDRESSING_TYPE_CV   = 5

    def __init__(self):
        self.init()
        self._task_addressing = None
        self._task_unaddressing = None
        self._task_set_value = None
        self._task_get_plugin_cv_port_op_mode = None
        self._task_get_plugin_data = None
        self._task_get_plugin_presets = None
        self._task_get_port_value = None
        self._task_get_tempo_divider = None
        self._task_store_address_data = None
        self._task_hw_added    = None
        self._task_hw_removed  = None
        self._task_hw_connected = None
        self._task_hw_disconnected = None
        self._task_act_added   = None
        self._task_act_removed = None
        self._task_set_available_pages = None
        self._task_host_hmi_map = None
        self._task_host_hmi_unmap = None

        self.cchain = ControlChainDeviceListener(self.cc_hardware_added,
                                                 self.cc_hardware_removed,
                                                 self.cc_hardware_connected,
                                                 self.cc_hardware_disconnected,
                                                 self.cc_actuator_added)

        # First addressings/pedalboard load flag
        self.first_load = True

        # Flag for load_current being active or aborted
        self.last_load_current_aborted = False
        self.pending_load_current = False

        # Flag and callbacks for Control Chain waiting
        self.waiting_for_cc = not self.cchain.initialized
        self.waiting_for_cc_cbs = []

    # -----------------------------------------------------------------------------------------------------------------

    # initialize (clear) all addressings
    def init(self):
        desc = get_hardware_descriptor()
        self.hw_actuators = desc.get('actuators', [])
        self.hw_actuators_uris = tuple(a['uri'] for a in self.hw_actuators)
        self.has_hmi_subpages = bool(desc.get('hmi_subpages', False))
        self.hmi_show_actuator_group_prefix = bool(desc.get('hmi_actuator_group_prefix', True))
        self.hmi_show_empty_pages = bool(desc.get('hmi_show_empty_pages', False))
        self.addressing_pages = int(desc.get('addressing_pages', 0))
        self.current_page = 0

        if self.addressing_pages:
            self.available_pages = [True if i == 0 else False for i in range(self.addressing_pages)]
        else:
            self.available_pages = []

        # 'hmi_addressings' uses a structure like this:
        # "/hmi/knob1": {'addrs': [...], 'idx': 0}
        # so per actuator we get:
        #  - 'addrs': list of addressings
        #  - 'idx'  : currently selected addressing (index)
        self.hmi_addressings = dict((uri, {'addrs': [], 'idx': -1}) for uri in self.hw_actuators_uris)

        self.cc_addressings = {}
        self.cc_metadata = {}
        self.midi_addressings = {}
        self.virtual_addressings = {kBpmURI: []}
        self.cv_addressings = {}

        # Store all possible HMI hardcoded values
        self.hmi_hw2uri_map = {}
        self.hmi_hwsubpages = {}
        self.hmi_uri2hw_map = {}

        for actuator in self.hw_actuators:
            uri = actuator['uri']
            hw_id = actuator['id']

            self.hmi_hw2uri_map[hw_id] = uri
            self.hmi_hwsubpages[hw_id] = 0 if self.has_hmi_subpages else None
            self.hmi_uri2hw_map[uri] = hw_id

    # clear all addressings, leaving metadata intact
    def clear(self):
        self.hmi_addressings  = dict((key, {'addrs': [], 'idx': -1}) for key in self.hmi_addressings.keys())
        self.cc_addressings   = dict((key, []) for key in self.cc_addressings.keys())
        self.cv_addressings   = dict((key, []) for key in self.cv_addressings.keys() if self.is_hw_cv_port(key))
        self.virtual_addressings   = dict((key, []) for key in self.virtual_addressings.keys())
        self.midi_addressings = {}
        self.current_page = 0
        self.last_load_current_aborted = False
        self.pending_load_current = False

        if self.has_hmi_subpages:
            for hw_id in self.hmi_hwsubpages:
                self.hmi_hwsubpages[hw_id] = 0

    # -----------------------------------------------------------------------------------------------------------------

    def get_actuators(self):
        actuators = self.hw_actuators.copy()

        for uri in sorted(self.cc_metadata.keys()):
            data = self.cc_metadata[uri]
            metadata = {
                'uri': uri,
                'name' : data['name'],
                'modes': data['modes'],
                'steps': data['steps'],
                'max_assigns': data['max_assigns'],
                'feedback'   : data['feedback'],
                'widgets'    : data['widgets'],
            }
            actuator_group = data.get('actuator_group', None)
            if actuator_group is not None:
                metadata['actuator_group'] = actuator_group

            actuators.append(metadata)

        return actuators

    # Not used (?)
    def get_addressings(self):
        addressings = {}

        # HMI
        for uri, addrs in self.hmi_addressings.items():
            addrs2 = []
            for addr in addrs['addrs']:
                addrs2.append({
                    'instance_id': addr['instance_id'],
                    'port'       : addr['port'],
                    'label'      : addr['label'],
                    'minimum'    : addr['minimum'],
                    'maximum'    : addr['maximum'],
                    'steps'      : addr['steps'],
                })
            addressings[uri] = addrs2

        # Control Chain
        for uri, addrs in self.cc_addressings.items():
            addrs2 = []
            for addr in addrs:
                addrs2.append({
                    'instance_id': addr['instance_id'],
                    'port'       : addr['port'],
                    'label'      : addr['label'],
                    'minimum'    : addr['minimum'],
                    'maximum'    : addr['maximum'],
                    'steps'      : addr['steps'],
                })
            addressings[uri] = addrs2

        return addressings

    def get_available_pages(self):
        if not self.hmi_show_empty_pages:
            return self.available_pages

        pages = self.available_pages.copy()
        rpages = self.available_pages.copy()
        rpages.reverse()
        for i in range(self.addressing_pages - rpages.index(True)):
            pages[i] = True

        return pages

    # -----------------------------------------------------------------------------------------------------------------

    # common function used in load() to finish waiting callbacks
    def _dont_wait_for_cc(self):
        self.waiting_for_cc = False
        for cb in self.waiting_for_cc_cbs:
            cb()
        self.waiting_for_cc_cbs = []

    def peek_for_momentary_toggles(self, bundlepath):
        datafile = os.path.join(bundlepath, "addressings.json")
        if not os.path.exists(datafile):
            return {}

        ret = {}
        data = safe_json_load(datafile, dict)
        for actuator_uri, addrs in data.items():
            # Special case for CV addressings
            if actuator_uri.startswith(CV_OPTION) and not actuator_uri.startswith(HW_CV_PREFIX):
                addrs = addrs['addrs']

            for addr in addrs:
                momentary = addr.get('momentary', None)
                if momentary is None or not isinstance(momentary, int):
                    continue

                instance   = addr['instance']
                portsymbol = addr['port']

                # momentary on
                if momentary == 1:
                    target = addr['maximum'] if portsymbol == ":bypass" else addr['minimum']
                # momentary off
                elif momentary == 2:
                    target = addr['minimum'] if portsymbol == ":bypass" else addr['maximum']
                else:
                    continue

                if not instance in ret:
                    ret[instance] = {}
                ret[instance][portsymbol] = target

        return ret

    @gen.coroutine
    def load(self, bundlepath, instances, skippedPorts, abort_catcher):
        # Check if this is the first time we load addressings (ie, first time mod-ui starts)
        first_load = self.first_load
        self.first_load = False

        # reset for load_current before fully loading addressings
        self.last_load_current_aborted = False
        self.pending_load_current = False

        # Check if pedalboard contains addressings first
        datafile = os.path.join(bundlepath, "addressings.json")
        if not os.path.exists(datafile):
            self._dont_wait_for_cc()
            return

        # Load addressings
        data = safe_json_load(datafile, dict)

        # Basic setup
        cc_initialized = self.cchain.initialized
        has_cc_addrs   = False
        retry_cc_addrs = False
        used_actuators = []
        hmi_widgets    = []

        # NOTE: We need to wait for Control Chain to finish initializing.
        #       Can take some time due to waiting for several device descriptors.
        #       We load everything that is possible first, then wait for Control Chain at the end if not ready yet.

        # Load all addressings possible
        for actuator_uri, addrs in data.items():
            actuator_type = self.get_actuator_type(actuator_uri)
            is_cc = actuator_type == self.ADDRESSING_TYPE_CC
            if is_cc:
                has_cc_addrs = True
                if not cc_initialized:
                    continue

            is_cv = actuator_type == self.ADDRESSING_TYPE_CV

            # Continue if current actuator_uri is not part of the actual available actuators (hardware, virtual bpm, cc or cv)
            if actuator_uri not in self.hw_actuators_uris and not is_cc and actuator_uri != kBpmURI and not is_cv:
                continue

            # Add addressed plugin cv port since it's not a hardware but pedalboard setup
            # plugin cv ports have the following structure:
            # { "/cv/graph/env/out": { "name": "Env Out", "addrs": [...] }} (instead of { "hmi/...": [...] })
            # because we need to save the port label even if nothing addressed to it
            is_hw_cv = self.is_hw_cv_port(actuator_uri)
            if is_cv and not is_hw_cv:
                self.cv_addressings[actuator_uri] = { 'name': addrs['name'], 'addrs': [] }
                addrs = addrs['addrs']

            i = 0
            for addr in addrs:
                instance   = addr['instance'].replace("/graph/","",1)
                portsymbol = addr['port']

                try:
                    instance_id, plugin_uri = instances[instance]
                except KeyError:
                    print("ERROR: An instance specified in addressings file is invalid")
                    i += 1
                    continue

                if len(skippedPorts) > 0 and instance+"/"+portsymbol in skippedPorts:
                    print("NOTE: An incompatible addressing has been skipped, port:", instance, portsymbol)
                    i += 1
                    continue

                page = addr.get('page', None)
                subpage = addr.get('subpage', None)

                if actuator_type == self.ADDRESSING_TYPE_HMI:
                    # Dealing with HMI addr from a pedalboard without subpages in a device with, or vice-versa
                    if subpage is None and self.has_hmi_subpages:
                        subpage = 0
                    elif subpage is not None and not self.has_hmi_subpages:
                        subpage = None

                    # Dealing with HMI addr from a pedalboard not supporting pages on a device supporting them
                    if self.addressing_pages and page is None:
                        if i < self.addressing_pages: # automatically assign the i-th assignment to page i
                            page = i
                        else: # cannot address more because we've reached the max nb of pages for current actuator
                            break

                coloured = addr.get('coloured', False)
                momentary = int(addr.get('momentary', 0))
                operational_mode = addr.get('operational_mode', '=')

                try:
                    curvalue = self._task_get_port_value(instance_id, portsymbol)
                except KeyError:
                    continue

                group = addr.get('group', None)
                addrdata = self.add(instance_id, plugin_uri, portsymbol, actuator_uri,
                                    addr['label'], addr['minimum'], addr['maximum'], addr['steps'], curvalue,
                                    addr.get('tempo'), addr.get('dividers'), page, subpage, group,
                                    coloured, momentary, operational_mode)

                if addrdata is not None:
                    stored_addrdata = addrdata.copy()
                    if group is not None: # if addressing is grouped, then store address data using group actuator uri
                        stored_addrdata['actuator_uri'] = group
                    self._task_store_address_data(instance_id, portsymbol, stored_addrdata)

                    if actuator_uri not in used_actuators:
                        used_actuators.append(actuator_uri)

                    if actuator_type == self.ADDRESSING_TYPE_HMI and not addr.get('tempo'):
                        hmi_widgets.append(addrdata)

                elif is_cc:
                    # Control Chain is initialized but addressing failed to load (likely due to missing hardware)
                    # Set this flag so we wait for devices later
                    retry_cc_addrs = True

                i += 1

        # Load HMI, Control Chain and CV addressings
        for actuator_uri in used_actuators:
            if abort_catcher is not None and abort_catcher.get('abort', False):
                print("WARNING: Abort triggered during addressings.load actuator requests, caller:", abort_catcher['caller'])
                return
            actuator_type = self.get_actuator_type(actuator_uri)
            if actuator_type == self.ADDRESSING_TYPE_HMI:
                try:
                    yield gen.Task(self.hmi_load_first, actuator_uri)
                except Exception as e:
                    logging.exception(e)
            elif actuator_type == self.ADDRESSING_TYPE_CC and cc_initialized:
                self.cc_load_all(actuator_uri)
            elif actuator_type == self.ADDRESSING_TYPE_CV:
                self.cv_load_all(actuator_uri)

        # Load HMI Widgets (needs to be done *after* HMI loads its addressings)
        if self._task_host_hmi_map:
            for addrdata in hmi_widgets:
                hw_id = self.hmi_uri2hw_map[addrdata['actuator_uri']]
                self.remap_host_hmi(hw_id, addrdata)

        # Load MIDI addressings
        # NOTE: MIDI addressings are not stored in addressings.json.
        #       They must be loaded by calling 'add_midi' before this `load` function.
        for actuator_uri, addressings in self.midi_addressings.items():
            for addressing in addressings:
                if abort_catcher is not None and abort_catcher.get('abort', False):
                    print("WARNING: Abort triggered during addressings.load MIDI requests, caller:", abort_catcher['caller'])
                    return
                # NOTE: label, value, steps and options missing, not needed or used for MIDI
                data = {
                    'instance_id': addressing['instance_id'],
                    'port'       : addressing['port'],
                    'minimum'    : addressing['minimum'],
                    'maximum'    : addressing['maximum'],
                    # MIDI specific
                    'midichannel': addressing['midichannel'],
                    'midicontrol': addressing['midicontrol'],
                }
                try:
                    yield gen.Task(self._task_addressing, self.ADDRESSING_TYPE_MIDI, actuator_uri, data)
                except Exception as e:
                    logging.exception(e)

        # Send available pages (ie with addressings) to hmi
        self.available_pages = []
        if self.addressing_pages:
            for i in range(self.addressing_pages):
                # Build default available_pages list
                if i == 0: # For the moment we always boot/load a pedalboard with first page
                    self.available_pages.append(True) # so it should always be available
                else:
                    self.available_pages.append(False)

                # Loop through HMI addressings
                def loop_addressings():
                    for uri, addrs in self.hmi_addressings.items():
                        for addr in addrs['addrs']:
                            if addr['page'] == i:
                                self.available_pages[i] = True
                                return

                loop_addressings()

            try:
                yield gen.Task(self._task_set_available_pages, self.get_available_pages())
            except Exception as e:
                logging.exception(e)

        # Unset retry flag if at least 1 Control Chain device is connected
        if retry_cc_addrs and len(self.cc_metadata) > 0:
            retry_cc_addrs = False

        # Check if we need to wait for Control Chain
        if not first_load or (cc_initialized and not retry_cc_addrs):
            self._dont_wait_for_cc()
            return

        if retry_cc_addrs:
            # Wait for any Control Chain devices to appear, with 10s maximum time-out
            print("NOTE: Waiting for Control Chain devices to appear")
            for i in range(10):
                yield gen.sleep(1)
                if len(self.cc_metadata) > 0 and self.cchain.initialized:
                    break

        elif not self.cchain.initialized:
            # Control Chain was not initialized yet by this point, wait for it
            # 'wait_initialized' will time-out in 10s if nothing happens
            print("NOTE: Waiting for Control Chain to initialize")
            try:
                yield gen.Task(self.cchain.wait_initialized)
            except Exception as e:
                logging.exception(e)

        self._dont_wait_for_cc()

        # Don't bother continuing if there are no Control Chain addressesings
        if not has_cc_addrs:
            return

        # Don't bother continuing if there are no Control Chain devices available
        if len(self.cc_metadata) == 0:
            print("WARNING: Pedalboard has Control Chain addressings but no devices are available")
            return

        # reset used actuators, only load for those that succeed
        used_actuators = []

        # Re-do the same as we did above
        for actuator_uri, addrs in data.items():
            if abort_catcher is not None and abort_catcher.get('abort', False):
                print("WARNING: Abort triggered during addressings.load CC requests, caller:", abort_catcher['caller'])
                return
            if self.get_actuator_type(actuator_uri) != self.ADDRESSING_TYPE_CC:
                continue
            for addr in addrs:
                instance   = addr['instance'].replace("/graph/","",1)
                portsymbol = addr['port']

                try:
                    instance_id, plugin_uri = instances[instance]
                except KeyError:
                    print("ERROR: An instance specified in addressings file is invalid")
                    continue

                if len(skippedPorts) > 0 and instance+"/"+portsymbol in skippedPorts:
                    print("NOTE: An incompatible addressing has been skipped, port:", instance, portsymbol)
                    continue

                try:
                    curvalue = self._task_get_port_value(instance_id, portsymbol)
                except KeyError:
                    continue

                addrdata = self.add(instance_id, plugin_uri, portsymbol, actuator_uri,
                                    addr['label'], addr['minimum'], addr['maximum'], addr['steps'], curvalue)

                if addrdata is not None:
                    self._task_store_address_data(instance_id, portsymbol, addrdata)

                    if actuator_uri not in used_actuators:
                        used_actuators.append(actuator_uri)

        for actuator_uri in used_actuators:
            self.cc_load_all(actuator_uri)

    def save(self, bundlepath, instances):
        addressings = {}

        # HMI
        for uri, addrs in self.hmi_addressings.items():
            addrs2 = []
            for addr in addrs['addrs']:
                instance = instances.get(addr['instance_id'], None)
                if instance is None:
                    continue
                addrs2.append({
                    'instance': instance,
                    'port'    : addr['port'],
                    'label'   : addr['label'],
                    'minimum' : addr['minimum'],
                    'maximum' : addr['maximum'],
                    'steps'   : addr['steps'],
                    'tempo'   : addr.get('tempo'),
                    'dividers': addr.get('dividers'),
                    'page'    : addr.get('page'),
                    'subpage' : addr.get('subpage'),
                    'group'   : addr.get('group'),
                    'coloured': addr.get('coloured', False),
                    'momentary': int(addr.get('momentary', 0)),
                })
            addressings[uri] = addrs2

        # Control Chain
        for uri, addrs in self.cc_addressings.items():
            addrs2 = []
            for addr in addrs:
                instance = instances.get(addr['instance_id'], None)
                if instance is None:
                    continue
                addrs2.append({
                    'instance': instance,
                    'port'    : addr['port'],
                    'label'   : addr['label'],
                    'minimum' : addr['minimum'],
                    'maximum' : addr['maximum'],
                    'steps'   : addr['steps'],
                    'coloured': addr.get('coloured', False),
                    'momentary': int(addr.get('momentary', 0)),
                })
            addressings[uri] = addrs2

        # Virtual actuator (only /bpm for now)
        for uri, addrs in self.virtual_addressings.items():
            addrs2 = []
            for addr in addrs:
                instance = instances.get(addr['instance_id'], None)
                if instance is None:
                    continue
                addrs2.append({
                    'instance': instance,
                    'port'    : addr['port'],
                    'label'   : addr['label'],
                    'minimum' : addr['minimum'],
                    'maximum' : addr['maximum'],
                    'steps'   : addr['steps'],
                    'tempo'   : addr.get('tempo'),
                    'dividers': addr.get('dividers'),
                    'page'    : addr.get('page')
                })
            addressings[uri] = addrs2

        # CV
        for uri, addrs in self.cv_addressings.items():
            if self.is_hw_cv_port(uri):
                addrs2 = []
                for addr in addrs:
                    instance = instances.get(addr['instance_id'], None)
                    if instance is None:
                        continue
                    addrs2.append({
                        'instance'        : instance,
                        'port'            : addr['port'],
                        'label'           : addr['label'],
                        'minimum'         : addr['minimum'],
                        'maximum'         : addr['maximum'],
                        'steps'           : addr['steps'],
                        'operational_mode': addr['operational_mode'],
                    })
            else: # plugin cv ports, different structure to save name as well
                addrs2 = { 'name': addrs['name'], 'addrs': [] }
                for addr in addrs['addrs']:
                    instance = instances.get(addr['instance_id'], None)
                    if instance is None:
                        continue
                    addrs2['addrs'].append({
                        'instance'        : instance,
                        'port'            : addr['port'],
                        'label'           : addr['label'],
                        'minimum'         : addr['minimum'],
                        'maximum'         : addr['maximum'],
                        'steps'           : addr['steps'],
                        'operational_mode': addr['operational_mode'],
                    })
            addressings[uri] = addrs2

        # Write addressings to disk
        with TextFileFlusher(os.path.join(bundlepath, "addressings.json")) as fh:
            json.dump(addressings, fh, indent=4)

    def registerMappings(self, msg_callback, instances):
        # CV plugin ports
        for actuator_uri, addrs in self.cv_addressings.items():
            # pluginData = self._task_get_plugin_data(instance_id)
            if not self.is_hw_cv_port(actuator_uri):
                operational_mode = self._task_get_plugin_cv_port_op_mode(actuator_uri)
                msg_callback("add_cv_port %s %s %s" % (actuator_uri, addrs['name'].replace(" ","_"), operational_mode))

        # HMI
        group_mappings = [] #{} if self.addressing_pages else []
        for uri, addrs in self.hmi_addressings.items():
            for addr in addrs['addrs']:
                addr_uri = uri
                dividers = "{0}".format(addr.get('dividers', "null")).replace(" ", "").replace("None", "null")
                page = "{0}".format(addr.get('page', "null")).replace("None", "null")
                subpage = "{0}".format(addr.get('subpage', "null")).replace("None", "null")
                group = "{0}".format(addr.get('group', "null")).replace("None", "null")
                send_hw_map = True
                if addr.get('group') is not None:
                    addr_uri = group
                    group_mapping = {'uri': group, 'page': addr.get('page')}
                    if group_mapping not in group_mappings:
                        group_mappings.append({'uri': group, 'page': addr.get('page')})
                        send_hw_map = False # Register harware group mapping only once
                if addr.get('group') is None or send_hw_map:
                    instance = instances.get(addr['instance_id'], None)
                    if instance is None:
                        continue
                    args = (instance,
                            addr['port'],
                            addr_uri,
                            addr['minimum'],
                            addr['maximum'],
                            addr['steps'],
                            addr['label'].replace(" ","_"),
                            addr.get('tempo', False),
                            dividers,
                            page,
                            subpage,
                            group,
                            int(addr.get('coloured', False)),
                            int(addr.get('momentary', 0)))
                    msg_callback("hw_map %s %s %s %f %f %d %s %s %s %s %s %s 1 %d %d" % args)

        # Virtual addressings (/bpm)
        for uri, addrs in self.virtual_addressings.items():
            for addr in addrs:
                instance = instances.get(addr['instance_id'], None)
                if instance is None:
                    continue
                dividers = "{0}".format(addr.get('dividers', "null")).replace(" ", "").replace("None", "null")
                page = "{0}".format(addr.get('page', "null")).replace("None", "null")
                args = (instance,
                        addr['port'],
                        uri,
                        addr['minimum'],
                        addr['maximum'],
                        addr['steps'],
                        addr['label'].replace(" ","_"),
                        addr.get('tempo', False),
                        dividers,
                        page)
                msg_callback("hw_map %s %s %s %f %f %d %s %s %s %s null null 1 0 0" % args)

        # Control Chain
        for uri, addrs in self.cc_addressings.items():
            feedback = int(self.cc_metadata[uri]['feedback'])
            for addr in addrs:
                instance = instances.get(addr['instance_id'], None)
                if instance is None:
                    continue
                args = (instance,
                        addr['port'],
                        uri,
                        addr['minimum'],
                        addr['maximum'],
                        addr['steps'],
                        addr['label'].replace(" ","_"),
                        feedback,
                        int(addr.get('coloured', False)),
                        int(addr.get('momentary', 0)))
                msg_callback("hw_map %s %s %s %f %f %d %s False null null null null %d %d %d" % args)

        # MIDI
        for uri, addrs in self.midi_addressings.items():
            for addr in addrs:
                instance = instances.get(addr['instance_id'], None)
                if instance is None:
                    continue
                msg_callback("midi_map %s %s %i %i %f %f" % (instance,
                                                             addr['port'],
                                                             addr['midichannel'],
                                                             addr['midicontrol'],
                                                             addr['minimum'],
                                                             addr['maximum']))

        # CV
        for uri, addrs in self.cv_addressings.items():
            if not self.is_hw_cv_port(uri):
                addrs = addrs['addrs']
            for addr in addrs:
                instance = instances.get(addr['instance_id'], None)
                if instance is None:
                    continue
                msg_callback("cv_map %s %s %s %f %f %s %s 0" % (instance,
                                                                addr['port'],
                                                                uri,
                                                                addr['minimum'],
                                                                addr['maximum'],
                                                                addr['label'].replace(" ","_"),
                                                                addr.get('operational_mode')))

    # -----------------------------------------------------------------------------------------------------------------

    def add(self, instance_id, plugin_uri, portsymbol, actuator_uri, label, minimum, maximum, steps, value,
            tempo=False, dividers=None, page=None, subpage=None, group=None, coloured=None, momentary=None,
            operational_mode=None):
        actuator_type = self.get_actuator_type(actuator_uri)
        if actuator_type not in (self.ADDRESSING_TYPE_HMI, self.ADDRESSING_TYPE_CC, self.ADDRESSING_TYPE_BPM, self.ADDRESSING_TYPE_CV):
            print("ERROR: Trying to address the wrong way, stop!")
            return None

        unit = "none"
        options = []
        pprops = []

        if portsymbol == ":presets":
            data = self.get_presets_as_options(instance_id)

            if data is None:
                return None

            value, maximum, options, spreset = data
            minimum = 0
            steps = maximum - 1

        elif instance_id == PEDALBOARD_INSTANCE_ID:
            if portsymbol == ":bpb":
                pprops = ["integer"]
                unit = "/4"

            elif portsymbol == ":bpm":
                pprops = ["integer", "tapTempo"]
                unit = "BPM"

            elif portsymbol == ":rolling":
                pprops = ["toggled"]

            else:
                print("ERROR: Trying to address wrong pedalboard port:", portsymbol)
                return None

        elif portsymbol != ":bypass":
            for port_info in get_plugin_control_inputs(plugin_uri):
                if port_info["symbol"] == portsymbol:
                    break
            else:
                print("ERROR: Trying to address non-existing control port '%s'" % (portsymbol))
                return None

            # useful info about this port
            pprops = port_info["properties"]

            if "symbol" in port_info["units"].keys():
                unit = port_info["units"]["symbol"]

            if "enumeration" in pprops and len(port_info["scalePoints"]) > 0:
                options = [(sp["value"], sp["label"]) for sp in port_info["scalePoints"]]

            # Load tap tempo addressings as tempo divider (1/4)
            if not tempo and "tapTempo" in pprops and actuator_uri.startswith("/hmi/footswitch"):
                tempo = True
                dividers = 4

            if tempo:
                divider_options = get_divider_options(port_info, 20.0, 280.0) # XXX min and max bpm hardcoded
                options_list = [opt['value'] for opt in divider_options]
                # Set min and max to min and max value among dividers
                minimum = min(options_list)
                maximum = max(options_list)
                steps   = len(options_list) - 1
                options = [(o["value"], o["label"]) for o in divider_options]

        # TODO do something with spreset

        addressing_data = {
            'actuator_uri': actuator_uri,
            'instance_id' : instance_id,
            'port'        : portsymbol,
            'label'       : label,
            'value'       : value,
            'minimum'     : minimum,
            'maximum'     : maximum,
            'steps'       : steps,
            'unit'        : unit,
            'options'     : options,
            'tempo'       : tempo,
            'dividers'    : dividers,
            'page'        : page,
            'subpage'     : subpage,
            'group'       : group,
            'coloured'    : coloured,
            'momentary'   : momentary,
            'operational_mode': operational_mode,
        }

        if tempo or "enumeration" in pprops and len(port_info["scalePoints"]) > 0:
            if not tempo and value not in [o[0] for o in options]:
                print("WARNING: current value '%f' for '%s' is not a valid scalepoint" % (value, portsymbol))
                addressing_data['value'] = get_nearest_valid_scalepoint_value(value, options)[1]

        # -------------------------------------------------------------------------------------------------------------

        if actuator_type == self.ADDRESSING_TYPE_HMI:
            if portsymbol == ":bypass":
                hmitype = FLAG_CONTROL_BYPASS
                if momentary:
                    hmitype |= FLAG_CONTROL_MOMENTARY
                    if momentary == 2:
                        hmitype |= FLAG_CONTROL_REVERSE

            elif portsymbol == ":presets":
                hmitype = FLAG_CONTROL_ENUMERATION|FLAG_CONTROL_SCALE_POINTS|FLAG_CONTROL_INTEGER

            else:
                if "toggled" in pprops:
                    hmitype = FLAG_CONTROL_TOGGLED
                    if momentary:
                        hmitype |= FLAG_CONTROL_MOMENTARY
                        if momentary == 2:
                            hmitype |= FLAG_CONTROL_REVERSE
                elif "integer" in pprops:
                    hmitype = FLAG_CONTROL_INTEGER
                else:
                    hmitype = 0x0 # linear, fallback mode

                if "logarithmic" in pprops:
                    hmitype |= FLAG_CONTROL_LOGARITHMIC
                if "trigger" in pprops:
                    hmitype |= FLAG_CONTROL_TRIGGER

                if portsymbol == ":bpm" and "tapTempo" in pprops and actuator_uri.startswith("/hmi/footswitch"):
                    hmitype |= FLAG_CONTROL_TAP_TEMPO

                if tempo or "enumeration" in pprops and len(port_info["scalePoints"]) > 0:
                    hmitype |= FLAG_CONTROL_ENUMERATION|FLAG_CONTROL_SCALE_POINTS

            # first actuator in group should have reverse enum hmi type
            if group is not None:
                group_actuator = next((act for act in self.hw_actuators if act['uri'] == group), None)
                if group_actuator is not None:
                    if group_actuator['actuator_group'].index(actuator_uri) == 0:
                        hmitype |= FLAG_CONTROL_REVERSE
                    else:
                        hmitype &= ~FLAG_CONTROL_REVERSE

            # hmi specific
            addressing_data['hmitype'] = hmitype

            addressings = self.hmi_addressings[actuator_uri]
            # if old_hmi_index is False:
            addressings['idx'] = len(addressings['addrs'])
            addressings['addrs'].append(addressing_data)
            # else:
            #     addressings['addrs'].insert(old_hmi_index, addressing_data)

        elif actuator_type == self.ADDRESSING_TYPE_BPM:
            addressings = self.virtual_addressings[actuator_uri]

            # make sure to not add the same addressing more than once
            for i, addr in enumerate(addressings):
                if addressing_data['actuator_uri'] != addr['actuator_uri']:
                    continue
                if addressing_data['instance_id'] != addr['instance_id']:
                    continue
                if addressing_data['port'] != addr['port']:
                    continue
                return None

            addressings.append(addressing_data)

        elif actuator_type == self.ADDRESSING_TYPE_CC:
            if actuator_uri not in self.cc_addressings.keys():
                print("ERROR: Can't load addressing for unavailable hardware '%s'" % actuator_uri)
                return None

            if portsymbol == ":bypass":
                cctype = CC_MODE_TOGGLE|CC_MODE_INTEGER
                if momentary:
                    cctype |= CC_MODE_MOMENTARY
                    if momentary == 2:
                        cctype |= CC_MODE_REVERSE

            elif portsymbol == ":presets":
                cctype = CC_MODE_OPTIONS|CC_MODE_INTEGER
                if coloured:
                    cctype |= CC_MODE_COLOURED

            else:
                if "toggled" in pprops:
                    cctype = CC_MODE_TOGGLE
                    if momentary:
                        cctype |= CC_MODE_MOMENTARY
                        if momentary == 2:
                            cctype |= CC_MODE_REVERSE
                elif "integer" in pprops:
                    cctype = CC_MODE_INTEGER
                else:
                    cctype = CC_MODE_REAL

                if "logarithmic" in pprops:
                    cctype |= CC_MODE_LOGARITHMIC
                if "trigger" in pprops:
                    cctype |= CC_MODE_TRIGGER

                if portsymbol == ":bpm" and "tapTempo" in pprops:
                    cctype |= CC_MODE_TAP_TEMPO

                if tempo or "enumeration" in pprops and len(port_info["scalePoints"]) > 0:
                    cctype |= CC_MODE_OPTIONS
                    if coloured:
                        cctype |= CC_MODE_COLOURED

            # CC specific
            addressing_data['cctype'] = cctype

            addressings = self.cc_addressings[actuator_uri]
            addressings.append(addressing_data)

        elif actuator_type == self.ADDRESSING_TYPE_CV:
            if actuator_uri not in self.cv_addressings.keys():
                print("ERROR: Can't load addressing for unavailable hardware '%s'" % actuator_uri)
                return None
            addressings = self.cv_addressings[actuator_uri]
            if self.is_hw_cv_port(actuator_uri):
                addressings.append(addressing_data)
            else:
                # plugin cv ports addressings have the following structure:
                # { "name": "Env out", "addrs": [...] }
                addressings['addrs'].append(addressing_data)

        return addressing_data

    def add_midi(self, instance_id, portsymbol, midichannel, midicontrol, minimum, maximum):
        actuator_uri = self.create_midi_cc_uri(midichannel, midicontrol)

        # NOTE: label, value, steps and options missing, not needed or used for MIDI
        addressing_data = {
            'actuator_uri': actuator_uri,
            'instance_id' : instance_id,
            'port'        : portsymbol,
            'minimum'     : minimum,
            'maximum'     : maximum,
            # MIDI specific
            'midichannel' : midichannel,
            'midicontrol' : midicontrol,
        }

        if actuator_uri not in self.midi_addressings.keys():
            self.midi_addressings[actuator_uri] = []

        addressings = self.midi_addressings[actuator_uri]
        addressings.append(addressing_data)

        return addressing_data

    def load_addr(self, actuator_uri, addressing_data, callback, send_hmi=True):
        addressing_data = addressing_data.copy()

        actuator_hw   = actuator_uri
        actuator_type = self.get_actuator_type(actuator_uri)

        def hmi_map_callback(resp):
            self.remap_host_hmi(actuator_hw, addressing_data)
            if callback is not None:
                callback(resp)

        shouldRemap = actuator_type == self.ADDRESSING_TYPE_HMI and not addressing_data.get('tempo', False)
        rcallback = hmi_map_callback if shouldRemap else callback

        if actuator_type == self.ADDRESSING_TYPE_HMI:
            try:
                actuator_hw      = self.hmi_uri2hw_map[actuator_uri]
                actuator_subpage = self.hmi_hwsubpages[actuator_hw]
            except KeyError:
                if rcallback is not None:
                    rcallback(False)
                print("ERROR: Why fail the hardware/URI mapping? Hardcoded number of actuators?")
                return

            if self.addressing_pages:
                # if new addressing page is not the same as the currently displayed page
                if self.current_page != addressing_data['page'] or actuator_subpage != addressing_data['subpage']:
                    # then no need to send control_add to hmi
                    if rcallback is not None:
                        rcallback(True)
                    return
            else:
                # HMI specific
                addressings = self.hmi_addressings[actuator_uri]
                addressing_data['addrs_idx'] = addressings['idx']+1
                addressing_data['addrs_max'] = len(addressings['addrs'])

        elif actuator_type == self.ADDRESSING_TYPE_CC:
            actuator_hw = self.cc_metadata[actuator_uri]['hw_id']

        self._task_addressing(actuator_type, actuator_hw, addressing_data, rcallback, send_hmi=send_hmi)

    def was_last_load_current_aborted(self):
        ret = self.last_load_current_aborted or self.pending_load_current
        self.last_load_current_aborted = False
        return ret

    def load_current_with_callback(self, actuator_uris, skippedPort, updateValue, from_hmi, abort_catcher, callback):
        self.load_current(actuator_uris, skippedPort, updateValue, from_hmi, abort_catcher, callback)

    @gen.coroutine
    def load_current(self, actuator_uris, skippedPort, updateValue, from_hmi, abort_catcher, callback=None):
        self.pending_load_current = True

        for actuator_uri in actuator_uris:
            if abort_catcher.get('abort', False):
                self.last_load_current_aborted = True
                self.pending_load_current = False
                if callback is not None:
                    callback(False)
                print("WARNING: Abort triggered during load_current request, caller:", abort_catcher['caller'])
                return

            actuator_type = self.get_actuator_type(actuator_uri)

            if actuator_type == Addressings.ADDRESSING_TYPE_HMI:
                # if the request comes from HMI, we cannot wait for HMI stuff, as otherwise we stall
                if from_hmi:
                    self.hmi_load_current(actuator_uri, None, skippedPort, updateValue)
                else:
                    try:
                        yield gen.Task(self.hmi_load_current, actuator_uri, skippedPort=skippedPort, updateValue=updateValue)
                    except Exception as e:
                        logging.exception(e)

            elif actuator_type == Addressings.ADDRESSING_TYPE_CC:
                actuator_cc = self.cc_metadata[actuator_uri]['hw_id']
                feedback    = self.cc_metadata[actuator_uri]['feedback']
                addressings = self.cc_addressings[actuator_uri]

                for addressing in addressings:
                    if (addressing['instance_id'], addressing['port']) == skippedPort:
                        continue
                    if abort_catcher.get('abort', False):
                        self.last_load_current_aborted = True
                        self.pending_load_current = False
                        if callback is not None:
                            callback(False)
                        print("WARNING: Abort triggered in CC loop during load_current request, caller:",
                              abort_catcher['caller'])
                        return

                    # reload value
                    addressing['value'] = self._task_get_port_value(addressing['instance_id'], addressing['port'])

                    # NOTE we never call `value_set` for CC lists, as it breaks pagination
                    if feedback and (addressing['cctype'] & CC_MODE_OPTIONS) == 0x0:
                        try:
                            yield gen.Task(self._task_set_value, self.ADDRESSING_TYPE_CC, actuator_cc, addressing)
                        except Exception as e:
                            logging.exception(e)
                    else:
                        try:
                            yield gen.Task(self._task_unaddressing, self.ADDRESSING_TYPE_CC,
                                           addressing['instance_id'], addressing['port'])
                            yield gen.Task(self._task_addressing, self.ADDRESSING_TYPE_CC, actuator_cc, addressing)
                        except Exception as e:
                            logging.exception(e)

        self.pending_load_current = False

        if callback is not None:
            callback(True)

    def remove_hmi(self, addressing_data, actuator_uri):
        addressings       = self.hmi_addressings[actuator_uri]
        actuator_hmi      = self.hmi_uri2hw_map[actuator_uri]
        actuator_subpage  = self.hmi_hwsubpages[actuator_hmi]
        addressings_addrs = addressings['addrs']

        actuator_uri = addressing_data['actuator_uri']
        instance_id = addressing_data['instance_id']
        portsymbol = addressing_data['port']

        if self.addressing_pages:
            was_assigned = self.is_page_assigned(addressings_addrs, self.current_page, actuator_subpage)

        for i, addr in enumerate(addressings_addrs):
            if actuator_uri != addr['actuator_uri']:
                continue
            if instance_id != addr['instance_id']:
                continue
            if portsymbol != addr['port']:
                continue
            index = i
            addressings_addrs.pop(index)
            break
        else:
            return False

        if self._task_host_hmi_unmap is not None:
            self._task_host_hmi_unmap(instance_id, portsymbol)

        if self.addressing_pages:
            return was_assigned

        old_idx = addressings['idx']
        if old_idx != 0 or (old_idx == 0 and not len(addressings_addrs)):
            addressings['idx'] -= 1

        return True

    def remove_cc(self, addressing_data, actuator_uri):
        addressings = self.cc_addressings[actuator_uri]

        instance_id = addressing_data['instance_id']
        portsymbol = addressing_data['port']

        for i, addr in enumerate(addressings):
            if actuator_uri != addr['actuator_uri']:
                continue
            if instance_id != addr['instance_id']:
                continue
            if portsymbol != addr['port']:
                continue
            addressings.pop(i)
            break

    def remove_virtual(self, addressing_data, actuator_uri):
        addressings = self.virtual_addressings[actuator_uri]

        instance_id = addressing_data['instance_id']
        portsymbol = addressing_data['port']

        for i, addr in enumerate(addressings):
            if actuator_uri != addr['actuator_uri']:
                continue
            if instance_id != addr['instance_id']:
                continue
            if portsymbol != addr['port']:
                continue
            addressings.pop(i)
            break

    # NOTE: make sure to call hmi_load_current() afterwards if removing HMI addressings
    def remove(self, addressing_data):
        actuator_uri  = addressing_data['actuator_uri']
        actuator_type = self.get_actuator_type(actuator_uri)

        if actuator_type == self.ADDRESSING_TYPE_HMI:
            group_actuators = self.get_group_actuators(actuator_uri)
            if group_actuators is not None:
                for i in range(len(group_actuators)):
                    group_actuator_uri = group_actuators[i]
                    group_addressing_data = addressing_data.copy()
                    group_addressing_data['actuator_uri'] = group_actuator_uri
                    if i == 0: # first actuator has reverse enum hmi type
                        group_addressing_data['hmitype'] |= FLAG_CONTROL_REVERSE
                    else:
                        group_addressing_data['hmitype'] &= ~FLAG_CONTROL_REVERSE
                    was_active = self.remove_hmi(group_addressing_data, group_actuator_uri)
                return was_active

            else:
                return self.remove_hmi(addressing_data, actuator_uri)

        elif actuator_type == self.ADDRESSING_TYPE_CC:
            self.remove_cc(addressing_data, actuator_uri)

        elif actuator_type == self.ADDRESSING_TYPE_MIDI:
            addressings = self.midi_addressings[actuator_uri]
            addressings.remove(addressing_data)

        elif actuator_type == self.ADDRESSING_TYPE_BPM:
            self.remove_virtual(addressing_data, actuator_uri)

        elif actuator_type == self.ADDRESSING_TYPE_CV:
            addressings = self.cv_addressings[actuator_uri]
            if self.is_hw_cv_port(actuator_uri):
                addressings.remove(addressing_data)
            else:
                addressings['addrs'].remove(addressing_data)

    def update_for_snapshots(self, actuator_uri, instance_id, portsymbol, newdata):
        actuator_type = self.get_actuator_type(actuator_uri)

        if actuator_type == self.ADDRESSING_TYPE_HMI:
            addressings = self.hmi_addressings[actuator_uri]['addrs']
        elif actuator_type == self.ADDRESSING_TYPE_CC:
            addressings = self.cc_addressings[actuator_uri]
        else:
            return

        for addr in addressings:
            if actuator_uri != addr['actuator_uri']:
                continue
            if instance_id != addr['instance_id']:
                continue
            if portsymbol != addr['port']:
                continue
            addr.update(newdata)
            return

    def is_page_assigned(self, addrs, page, subpage):
        return any('page' in a and a['page'] == page and a['subpage'] == subpage for a in addrs)

    def get_addressing_for_page(self, addrs, page, subpage):
        # Assumes is_page_assigned(addrs, page) has returned True
        return next(a for a in addrs if 'page' in a and a['page'] == page and a['subpage'] == subpage)

    # -----------------------------------------------------------------------------------------------------------------
    # HMI specific functions

    def hmi_load_current(self, actuator_uri, callback,
                         skippedPort = (None, None), updateValue = False, send_hmi = True, newValue = None):
        actuator_hmi      = self.hmi_uri2hw_map[actuator_uri]
        actuator_subpage  = self.hmi_hwsubpages[actuator_hmi]
        addressings       = self.hmi_addressings[actuator_uri]
        addressings_addrs = addressings['addrs']
        addressings_len   = len(addressings['addrs'])

        if addressings_len == 0:
            print("T2 addressings_len == 0")
            if callback is not None:
                callback(False)
            return

        if self.addressing_pages: # device supports pages
            current_page_assigned = self.is_page_assigned(addressings_addrs, self.current_page, actuator_subpage)
            if not current_page_assigned:
                if callback is not None:
                    callback(False)
                return
            else:
                addressing_data = self.get_addressing_for_page(addressings_addrs, self.current_page, actuator_subpage)
                if (addressing_data['instance_id'], addressing_data['port']) == skippedPort:
                    print("skippedPort", skippedPort)
                    if callback is not None:
                        callback(True)
                    return

                if newValue is not None:
                    addressing_data['value'] = newValue
                else:
                    try:
                        addressing_data['value'] = self._task_get_port_value(addressing_data['instance_id'],
                                                                             addressing_data['port'])
                    except KeyError:
                        if callback is not None:
                            callback(False)
                        return

                if addressing_data.get('tempo', False):
                    dividers = self._task_get_tempo_divider(addressing_data['instance_id'],
                                                            addressing_data['port'])
                    addressing_data['dividers'] = dividers

        else:
            addressings_idx = addressings['idx']
            if addressings_len == addressings_idx:
                canSkipAddressing = False
                addressings['idx'] = addressings_idx = addressings_len - 1
            else:
                canSkipAddressing = True

            # current addressing data
            addressing_data = addressings_addrs[addressings_idx].copy()

            if canSkipAddressing and (addressing_data['instance_id'], addressing_data['port']) == skippedPort:
                print("skippedPort", skippedPort)
                if callback is not None:
                    callback(True)
                return

            # needed fields for addressing task
            addressing_data['addrs_idx'] = addressings_idx+1
            addressing_data['addrs_max'] = addressings_len

            # reload value
            addressing = addressings_addrs[addressings_idx]
            if newValue is None:
                try:
                    newValue = self._task_get_port_value(addressing['instance_id'], addressing['port'])
                except KeyError:
                    if callback is not None:
                        callback(False)
                    return

            addressing['value'] = addressing_data['value'] = newValue

            if addressing_data.get('tempo', False):
                dividers = self._task_get_tempo_divider(addressing['instance_id'], addressing['port'])
                addressing['dividers'] = addressing_data['dividers'] = dividers

        # NOTE we never call `control_set` for HMI lists, as it breaks pagination
        if updateValue and not (addressing_data['hmitype'] & FLAG_CONTROL_ENUMERATION):
            self._task_set_value(self.ADDRESSING_TYPE_HMI, actuator_hmi, addressing_data, callback, send_hmi=send_hmi)
        else:
            self._task_addressing(self.ADDRESSING_TYPE_HMI, actuator_hmi, addressing_data, callback, send_hmi=send_hmi)

    def hmi_load_footswitches(self, callback):
        def footswitch1_callback(_):
            self.hmi_load_current("/hmi/footswitch2", callback)

        self.hmi_load_current("/hmi/footswitch1", footswitch1_callback)

    def hmi_load_first(self, actuator_uri, callback):
        addressings     = self.hmi_addressings[actuator_uri]
        addressings_len = len(addressings['addrs'])

        if addressings_len == 0:
            print("addressings_len == 0")
            callback(False)
            return

        # jump to first addressing or page
        addressings['idx'] = 0
        self.current_page = 0

        # ready to load
        self.hmi_load_current(actuator_uri, callback)

    def hmi_load_next_hw(self, hw_id):
        actuator_uri    = self.hmi_hw2uri_map[hw_id]
        addressings     = self.hmi_addressings[actuator_uri]
        addressings_len = len(addressings['addrs'])

        if addressings_len == 0:
            print("ERROR: hmi_load_next_hw failed, empty list")
            return

        # jump to next available addressing
        addressings['idx'] = (addressings['idx'] + 1) % addressings_len

        # ready to load
        self.hmi_load_current(actuator_uri, None)

    def hmi_load_subpage(self, hw_id, subpage):
        actuator_uri    = self.hmi_hw2uri_map[hw_id]
        addressings     = self.hmi_addressings[actuator_uri]
        addressings_len = len(addressings['addrs'])

        # set actuator page
        self.hmi_hwsubpages[hw_id] = subpage

        # ready to load
        self.hmi_load_current(actuator_uri, None)

    def hmi_get_addr_data(self, hw_id):
        actuator_uri      = self.hmi_hw2uri_map[hw_id]
        actuator_subpage  = self.hmi_hwsubpages[hw_id]
        addressings       = self.hmi_addressings[actuator_uri]
        addressings_addrs = addressings['addrs']
        addressings_len   = len(addressings_addrs)

        if addressings_len == 0:
            print("ERROR: hmi_get_addr_data failed, empty list")
            return None

        if self.addressing_pages: # device supports pages
            if not self.is_page_assigned(addressings_addrs, self.current_page, actuator_subpage):
                return None
            return self.get_addressing_for_page(addressings_addrs, self.current_page, actuator_subpage)

        else:
            return addressings_addrs[addressings['idx']]

    # def hmi_load_next_page(self, page_to_load, callback):

    def remap_host_hmi(self, hw_id, data):
        if self._task_host_hmi_map is None:
            return

        page = data['page'] or 0
        subpage = data['subpage'] or 0
        label = data['label']
        hmitype = data['hmitype']

        if data.get('group', None) is not None and self.hmi_show_actuator_group_prefix:
            if hmitype & FLAG_CONTROL_REVERSE:
                prefix = "- "
            else:
                prefix = "+ "
            label = prefix + label

        label = normalize_for_hw(label)

        hostcaps = 0x0
        for actuator in self.hw_actuators:
            if actuator['id'] != hw_id:
                continue
            widgets = actuator.get('widgets', None)
            if widgets is None:
                break
            if "led" in widgets:
                hostcaps |= LV2_HMI_AddressingCapability_LED
            if "label" in widgets:
                hostcaps |= LV2_HMI_AddressingCapability_Label
            if "value" in widgets:
                hostcaps |= LV2_HMI_AddressingCapability_Value
            if "unit" in widgets:
                hostcaps |= LV2_HMI_AddressingCapability_Unit
            if "indicator" in widgets:
                hostcaps |= LV2_HMI_AddressingCapability_Indicator
            break

        hostflags = 0x0
        if data.get('coloured', False):
            hostflags |= LV2_HMI_AddressingFlag_Coloured
        if hmitype & FLAG_CONTROL_MOMENTARY:
            hostflags |= LV2_HMI_AddressingFlag_Momentary
        if hmitype & FLAG_CONTROL_REVERSE:
            hostflags |= LV2_HMI_AddressingFlag_Reverse
        if hmitype & FLAG_CONTROL_TAP_TEMPO:
            hostflags |= LV2_HMI_AddressingFlag_TapTempo

        self._task_host_hmi_map(data['instance_id'], data['port'], hw_id, page, subpage,
                                hostcaps, hostflags, label, data['minimum'], data['maximum'], data['steps'])

    # -----------------------------------------------------------------------------------------------------------------
    # Control Chain specific functions

    def cc_hardware_added(self, dev_id, dev_uri, label, labelsuffix, version):
        print("cc_hardware_added", dev_id, dev_uri, label, labelsuffix, version)
        self._task_hw_added(dev_uri, label, labelsuffix, version)

    def cc_hardware_removed(self, dev_id, dev_uri, label, version):
        removed_actuators = []

        for actuator in self.cc_metadata.values():
            if actuator['hw_id'][0] == dev_id:
                removed_actuators.append(actuator['uri'])

        for actuator_uri in removed_actuators:
            print("cc_actuator_removed", actuator_uri)
            self.cc_metadata.pop(actuator_uri)
            self.cc_addressings.pop(actuator_uri)
            self._task_act_removed(actuator_uri)

        print("cc_hardware_removed", dev_id, dev_uri, label, version)
        self._task_hw_removed(dev_uri, label, version)

    def cc_hardware_connected(self, label, version):
        print("cc_hardware_connected", label, version)
        self._task_hw_connected(label, version)

    def cc_hardware_disconnected(self, label, version):
        print("cc_hardware_disconnected", label, version)
        self._task_hw_disconnected(label, version)

    def cc_actuator_added(self, dev_id, actuator_id, metadata):
        print("cc_actuator_added", metadata['uri'])
        actuator_uri = metadata['uri']

        if actuator_uri in self.cc_metadata:
            self.cc_metadata[actuator_uri]['hw_id'] = (dev_id, actuator_id)
            self.cc_load_all(actuator_uri)
        else:
            self.cc_metadata[actuator_uri] = metadata.copy()
            self.cc_metadata[actuator_uri]['hw_id'] = (dev_id, actuator_id)
            self.cc_addressings[actuator_uri] = []
            self._task_act_added(metadata)

    @gen.coroutine
    def cc_load_all(self, actuator_uri):
        actuator_cc = self.cc_metadata[actuator_uri]['hw_id']
        addressings = self.cc_addressings[actuator_uri]

        for addressing in addressings:
            try:
                yield gen.Task(self._task_addressing, self.ADDRESSING_TYPE_CC, actuator_cc, addressing)
            except Exception as e:
                logging.exception(e)

    def wait_for_cc_if_needed(self, callback):
        if not self.waiting_for_cc:
            callback()
            return
        self.waiting_for_cc_cbs.append(callback)

    # -----------------------------------------------------------------------------------------------------------------
    # Utilities

    def create_midi_cc_uri(self, channel, controller):
        if controller == MIDI_PITCHBEND_AS_CC:
            return "%sCh.%d_Pbend" % (kMidiCustomPrefixURI, channel+1)
        return "%sCh.%i_CC#%i" % (kMidiCustomPrefixURI, channel+1, controller)

    def get_midi_cc_from_uri(self, uri):
        data = uri.replace(kMidiCustomPrefixURI+"Ch.","",1).split("_CC#",1)
        if len(data) == 2:
            channel = int(data[0])-1
            if data[1].endswith("_Pbend"):
                controller = MIDI_PITCHBEND_AS_CC
            else:
                controller = int(data[1])
            return (channel, controller)

        print("ERROR: get_midi_cc_from_uri() called with invalid uri:", uri)
        return (-1,-1)

    def is_hmi_actuator(self, actuator_uri):
        return actuator_uri.startswith("/hmi/")

    def get_actuator_type(self, actuator_uri):
        if actuator_uri.startswith("/hmi/"):
            return self.ADDRESSING_TYPE_HMI
        if actuator_uri.startswith(kMidiCustomPrefixURI):
            return self.ADDRESSING_TYPE_MIDI
        if actuator_uri == kBpmURI:
            return self.ADDRESSING_TYPE_BPM
        if actuator_uri.startswith(CV_OPTION):
            return self.ADDRESSING_TYPE_CV
        return self.ADDRESSING_TYPE_CC

    def get_group_actuators(self, actuator_uri):
        if not self.is_hmi_actuator(actuator_uri) or actuator_uri not in self.hw_actuators_uris:
            return None

        actuator = next(a for a in self.hw_actuators if a['uri'] == actuator_uri)
        group_actuators = actuator.get('actuator_group', None)
        if group_actuators is None or len(group_actuators) == 0:
            return None
        return group_actuators

    def get_presets_as_options(self, instance_id):
        pluginData = self._task_get_plugin_data(instance_id)
        presets    = self._task_get_plugin_presets(pluginData["uri"])

        handled = False
        maximum = len(presets)
        options = []
        value   = 0

        # save preset mapping
        pluginData['mapPresets'] = []

        # safety check
        if maximum == 0:
            pluginData['preset'] = ""
            print("ERROR: get_presets_as_options() called with 0 presets available for '%s'" % pluginData["uri"])
            return None

        # if no preset selected yet, we need to force one
        if not pluginData['preset']:
            pluginData['preset'] = presets[0]['uri']
            handled = True

        # save preset list, within a limit
        for i in range(maximum):
            uri = presets[i]['uri']
            pluginData['mapPresets'].append(uri)
            options.append((i, presets[i]['label']))
            if handled:
                continue
            if pluginData['preset'] == uri:
                value = i
                handled = True

        # check if selected preset is non-existent
        if not handled:
            print("WARNING: get_presets_as_options() called with an invalid preset uri '%s'" % pluginData['preset'])
            value = 0
            pluginData['preset'] = presets[0]['uri']

        return (value, maximum, options, pluginData['preset'])

    # -----------------------------------------------------------------------------------------------------------------

    # CV specific functions

    @gen.coroutine
    def cv_load_all(self, actuator_uri):
        addressings = self.cv_addressings[actuator_uri]
        if not self.is_hw_cv_port(actuator_uri):
            addressings = addressings['addrs']

        for addressing in addressings:
            data = {
                'instance_id'     : addressing['instance_id'],
                'port'            : addressing['port'],
                'label'           : addressing['label'],
                'value'           : addressing['value'],
                'minimum'         : addressing['minimum'],
                'maximum'         : addressing['maximum'],
                'steps'           : addressing['steps'],
                'unit'            : addressing['unit'],
                'options'         : addressing['options'],
                'operational_mode': addressing['operational_mode'],
            }
            try:
                yield gen.Task(self._task_addressing, self.ADDRESSING_TYPE_CV, actuator_uri, data)
            except Exception as e:
                logging.exception(e)

    def is_hw_cv_port(self, actuator_uri):
        if actuator_uri.startswith(HW_CV_PREFIX):
            return True
        return False

    def add_hw_cv_port(self, actuator_uri):
        if not self.is_hw_cv_port(actuator_uri):
            return
        if actuator_uri not in self.cv_addressings:
            self.cv_addressings[actuator_uri] = []
