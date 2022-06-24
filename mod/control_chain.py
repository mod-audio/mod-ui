#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import socket
from tornado import gen, iostream
from tornado.ioloop import IOLoop
from mod import symbolify

CC_MODE_TOGGLE      = 0x001
CC_MODE_TRIGGER     = 0x002
CC_MODE_OPTIONS     = 0x004
CC_MODE_TAP_TEMPO   = 0x008
CC_MODE_REAL        = 0x010
CC_MODE_INTEGER     = 0x020
CC_MODE_LOGARITHMIC = 0x040
CC_MODE_COLOURED    = 0x100
CC_MODE_MOMENTARY   = 0x200
CC_MODE_REVERSE     = 0x400

# ---------------------------------------------------------------------------------------------------------------------

class ControlChainDeviceListener(object):
    socket_path = "/tmp/control-chain.sock"

    def __init__(self, hw_added_cb, hw_removed_cb, hw_disconnected_cb, act_added_cb):
        self.crashed        = False
        self.idle           = False
        self.initialized    = False
        self.initialized_cb = None
        self.hw_added_cb    = hw_added_cb
        self.hw_removed_cb  = hw_removed_cb
        self.hw_disconnected_cb = hw_disconnected_cb
        self.act_added_cb   = act_added_cb
        self.hw_counter     = {}
        self.hw_versions    = {}
        self.write_queue    = []

        self.start()

    # -----------------------------------------------------------------------------------------------------------------

    def start(self):
        if not os.path.exists(self.socket_path):
            print("cc start socket missing")
            self.initialized = True
            return

        self.initialized = False

        self.socket = iostream.IOStream(socket.socket(socket.AF_UNIX, socket.SOCK_STREAM))
        self.socket.set_close_callback(self.connection_closed)
        self.socket.set_nodelay(True)

        # put device_list message in queue, so it's handled asap
        self.send_request("device_list", None, self.device_list_init)

        # ready to roll
        self.socket.connect(self.socket_path, self.connection_started)

    def restart_if_crashed(self):
        if not self.crashed:
            return

        self.crashed = False
        self.start()

    def wait_initialized(self, callback):
        if self.initialized:
            callback()
            return

        self.initialized_cb = callback
        IOLoop.instance().call_later(10, self.wait_init_timeout)

    def wait_init_timeout(self):
        if self.initialized:
            return

        print("Control Chain initialization timed out")
        self.socket = None

        if self.initialized_cb is not None:
            cb = self.initialized_cb
            self.initialized_cb = None
            cb()

    # -----------------------------------------------------------------------------------------------------------------

    def connection_started(self):
        if len(self.write_queue):
            self.process_write_queue()
        else:
            self.idle = True

    def connection_closed(self):
        print("Control Chain closed")
        self.socket  = None
        self.crashed = True
        self.hw_counter = {}
        self.write_queue = []
        self.set_initialized()

        hw_versions = self.hw_versions.copy()
        self.hw_versions = {}
        for dev_id, (dev_uri, label, labelsuffix, version) in hw_versions.items():
            if dev_uri in self.hw_counter:
                self.hw_versions[dev_id] = (dev_uri, label, labelsuffix, version)
                self.hw_disconnected_cb(dev_id, dev_uri, label+labelsuffix, version)
            else:
                self.hw_removed_cb(dev_id, dev_uri, label+labelsuffix, version)

        IOLoop.instance().call_later(2, self.restart_if_crashed)

    def set_initialized(self):
        print("Control Chain initialized")
        self.initialized = True

        if self.initialized_cb is not None:
            cb = self.initialized_cb
            self.initialized_cb = None
            cb()

    # -----------------------------------------------------------------------------------------------------------------

    def process_read_queue(self, _=None):
        self.socket.read_until(b"\0", self.check_read_response)

    @gen.coroutine
    def check_read_response(self, resp):
        try:
            data = json.loads(resp[:-1].decode("utf-8", errors="ignore"))
        except:
            print("ERROR: Control Chain read response failed")
        else:
            if 'event' not in data.keys():
                print("ERROR: Control Chain read response invalid, missing 'event' field", data)

            elif data['event'] == "device_status":
                data   = data['data']
                dev_id = data['device_id']

                if data['status']:
                    yield gen.Task(self.send_device_descriptor, dev_id)

                else:
                    try:
                        (dev_uri, label, labelsuffix, version) = self.hw_versions[dev_id]
                    except KeyError:
                        print("ERROR: Control Chain device removed, but not on current list!?", dev_id)
                    else:
                        if dev_uri in self.hw_counter:
                            self.hw_counter[dev_uri] -= 1
                            self.hw_disconnected_cb(dev_id, dev_uri, label+labelsuffix, version)
                        else:
                            self.hw_versions.pop(dev_id)
                            self.hw_removed_cb(dev_id, dev_uri, label+labelsuffix, version)

        finally:
            self.process_read_queue()

    # -----------------------------------------------------------------------------------------------------------------

    def process_write_queue(self):
        try:
            to_send, request_name, callback = self.write_queue.pop(0)
        except IndexError:
            self.idle = True
            return

        if self.socket is None:
            self.process_write_queue()
            return

        def check_write_response(resp):
            if callback is not None:
                try:
                    data = json.loads(resp[:-1].decode("utf-8", errors="ignore"))
                except:
                    data = None
                    print("ERROR: Control Chain write response failed")
                else:
                    if data is not None:
                        if 'reply' not in data.keys():
                            print("ERROR: Control Chain write response invalid, missing 'reply' field", data)
                            data = None
                        elif data['reply'] != request_name:
                            print("ERROR: Control Chain reply name mismatch")
                            data = None

                if data is not None:
                    callback(data['data'])

            self.process_write_queue()

        self.idle = False
        self.socket.write(to_send)
        self.socket.read_until(b"\0", check_write_response)

    # -----------------------------------------------------------------------------------------------------------------

    def send_request(self, request_name, request_data, callback=None):

        request = {
            'request': request_name,
            'data'   : request_data
        }

        to_send = bytes(json.dumps(request).encode('utf-8')) + b'\x00'
        self.write_queue.append((to_send, request_name, callback))

        if self.idle:
            self.process_write_queue()

    # -----------------------------------------------------------------------------------------------------------------

    @gen.coroutine
    def device_list_init(self, dev_list):
        for dev_id in dev_list:
            yield gen.Task(self.send_device_descriptor, dev_id)

        if not self.initialized:
            self.send_request('device_status', {'enable':1}, self.process_read_queue)

        self.set_initialized()

    # -----------------------------------------------------------------------------------------------------------------

    def send_device_descriptor(self, dev_id, callback):
        def dev_desc_cb(dev):
            dev_uri = dev['uri']

            if " " in dev_uri or "<" in dev_uri or ">" in dev_uri:
                print("WARNING: Control Chain device URI '%s' is invalid" % dev_uri)
                callback()
                return

            if 'protocol' in dev:
                protocol_version = tuple(int(v) for v in dev['protocol'].split("."))
                supports_feedback = protocol_version >= (0,6)
            else:
                protocol_version = (0,0)
                supports_feedback = False

            if supports_feedback:
                # use connected hw counter as id
                if dev_uri not in self.hw_counter:
                    dev_unique_id = 0
                else:
                    dev_unique_id = self.hw_counter[dev_uri]

                # increment counter for next device with the same URI
                self.hw_counter[dev_uri] = dev_unique_id + 1

            else:
                # assign an unique id starting from 0
                dev_unique_id = 0
                for _dev_uri, _1, _2, _3 in self.hw_versions.values():
                    if _dev_uri == dev_uri:
                        dev_unique_id += 1

            if dev_unique_id != 0:
                dev_label_suffix = " " + str(dev_unique_id+1)
            else:
                dev_label_suffix = ""

            self.hw_added_cb(dev_id, dev_uri, dev['label'], dev_label_suffix, dev['version'])
            self.hw_versions[dev_id] = (dev_uri, dev['label'], dev_label_suffix, dev['version'])

            for actuator in dev['actuators']:
                modes_int = actuator['supported_modes']
                modes_str = ""

                if modes_int & CC_MODE_TOGGLE:
                    modes_str += ":bypass:toggled"
                if modes_int & CC_MODE_TRIGGER:
                    modes_str += ":trigger"
                if modes_int & CC_MODE_OPTIONS:
                    modes_str += ":enumeration"
                if modes_int & CC_MODE_TAP_TEMPO:
                    modes_str += ":taptempo"
                if modes_int & CC_MODE_REAL:
                    modes_str += ":float"
                if modes_int & CC_MODE_INTEGER:
                    modes_str += ":integer"
                if modes_int & CC_MODE_LOGARITHMIC:
                    modes_str += ":logarithmic"
                if modes_int & CC_MODE_COLOURED:
                    modes_str += ":colouredlist"
                if modes_int & CC_MODE_MOMENTARY:
                    modes_str += ":momentarytoggle"

                if not modes_str:
                    continue

                modes_str += ":"

                metadata = {
                    'uri'  : "%s:%i:%i" % (dev_uri, dev_unique_id, actuator['id']),
                    'name' : "%s%s:%s" % (dev['label'], dev_label_suffix, actuator['name']),
                    'modes': modes_str,
                    'steps': [],
                    'widgets': [],
                    'feedback': supports_feedback,
                    'max_assigns': actuator['max_assignments'],
                }
                self.act_added_cb(dev_id, actuator['id'], metadata)

            for actuatorgroup in dev['actuatorgroups']:
                modes_str = ":enumeration"

                # check if grouped actuators support colouredlist, retrieve max_assigns
                for actuator in dev['actuators']:
                    if actuator['id'] != actuatorgroup['actuator1']:
                        continue
                    if actuator['supported_modes'] & CC_MODE_COLOURED:
                        modes_str += ":colouredlist"
                    max_assigns = actuator['max_assignments']
                    break
                else:
                    print("WARNING: Control Chain group '%s' is invalid" % actuatorgroup['name'])
                    continue

                modes_str += ":"

                metadata = {
                    'uri'  : "%s:%i:%i" % (dev_uri, dev_unique_id, actuatorgroup['id']),
                    'name' : "%s%s:%s" % (dev['label'], dev_label_suffix, actuatorgroup['name']),
                    'modes': modes_str,
                    'steps': [],
                    'widgets': [],
                    'feedback': True,
                    'max_assigns': max_assigns,
                    'actuator_group': ("%s:%i:%i" % (dev_uri, dev_unique_id, actuatorgroup['actuator1']),
                                       "%s:%i:%i" % (dev_uri, dev_unique_id, actuatorgroup['actuator2'])),
                }
                self.act_added_cb(dev_id, (actuatorgroup['id'],
                                           actuatorgroup['actuator1'],
                                           actuatorgroup['actuator2']), metadata)

            callback()

        self.send_request('device_descriptor', {'device_id':dev_id}, dev_desc_cb)

    # -----------------------------------------------------------------------------------------------------------------

if __name__ == "__main__":
    from tornado.web import Application
    from tornado.ioloop import IOLoop

    def hw_added_cb(dev_id, dev_uri, label, labelsuffix, version):
        print("hw_added_cb", dev_uri, label, labelsuffix, version)

    def hw_removed_cb(dev_id, dev_uri, label, version):
        print("hw_removed_cb", dev_id)

    def hw_disconnected_cb(dev_id, dev_uri, label, version):
        print("hw_disconnected_cb", dev_id)

    def act_added_cb(dev_id, actuator_id, metadata):
        print("act_added_cb", dev_id, actuator_id, metadata)

    application = Application()
    cc = ControlChainDeviceListener(hw_added_cb, hw_removed_cb, hw_disconnected_cb, act_added_cb)
    IOLoop.instance().start()
