# coding: utf-8

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


from datetime import timedelta
from tornado.iostream import BaseIOStream
from tornado import ioloop

from mod.protocol import Protocol, ProtocolError
from mod import get_hardware_actuators, get_hardware_descriptor

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
        try:
            r = self.sp.read(self.read_chunk_size)
        except:
            print("SerialIOStream: failed to read from HMI serial")
            return None
        if r == '':
            return None
        return r

class HMI(object):
    def __init__(self, port, baud_rate, callback):
        logging.basicConfig(level=logging.DEBUG)
        self.sp = None
        self.port = port
        self.baud_rate = baud_rate
        self.queue = []
        self.queue_idle = True
        self.initialized = False
        self.ioloop = ioloop.IOLoop.instance()
        hw_actuators = get_hardware_actuators()
        self.hw_ids = [actuator['id'] for actuator in hw_actuators]
        self.init(callback)

    # this can be overriden by subclasses to avoid any connection in DEV mode
    def init(self, callback):
        try:
            print("{0}, {1}".format(self.port, self.baud_rate))
            sp = None
            try:
                sp = serial.Serial(self.port, self.baud_rate, timeout=0, write_timeout=0)
            except:
                sp = serial.Serial(self.port, self.baud_rate, timeout=0, writeTimeout=0)
            sp.flushInput()
            sp.flushOutput()
        except Exception as e:
            print("ERROR: Failed to open HMI serial port, error was:\n%s" % e)
            return

        self.sp = SerialIOStream(sp)

        def clear_callback(ok):
            callback()

        # calls ping until ok is received
        def ping_callback(ok):
            if ok:
                self.clear(clear_callback)
            else:
                self.ioloop.add_timeout(timedelta(seconds=1), lambda:self.ping(ping_callback))

        self.ping(ping_callback)
        self.checker()

    def checker(self, data=None):
        if data is not None:
            logging.info('[hmi] received <- %s' % repr(data))
            try:
                msg = Protocol(data.decode("utf-8", errors="ignore"))
            except ProtocolError as e:
                logging.error('[hmi] error parsing msg %s' % repr(data))
                logging.error('[hmi]   error code %s' % e.error_code())
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
                        self.process_queue()
                else:
                    def _callback(resp, resp_args=None):
                        if resp_args is None:
                            logging.info('[hmi]     sent "resp {0}"'.format(resp))
                            self.send("resp %d" % (0 if resp else -1))
                        else:
                            logging.info('[hmi]     sent "resp {0} {1}"'.format(resp, resp_args))
                            self.send("resp %d %s" % (0 if resp else -1, resp_args))

                    msg.run_cmd(_callback)
        try:
            self.sp.read_until(b'\0', self.checker)
        except serial.SerialException as e:
            logging.error("[hmi] error while reading %s" % e)

    def process_queue(self):
        if self.sp is None:
            return

        try:
            msg, callback, datatype = self.queue[0] # fist msg on the queue
            logging.info("[hmi] popped from queue: %s" % msg)
            self.sp.write(bytes(msg, 'utf-8') + b"\0")
            logging.info("[hmi] sending -> %s" % msg)
            self.queue_idle = False
        except IndexError:
            logging.info("[hmi] queue is empty, nothing to do")
            self.queue_idle = True

    def reply_protocol_error(self, error):
        #self.send(error) # TODO: proper error handling, needs to be implemented by HMI
        self.send("resp -1")

    def send(self, msg, callback=None, datatype='int'):
        if self.sp is None:
            return

        if not any([ msg.startswith(resp) for resp in Protocol.RESPONSES ]):
            self.queue.append((msg, callback, datatype))
            logging.info("[hmi] scheduling -> %s" % str(msg))
            if self.queue_idle:
                self.process_queue()
            return

        # is resp, just send
        self.sp.write(msg.encode('utf-8') + b'\0')

    def initial_state(self, bank_id, pedalboard_id, pedalboards, callback):
        numBytesFree = 1024-64
        pedalboardsData = None

        num = 0
        for pb in pedalboards:
            if num > 50:
                break

            title   = pb['title'].replace('"', '').upper()[:31]
            data    = '"%s" %i' % (title, num)
            dataLen = len(data)

            if numBytesFree-dataLen-2 < 0:
                print("ERROR: Controller out of memory when sending initial state (stopped at %i)" % num)
                if pedalboard_id >= num:
                    pedalboard_id = 0
                break

            num += 1

            if pedalboardsData is None:
                pedalboardsData = ""
            else:
                pedalboardsData += " "

            numBytesFree -= dataLen+1
            pedalboardsData += data

        if pedalboardsData is None:
            pedalboardsData = ""

        self.send("initial_state %d %d %s" % (bank_id, pedalboard_id, pedalboardsData), callback)

    def ui_con(self, callback):
        self.send("ui_con", callback, datatype='boolean')

    def ui_dis(self, callback):
        self.send("ui_dis", callback, datatype='boolean')


    def control_add(self, data, hw_id, actuator_uri, callback):
        # instance_id = data['instance_id']
        # port = data['port']
        label = data['label']
        var_type = data['hmitype']
        unit = data['unit']
        value = data['value']
        min = data['minimum']
        max = data['maximum']
        steps = data['steps']
        n_controllers = data['addrs_max']
        index = data['addrs_idx']
        options = data['options']
        # tempo = data['tempo']
        # dividers = data['dividers']

        # hw_type = actuator[0]
        # hw_id = actuator[1]
        # actuator_type = actuator[2]
        # actuator_id = actuator[3]

        label = '"%s"' % label.upper().replace('"', "")
        unit = '"%s"' % unit.replace('"', '')
        optionsData = []

        rmax = max
        if options:
            currentNum = 0
            numBytesFree = 1024-128

            for o in options:
                if currentNum > 50:
                    if value >= currentNum:
                        value = 0
                    rmax = currentNum
                    break

                data    = '"%s" %f' % (o[1].replace('"', '').upper(), float(o[0]))
                dataLen = len(data)

                if numBytesFree-dataLen-2 < 0:
                    print("ERROR: Controller out of memory when sending options (stopped at %i)" % currentNum)
                    if value >= currentNum:
                        value = 0.0
                    rmax = currentNum
                    break

                currentNum += 1
                numBytesFree -= dataLen+1
                optionsData.append(data)

        options = "%d %s" % (len(optionsData), " ".join(optionsData))
        options = options.strip()

        def control_add_callback(ok):
            self.control_set_index(hw_id, index, n_controllers, callback)

        cb = callback
        platform = get_hardware_descriptor().get('platform', 'Unknown')

        if not actuator_uri.startswith("/hmi/footswitch") and platform == 'duo':
            cb = control_add_callback

        self.send('control_add %d %s %d %s %f %f %f %d %s' %
                  ( hw_id,
                    label,
                    var_type,
                    unit,
                    value,
                    rmax,
                    min,
                    steps,
                    options,
                  ),
                  cb, datatype='boolean')

    def control_set_index(self, hw_id, index, n_controllers, callback):
        self.send('control_set_index %d %d %d' % (hw_id, index, n_controllers), callback, datatype='boolean')

    def control_set(self, hw_id, value, callback):
        """Set a plug-in's control port value on the HMI."""
        # control_set <hw_id> <value>"""
        self.send('control_set %d %f' %
                  (hw_id, value),
                  callback, datatype='boolean')

    def control_rm(self, hw_ids, callback):
        """
        removes an addressing
        """

        idsData = []
        currentNum = 0
        numBytesFree = 1024-128

        for id in hw_ids:
            data    = '%d' % (id)
            dataLen = len(data)

            if numBytesFree-dataLen-2 < 0:
                print("ERROR: Controller out of memory when sending hw_ids (stopped at %i)" % currentNum)
                break

            currentNum += 1
            numBytesFree -= dataLen+1
            idsData.append(data)

        ids = "%s" % (" ".join(idsData))
        ids = ids.strip()
        self.send('control_rm %s' % (ids), callback, datatype='boolean')

    def ping(self, callback):
        self.send('ping', callback, datatype='boolean')

    def tuner(self, freq, note, cents, callback):
        self.send('tuner %f %s %f' % (freq, note, cents), callback)

    def xrun(self, callback):
        self.send('xrun', callback)

    def bank_config(self, hw_id, action, callback):
        """
        configures bank addressings

        action is one of the following:
            0: None (usado para des-endereçar)
            1: True Bypass
            2: Pedalboard UP
            3: Pedalboard DOWN
        """
        self.send('bank_config %d %d' % (hw_id, action), callback, datatype='boolean')

    # new messages

    def clear(self, callback):
        self.control_rm(self.hw_ids, callback)
