# -*- coding: utf-8 -*-

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

import logging
from tornado import ioloop
from mod.hmi import HMI
from mod.host import Host

class FakeCommunicator(object):
    def init(self, callback):
        pass

    def send(self, msg, callback, datatype=None):
        logging.info(msg)
        if callback is None:
            return
        if datatype == 'boolean':
            callback(True)
        else:
            callback(0)

class FakeHMI(FakeCommunicator, HMI):
    pass

class FakeHost(FakeCommunicator, Host):
    def __del__(self):
        self.sock = None

    def init_connection(self):
        self.open_connection_if_needed(lambda:None)

    def open_connection_if_needed(self, callback):
        if self.sock is None:
            self.sock = True
            self._timer = ioloop.PeriodicCallback(self._timer_callback, 500)

        callback()

    def _send(self, msg, callback=lambda r:r, datatype='int'):
        callback(True)

        msg = msg.replace("[]","",1).strip()
        msg = [line.strip() for line in msg.split("\n")]
        #print("_send", msg)

        method = msg[0]

        if method == "a patch:Get ;":
            pass
        elif method == "a patch:Set ;":
            pass
        elif method == "a patch:Put ;":
            pass

        #a patch:Get ;
        #patch:subject </engine> .

        #a patch:Get ;
        #patch:subject </graph> .

        #a patch:Put ;
        #patch:subject </graph/autopan> ;
        #patch:body [
        #a ingen:Block ;
        #<http://lv2plug.in/ns/lv2core#prototype> <http://moddevices.com/plugins/tap/autopan> ;
        #ingen:enabled true ;
        #ingen:canvasX 1589.718750 ;
        #ingen:canvasY 404.000000 ;
 #] .

    def _timer_callback(self):
        pass

    #def param_get(self, instance_id, symbol, callback=lambda result: None):
        #callback({'ok': True, 'value': 17})

    #def cpu_load(self, callback=lambda result: None):
        #callback({'ok': True, 'value': random.random()*100})
