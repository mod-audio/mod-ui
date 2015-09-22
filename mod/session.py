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
                          PEAKMETER_MON_PEAK_R, PEAKMETER_L, PEAKMETER_R, TUNER, TUNER_URI, TUNER_MON_PORT, TUNER_PORT,
                          INGEN_AUTOCONNECT,
                          INGEN_NUM_AUDIO_INS, INGEN_NUM_AUDIO_OUTS,
                          INGEN_NUM_MIDI_INS, INGEN_NUM_MIDI_OUTS,
                          INGEN_NUM_CV_INS, INGEN_NUM_CV_OUTS)
from mod import symbolify
from mod.addressing import Addressing
from mod.development import FakeHost, FakeHMI
from mod.hardware import get_hardware
from mod.hmi import HMI
from mod.ingen import Host
from mod.lv2 import add_bundle_to_lilv_world
from mod.clipmeter import Clipmeter
from mod.recorder import Recorder, Player
from mod.screenshot import ScreenshotGenerator
from mod.tuner import NOTES, FREQS, find_freqnotecents
from mod.jacklib_helpers import jacklib, charPtrToString, charPtrPtrToStringList

# TODO stuff:
# - ingen command to remove all plugins?
# - callback for loaded graph?

class Session(object):
    def __init__(self):
        self.host_initialized = False

        self._tuner = False
        self._tuner_port = 1
        self._peakmeter = False

        self.monitor_server = None
        self.current_bank = None
        self.hmi_initialized = False

        # JACK client name of the backend
        self.backend_client_name = "ingen"

        # Used in mod-app to know when the current pedalboard changed
        self.pedalboard_changed_callback = lambda ok,bundlepath,title:None

        # For saving the current pedalboard bundlepath and title
        self.bundlepath = None
        self.title      = None

        self.engine_samplerate = 48000 # default value
        self.jack_client = None
        self.xrun_count = 0
        self.xrun_count2 = 0

        self.ioloop = ioloop.IOLoop.instance()
        self.host = Host(os.environ.get("MOD_INGEN_SOCKET_URI", "unix:///tmp/ingen.sock"))

        # Try to open real HMI
        hmiOpened = False

        if not DEV_HMI:
            self.hmi  = HMI(HMI_SERIAL_PORT, HMI_BAUD_RATE, self.hmi_initialized_cb)
            hmiOpened = self.hmi.sp is not None

        print("Using HMI =>", hmiOpened)

        if hmiOpened:
            # If all ok, use addressings
            self.addressings = Addressing(self.hmi)
        else:
            # Otherwise disable HMI entirely
            self.hmi = FakeHMI(HMI_SERIAL_PORT, HMI_BAUD_RATE, self.hmi_initialized_cb)
            self.addressings = None

        self.recorder = Recorder()
        self.player = Player()
        self.mute_state = True
        self.recording = None
        self.instances = []
        self.screenshot_generator = ScreenshotGenerator()

        self._clipmeter = Clipmeter(self.hmi)
        self.websockets = []
        self.mididevuuids = []

        self.jack_cpu_load_timer = ioloop.PeriodicCallback(self.jack_cpu_load_timer_callback, 1000)
        self.jack_xrun_timer     = ioloop.PeriodicCallback(self.jack_xrun_timer_callback, 500)

        self.ioloop.add_callback(self.init_jack)
        self.ioloop.add_callback(self.init_socket)

    def __del__(self):
        if self.jack_client is None:
            return
        jacklib.deactivate(self.jack_client)
        jacklib.client_close(self.jack_client)
        self.jack_client = None
        print("jacklib client deactivated")

    def get_hardware(self):
        if self.addressings is None:
            return {}
        return get_hardware()

    # -----------------------------------------------------------------------------------------------------------------
    # App utilities, needed only for mod-app

    def setupApp(self, clientName, pedalboardChangedCallback):
        self.backend_client_name = clientName
        self.pedalboard_changed_callback = pedalboardChangedCallback

    def reconnectApp(self):
        if self.host.sock is not None:
            self.host.sock.close()
            self.host.sock = None
        self.host.open_connection_if_needed(self.host_callback)

    # -----------------------------------------------------------------------------------------------------------------
    # Initialization

    def autoconnect_jack(self):
        if self.jack_client is None:
            return

        for i in range(1, INGEN_NUM_AUDIO_INS+1):
            jacklib.connect(self.jack_client, "system:capture_%i" % i, "%s:audio_port_%i_in" % (SESSION.backend_client_name, i))

        for i in range(1, INGEN_NUM_AUDIO_OUTS+1):
            jacklib.connect(self.jack_client,"%s:audio_port_%i_out" % (SESSION.backend_client_name, i), "system:playback_%i" % i)

        if not DEV_HMI:
            # this means we're using HMI, so very likely running MOD hardware
            jacklib.connect(self.jack_client, "alsa_midi:ttymidi MIDI out in", "%s:midi_port_1_in" % SESSION.backend_client_name)
            jacklib.connect(self.jack_client, "%s:midi_port_1_out" % SESSION.backend_client_name, "alsa_midi:ttymidi MIDI in out")

    def init_jack(self):
        self.jack_client = jacklib.client_open("%s-helper" % self.backend_client_name, jacklib.JackNoStartServer, None)
        self.xrun_count  = 0
        self.xrun_count2 = 0

        if self.jack_client is None:
            return

        #jacklib.jack_set_port_registration_callback(self.jack_client, self.JackPortRegistrationCallback, None)
        jacklib.set_property_change_callback(self.jack_client, self.JackPropertyChangeCallback, None)
        jacklib.set_xrun_callback(self.jack_client, self.JackXRunCallback, None)
        jacklib.on_shutdown(self.jack_client, self.JackShutdownCallback, None)
        jacklib.activate(self.jack_client)
        print("jacklib client activated")

        if INGEN_AUTOCONNECT:
            self.ioloop.add_timeout(timedelta(seconds=3.0), self.autoconnect_jack)

    def init_socket(self):
        self.host.open_connection_if_needed(self.host_callback)

    def hmi_initialized_cb(self):
        logging.info("hmi initialized")
        self.hmi_initialized = True
        self.hmi.clear()

        if self.addressings is not None:
            self.addressings.init_host()

    # -----------------------------------------------------------------------------------------------------------------
    # Timers (start and stop in sync with webserver IOLoop)

    def start_timers(self):
        self.jack_cpu_load_timer.start()
        self.jack_xrun_timer.start()

    def stop_timers(self):
        self.jack_xrun_timer.stop()
        self.jack_cpu_load_timer.stop()

    # -----------------------------------------------------------------------------------------------------------------
    # Webserver callbacks, called from the browser (see webserver.py)
    # These will be called as a reponse to an action in the browser.
    # A callback must always be used unless specified otherwise.

    # Add a new plugin, starts enabled (ie, not bypassed)
    def web_add(self, instance, uri, x, y, callback):
        self.host.add_plugin(instance, uri, True, x, y, callback)

    # Remove a plugin
    def web_remove(self, instance, callback):
        self.host.remove_plugin(instance, callback)

    # Set a plugin parameter
    # We use ":bypass" symbol for on/off state
    def web_parameter_set(self, port, value, callback):
        instance, port2 = port.rsplit("/",1)

        if port2 == ":bypass":
            value = value >= 0.5
            self.host.enable(instance, not value, callback)
        else:
            self.host.param_set(port, value, callback)

        #self.recorder.parameter(port, value)

    # Address a plugin parameter
    def web_parameter_address(self, port, addressing_type, label, ctype, unit, value, maximum, minimum, steps,
                              actuator, options, callback):
        if self.addressings is None or not self.hmi_initialized:
            callback(False)
            return

        instance, port2 = port.rsplit("/",1)
        self.addressings.address(instance, port2, addressing_type, label, ctype, unit, value, maximum, minimum, steps,
                                 actuator, options, callback)

    # Set a parameter for MIDI learn
    def web_parameter_midi_learn(self, port, callback):
        self.host.midi_learn(port, callback)

    # Load a plugin preset
    def web_preset_load(self, instance, uri, callback):
        self.host.preset_load(instance, uri, callback)

    # Set a plugin block position within the canvas
    def web_set_position(self, instance, x, y, callback):
        self.host.set_position(instance, x, y, callback)

    # Connect 2 ports
    def web_connect(self, port_from, port_to, callback):
        self.host.connect(port_from, port_to, callback)

    # Disconnect 2 ports
    def web_disconnect(self, port_from, port_to, callback):
        self.host.disconnect(port_from, port_to, callback)

    # Get list of Hardware MIDI devices
    # returns (devsInUse, devList)
    def web_get_midi_device_list(self):
        return self.get_midi_ports(self.backend_client_name), self.get_midi_ports("alsa_midi")

    # Set the selected MIDI devices to @a newDevs
    # Will remove or add new JACK ports as needed
    @gen.engine
    def web_set_midi_devices(self, newDevs):
        curDevs = self.get_midi_ports(self.backend_client_name)

        # remove
        for dev in curDevs:
            if dev in newDevs:
                continue
            if dev.startswith("MIDI Port-"):
                continue
            dev, modes = dev.rsplit(" (",1)
            jacklib.disconnect(self.jack_client, "alsa_midi:%s in" % dev, self.backend_client_name+":control_in")

            def remove_external_port_in(callback):
                self.host.remove_external_port(dev+" in")
                callback(True)
            def remove_external_port_out(callback):
                self.host.remove_external_port(dev+" out")
                callback(True)

            yield gen.Task(remove_external_port_in)

            if "out" in modes:
                yield gen.Task(remove_external_port_out)

        # add
        for dev in newDevs:
            if dev in curDevs:
                continue
            dev, modes = dev.rsplit(" (",1)

            def add_external_port_in(callback):
                self.host.add_external_port(dev+" in", "Input", "MIDI")
                callback(True)
            def add_external_port_out(callback):
                self.host.add_external_port(dev+" out", "Output", "MIDI")
                callback(True)

            yield gen.Task(add_external_port_in)

            if "out" in modes:
                yield gen.Task(add_external_port_out)

    # Send a ping to HMI
    def web_ping_hmi(self, callback):
        self.hmi.ping(callback)

    # A new webbrowser page has been open
    # We need to cache its socket address and send any msg callbacks to it
    def websocket_opened(self, ws):
        self.websockets.append(ws)

        self.host.open_connection_if_needed(self.host_callback)
        self.host.get("/graph")

    # Webbrowser page closed
    def websocket_closed(self, ws):
        self.websockets.remove(ws)

    # -----------------------------------------------------------------------------------------------------------------
    # JACK callbacks, called by JACK itself
    # We must take care to ensure not to block for long periods of time or else audio will skip or xrun.

    # Callback for when a port appears or disappears
    # We use this to trigger a auto-connect mode
    #def JackPortRegistrationCallback(self, port, registered, arg):
        #if self.jack_client is None:
            #return
        #if not registered:
            #return

    # Callback for when a client or port property changes.
    # We use this to know the full length name of ingen created ports.
    def JackPropertyChangeCallback(self, subject, key, change, arg):
        if self.jack_client is None:
            return
        if change != jacklib.PropertyCreated:
            return
        if key != jacklib.bJACK_METADATA_PRETTY_NAME:
            return

        self.mididevuuids.append(subject)
        self.ioloop.add_callback(self.jack_midi_devs_callback)

    # Callback for when an xrun occurs
    def JackXRunCallback(self, arg):
        self.xrun_count += 1
        return 0

    # Callback for when JACK has shutdown or our client zombified
    def JackShutdownCallback(self, arg):
        self.jack_client = None

    # -----------------------------------------------------------------------------------------------------------------
    # Misc/Utility functions
    # We use these to save possibly duplicated code.

    # Get all available MIDI ports of a specific JACK client.
    def get_midi_ports(self, client_name):
        if self.jack_client is None:
            return []

        # get input and outputs separately
        in_ports = charPtrPtrToStringList(jacklib.get_ports(self.jack_client, client_name+":", jacklib.JACK_DEFAULT_MIDI_TYPE,
                                                            jacklib.JackPortIsPhysical|jacklib.JackPortIsOutput
                                                            if client_name == "alsa_midi" else
                                                            jacklib.JackPortIsInput
                                                            ))
        out_ports = charPtrPtrToStringList(jacklib.get_ports(self.jack_client, client_name+":", jacklib.JACK_DEFAULT_MIDI_TYPE,
                                                             jacklib.JackPortIsPhysical|jacklib.JackPortIsInput
                                                             if client_name == "alsa_midi" else
                                                             jacklib.JackPortIsOutput
                                                             ))

        if client_name != "alsa_midi":
            if "ingen:control_in" in in_ports:
                in_ports.remove("ingen:control_in")
            if "ingen:control_out" in out_ports:
                out_ports.remove("ingen:control_out")

            for i in range(len(in_ports)):
                uuid = jacklib.port_uuid(jacklib.port_by_name(self.jack_client, in_ports[i]))
                ret, value, type_ = jacklib.get_property(uuid, jacklib.JACK_METADATA_PRETTY_NAME)
                if ret == 0 and type_ == b"text/plain":
                    in_ports[i] = charPtrToString(value)

            for i in range(len(out_ports)):
                uuid = jacklib.port_uuid(jacklib.port_by_name(self.jack_client, out_ports[i]))
                ret, value, type_ = jacklib.get_property(uuid, jacklib.JACK_METADATA_PRETTY_NAME)
                if ret == 0 and type_ == b"text/plain":
                    out_ports[i] = charPtrToString(value)

        # remove suffixes from ports
        in_ports  = [port.replace(client_name+":","",1).rsplit(" in" ,1)[0] for port in in_ports ]
        out_ports = [port.replace(client_name+":","",1).rsplit(" out",1)[0] for port in out_ports]

        # add our own suffix now
        ports = []
        for port in in_ports:
            #if "Midi Through" in port:
                #continue
            if port in ("jackmidi", "OSS sequencer"):
                continue
            ports.append(port + (" (in+out)" if port in out_ports else " (in)"))

        return ports

    # -----------------------------------------------------------------------------------------------------------------
    # Timer callbacks
    # These are functions called by the IO loop at regular intervals.

    # Single-shot callback that automatically connects new backend JACK MIDI ports to their hardware counterparts.
    def jack_midi_devs_callback(self):
        while len(self.mididevuuids) != 0:
            subject = self.mididevuuids.pop()

            ret, value, type_ = jacklib.get_property(subject, jacklib.JACK_METADATA_PRETTY_NAME)
            if ret != 0:
                continue
            if type_ != b"text/plain":
                continue

            value = charPtrToString(value)
            if not (value.endswith(" in") or value.endswith(" out")):
                continue

            mod_name  = "%s:%s" % (self.backend_client_name, value.replace(" ", "_").replace("-","_").lower())
            midi_name = "alsa_midi:%s" % value

            # All good, make connection now
            if value.endswith(" in"):
                jacklib.connect(self.jack_client, midi_name, mod_name)
                jacklib.connect(self.jack_client, midi_name, self.backend_client_name+":control_in")
            else:
                jacklib.connect(self.jack_client, mod_name, midi_name)

    # Callback for getting the current JACK cpu load and report it to the browser side.
    def jack_cpu_load_timer_callback(self):
        if self.jack_client is not None:
            msg = """[]
            a <http://lv2plug.in/ns/ext/patch#Set> ;
            <http://lv2plug.in/ns/ext/patch#subject> </engine/> ;
            <http://lv2plug.in/ns/ext/patch#property> <http://moddevices/ns/mod#cpuload> ;
            <http://lv2plug.in/ns/ext/patch#value> "%i" .
            """ % round(100.0 - jacklib.cpu_load(self.jack_client))

            for ws in self.websockets:
                ws.write_message(msg)

    # Callback that checks if xruns have occured.
    def jack_xrun_timer_callback(self):
        for i in range(self.xrun_count2, self.xrun_count):
            self.xrun_count2 += 1
            #self.hmi.xrun()

    # -----------------------------------------------------------------------------------------------------------------
    # TODO
    # Everything after this line is yet to be documented

    @gen.engine
    def host_callback(self):
        if self.host_initialized:
            return

        self.host_initialized = True

        def msg_callback(msg):
            for ws in self.websockets:
                ws.write_message(msg)

        def saved_callback(bundlepath):
            if add_bundle_to_lilv_world(bundlepath):
                pass #self.host.add_bundle(bundlepath)
            self.screenshot_generator.schedule_screenshot(bundlepath)

        def samplerate_callback(srate):
            self.engine_samplerate = srate

        def plugin_added_callback(instance, uri, enabled, x, y):
            if instance not in self.instances:
                self.instances.append(instance)

        def plugin_removed_callback(instance):
            if instance in self.instances:
                self.instances.remove(instance)

        self.host.msg_callback = msg_callback
        self.host.saved_callback = saved_callback
        self.host.samplerate_callback = samplerate_callback
        self.host.plugin_added_callback = plugin_added_callback
        self.host.plugin_removed_callback = plugin_removed_callback

        yield gen.Task(self.host.initial_setup)

        # Add ports
        for i in range(1, INGEN_NUM_AUDIO_INS+1):
            yield gen.Task(lambda callback: self.host.add_external_port("Audio Port-%i in" % i, "Input", "Audio", callback))

        for i in range(1, INGEN_NUM_AUDIO_OUTS+1):
            yield gen.Task(lambda callback: self.host.add_external_port("Audio Port-%i out" % i, "Output", "Audio", callback))

        for i in range(1, INGEN_NUM_MIDI_INS+1):
            yield gen.Task(lambda callback: self.host.add_external_port("MIDI Port-%i in" % i, "Input", "MIDI", callback))

        for i in range(1, INGEN_NUM_MIDI_OUTS+1):
            yield gen.Task(lambda callback: self.host.add_external_port("MIDI Port-%i out" % i, "Output", "MIDI", callback))

        for i in range(1, INGEN_NUM_CV_INS+1):
            yield gen.Task(lambda callback: self.host.add_external_port("CV Port-%i in" % i, "Input", "CV", callback))

        for i in range(1, INGEN_NUM_CV_OUTS+1):
            yield gen.Task(lambda callback: self.host.add_external_port("CV Port-%i out" % i, "Output", "CV", callback))

    def load_pedalboard(self, bundlepath, title):
        self.bundlepath = bundlepath
        self.title      = title
        self.host.load(bundlepath)
        self.pedalboard_changed_callback(True, bundlepath, title)

    def save_pedalboard(self, bundlepath, title, callback):
        def step1(ok):
            if ok: self.host.save(os.path.join(bundlepath, "%s.ttl" % symbolify(title)), step2)
            else: callback(False)

        def step2(ok):
            if ok:
                self.bundlepath = bundlepath
                self.title      = title
            else:
                self.bundlepath = None
                self.title      = None

            self.pedalboard_changed_callback(ok, bundlepath, title)
            callback(ok)

        self.host.set_pedalboard_name(title, step1)

    def reset(self, callback):
        self.bundlepath = None
        self.title      = None

        # Callback from socket
        def remove_next_plugin(ok):
            if not ok:
                callback(False)
                return

            try:
                instance = self.instances.pop(0)
            except IndexError:
                callback(True)
                return

            self.host.remove_plugin(instance, remove_next_plugin)

        # Callback from HMI, ignore ok status
        def remove_all_plugins(ok):
            remove_next_plugin(True)

        if self.hmi_initialized:
            self.hmi.clear(remove_all_plugins)
        else:
            remove_next_plugin(True)

        self.pedalboard_changed_callback(True, "", "")

    #def setup_monitor(self):
        #if self.monitor_server is None:
            #from mod.monitor import MonitorServer
            #self.monitor_server = MonitorServer()
            #self.monitor_server.listen(12345)

            #self.set_monitor("localhost", 12345, 1, self.add_tools)

    #def add_tools(self, resp):
        #if resp:
            #self.add(CLIPMETER_URI, CLIPMETER_IN, self.setup_clipmeter_in, True)
            #self.add(CLIPMETER_URI, CLIPMETER_OUT, self.setup_clipmeter_out, True)

    #def setup_clipmeter_in(self, resp):
        #if resp:
            #self.connect("system:capture_1", "effect_%d:%s" % (CLIPMETER_IN, CLIPMETER_L), lambda r:None, True)
            #self.connect("system:capture_2", "effect_%d:%s" % (CLIPMETER_IN, CLIPMETER_R), lambda r:None, True)
            #self.parameter_monitor(CLIPMETER_IN, CLIPMETER_MON_L, ">=", 0, lambda r:None)
            #self.parameter_monitor(CLIPMETER_IN, CLIPMETER_MON_R, ">=", 0, lambda r:None)

    #def setup_clipmeter_out(self, resp):
        #if resp:
            #self.parameter_monitor(CLIPMETER_OUT, CLIPMETER_MON_L, ">=", 0, lambda r:None)
            #self.parameter_monitor(CLIPMETER_OUT, CLIPMETER_MON_R, ">=", 0, lambda r:None)

    # host commands

    def bypass(self, instance, value, callback):
        value = int(value) > 0
        #if not loaded:
        #    self._pedalboard.bypass(instance_id, value)
        #self.recorder.bypass(instance, value)
        self.host.enable(instance, value, callback)

    def format_port(self, port):
        if not 'system' in port and not 'effect' in port:
            port = "effect_%s" % port
        return port

    #def set_monitor(self, addr, port, status, callback):
        #self.host.monitor(addr, port, status, callback)

    #def parameter_monitor(self, instance_id, port_id, op, value, callback):
        #self.host.param_monitor(instance_id, port_id, op, value, callback)

    # END host commands

    # hmi commands
    def start_session(self, callback=None):
        def verify(resp):
            if callback:
                callback(resp)
            else:
                assert(resp)
        self.bank_address(0, 0, 1, 0, 0, lambda r: None)
        self.bank_address(0, 0, 1, 1, 0, lambda r: None)
        self.bank_address(0, 0, 1, 2, 0, lambda r: None)
        self.bank_address(0, 0, 1, 3, 0, lambda r: None)

        self.hmi.ui_con(verify)

    def end_session(self, callback):
        self.hmi.ui_dis(callback)

    def bank_address(self, hardware_type, hardware_id, actuator_type, actuator_id, function, callback):
        """
        Function is an integer, meaning:
         - 0: Nothing (unaddress)
         - 1: True bypass
         - 2: Pedalboard up
         - 3: Pedalboard down
        """
        self.hmi.bank_config(hardware_type, hardware_id, actuator_type, actuator_id, function, callback)

    def pedalboard_size(self, width, height, callback):
        self.host.set_pedalboard_size(width, height, callback)

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
        self.recorder.start(self.backend_client_name)

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
            self.ioloop.add_timeout(timedelta(seconds=0.5), stop)
        def play():
            self.player.play(self.recording['handle'], schedule_stop)
        self.mute(play)

    def stop_playing(self):
        self.player.stop()

    def reset_recording(self):
        self.recording = None

    def mute(self, callback):
        return
        #self.set_audio_state(False, callback)

    def unmute(self, callback):
        return
        #self.set_audio_state(True, callback)

    #def set_audio_state(self, state, callback):
        #if self.mute_state == state:
            #return callback()
        #self.mute_state = state
        #connections = self._pedalboard.data['connections']
        #queue = []
        #for connection in connections:
            #if connection[2] == 'system' and connection[3].startswith('playback'):
                #port_from = self.format_port(':'.join([str(x) for x in connection[:2]]))
                #port_to = self.format_port(':'.join([str(x) for x in connection[2:]]))
                #queue.append([port_from, port_to])
        #def consume(result=None):
            #if len(queue) == 0:
                #return callback()
            #nxt = queue.pop(0)
            #if state:
                #self.host.connect(nxt[0], nxt[1], consume)
            #else:
                #self.host.disconnect(nxt[0], nxt[1], consume)
        #consume()

    #def serialize_pedalboard(self):
        #return self._pedalboard.serialize()

    #def xrun(self, callback=None):
        #cb = callback
        #if not cb:
            #cb = lambda r: r
        #self.hmi.xrun(cb)

SESSION = Session()
