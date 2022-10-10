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
from tornado.ioloop import IOLoop
from unicodedata import normalize

from mod import get_hardware_actuators, get_hardware_descriptor, get_nearest_valid_scalepoint_value, normalize_for_hw
from mod.protocol import Protocol, ProtocolError, process_resp
from mod.mod_protocol import (
    CMD_PING,
    CMD_GUI_CONNECTED,
    CMD_GUI_DISCONNECTED,
    CMD_INITIAL_STATE,
    CMD_CONTROL_ADD,
    CMD_CONTROL_REMOVE,
    CMD_CONTROL_SET,
    CMD_PEDALBOARD_CHANGE,
    CMD_PEDALBOARD_CLEAR,
    CMD_PEDALBOARD_NAME_SET,
    CMD_SNAPSHOT_NAME_SET,
    CMD_TUNER,
    CMD_MENU_ITEM_CHANGE,
    CMD_RESET_EEPROM,
    CMD_DUO_CONTROL_INDEX_SET,
    CMD_DUO_BANK_CONFIG,
    CMD_DUOX_PAGES_AVAILABLE,
    CMD_DUOX_EXP_OVERCURRENT,
    CMD_RESPONSE,
    CMD_RESTORE,
    FLAG_CONTROL_MOMENTARY,
    FLAG_CONTROL_REVERSE,
    FLAG_CONTROL_TAP_TEMPO,
    FLAG_PAGINATION_PAGE_UP,
    FLAG_PAGINATION_WRAP_AROUND,
    FLAG_PAGINATION_INITIAL_REQ,
    FLAG_PAGINATION_ALT_LED_COLOR,
    MENU_ID_TEMPO,
    MENU_ID_PLAY_STATUS,
    MENU_ID_SL_IN,
    MENU_ID_SL_OUT,
    MENU_ID_MASTER_VOL_PORT,
    MENU_ID_MIDI_CLK_SOURCE,
    MENU_ID_MIDI_CLK_SEND,
    MENU_ID_SNAPSHOT_PRGCHGE,
    MENU_ID_PB_PRGCHNGE,
    cmd_to_str,
)
from mod.settings import LOG

