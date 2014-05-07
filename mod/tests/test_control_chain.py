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
        return self.chain.parse('\xaa%s\x00' % msg)

    def test_connection_device(self):
        msg = '\x00\x00\x01\x08\x00my-dev\x00\x01'
        msg = self.parse(msg)
        self.assertEquals(msg.origin, 0)
        self.assertEquals(msg.destination, 0)
        self.assertEquals(msg.function, 1)
        self.assertEquals(msg.connection.name, 'my-dev')
        self.assertEquals(msg.connection.channel, 1)

    def test_connection_host(self):
        msg = '\x80\x00\x01\x08\x00my-dev\x00\x01'
        msg = self.parse(msg)
        self.assertEquals(msg.origin, 0)
        self.assertEquals(msg.destination, 128)
        self.assertEquals(msg.function, 1)
        self.assertEquals(msg.connection.name, 'my-dev')
        self.assertEquals(msg.connection.channel, 1)

    def test_device_descriptor_host(self):
        msg = '\x80\x00\x02\x00\x00'
        msg = self.parse(msg)
        self.assertEquals(msg.origin, 0)
        self.assertEquals(msg.destination, 128)
        self.assertEquals(msg.function, 2)

    def test_device_descriptor_device(self):
        msg = '\x00\x80\x02\xe2\x00\x05\x01\x02knob\x00\x03\x01\x00\x02\x00\x03\x00\x01\x03\x10\x00\x20\x00\x40\x00foot\x00\x02\x04ON/OFF\x00\x0cPULSE\x00\x01\x00'
        msg = self.parse(msg)
        self.assertEquals(msg.origin, 128)
        self.assertEquals(msg.destination, 0)
        self.assertEquals(msg.function, 2)
        self.assertEquals(msg.dev_desc.channels_count, 5)
        self.assertEquals(len(msg.dev_desc.actuator), 2)
        self.assertEquals(msg.dev_desc.actuator[0].name, 'knob')
        self.assertEquals(msg.dev_desc.actuator[0].steps, [16, 32, 64])
        self.assertEquals(len(msg.dev_desc.actuator[0].mask), 3)
        self.assertEquals(msg.dev_desc.actuator[0].mask[0].prop, 1)
        self.assertEquals(msg.dev_desc.actuator[0].mask[0].label, '')
        self.assertEquals(msg.dev_desc.actuator[0].mask[1].prop, 2)
        self.assertEquals(msg.dev_desc.actuator[0].mask[1].label, '')
        self.assertEquals(msg.dev_desc.actuator[0].mask[2].prop, 3)
        self.assertEquals(msg.dev_desc.actuator[0].mask[2].label, '')

    def test_control_addressing_host(self):
        msg = '\x80\x00\x03\x1C\x00\x01\x02\x01\x0CBYP\x00\x00\x00\x80\x3F\x00\x00\x00\x00\x00\x00\x80\x3F\x00\x00\x00\x00\x00\x00\x00\x00'
        msg = self.parse(msg)
        self.assertEquals(msg.origin, 0)
        self.assertEquals(msg.destination, 128)
        self.assertEquals(msg.function, 3)
        self.assertEquals(msg.control_addressing.channel, 1)
        self.assertEquals(msg.control_addressing.actuator_id, 2)
        self.assertEquals(msg.control_addressing.mask, 12)
        self.assertEquals(msg.control_addressing.label, 'BYP')
        self.assertEquals(msg.control_addressing.value, 1.0)
        self.assertEquals(msg.control_addressing.minimum, 0)
        self.assertEquals(msg.control_addressing.maximum, 1.0)
        self.assertEquals(msg.control_addressing.default, 0)
        self.assertEquals(msg.control_addressing.steps, 0)
        self.assertEquals(msg.control_addressing.scale_points, [])

    def test_control_addressing_device(self):
        msg = '\x00\x80\x03\x02\x00\x00\x00'
        msg = self.parse(msg)
        self.assertEquals(msg.origin, 128)
        self.assertEquals(msg.destination, 0)
        self.assertEquals(msg.function, 3)
        self.assertEquals(msg.control_addressing.resp_status, 0)

if __name__ == '__main__':
    unittest.main()
