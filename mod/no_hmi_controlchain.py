# coding: utf-8

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


from tornado.iostream import BaseIOStream
from tornado import ioloop

import serial, logging
import time

class SerialIOStream(BaseIOStream):
    def __init__(self, sp):
        self.sp = sp
        super(SerialIOStream, self).__init__()

    def fileno(self):
        return self.sp.fileno()

    def close_fd(self):
        return self.sp.close()

    def write_to_fd(self, data):
        try:
            return self.sp.write(data)
        except serial.SerialTimeoutException:
            return 0

    def read_from_fd(self):
        r = self.sp.read(self.read_chunk_size)
        if r == '':
            return None
        return r

from mod.development import FakeHMI, FakeCommunicator
class CC(FakeHMI):
    def __init__(self, port, baud_rate, callback):
        self.port = port
        self.baud_rate = baud_rate
        self.queue = []
        self.queue_idle = True
        self.ioloop = ioloop.IOLoop.instance()

        self.sp = self.open_connection(callback)


    def open_connection(self, callback):
        sp = serial.Serial(self.port, self.baud_rate, timeout=0, writeTimeout=0)
        sp.flushInput()
        sp.flushOutput()

        self.ioloop.add_callback(self.checker)
        self.ioloop.add_callback(callback)

        return SerialIOStream(sp)

    def checker(self, data=None):
        if data is not None and data != 'xuxu':
            logging.info('[cc] received <- %s' % repr(data))
            msg = data.replace("xuxu", "")
            try:
                self.msg_callback(msg, lambda: None)
            except AssertionError, e:
                print repr(msg)
                print e
        try:
            self.sp.read_until('xuxu', self.checker)
        except serial.SerialException, e:
            logging.error("[hmi] error while reading %s" % e)

    def build_msg(self, msg, args=[]):
        return msg

    def send(self, msg, args=[], callback=None, datatype='int'):
        self.sp.write(msg)
        logging.info('[cc] sent -> %s' % repr(msg))

class FakeCC(CC):
    def open_connection(self, callback):
        callback()

    def send(self, msg, args=[], callback=None, datatype='int'):
        logging.info(msg)
        if datatype == 'boolean':
            callback(True)
        else:
            callback(0)

