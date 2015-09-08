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

ADDRESSING_TYPE_LINEAR      = 0
ADDRESSING_TYPE_LOGARITHM   = 1
ADDRESSING_TYPE_ENUMERATION = 2
ADDRESSING_TYPE_TOGGLED     = 3
ADDRESSING_TYPE_TRIGGER     = 4
ADDRESSING_TYPE_TAP_TEMPO   = 5
ADDRESSING_TYPE_BYPASS      = 6

ACTUATOR_TYPE_FOOTSWITCH = 1
ACTUATOR_TYPE_KNOB       = 2
ACTUATOR_TYPE_POT        = 3

HARDWARE_TYPE_QUADRA = 0
HARDWARE_TYPE_PEDAL  = 1
HARDWARE_TYPE_TOUCH  = 2
HARDWARE_TYPE_ACCEL  = 3
HARDWARE_TYPE_CUSTOM = 4

import logging

from mod.hardware import get_hardware

# TODO stuff:
# - X, Y is needed?

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
        self.hmi = hmi
        self.mapper = InstanceIdMapper()
        self.instances = {}
        self._init_addressings()

    def _init_addressings(self):
        # 'self.addressings' uses a structure like this:
        # (4, 0, 1, 0): {'addrs': [], 'idx': 0}
        # the 'key' is a hardware identifier, meaning a button, knob, etc
        hw = set([ tuple(h[:4]) for sublist in get_hardware().values() for h in sublist ])
        self.addressings = dict( (k, {'idx': 0, 'addrs': []}) for k in hw )

    def clear(self):
        self.instances = {}
        self._init_addressings()

    def get_instance_from_id(self, instance_id):
        return self.mapper.get_instance(instance_id)

    def get_value(self, instance, port):
        return self.instances[instance]['ports'][port]

    def add_instance(self, instance, uri, bypassed, x, y):
        instance_id = self.mapper.get_id(instance)

        self.instances[instance] = {
              'id': instance_id,
              'instance': instance,
              'uri': uri,
              'bypassed': bypassed,
              'x': x,
              'y': y,
              'addressing': {}, # symbol: addressing
              'ports': {},      # symbol: value
        }
        logging.info('[addressing] Added instance %s' % instance)

    def remove_instance(self, instance):
        instance_id = self.mapper.get_id(instance)

        try:
            # Remove the instance
            self.instances.pop(instance)
        except KeyError:
            logging.error('[addressing] Cannot remove unknown instance %d' % instance)

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

    def set_bypassed(self, instance, bypassed):
        data = self.instances.get(instance, None)
        if data is None:
            return
        data['bypassed'] = bypassed

    def set_position(self, instance, x, y):
        data = self.instances.get(instance, None)
        if data is None:
            return
        data['x'] = x
        data['y'] = y

    def set_value(self, instance, port, value):
        data = self.instances.get(instance, None)
        if data is None:
            return
        data['ports'][port] = value

        addr = data['addressing'].get(port, None)
        if addr is None:
            return
        addr['value'] = value
        #self._addressing_load(addr['actuator'])

    def address(self, instance, port, addressing_type,
                label, ctype, unit, value, maximum, minimum, steps, actuator, options, callback):
        instance_id = self.mapper.get_id(instance)

        old_actuator = self._unaddress(instance, port)

        if all(i == -1 for i in actuator):
            self.hmi.control_rm(instance_id, port, callback)
            if old_actuator is not None:
                  self.address_next(old_actuator)
            return

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

        hardware_type, hardware_id, actuator_type, actuator_id = actuator

        self.hmi.control_add(instance_id, port, label, ctype, unit, value, maximum, minimum, steps,
                             hardware_type, hardware_id, actuator_type, actuator_id,
                             len(self.addressings[actuator]['addrs']), # num controllers
                             len(self.addressings[actuator]['addrs']), # index
                             options, callback)

        if old_actuator is not None:
            self._addressing_load(old_actuator)

    def address_next(self, actuator, callback=lambda r:r):
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

    def _addressing_load(self, actuator, callback=None):
        print("_addressing_load", actuator)

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
        if index <= addressings_idx:
            addressings['idx'] = addressings_idx - 1

        return actuator
