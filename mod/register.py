
# Copyright 2012-2013 AGR Audio, Industria e Comercio LTDA. <contato@portalmod.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import urllib, json, re
from hashlib import md5
from os import mkdir
from os.path import exists
from mod.settings import (CLOUD_HTTP_ADDRESS, CLOUD_PUB, DEVICE_KEY, DEVICE_PUB,
                          DEVICE_SERIAL, DEVICE_MODEL, KEYPATH)
from mod.communication import crypto

class DeviceAlreadyRegistered(Exception):
    pass

class DeviceRegisterer(object):

    def __init__(self):
        pass

    def generate_registration_package(self, serial):
        if (exists(DEVICE_SERIAL) and
            exists(DEVICE_KEY) and
            exists(DEVICE_PUB)):
            raise DeviceAlreadyRegistered
        
        if not exists(KEYPATH):
            mkdir(KEYPATH)

        key = crypto.NewKey(1024)

        open(DEVICE_KEY, 'w').write(key.private)
        open(DEVICE_PUB, 'w').write(key.public)

        data = { 
            'public_key': key.public,
            'serial_number': serial,
            }

        serialized_data = json.dumps(data)
        checksum = md5(serialized_data.encode("utf-8")).hexdigest()
        signature = crypto.Sender(DEVICE_KEY, checksum).pack()

        return {
            'data': serialized_data,
            'signature': signature
            }

    def register(self, resp):
        serial_number = resp['serial_number']
        signature = resp['signature']

        if not crypto.Receiver(CLOUD_PUB, signature).unpack() == serial_number:
            return False

        model = re.search('^[A-Za-z]', serial_number).group().upper()

        open(DEVICE_SERIAL, 'w').write(serial_number)
        open(DEVICE_MODEL, 'w').write(model)

        return True
