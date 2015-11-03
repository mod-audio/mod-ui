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

"""
This module works as an interface for mod-host, it uses a socket to communicate
with mod-host, the protocol is described in <http://github.com/portalmod/mod-host>

The module relies on tornado.ioloop stuff, but you need to start the ioloop
by yourself:

>>> from tornado import ioloop
>>> ioloop.IOLoop.instance().start()

This will start the mainloop and will handle the callbacks and the async functions
"""

from carla_utils import *
from tornado import ioloop
import logging

class Host(object):
    def __init__(self, uri):
        self.carla = CarlaHostDLL("/usr/lib/carla/libcarla_standalone2.so")
        self.carla.set_engine_callback(self.carla_callback)
        self.carla.set_engine_option(ENGINE_OPTION_PREFER_PLUGIN_BRIDGES, 0, "")
        self.carla.set_engine_option(ENGINE_OPTION_PREFER_UI_BRIDGES, 0, "")
        self.carla.set_engine_option(ENGINE_OPTION_PROCESS_MODE, ENGINE_PROCESS_MODE_MULTIPLE_CLIENTS, "")
        self.carla.set_engine_option(ENGINE_OPTION_TRANSPORT_MODE, ENGINE_TRANSPORT_MODE_JACK, "")
        self.carla.set_engine_option(ENGINE_OPTION_PATH_BINARIES, 0, "/usr/lib/carla/")
        self.carla.set_engine_option(ENGINE_OPTION_PATH_RESOURCES, 0, "/usr/share/carla/resources/")
        self.sock  = None
        self.timer = ioloop.PeriodicCallback(self.timer_callback, 300)
        self.connected = False

        self.msg_callback = lambda msg:None

        self._client_id_system = -1
        self._plugins_info = []

        ioloop.IOLoop.instance().add_callback(self.init_connection)

    def __del__(self):
        if self.sock is None:
            return

        if self.carla.is_engine_running():
            self.timer.stop()
            self.carla.engine_close()

        self.sock = None

    def _getPluginId(self, instance):
        for i in range(len(self._plugins_info)):
            if self._plugins_info[i]['name'] == instance:
                return i
        return -1

    def init_connection(self):
        self.open_connection_if_needed(lambda:None)

    def open_connection_if_needed(self, callback):
        if self.sock is not None:
            callback()
            return

        if self.carla.engine_init("JACK", "MOD"):
            self.timer.start()
            self.sock = True
            self.connected = True

    # host stuff
    def initial_setup(self, callback):
        callback(True)

    def get(self, subject):
        if subject == "/graph":
            self._client_id_system = -1
            self.carla.patchbay_refresh(True)
            return

    def add_plugin(self, instance, uri, enabled, x, y, callback):
        if self.carla.add_plugin(BINARY_NATIVE, PLUGIN_LV2, "", instance, uri, 0, None, 0x0):
            if enabled:
                self.carla.set_active(self.carla.get_current_plugin_count()-1, True)
            callback(True)
        else:
            callback(False)

    def remove_plugin(self, instance, callback):
        pluginId = self._getPluginId(instance)
        if pluginId >= 0:
            self.carla.remove_plugin(pluginId)
            callback(True)
        else:
            callback(False)

    def enable(self, instance, enabled, callback):
        pluginId = self._getPluginId(instance)
        if pluginId >= 0:
            self.carla.set_active(pluginId, enabled)
            callback(True)
        else:
            callback(False)

    def param_set(self, port, value, callback):
        instance, port = port.rsplit("/", 1)
        pluginId = self._getPluginId(instance)
        if pluginId >= 0:
            #parameterId = self._plugins_info[pluginId]['symbols'][parameterId]
            #self.carla.set_parameter_value(pluginId, parameterId, value)
            callback(True)
        else:
            callback(False)

    def set_position(self, instance, x, y, callback):
        # TODO
        callback(True)

    def connect(self, port_from, port_to, callback):
        # TODO
        #split_from = port_from.split("/")
        #if len(split_from) != 3:
            #return
        #if split_from[1] == "system":
            #groupIdA = self._client_id_system
            #portIdA  = int(split_from[2].rsplit("_",1)[-1])
            #instance_from, port_from = port_from.rsplit("/", 1)
        #else:
            #groupIdB = self._getPluginId(split_from[:1].join("/"))
            #portIdB  = int(split_from[2].rsplit("_",1)[-1])
            #instance_from, port_from = port_from.rsplit("/", 1)
        #self.carla.patchbay_connect()
        callback(True)

    def disconnect(self, port_from, port_to, callback):
        # TODO
        callback(True)

    def set_pedalboard_name(self, title, callback):
        # TODO
        callback(True)

    def set_pedalboard_size(self, width, height, callback):
        # TODO
        callback(True)

    def add_external_port(self, name, mode, typ, callback):
        # ignored
        callback(True)

    def remove_external_port(self, name, callback):
        # ignored
        callback(True)

    def carla_callback(self, host, action, pluginId, value1, value2, value3, valueStr):
        valueStr = charPtrToString(valueStr)
        print("carla callback", host, action, pluginId, value1, value2, value3, valueStr)

        # Debug.
        # This opcode is undefined and used only for testing purposes.
        if action == ENGINE_CALLBACK_DEBUG:
            return

        # A plugin has been added.
        # @a pluginId Plugin Id
        # @a valueStr Plugin name
        if action == ENGINE_CALLBACK_PLUGIN_ADDED:
            if pluginId != len(self._plugins_info):
                return

            info = self.carla.get_plugin_info(pluginId)
            self._plugins_info.append(info)

            uri  = info['label']
            x    = 0.0
            y    = 0.0
            msg = """[]
            a <http://lv2plug.in/ns/ext/patch#Put> ;
            <http://lv2plug.in/ns/ext/patch#subject> <%s> ;
            <http://lv2plug.in/ns/ext/patch#body> [
                <http://drobilla.net/ns/ingen#canvasX> "%.1f"^^<http://www.w3.org/2001/XMLSchema#float> ;
                <http://drobilla.net/ns/ingen#canvasY> "%.1f"^^<http://www.w3.org/2001/XMLSchema#float> ;
                <http://drobilla.net/ns/ingen#enabled> true ;
                <http://lv2plug.in/ns/lv2core#prototype> <%s> ;
                a <http://drobilla.net/ns/ingen#Block> ;
            ] .
            """ % (valueStr, x, y, uri)

            self.plugin_added_callback(valueStr, uri, False, x, y)
            self.msg_callback(msg)
            return

        # A plugin has been removed.
        # @a pluginId Plugin Id
        if action == ENGINE_CALLBACK_PLUGIN_REMOVED:
            if pluginId >= len(self._plugins_info):
                return
            info = self._plugins_info.pop(pluginId)

            msg = """[]
            a <http://lv2plug.in/ns/ext/patch#Delete> ;
            <http://lv2plug.in/ns/ext/patch#subject> <%s> .
            """ % (info['name'])
            self.plugin_removed_callback(info['name'])
            self.msg_callback(msg)
            return

        # A plugin has been renamed.
        # @a pluginId Plugin Id
        # @a valueStr New plugin name
        if action == ENGINE_CALLBACK_PLUGIN_RENAMED:
            return

        # A plugin has become unavailable.
        # @a pluginId Plugin Id
        # @a valueStr Related error string
        if action == ENGINE_CALLBACK_PLUGIN_UNAVAILABLE:
            return

        # A parameter value has changed.
        # @a pluginId Plugin Id
        # @a value1   Parameter index
        # @a value3   New parameter value
        if action == ENGINE_CALLBACK_PARAMETER_VALUE_CHANGED:
            return

        # A parameter default has changed.
        # @a pluginId Plugin Id
        # @a value1   Parameter index
        # @a value3   New default value
        if action == ENGINE_CALLBACK_PARAMETER_DEFAULT_CHANGED:
            return

        # A parameter's MIDI CC has changed.
        # @a pluginId Plugin Id
        # @a value1   Parameter index
        # @a value2   New MIDI CC
        if action == ENGINE_CALLBACK_PARAMETER_MIDI_CC_CHANGED:
            return

        # A parameter's MIDI channel has changed.
        # @a pluginId Plugin Id
        # @a value1   Parameter index
        # @a value2   New MIDI channel
        if action == ENGINE_CALLBACK_PARAMETER_MIDI_CHANNEL_CHANGED:
            return

        # A plugin option has changed.
        # @a pluginId Plugin Id
        # @a value1   Option
        # @a value2   New on/off state (1 for on, 0 for off)
        # @see PluginOptions
        if action == ENGINE_CALLBACK_OPTION_CHANGED:
            return

        # The current program of a plugin has changed.
        # @a pluginId Plugin Id
        # @a value1   New program index
        if action == ENGINE_CALLBACK_PROGRAM_CHANGED:
            return

        # The current MIDI program of a plugin has changed.
        # @a pluginId Plugin Id
        # @a value1   New MIDI program index
        if action == ENGINE_CALLBACK_MIDI_PROGRAM_CHANGED:
            return

        # A plugin's custom UI state has changed.
        # @a pluginId Plugin Id
        # @a value1   New state, as follows:
        #                  0: UI is now hidden
        #                  1: UI is now visible
        #                 -1: UI has crashed and should not be shown again
        if action == ENGINE_CALLBACK_UI_STATE_CHANGED:
            return

        # A note has been pressed.
        # @a pluginId Plugin Id
        # @a value1   Channel
        # @a value2   Note
        # @a value3   Velocity
        if action == ENGINE_CALLBACK_NOTE_ON:
            return

        # A note has been released.
        # @a pluginId Plugin Id
        # @a value1   Channel
        # @a value2   Note
        if action == ENGINE_CALLBACK_NOTE_OFF:
            return

        # A plugin needs update.
        # @a pluginId Plugin Id
        if action == ENGINE_CALLBACK_UPDATE:
            return

        # A plugin's data/information has changed.
        # @a pluginId Plugin Id
        if action == ENGINE_CALLBACK_RELOAD_INFO:
            return

        # A plugin's parameters have changed.
        # @a pluginId Plugin Id
        if action == ENGINE_CALLBACK_RELOAD_PARAMETERS:
            return

        # A plugin's programs have changed.
        # @a pluginId Plugin Id
        if action == ENGINE_CALLBACK_RELOAD_PROGRAMS:
            return

        # A plugin state has changed.
        # @a pluginId Plugin Id
        if action == ENGINE_CALLBACK_RELOAD_ALL:
            return

        # A patchbay client has been added.
        # @a pluginId Client Id
        # @a value1   Client icon
        # @a value2   Plugin Id (-1 if not a plugin)
        # @a valueStr Client name
        # @see PatchbayIcon
        if action == ENGINE_CALLBACK_PATCHBAY_CLIENT_ADDED:
            if valueStr == "system":
                self._client_id_system = pluginId
            return

        # A patchbay client has been removed.
        # @a pluginId Client Id
        if action == ENGINE_CALLBACK_PATCHBAY_CLIENT_REMOVED:
            if self._client_id_system == pluginId:
                self._client_id_system = -1
            return

        # A patchbay client has been renamed.
        # @a pluginId Client Id
        # @a valueStr New client name
        if action == ENGINE_CALLBACK_PATCHBAY_CLIENT_RENAMED:
            return

        # A patchbay client data has changed.
        # @a pluginId Client Id
        # @a value1   New icon
        # @a value2   New plugin Id (-1 if not a plugin)
        # @see PatchbayIcon
        if action == ENGINE_CALLBACK_PATCHBAY_CLIENT_DATA_CHANGED:
            return

        # A patchbay port has been added.
        # @a pluginId Client Id
        # @a value1   Port Id
        # @a value2   Port hints
        # @a valueStr Port name
        # @see PatchbayPortHints
        if action == ENGINE_CALLBACK_PATCHBAY_PORT_ADDED:
            if self._client_id_system == pluginId:
                if value2 & PATCHBAY_PORT_TYPE_MIDI:
                    types = "<http://lv2plug.in/ns/ext/atom#bufferType> <http://lv2plug.in/ns/ext/atom#Sequence> ;\n"
                    types += "a <http://lv2plug.in/ns/ext/atom#AtomPort> ,\n"
                elif value2 & PATCHBAY_PORT_TYPE_AUDIO:
                    types = "a <http://lv2plug.in/ns/lv2core#AudioPort> ,\n"
                elif value2 & PATCHBAY_PORT_TYPE_CV:
                    types = "a <http://lv2plug.in/ns/lv2core#CVPort> ,\n"
                else:
                    return
                if value2 & PATCHBAY_PORT_IS_INPUT:
                    types += "<http://lv2plug.in/ns/lv2core#OutputPort>\n"
                else:
                    types += "<http://lv2plug.in/ns/lv2core#InputPort>\n"
                msg = """[]
                a <http://lv2plug.in/ns/ext/patch#Put> ;
                <http://lv2plug.in/ns/ext/patch#subject> </graph/system/%s> ;
                <http://lv2plug.in/ns/ext/patch#body> [
                    <http://lv2plug.in/ns/lv2core#index> "0"^^<http://www.w3.org/2001/XMLSchema#int> ;
                    <http://lv2plug.in/ns/lv2core#name> "%s" ;
                    %s
                ] .
                """ % (valueStr, valueStr.title().replace("_", " "), types)
                self.msg_callback(msg)
            return

        # A patchbay port has been removed.
        # @a pluginId Client Id
        # @a value1   Port Id
        if action == ENGINE_CALLBACK_PATCHBAY_PORT_REMOVED:
            return

        # A patchbay port has been renamed.
        # @a pluginId Client Id
        # @a value1   Port Id
        # @a valueStr New port name
        if action == ENGINE_CALLBACK_PATCHBAY_PORT_RENAMED:
            return

        # A patchbay connection has been added.
        # @a pluginId Connection Id
        # @a valueStr Out group, port plus in group and port, in "og:op:ig:ip" syntax.
        if action == ENGINE_CALLBACK_PATCHBAY_CONNECTION_ADDED:
            return

        # A patchbay connection has been removed.
        # @a pluginId Connection Id
        if action == ENGINE_CALLBACK_PATCHBAY_CONNECTION_REMOVED:
            return

        # Engine started.
        # @a value1   Process mode
        # @a value2   Transport mode
        # @a valuestr Engine driver
        # @see EngineProcessMode
        # @see EngineTransportMode
        if action == ENGINE_CALLBACK_ENGINE_STARTED:
            return

        # Engine stopped.
        if action == ENGINE_CALLBACK_ENGINE_STOPPED:
            return

        # Engine process mode has changed.
        # @a value1 New process mode
        # @see EngineProcessMode
        if action == ENGINE_CALLBACK_PROCESS_MODE_CHANGED:
            return

        # Engine transport mode has changed.
        # @a value1 New transport mode
        # @see EngineTransportMode
        if action == ENGINE_CALLBACK_TRANSPORT_MODE_CHANGED:
            return

        # Engine buffer-size changed.
        # @a value1 New buffer size
        if action == ENGINE_CALLBACK_BUFFER_SIZE_CHANGED:
            return

        # Engine sample-rate changed.
        # @a value3 New sample rate
        if action == ENGINE_CALLBACK_SAMPLE_RATE_CHANGED:
            return

        # NSM callback.
        # (Work in progress, values are not defined yet)
        if action == ENGINE_CALLBACK_NSM:
            return

        # Idle frontend.
        # This is used by the engine during long operations that might block the frontend,
        # giving it the possibility to idle while the operation is still in place.
        if action == ENGINE_CALLBACK_IDLE:
            return

        # Show a message as information.
        # @a valueStr The message
        if action == ENGINE_CALLBACK_INFO:
            return

        # Show a message as an error.
        # @a valueStr The message
        if action == ENGINE_CALLBACK_ERROR:
            return

        # The engine has crashed or malfunctioned and will no longer work.
        if action == ENGINE_CALLBACK_QUIT:
            return

    def timer_callback(self):
        self.carla.engine_idle()

    #def open_connection(self, callback=None):
        #self.socket_idle = False

        #if (self.latest_callback):
            ## There's a connection waiting, let's just send an error
            ## for it to finish properly
            #try:
                #self.latest_callback("finish\0".encode("utf-8"))
            #except Exception as e:
                #logging.warn("[host] latest callback failed: %s" % str(e))

        #self.latest_callback = None

        #def check_response():
            #if callback is not None:
                #callback()
            #if len(self.queue):
                #self.process_queue()
            #else:
                #self.socket_idle = True
            ##self.setup_monitor()

        #s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #self.s = iostream.IOStream(s)
        #self.s.set_close_callback(self.open_connection)

        #ioloop.IOLoop.instance().add_callback(lambda: self.s.connect((self.address, self.port), check_response))

    #def send(self, msg, callback, datatype='int'):
        #self.queue.append((msg, callback, datatype))
        #if self.socket_idle:
            #self.process_queue()

    #def process_queue(self):
        #try:
            #msg, callback, datatype = self.queue.pop(0)
            #logging.info("[host] popped from queue: %s" % msg)
        #except IndexError:
            #self.socket_idle = True
            #return

        #def check_response(resp):
            #resp = resp.decode("utf-8", errors="ignore")

            #logging.info("[host] received <- %s" % repr(resp))
            #if not resp.startswith("resp"):
                #logging.error("[host] protocol error: %s" % ProtocolError(resp)) # TODO: proper error handling

            #r = resp.replace("resp ", "").replace("\0", "").strip()
            #callback(process_resp(r, datatype))
            #self.process_queue()

        #self.socket_idle = False
        #logging.info("[host] sending -> %s" % msg)

        #encmsg = "%s\0" % str(msg)
        #self.s.write(encmsg.encode("utf-8"))
        #self.s.read_until("\0".encode("utf-8"), check_response)

        #self.latest_callback = check_response

    #def add(self, uri, instance_id, callback=lambda result: None):
        #self.send("add %s %d" % (uri, instance_id), callback)

    #def remove(self, instance_id, callback=lambda result: None):
        #self.send("remove %d" % instance_id, callback, datatype='boolean')

    #def connect(self, origin_port, destination_port, callback=lambda result: None):
        #self.send("connect %s %s" % (origin_port, destination_port), callback, datatype='boolean')

    #def disconnect(self, origin_port, destination_port, callback=lambda result: None):
        #self.send("disconnect %s %s" % (origin_port, destination_port), callback, datatype='boolean')

    #def param_set(self, instance_id, symbol, value, callback=lambda result: None):
        #self.send("param_set %d %s %f" % (instance_id, symbol, value), callback, datatype='boolean')

    #def param_get(self, instance_id, symbol, callback=lambda result: None):
        #self.send("param_get %d %s" % (instance_id, symbol), callback, datatype='float_structure')

    #def preset_load(self, instance_id, label, callback=lambda result: None):
        #self.send('preset %d "%s"' % (instance_id, label), callback, datatype='boolean')

    #def param_monitor(self, instance_id, symbol, op, value, callback=lambda result: None):
        #self.send("param_monitor %d %s %s %f" % (instance_id, symbol, op, value), callback, datatype='boolean')

    #def monitor(self, addr, port, status, callback=lambda result: None):
        #self.send("monitor %s %d %d" % (addr, port, status), callback, datatype='boolean')

    #def bypass(self, instance_id, value, callback=lambda result: None):
        #self.send("bypass %d %d" % (instance_id, value), callback, datatype='boolean')

    #def cpu_load(self, callback=lambda result: None):
        #self.send("cpu_load", callback, datatype='float_structure')
