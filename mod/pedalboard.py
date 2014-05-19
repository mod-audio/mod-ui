
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

import os, json, logging, copy
from datetime import datetime
from bson import ObjectId
from mod.settings import (PEDALBOARD_DIR, PEDALBOARD_INDEX_PATH,
                          INDEX_PATH, BANKS_JSON_FILE, DEFAULT_JACK_BUFSIZE)

from modcommon import json_handler
from mod.bank import remove_pedalboard_from_banks
from mod import indexing


class Pedalboard(object):
    version = 1

    class ValidationError(Exception):
        pass

    def __init__(self, uid=None):
        self.data = None
        self.clear()

        if uid:
            self.load(uid)
        
    def clear(self):
        self.max_instance_id = -1
        if self.data:
            width = self.data['width']
            height = self.data['height']
        else:
            width = 0
            height = 0
        self.data = {
            '_id': None,
            'metadata': {
                'title': '',
                'tstamp': None,
                },
            'width': width,
            'height': height,
            'instances': {},
            'connections': [],
            }

    def serialize(self):
        serialized = copy.deepcopy(self.data)
        serialized['instances'] = serialized['instances'].values()
        serialized['version'] = self.version
        return serialized

    def unserialize(self, data):
        data = Migration.migrate(data)
        instances = data.pop('instances')
        data['instances'] = {}
        for instance in instances:
            data['instances'][instance['instanceId']] = instance
        self.data = data

    def load(self, uid):
        try:
            fh = open(os.path.join(PEDALBOARD_DIR, str(uid)))
        except IOError:
            logging.error('[pedalboard] Unknown pedalboard %s' % uid)
            return self.clear()
        self.unserialize(json.load(fh))
        fh.close()
        self.load_addressings()

    def load_addressings(self):
        for instance_id, instance in self.data.get('instances', {}).items():
            for port_id, addressing in instance.get('addressing', {}).items():
                if not addressing.get("instance_id", False):
                    addressing.update({'instance_id': instance_id, 'port_id': port_id})
                if port_id == ":bypass":
                    addressing['value'] = int(instance['bypassed'])

    def save(self, title=None, as_new=False):
        if as_new or not self.data['_id']:
            self.data['_id'] = ObjectId()
        if title is not None:
            self.set_title(title)
        
        title = self.data['metadata']['title']

        if not title:
            raise self.ValidationError("Title cannot be empty")

        index = indexing.PedalboardIndex()
        try:
            existing = index.find(title=title).next()
            assert existing['id'] == unicode(self.data['_id'])
        except StopIteration:
            pass
        except AssertionError:
            raise self.ValidationError('Pedalboard "%s" already exists' % title)
        
        fh = open(os.path.join(PEDALBOARD_DIR, str(self.data['_id'])), 'w')
        self.data['metadata']['tstamp'] = datetime.now()
        serialized = self.serialize()
        fh.write(json.dumps(serialized, default=json_handler))
        fh.close()

        index = indexing.PedalboardIndex()
        index.add(self.data)

        return self.data['_id']

    def _port_to_list(self, port):
        port = port.split(':')
        if port[0].startswith('effect_'):
            port[0] = port[0][len('effect_'):]
        try:
            port[0] = int(port[0])
        except ValueError:
            pass
        return port

    def add_instance(self, url, instance_id=None, bypassed=False, x=0, y=0):
        if instance_id is None:
            instance_id = self.max_instance_id + 1
        self.max_instance_id = max(self.max_instance_id, instance_id)
        self.data['instances'][instance_id] = { 'url': url,
                                                'instanceId': instance_id,
                                                'bypassed': bool(bypassed),
                                                'x': x,
                                                'y': y,
                                                'preset': {},
                                                'addressing': {},
                                                }
        return instance_id

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

        # Remove all connections involving that instance
        i = 0
        while i < len(self.data['connections']):
            connection = self.data['connections'][i]
            if connection[0] == instance_id or connection[2] == instance_id:
                self.data['connections'].pop(i)
            else:
                i += 1

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
        return old_actuator

    def parameter_unaddress(self, instance_id, port_id):
        try:
            instance = self.data['instances'][instance_id]
        except KeyError:
            logging.error('[pedalboard] Cannot find instance %d to unaddress parameter %s' %
                          (instance_id, port_id))
        else:
            try:
                addressing = instance['addressing'].pop(port_id)
            except KeyError:
                logging.error("[pedalboard] Trying to unaddress parameter %s in instance %d, but it's not addressed" %
                              (port_id, instance_id))
            else:
                return addressing['actuator']
        # If we reached here, this is an error situation
        return tuple()

    def set_title(self, title):
        self.data['metadata']['title'] = unicode(title)

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
            effect = index.find(url=instance['url']).next()
            bufsize = max(effect['bufsize'], minimum)
        return bufsize

