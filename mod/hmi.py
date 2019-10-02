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
from tornado.iostream import BaseIOStream, StreamClosedError
from tornado import ioloop

from mod import get_hardware_actuators, get_hardware_descriptor
from mod.protocol import Protocol, ProtocolError, process_resp

import logging
import serial
import time

class Menu(object):
    # implemented
    STEREOLINK_INP_ID     = 13
    STEREOLINK_OUTP_ID    = 23
    MASTER_VOL_PORT_ID    = 24
    FOOTSWITCH_NAVEG_ID   = 150
    PLAY_STATUS_ID        = 180
    TEMPO_BPM_ID          = 181
    TEMPO_BPB_ID          = 182
    SYS_CLK_SOURCE_ID     = 202
    MIDI_CLK_SEND_ID      = 203
    SNAPSHOT_PRGCHGE_ID   = 204
    PB_PRGCHNGE_ID        = 205

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
    def __init__(self, port, baud_rate, timeout, init_cb, reinit_cb):
        self.sp = None
        self.port = port
        self.baud_rate = baud_rate
        self.queue = []
        self.queue_idle = True
        self.initialized = False
        self.need_flush = 0 # 0 means False, otherwise use it as counter
        self.flush_io = None
        self.last_write_time = 0
        self.timeout = timeout # in seconds
        self.ioloop = ioloop.IOLoop.instance()
        self.reinit_cb = reinit_cb
        self.hw_desc = get_hardware_descriptor()
        hw_actuators = self.hw_desc.get('actuators', [])
        self.hw_ids = [actuator['id'] for actuator in hw_actuators]
        self.bpm = None
        self.init(init_cb)

    def isFake(self):
        return False

    # this can be overriden by subclasses to avoid any connection in DEV mode
    def init(self, callback):
        try:
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
                self.ioloop.add_timeout(1, lambda:self.ping(ping_callback))

        self.ping(ping_callback)
        self.checker()

    def checker(self, data=None):
        if data is not None and data != b'\0':
            self.last_write_time = 0
            logging.debug('[hmi] received <- %s', data)
            try:
                msg = Protocol(data.decode("utf-8", errors="ignore"))
            except ProtocolError as e:
                logging.error('[hmi] error parsing msg %s', data)
                logging.error('[hmi]   error code %s', e.error_code())
                self.reply_protocol_error(e.error_code())
            else:
                # reset timeout checks when a message is received
                self.need_flush = 0
                if self.flush_io is not None:
                    self.ioloop.remove_timeout(self.flush_io)
                    self.flush_io = None

                if msg.is_resp():
                    try:
                        original_msg, callback, datatype = self.queue.pop(0)
                        logging.debug("[hmi] popped from queue: %s", original_msg)
                    except IndexError:
                        # something is wrong / not synced!!
                        logging.error("[hmi] NOT SYNCED")
                    else:
                        if callback is not None:
                            logging.debug("[hmi] calling callback for %s", original_msg)
                            callback(msg.process_resp(datatype))
                        self.process_queue()
                else:
                    def _callback(resp, resp_args=None):
                        resp = 0 if resp else -1
                        if resp_args is None:
                            self.send_reply("resp %d" % resp)
                            logging.debug('[hmi]     sent "resp %s"', resp)

                        else:
                            self.send_reply("resp %d %s" % (resp, resp_args))
                            logging.debug('[hmi]     sent "resp %s %s"', resp, resp_args)

                    msg.run_cmd(_callback)

        if self.need_flush != 0:
            if self.flush_io is not None:
                self.ioloop.remove_timeout(self.flush_io)
            self.flush_io = self.ioloop.call_later(self.timeout/2, self.flush)

        try:
            self.sp.read_until(b'\0', self.checker)
        except serial.SerialException as e:
            logging.error("[hmi] error while reading %s", e)

    def flush(self, forced = False):
        prev_queue = self.need_flush
        self.need_flush = 0

        if len(self.queue) < max(5, prev_queue) and not forced:
            logging.debug("[hmi] flushing ignored")
            return

        # FUCK!
        logging.warn("[hmi] flushing queue as workaround now: %d in queue", len(self.queue))
        self.sp.sp.flush()
        self.sp.sp.flushInput()
        self.sp.sp.flushOutput()
        self.sp.close()
        self.sp = None

        while len(self.queue) > 1:
            msg, callback, datatype = self.queue.pop(0)

            if any(msg.startswith(resp) for resp in Protocol.RESPONSES):
                if callback is not None:
                    callback(process_resp(None, datatype))
            else:
                if callback is not None:
                    callback("-1003")

        self.reinit_cb()

        #os.system("touch /tmp/reset-hmi; kill -9 {}".format(os.getpid()))

    def process_queue(self):
        if self.sp is None:
            return

        try:
            msg, callback, datatype = self.queue[0] # fist msg on the queue
        except IndexError:
            logging.debug("[hmi] queue is empty, nothing to do")
            self.queue_idle = True
            self.last_write_time = 0
        else:
            logging.debug("[hmi] sending -> %s", msg)
            try:
                self.sp.write(msg.encode('utf-8') + b'\0')
            except StreamClosedError as e:
                logging.exception(e)
                self.sp = None

            self.queue_idle = False
            self.last_write_time = time.time()

    def reply_protocol_error(self, error):
        #self.send(error) # TODO: proper error handling, needs to be implemented by HMI
        self.send("resp -1", None)

    def send(self, msg, callback, datatype='int'):
        if self.sp is None:
            return

        if self.timeout > 0:
            if len(self.queue) > 30:
                self.need_flush = len(self.queue)

            elif self.last_write_time != 0 and time.time() - self.last_write_time > self.timeout:
                logging.warn("[hmi] no response for %ds, giving up", self.timeout)
                if self.flush_io is not None:
                    self.ioloop.remove_timeout(self.flush_io)
                    self.flush_io = None
                self.flush(True)

        if not any([ msg.startswith(resp) for resp in Protocol.RESPONSES ]):
            # make an exception for control_set, calling callback right away without waiting
            #if msg.startswith("s "):
                #self.queue.append((msg, None, datatype))
                #if callback is not None:
                    #callback(True)
            #else:
            self.queue.append((msg, callback, datatype))
            logging.debug("[hmi] scheduling -> %s", msg)
            if self.queue_idle:
                self.process_queue()
            return

        # is resp, just send
        self.sp.write(msg.encode('utf-8') + b'\0')

    def send_reply(self, msg):
        if self.sp is None:
            return

        self.sp.write(msg.encode('utf-8') + b'\0')

    def initial_state(self, bank_id, pedalboard_id, pedalboards, callback):
        numPedals = len(pedalboards)

        if numPedals <= 9 or pedalboard_id < 4:
            startIndex = 0
        elif pedalboard_id+4 >= numPedals:
            startIndex = numPedals - 9
        else:
            startIndex = pedalboard_id - 4

        endIndex = min(startIndex+9, numPedals)

        data = 'is %d %d %d %d %d' % (numPedals, startIndex, endIndex, bank_id, pedalboard_id)

        for i in range(startIndex, endIndex):
            data += ' "%s" %d' % (pedalboards[i]['title'].replace('"', '')[:31].upper(), i+1)

        self.send(data, callback)

    def ui_con(self, callback):
        self.send("ui_con", callback, 'boolean')

    def ui_dis(self, callback):
        self.send("ui_dis", callback, 'boolean')

    def control_add(self, data, hw_id, actuator_uri, callback):
        # instance_id = data['instance_id']
        # port = data['port']
        hasTempo = data.get('tempo', False)
        label = data['label']
        var_type = data['hmitype']
        unit = data['unit']
        value = data['dividers'] if hasTempo else data['value']
        xmin = data['minimum']
        xmax = data['maximum']
        steps = data['steps']
        options = data['options']
        hmi_set_index = self.hw_desc.get('hmi_set_index', False)

        if data.get('group', None) is not None:
            if var_type & 0x100: # HMI_ADDRESSING_TYPE_REVERSE_ENUM
                prefix = "- "
            else:
                prefix = "+ "
            label = prefix + label

        label = '"%s"' % label.replace('"', "")[:31].upper()
        unit = '"%s"' % unit.replace('"', '')[:7]

        if value < xmin:
            logging.error('[hmi] control_add received value < min for %s', label)
            value = xmin
        elif value > xmax:
            logging.error('[hmi] control_add received value > max for %s', label)
            value = xmax

        if options:
            numOpts = len(options)
            optionsData = []

            for i, (ovalue, _) in enumerate(options):
                if ovalue == value:
                    ivalue = i
                    break
            else:
                logging.error("[hmi] control_add received value which is not in list (%f) for %s", value, label)
                ivalue = int(value)

            if hasTempo:
                unit = '""'
                startIndex = 0
                endIndex = numOpts
            else:
                if numOpts <= 5 or ivalue <= 2:
                    startIndex = 0
                elif ivalue+2 >= numOpts:
                    startIndex = numOpts-5
                else:
                    startIndex = ivalue - 2
                endIndex = min(startIndex+5, numOpts)

            isPaginated = int(startIndex != 0 or endIndex != numOpts)

            for i in range(startIndex, endIndex):
                option = options[i]
                xdata  = '"%s" %f' % (option[1].replace('"', '')[:31].upper(), float(option[0]))
                optionsData.append(xdata)

            options = "%d %d %s" % (len(optionsData), isPaginated, " ".join(optionsData))
            options = options.strip()

        else:
            options = "0"

        def control_add_callback(ok):
            if not ok:
                callback(False)
                return
            n_controllers = data['addrs_max']
            index = data['addrs_idx']
            self.control_set_index(hw_id, index, n_controllers, callback)

        cb = callback

        if not actuator_uri.startswith("/hmi/footswitch") and hmi_set_index:
            cb = control_add_callback

        self.send('a %d %s %d %s %f %f %f %d %s' %
                  ( hw_id,
                    label,
                    var_type,
                    unit,
                    value,
                    xmax,
                    xmin,
                    steps,
                    options,
                  ),
                  cb, 'boolean')

    def control_set_index(self, hw_id, index, n_controllers, callback):
        self.send('si %d %d %d' % (hw_id, index, n_controllers), callback, 'boolean')

    def control_set(self, hw_id, value, callback):
        """Set a plug-in's control port value on the HMI."""
        # control_set <hw_id> <value>"""
        self.send('s %d %f' % (hw_id, value), callback, 'boolean')

    def control_rm(self, hw_ids, callback):
        """
        removes an addressing
        """

        idsStr = tuple(str(i) for i in hw_ids)

        ids = "%s" % (" ".join(idsStr))
        ids = ids.strip()
        self.send('rm %s' % (ids), callback, 'boolean')

    def ping(self, callback):
        self.send('ping', callback, 'boolean')

    def tuner(self, freq, note, cents, callback):
        self.send('tu_v %f %s %f' % (freq, note, cents), callback)

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
        self.send('bank_config %d %d' % (hw_id, action), callback, 'boolean')

    def set_bpm(self, bpm):
        if int(bpm) != self.bpm:
            self.bpm = int(bpm)
            return True
        return False

    # new messages

    def clear(self, callback):
        self.send("pb_cl", callback)

    def set_profile_value(self, key, value, callback):
        # Do not send new bpm value to HMI if its int value is the same
        if key == Menu.TEMPO_BPM_ID and not self.set_bpm(value):
            callback(True)
        else:
            self.send("mc %i %i" % (key, int(value)), callback, 'boolean')

    def set_profile_values(self, playback_rolling, values, callback):
        msg  = "mc"
        msg += " %i %i" % (Menu.PLAY_STATUS_ID, int(playback_rolling))
        msg += " %i %i" % (Menu.STEREOLINK_INP_ID, int(values['inputStereoLink']))
        msg += " %i %i" % (Menu.STEREOLINK_OUTP_ID, int(values['outputStereoLink']))
        msg += " %i %i" % (Menu.MASTER_VOL_PORT_ID, int(values['masterVolumeChannelMode']))
        msg += " %i %i" % (Menu.SYS_CLK_SOURCE_ID, values['transportSource'])
        msg += " %i %i" % (Menu.MIDI_CLK_SEND_ID, int(values['midiClockSend']))
        msg += " %i %i" % (Menu.SNAPSHOT_PRGCHGE_ID, values['midiChannelForSnapshotsNavigation'])
        msg += " %i %i" % (Menu.PB_PRGCHNGE_ID, values['midiChannelForPedalboardsNavigation'])
        self.send(msg, callback)
