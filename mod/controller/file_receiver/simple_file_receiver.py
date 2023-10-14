#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later


import os
from uuid import uuid4

from tornado import web, gen

from mod.controller.handler.json_request_handler import JsonRequestHandler


class SimpleFileReceiver(JsonRequestHandler):
    @property
    def destination_dir(self):
        raise NotImplementedError

    @classmethod
    def urls(cls, path):
        return [
            (r"/%s/$" % path, cls),
        ]

    @web.asynchronous
    @gen.engine
    def post(self, sessionid=None, chunk_number=None):
        # self.result can be set by subclass in process_file,
        # so that answer will be returned to browser
        self.result = None

        basename = str(uuid4())
        if not os.path.exists(self.destination_dir):
            os.mkdir(self.destination_dir)
        with open(os.path.join(self.destination_dir, basename), 'wb') as fh:
            fh.write(self.request.body)

        yield gen.Task(self.process_file, basename)
        self.write({
            'ok': True,
            'result': self.result
        })

    def process_file(self, basename, callback=lambda: None):
        """to be overriden"""
