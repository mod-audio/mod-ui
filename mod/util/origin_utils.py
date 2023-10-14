#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

import re


class OriginUtils:
    VALID_PROTOCOLS = ("http", "https")
    VALID_DOMAINS = ("mod.audio", "moddevices.com")

    @staticmethod
    def is_valid(origin: str) -> bool:
        match = re.match(r'^(\w+)://([^/]*)/?', origin)

        if match is None:
            return False

        protocol, domain = match.groups()

        if not OriginUtils.is_valid_protocol(protocol):
            return False

        return OriginUtils.is_valid_domain(domain)

    @staticmethod
    def is_valid_protocol(protocol: str) -> bool:
        return protocol in OriginUtils.VALID_PROTOCOLS

    @staticmethod
    def is_valid_domain(domain: str) -> bool:
        is_valid_subdomain = lambda valid_domain: domain.endswith(f".{valid_domain}")

        return domain in OriginUtils.VALID_DOMAINS or any(map(is_valid_subdomain, OriginUtils.VALID_DOMAINS))
