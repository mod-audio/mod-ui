#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Parameter Adressing for MOD
# Copyright (C) 2015 Filipe Coelho <falktx@falktx.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# For a full copy of the GNU General Public License see the COPYING file

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

import logging
import os

from mod import get_hardware
from mod.bank import list_banks
from mod.ingen import Host
from mod.lv2 import get_plugin_info
from mod.protocol import Protocol

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

    # get a string instance from a numeric id
    def get_instance(self, id):
        return self.id_map[id]

# class that saves the current addressing state
class Addressing(object):
    def __init__(self, hmi):
        self.host = None
        self.hmi  = hmi
        self.mapper = InstanceIdMapper()
        self.banks = []
        self.instances = {}
        self._init_addressings()

        # Register HMI protocol callbacks
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

    def get_addressings(self):
        addressings = {}
        for uri, addressing in self.addressings.items():
            addrs = []
            for addr in addressing['addrs']:
                addrs.append({
                    'instance': addr['instance'],
                    'port'    : addr['port'],
                    'label'   : addr['label'],
                    'minimum' : addr['minimum'],
                    'maximum' : addr['maximum'],
                    'steps'   : addr['steps'],
                })
            addressings[uri] = addrs
        return addressings

    # -----------------------------------------------------------------------------------------------------------------

    # Init our ingen host class
    # This is only called when the HMI responds to our initial ping (and it's thus initialized)
    # The reason for this being a separate init function is because we don't need it when HMI is off
    def init_host(self):
        # We need our own host instance so that messages get propagated correctly by ingen
        # Later on this code will be a separate application so it all fits anyway
        self.host = Host(os.getenv("MOD_INGEN_SOCKET_URI", "unix:///tmp/ingen.sock"))

        def plugin_added_callback(instance, uri, enabled, x, y):
            self._add_instance(instance, uri, not enabled)

        def plugin_removed_callback(instance):
            self._remove_instance(instance)

        def plugin_enabled_callback(instance, enabled):
            self._set_bypassed(instance, not enabled)

        def port_value_callback(port, value):
            instance, port = port.rsplit("/", 1)
            self._set_value(instance, port, value)

        self.host.plugin_added_callback = plugin_added_callback
        self.host.plugin_removed_callback = plugin_removed_callback
        self.host.port_value_callback = port_value_callback

        self.host.open_connection_if_needed(self.host_callback)

    def host_callback(self):
        self.host.get("/graph")

    # -----------------------------------------------------------------------------------------------------------------

    def _add_instance(self, instance, uri, bypassed):
        instance_id = self.mapper.get_id(instance)

        self.instances[instance] = {
              'id': instance_id,
              'instance': instance,
              'uri': uri,
              'bypassed': bypassed,
              'addressing': {}, # symbol: addressing
              'ports': {},      # symbol: value
        }
        logging.info('[addressing] Added instance %s' % instance)

    def _remove_instance(self, instance):
        instance_id = self.mapper.get_id(instance)

        # Remove the instance
        try:
            self.instances.pop(instance)
        except KeyError:
            logging.error('[addressing] Cannot remove unknown instance %s' % instance)

        # Remove addressings of that instance
        #affected_actuators = {}
        for actuator_uri, addressing in self.addressings.items():
            i = 0
            while i < len(addressing['addrs']):
                if addressing['addrs'][i].get('instance_id') == instance_id:
                    addressing['addrs'].pop(i)
                    if addressing['idx'] >= i:
                        addressing['idx'] -= 1
                    #affected_actuators[actuator_uri] = addressing['idx']
                else:
                    i += 1

        self.hmi.control_rm(instance_id, ":all")
        #for addr in affected_actuators:
            #self.parameter_addressing_load(*addr)

        logging.info('[addressing] Removed instance %s' % instance)
        #return [ list(act) + [idx] for act, idx in affected_actuators.items() ]

    def _set_bypassed(self, instance, bypassed):
        data = self.instances.get(instance, None)
        if data is None:
            return
        data['bypassed'] = bypassed

    def _set_value(self, instance, port, value):
        data = self.instances.get(instance, None)
        if data is None:
            return
        data['ports'][port] = value

        addr = data['addressing'].get(port, None)
        if addr is None:
            return
        addr['value'] = value

    # -----------------------------------------------------------------------------------------------------------------

    """
    label: lcd display label
    unit: string representing the parameter unit (hz, bpm, seconds, etc)
    options: array of options, each one being a tuple (value, label)
    """
    def address(self, instance, port, actuator_uri, label, unit, maximum, minimum, value, steps, callback):
        print(instance, port, actuator_uri, label, unit, maximum, minimum, value, steps)

        instance_id      = self.mapper.get_id(instance)
        old_actuator_uri = self._unaddress(instance, port)

        if (not actuator_uri) or actuator_uri == "null":
            self.hmi.control_rm(instance_id, port, callback)
            if old_actuator_uri is not None:
                  old_actuator_hw = self._uri2hw_map[old_actuator_uri]
                  self._address_next(old_actuator_hw)
            return

        data = self.instances.get(instance, None)
        if data is None:
            callback(False)
            return

        for port_info in get_plugin_info(data["uri"])["ports"]["control"]["input"]:
            if port_info["symbol"] != port:
                continue
            break
        else:
            callback(False)
            return

        pprops  = port_info["properties"]
        options = []

        if port == ":bypass":
            ctype = ADDRESSING_CTYPE_BYPASS
        elif "toggled" in pprops:
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

        addressing = {
            'actuator_uri': actuator_uri,
            'instance_id': instance_id,
            'port': port,
            'label': label,
            'type': ctype,
            'unit': unit,
            'minimum': minimum,
            'maximum': maximum,
            'value': value,
            'steps': steps,
            'options': options,
        }
        self.instances[instance]['addressing'][port] = addressing
        self.addressings[actuator_uri]['addrs'].append(addressing)
        self.addressings[actuator_uri]['idx'] = len(self.addressings[actuator_uri]['addrs']) - 1

        if old_actuator_uri is not None:
            self._addressing_load(old_actuator_uri)

        self._addressing_load(actuator_uri, callback)

    def clear(self):
        self.banks = []
        self.instances = {}
        self._init_addressings()

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

        #if bank_id >= len(self.banks):
            #print("ERROR in addressing.py: bank id out of bounds")
            #return

        #pedalboards = self.banks[bank_id]['pedalboards']
        #if pedalboard_id >= len(pedalboards):
            #print("ERROR in addressing.py: pedalboard id out of bounds")
            #return

        #uri = pedalboards[pedalboard_id]['uri']

        self.host.load_uri(pedalboard_uri)

    def hmi_parameter_get(self, instance_id, port, callback):
        logging.info("hmi parameter get")
        instance = self.mapper.get_instance(instance_id)
        callback(self.instances[instance]['ports'][port])

    def hmi_parameter_set(self, instance_id, port, value, callback=None):
        logging.info("hmi parameter set")
        instance = self.mapper.get_instance(instance_id)

        if port == ":bypass":
            self._set_bypassed(instance, bool(value))
            if self.host is not None:
                self.host.enable(instance, not value, callback)

        else:
            self._set_value(instance, port, value)
            if self.host is not None:
                self.host.param_set("%s/%s" % (instance, port), value, callback)

    def hmi_parameter_addressing_next(self, hardware_type, hardware_id, actuator_type, actuator_id, callback):
        logging.info("hmi parameter addressing next")
        if hardware_type == HARDWARE_TYPE_MOD:
            hardware_type = HARDWARE_TYPE_CUSTOM
        actuator_hw = (hardware_type, hardware_id, actuator_type, actuator_id)
        self._address_next(actuator_hw, callback)

    # -----------------------------------------------------------------------------------------------------------------

    #def peakmeter_set(self, status, callback):
        #if "on" in status:
            #self.peakmeter_on(callback)
        #elif "off" in status:
            #self.peakmeter_off(callback)

    #def peakmeter_on(self, cb):

        #def mon_peak_in_l(ok):
            #if ok:
                #self.parameter_monitor(PEAKMETER_IN, PEAKMETER_MON_VALUE_L, ">=", -30, cb)
                #self.parameter_monitor(PEAKMETER_IN, PEAKMETER_MON_PEAK_L, ">=", -30, cb)

        #def mon_peak_in_r(ok):
            #if ok:
                #self.parameter_monitor(PEAKMETER_IN, PEAKMETER_MON_VALUE_R, ">=", -30, lambda r:None)
                #self.parameter_monitor(PEAKMETER_IN, PEAKMETER_MON_PEAK_R, ">=", -30, lambda r:None)

        #def mon_peak_out_l(ok):
            #if ok:
                #self.parameter_monitor(PEAKMETER_OUT, PEAKMETER_MON_VALUE_L, ">=", -30, lambda r:None)
                #self.parameter_monitor(PEAKMETER_OUT, PEAKMETER_MON_PEAK_L, ">=", -30, lambda r:None)

        #def mon_peak_out_r(ok):
            #if ok:
                #self.parameter_monitor(PEAKMETER_OUT, PEAKMETER_MON_VALUE_R, ">=", -30, lambda r:None)
                #self.parameter_monitor(PEAKMETER_OUT, PEAKMETER_MON_PEAK_R, ">=", -30, lambda r:None)

        #def setup_peak_in(ok):
            #if ok:
                #self.connect("system:capture_1", "effect_%d:%s" % (PEAKMETER_IN, PEAKMETER_L), mon_peak_in_l, True)
                #self.connect("system:capture_2", "effect_%d:%s" % (PEAKMETER_IN, PEAKMETER_R), mon_peak_in_r, True)

        #def setup_peak_out(ok):
            #if ok:
                #self._peakmeter = True
                #for port in self._playback_1_connected_ports:
                    #self.connect(port, "effect_%d:%s" % (PEAKMETER_OUT, PEAKMETER_L), mon_peak_out_l, True)
                #for port in self._playback_2_connected_ports:
                    #self.connect(port, "effect_%d:%s" % (PEAKMETER_OUT, PEAKMETER_R), mon_peak_out_r, True)

        #self.add(PEAKMETER_URI, PEAKMETER_IN, setup_peak_in, True)
        #self.add(PEAKMETER_URI, PEAKMETER_OUT, setup_peak_out, True)

    #def peakmeter_off(self, cb):
        #self.remove(PEAKMETER_IN, cb, True)
        #self.remove(PEAKMETER_OUT, lambda r: None, True)
        #self._tuner = False

    #def tuner_set(self, status, callback):
        #if "on" in status:
            #self.tuner_on(callback)
        #elif "off" in status:
            #self.tuner_off(callback)

    #def tuner_on(self, cb):
        #def mon_tuner(ok):
            #if ok:
                #self.parameter_monitor(TUNER, TUNER_MON_PORT, ">=", 0, cb)

        #def setup_tuner(ok):
            #if ok:
                #self._tuner = True
                #self.connect("system:capture_%s" % self._tuner_port, "effect_%d:%s" % (TUNER, TUNER_PORT), mon_tuner, True)

        #def mute_callback():
            #self.add(TUNER_URI, TUNER, setup_tuner, True)
        #self.mute(mute_callback)

    #def tuner_off(self, cb):
        #def callback():
            #self.remove(TUNER, cb, True)
            #self._tuner = False
        #self.unmute(callback)

    #def tuner_set_input(self, input, callback):
        ## TODO: implement
        #self.disconnect("system:capture_%s" % self._tuner_port, "effect_%d:%s" % (TUNER, TUNER_PORT), lambda r:r, True)
        #self._tuner_port = input
        #self.connect("system:capture_%s" % input, "effect_%d:%s" % (TUNER, TUNER_PORT), callback, True)

    # -----------------------------------------------------------------------------------------------------------------

    def _init_addressings(self):
        # 'self.addressings' uses a structure like this:
        # "/hmi/knob1": {'addrs': [], 'idx': 0}
        self.addressings = dict((act["uri"], {'idx': 0, 'addrs': []}) for act in get_hardware()["actuators"])

        # Store all possible hardcoded values
        self._hw2uri_map = {}
        self._uri2hw_map = {}

        for i in range(0, 4):
            knob_hw  = (HARDWARE_TYPE_CUSTOM, 0, ACTUATOR_TYPE_KNOB,       i)
            foot_hw  = (HARDWARE_TYPE_CUSTOM, 0, ACTUATOR_TYPE_FOOTSWITCH, i)
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

    def _address_next(self, actuator_hw, callback=lambda r:r):
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

    def _unaddress(self, instance, port):
        data = self.instances.get(instance, None)
        if data is None:
            return None

        addressing = data['addressing'].pop(port, None)
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
