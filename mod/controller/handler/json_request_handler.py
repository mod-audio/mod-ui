#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

import json

from tornado.util import unicode_type

from mod.controller.handler.timeless_request_handler import TimelessRequestHandler


class JsonRequestHandler(TimelessRequestHandler):
    def write(self, data):
        # FIXME: something is sending strings out, need to investigate what later..
        # it's likely something using write(json.dumps(...))
        # we want to prevent that as it causes issues under Mac OS

        if isinstance(data, (bytes, unicode_type, dict)):
            TimelessRequestHandler.write(self, data)
            self.finish()
            return

        elif data is True:
            data = "true"
            self.set_header("Content-Type", "application/json; charset=UTF-8")

        elif data is False:
            data = "false"
            self.set_header("Content-Type", "application/json; charset=UTF-8")

        # TESTING for data types, remove this later
        #elif not isinstance(data, list):
            #print("=== TESTING: Got new data type for RequestHandler.write():", type(data), "msg:", data)
            #data = json.dumps(data)
            #self.set_header('Content-type', 'application/json')

        else:
            data = json.dumps(data)
            self.set_header("Content-Type", "application/json; charset=UTF-8")

        TimelessRequestHandler.write(self, data)
        self.finish()
