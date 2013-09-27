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

from mod.protocol import Protocol, ProtocolError

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

class HMI(object):
    def __init__(self, port, baud_rate, callback):
        self.port = port
        self.baud_rate = baud_rate
        self.queue = []
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
        if data is not None:
            logging.info('[hmi] received <- %s' % repr(data))
            try:
                msg = Protocol(data)
            except ProtocolError, e:
                logging.error('[hmi] error parsing msg %s' % repr(data))
                self.reply_protocol_error(e.error_code())
            else:
                if msg.is_resp():
                    try:
                        original_msg, callback, datatype = self.queue.pop(0)
                    except IndexError:
                        # something is wrong / not synced!!
                        logging.error("[hmi] NOT SYNCED")
                    else:
                        if callback is not None:
                            logging.info("[hmi] calling callback for %s" % original_msg)
                            callback(msg.process_resp(datatype))
                else:
                    def _callback(resp, resp_args=None):
                        if resp_args is None:
                            self.send("resp %d" % (0 if resp else -1))
                        else:
                            self.send("resp %d %s" % (0 if resp else -1, resp_args))

                    msg.run_cmd(_callback)
        try:
            self.sp.read_until('\0', self.checker)
        except serial.SerialException, e:
            logging.error("[hmi] error while reading %s" % e)


    def reply_protocol_error(self, error):
        #self.send(error) # TODO: proper error handling, needs to be implemented by HMI
        self.send("resp -1")

    def send(self, msg, callback=None, datatype='int'):
        if not any([ msg.startswith(resp) for resp in Protocol.RESPONSES ]):
            self.queue.append((msg, callback, datatype))
        logging.info("[hmi] sending -> %s" % str(msg))
        self.sp.write("%s\0" % str(msg))

    def ui_con(self, callback=lambda result: None):
        self.send("ui_con", callback, datatype='boolean')

    def ui_dis(self, callback=lambda result: None):
        self.send("ui_dis", callback, datatype='boolean')

    def control_add(self, instance_id, symbol, label, var_type, unit, value, max, 
                    min, steps, hw_type, hw_id, actuator_type, actuator_id, 
                    options=[], callback=lambda result: None):
        """
        addresses a new control
        var_type is one of the following:
            0 linear
            1 log
            2 enumeration
            3 toggled
            4 trigger
            5 tap tempo
            6 bypass
        """
        label = '"%s"' % label.upper().replace('"', "")
        unit = '"%s"' % unit.replace('"', '')
        length = len(options)
        if options:
            options = [ '"%s" %f' % (o[1].replace('"', '').upper(), float(o[0]))
                        for o in options ]
        options = "%d %s" % (length, " ".join(options))
        options = options.strip()

        self.send('control_add %d %s %s %d %s %f %f %f %d %d %d %d %d %s' %
                  ( instance_id,
                    symbol,
                    label,
                    var_type,
                    unit,
                    value,
                    max,
                    min,
                    steps,
                    hw_type,
                    hw_id,
                    actuator_type,
                    actuator_id,
                    options,
                  ),
                  callback, datatype='boolean')

    def control_rm(self, instance_id, symbol, callback=lambda result: None):
        """
        removes an addressing

        if instance_id is -1 will remove all addressings
        if symbol == ":all" will remove every addressing for the instance_id
        """
        self.send('control_rm %d %s' % (instance_id, symbol), callback, datatype='boolean')

    def ping(self, callback=lambda result: None):
        self.send('ping', callback, datatype='boolean')

    def clipmeter(self, position, callback=lambda result: None):
        self.send('clipmeter %d' % position, callback)

    def peakmeter(self, position, value, callback=lambda result: None):
        self.send('peakmeter %d %f' % (position, value), callback)

    def tuner(self, freq, note, cents, callback=lambda result: None):
        self.send('tuner %f %s %f' % (freq, note, cents), callback)

    def xrun(self, callback=lambda result: None):
        self.send('xrun', callback)

    def bank_config(self, hw_type, hw_id, actuator_type, actuator_id, action, callback=lambda result: None):
        """
        configures bank addressings

        action is one of the following:
            0: None (usado para des-endereçar)
            1: True Bypass
            2: Pedalboard UP
            3: Pedalboard DOWN
        """
        self.send('bank_config %d %d %d %d %d' % (hw_type, hw_id, actuator_type, actuator_id, action), callback, datatype='boolean')

