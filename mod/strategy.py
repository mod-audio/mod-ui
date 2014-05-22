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
        self.session.add(url, instance_id, callback)

    def remove_effect(self, instance_id, callback):
        self.session.remove(instance_id, callback)

class FreeAssociation(Strategy):
    pass

class Stompbox(Strategy):
    def __init__(self, session, callback):
        super(Stompbox, self).__init__(session)
        self.effects = [None] * 4
        self.index = EffectIndex()
        session.reset(callback)
        
    def add_effect(self, url, slot, callback=None):
        effect = self.index.find(url=url).next()
        def add(instance_id):
            self.effects[slot] = (instance_id, effect)
            if callback:
                callback(True)
        self.session.add(url, None, add)