class Migration():
    version = 1

    @classmethod
    def migrate(cls, data):
        """
        This assures that the pedalboard data is formatted as defined by the latest
        specification, and adapts the structure if necessary
        """
        version = data.get('version', 0)
        
        if version == cls.version:
            return data

        for instance in data['instances']:
            addressing = instance.get('addressing', {})
            for port_id in addressing.keys():
                addr = addressing[port_id]
                add['actuator'] = cls._migrate_actuator(addr['actuator'])
                mode, props = cls._migrate_type(instance['url'], port_id, addr['addressing_type'])
                if mode is None:
                    # Either the effect is not installed anymore, or there's some weird
                    # addressing here. Let's unaddress to recover.
                    del addressing[port_id]
                    continue
                addr['mode'] = mode
                addr['port_properties'] = props
                try:
                    addr['scale_points'] = addr.pop('options')
                except KeyError:
                    addr['scale_points'] = []

        return data

    @classmethod
    def _migrate_actuator(cls, actuator):
        if actuator[0] == -1:
            return None
        if actuator[0] == 0:
            # This is Quadra. The actuator IDs will be:
            # 1-4: foots 1-4
            # 5-8: knobs 1-4
            return [ 'http://portalmod.com/devices/quadra',
                     actuator[1],
                     (actuator[2]-1) * 4 + actuator[3] + 1,
                     ]
        if actuator[0] == 1:
            # This is the expression pedal. The actuator IDs will be:
            # 1 - the pedal (potenciometer); 2 - the footswitch
            return [ 'http://portalmod.com/devices/expression_pedal',
                     actuator[1],
                     { 3: 1, 1: 2 }[actuator[2]],
                     ]

    @classmethod
    def _migrate_type(cls, url, port_id, addr):
        if port_id == ':bypass':
            mode = (0b01111110, 0b00100000) # ON/OFF, same as below
            return (struct.pack('2B', *mode), 
                    0b00100001)
        try:
            port = cls._get_port(url, port_id)
        except:
            # The effect is not installed, we can't migrate the data, let's unaddress
            return None, None
        mode = None
        if addr['addressing_type'] == 'range':
            if addr['actuator'][2] == 2:
                # this is a knob
                mode = (0b00110011, 0b00000000)
            elif addr['actuator'][2] == 3:
                # this is expression pedal
                mode = (0b00111111, 0b00000000)
        elif addr['addressing_type'] == 'switch':
            # This is footswitch, only possible case, 
            # let's make sure everything is consistent
            if addr['actuator'][2] == 1:
                if port.get('toggled') and port.get('trigger'):
                    # Pulse
                    mode = (0b01111111, 0b00110000)
                elif port.get('toggled'):
                    # ON/OFF
                    mode = (0b01111110, 0b00100000)
                elif len(port.get('scale_points', [])) > 0:
                    # Select next scale point
                    mode = (0b01111111, 0b00001000)
        elif addr['addressing_type'] == 'tap_tempo':
            # Again, let's check for consistency, must be footswitch
            if addr['actuator'][2] == 1:
                # Tap Tempo
                mode = (0b11111111, 0b00000010)

        if mode is None:
            return (None, None)
        mode = struct.pack('2B', *mode)

        props = 0
        if port.get("integer"):
            props |= 0b10000000
        if port.get("logarithmic"):
            props |= 0b01000000
        if port.get("toggled"):
            props |= 0b00100000
        if port.get("trigger"):
            props |= 0b00010000
        if len(port.get("scalePoints", [])) > 0:
            props |= 0b00001000
        if port.get("enumeration"):
            props |= 0b00000100
        if port.get("tap_tempo"):
            props |= 0b00000010

        return (mode, props)


        
    @classmethod
    def _get_port(cls, url, port_id):
        index = indexing.EffectIndex()
        # That might raise error if effect is not installed.
        # It is handled by _migrate_type
        effect = index.find(url=url).next()
        effect = json.loads(open(os.path.join(EFFECT_DIR, str(effect['id']))).read())
        for port in effect['ports']['control']['input']:
            if port.symbol == port_id:
                return port

def remove_pedalboard(uid):
    # Delete pedalboard file
    fname = os.path.join(PEDALBOARD_DIR, str(uid))
    if not os.path.exists(fname):
        return False
    os.remove(fname)

    # Remove from index
    index = indexing.PedalboardIndex()
    index.delete(uid)

    return remove_pedalboard_from_banks(uid)
