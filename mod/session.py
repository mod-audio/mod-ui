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

import os, time, logging, copy, json

from os import path

from datetime import timedelta
from tornado import iostream, ioloop, gen
from queue import Empty

from mod.settings import (MANAGER_PORT, DEV_ENVIRONMENT, DEV_HMI, DEV_HOST,
                          HMI_SERIAL_PORT, HMI_BAUD_RATE, CLIPMETER_URI, PEAKMETER_URI,
                          CLIPMETER_IN, CLIPMETER_OUT, CLIPMETER_L, CLIPMETER_R, PEAKMETER_IN, PEAKMETER_OUT,
                          CLIPMETER_MON_R, CLIPMETER_MON_L, PEAKMETER_MON_VALUE_L, PEAKMETER_MON_VALUE_R, PEAKMETER_MON_PEAK_L,
                          PEAKMETER_MON_PEAK_R, PEAKMETER_L, PEAKMETER_R, TUNER, TUNER_URI, TUNER_MON_PORT, TUNER_PORT, HARDWARE_DIR,
                          INGEN_NUM_AUDIO_INS, INGEN_NUM_AUDIO_OUTS, INGEN_NUM_MIDI_INS, INGEN_NUM_MIDI_OUTS,
                          DEFAULT_JACK_BUFSIZE)
from mod import symbolify
from mod.development import FakeHost, FakeHMI
from mod.pedalboard import Pedalboard
from mod.hmi import HMI
#from mod.host import Host
from mod.ingen import Host
from mod.lv2 import add_bundle_to_lilv_world
from mod.clipmeter import Clipmeter
from mod.protocol import Protocol
from mod.jack import change_jack_bufsize
from mod.recorder import Recorder, Player
from mod.screenshot import ScreenshotGenerator
from mod.indexing import EffectIndex
from mod.tuner import NOTES, FREQS, find_freqnotecents

def factory(realClass, fakeClass, fake, *args, **kwargs):
    if fake:
        return fakeClass(*args, **kwargs)
    return realClass(*args, **kwargs)


class InstanceIdMapper(object):
    def __init__(self):
        self.instance_map = {}
        self.id_map = {}

    def _get_new_id(self):
        return max(self.id_map.keys()) + 1 if self.id_map else 0

    def map(self, instance):
        if instance not in self.instance_map:
            id = self._get_new_id()
            self.instance_map[instance] = id
            self.id_map[id] = instance
        return self.instance_map[instance]

    def get_instance(self, id):
        return self.id_map.get(id, None)


class Session(object):
    def __init__(self):
        self.hmi_initialized = False
        self.host_initialized = False
        self.pedalboard_initialized = False

        self._playback_1_connected_ports = []
        self._playback_2_connected_ports = []
        self._tuner = False
        self._tuner_port = 1
        self._peakmeter = False

        self.monitor_server = None

        self.current_bank = None

        self.jack_bufsize = DEFAULT_JACK_BUFSIZE
        self.effect_index = EffectIndex()

        self._pedalboard = Pedalboard()

        #Protocol.register_cmd_callback("banks", self.hmi_list_banks)
        #Protocol.register_cmd_callback("pedalboards", self.hmi_list_pedalboards)
        Protocol.register_cmd_callback("hw_con", self.hardware_connected)
        Protocol.register_cmd_callback("hw_dis", self.hardware_disconnected)
        Protocol.register_cmd_callback("control_set", self.hmi_parameter_set)
        Protocol.register_cmd_callback("control_get", self.parameter_get)
        Protocol.register_cmd_callback("control_next", self.parameter_addressing_next)
        Protocol.register_cmd_callback("peakmeter", self.peakmeter_set)
        Protocol.register_cmd_callback("tuner", self.tuner_set)
        Protocol.register_cmd_callback("tuner_input", self.tuner_set_input)
        #Protocol.register_cmd_callback("pedalboard_save", self.save_current_pedalboard)
        #Protocol.register_cmd_callback("pedalboard_reset", self.reset_current_pedalboard)
        Protocol.register_cmd_callback("jack_cpu_load", self.jack_cpu_load)

