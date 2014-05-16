# -*- coding: utf-8
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


import unittest
from mod.addressing import ControlChainMessage

class ControlChainMessageTest(unittest.TestCase):

    def setUp(self):
        self.msg = ControlChainMessage()

    def parse(self, string):
        return self.msg.parse(string)

    def build(self, destination, function, data={}):
        return self.msg.build(destination, function, data)

    def test_connection_device(self):
        msg = '\x00\x00\x01\x29\x00\x25http://portalmod.com/moduino/mydevice\x01\x01\x00'
        msg = self.parse(msg)
        self.assertEquals(msg.origin, 0)
        self.assertEquals(msg.destination, 0)
        self.assertEquals(msg.function, 1)
        self.assertEquals(msg.data.url, 'http://portalmod.com/moduino/mydevice')
        self.assertEquals(msg.data.channel, 1)
        self.assertEquals(msg.data.protocol_version, 1)

    def test_connection_host(self):
        data = {
            'url': 'http://portalmod.com/moduino/mydevice',
            'channel': 1,
            'protocol_version': 1
            }
            
        msg = self.build(128, 1, data)
        self.assertEquals(msg, '\x80\x00\x01\x29\x00\x25http://portalmod.com/moduino/mydevice\x01\x01\x00')

    def test_error_protocol_not_supported(self):
        msg = '\x80\x00\xFF\x0E\x00\x01\x01\x0BUpgrade MOD'
        msg = self.parse(msg)
        self.assertEquals(msg.origin, 0)
        self.assertEquals(msg.destination, 128)
        self.assertEquals(msg.function, 255)
        self.assertEquals(msg.data.function, 1)
        self.assertEquals(msg.data.code, 1)
        self.assertEquals(msg.data.message, "Upgrade MOD")

    def test_device_descriptor_host(self):
        msg = self.build(128, 2)
        self.assertEquals(msg, '\x80\x00\x02\x00\x00')

    def test_device_descriptor_device(self):
        msg = '\x00\x80\x02\x4F\x00\x09My device\x02\x01\x04knob\x02\x08\x00\x00\x08\x08\x00\xFF\x03\x10\x00\x20\x00\x40\x00\x02\x04foot\x04\x7D\x5D\x06ON/OFF\x7D\x4D\x05PULSE\x02\x00\x09Tap tempo\x2A\x22\x06Rotate\x01\x00'
        msg = self.parse(msg)
        self.assertEquals(msg.origin, 128)
        self.assertEquals(msg.destination, 0)
        self.assertEquals(msg.function, 2)
        self.assertEquals(msg.data.name, 'My device')
        self.assertEquals(len(msg.data.actuator), 2)
        self.assertEquals(msg.data.actuator[0].id, 1)
        self.assertEquals(msg.data.actuator[0].name, 'knob')
        self.assertEquals(msg.data.actuator[0].slots, 255)
        self.assertEquals(msg.data.actuator[0].steps, [16, 32, 64])
        self.assertEquals(len(msg.data.actuator[0].modes), 2)
        self.assertEquals(msg.data.actuator[0].modes[0].mask, 0x0800)
        self.assertEquals(msg.data.actuator[0].modes[0].label, '')
        self.assertEquals(msg.data.actuator[0].modes[1].mask, 0x0808)
        self.assertEquals(msg.data.actuator[0].modes[1].label, '')
        self.assertEquals(msg.data.actuator[1].id, 2)
        self.assertEquals(msg.data.actuator[1].name, 'foot')
        self.assertEquals(msg.data.actuator[1].slots, 1)
        self.assertEquals(msg.data.actuator[1].steps, [])
        self.assertEquals(len(msg.data.actuator[1].modes), 4)
        self.assertEquals(msg.data.actuator[1].modes[0].mask, 0x7D5D)
        self.assertEquals(msg.data.actuator[1].modes[0].label, 'ON/OFF')
        self.assertEquals(msg.data.actuator[1].modes[1].mask, 0x7D4D)
        self.assertEquals(msg.data.actuator[1].modes[1].label, 'PULSE')
        self.assertEquals(msg.data.actuator[1].modes[2].mask, 0x0200)
        self.assertEquals(msg.data.actuator[1].modes[2].label, 'Tap tempo')
        self.assertEquals(msg.data.actuator[1].modes[3].mask, 0x2A22)
        self.assertEquals(msg.data.actuator[1].modes[3].label, 'Rotate')


    def test_control_addressing_host(self):
        data = {
            'actuator_id': 1,
            'chosen_mask': 0x0C00,
            'addressing_id': 1,
            'port_mask': 0x0C,
            'label': 'Delay',
            'value': 1.0,
            'minimum': 0,
            'maximum': 1.0,
            'default': 0,
            'steps': 33,
            'unit': '%d dB',
            'scale_points': [
                {
                    'labil': 'One',
                    'value': 1.0,
                    }, {
                    'labil': 'Two',
                    'value': 2, # using int is intentional, lib must tolerate
                    },
                ]
            
            }
        msg = self.build(128, 3, data)
        self.assertEquals(msg, '\x80\x00\x03\x34\x00\x01\x0C\x00\x01\x0C\x05Delay\x00\x00\x80\x3F\x00\x00\x00\x00\x00\x00\x80\x3F\x00\x00\x00\x00\x21\x00\x05%d dB\x02\x03One\x00\x00\x80\x3F\x03Two\x00\x00\x00\x40')

    def test_control_addressing_device(self):
        msg = '\x00\x80\x03\x02\x00\x00\x00'
        msg = self.parse(msg)
        self.assertEquals(msg.origin, 128)
        self.assertEquals(msg.destination, 0)
        self.assertEquals(msg.function, 3)
        self.assertEquals(msg.data.resp_status, 0)

    def test_data_request_host(self):
        msg = self.build(128, 4, { 'seq': 67 })
        self.assertEquals(msg, '\x80\x00\x04\x01\x00\x43')

    def test_data_request_device(self):
        msg = '\x00\x80\x04\x0D\x00\x02\x00\x00\x00\x80\x3F\x03\x00\x00\xDC\x43\x01\x04'
        msg = self.parse(msg)
        self.assertEquals(msg.origin, 128)
        self.assertEquals(msg.destination, 0)
        self.assertEquals(msg.function, 4)
        self.assertEquals(len(msg.data.events), 2)
        self.assertEquals(msg.data.events[0].id, 0)
        self.assertEquals(msg.data.events[0].value, 1.0)
        self.assertEquals(msg.data.events[1].id, 3)
        self.assertEquals(msg.data.events[1].value, 440.0)
        self.assertEquals(msg.data.requests, [4])

    def test_control_unaddressing_host(self):
        msg = self.build(128, 5, { 'addressing_id': 3 })
        self.assertEquals(msg, '\x80\x00\x05\x01\x00\x03')

    def test_control_unaddressing_device(self):
        msg = '\x00\x80\x05\x00\x00'
        msg = self.parse(msg)
        self.assertEquals(msg.origin, 128)
        self.assertEquals(msg.destination, 0)
        self.assertEquals(msg.function, 5)

        
if __name__ == '__main__':
    unittest.main()
