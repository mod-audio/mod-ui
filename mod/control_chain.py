#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import socket
from tornado import iostream
from mod import symbolify

# ---------------------------------------------------------------------------------------------------------------------

class ControlChainDeviceListener(object):
    socket_path = "/tmp/control-chain.sock"

    def __init__(self, hw_added_cb, hw_removed_cb):
        self.crashed       = False
        self.idle          = False
        self.initialized   = False
        self.initialize_cb = None
        self.hw_added_cb   = hw_added_cb
        self.hw_removed_cb = hw_removed_cb
        self.pending_devs  = 0
        self.queue         = []

        self.start()

    # -----------------------------------------------------------------------------------------------------------------

    def start(self):
        if not os.path.exists(self.socket_path):
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

        self.initialize_cb = callback

    # -----------------------------------------------------------------------------------------------------------------

    def connection_started(self):
        if len(self.queue):
            self.process_write_queue()
        else:
            self.idle = True

    def connection_closed(self):
        self.socket  = None
        self.crashed = True
        self.set_initialized()

    def set_initialized(self):
        self.initialized = True

        if self.initialize_cb is not None:
            cb = self.initialize_cb
            self.initialize_cb = None
            cb()

    # -----------------------------------------------------------------------------------------------------------------

    def process_read_queue(self, ignored=None):
        def check_response(resp):
            try:
                data = json.loads(resp[:-1].decode("utf-8", errors="ignore"))
            except:
                print("ERROR: control-chain read response failed")
            else:
                if data['event'] == "device_status":
                    data   = data['data']
                    dev_id = data['device_id']

                    if data['status']:
                        self.send_device_descriptor(dev_id)

                    else:
                        self.hw_removed_cb(dev_id)

            self.process_read_queue()

        self.socket.read_until(b"\0", check_response)

    def process_write_queue(self):
        try:
            to_send, request_name, callback = self.queue.pop(0)
        except IndexError:
            self.idle = True
            return

        if self.socket is None:
            self.process_write_queue()
            return

        def check_response(resp):
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
        self.socket.read_until(b"\0", check_response)

    # -----------------------------------------------------------------------------------------------------------------

    def send_request(self, request_name, request_data, callback=None):
        request = {
            'request': request_name,
            'data'   : request_data
        }

        to_send = bytes(json.dumps(request).encode('utf-8')) + b'\x00'
        self.queue.append((to_send, request_name, callback))

        if self.idle:
            self.process_write_queue()

    # -----------------------------------------------------------------------------------------------------------------

    def device_list_init(self, dev_list):
        self.pending_devs = len(dev_list)

        if self.pending_devs == 0:
            return self.device_list_finished()

        for dev_id in dev_list:
            self.send_device_descriptor(dev_id)

    def device_list_finished(self):
        self.set_initialized()
        self.send_request('device_status', {'enable':1}, self.process_read_queue)

    # -----------------------------------------------------------------------------------------------------------------

    def send_device_descriptor(self, dev_id):
        def dev_desc_cb(dev):
            self.pending_devs -= 1

            for actuator in dev['actuators']:
                uri = "/cc/%s-%i/%i" % (symbolify(dev['label']), dev_id, actuator['id'])
                metadata = {
                    'uri'  : uri,
                    # FIXME
                    'name' : dev['label'] + " " + str(actuator['id']+1),
                    'modes': ":bypass:trigger:toggled:",
                    'steps': [],
                    'max_assigns': 1,
                }
                self.hw_added_cb(dev_id, actuator['id'], metadata)

            if self.pending_devs == 0:
                self.device_list_finished()

        self.send_request('device_descriptor', {'device_id':dev_id}, dev_desc_cb)