#        self.host = factory(Host, FakeHost, DEV_HOST,
#                            "unix:///tmp/ingen.sock", self.host_callback)
        self.host = Host(os.environ.get("MOD_INGEN_SOCKET_URI", "unix:///tmp/ingen.sock"), self.host_callback)
        self.hmi = factory(HMI, FakeHMI, DEV_HMI,
                           HMI_SERIAL_PORT, HMI_BAUD_RATE, self.hmi_callback)

        self.recorder = Recorder()
        self.player = Player()
        self.bundlepath = None
        self.mute_state = True
        self.recording = None
        self.instances = []
        self.instance_mapper = InstanceIdMapper()
        self.screenshot_generator = ScreenshotGenerator()

        self.engine_samplerate = 48000 # default value

        self._clipmeter = Clipmeter(self.hmi)
        self.websockets = []

        self._pedal_changed_callback = None

    def reconnect(self):
        self.host.open_connection(self.host_callback)

    def websocket_opened(self, ws):
        self.websockets.append(ws)
        self.host.get("/graph")

    @gen.engine
    def host_callback(self):
        self.host_initialized = True

        def port_value_cb(port, value):
            instance = port.rpartition("/")[0]
            port = port.rpartition("/")[-1]
            instance_id = self.instance_mapper.map(instance)
            if self._pedalboard.data['instances'].get(instance_id, False):
                self._pedalboard.parameter_set(instance_id, port, value)
                addrs = self._pedalboard.data['instances'][instance_id]['addressing']
                addr = addrs.get(port, None)
                if addr:
                    addr['value'] = value
                    act = addr['actuator']
                    #self.parameter_addressing_load(*act)

        def position_cb(instance, x, y):
            pass

        def plugin_add_cb(instance, uri, x, y):
            if not instance in self.instances:
                self._pedalboard.add_instance(uri, self.instance_mapper.map(instance), x=x, y=y)
                self.instances.append(instance)

        def pedal_save_cb(bundlepath):
            if add_bundle_to_lilv_world(bundlepath):
                self.host.add_bundle(bundlepath)
            self.screenshot_generator.schedule_screenshot(bundlepath)

        def delete_cb(instance):
            if instance in self.instances:
                self.instances.remove(instance)

        def connection_add_cb(port_a, port_b):
            pass

        def connection_delete_cb(port_a, port_b):
            pass

        def msg_cb(msg):
            for ws in self.websockets:
                ws.write_message(msg)

        def sr_cb(value):
            self.engine_samplerate = value

        self.host.msg_callback = msg_cb
        self.host.samplerate_value_callback = sr_cb

        yield gen.Task(lambda callback: self.host.get_engine_info(callback=callback))

        # Add ports
        for i in range(1, INGEN_NUM_AUDIO_INS+1):
            yield gen.Task(lambda callback: self.host.add_external_port("Audio In %i" % i, "Input", "Audio", callback=callback))

        for i in range(1, INGEN_NUM_AUDIO_OUTS+1):
            yield gen.Task(lambda callback: self.host.add_external_port("Audio Out %i" % i, "Output", "Audio", callback=callback))

        for i in range(2, INGEN_NUM_MIDI_INS+1):
            yield gen.Task(lambda callback: self.host.add_external_port("MIDI In %i" % i, "Input", "MIDI", callback=callback))

        for i in range(2, INGEN_NUM_MIDI_OUTS+1):
            yield gen.Task(lambda callback: self.host.add_external_port("MIDI Out %i" % i, "Output", "MIDI", callback=callback))

        yield gen.Task(lambda callback: self.host.initial_setup(callback=callback))

        self.host.position_callback = position_cb
        self.host.port_value_callback = port_value_cb
        self.host.plugin_add_callback = plugin_add_cb
        self.host.delete_callback = delete_cb
        self.host.save_callback = pedal_save_cb
        self.host.connection_add_callback = connection_add_cb
        self.host.connection_delete_callback = connection_delete_cb

    def hmi_callback(self):
        if self.host_initialized:
            self.restore_last_pedalboard()
        logging.info("hmi initialized")
        self.hmi_initialized = True

    def reset(self, callback):
        self.bundlepath = None

        gen = iter(copy.deepcopy(self.instances))
        def remove_all_plugins(r=True):
            try:
                self.remove(next(gen), remove_all_plugins)
            except StopIteration:
                callback(r)
        self.hmi.control_rm(-1, ":all", remove_all_plugins)
        #remove_all_plugins()

        if self._pedal_changed_callback is not None:
            self._pedal_changed_callback(True, "", "")

    def save_pedalboard(self, bundlepath, title, callback):
        def callback2(ok):
            self.bundlepath = bundlepath if ok else None
            callback(ok)

            if self._pedal_changed_callback is not None:
                self._pedal_changed_callback(ok, bundlepath, title)

        self.host.set_pedalboard_name(title)
        self.host.save(os.path.join(bundlepath, "%s.ttl" % symbolify(title)), callback2)

    def load_pedalboard(self, bundlepath, name):
        self.bundlepath = bundlepath
        self.host.load(bundlepath)

        if self._pedal_changed_callback is not None:
            self._pedal_changed_callback(True, bundlepath, name)

    def setup_monitor(self):
        if self.monitor_server is None:
            from mod.monitor import MonitorServer
            self.monitor_server = MonitorServer()
            self.monitor_server.listen(12345)

            self.set_monitor("localhost", 12345, 1, self.add_tools)

    def add_tools(self, resp):
        if resp:
            self.add(CLIPMETER_URI, CLIPMETER_IN, self.setup_clipmeter_in, True)
            self.add(CLIPMETER_URI, CLIPMETER_OUT, self.setup_clipmeter_out, True)

    def setup_clipmeter_in(self, resp):
        if resp:
            self.connect("system:capture_1", "effect_%d:%s" % (CLIPMETER_IN, CLIPMETER_L), lambda r:None, True)
            self.connect("system:capture_2", "effect_%d:%s" % (CLIPMETER_IN, CLIPMETER_R), lambda r:None, True)
            self.parameter_monitor(CLIPMETER_IN, CLIPMETER_MON_L, ">=", 0, lambda r:None)
            self.parameter_monitor(CLIPMETER_IN, CLIPMETER_MON_R, ">=", 0, lambda r:None)

    def setup_clipmeter_out(self, resp):
        if resp:
            self.parameter_monitor(CLIPMETER_OUT, CLIPMETER_MON_L, ">=", 0, lambda r:None)
            self.parameter_monitor(CLIPMETER_OUT, CLIPMETER_MON_R, ">=", 0, lambda r:None)


    def tuner_set_input(self, input, callback):
        # TODO: implement
        self.disconnect("system:capture_%s" % self._tuner_port, "effect_%d:%s" % (TUNER, TUNER_PORT), lambda r:r, True)
        self._tuner_port = input
        self.connect("system:capture_%s" % input, "effect_%d:%s" % (TUNER, TUNER_PORT), callback, True)

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
                self.connect("system:capture_%s" % self._tuner_port, "effect_%d:%s" % (TUNER, TUNER_PORT), mon_tuner, True)

        def mute_callback():
            self.add(TUNER_URI, TUNER, setup_tuner, True)
        self.mute(mute_callback)

    def tuner_off(self, cb):
        def callback():
            self.remove(TUNER, cb, True)
            self._tuner = False
        self.unmute(callback)

    def peakmeter_set(self, status, callback):
        if "on" in status:
            self.peakmeter_on(callback)
        elif "off" in status:
            self.peakmeter_off(callback)

    def peakmeter_on(self, cb):

        def mon_peak_in_l(ok):
            if ok:
                self.parameter_monitor(PEAKMETER_IN, PEAKMETER_MON_VALUE_L, ">=", -30, cb)
                self.parameter_monitor(PEAKMETER_IN, PEAKMETER_MON_PEAK_L, ">=", -30, cb)

        def mon_peak_in_r(ok):
            if ok:
                self.parameter_monitor(PEAKMETER_IN, PEAKMETER_MON_VALUE_R, ">=", -30, lambda r:None)
                self.parameter_monitor(PEAKMETER_IN, PEAKMETER_MON_PEAK_R, ">=", -30, lambda r:None)

        def mon_peak_out_l(ok):
            if ok:
                self.parameter_monitor(PEAKMETER_OUT, PEAKMETER_MON_VALUE_L, ">=", -30, lambda r:None)
                self.parameter_monitor(PEAKMETER_OUT, PEAKMETER_MON_PEAK_L, ">=", -30, lambda r:None)

        def mon_peak_out_r(ok):
            if ok:
                self.parameter_monitor(PEAKMETER_OUT, PEAKMETER_MON_VALUE_R, ">=", -30, lambda r:None)
                self.parameter_monitor(PEAKMETER_OUT, PEAKMETER_MON_PEAK_R, ">=", -30, lambda r:None)

        def setup_peak_in(ok):
            if ok:
                self.connect("system:capture_1", "effect_%d:%s" % (PEAKMETER_IN, PEAKMETER_L), mon_peak_in_l, True)
                self.connect("system:capture_2", "effect_%d:%s" % (PEAKMETER_IN, PEAKMETER_R), mon_peak_in_r, True)

        def setup_peak_out(ok):
            if ok:
                self._peakmeter = True
                for port in self._playback_1_connected_ports:
                    self.connect(port, "effect_%d:%s" % (PEAKMETER_OUT, PEAKMETER_L), mon_peak_out_l, True)
                for port in self._playback_2_connected_ports:
                    self.connect(port, "effect_%d:%s" % (PEAKMETER_OUT, PEAKMETER_R), mon_peak_out_r, True)

        self.add(PEAKMETER_URI, PEAKMETER_IN, setup_peak_in, True)
        self.add(PEAKMETER_URI, PEAKMETER_OUT, setup_peak_out, True)

    def peakmeter_off(self, cb):
        self.remove(PEAKMETER_IN, cb, True)
        self.remove(PEAKMETER_OUT, lambda r: None, True)
        self._tuner = False

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

    def add(self, objid, instance, x, y, callback, loaded=False):
        self.host.add(objid, instance, x, y, callback)

    def remove(self, instance, callback, loaded=False):
        """
        affected_actuators = []
        if not loaded:
            affected_actuators = self._pedalboard.remove_instance(instance_id)
        def bufsize_callback(bufsize_changed):
            callback(True)
        def change_bufsize(ok):
            self.change_bufsize(self._pedalboard.get_bufsize(), bufsize_callback)

        def _callback(ok):
            if ok:
                self.hmi.control_rm(instance_id, ":all", change_bufsize)
                for addr in affected_actuators:
                    self.parameter_addressing_load(*addr)
            else:
                change_bufsize(ok)
        """
        if instance == "-1":
            self.reset(callback)
        else:
            self.host.remove(instance, callback)

    def bypass(self, instance, value, callback, loaded=False):
        value = 1 if int(value) > 0 else 0
        #if not loaded:
        #    self._pedalboard.bypass(instance_id, value)
        #self.recorder.bypass(instance, value)
        self.host.bypass(instance, value, callback)

    def connect(self, port_from, port_to, callback, loaded=False):
        #if not loaded:
        #    self._pedalboard.connect(port_from, port_to)

        # Cases below happen because we just save instance ID in pedalboard connection structure, not whole string
        #if not 'system' in port_from and not 'effect' in port_from:
        #    port_from = "effect_%s" % port_from
        #if not 'system' in port_to and not 'effect' in port_to:
        #    port_to = "effect_%s" % port_to

        #if "system" in port_to:
        #    def cb(result):
        #        if result:
        #            if port_to == "system:playback_1":
        #                self.connect(port_from, "effect_%d:%s" % (CLIPMETER_OUT, CLIPMETER_L), lambda r: r, True)
        #                self._playback_1_connected_ports.append(port_from)
        #                if self._peakmeter:
        #                    self.connect(port_from, "effect_%d:%s" % (PEAKMETER_OUT, PEAKMETER_L), lambda r: r, True)
        #            elif port_to == "system:playback_2":
        #                self.connect(port_from, "effect_%d:%s" % (CLIPMETER_OUT, CLIPMETER_R), lambda r: r, True)
        #                self._playback_2_connected_ports.append(port_from)
        #                if self._peakmeter:
        #                    self.connect(port_from, "effect_%d:%s" % (PEAKMETER_OUT, PEAKMETER_R), lambda r: r, True)
        #        callback(result)
        #else:
        #    cb = callback

        self.host.connect(port_from, port_to, callback)

    def format_port(self, port):
        if not 'system' in port and not 'effect' in port:
            port = "effect_%s" % port
        return port

    def disconnect(self, port_from, port_to, callback, loaded=False):
        """if not loaded:
            self._pedalboard.disconnect(port_from, port_to)

        port_from = self.format_port(port_from)
        port_to = self.format_port(port_to)

        if "system" in port_to:

            def cb(result):
                if result:
                    if port_to == "system:playback_1":
                        self.disconnect(port_from, "effect_%d:%s" % (CLIPMETER_OUT, CLIPMETER_L), lambda r: r, True)
                        if self._peakmeter:
                            self.disconnect(port_from, "effect_%d:%s" % (PEAKMETER_OUT, PEAKMETER_L), lambda r: r, True)
                        try:
                            self._playback_1_connected_ports.remove(port_from)
                        except ValueError:
                            pass
                    elif port_to == "system:playback_2":
                        self.disconnect(port_from, "effect_%d:%s" % (CLIPMETER_OUT, CLIPMETER_R), lambda r: r, True)
                        if self._peakmeter:
                            self.disconnect(port_from, "effect_%d:%s" % (PEAKMETER_OUT, PEAKMETER_R), lambda r: r, True)
                        try:
                            self._playback_2_connected_ports.remove(port_from)
                        except ValueError:
                            pass
                callback(result)
        else:
            cb = callback
        """
        self.host.disconnect(port_from, port_to, callback)

    def hmi_parameter_set(self, instance_id, port_id, value, callback):
        #self.browser.send(instance_id, port_id, value)
        self.parameter_set(self.instance_mapper.get_instance(instance_id) + "/" + port_id, value, callback)

    def preset_load(self, instance_id, uri, callback):
        self.host.preset_load(instance_id, uri, callback)

    def parameter_set(self, port, value, callback, loaded=False):
        if port == ":bypass":
            # self.bypass(instance_id, value, callback)
            return
        #self.recorder.parameter(instance, port_id, value)
        self.host.param_set(port, value, callback)

    def parameter_get(self, port, callback):
        self.host.param_get(port, callback)

    def set_monitor(self, addr, port, status, callback):
        self.host.monitor(addr, port, status, callback)

    def parameter_monitor(self, instance_id, port_id, op, value, callback):
        self.host.param_monitor(instance_id, port_id, op, value, callback)

    # TODO: jack cpu load with ingen
    def jack_cpu_load(self, callback=lambda result: None):
        def cb(result):
            if result['ok']:
                pass
                #self.browser.send(99999, 'cpu_load', round(result['value']))
        self.host.cpu_load(cb)
    # END host commands

    # hmi commands
    def start_session(self, callback=None):
        self._playback_1_connected_ports = []
        self._playback_2_connected_ports = []

        def verify(resp):
            if callback:
                callback(resp)
            else:
                assert resp
        self.bank_address(0, 0, 1, 0, 0, lambda r: None)
        self.bank_address(0, 0, 1, 1, 0, lambda r: None)
        self.bank_address(0, 0, 1, 2, 0, lambda r: None)
        self.bank_address(0, 0, 1, 3, 0, lambda r: None)

        self.hmi.ui_con(verify)

    def end_session(self, callback):
        self.hmi.ui_dis(callback)

    def bypass_address(self, instance_id, hardware_type, hardware_id, actuator_type, actuator_id, value, label,
                       callback, loaded=False):
        self.parameter_address(instance_id, ":bypass", 'switch', label, 6, "none", value,
                               1, 0, 0, hardware_type, hardware_id, actuator_type,
                               actuator_id, [], callback, loaded)

    def parameter_addressing_next(self, hardware_type, hardware_id, actuator_type, actuator_id, callback):
        addrs = self._pedalboard.addressings[(hardware_type, hardware_id, actuator_type, actuator_id)]
        if len(addrs['addrs']) > 0:
            addrs['idx'] = (addrs['idx'] + 1) % len(addrs['addrs'])
            callback(True)
            self.parameter_addressing_load(hardware_type, hardware_id, actuator_type, actuator_id,
                                           addrs['idx'])
            return True
        #elif len(addrs['addrs']) <= 0:
        #   self.hmi.control_clean(hardware_type, hardware_id, actuator_type, actuator_id)
        callback(True)
        return False

    def parameter_addressing_load(self, hw_type, hw_id, act_type, act_id, idx=None):
        addrs = self._pedalboard.addressings[(hw_type, hw_id, act_type, act_id)]
        if idx == None:
            idx = addrs['idx']
        try:
            addressing = addrs['addrs'][idx]
        except IndexError:
            return
        self.hmi.control_add(addressing['instance_id'], addressing['port_id'], addressing['label'],
                             addressing['type'], addressing['unit'], addressing['value'],
                             addressing['maximum'], addressing['minimum'], addressing['steps'],
                             addressing['actuator'][0], addressing['actuator'][1],
                             addressing['actuator'][2], addressing['actuator'][3], len(addrs['addrs']), idx+1,
                             addressing.get('options', []))


    def parameter_address(self, port, addressing_type, label, ctype,
                          unit, current_value, maximum, minimum, steps,
                          hardware_type, hardware_id, actuator_type, actuator_id,
                          options, callback, loaded=False):
        # TODO the IHM parameters set by hardware.js should be here!
        # The problem is that we need port data, and getting it now is expensive
        """
        instance_id: effect instance
        port_id: control port
        addressing_type: 'range', 'switch' or 'tap_tempo'
        label: lcd display label
        ctype: 0 linear, 1 logarithm, 2 enumeration, 3 toggled, 4 trigger, 5 tap tempo, 6 bypass
        unit: string representing the parameter unit (hz, bpm, seconds, etc)
        hardware_type: the hardware model
        hardware_id: the id of the hardware where we find this actuator
        actuator_type: the encoder button type
        actuator_id: the encoder button number
        options: array of options, each one being a tuple (value, label)
        """
        instance_id = self.instance_mapper.map(port.rpartition("/")[0])
        port_id = port.rpartition("/")[-1]
        if (hardware_type == -1 and
            hardware_id == -1 and
            actuator_type == -1 and
            actuator_id == -1):
            if not loaded:
                a = self._pedalboard.parameter_unaddress(instance_id, port_id)
                if a:
                    if not self.parameter_addressing_next(a[0], a[1], a[2], a[3], callback):
                        self.hmi.control_rm(instance_id, port_id, lambda r:None)
                else:
                    callback(True)
            else:
                self.hmi.control_rm(instance_id, port_id, callback)
            return
        if not loaded:
            old = self._pedalboard.parameter_address(instance_id, port_id,
                                                     addressing_type,
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
                                                     options)

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
                                 len(self._pedalboard.addressings[(hardware_type, hardware_id, actuator_type, actuator_id)]['addrs']),
                                 len(self._pedalboard.addressings[(hardware_type, hardware_id, actuator_type, actuator_id)]['addrs']),
                                 options,
                                 callback)
            if old:
                self.parameter_addressing_load(*old)
        else:
            callback(True)


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

    def effect_position(self, instance, x, y):
        self.host.set_position(instance, x, y)
        #self._pedalboard.set_position(instance, x, y)

    def pedalboard_size(self, width, height):
        self.host.set_pedalboard_size(width, height)

    def clipmeter(self, pos, value):
        self._clipmeter.set(pos, value)

    def peakmeter(self, pos, value, peak, callback=None):
        cb = callback
        if not cb:
            cb = lambda r: r
        self.hmi.peakmeter(pos, value, peak, cb)

    def tuner(self, value, callback=None):
        cb = callback
        if not cb:
            cb = lambda r: r

        freq, note, cents = find_freqnotecents(value)
        self.hmi.tuner(freq, note, cents, cb)

    def start_recording(self):
        if self.player.playing:
            self.player.stop()
        self.recorder.start(self._pedalboard)

    def stop_recording(self):
        if self.recorder.recording:
            self.recording = self.recorder.stop()
            return self.recording

    def start_playing(self, stop_callback):
        if self.recorder.recording:
            self.recording = self.recorder.stop()
        def stop():
            self.unmute(stop_callback)
        def schedule_stop():
            ioloop.IOLoop.instance().add_timeout(timedelta(seconds=0.5), stop)
        def play():
            self.player.play(self.recording['handle'], schedule_stop)
        self.mute(play)

    def stop_playing(self):
        self.player.stop()

    def reset_recording(self):
        self.recording = None

    def mute(self, callback):
        self.set_audio_state(False, callback)
    def unmute(self, callback):
        self.set_audio_state(True, callback)

    def set_audio_state(self, state, callback):
        if self.mute_state == state:
            return callback()
        self.mute_state = state
        connections = self._pedalboard.data['connections']
        queue = []
        for connection in connections:
            if connection[2] == 'system' and connection[3].startswith('playback'):
                port_from = self.format_port(':'.join([str(x) for x in connection[:2]]))
                port_to = self.format_port(':'.join([str(x) for x in connection[2:]]))
                queue.append([port_from, port_to])
        def consume(result=None):
            if len(queue) == 0:
                return callback()
            nxt = queue.pop(0)
            if state:
                self.host.connect(nxt[0], nxt[1], consume)
            else:
                self.host.disconnect(nxt[0], nxt[1], consume)
        consume()

    def serialize_pedalboard(self):
        return self._pedalboard.serialize()

    def xrun(self, callback=None):
        cb = callback
        if not cb:
            cb = lambda r: r
        self.hmi.xrun(cb)

SESSION = Session()
