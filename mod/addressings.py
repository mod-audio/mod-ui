#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import os

from tornado import gen
from mod import safe_json_load, TextFileFlusher, get_hardware_descriptor
from mod.control_chain import ControlChainDeviceListener
from mod.settings import PEDALBOARD_INSTANCE_ID
from modtools.utils import get_plugin_control_inputs_and_monitored_outputs
from modtools.tempo import get_divider_options

HMI_ADDRESSING_TYPE_LINEAR       = 0x00
HMI_ADDRESSING_TYPE_BYPASS       = 0x01
HMI_ADDRESSING_TYPE_TAP_TEMPO    = 0x02
HMI_ADDRESSING_TYPE_ENUMERATION  = 0x04 | 0x08 # implies scalepoints
HMI_ADDRESSING_TYPE_SCALE_POINTS = 0x08
HMI_ADDRESSING_TYPE_TRIGGER      = 0x10
HMI_ADDRESSING_TYPE_TOGGLED      = 0x20
HMI_ADDRESSING_TYPE_LOGARITHMIC  = 0x40
HMI_ADDRESSING_TYPE_INTEGER      = 0x80
HMI_ADDRESSING_TYPE_REVERSE_ENUM = 0x100

HMI_ACTUATOR_TYPE_FOOTSWITCH = 1
HMI_ACTUATOR_TYPE_KNOB       = 2
HMI_ACTUATOR_TYPE_POTENTIOMETER = 3

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

