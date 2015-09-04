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
        self.instances[instance] = {
              'id': self.mapper.get_id(instance),
              'instance': instance,
              'uri': uri,
              'bypassed': bypassed,
              'x': x,
              'y': y,
              'addressing': {},
              'ports': {},
        }
        logging.info('[addressing] Added instance %s' % instance)

    def remove_instance(self, instance):
        idx = self.mapper.get_id(instance)

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
                if addressing['addrs'][i].get('instance_id') == idx:
                    addressing['addrs'].pop(i)
                    if addressing['idx'] >= i:
                        addressing['idx'] -= 1
                    affected_actuators[actuator] = addressing['idx']
                else:
                    i += 1

        self.hmi.control_rm(idx, ":all")
        #for addr in affected_actuators:
            #self.parameter_addressing_load(*addr)

        logging.info('[addressing] Removed instance %s' % instance)
        #return [ list(act) + [idx] for act, idx in affected_actuators.items() ]

    def set_bypassed(self, instance, bypassed):
        if instance in self.instances.keys():
            self.instances[instance]['bypassed'] = bypassed

    def set_position(self, instance, x, y):
        if instance in self.instances.keys():
            data = self.instances[instance]
            data['x'] = x
            data['y'] = y

    def set_value(self, instance, port, value):
        if instance in self.instances.keys():
            data = self.instances[instance]
            data['ports']['port'] = value

            addr = data['addressing'].get(port, None)
            if addr is not None:
                addr['value'] = value
                act = addr['actuator']
                #self.parameter_addressing_load(*act)