import logging
import serial
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
    def __init__(self, port, baud_rate, timeout, init_cb, reinit_cb):
        self.sp = None
        self.port = port
        self.baud_rate = baud_rate
        self.queue = []
        self.queue_idle = True
        self.initialized = False
        self.connected = False
        self.handling_response = False
        self.need_flush = 0 # 0 means False, otherwise use it as counter
        self.flush_io = None
        self.last_write_time = 0
        self.timeout = timeout # in seconds
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
        ioloop = IOLoop.instance()
        try:
            sp = None
            # pylint: disable=unexpected-keyword-arg
            try:
                sp = serial.Serial(self.port, self.baud_rate, timeout=0, write_timeout=0)
            except:
                sp = serial.Serial(self.port, self.baud_rate, timeout=0, writeTimeout=0)
            # pylint: enable=unexpected-keyword-arg
            sp.flushInput()
            sp.flushOutput()
        except Exception as e:
            print("ERROR: Failed to open HMI serial port, error was:\n%s" % e)
            return

        self.sp = SerialIOStream(sp)
        self.ping_io = None

        def clear_callback(ok):
            callback()

        # calls ping until ok is received
        def ping_callback(ok):
            if self.ping_io is not None:
                ioloop.remove_timeout(self.ping_io)
                self.ping_io = None

            if ok:
                self.clear(clear_callback)
            else:
                ioloop.call_later(1, call_ping)

        def call_ping():
            sp.flushInput()
            sp.flushOutput()
            self.queue = []
            self.queue_idle = True

            self.ping(ping_callback)
            self.ping_io = ioloop.call_later(1, call_ping)

        call_ping()
        self.checker()

    def checker(self, data=None):
        ioloop = IOLoop.instance()

        if data is not None and data != b'\0':
            self.last_write_time = 0
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
                    ioloop.remove_timeout(self.flush_io)
                    self.flush_io = None

                if msg.is_resp():
                    try:
                        original_msg, callback, datatype = self.queue.pop(0)
                        withlog = LOG >= 2 or (LOG and original_msg not in ("pi",))
                        if withlog:
                            logging.debug('[hmi] received response <- %s', data)
                            logging.debug("[hmi] popped from queue: %s | %s",
                                          original_msg, cmd_to_str(original_msg.split(" ",1)[0]))
                    except IndexError:
                        # something is wrong / not synced!!
                        logging.error("[hmi] NOT SYNCED after receiving %s", data)
                    else:
                        if callback is not None:
                            if withlog:
                                logging.debug("[hmi] calling callback for %s", original_msg)
                            callback(msg.process_resp(datatype))
                        self.process_queue()
                else:
                    def _callback(resp, resp_args=None):
                        if not isinstance(resp, int):
                            resp = 0 if resp else -1
                        if resp_args is None:
                            self.send_reply("%s %d" % (CMD_RESPONSE, resp))
                            logging.debug('[hmi]     sent "%s %d"', CMD_RESPONSE, resp)

                        else:
                            self.send_reply("%s %d %s" % (CMD_RESPONSE, resp, resp_args))
                            logging.debug('[hmi]     sent "%s %d %s"', CMD_RESPONSE, resp, resp_args)

                        self.handling_response = False
                        if self.queue_idle:
                            self.process_queue()

                    if LOG >= 1:
                        logging.debug('[hmi] received <- %s | %s', data,
                                      cmd_to_str((data.split(b' ',1)[0] if b' ' in data else data[:-1]).decode("utf-8", errors="ignore")))

                    self.handling_response = True
                    msg.run_cmd(_callback)

        if self.need_flush != 0:
            if self.flush_io is not None:
                ioloop.remove_timeout(self.flush_io)
            self.flush_io = ioloop.call_later(self.timeout/2, self.flush)

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
            if LOG >= 2:
                logging.debug("[hmi] queue is empty, nothing to do")
            self.queue_idle = True
            self.last_write_time = 0
        else:
            if LOG >= 2 or (LOG and msg not in ("pi",)):
                logging.debug("[hmi] sending -> %s | %s", msg, cmd_to_str(msg.split(" ",1)[0]))
            try:
                self.sp.write(msg.encode('utf-8') + b'\0')
            except StreamClosedError as e:
                logging.exception(e)
                self.sp = None

            self.queue_idle = False
            self.last_write_time = time.time()

    def reply_protocol_error(self, error):
        #self.send(error) # TODO: proper error handling, needs to be implemented by HMI
        self.send("{} -1".format(CMD_RESPONSE), None)

    def send(self, msg, callback, datatype='int'):
        if self.sp is None:
            return

        if self.timeout > 0:
            if len(self.queue) > 30:
                self.need_flush = len(self.queue)

            elif self.last_write_time != 0 and time.time() - self.last_write_time > self.timeout:
                logging.warn("[hmi] no response for %ds, giving up", self.timeout)
                if self.flush_io is not None:
                    IOLoop.instance().remove_timeout(self.flush_io)
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
            if LOG >= 2 or (LOG and msg not in ("pi",)):
                logging.debug("[hmi] scheduling -> %s | %s", msg, cmd_to_str(msg.split(" ",1)[0]))
            if self.queue_idle and not self.handling_response:
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

        data = '%s %d %d %d %d %d' % (CMD_INITIAL_STATE, numPedals, startIndex, endIndex, bank_id, pedalboard_id)

        for i in range(startIndex, endIndex):
            data += ' %s %d' % (normalize_for_hw(pedalboards[i]['title']), i+1)

        self.send(data, callback)

    def ui_con(self, callback):
        self.send(CMD_GUI_CONNECTED, callback, 'boolean')

    def ui_dis(self, callback):
        self.send(CMD_GUI_DISCONNECTED, callback, 'boolean')

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

        if data.get('group', None) is not None and self.hw_desc.get('hmi_actuator_group_prefix', True):
            if var_type & FLAG_CONTROL_REVERSE:
                prefix = "- "
            else:
                prefix = "+ "
            label = prefix + label

        label = normalize_for_hw(label)
        unit = normalize_for_hw(unit, 7)

        if value < xmin:
            logging.error('[hmi] control_add received value < min for %s', label)
            value = xmin
        elif value > xmax:
            logging.error('[hmi] control_add received value > max for %s', label)
            value = xmax

        if options:
            numOpts = len(options)
            optionsData = []

            ivalue, value = get_nearest_valid_scalepoint_value(value, options)

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

            flags = 0x0
            if startIndex != 0 or endIndex != numOpts:
                flags |= FLAG_PAGINATION_PAGE_UP
            if data.get('group', None) is None:
                flags |= FLAG_PAGINATION_WRAP_AROUND
            if endIndex == numOpts:
                flags |= FLAG_PAGINATION_INITIAL_REQ
            if data.get('coloured', False):
                flags |= FLAG_PAGINATION_ALT_LED_COLOR

            data['steps'] = steps = numOpts - 1

            for i in range(startIndex, endIndex):
                option = options[i]
                xdata  = '%s %f' % (normalize_for_hw(option[1]), float(option[0]))
                optionsData.append(xdata)

            options = "%d %d %d %s" % (len(optionsData), flags, ivalue, " ".join(optionsData))
            options = options.strip()

        else:
            flags = 0x0
            options = "0"

        def control_add_callback(ok):
            if not ok:
                callback(False)
                return
            n_controllers = data['addrs_max']
            index = data['addrs_idx']
            self.control_set_index(hw_id, index, n_controllers, callback)

        # FIXME this should be based on hw desc "max_assigns" instead of hardcoded
        if not actuator_uri.startswith("/hmi/footswitch") and hmi_set_index:
            cb = control_add_callback
        else:
            cb = callback

        self.send('%s %d %s %d %s %f %f %f %d %s' %
                  ( CMD_CONTROL_ADD,
                    hw_id,
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
        self.send('%s %d %d %d' % (CMD_DUO_CONTROL_INDEX_SET, hw_id, index, n_controllers), callback, 'boolean')

    def control_set(self, hw_id, value, callback):
        """Set a plug-in's control port value on the HMI."""
        # control_set <hw_id> <value>"""
        self.send('%s %d %f' % (CMD_CONTROL_SET, hw_id, value), callback, 'boolean')

    def control_rm(self, hw_ids, callback):
        """
        removes an addressing
        """

        ids = " ".join(str(i) for i in hw_ids).strip()
        self.send('%s %s' % (CMD_CONTROL_REMOVE, ids), callback, 'boolean')

    def ping(self, callback):
        self.send(CMD_PING, callback, 'boolean')

    def tuner(self, freq, note, cents, callback):
        self.send('%s %f %s %f' % (CMD_TUNER, freq, note, cents), callback)

    #TODO, This message should be handled by mod-system-control once in place
    def expression_overcurrent(self, callback):
        self.send(CMD_DUOX_EXP_OVERCURRENT, callback, 'boolean')

    def bank_config(self, hw_id, action, callback):
        """
        configures bank addressings

        action is one of the following:
            0: None (usado para des-endereçar)
            1: True Bypass
            2: Pedalboard UP
            3: Pedalboard DOWN
        """
        self.send('%s %d %d' % (CMD_DUO_BANK_CONFIG, hw_id, action), callback, 'boolean')

    def set_bpm(self, bpm):
        if round(bpm) != self.bpm:
            self.bpm = round(bpm)
            return True
        return False

    # new messages

    def clear(self, callback):
        self.send(CMD_PEDALBOARD_CLEAR, callback)

    def set_profile_value(self, key, value, callback):
        # Do not send new bpm value to HMI if its int value is the same
        if key == MENU_ID_TEMPO and not self.set_bpm(value):
            if callback is not None:
                callback(True)
        else:
            if key == MENU_ID_TEMPO:
                value = self.bpm # set rounded value for bpm
            self.send("%s %i %i" % (CMD_MENU_ITEM_CHANGE, key, int(value)), callback, 'boolean')

    def set_profile_values(self, playback_rolling, values, callback):
        msg  = CMD_MENU_ITEM_CHANGE
        msg += " %i %i" % (MENU_ID_SL_IN, int(values['inputStereoLink']))
        msg += " %i %i" % (MENU_ID_SL_OUT, int(values['outputStereoLink']))
        msg += " %i %i" % (MENU_ID_PLAY_STATUS, int(playback_rolling))
        msg += " %i %i" % (MENU_ID_MIDI_CLK_SOURCE, values['transportSource'])
        msg += " %i %i" % (MENU_ID_MIDI_CLK_SEND, int(values['midiClockSend']))
        msg += " %i %i" % (MENU_ID_SNAPSHOT_PRGCHGE, values['midiChannelForSnapshotsNavigation'])
        msg += " %i %i" % (MENU_ID_PB_PRGCHNGE, values['midiChannelForPedalboardsNavigation'])
        msg += " %i %i" % (MENU_ID_MASTER_VOL_PORT, int(values['masterVolumeChannelMode']))
        self.send(msg, callback)

    # pages is a list of int (1 if page available else 0)
    # NOTE CMD_DUOX_PAGES_AVAILABLE and CMD_DWARF_PAGES_AVAILABLE have the same message prefix
    def set_available_pages(self, pages, callback):
        msg = CMD_DUOX_PAGES_AVAILABLE
        for page_enabled in pages:
            msg += " %i" % int(page_enabled)
        self.send(msg, callback, 'boolean')

    # even newer messages. really need to clean this up later..

    def restore(self, callback=None, datatype='int'):
        self.send(CMD_RESTORE, callback, datatype)

    def reset_eeprom(self, callback=None, datatype='int'):
        self.send(CMD_RESET_EEPROM, callback, datatype)

    # FIXME this message should be generic, most likely
    def boot(self, bootdata, callback, datatype='int'):
        self.send("boot {}".format(bootdata), callback, datatype)

    def set_pedalboard_index(self, index, callback):
        self.send('{} {}'.format(CMD_PEDALBOARD_CHANGE, index), callback)

    def set_pedalboard_name(self, name, callback):
        self.send('{} {}'.format(CMD_PEDALBOARD_NAME_SET, normalize_for_hw(name)), callback)

    def set_snapshot_name(self, index, name, callback):
        self.send('{} {} {}'.format(CMD_SNAPSHOT_NAME_SET, index, normalize_for_hw(name)), callback)
