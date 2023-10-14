#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

from mod.controller.handler.json_request_handler import JsonRequestHandler
from mod.util.origin_utils import OriginUtils


class RemoteRequestHandler(JsonRequestHandler):

    def set_default_headers(self):
        if 'Origin' not in self.request.headers.keys():
            return

        origin = self.request.headers['Origin']

        if OriginUtils.is_valid_domain(origin):
            self.set_header("Access-Control-Allow-Origin", origin)
