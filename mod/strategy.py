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

from mod.indexing import EffectIndex
from tornado.ioloop import IOLoop

class Strategy(object):

    instance = None

    @classmethod
    def use(cls, strategy, session, callback=None):
        if isinstance(Strategy.instance, strategy):
            if callback:
                IOLoop.instance().add_callback(callback)
            return Strategy.instance
                
        return strategy(session, callback)

    def __init__(self, session, callback=None):
        self.session = session
        Strategy.instance = self
        if callback:
            IOLoop.instance().add_callback(lambda: callback(True))

    def add_effect(self, url, instance_id, callback=None):
        def _callback(instance_id):
            if callback is None:
                return
            callback(bool(instance_id))
        self.session.add(url, instance_id, _callback)

    def remove_effect(self, instance_id, callback):
        self.session.remove(instance_id, callback)

class FreeAssociation(Strategy):
    pass

class Stompbox(Strategy):
    margin_top = 80
    margin_left = 250
    margin_bottom = 50
    margin_right = 250
    plugin_distance = 100
    average_width = 600

    def __init__(self, session, callback):
        super(Stompbox, self).__init__(session)
        self.effects = [None] * 4
        self.index = EffectIndex()
        if callback is None:
            callback = lambda result: None
        def initial_connection(result):
            self.connect(self.get_outputs(-1),
                         self.get_inputs(4),
                         lambda: callback(result))
        session.reset(initial_connection)
        
    def add_effect(self, url, slot, callback=None):
        def add(instance_id):
            self.insert(url, slot, instance_id, callback)
        self.session.add(url, None, add)

    def insert(self, url, slot, instance_id, callback):
        effect = self.index.get(url=url)
        self.effects[slot] = (instance_id, effect)
        previous_outputs = self.get_outputs(slot-1)
        my_inputs = self.get_inputs(slot)
        my_outputs = self.get_outputs(slot)
        next_inputs = self.get_inputs(slot+1)

        self.async_jobs([
                [self.disconnect, previous_outputs, next_inputs],
                [self.connect, previous_outputs, my_inputs],
                [self.connect, my_outputs, next_inputs],
                [self.calculate_positions],
                ], lambda: callback(True))

    def get_outputs(self, slot):
        if slot < 0:
            return ('system:capture_1', 'system:capture_2')

        if self.effects[slot] is None:
            return self.get_outputs(slot-1)

        instance_id, effect = self.effects[slot]
        return (self.get_port_id(instance_id, effect['ports']['audio']['output'], 'left'),
                self.get_port_id(instance_id, effect['ports']['audio']['output'], 'right'),
                )

    def get_inputs(self, slot):
        if slot >= len(self.effects):
            return ('system:playback_1', 'system:playback_2')

        if self.effects[slot] is None:
            return self.get_inputs(slot+1)

        instance_id, effect = self.effects[slot]
        return (self.get_port_id(instance_id, effect['ports']['audio']['input'], 'left'),
                self.get_port_id(instance_id, effect['ports']['audio']['input'], 'right'),
                )

    def get_port_id(self, instance_id, ports, channel):
        for port in ports:
            if port[channel]:
                return "%d:%s" % (instance_id, port['symbol'])

    def connect(self, outputs, inputs, callback):
        jobs = []
        if outputs[0] is not None and inputs[0] is not None:
            jobs.append([self.session.connect, outputs[0], inputs[0]])
        if outputs[1] is not None and inputs[1] is not None:
            jobs.append([self.session.connect, outputs[1], inputs[1]])
        self.async_jobs(jobs, callback)

    def disconnect(self, outputs, inputs, callback):
        jobs = []
        if outputs[0] is not None and inputs[0] is not None:
            jobs.append([self.session.disconnect, outputs[0], inputs[0]])
        if outputs[1] is not None and inputs[1] is not None:
            jobs.append([self.session.disconnect, outputs[1], inputs[1]])
        self.async_jobs(jobs, callback)

    def calculate_positions(self, callback):
        height = 0
        for effect in self.effects:
            if effect is None:
                continue
            instance_id, effect = effect
            height = max(height, effect['gui']['height'])
        x = self.margin_left
        for effect in self.effects:
            if effect is None:
                x += self.average_width
                continue
            instance_id, effect = effect
            y = self.margin_top + (height - effect['gui']['height'])/2
            self.session.effect_position(instance_id, x, y)
            x += effect['gui']['width'] + self.plugin_distance

        self.session.pedalboard_size(x + self.margin_right,
                                     height + self.margin_top + self.margin_bottom)

        callback()
            
        
    def async_jobs(self, jobs, callback):
        def process(result=None):
            if len(jobs) == 0:
                if callback:
                    IOLoop.instance().add_callback(callback)
                return
            job = jobs.pop(0)
            method = job.pop(0)
            method(*job, callback=process)
        IOLoop.instance().add_callback(process)
