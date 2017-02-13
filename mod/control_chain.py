#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import socket
from tornado import gen, iostream
from mod import symbolify

# ---------------------------------------------------------------------------------------------------------------------

class ControlChainDeviceListener(object):
    socket_path = "/tmp/control-chain.sock"

    def __init__(self, hw_added_cb, act_added_cb, act_removed_cb):
        self.crashed        = False
        self.idle           = False
        self.initialized    = False
        self.initialized_cb = None
        self.hw_added_cb    = hw_added_cb
        self.act_added_cb   = act_added_cb
        self.act_removed_cb = act_removed_cb
        self.write_queue    = []

        self.start()

    # -----------------------------------------------------------------------------------------------------------------

    def start(self):
        if not os.path.exists(self.socket_path):
            print("cc start socket missing")
            self.initialized = True
            return

        self.initialized = False
        print("cc start socket initializing")

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

    # -----------------------------------------------------------------------------------------------------------------

    def connection_started(self):
        print("cc started")
        if len(self.write_queue):
            self.process_write_queue()
        else:
            self.idle = True

    def connection_closed(self):
        print("cc closed")
        self.socket  = None
        self.crashed = True
        self.set_initialized()

    def set_initialized(self):
        print("cc initialized")
        self.initialized = True

        if self.initialized_cb is not None:
            cb = self.initialized_cb
            self.initialized_cb = None
            cb()

    # -----------------------------------------------------------------------------------------------------------------

    @gen.coroutine
    def process_read_queue(self, ignored=None):
        print("process_read_queue 1")

        def check_read_response(resp):
            print("process_read_queue resp 2")
            try:
                data = json.loads(resp[:-1].decode("utf-8", errors="ignore"))
            except:
                print("ERROR: control-chain read response failed")
            else:
                if data['event'] == "device_status":
                    data   = data['data']
                    dev_id = data['device_id']

                    if data['status']:
                        print("process_read_queue resp 3")
                        yield gen.Task(self.send_device_descriptor, dev_id)
                        print("process_read_queue resp 4")

                    else:
                        self.act_removed_cb(dev_id)

            print("process_read_queue resp 4")
            self.process_read_queue()

        print("process_read_queue resp 1.1")
        self.socket.read_until(b"\0", check_read_response)

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
                    print("ERROR: control-chain write response failed")
                else:
                    if data is not None and data['reply'] != request_name:
                        print("ERROR: control-chain reply name mismatch")
                        data = None

                if data is not None:
                    callback(data['data'])

            self.process_write_queue()

        self.idle = False
        self.socket.write(to_send)
        self.socket.read_until(b"\0", check_write_response)

    # -----------------------------------------------------------------------------------------------------------------

    def send_request(self, request_name, request_data, callback=None):
        print("cc send_request", request_name, request_data)

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
        print("cc device_list_init", dev_list)

        for dev_id in dev_list:
            yield gen.Task(self.send_device_descriptor, dev_id)

        print("cc device_list_finished")
        if not self.initialized:
            self.send_request('device_status', {'enable':1}, self.process_read_queue)
        self.set_initialized()

    # -----------------------------------------------------------------------------------------------------------------

    def send_device_descriptor(self, dev_id, callback):
        print("cc send_device_descriptor", dev_id)

        def dev_desc_cb(dev):
            print("cc send_device_descriptor RESP", dev_id, dev)

            # FIXME
            dev_uri = "/cc/%s-%i" % (symbolify(dev['label']), dev_id)
            self.hw_added_cb(dev_uri, dev['version'])

            for actuator in dev['actuators']:
                uri = "/cc/%s-%i/%i" % (symbolify(dev['label']), dev_id, actuator['id'])
                metadata = {
                    'uri'  : uri,
                    # FIXME
                    'name' : dev['label'] + " " + str(actuator['id']+1),
                    'modes': ":bypass:trigger:toggled:",
                    'steps': [],
                    'max_assigns': 1,
                    'version': dev['version']
                }
                print("cc added", metadata)
                self.act_added_cb(dev_id, actuator['id'], metadata)

            callback()

        self.send_request('device_descriptor', {'device_id':dev_id}, dev_desc_cb)
