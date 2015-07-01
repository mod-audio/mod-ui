
# Copyright 2012-2013 AGR Audio, Industria e Comercio LTDA. <contato@moddevices.com>
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

import os, json, logging, copy
from datetime import datetime
from mod.settings import BANKS_JSON_FILE, DEFAULT_JACK_BUFSIZE

from mod import json_handler
from mod.bank import remove_pedalboard_from_banks
from mod.hardware import get_hardware
from mod import indexing


class Pedalboard(object):
    class ValidationError(Exception):
        pass

    def __init__(self, uid=None):
        self.data = None
        self.clear()

        self.init_addressings()

        if uid:
            self.load(uid)

    def init_addressings(self):
        hw = set([ tuple(h[:4]) for sublist in get_hardware().values() for h in sublist  ])
        self.addressings = dict( (k, {'idx': 0, 'addrs': []}) for k in hw )

    def clear(self):
        if self.data:
            width = self.data['width']
            height = self.data['height']
        else:
            width = 0
            height = 0
        self.data = {
            'instances': {},
            'connections': [],
            'metadata': {
                'title':      "",
                'thumbnail':  "",
                'tstamp':     None,
            },
            'uri':    "",
            'width':  width,
            'height': height
            }
        self.init_addressings()

    def serialize(self):
        serialized = copy.deepcopy(self.data)
        serialized['instances'] = list(serialized['instances'].values())
        return serialized

    def unserialize(self, data):
        instances = data.pop('instances')
        data['instances'] = {}
        for instance in instances:
            data['instances'][instance['instanceId']] = instance
        self.data = data

    #def load(self, uid):
        #try:
            #fh = open(os.path.join(PEDALBOARD__DIR, str(uid)))
        #except IOError:
            #logging.error('[pedalboard] Unknown pedalboard %s' % uid)
            #return self.clear()
        #self.unserialize(json.load(fh))
        #fh.close()
        #self.load_addressings()

    def load_addressings(self):
        self.init_addressings()
        for instance, data in self.data.get('instances', {}).items():
            for port_id, addressing in instance.get('addressing', {}).items():
                if not addressing.get("instance", False):
                    addressing.update({'instance_id': instance_id, 'port_id': port_id})
                if port_id == ":bypass":
                    addressing['value'] = int(instance['bypassed'])
                try:
                    self.addressings[tuple(addressing['actuator'])]['addrs'].append(addressing)
                except KeyError:
                    self.data['instances'][addressing['instance_id']]['addressing'].pop(addressing['port_id'])

    #def save(self, title=None, as_new=False):
        #if as_new or not self.data['_id']:
            #self.data['_id'] = "RANDOM"
        #if title is not None:
            #self.set_title(title)

        #title = self.data['metadata']['title']

        #if not title:
            #raise self.ValidationError("Title cannot be empty")

        #index = indexing.PedalboardIndex()
        #try:
            #existing = next(index.find(title=title))
            #assert existing['id'] == str(self.data['_id'])
        #except StopIteration:
            #pass
        #except AssertionError:
            #raise self.ValidationError('Pedalboard "%s" already exists' % title)

        #fh = open(os.path.join(PEDALBOARD__DIR, str(self.data['_id'])), 'w')
        #self.data['metadata']['tstamp'] = datetime.now()
        #serialized = self.serialize()
        #fh.write(json.dumps(serialized, default=json_handler))
        #fh.close()

        #index = indexing.PedalboardIndex()
        #index.add(self.data)

        #return self.data['_id']

    def _port_to_list(self, port):
        port = port.split(':')
        if port[0].startswith('effect_'):
            port[0] = port[0][len('effect_'):]
        try:
            port[0] = int(port[0])
        except ValueError:
            pass
        return port

    def add_instance(self, uri, instance, bypassed=False, x=0, y=0):
        self.data['instances'][instance] = {
              'uri': uri,
              'instance': instance,
              'bypassed': bool(bypassed),
              'x': x,
              'y': y,
              'preset': {},
              'addressing': {},
        }
        return instance

    # Remove an instance and returns a list of all affected actuators
    def remove_instance(self, instance_id):
        if instance_id < 0:
            # remove all effects
            self.clear()
            return []
        try:
            # Remove the instance
            self.data['instances'].pop(instance_id)
        except KeyError:
            logging.error('[pedalboard] Cannot remove unknown instance %d' % instance_id)
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

        # Remove all connections involving that instance
        i = 0
        while i < len(self.data['connections']):
            connection = self.data['connections'][i]
            if connection[0] == instance_id or connection[2] == instance_id:
                self.data['connections'].pop(i)
            else:
                i += 1
        return [ list(act) + [idx] for act, idx in affected_actuators.items() ]

    def bypass(self, instance_id, value):
        try:
            self.data['instances'][instance_id]['bypassed'] = bool(value)
            return True
        except KeyError:
            logging.error('[pedalboard] Cannot bypass unknown instance %d' % instance_id)

    def connect(self, port_from, port_to):
        port_from = self._port_to_list(port_from)
        port_to = self._port_to_list(port_to)
        for port in (port_from, port_to):
            try:
                instance_id = int(port[0])
            except ValueError:
                continue
            if not self.data['instances'].get(instance_id):
                # happens with clipmeter and probably with other internal plugins
                return
        self.data['connections'].append([port_from[0], port_from[1], port_to[0], port_to[1]])

    def disconnect(self, port_from, port_to):
        pf = self._port_to_list(port_from)
        pt = self._port_to_list(port_to)
        # This is O(N). It will hardly be a problem, since it's only called when user is connected
        # and manually disconnects two ports, and number of connections is expected to be relatively small.
        # Anyway, if you're greping TODO, check if optimizing this is one ;-)
        for i, c in enumerate(self.data['connections']):
            if c[0] == pf[0] and c[1] == pf[1] and c[2] == pt[0] and c[3] == pt[1]:
                self.data['connections'].pop(i)
                return True

    def parameter_set(self, instance_id, port_id, value):
        try:
            self.data['instances'][instance_id]['preset'][port_id] = value
            if len(self.data['instances'][instance_id].get('addressing', [])) > 0:
                addr = self.data['instances'][instance_id]['addressing'].get(port_id, {})
                if addr:
                    addr['value'] = value
            return True
        except KeyError:
            logging.error('[pedalboard] Cannot set parameter %s of unknown instance %d' % (port_id, instance_id))

    def parameter_address(self, instance_id, port_id, addressing_type, label, ctype,
                          unit, current_value, maximum, minimum, steps,
                          hardware_type, hardware_id, actuator_type, actuator_id,
                          options):
        old_actuator = None
        if self.data['instances'][instance_id]['addressing'].get(port_id, False):
            old_actuator = self.parameter_unaddress(instance_id, port_id)
        addressing = { 'actuator': [ hardware_type, hardware_id, actuator_type, actuator_id ],
                       'addressing_type': addressing_type,
                       'type': ctype,
                       'unit': unit,
                       'label': label,
                       'minimum': minimum,
                       'maximum': maximum,
                       'value': current_value,
                       'steps': steps,
                       'instance_id': instance_id,
                       'port_id': port_id,
                       'options': options,
                       }
        self.data['instances'][instance_id]['addressing'][port_id] = addressing
        self.addressings[tuple(addressing['actuator'])]['addrs'].append(addressing)
        self.addressings[tuple(addressing['actuator'])]['idx'] = len(self.addressings[tuple(addressing['actuator'])]['addrs']) -1
        if old_actuator:
            return list(old_actuator) + [self.addressings[tuple(old_actuator)]['idx']]

    def parameter_unaddress(self, instance_id, port_id):
        try:
            instance = self.data['instances'][instance_id]
        except KeyError:
            logging.error('[pedalboard] Cannot find instance %d to unaddress parameter %s' %
                          (instance_id, port_id))
        else:
            try:
                addressing = instance['addressing'].pop(port_id)
                addrs = self.addressings[tuple(addressing['actuator'])]['addrs']
                addrs_idx = self.addressings[tuple(addressing['actuator'])]['idx']
                idx = addrs.index(addressing)
                addrs.pop(idx)
                if idx <= addrs_idx:
                    self.addressings[tuple(addressing['actuator'])]['idx'] = addrs_idx - 1
            except KeyError:
                logging.error("[pedalboard] Trying to unaddress parameter %s in instance %d, but it's not addressed" %
                              (port_id, instance_id))
            else:
                return addressing['actuator']
        return tuple()

    def set_title(self, title):
        self.data['metadata']['title'] = title

    def set_size(self, width, height):
        logging.debug("[pedalboard] setting window size %dx%d" % (width, height))
        self.data['width'] = width
        self.data['height'] = height

    def set_position(self, instance_id, x, y):
        try:
            self.data['instances'][instance_id]['x'] = x
            self.data['instances'][instance_id]['y'] = y
            logging.debug('[pedalboard] Setting position of instance %d at (%d,%d)' %
                          (instance_id, x, y))
            return True
        except KeyError:
            logging.error('[pedalboard] Cannot set position of unknown instance %d' % instance_id)

    def get_bufsize(self, minimum=DEFAULT_JACK_BUFSIZE):
        bufsize = minimum
        index = indexing.EffectIndex()
        for instance in self.data['instances'].values():
            effect  = next(index.find(uri=instance['uri']))
            bufsize = max(effect['bufsize'], minimum)
        return bufsize

#def remove_pedalboard(uid):
    ## Delete pedalboard file
    #fname = os.path.join(PEDALBOARD__DIR, str(uid))
    #if not os.path.exists(fname):
        #return False
    #os.remove(fname)

    ## Remove from index
    #index = indexing.PedalboardIndex()
    #index.delete(uid)

    #return remove_pedalboard_from_banks(uid)