class Addressings(object):
    ADDRESSING_TYPE_NONE = 0
    ADDRESSING_TYPE_HMI  = 1
    ADDRESSING_TYPE_CC   = 2
    ADDRESSING_TYPE_MIDI = 3
    ADDRESSING_TYPE_BPM  = 4

    def __init__(self):
        self.init()
        self._task_addressing = None
        self._task_unaddressing = None
        self._task_set_value = None
        self._task_get_plugin_data = None
        self._task_get_plugin_presets = None
        self._task_get_port_value = None
        self._task_store_address_data = None
        self._task_hw_added    = None
        self._task_hw_removed  = None
        self._task_act_added   = None
        self._task_act_removed = None

        # First addressings/pedalboard load flag
        self.first_load = True

        # Flag and callbacks for Control Chain waiting
        self.waiting_for_cc = True
        self.waiting_for_cc_cbs = []

        self.cchain = ControlChainDeviceListener(self.cc_hardware_added,
                                                 self.cc_hardware_removed,
                                                 self.cc_actuator_added)

    # -----------------------------------------------------------------------------------------------------------------

    # initialize (clear) all addressings
    def init(self):
        desc = get_hardware_descriptor()
        self.hw_actuators = desc.get('actuators', [])
        self.hw_actuators_uris = tuple(a['uri'] for a in self.hw_actuators)
        self.pages_nb = desc.get('pages_nb', 0)
        self.pages_cb = desc.get('pages_cb', 0)
        self.current_page = 0

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

        # Store all possible HMI hardcoded values
        self.hmi_hw2uri_map = {}
        self.hmi_uri2hw_map = {}

        i = 0
        for actuator in self.hw_actuators:
            uri = actuator['uri']
            hw_id = actuator['id']

            self.hmi_hw2uri_map[hw_id] = uri
            self.hmi_uri2hw_map[uri] = hw_id

            i = i+1

    # clear all addressings, leaving metadata intact
    def clear(self):
        self.hmi_addressings  = dict((key, {'addrs': [], 'idx': -1}) for key in self.hmi_addressings.keys())
        self.cc_addressings   = dict((key, []) for key in self.cc_addressings.keys())
        self.virtual_addressings   = dict((key, []) for key in self.virtual_addressings.keys())
        self.midi_addressings = {}
        self.current_page = 0

    # -----------------------------------------------------------------------------------------------------------------

    def get_actuators(self):
        actuators = self.hw_actuators.copy()

        for uri in sorted(self.cc_metadata.keys()):
            data = self.cc_metadata[uri]
            actuators.append({
                'uri': uri,
                'name' : data['name'],
                'modes': data['modes'],
                'steps': data['steps'],
                'max_assigns': data['max_assigns'],
                'feedback'   : data['feedback'],
            })

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

    # -----------------------------------------------------------------------------------------------------------------

    @gen.coroutine
    def load(self, bundlepath, instances, skippedPorts):
        # Check if this is the first time we load addressings (ie, first time mod-ui starts)
        first_load = self.first_load
        self.first_load = False

        # Check if pedalboard contains addressings first
        datafile = os.path.join(bundlepath, "addressings.json")
        if not os.path.exists(datafile):
            self.waiting_for_cc = False
            return

        # Load addressings
        data = safe_json_load(datafile, dict)

        # Basic setup
        cc_initialized = self.cchain.initialized
        has_cc_addrs   = False
        retry_cc_addrs = False
        used_actuators = []

        # NOTE: We need to wait for Control Chain to finish initializing.
        #       Can take some time due to waiting for several device descriptors.
        #       We load everything that is possible first, then wait for Control Chain at the end if not ready yet.

        # Load all addressings possible
        for actuator_uri, addrs in data.items():
            is_cc = self.get_actuator_type(actuator_uri) == self.ADDRESSING_TYPE_CC
            if is_cc:
                has_cc_addrs = True
                if not cc_initialized:
                    continue

            # Continue if current actuator_uri is not part of the actual available actuators (hardware, virtual bpm or cc)
            if actuator_uri not in self.hw_actuators_uris and not is_cc and actuator_uri != kBpmURI:
                continue

            i = 0
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

                page = addr.get('page', None)
                # Dealing with HMI addr from a pedalboard not supporting pages on a device supporting them
                if self.get_actuator_type(actuator_uri) == self.ADDRESSING_TYPE_HMI and self.pages_cb and self.pages_nb and page is None:
                    if i < self.pages_nb: # automatically assign the i-th assignment to page i
                        page = i
                    else: # cannot address more because we've reached the max nb of pages for current actuator
                        break


                curvalue = self._task_get_port_value(instance_id, portsymbol)
                group = addr.get('group', None)
                addrdata = self.add(instance_id, plugin_uri, portsymbol, actuator_uri,
                                    addr['label'], addr['minimum'], addr['maximum'], addr['steps'], curvalue,
                                    addr.get('tempo'), addr.get('dividers'), page, group)

                if addrdata is not None:
                    stored_addrdata = addrdata.copy()
                    if group is not None: # if addressing is grouped, then store address data using group actuator uri
                        stored_addrdata['actuator_uri'] = group
                    self._task_store_address_data(instance_id, portsymbol, stored_addrdata)

                    if actuator_uri not in used_actuators:
                        used_actuators.append(actuator_uri)

                elif is_cc:
                    # Control Chain is initialized but addressing failed to load (likely due to missing hardware)
                    # Set this flag so we wait for devices later
                    retry_cc_addrs = True
                i += 1

        # Load HMI and Control Chain addressings
        for actuator_uri in used_actuators:
            if self.get_actuator_type(actuator_uri) == self.ADDRESSING_TYPE_HMI:
                try:
                    yield gen.Task(self.hmi_load_first, actuator_uri)
                except Exception as e:
                    logging.exception(e)
                yield gen.Task(self.hmi_load_first, actuator_uri)
            elif self.get_actuator_type(actuator_uri) == self.ADDRESSING_TYPE_CC and cc_initialized:
                self.cc_load_all(actuator_uri)

        # Load MIDI addressings
        # NOTE: MIDI addressings are not stored in addressings.json.
        #       They must be loaded by calling 'add_midi' before calling this function.
        self.midi_load_everything()

        # Unset retry flag if at least 1 Control Chain device is connected
        if retry_cc_addrs and len(self.cc_metadata) > 0:
            retry_cc_addrs = False

        # Check if we need to wait for Control Chain
        if not first_load or (cc_initialized and not retry_cc_addrs):
            self.waiting_for_cc = False
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

        self.waiting_for_cc = False

        for cb in self.waiting_for_cc_cbs:
            cb()
        self.waiting_for_cc_cbs = []

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

                curvalue = self._task_get_port_value(instance_id, portsymbol)
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
                addrs2.append({
                    'instance': instances[addr['instance_id']],
                    'port'    : addr['port'],
                    'label'   : addr['label'],
                    'minimum' : addr['minimum'],
                    'maximum' : addr['maximum'],
                    'steps'   : addr['steps'],
                    'tempo'   : addr.get('tempo'),
                    'dividers': addr.get('dividers'),
                    'page'    : addr.get('page'),
                    'group'   : addr.get('group')
                })
            addressings[uri] = addrs2

        # Control Chain
        for uri, addrs in self.cc_addressings.items():
            addrs2 = []
            for addr in addrs:
                addrs2.append({
                    'instance': instances[addr['instance_id']],
                    'port'    : addr['port'],
                    'label'   : addr['label'],
                    'minimum' : addr['minimum'],
                    'maximum' : addr['maximum'],
                    'steps'   : addr['steps'],
                })
            addressings[uri] = addrs2

        # Virtual actuator (only /bpm for now)
        for uri, addrs in self.virtual_addressings.items():
            addrs2 = []
            for addr in addrs:
                addrs2.append({
                    'instance': instances[addr['instance_id']],
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

        # Write addressings to disk
        with TextFileFlusher(os.path.join(bundlepath, "addressings.json")) as fh:
            json.dump(addressings, fh, indent=4)

    def registerMappings(self, msg_callback, instances):
        # HMI
        group_mappings = [] #{} if self.pages_cb else []
        for uri, addrs in self.hmi_addressings.items():
            for addr in addrs['addrs']:
                addr_uri = uri
                dividers = "{0}".format(addr.get('dividers', "null")).replace(" ", "").replace("None", "null")
                page = "{0}".format(addr.get('page', "null")).replace("None", "null")
                group = "{0}".format(addr.get('group', "null")).replace("None", "null")
                send_hw_map = True
                if addr.get('group') is not None:
                    addr_uri = group
                    group_mapping = {'uri': group, 'page': addr.get('page')}
                    if group_mapping not in group_mappings:
                        group_mappings.append({'uri': group, 'page': addr.get('page')})
                        send_hw_map = False # Register harware group mapping only once
                if addr.get('group') is None or send_hw_map:
                    msg_callback("hw_map %s %s %s %f %f %d %s %s %s %s %s 1" % (instances[addr['instance_id']],
                                                                          addr['port'],
                                                                          addr_uri,
                                                                          addr['minimum'],
                                                                          addr['maximum'],
                                                                          addr['steps'],
                                                                          addr['label'].replace(" ","_"),
                                                                          addr.get('tempo'),
                                                                          dividers,
                                                                          page,
                                                                          group))

        # Virtual addressings (/bpm)
        for uri, addrs in self.virtual_addressings.items():
            for addr in addrs:
                dividers = "{0}".format(addr.get('dividers', "null")).replace(" ", "").replace("None", "null")
                page = "{0}".format(addr.get('page', "null")).replace("None", "null")
                msg_callback("hw_map %s %s %s %f %f %d %s %s %s %s 1" % (instances[addr['instance_id']],
                                                                      addr['port'],
                                                                      uri,
                                                                      addr['minimum'],
                                                                      addr['maximum'],
                                                                      addr['steps'],
                                                                      addr['label'].replace(" ","_"),
                                                                      addr.get('tempo'),
                                                                      dividers,
                                                                      page))

        # Control Chain
        for uri, addrs in self.cc_addressings.items():
            for addr in addrs:
                msg_callback("hw_map %s %s %s %f %f %d %s False null 0" % (instances[addr['instance_id']],
                                                                           addr['port'],
                                                                           uri,
                                                                           addr['minimum'],
                                                                           addr['maximum'],
                                                                           addr['steps'],
                                                                           addr['label'].replace(" ","_")))

        # MIDI
        for uri, addrs in self.midi_addressings.items():
            for addr in addrs:
                msg_callback("midi_map %s %s %i %i %f %f" % (instances[addr['instance_id']],
                                                             addr['port'],
                                                             addr['midichannel'],
                                                             addr['midicontrol'],
                                                             addr['minimum'],
                                                             addr['maximum']))

    # -----------------------------------------------------------------------------------------------------------------

    def add(self, instance_id, plugin_uri, portsymbol, actuator_uri, label, minimum, maximum, steps, value, tempo=False, dividers=None, page=None, group=None):
        actuator_type = self.get_actuator_type(actuator_uri)

        if actuator_type not in (self.ADDRESSING_TYPE_HMI, self.ADDRESSING_TYPE_CC, self.ADDRESSING_TYPE_BPM):
            print("ERROR: Trying to address the wrong way, stop!")
            return None

        unit = "none"
        options = []

        if portsymbol == ":presets":
            data = self.get_presets_as_options(instance_id)

            if data is None:
                return None

            value, maximum, options, spreset = data

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
            for port_info in get_plugin_control_inputs_and_monitored_outputs(plugin_uri)['inputs']:
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
            'group'       : group
        }

        # -------------------------------------------------------------------------------------------------------------
        if actuator_type == self.ADDRESSING_TYPE_HMI:

            if portsymbol == ":bypass":
                hmitype = HMI_ADDRESSING_TYPE_BYPASS

            elif portsymbol == ":presets":
                hmitype = HMI_ADDRESSING_TYPE_ENUMERATION|HMI_ADDRESSING_TYPE_INTEGER

            else:
                if "toggled" in pprops:
                    hmitype = HMI_ADDRESSING_TYPE_TOGGLED
                elif "integer" in pprops:
                    hmitype = HMI_ADDRESSING_TYPE_INTEGER
                else:
                    hmitype = HMI_ADDRESSING_TYPE_LINEAR

                if "logarithmic" in pprops:
                    hmitype |= HMI_ADDRESSING_TYPE_LOGARITHMIC
                if "trigger" in pprops:
                    hmitype |= HMI_ADDRESSING_TYPE_TRIGGER

                if portsymbol == ":bpm" and "tapTempo" in pprops and actuator_uri.startswith("/hmi/footswitch"):
                    hmitype |= HMI_ADDRESSING_TYPE_TAP_TEMPO

                if tempo or "enumeration" in pprops and len(port_info["scalePoints"]) > 0:
                    hmitype |= HMI_ADDRESSING_TYPE_ENUMERATION

            # first actuator in group should have reverse enum hmi type
            if group is not None:
                group_actuator = next((act for act in self.hw_actuators if act['uri'] == group), None)
                if group_actuator is not None and group_actuator['group'].index(actuator_uri) == 0:
                    hmitype |= HMI_ADDRESSING_TYPE_REVERSE_ENUM

            if hmitype & HMI_ADDRESSING_TYPE_SCALE_POINTS:
                if not tempo and value not in [o[0] for o in options]:
                    print("ERROR: current value '%f' for '%s' is not a valid scalepoint" % (value, portsymbol))
                    addressing_data['value'] = float(options[0][0])

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
            addressings.append(addressing_data)

        elif actuator_type == self.ADDRESSING_TYPE_CC:
            if actuator_uri not in self.cc_addressings.keys():
                print("ERROR: Can't load addressing for unavailable hardware '%s'" % actuator_uri)
                return None

            addressings = self.cc_addressings[actuator_uri]
            addressings.append(addressing_data)

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

        if actuator_type == self.ADDRESSING_TYPE_HMI:
            try:
                actuator_hw = self.hmi_uri2hw_map[actuator_uri]
            except KeyError:
                print("ERROR: Why fails the hardware/URI mapping? Hardcoded number of actuators?")
            if self.pages_cb:
                # if new addressing page is not the same as the currently displayed page
                if self.current_page != addressing_data['page']:
                    # then no need to send control_add to hmi
                    callback(True)
                    return
            else:
                # HMI specific
                addressings = self.hmi_addressings[actuator_uri]
                addressing_data['addrs_idx'] = addressings['idx']+1
                addressing_data['addrs_max'] = len(addressings['addrs'])

        elif actuator_type == self.ADDRESSING_TYPE_CC:
            actuator_hw = self.cc_metadata[actuator_uri]['hw_id']

        self._task_addressing(actuator_type, actuator_hw, addressing_data, callback, send_hmi=send_hmi)

    @gen.coroutine
    def load_current(self, actuator_uris, skippedPort, updateValue, abort_catcher):
        for actuator_uri in actuator_uris:
            if abort_catcher.get('abort', False):
                print("WARNING: Abort triggered during load_current request, caller:", abort_catcher['caller'])
                return

            actuator_type = self.get_actuator_type(actuator_uri)

            if actuator_type == Addressings.ADDRESSING_TYPE_HMI:
                try:
                    yield gen.Task(self.hmi_load_current, actuator_uri, skippedPort=skippedPort, updateValue=updateValue)
                except Exception as e:
                    logging.exception(e)

            elif actuator_type == Addressings.ADDRESSING_TYPE_CC:
                # FIXME: we need a way to change CC value, without re-addressing
                actuator_cc = self.cc_metadata[actuator_uri]['hw_id']
                addressings = self.cc_addressings[actuator_uri]

                for addressing in addressings:
                    if (addressing['instance_id'], addressing['port']) == skippedPort:
                        continue
                    data = {
                        'instance_id': addressing['instance_id'],
                        'port'       : addressing['port'],
                        'label'      : addressing['label'],
                        'value'      : addressing['value'],
                        'minimum'    : addressing['minimum'],
                        'maximum'    : addressing['maximum'],
                        'steps'      : addressing['steps'],
                        'unit'       : addressing['unit'],
                        'options'    : addressing['options'],
                    }
                    try:
                        yield gen.Task(self._task_unaddressing, self.ADDRESSING_TYPE_CC, data['instance_id'], data['port'])
                        yield gen.Task(self._task_addressing, self.ADDRESSING_TYPE_CC, actuator_cc, data)
                    except Exception as e:
                        logging.exception(e)

    def remove_hmi(self, addressing_data, actuator_uri):
        addressings       = self.hmi_addressings[actuator_uri]
        addressings_addrs = addressings['addrs']

        for i, addr in enumerate(addressings_addrs):
            if addressing_data['actuator_uri'] != addr['actuator_uri']:
                continue
            if addressing_data['instance_id'] != addr['instance_id']:
                continue
            if addressing_data['port'] != addr['port']:
                continue
            index = i
            addressings_addrs.pop(index)
            break
        else:
            return False

        old_idx = addressings['idx']
        # if addressings['idx'] == index:
        if old_idx != 0 or (old_idx == 0 and not len(addressings_addrs)):
            addressings['idx'] -= 1
        return old_idx == index

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
                        group_addressing_data['hmitype'] = HMI_ADDRESSING_TYPE_REVERSE_ENUM
                    was_active = self.remove_hmi(group_addressing_data, group_actuator_uri)
                return was_active

            else:
                return self.remove_hmi(addressing_data, actuator_uri)

        elif actuator_type == self.ADDRESSING_TYPE_CC:
            addressings = self.cc_addressings[actuator_uri]
            addressings.remove(addressing_data)

        elif actuator_type == self.ADDRESSING_TYPE_MIDI:
            addressings = self.midi_addressings[actuator_uri]
            addressings.remove(addressing_data)

        elif actuator_type == self.ADDRESSING_TYPE_BPM:
            addressings = self.virtual_addressings[actuator_uri]
            addressings.remove(addressing_data)

    def is_page_assigned(self, addrs, page):
        return any('page' in a and a['page'] == page for a in addrs)

    def get_addressing_for_page(self, addrs, page):
        # Assumes is_page_assigned(addrs, page) has returned True
        return next(a for a in addrs if 'page' in a and a['page'] == page)

    # -----------------------------------------------------------------------------------------------------------------
    # HMI specific functions

    def hmi_load_current(self, actuator_uri, callback, skippedPort = (None, None), updateValue = False, send_hmi = True):
        actuator_hmi      = self.hmi_uri2hw_map[actuator_uri]
        addressings       = self.hmi_addressings[actuator_uri]
        addressings_addrs = addressings['addrs']
        addressings_len   = len(addressings['addrs'])

        if addressings_len == 0:
            print("T2 addressings_len == 0")
            callback(False)
            return

        if self.pages_cb: # device supports pages
            current_page_assigned = self.is_page_assigned(addressings_addrs, self.current_page)
            if not current_page_assigned:
                callback(False)
                return
            else:
                addressing_data = self.get_addressing_for_page(addressings_addrs, self.current_page)
                if (addressing_data['instance_id'], addressing_data['port']) == skippedPort:
                    print("skippedPort", skippedPort)
                    callback(True)
                    return

                addressing_data['value'] = self._task_get_port_value(addressing_data['instance_id'],
                                                                     addressing_data['port'])

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
                callback(True)
                return

            # needed fields for addressing task
            addressing_data['addrs_idx'] = addressings_idx+1
            addressing_data['addrs_max'] = addressings_len

            # reload value
            addressing = addressings_addrs[addressings_idx]
            addressing['value'] = addressing_data['value'] = self._task_get_port_value(addressing['instance_id'],
                                                                                       addressing['port'])

        if updateValue:
            self._task_set_value(self.ADDRESSING_TYPE_HMI, actuator_hmi, addressing_data, callback)
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

    def hmi_load_next_hw(self, hw_id, callback):
        actuator_uri    = self.hmi_hw2uri_map[hw_id]
        addressings     = self.hmi_addressings[actuator_uri]
        addressings_len = len(addressings['addrs'])

        if addressings_len == 0:
            print("ERROR: hmi_load_next_hw failed, empty list")
            return

        # jump to next available addressing
        addressings['idx'] = (addressings['idx'] + 1) % addressings_len

        # ready to load
        self.hmi_load_current(actuator_uri, callback)

    def hmi_get_addr_data(self, hw_id):
        actuator_uri      = self.hmi_hw2uri_map[hw_id]
        addressings       = self.hmi_addressings[actuator_uri]
        addressings_addrs = addressings['addrs']
        addressings_len   = len(addressings_addrs)

        if addressings_len == 0:
            print("ERROR: hmi_get_addr_data failed, empty list")
            return None

        if self.pages_cb: # device supports pages
            if not self.is_page_assigned(addressings_addrs, self.current_page):
                return None
            return self.get_addressing_for_page(addressings_addrs, self.current_page)

        else:
            return addressings_addrs[addressings['idx']]

    # def hmi_load_next_page(self, page_to_load, callback):

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

    def cc_actuator_added(self, dev_id, actuator_id, metadata):
        print("cc_actuator_added", metadata['uri'])
        actuator_uri = metadata['uri']
        self.cc_metadata[actuator_uri] = metadata.copy()
        self.cc_metadata[actuator_uri]['hw_id'] = (dev_id, actuator_id)
        self.cc_addressings[actuator_uri] = []
        self._task_act_added(metadata)

    @gen.coroutine
    def cc_load_all(self, actuator_uri):
        actuator_cc = self.cc_metadata[actuator_uri]['hw_id']
        addressings = self.cc_addressings[actuator_uri]

        for addressing in addressings:
            data = {
                'instance_id': addressing['instance_id'],
                'port'       : addressing['port'],
                'label'      : addressing['label'],
                'value'      : addressing['value'],
                'minimum'    : addressing['minimum'],
                'maximum'    : addressing['maximum'],
                'steps'      : addressing['steps'],
                'unit'       : addressing['unit'],
                'options'    : addressing['options'],
            }
            try:
                yield gen.Task(self._task_addressing, self.ADDRESSING_TYPE_CC, actuator_cc, data)
            except Exception as e:
                logging.exception(e)

    def wait_for_cc_if_needed(self, callback):
        if not self.waiting_for_cc:
            callback()
            return

        self.waiting_for_cc_cbs.append(callback)

    # -----------------------------------------------------------------------------------------------------------------
    # MIDI specific functions

    @gen.coroutine
    def midi_load_everything(self):
        for actuator_uri, addressings in self.midi_addressings.items():
            for addressing in addressings:
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
        return self.ADDRESSING_TYPE_CC

    def get_group_actuators(self, actuator_uri):
        if not self.is_hmi_actuator(actuator_uri) or actuator_uri not in self.hw_actuators_uris:
            return None

        actuator = next(a for a in self.hw_actuators if a['uri'] == actuator_uri)
        group_actuators = actuator.get('group', None)
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
            pluginData['mapPresets'] = []
            pluginData['preset'] = ""
            print("ERROR: get_presets_as_options() called with an invalid preset uri '%s'" % pluginData['preset'])
            return None

        return (value, maximum, options, pluginData['preset'])

    # -----------------------------------------------------------------------------------------------------------------
