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


import os, time

from datetime import timedelta
from tornado import iostream, ioloop
from Queue import Empty

from mod.settings import (MANAGER_PORT, DEV_ENVIRONMENT, CONTROLLER_INSTALLED,
                        CONTROLLER_SERIAL_PORT, CONTROLLER_BAUD_RATE, CLIPMETER_URI, PEAKMETER_URI, 
                        CLIPMETER_IN, CLIPMETER_OUT, CLIPMETER_L, CLIPMETER_R, PEAKMETER_IN, PEAKMETER_OUT, 
                        CLIPMETER_MON_R, CLIPMETER_MON_L, PEAKMETER_MON_L, PEAKMETER_MON_R, 
                        PEAKMETER_L, PEAKMETER_R, TUNER, TUNER_URI, TUNER_MON_PORT, TUNER_PORT, HARDWARE_DIR)
from mod.pedalboard import (load_pedalboard, list_pedalboards, list_banks, save_last_pedalboard, 
                           save_pedalboard, get_last_pedalboard)
from mod.controller import HMI
from mod.host import Host
from mod.protocol import Protocol
from tuner import NOTES, FREQS, find_freqnotecents

class Session(object):

    def __init__(self):
        self.host = Host(MANAGER_PORT, "localhost", self.setup_monitor)
        self.hmi = HMI(CONTROLLER_SERIAL_PORT, CONTROLLER_BAUD_RATE)
        self._playback_1_connected_ports = []
        self._playback_2_connected_ports = []
        self._tuner = False
        self._peakmeter = False

        self.monitor_server = None

        self.current_bank = None

        self._pedalboard = None
        self._pedalboards = {}
        Protocol.register_cmd_callback("banks", self.list_banks)
        Protocol.register_cmd_callback("pedalboards", self.list_pedalboards)
        Protocol.register_cmd_callback("pedalboard", self.load_pedalboard)
        Protocol.register_cmd_callback("hw_con", self.hardware_connected)
        Protocol.register_cmd_callback("hw_dis", self.hardware_disconnected)
        Protocol.register_cmd_callback("control_set", self.parameter_set)
        Protocol.register_cmd_callback("control_get", self.parameter_get)
        Protocol.register_cmd_callback("peakmeter", self.peakmeter_set) 
        Protocol.register_cmd_callback("tuner", self.tuner_set)
        Protocol.register_cmd_callback("tuner_input", self.tuner_set_input)

        def set_last_pedalboard():
            last_bank, last_pedalboard = get_last_pedalboard()
            if last_bank and last_pedalboard:
                self.load_pedalboard(last_bank, last_pedalboard, lambda r:r)

    def setup_monitor(self):
        if self.monitor_server is None:
            from mod.monitor import MonitorServer
            self.monitor_server = MonitorServer()
            self.monitor_server.listen(12345)

            self.set_monitor("localhost", 12345, 1, self.add_tools)

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


    def tuner_set_input(self, input, callback):
        # TODO: implement
        callback(1)

    def tuner_set(self, status, callback):
        if "on" in status:
            self.tuner_on(callback)
        elif "off" in status:
            self.tuner_off(callback)

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

    def peakmeter_set(self, status, callback):
        if "on" in status:
            self.peakmeter_on(callback)
        elif "off" in status:
            self.peakmeter_off(callback)

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

    def load_pedalboard_controller(self, bank_id, pedalboard_id, callback):
        self.load_pedalboard(bank_id, pedalboard_id, load_from_dict=True)

    def load_pedalboard(self, bank_id, pedalboard_id, callback, load_from_dict=False):
        # loads the pedalboard json
        self._pedalboard = pedalboard_id

        import copy
        if self._pedalboards.get(pedalboard_id, None) is None or not load_from_dict:
            pedalboard = load_pedalboard(pedalboard_id)
            self._pedalboards[pedalboard_id] = copy.deepcopy(pedalboard)
        else:
            pedalboard = self._pedalboards[pedalboard_id]

        # let's copy the data
        effects = copy.deepcopy(pedalboard['instances'])
        connections = copy.deepcopy(pedalboard['connections'])

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
        def add_effects():
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
                ioloop.IOLoop.instance().add_callback(lambda: add_effects())
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
                ioloop.IOLoop.instance().add_callback(lambda: add_effects())
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
                                   addressing.get('unit', 'none') or 'none',
                                   float(addressing['value']),
                                   float(addressing['maximum']),
                                   float(addressing['minimum']),
                                   int(addressing.get('steps', 33)),
                                   hwtyp,
                                   hwid,
                                   acttyp,
                                   actid,
                                   addressing.get('options', []),
                                   lambda result: set_ports_addr(effect))

        def add_connections():
            if not connections:
                save_last_pedalboard(bank_id, pedalboard_id)
                ioloop.IOLoop.instance().add_callback(lambda: callback(True))
                return
            connection = connections.pop(0)
            orig = '%s:%s' % (str(connection[0]), connection[1])
            dest = '%s:%s' % (str(connection[2]), connection[3])
            self.connect(orig, dest, lambda result: add_connections())

        def load(result):
            add_effects()
            if not bank_id == self.current_bank and bank_id is not None:
                self.current_bank = bank_id
                self.load_bank(bank_id)

        self.bank_address(0, 0, 1, 0, 0, lambda r: None)
        self.bank_address(0, 0, 1, 1, 0, lambda r: None)
        self.bank_address(0, 0, 1, 2, 0, lambda r: None)
        self.bank_address(0, 0, 1, 3, 0, lambda r: None)
        self.remove(-1, load)

    def load_bank(self, bank_id):
        bank = list_banks()[bank_id]
        addressing = bank.get('addressing', [0, 0, 0, 0])
        queue = []

        def consume(result=None) :
            if len(queue) == 0:
                return
            param = queue.pop(0)
            self.bank_address(*param)

        for actuator, function in enumerate(addressing):
            queue.append([0, 0, 1, actuator, function, consume])

        consume()

    def hardware_connected(self, hwtyp, hwid, callback): 
        callback(True)
        #open(os.path.join(HARDWARE_DIR, "%d_%d" % (hwtyp, hwid)), 'w')
        #callback(True)

    def hardware_disconnected(self, hwtype, hwid, callback):
        callback(True)
        #if os.path.exist():
        #    os.remove(os.path.join(HARDWARE_DIR, "%d_%d" % (hwtyp, hwid)), callback)
        #callback(True)

    # host commands

    def add(self, objid, instance_id, callback):
        return self.host.add(objid, instance_id, callback)

    def remove(self, instance_id, callback):
        def _callback(ok):
            if ok:
                self.hmi.control_rm(instance_id, ":all", callback)
            else:
                callback(ok)

        self.host.remove(instance_id, _callback)

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

        self.host.bypass(instance_id, value, _callback)

    def connect(self, port_from, port_to, callback):
        if not 'system' in port_from and not 'effect' in port_from:
            port_from = "effect_%s" % port_from
        if not 'system' in port_to and not 'effect' in port_to:
            port_to = "effect_%s" % port_to
        
        if "system" in port_to:
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
        else:
            cb = callback

        self.host.connect(port_from, port_to, cb)

    def disconnect(self, port_from, port_to, callback):
        if not 'system' in port_from and not 'effect' in port_from:
            port_from = "effect_%s" % port_from
        if not 'system' in port_to and not 'effect' in port_to:
            port_to = "effect_%s" % port_to
       
        if "system" in port_to: 
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
        else:
            cb = callback

        self.host.disconnect(port_from, port_to, cb)

    def control_set(self, insance_id, port_id, value, callback):
        self.parameter_set(instance_id, port_id, value, callback, controller=True)

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
                        self._pedalboards[self._pedalboard]["instances"][i]["preset"][port_id] = value
                        self._pedalboards[self._pedalboard]["instances"][i]["addressing"][port_id]["value"] = value
                callback(r)
        else:
            _callback = callback
        self.host.param_set(instance_id, port_id, value, callback)

    def parameter_get(self, instance_id, port_id, callback):
        self.host.param_get(instance_id, port_id, callback)

    def set_monitor(self, addr, port, status, callback):
        self.host.monitor(addr, port, status, callback)

    def parameter_monitor(self, instance_id, port_id, op, value, callback):
        self.host.param_monitor(instance_id, port_id, op, value, callback)
    # END host commands

    # controller commands
    def start_session(self, callback=None):
        self._playback_1_connected_ports = []
        self._playback_2_connected_ports = []
        self._pedalboard = None

        def verify(resp):
            if callback:
                callback(resp)
            else:
                assert resp
        self.bank_address(0, 0, 1, 0, 0, lambda r: None)
        self.bank_address(0, 0, 1, 1, 0, lambda r: None)
        self.bank_address(0, 0, 1, 2, 0, lambda r: None)
        self.bank_address(0, 0, 1, 3, 0, lambda r: None)
        self.remove(-1, lambda r:r)
        self.hmi.ui_con(verify)

    def end_session(self, callback):
        self.hmi.ui_dis(callback)

    def bypass_address(self, instance_id, hardware_type, hardware_id, actuator_type, actuator_id, value, label, callback):
        self.parameter_address(instance_id, ":bypass", label, 6, "none", value, 
                               1, 0, 0, hardware_type, hardware_id, actuator_type, 
                               actuator_id, [], callback)

    def parameter_address(self, instance_id, port_id, label, ctype,
                          unit, current_value, maximum, minimum, steps,
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
        label = '"%s"' % label.upper().replace('"', "")
        unit = '"%s"' % unit.replace('"', '')
        length = len(options)
        if options:
            options = [ '"%s" %f' % (o[1].replace('"', '').upper(), float(o[0]))
                        for o in options ]
        options = "%d %s" % (length, " ".join(options))
        options = options.strip()

        if (hardware_type == -1 and
            hardware_id == -1 and
            actuator_type == -1 and
            actuator_id == -1):
            self.hmi.control_rm(instance_id, port_id, callback)
            return

        self.hmi.control_add(instance_id,
                    port_id,
                    label,
                    ctype,
                    unit,
                    current_value,
                    maximum,
                    minimum,
                    steps,
                    hardware_type,
                    hardware_id,
                    actuator_type,
                    actuator_id,
                    options,
                    callback)

    def bank_address(self, hardware_type, hardware_id, actuator_type, actuator_id, function, callback):
        """
        Function is an integer, meaning:
         - 0: Nothing (unaddress)
         - 1: True bypass
         - 2: Pedalboard up
         - 3: Pedalboard down
        """
        self.hmi.bank_config(hardware_type, hardware_id, actuator_type, actuator_id, function, callback)

    def ping(self, callback):
        self.hmi.ping(callback)

    def list_banks(self, callback):
        banks = " ".join('"%s" %d' % (bank['title'], i) for i,bank in enumerate(list_banks()))
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

        if value > 0:
            self.hmi.clipmeter(pos, cb)

    def peakmeter(self, pos, value, callback=None):
        cb = callback
        if not cb:
            cb = lambda r: r
        self.hmi.peakmeter(pos, value, cb)

    def tuner(self, value, callback=None):
        cb = callback
        if not cb:
            cb = lambda r: r
        
        freq, note, cents = find_freqnotecents(value)
        self.hmi.tuner(freq, note, cents, cb)

    def xrun(self, callback=None):
        cb = callback
        if not cb:
            cb = lambda r: r
        self.hmi.xrun(cb)


# for development purposes
class FakeControllerSession(Session):

    def serial_init(self, callback):
        ioloop.IOLoop.instance().add_callback(callback)

    def serial_send(self, msg, callback, datatype=None):
        logging.info(msg)
        if datatype == 'boolean':
            callback(True)
        else:
            callback(0)

# for development purposes
class FakeSession(FakeControllerSession):
    def __init__(self):
        self._playback_1_connected_ports = []
        self._playback_2_connected_ports = []
        self._peakmeter = False
        self._tuner = False
        self.current_bank = None
        self._pedalboard = None
        self._pedalboards = {}

        def set_last_pedalboard():
            last_bank, last_pedalboard = get_last_pedalboard()
            if last_bank and last_pedalboard:
                self.load_pedalboard(last_bank, last_pedalboard, lambda r:r)
        self.serial_init(set_last_pedalboard)

    def add(self, objid, instance_id, callback):
        super(FakeSession, self).add(objid, instance_id, lambda x: None)
        callback(instance_id)

    def open(self, callback=None):
        pass

    def parameter_get(self, instance_id, port_id, callback):
        callback({ 'ok': True, 'value': 17.0 })


if DEV_ENVIRONMENT:
    _cls = FakeSession
elif CONTROLLER_INSTALLED == False:
    _cls = FakeControllerSession
else:
    _cls = Session 

SESSION = _cls()

