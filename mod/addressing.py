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

ADDRESSING_TYPE_RANGE     = "range"
ADDRESSING_TYPE_SWITCH    = "switch"
ADDRESSING_TYPE_TAP_TEMPO = "tap_tempo"

ADDRESSING_TYPES = [
    ADDRESSING_TYPE_RANGE,
    ADDRESSING_TYPE_SWITCH,
    ADDRESSING_TYPE_TAP_TEMPO
]

ADDRESSING_CTYPE_LINEAR         = 0
ADDRESSING_CTYPE_BYPASS         = 1
ADDRESSING_CTYPE_TAP_TEMPO      = 2
ADDRESSING_CTYPE_ENUMERATION    = 4 # implies scalepoints
ADDRESSING_CTYPE_SCALE_POINTS   = 8
ADDRESSING_CTYPE_TRIGGER        = 16
ADDRESSING_CTYPE_TOGGLED        = 32
ADDRESSING_CTYPE_LOGARITHMIC    = 64
ADDRESSING_CTYPE_INTEGER        = 128

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

from mod.bank import list_banks
from mod.hardware import get_hardware
from mod.ingen import Host
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
        affected_actuators = {}
        for actuator, addressing in self.addressings.items():
            i = 0
            while i < len(addressing['addrs']):
                if addressing['addrs'][i].get('instance_id') == instance_id:
                    addressing['addrs'].pop(i)
                    if addressing['idx'] >= i:
                        addressing['idx'] -= 1
                    affected_actuators[actuator] = addressing['idx']
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
    instance_id: effect instance
    port_id: control port
    addressing_type: 'range', 'switch' or 'tap_tempo'
    label: lcd display label
    ctype: 0 linear, 1 logarithm, 2 enumeration, 3 toggled, 4 trigger, 5 tap tempo, 6 bypass
    unit: string representing the parameter unit (hz, bpm, seconds, etc)
    hardware_type: the hardware model
    hardware_id: the id of the hardware where we find this actuator
    actuator_type: the encoder button type
    actuator_id: the encoder button number
    options: array of options, each one being a tuple (value, label)
    """
    def address(self, instance, port, addressing_type,
                label, ctype, unit, value, maximum, minimum, steps, actuator, options, callback):
        instance_id = self.mapper.get_id(instance)

        old_actuator = self._unaddress(instance, port)

        if all(i == -1 for i in actuator):
            self.hmi.control_rm(instance_id, port, callback)
            if old_actuator is not None:
                  self._address_next(old_actuator)
            return

        hardware_type, hardware_id, actuator_type, actuator_id = actuator

        addressing = {
            'actuator': actuator,
            'addressing_type': addressing_type,
            'instance_id': instance_id,
            'port': port,
            'label': label,
            'type': ctype,
            'unit': unit,
            'value': value,
            'minimum': minimum,
            'maximum': maximum,
            'steps': steps,
            'options': options,
        }
        self.instances[instance]['addressing'][port] = addressing
        self.addressings[actuator]['addrs'].append(addressing)
        self.addressings[actuator]['idx'] = len(self.addressings[actuator]['addrs']) - 1

        self.hmi.control_add(instance_id, port, label, ctype, unit, value, maximum, minimum, steps,
                             hardware_type, hardware_id, actuator_type, actuator_id,
                             len(self.addressings[actuator]['addrs']), # num controllers
                             len(self.addressings[actuator]['addrs']), # index
                             options, callback)

        if old_actuator is not None:
            self._addressing_load(old_actuator)

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
        actuator = (hardware_type, hardware_id, actuator_type, actuator_id)
        self._address_next(actuator, callback)

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
        # (4, 0, 1, 0): {'addrs': [], 'idx': 0}
        # the 'key' is a hardware identifier, meaning a button, knob, etc
        hw = set([ tuple(h[:4]) for sublist in get_hardware().values() for h in sublist ])
        self.addressings = dict( (k, {'idx': 0, 'addrs': []}) for k in hw )

    # -----------------------------------------------------------------------------------------------------------------

    def _addressing_load(self, actuator, callback=None):
        addressings       = self.addressings[actuator]
        addressings_addrs = addressings['addrs']
        addressings_idx   = addressings['idx']

        try:
            addressing = addressings_addrs[addressings_idx]
        except IndexError:
            return

        hardware_type, hardware_id, actuator_type, actuator_id = actuator

        self.hmi.control_add(addressing['instance_id'], addressing['port'],
                             addressing['label'], addressing['type'], addressing['unit'],
                             addressing['value'], addressing['maximum'], addressing['minimum'], addressing['steps'],
                             hardware_type, hardware_id, actuator_type, actuator_id,
                             len(addressings_addrs), # num controllers
                             addressings_idx+1,      # index
                             addressing['options'], callback)

    def _address_next(self, actuator, callback=lambda r:r):
        hardware_type, hardware_id, actuator_type, actuator_id = actuator

        addressings       = self.addressings[actuator]
        addressings_addrs = addressings['addrs']
        addressings_idx   = addressings['idx']

        if len(addressings_addrs) > 0:
            addressings['idx'] = (addressings['idx'] + 1) % len(addressings_addrs)
            callback(True)
            self._addressing_load(actuator)
        else:
            callback(True)
            self.hmi.control_clean(hardware_type, hardware_id, actuator_type, actuator_id)

    def _unaddress(self, instance, port):
        data = self.instances.get(instance, None)
        if data is None:
            return None

        addressing = data['addressing'].pop(port, None)
        if addressing is None:
            return None

        actuator          = addressing['actuator']
        addressings       = self.addressings[actuator]
        addressings_addrs = addressings['addrs']
        addressings_idx   = addressings['idx']

        index = addressings_addrs.index(addressing)
        addressings_addrs.pop(index)

        # FIXME ?
        if addressings_idx >= index:
            addressings['idx'] -= 1
        #if index <= addressings_idx:
            #addressings['idx'] = addressings_idx - 1

        return actuator

    # -----------------------------------------------------------------------------------------------------------------
