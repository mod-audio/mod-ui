#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

import os
from uuid import uuid4

from tornado import web, gen

from mod.controller.handler.json_request_handler import JsonRequestHandler


@web.stream_request_body
class MultiPartFileReceiver(JsonRequestHandler):
    @property
    def destination_dir(self):
        raise NotImplementedError

    @classmethod
    def urls(cls, path):
        return [
            (r"/%s/$" % path, cls),
        ]

    def prepare(self):
        self.basename = "/tmp/" + str(uuid4())
        if not os.path.exists(self.destination_dir):
            os.mkdir(self.destination_dir)
        self.filehandle = open(os.path.join(self.destination_dir, self.basename), 'wb')
        self.filehandle.write(b'')

        if 'expected_size' in self.request.arguments:
            self.request.connection.set_max_body_size(int(self.get_argument('expected_size')))
        else:
            self.request.connection.set_max_body_size(200*1024*1024)

        if 'body_timeout' in self.request.arguments:
            self.request.connection.set_body_timeout(float(self.get_argument('body_timeout')))

    def data_received(self, data):
        self.filehandle.write(data)

    @web.asynchronous
    @gen.engine
    def post(self):
        # self.result can be set by subclass in process_file,
        # so that answer will be returned to browser
        self.result = None

        self.filehandle.flush()
        self.filehandle.close()

        yield gen.Task(self.process_file, self.basename)
        self.write({
            'ok': True,
            'result': self.result
        })

    def process_file(self, basename, callback=lambda: None):
        """to be overriden"""
