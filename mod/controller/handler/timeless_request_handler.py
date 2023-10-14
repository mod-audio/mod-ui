#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

from tornado import web


class TimelessRequestHandler(web.RequestHandler):

    def compute_etag(self):
        return None

    def set_default_headers(self):
        self._headers.pop("Date")

    def should_return_304(self):
        return False
