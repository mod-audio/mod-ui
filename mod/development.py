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

from tornado.ioloop import IOLoop
import logging
from mod.hmi import HMI
from mod.host import Host

class FakeCommunicator(object):
    def send(self, msg, callback, datatype=None):
        logging.info(msg)
        if datatype == 'boolean':
            IOLoop.instance().add_callback(lambda: callback(True))
        else:
            IOLoop.instance().add_callback(lambda: callback(0))

    def open_connection(self, callback):
        IOLoop.instance().add_callback(callback)

class FakeHMI(FakeCommunicator, HMI):
    pass

class FakeHost(FakeCommunicator, Host):
    def param_get(self, instance_id, symbol, callback=lambda result: None):
        IOLoop.instance().add_callback(lambda: callback({'ok': True, 'value': 17}))

    def add(self, uri, instance_id, callback=lambda result: None):
        IOLoop.instance().add_callback(lambda: callback(instance_id))


