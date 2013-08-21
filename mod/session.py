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


import socket, os, serial, multiprocessing, time, logging, os.path

from datetime import timedelta
from tornado import iostream, ioloop
from Queue import Empty

from mod.settings import (MANAGER_PORT, DEV_ENVIRONMENT, PEDALBOARD_DIR, CONTROLLER_INSTALLED,
                        CONTROLLER_SERIAL_PORT, CONTROLLER_BAUD_RATE, CLIPMETER_URI, PEAKMETER_URI, 
                        CLIPMETER_IN, CLIPMETER_OUT, CLIPMETER_L, CLIPMETER_R, PEAKMETER_IN, PEAKMETER_OUT, 
                        CLIPMETER_MON_R, CLIPMETER_MON_L, PEAKMETER_MON_L, PEAKMETER_MON_R, 
                        PEAKMETER_L, PEAKMETER_R, TUNER, TUNER_URI, TUNER_MON_PORT, TUNER_PORT, HARDWARE_DIR)
from mod.pedalboard import load_pedalboard, list_pedalboards, list_banks
from mod.controller import WriterProcess, ReaderProcess

NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

_freqs4 = [261.63, 277.18, 293.66, 311.13, 329.63, 349.23, 369.99, 392.0, 415.3, 440.0, 466.16, 493.88]
FREQS = reduce(lambda l1, l2: l1+l2, ([ freq/2**i for freq in _freqs4 ] for i in range(4, -4, -1)))

def find_freqnotecents(f):
    freq = min(FREQS, key=lambda i: abs(i-f))
    idx = FREQS.index(freq)
    octave = idx / 12
    note = NOTES[FREQS.index(freq/2**octave)]
    d = 1 if f >= freq else -1
    next_f = FREQS[idx+d]
    cents =  int(100 * (f - freq) / (next_f - freq)) * d
    return freq, "%s%d" % (note, octave), cents

def _serial_check():
    """
    blocking function to check the reader queue

    the queue is set as a function attribute by the function
    below when we initialize the workers Pool
    """
    return _serial_check.queue.get() # blocks until there's something

def _serial_check_init(queue):
    _serial_check.queue = queue

