#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

from mod.controller.handler.json_request_handler import JsonRequestHandler


class CachedJsonRequestHandler(JsonRequestHandler):
    def set_default_headers(self):
        JsonRequestHandler.set_default_headers(self)
        self.set_header("Cache-Control", "public, max-age=31536000")
        self.set_header("Expires", "Mon, 31 Dec 2035 12:00:00 gmt")
