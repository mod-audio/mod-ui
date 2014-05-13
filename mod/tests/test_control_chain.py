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
from mod.control_chain import ControlChain

class ControlChainParserTest(unittest.TestCase):

    def setUp(self):
        self.chain = ControlChain()

    def parse(self, msg):
        return self.chain.parse(msg)

    def test_connection_device(self):
        msg = '\x00\x00\x01\x0A\x00\x06my-dev\x01\x01\x00'
        msg = self.parse(msg)
        self.assertEquals(msg.origin, 0)
        self.assertEquals(msg.destination, 0)
        self.assertEquals(msg.function, 1)
        self.assertEquals(msg.connection.name, 'my-dev')
        self.assertEquals(msg.connection.channel, 1)
        self.assertEquals(msg.connection.protocol_version, 1)

    def test_connection_host(self):
        msg = '\x80\x00\x01\x0A\x00\x06my-dev\x01\x01\x00'
        msg = self.parse(msg)
        self.assertEquals(msg.origin, 0)
        self.assertEquals(msg.destination, 128)
        self.assertEquals(msg.function, 1)
        self.assertEquals(msg.connection.name, 'my-dev')
        self.assertEquals(msg.connection.channel, 1)
        self.assertEquals(msg.connection.protocol_version, 1)

    def test_error_protocol_not_supported(self):
        msg = '\x80\x00\xFF\x0E\x00\x01\x00\x0BUpgrade MOD'
        msg = self.parse(msg)
        self.assertEquals(msg.origin, 0)
        self.assertEquals(msg.destination, 128)
        self.assertEquals(msg.function, 255)
        self.assertEquals(msg.error.code, 1)
        self.assertEquals(msg.error.message, "Upgrade MOD")

    def test_device_descriptor_host(self):
        msg = '\x80\x00\x02\x00\x00'
        msg = self.parse(msg)
        self.assertEquals(msg.origin, 0)
        self.assertEquals(msg.destination, 128)
        self.assertEquals(msg.function, 2)

    def test_device_descriptor_device(self):
        msg = '\x00\x80\x02\x2E\x00\x02\x04knob\x03\x01\x00\x02\x00\x03\x00\x0A\x01\x03\x10\x00\x20\x00\x40\x00\x04foot\x02\x04\x06ON/OFF\x0C\x05PULSE\x01\x01\x00'
        msg = self.parse(msg)
        self.assertEquals(msg.origin, 128)
        self.assertEquals(msg.destination, 0)
        self.assertEquals(msg.function, 2)
        self.assertEquals(len(msg.dev_desc.actuator), 2)
        self.assertEquals(msg.dev_desc.actuator[0].name, 'knob')
        self.assertEquals(msg.dev_desc.actuator[0].slots, 10)
        self.assertEquals(msg.dev_desc.actuator[0].steps, [16, 32, 64])
        self.assertEquals(len(msg.dev_desc.actuator[0].mask), 3)
        self.assertEquals(msg.dev_desc.actuator[0].mask[0].prop, 1)
        self.assertEquals(msg.dev_desc.actuator[0].mask[0].label, '')
        self.assertEquals(msg.dev_desc.actuator[0].mask[1].prop, 2)
        self.assertEquals(msg.dev_desc.actuator[0].mask[1].label, '')
        self.assertEquals(msg.dev_desc.actuator[0].mask[2].prop, 3)
        self.assertEquals(msg.dev_desc.actuator[0].mask[2].label, '')
        self.assertEquals(msg.dev_desc.actuator[1].name, 'foot')
        self.assertEquals(msg.dev_desc.actuator[1].slots, 1)
        self.assertEquals(msg.dev_desc.actuator[1].steps, [])
        self.assertEquals(len(msg.dev_desc.actuator[1].mask), 2)
        self.assertEquals(msg.dev_desc.actuator[1].mask[0].prop, 4)
        self.assertEquals(msg.dev_desc.actuator[1].mask[0].label, 'ON/OFF')
        self.assertEquals(msg.dev_desc.actuator[1].mask[1].prop, 12)
        self.assertEquals(msg.dev_desc.actuator[1].mask[1].label, 'PULSE')
        

    def test_control_addressing_host(self):
        msg = '\x80\x00\x03\x30\x00\x01\x0C\x02\x08\x03BYP\x00\x00\x80\x3F\x00\x00\x00\x00\x00\x00\x80\x3F\x00\x00\x00\x00\x00\x00\x05%d dB\x02\x03One\x00\x00\x80\x3F\x03Two\x00\x00\x00\x40'
        msg = self.parse(msg)
        self.assertEquals(msg.origin, 0)
        self.assertEquals(msg.destination, 128)
        self.assertEquals(msg.function, 3)
        self.assertEquals(msg.control_addressing.addressing_id, 1)
        self.assertEquals(msg.control_addressing.port_mask, 12)
        self.assertEquals(msg.control_addressing.actuator_id, 2)
        self.assertEquals(msg.control_addressing.chosen_mask, 8)
        self.assertEquals(msg.control_addressing.label, 'BYP')
        self.assertEquals(msg.control_addressing.value, 1.0)
        self.assertEquals(msg.control_addressing.minimum, 0)
        self.assertEquals(msg.control_addressing.maximum, 1.0)
        self.assertEquals(msg.control_addressing.default, 0)
        self.assertEquals(msg.control_addressing.steps, 0)
        self.assertEquals(msg.control_addressing.unit, '%d dB')
        self.assertEquals(len(msg.control_addressing.scale_points), 2)
        self.assertEquals(msg.control_addressing.scale_points[0].label, 'One')
        self.assertEquals(msg.control_addressing.scale_points[0].value, 1.0)
        self.assertEquals(msg.control_addressing.scale_points[1].label, 'Two')
        self.assertEquals(msg.control_addressing.scale_points[1].value, 2.0)

    def test_control_addressing_device(self):
        msg = '\x00\x80\x03\x02\x00\x00\x00'
        msg = self.parse(msg)
        self.assertEquals(msg.origin, 128)
        self.assertEquals(msg.destination, 0)
        self.assertEquals(msg.function, 3)
        self.assertEquals(msg.control_addressing.resp_status, 0)

    def test_data_request_host(self):
        msg = '\x80\x00\x04\x01\x00\x43'
        msg = self.parse(msg)
        self.assertEquals(msg.origin, 0)
        self.assertEquals(msg.destination, 128)
        self.assertEquals(msg.function, 4)
        self.assertEquals(msg.data_request.seq, 67)

    def test_data_request_device(self):
        msg = '\x00\x80\x04\x0D\x00\x02\x00\x00\x00\x80\x3F\x03\x00\x00\xDC\x43\x01\x04'
        msg = self.parse(msg)
        self.assertEquals(msg.origin, 128)
        self.assertEquals(msg.destination, 0)
        self.assertEquals(msg.function, 4)
        self.assertEquals(len(msg.data_request.events), 2)
        self.assertEquals(msg.data_request.events[0].id, 0)
        self.assertEquals(msg.data_request.events[0].value, 1.0)
        self.assertEquals(msg.data_request.events[1].id, 3)
        self.assertEquals(msg.data_request.events[1].value, 440.0)
        self.assertEquals(msg.data_request.requests, [4])

    def test_control_unaddressing_host(self):
        msg = '\x80\x00\x05\x01\x00\x03'
        msg = self.parse(msg)
        self.assertEquals(msg.origin, 0)
        self.assertEquals(msg.destination, 128)
        self.assertEquals(msg.function, 5)
        self.assertEquals(msg.control_unaddressing.addressing_id, 3)

    def test_control_unaddressing_device(self):
        msg = '\x80\x00\x05\x00\x00'
        msg = self.parse(msg)
        self.assertEquals(msg.origin, 0)
        self.assertEquals(msg.destination, 128)
        self.assertEquals(msg.function, 5)


        
if __name__ == '__main__':
    unittest.main()