class Session(object):

    def __init__(self):
        self.s = None
        self.socket_idle = False
        self.latest_callback = None
        self.socket_queue = []
        self.open_connection(True)
        self._playback_1_connected_ports = []
        self._playback_2_connected_ports = []
        self._tuner = False
        self._peakmeter = True

        self.monitor_server = None

        self._pedalboard = None
        self._pedalboards = {}
        self.serial_init()

    def serial_init(self):
        # serial blocking communication runs in other processes
        self.serial_queue = []
        sp = serial.Serial(CONTROLLER_SERIAL_PORT, CONTROLLER_BAUD_RATE)
        sp.setRTS(False)
        sp.setDTR(False)
        time.sleep(0.2) # black magic 
        sp.flushInput()
        sp.flushOutput()

        lock = multiprocessing.Lock()

        self.writer_queue = multiprocessing.Queue()
        self.reader_queue = multiprocessing.Queue()

        self.writer = WriterProcess(sp, self.writer_queue, lock, self.reader_queue)
        self.reader = ReaderProcess(sp, self.reader_queue, lock)

        self.writer.daemon = True
        self.reader.daemon = True

        self.writer.start()
        self.reader.start()

        self.workers = multiprocessing.Pool(2, _serial_check_init, [self.reader_queue])

        ioloop.IOLoop.instance().add_callback(self._serial_checker)

    def open_connection(self, first=False):
        self.socket_idle = False

        if (self.latest_callback):
            # There's a connection waiting, let's just send an error
            # for it to finish properly
            self.latest_callback('-1\0')

        self.latest_callback = None

        def check_response():
            if len(self.socket_queue):
                self._socket_process_next()
            else:
                self.socket_idle = True
            self.setup_monitor()

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s = iostream.IOStream(s)
        self.s.set_close_callback(self.open_connection)

        def connect():
            self.s.connect(('127.0.0.1', MANAGER_PORT), check_response)

        if first:
            connect()
        else:
           # avoid consuming too much cpu
            ioloop.IOLoop.instance().add_callback(connect)
    
    def setup_monitor(self):
        if self.monitor_server is None:
            from mod.monitor import MonitorServer
            self.monitor_server = MonitorServer()
            self.monitor_server.listen(12345)

            self.set_monitor("localhost", 12345, self.add_tools)

    def add_tools(self, resp):
        if resp:
            self.add(CLIPMETER_URI, CLIPMETER_IN, self.setup_clipmeter_in)
            self.add(CLIPMETER_URI, CLIPMETER_OUT, self.setup_clipmeter_out)

    def setup_clipmeter_in(self, resp):
        if resp:
            self.connect("system:capture_1", "effect_%d:%s" % (CLIPMETER_IN, CLIPMETER_L), lambda r:None)
            self.connect("system:capture_2", "effect_%d:%s" % (CLIPMETER_IN, CLIPMETER_R), lambda r:None)
            self.parameter_monitor(CLIPMETER_IN, CLIPMETER_MON_L, ">=", 0, lambda r:None)
            self.parameter_monitor(CLIPMETER_IN, CLIPMETER_MON_R, ">=", 0, lambda r:None)

    def setup_clipmeter_out(self, resp):
        if resp:
            self.parameter_monitor(CLIPMETER_OUT, CLIPMETER_MON_L, ">=", 0, lambda r:None)
            self.parameter_monitor(CLIPMETER_OUT, CLIPMETER_MON_R, ">=", 0, lambda r:None)

    def tuner_on(self, cb):
        def mon_tuner(ok):
            if ok:
                self.parameter_monitor(TUNER, TUNER_MON_PORT, ">=", 0, cb)
        
        def setup_tuner(ok):
            if ok:
                self._tuner = True
                self.connect("system:capture_1", "effect_%d:%s" % (TUNER, TUNER_PORT), mon_tuner)
        
        self.add(TUNER_URI, TUNER, setup_tuner)

    def tuner_off(self, cb):
        self.remove(TUNER, cb)
        self._tuner = False

    def peakmeter_on(self, cb):
        
        def mon_peak_in_l(ok):
            if ok:
                self.parameter_monitor(PEAKMETER_IN, PEAKMETER_MON_L, ">=", -30, cb)
        
        def mon_peak_in_r(ok):
            if ok:
                self.parameter_monitor(PEAKMETER_IN, PEAKMETER_MON_R, ">=", -30, lambda r:None)

        def mon_peak_out_l(ok):
            if ok:
                self.parameter_monitor(PEAKMETER_OUT, PEAKMETER_MON_L, ">=", -30, lambda r:None)

        def mon_peak_out_r(ok):
            if ok:
                self.parameter_monitor(PEAKMETER_OUT, PEAKMETER_MON_R, ">=", -30, lambda r:None)

        def setup_peak_in(ok):
            if ok:
                self.connect("system:capture_1", "effect_%d:%s" % (PEAKMETER_IN, PEAKMETER_L), mon_peak_in_l)
                self.connect("system:capture_2", "effect_%d:%s" % (PEAKMETER_IN, PEAKMETER_R), mon_peak_in_r)

        def setup_peak_out(ok):
            if ok:
                self._peakmeter = True
                for port in self._playback_1_connected_ports:
                    self.connect(port, "effect_%d:%s" % (PEAKMETER_OUT, PEAKMETER_L), mon_peak_out_l)
                for port in self._playback_2_connected_ports:
                    self.connect(port, "effect_%d:%s" % (PEAKMETER_OUT, PEAKMETER_L), mon_peak_out_r)

        self.add(PEAKMETER_URI, PEAKMETER_IN, setup_peak_in)
        self.add(PEAKMETER_URI, PEAKMETER_OUT, setup_peak_out) 

    def peakmeter_off(self, cb):
        self.remove(PEAKMETER_IN, cb)
        self.remove(PEAKMETER_OUT, lambda r: None)
        self._tuner = False

    def socket_send(self, msg, callback, datatype='int'):
        logging.info("[socket] scheduling %s" % msg)
        self.socket_queue.append((msg, callback, datatype))
        if self.socket_idle:
            self._socket_process_next()

    def serial_send(self, msg, callback, datatype='int'):
        logging.info("[serial] scheduling %s" % msg)

        # no worries as our queue is never full
        self.writer_queue.put_nowait(msg) # non-blocking put()
        self.serial_queue.append((msg, callback, datatype))

    def serial_send_resp(self, resp):
        logging.info("[serial] -> resp %s" % resp)
        # no worries as our queue is never full
        self.writer_queue.put_nowait("resp %s" % resp) # non-blocking put()

    def _serial_checker(self):
        def _callback(result):
            ioloop.IOLoop.instance().add_callback(lambda: self._serial_process_msg(result))

        self.workers.apply_async(_serial_check, callback=_callback)

    def _serial_send_file(self, filename, typ, callback):
        f = open(filename, 'rb')
        content = f.read()
        fsize = len(content)

        def _callback(result):
            assert result, "dados -x failed"
            self.serial_send("dados -y %s" % content, callback, 'boolean')

        self.serial_send("dados -x %d %d" % (fsize, typ), _callback, 'boolean')

    def _check_resp(self, resp, datatype):
        if datatype == 'float_structure':
            # resp is first an int representing status
            # then the float
            resps = resp.split()
            resp = { 'ok': int(resps[0]) >= 0 }
            try:
                resp['value'] = float(resps[1])
            except IndexError:
                resp['ok'] = False
        else:
            try:
                resp = int(resp)
            except:
                resp = -1003

            if datatype == 'boolean':
                resp = resp >= 0
        return resp

    def _serial_process_response(self, msg):
        try:
            req, callback, datatype = self.serial_queue.pop(0)
        except IndexError:
            logging.warning("[serial] unexpected response received from reader process")
            ioloop.IOLoop.instance().add_callback(self._serial_checker)
        else:
            if msg.startswith("not found"):
                resp = "-1"
                datatype = 'boolean'
            else:
                resp = msg[5:] # removes the resp prefix

            resp = self._check_resp(resp, datatype)
            callback(resp)

    def _serial_process_command(self, msg):
        cmd = msg.split()
        def _callback(resp, resp_args=None):
            if resp_args is None:
                self.serial_send_resp(0 if resp else -1)
            else:
                self.serial_send_resp("%d %s" % (0 if resp else -1, resp_args))

        def _error(e):
            logging.error("[serial] error for '%s': %s" % (msg, e))
            _callback(False)

        def _check_values(types):
            for i,value in enumerate(cmd[2:]):
                try:
                    types[i](value)
                except ValueError:
                    _error("parameter '%s' is not a %s" % (value, repr(types[i])))
                    return False
            return True

        # TODO: more documentation 
        if msg.startswith("control_set") and len(cmd) == 4:
            if _check_values([int, str, float]):
                self.parameter_set(int(cmd[1]), cmd[2], float(cmd[3]), _callback, controller=True)
        elif msg.startswith("pedalboard ") and len(cmd) == 2: 
            if _check_values([str]):
                self.load_pedalboard(cmd[1], _callback, load_from_dict=True)
        elif msg.startswith("ping") and len(cmd) == 1:
            _callback(True)
        elif msg.startswith("tuner ") and len(cmd) == 2:
            if cmd[1] == "on":
                self.tuner_on(_callback)
            elif cmd[1] == "off":
                self.tuner_off(_callback)
            else:
                _error("invalid argument")
        elif msg.startswith("peakmeter ") and len(cmd) == 2:
            if cmd[1] == "on":
                self.peakmeter_on(_callback)
            elif cmd[1] == "off":
                self.peakmeter_off(_callback)
            else:
                _error("invalid argument")
        elif msg.startswith("hw_con") and len(cmd) == 3:
            if _check_values([int, int]):
                self.hardware_connected(cmd[1], cmd[2], _callback)
        elif msg.startswith("hw_dis") and len(cmd) == 3:
            if _check_values([int, int]):
                self.hardware_disconnected(cmd[1], cmd[2], _callback)
        elif msg.startswith("banks") and len(cmd) == 1:
            self.list_banks(_callback)
        elif msg.startswith("pedalboards") and len(cmd) == 2:
            if _check_values([int]):
                self.list_pedalboards(int(cmd[1]), _callback)
        else:
            _error("command not found")

    def _serial_process_msg(self, msg):
        if msg.startswith('resp') or msg.startswith('not found'):
            self._serial_process_response(msg)
        else:
            self._serial_process_command(msg)
        
        # always schedule to check again
        ioloop.IOLoop.instance().add_callback(self._serial_checker)

    def _socket_process_next(self):
        try:
            msg, callback, datatype = self.socket_queue.pop(0)
        except IndexError:
            self.socket_idle = True
            return

        def check_response(resp):
            logging.info("[socket] <- %s" % (resp))
            try:
                resp = resp.split('resp ')[1] # responses now have the prefix resp
                resp = resp.split('\0')[0]
            except:
                resp = -1002

            resp = self._check_resp(resp, datatype)
            callback(resp)
            self._socket_process_next()

        self.socket_idle = False

        self.s.write('%s\0' % str(msg))
        self.s.read_until('\0', check_response)

        self.latest_callback = check_response


    def load_pedalboard(self, pedalboard_id, callback, load_from_dict=False):
        # loads the pedalboard json
        self._pedalboard = pedalboard_id

        if self._pedalboards.get(pedalboard_id, None) is None or not load_from_dict:
            pedalboard = load_pedalboard(pedalboard_id)
            self._pedalboards[pedalboard_id] = pedalboard
        else:
            pedalboard = self._pedalboards[pedalboard_id]

        # let's copy the data
        effects = pedalboard['instances'][:]
        connections = pedalboard['connections'][:]

        # How it works:
        # remove -1  (remove all effects)
        # for each effect
        #   add effect
        #   sets bypass value
        #   sets bypass addressing if any
        #   sets value of all ports
        #   sets addressings of all ports
        # add all connections

        # TODO: tratar o result para cada callback

        # Consumes a queue of effects, in each one goes through bypass, bypass addressing,
        # control port values and control port addressings, before processing next effect
        # in queue. Then proceed to connections
        def add_effects(result):
            if not effects:
                ioloop.IOLoop.instance().add_callback(add_connections)
                return
            effect = effects.pop(0)
            self.add(effect['url'], effect['instanceId'],
                    lambda result: set_bypass(effect))
        
        # Set bypass state of one effect, then goes to bypass addressing
        def set_bypass(effect):
            self.bypass(effect['instanceId'], effect['bypassed'], lambda result: set_ports(effect))

        # Set the value of one port of an effect, consumes it and schedules next one
        # After queue is empty, goes to control addressings
        def set_ports(effect):
            if not effect.get('preset', {}):
                ioloop.IOLoop.instance().add_callback(lambda: set_bypass_addr(effect)) #add_effects(0))
                return
            symbol = effect['preset'].keys()[0]
            value = effect['preset'].pop(symbol)
            self.parameter_set(effect['instanceId'], symbol, value, lambda result: set_ports(effect)) #_addr(effect, param))

        # Sets bypass addressing of one effect. 
        def set_bypass_addr(effect):
            if not effect.get('addressing', {}):
                ioloop.IOLoop.instance().add_callback(lambda: add_effects(0))
                return

            symbol = ":bypass"
            addressing = effect['addressing'].pop(symbol, {})

            if addressing.get('actuator', [-1])[0] == -1:
                ioloop.IOLoop.instance().add_callback(lambda: set_ports_addr(effect))
                return

            hwtyp, hwid, acttyp, actid = addressing['actuator']
            self.bypass_address(effect['instanceId'], hwtyp, hwid, acttyp, actid,
                                effect['bypassed'], addressing['label'],
                                lambda result: set_ports_addr(effect))

        # Consumes a queue of control addressing, then goes to next effect
        def set_ports_addr(effect):
            # addressing['actuator'] can be [-1] or [hwtyp, hwid, acttyp, actid]
            if not effect.get('addressing', {}):
                ioloop.IOLoop.instance().add_callback(lambda: add_effects(0))
                return

            symbol = effect['addressing'].keys()[0]
            addressing = effect['addressing'].pop(symbol)

            if addressing.get('actuator', [-1])[0] == -1:
                ioloop.IOLoop.instance().add_callback(lambda: set_ports_addr(effect))
                return

            hwtyp, hwid, acttyp, actid = map(int, addressing['actuator'])
            self.parameter_address(effect['instanceId'],
                                   symbol,
                                   addressing.get('label', '---'),
                                   int(addressing.get('type', 0)),
                                   addressing.get('unit', 'none'),
                                   float(addressing['value']),
                                   float(addressing['maximum']),
                                   float(addressing['minimum']),
                                   hwtyp,
                                   hwid,
                                   acttyp,
                                   actid,
                                   addressing.get('options', []),
                                   lambda result: set_ports_addr(effect))

        def add_connections():
            if not connections:
                ioloop.IOLoop.instance().add_callback(lambda: callback(True))
                return
            connection = connections.pop(0)
            orig = '%s:%s' % (str(connection[0]), connection[1])
            dest = '%s:%s' % (str(connection[2]), connection[3])
            self.connect(orig, dest, lambda result: add_connections())

        self.remove(-1, add_effects)

    def hardware_connected(self, hwtyp, hwid, callback): 
        open(os.path.join(HARDWARE_DIR, "%d_%d" % (hwtyp, hwid)), 'w')
        callback(True)

    def hardware_disconnected(self, hwtype, hwid):
        if os.path.exist():
            os.remove(os.path.join(HARDWARE_DIR, "%d_%d" % (hwtyp, hwid)), callback)
        callback(True)

    # host commands

    def add(self, objid, instance_id, callback):
        return self.socket_send('add %s %d' % (objid, instance_id), callback)

    def remove(self, instance_id, callback):
        def _callback(ok):
            if ok:
                self.serial_send("control_rm %d :all" % instance_id, callback, datatype='boolean')
            else:
                callback(ok)

        self.socket_send('remove %d' % instance_id, _callback,
                  datatype='boolean')

    def bypass(self, instance_id, value, callback, controller=False):
        value = 1 if int(value) > 0 else 0

        if controller:
            def _callback(r):
                if r:
                    if self._pedalboard is not None:
                        for i, instance in enumerate(self._pedalboards[self._pedalboard]["instances"]):
                            if instance["instanceId"] == instance_id:
                                break
                        self._pedalboards[self._pedalboard]["instances"][i]['bypassed'] = bool(value)
                callback(r)
        else:
            _callback = callback

        self.socket_send('bypass %d %d' % (instance_id, value), _callback,
                  datatype='boolean')

    def connect(self, port_from, port_to,
                callback):
        if not 'system' in port_from and not 'effect' in port_from:
            port_from = "effect_%s" % port_from
        if not 'system' in port_to and not 'effect' in port_to:
            port_to = "effect_%s" % port_to
        
        def cb(result):
            if result:
                if port_to == "system:playback_1":
                    self.connect(port_from, "effect_%d:%s" % (CLIPMETER_OUT, CLIPMETER_L), lambda r: r)
                    self._playback_1_connected_ports.append(port_from)
                    if self._peakmeter:
                        self.connect(port_from, "effect_%d:%s" % (PEAKMETER_OUT, PEAKMETER_L), lambda r: r)
                elif port_to == "system:playback_2":
                    self.connect(port_from, "effect_%d:%s" % (CLIPMETER_OUT, CLIPMETER_R), lambda r: r)
                    self._playback_2_connected_ports.append(port_from)
                    if self._peakmeter:
                        self.connect(port_from, "effect_%d:%s" % (PEAKMETER_OUT, PEAKMETER_R), lambda r: r)
            callback(result)

        if "system" in port_to:
            self.socket_send('connect %s %s' % (port_from, port_to),
                cb, datatype='boolean')
        else:
            self.socket_send('connect %s %s' % (port_from, port_to),
                callback, datatype='boolean')

    def disconnect(self, port_from, port_to,
                   callback):
        if not 'system' in port_from and not 'effect' in port_from:
            port_from = "effect_%s" % port_from
        if not 'system' in port_to and not 'effect' in port_to:
            port_to = "effect_%s" % port_to
        
        def cb(result):
            if result:
                if port_to == "system:playback_1":
                    self.disconnect(port_from, "effect_%d:%s" % (CLIPMETER_OUT, CLIPMETER_L), lambda r: r)
                    if self._peakmeter:
                        self.disconnect(port_from, "effect_%d:%s" % (PEAKMETER_OUT, PEAKMETER_L), lambda r: r)
                    try:
                        self._playback_1_connected_ports.remove(port_from)
                    except ValueError:
                        pass
                elif port_to == "system:playback_2":
                    self.disconnect(port_from, "effect_%d:%s" % (CLIPMETER_OUT, CLIPMETER_R), lambda r: r)
                    if self._peakmeter:
                        self.disconnect(port_from, "effect_%d:%s" % (PEAKMETER_OUT, PEAKMETER_R), lambda r: r)
                    try:
                        self._playback_2_connected_ports.remove(port_from)
                    except ValueError:
                        pass
            callback(result)

        if "system" in port_to:
            self.socket_send('disconnect %s %s' % (port_from, port_to),
                cb, datatype='boolean')
        else:
            self.socket_send('disconnect %s %s' % (port_from, port_to),
                callback, datatype='boolean')


    def parameter_set(self, instance_id, port_id, value, callback, controller=False):
        if port_id == ":bypass":
            self.bypass(instance_id, value, callback, controller)
            return

        if controller:
            def _callback(r):
                if r:
                    if self._pedalboard is not None:
                        for i, instance in enumerate(self._pedalboards[self._pedalboard]["instances"]):
                            if instance["instanceId"] == instance_id:
                                break
                        self._pedalboards[self._pedalboard]["instances"][i]["preset"]["port_id"] = value
                callback(r)
        else:
            _callback = callback
        self.socket_send('param_set %d %s %f' % (instance_id,
                                           port_id,
                                           value),
                  _callback, datatype='boolean')

    def parameter_get(self, instance_id, port_id, callback):
        self.socket_send('param_get %d %s' % (instance_id, port_id),
                  callback, datatype='float_structure')

    def set_monitor(self, addr, port, callback):
        self.socket_send('monitor %s %d 1' % (addr, port), callback, datatype='boolean')

    def parameter_monitor(self, instance_id, port_id, op, value, callback):
        self.socket_send("param_monitor %d %s %s %f" % (instance_id, port_id, op, value), 
                  callback, datatype='boolean')
    # END host commands

    # controller commands
    def start_session(self, callback=None):
        self.socket_queue = []
        self.serial_queue = []
        self._playback_1_connected_ports = []
        self._playback_2_connected_ports = []

        def verify(resp):
            if callback:
                callback(resp)
            else:
                assert resp
        self.remove(-1, lambda r: None)
        self.serial_send('ui_con', verify,
                  datatype='boolean')

    def end_session(self, callback):
        self.socket_queue = []
        self.serial_queue = []
        self.serial_send('ui_dis', callback,
                  datatype='boolean')

    def bypass_address(self, instance_id, hardware_type, hardware_id, actuator_type, actuator_id, value, label, callback):
        self.parameter_address(instance_id, ":bypass", label, 6, "none", value, 
                               1, 0, hardware_type, hardware_id, actuator_type, 
                               actuator_id, [], callback)

    def parameter_address(self, instance_id, port_id, label, ctype,
                          unit, current_value, maximum, minimum,
                          hardware_type, hardware_id, actuator_type, actuator_id,
                          options, callback):
        # TODO the IHM parameters set by hardware.js should be here!
        """
        instance_id: effect instance
        port_id: control port
        label: lcd display label
        ctype: 0 linear, 1 logarithm, 2 enumeration, 3 toggled, 4 trigger, 5 tap tempo, 6 bypass
        unit: string representing the parameter unit (hz, bpm, seconds, etc)
        hardware_type: the hardware model
        hardware_id: the id of the hardware where we find this actuator
        actuator_type: the encoder button type
        actuator_id: the encoder button number
        options: array of options, each one being a tuple (value, label)
        """
        label = label.replace(' ', '_')
        unit = unit.replace(' ', '_')
        length = len(options)
        if options:
            options = [ "%s %f" % (o[1].replace(' ', '_'), float(o[0]))
                        for o in options ]
        options = "%d %s" % (length, " ".join(options))
        options = options.strip()

        self.serial_send('control_add %d %s %s %d %s %f %f %f %d %d %d %d %d %s' %
                  ( instance_id,
                    port_id,
                    label,
                    ctype,
                    unit,
                    current_value,
                    maximum,
                    minimum,
                    33, # step
                    hardware_type,
                    hardware_id,
                    actuator_type,
                    actuator_id,
                    options,
                    ),
                  callback, datatype='boolean')

    def ping(self, callback):
        self.serial_send('ping', callback, datatype='boolean')

    def list_banks(self, callback):
        banks = " ".join('"%s" %d' % (bank, i) for i,bank in enumerate(list_banks()))
        callback(True, banks)
    
    def list_pedalboards(self, bank_id, callback):
        pedalboards = list_pedalboards(bank_id)
        if pedalboards != False:
            pedalboards = " ".join('"%s" %s' % (pedalboard, pedalboard_id) for pedalboard,pedalboard_id in pedalboards)
            callback(True, pedalboards)
            return
        callback(pedalboards)

    def clipmeter(self, pos, value, callback=None):
        cb = callback
        if not cb:
            cb = lambda r: r
        self.serial_send("clipmeter %d %f" % (pos, value), cb)

    def peakmeter(self, pos, value, callback=None):
        cb = callback
        if not cb:
            cb = lambda r: r
        self.serial_send("peakmeter %d %f" % (pos, value), cb)

    def tuner(self, value, callback=None):
        cb = callback
        if not cb:
            cb = lambda r: r
        
        freq, note, cents = find_freqnotecents(value)
        self.serial_send("tuner %f %s %d" % (freq, note, cents), cb)

    def xrun(self, callback=None):
        cb = callback
        if not cb:
            cb = lambda r: r
        self.serial_send('xrun -x', cb)


# for development purposes
class FakeControllerSession(Session):

    def serial_init(self):
        pass

    def serial_send(self, msg, callback, datatype=None):
        logging.info(msg)
        if datatype == 'boolean':
            callback(True)
        else:
            callback(0)

# for development purposes
class FakeSession(FakeControllerSession):
    def __init__(self):
        self._peakmeter = False
        self._tuner = False
        self._pedalboard = None
        self._pedalboards = {}
        pass

    def add(self, objid, instance_id, callback):
        logging.info("adding instance %d" % instance_id)
        super(FakeSession, self).add(objid, instance_id, lambda x: None)
        callback(instance_id)

    def open(self, callback=None):
        pass

    def parameter_get(self, instance_id, port_id, callback):
        logging.info("getting parameter %d %s" % (instance_id, port_id))
        callback({ 'ok': True, 'value': 17.0 })

    def socket_send(self, msg, callback, datatype=None):
        logging.info(msg)
        if datatype == 'boolean':
            callback(True)
        else:
            callback(0)


if DEV_ENVIRONMENT:
    _cls = FakeSession
elif CONTROLLER_INSTALLED == False:
    _cls = FakeControllerSession
else:
    _cls = Session 

SESSION = _cls()

