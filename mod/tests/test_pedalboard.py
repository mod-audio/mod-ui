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


import unittest, os, shutil, json
from mod.pedalboard import binary_pedalboard, binary_banks
from mod import pedalboard
from mod import indexing
from mod import settings
from . import effects

class PedalboardTest(unittest.TestCase):

    def setUp(self):
        self.tearDown()
        os.mkdir('/tmp/pedalboards')
        os.mkdir('/tmp/effects')
        pedalboard.PEDALBOARD_DIR = '/tmp/pedalboards'
        pedalboard.PEDALBOARD_INDEX_PATH = '/tmp/pedalboards.index'
        pedalboard.EFFECT_DIR = '/tmp/effects'
        pedalboard.INDEX_PATH = '/tmp/effects.index'
        index = indexing.EffectIndex()
        for key, effect in effects.items():
            open('/tmp/effects/%s' % effect['_id'], 'w').write(json.dumps(effect))
            index.add(effect)
            
    def tearDown(self):
        for dirname in ('pedalboards', 'pedalboards.index', 'effects', 'effects.index'):
            try:
                shutil.rmtree('/tmp/%s' % dirname)
            except:
                pass

    def test_simplest_pedalboard_binary(self):
        pedalboard = {
            "_id": "5092a1c9a9a0190f985ced66", 
            "connections": [
                {
                    "destination": "system:playback_1", 
                    "origin": "effect_3:out"
                    }, 
                {
                    "destination": "effect_3:in", 
                    "origin": "system:capture_1"
                    }
                ], 
            "effects": [
                {
                    "bypass": 1, 
                    "bypass_label": "efeito3",
                    "id": "effect_3", 
                    "instanceId": 3, 
                    "parameters": [
                        {
                            "addressing": {
                                "actuator": [ -1 ],
                                "label": "Drive"
                                }, 
                            "symbol": "drive", 
                            "value": 0
                            }, 
                        {
                            "addressing": {
                                "actuator": [ -1 ],
                                "label": "DC Offset"
                                }, 
                            "symbol": "dcoffset", 
                            "value": 0
                            }, 
                        {
                            "addressing": {
                                "actuator": [ -1 ],
                                "label": "Tube Phase"
                                }, 
                            "symbol": "phase", 
                            "value": 0
                            }, 
                        {
                            "addressing": {
                                "actuator": [ -1 ],
                                "label": "Mix"
                                }, 
                            "symbol": "mix", 
                            "value": 75
                            }
                        ], 
                    "positionX": 406, 
                    "positionY": 92, 
                    "url": "http://portalmod.com/plugins/invada/tube/mono", 
                    }
                ], 
            "height": 640, 
            "inputs": [
                {
                    "effect": "effect_3", 
                    "id": "effect_3:in", 
                    "name": "In", 
                    "number": 0, 
                    "portId": 8
                    }
                ], 
            "metadata": {
                "description": "", 
                "musics": [], 
                "tags": [], 
                "title": "One Single Effect"
                }, 
            "outputs": [
                {
                    "effect": "effect_3", 
                    "id": "effect_3:out", 
                    "name": "Out", 
                    "number": 0, 
                    "portId": 9
                    }
                ], 
            "width": 1194
            }

        binary = binary_pedalboard(pedalboard)

        # No controls addressed, so it's just the id, zero-terminated name and zero controls
        self.assertEquals(binary, 
                          '5092a1c9a9a0190f985ced66\x00' + # uid
                          'One Single Effect' + '\x00' * 8 + # name
                          '\x01' + # effects count
                          '\x03' + # instance id
                          '\x01' + # bypassed
                          '\xff\xff' + # bypass not addressed
                          'efeito3' + '\x00' * 18 +# bypass label
                          '\x00' # controls count
                          )
        
    @unittest.skip("missing plugin")
    def test_pedalboard_with_two_addressings_binary(self):
        pedalboard = {
            "_id": "5092a1c9a9a0190f985ced66", 
            "connections": [
                {
                    "destination": "system:playback_1", 
                    "origin": "effect_3:out"
                    }, 
                {
                    "destination": "effect_3:in", 
                    "origin": "system:capture_1"
                    }
                ], 
            "effects": [
                {
                    "bypass": 0, 
                    "bypass_label": "efeito3",
                    "id": "effect_3", 
                    "instanceId": 4, 
                    "parameters": [
                        {
                            "addressing": {
                                "actuator": [ 0, 0, 2, 0 ],
                                "addressing_type": "range",
                                "label": "Drive", 
                                "maximum": 18, 
                                "minimum": 0,
                                "steps": 18,
                                "options": [], 
                                "type": 0, 
                                "value": 3
                                }, 
                            "symbol": "drive", 
                            "value": 0
                            }, 
                        {
                            "addressing": {
                                "actuator": [ 0, 0, 2, 1 ],
                                "addressing_type": "range",
                                "label": "DC Offset", 
                                "steps": 10,
                                "maximum": 1, 
                                "minimum": -1, 
                                "options": [], 
                                "type": 0, 
                                "value": 2
                                }, 
                            "symbol": "dcoffset", 
                            "value": 0
                            }, 
                        {
                            "addressing": {
                                "actuator": [ -1 ],
                                "label": "Tube Phase"
                                }, 
                            "symbol": "phase", 
                            "value": 2
                            }, 
                        {
                            "addressing": {
                                "actuator": [ -1 ],
                                "label": "Mix"
                                }, 
                            "symbol": "mix", 
                            "value": 75
                            }
                        ], 
                    "positionX": 406, 
                    "positionY": 92, 
                    "url": "http://portalmod.com/plugins/invada/tube/mono", 
                    }
                ], 
            "height": 640, 
            "inputs": [
                {
                    "effect": "effect_3", 
                    "id": "effect_3:in", 
                    "name": "In", 
                    "number": 0, 
                    "portId": 8
                    }
                ], 
            "metadata": {
                "description": "", 
                "musics": [], 
                "tags": [], 
                "title": "One Single Effect with two addressings"
                }, 
            "outputs": [
                {
                    "effect": "effect_3", 
                    "id": "effect_3:out", 
                    "name": "Out", 
                    "number": 0, 
                    "portId": 9
                    }
                ], 
            "width": 1194
            }

        binary = binary_pedalboard(pedalboard)
        expected = ''.join([ '5092a1c9a9a0190f985ced66\x00', # uid
                             'One Single Effect with t' + '\x00', # name truncated on 24
                             '\x01', # effects count
                             '\x04', # instance id
                             '\x00', # not bypassed
                             '\xff\xff', # bypass not addressed
                             'efeito3' + '\x00' * 18, # bypass label
                             '\x02', # controls count

                             '\x00\x00', # hardware
                             '\x02', # actuator type
                             '\x00', # actuator id
                             'Drive' + '\x00' * 20, #label
                             '\x12', # 18 steps
                             '\x04', # instance id
                             'drive' + '\x00' * 20, #symbol
                             '\x00\x00@@', # value 3
                             '\x00' * 4, # minimum 0
                             '\x00\x00\x90A', # maximum 18
                             '\x00', # linear
                             'none\x00\x00\x00\x00\x00', # unit
                             '\x00', # scalepoints

                             '\x00\x00', # hardware
                             '\x02', # actuator type
                             '\x01', # actuator id
                             'DC Offset' + '\x00' * 16, #label
                             '\n', # 10 steps
                             '\x04', # instance id
                             'dcoffset' + '\x00' * 17, #symbol
                             '\x00\x00\x00@', # value 2
                             '\x00\x00\x80\xbf', # minimum -1
                             '\x00\x00\x80?', # maximum 1
                             '\x00', # linear
                             'none\x00\x00\x00\x00\x00', # unit
                             '\x00', # scalepoints
                             ])

        self.assertEquals(binary, expected)


    def test_binary_of_logarithmic_addressing(self):
        pedalboard = {
            "_id": "5092a1c9a9a0190f985ced66", 
            "connections": [
                {
                    "destination": "system:playback_1", 
                    "origin": "effect_2:out"
                    }, 
                {
                    "destination": "effect_2:in", 
                    "origin": "system:capture_1"
                    }
                ], 
            "effects": [
                {
                    "bypass": 1, 
                    "bypass_label": "efeito2",
                    "id": "effect_2", 
                    "instanceId": 2, 
                    "parameters": [
                        {
                            "addressing": {
                                "actuator": [ -1 ], 
                                "label": "RMS"
                                }, 
                            "symbol": "rms", 
                            "value": 0.5
                            }, 
                        {
                            "addressing": {
                                "actuator": [ 0, 0, 2, 3],
                                "addressing_type": "range",
                                "label": "Ataque", 
                                "maximum": 0.75, 
                                "minimum": 1e-05, 
                                "options": [], 
                                "type": 0, 
                                "value": 0.015
                                }, 
                            "symbol": "attack", 
                            "value": 0.015
                            }, 
                        {
                            "addressing": {
                                "actuator": [ -1 ],
                                "label": "Soltar", 
                                }, 
                            "symbol": "rms", 
                            "value": 0.05
                            }, 
                        {
                            "addressing": {
                                "actuator": [ -1 ], 
                                "label": "Threshold"
                                }, 
                            "symbol": "threshold", 
                            "value": -27
                            }, 
                        {
                            "addressing": {
                                "actuator": [ -1 ], 
                                "label": "Ratio"
                                }, 
                            "symbol": "ratio", 
                            "value": 15
                            }, 
                        {
                            "addressing": {
                                "actuator": [ -1 ], 
                                "label": "Gain"
                                }, 
                            "symbol": "gain", 
                            "value": 14
                            }, 
                        {
                            "addressing": {
                                "actuator": [ -1 ], 
                                "label": "Soft Clip"
                                }, 
                            "symbol": "noClip", 
                            "value": 1
                            }
                        ], 
                    "positionX": 393, 
                    "positionY": 75, 
                    "url": "http://portalmod.com/plugins/invada/compressor/mono", 
                    }
                ], 
            "height": 593, 
            "inputs": [
                {
                    "effect": "effect_2", 
                    "id": "effect_2:in", 
                    "name": "In", 
                    "number": 0, 
                    "portId": 12
                    }
                ], 
            "metadata": {
                "description": "", 
                "musics": [], 
                "tags": [], 
                "title": "Test Logarithmic Binary"
                }, 
            "outputs": [
                {
                    "effect": "effect_2", 
                    "id": "effect_2:out", 
                    "name": "Out", 
                    "number": 0, 
                    "portId": 13
                    }
                ], 
            "width": 1194
            }

        binary = binary_pedalboard(pedalboard)
        expected = ''.join([ '5092a1c9a9a0190f985ced66\x00', # uid
                             'Test Logarithmic Binary' + '\x00\x00', # name 
                             '\x01', # effects count
                             '\x02', # instance id
                             '\x01', # bypassed
                             '\xff\xff', # bypass not addressed
                             'efeito2' + '\x00' * 18, # bypass label
                             '\x01', # controls count

                             '\x00\x00', # hardware
                             '\x02', # actuator type
                             '\x03', # actuator id
                             'Ataque' + '\x00' * 19, #label
                             '\x14', # 20 steps
                             '\x02', # instance id
                             'attack' + '\x00' * 19, #symbol
                             '\x8f\xc2u<', # value 0.015
                             "\xac\xc5'7", # minimum 1e-05
                             '\x00\x00@?', # maximum 0.75
                             '\x01', # logarithmic
                             'none\x00\x00\x00\x00\x00', # unit
                             '\x00', # scalepoints
                             ])

        self.assertEquals(binary, expected)

    def test_footswitch_addressing(self):
        pedalboard = {
            "_id": "5092a1c9a9a0190f985ced66", 
            "connections": [
                {
                    "destination": "system:playback_1", 
                    "origin": "effect_2:out"
                    }, 
                {
                    "destination": "effect_2:in", 
                    "origin": "system:capture_1"
                    }
                ], 
            "effects": [
                {
                    "bypass": 1, 
                    "bypass_label": "efeito2",
                    "id": "effect_2", 
                    "instanceId": 2, 
                    "parameters": [
                        {
                            "addressing": {
                                "actuator": [ -1 ], 
                                "label": "RMS"
                                }, 
                            "symbol": "rms", 
                            "value": 0.5
                            }, 
                        {
                            "addressing": {
                                "actuator": [ -1 ],
                                "label": "Ataque", 
                                }, 
                            "symbol": "attack", 
                            "value": 0.015
                            }, 
                        {
                            "addressing": {
                                "actuator": [ -1 ],
                                "label": "Soltar", 
                                }, 
                            "symbol": "rms", 
                            "value": 0.05
                            }, 
                        {
                            "addressing": {
                                "actuator": [ -1 ], 
                                "label": "Threshold"
                                }, 
                            "symbol": "threshold", 
                            "value": -27
                            }, 
                        {
                            "addressing": {
                                "actuator": [ -1 ], 
                                "label": "Ratio"
                                }, 
                            "symbol": "ratio", 
                            "value": 15
                            }, 
                        {
                            "addressing": {
                                "actuator": [ -1 ], 
                                "label": "Gain"
                                }, 
                            "symbol": "gain", 
                            "value": 14
                            }, 
                        {
                            "addressing": {
                                "actuator": [ 0, 0, 1, 2 ],
                                "label": "Soft Clip",
                                "addressing_type": "range",
                                "minimum": 0,
                                "maximum": 1,
                                "value": 1,
                                }, 
                            "symbol": "noClip", 
                            "value": 1
                            }
                        ], 
                    "positionX": 393, 
                    "positionY": 75, 
                    "url": "http://portalmod.com/plugins/invada/compressor/mono", 
                    }
                ], 
            "height": 593, 
            "inputs": [
                {
                    "effect": "effect_2", 
                    "id": "effect_2:in", 
                    "name": "In", 
                    "number": 0, 
                    "portId": 12
                    }
                ], 
            "metadata": {
                "description": "", 
                "musics": [], 
                "tags": [], 
                "title": "Test Toggled Binary"
                }, 
            "outputs": [
                {
                    "effect": "effect_2", 
                    "id": "effect_2:out", 
                    "name": "Out", 
                    "number": 0, 
                    "portId": 13
                    }
                ], 
            "width": 1194
            }

        binary = binary_pedalboard(pedalboard)
        expected = ''.join([ '5092a1c9a9a0190f985ced66\x00', # uid
                             'Test Toggled Binary' + '\x00' * 6, # name 
                             '\x01', # effects count
                             '\x02', # instance id
                             '\x01', # bypassed
                             '\xff\xff', # bypass not addressed
                             'efeito2' + '\x00' * 18, # bypass label
                             '\x01', # controls count

                             '\x00\x00', # hardware
                             '\x01', # actuator type
                             '\x02', # actuator id
                             'Soft Clip' + '\x00' * 16, #label
                             '\x02', # 2 steps
                             '\x02', # instance id
                             'noClip' + '\x00' * 19, #symbol
                             '\x00\x00\x80?', # value 1
                             "\x00\x00\x00\x00", # minimum 0
                             '\x00\x00\x80?', # maximum 1
                             '\x03', # toggled
                             'none\x00\x00\x00\x00\x00', # unit
                             '\x00', # scalepoints
                             ])

        self.assertEquals(binary, expected)

    def test_enumeration_options(self):
        pedalboard = {
            "_id": "5092a1c9a9a0190f985ced66", 
            "connections": [
                {
                    "destination": "system:playback_1", 
                    "origin": "effect_2:out"
                    }, 
                {
                    "destination": "effect_2:in", 
                    "origin": "system:capture_1"
                    }
                ], 
            "effects": [
                {
                    "bypass": 0, 
                    "id": "effect_2", 
                    "bypass_label": "efeito2",
                    "instanceId": 2, 
                    "parameters": [
                        {
                            "addressing": {
                                "actuator": [ 0, 0, 2, 3 ], 
                                "addressing_type": "select",
                                "label": "Model",
                                "options": [ [ 2, 'Second Unmatched on-axis' ],
                                             [ 6, 'Sixth Mesa' ],
                                             [ 4, 'Fourth Little Wing 68' ],
                                             ],
                                "value": 4,
                                }, 
                            "symbol": "model", 
                            "value": 4
                            }, 
                        {
                            "addressing": {
                                "actuator": [ -1 ],
                                }, 
                            "symbol": "gain", 
                            "value": 12
                            }, 

                        ], 
                    "positionX": 393, 
                    "positionY": 75, 
                    "url": "http://portalmod.com/plugins/caps/CabinetI", 
                    }
                ], 
            "height": 593, 
            "inputs": [
                {
                    "effect": "effect_2", 
                    "id": "effect_2:in", 
                    "name": "In", 
                    "number": 0, 
                    "portId": 12
                    }
                ], 
            "metadata": {
                "description": "", 
                "musics": [], 
                "tags": [], 
                "title": "Test Enumeration Binary"
                }, 
            "outputs": [
                {
                    "effect": "effect_2", 
                    "id": "effect_2:out", 
                    "name": "Out", 
                    "number": 0, 
                    "portId": 13
                    }
                ], 
            "width": 1194
            }

        binary = binary_pedalboard(pedalboard)
        expected = ''.join([ '5092a1c9a9a0190f985ced66\x00', # uid
                             'Test Enumeration Binary' + '\x00' * 2, # name 
                             '\x01', # effects count
                             '\x02', # instance id
                             '\x00', # not bypassed
                             '\xff\xff', # bypass not addressed
                             'efeito2' + '\x00' * 18, # bypass label
                             '\x01', # controls count

                             '\x00\x00', # hardware
                             '\x02', # actuator type
                             '\x03', # actuator id
                             'Model' + '\x00' * 20, #label
                             '\x03', # 3 steps
                             '\x02', # instance id
                             'model' + '\x00' * 20, #symbol
                             '\x00\x00\x80@', # value 4
                             "\x00\x00\x00@", # minimum 2
                             '\x00\x00\xc0@', # maximum 6
                             '\x02', # enumeration
                             'none\x00\x00\x00\x00\x00', # unit
                             '\x03', # 3 scalepoints
                             
                             'Second Unmatched on-axis' + '\x00',
                             '\x00\x00\x00@' # value 2
                             'Sixth Mesa' + '\x00' * 15,
                             '\x00\x00\xc0@', # value 6
                             'Fourth Little Wing 68' + '\x00' * 4,
                             '\x00\x00\x80@', # value 4
                             ])

        self.assertEquals(binary, expected)

    def test_all_enumeration_options_are_sent_by_default(self):
        pedalboard = {
            "_id": "5092a1c9a9a0190f985ced66", 
            "connections": [
                {
                    "destination": "system:playback_1", 
                    "origin": "effect_2:out"
                    }, 
                {
                    "destination": "effect_2:in", 
                    "origin": "system:capture_1"
                    }
                ], 
            "effects": [
                {
                    "bypass": 0, 
                    "bypass_label": "efeito2",
                    "id": "effect_2", 
                    "instanceId": 2, 
                    "parameters": [
                        {
                            "addressing": {
                                "actuator": [ 0, 0, 2, 3 ],
                                "addressing_type": "select",
                                "label": "Model",
                                "value": 4,
                                }, 
                            "symbol": "model", 
                            "value": 4
                            }, 
                        {
                            "addressing": {
                                "actuator": [ -1 ],
                                }, 
                            "symbol": "gain", 
                            "value": 12
                            }, 

                        ], 
                    "positionX": 393, 
                    "positionY": 75, 
                    "url": "http://portalmod.com/plugins/caps/CabinetI", 
                    }
                ], 
            "height": 593, 
            "inputs": [
                {
                    "effect": "effect_2", 
                    "id": "effect_2:in", 
                    "name": "In", 
                    "number": 0, 
                    "portId": 12
                    }
                ], 
            "metadata": {
                "description": "", 
                "musics": [], 
                "tags": [], 
                "title": "Test Enumeration Binary"
                }, 
            "outputs": [
                {
                    "effect": "effect_2", 
                    "id": "effect_2:out", 
                    "name": "Out", 
                    "number": 0, 
                    "portId": 13
                    }
                ], 
            "width": 1194
            }

        binary = binary_pedalboard(pedalboard)
        expected = ''.join([ '5092a1c9a9a0190f985ced66\x00', # uid
                             'Test Enumeration Binary' + '\x00' * 2, # name 
                             '\x01', # effects count
                             '\x02', # instance id
                             '\x00', # not bypassed
                             '\xff\xff', # bypass not addressed
                             'efeito2' + '\x00' * 18, # bypass label
                             '\x01', # controls count

                             '\x00\x00', # hardware
                             '\x02', # actuator type
                             '\x03', # actuator id
                             'Model' + '\x00' * 20, #label
                             '\x07', # 7 steps
                             '\x02', # instance id
                             'model' + '\x00' * 20, #symbol
                             '\x00\x00\x80@', # value 4
                             "\x00\x00\x80?", # minimum 1
                             '\x00\x00\xe0@', # maximum 7
                             '\x02', # enumeration
                             'none\x00\x00\x00\x00\x00', # unit
                             '\x07', # 7 scalepoints
                             
                             'Unmatched off-axis' + '\x00' * 7,
                             '\x00\x00\x80?' # value 1
                             'Unmatched on-axis' + '\x00' * 8,
                             '\x00\x00\x00@' # value 2
                             'Supertramp' + '\x00' * 15,
                             '\x00\x00@@', # value 3
                             'Little Wing 68' + '\x00' * 11,
                             '\x00\x00\x80@', # value 4
                             'Martial' + '\x00' * 18,
                             '\x00\x00\xa0@', # value 5
                             'Mesa' + '\x00' * 21,
                             '\x00\x00\xc0@', # value 6
                             'Pro Jr' + '\x00' * 19,
                             '\x00\x00\xe0@', # value 7
                             ])

        self.assertEquals(binary, expected)

    def test_tap_tempo_is_properly_addressed(self):
        pedalboard = {
            "_id": "5092a1c9a9a0190f985ced66", 
            "connections": [
                {
                    "destination": "system:playback_1", 
                    "origin": "effect_2:out"
                    }, 
                {
                    "destination": "effect_2:in", 
                    "origin": "system:capture_1"
                    }
                ], 
            "effects": [
                {
                    "bypass": 0, 
                    "bypass_label": "efeito2",
                    "id": "effect_2", 
                    "instanceId": 2, 
                    "parameters": [
                        {
                            "addressing": {
                                "actuator": [ -1 ], 
                                "label": "RMS"
                                }, 
                            "symbol": "rms", 
                            "value": 0.5
                            }, 
                        {
                            "addressing": {
                                "actuator": [ 0, 0, 2, 1 ],
                                "label": "Ataque", 
                                "addressing_type": "tap_tempo",
                                "type_options": 4,
                                "maximum": 2,
                                "minimum": 0.2,
                                "type": 5,
                                "value": 1,
                                }, 
                            "symbol": "attack", 
                            "value": 1
                            }, 
                        {
                            "addressing": {
                                "actuator": [ -1 ],
                                "label": "Soltar", 
                                }, 
                            "symbol": "rms", 
                            "value": 0.05
                            }, 
                        {
                            "addressing": {
                                "actuator": [ -1 ], 
                                "label": "Threshold"
                                }, 
                            "symbol": "threshold", 
                            "value": -27
                            }, 
                        {
                            "addressing": {
                                "actuator": [ -1 ], 
                                "label": "Ratio"
                                }, 
                            "symbol": "ratio", 
                            "value": 15
                            }, 
                        {
                            "addressing": {
                                "actuator": [ -1 ], 
                                "label": "Gain"
                                }, 
                            "symbol": "gain", 
                            "value": 14
                            }, 
                        {
                            "addressing": {
                                "actuator": [ -1 ],
                                "label": "Soft Clip",
                                }, 
                            "symbol": "noClip", 
                            "value": 1
                            }
                        ], 
                    "positionX": 393, 
                    "positionY": 75, 
                    "url": "http://portalmod.com/plugins/invada/compressor/mono", 
                    }
                ], 
            "height": 593, 
            "inputs": [
                {
                    "effect": "effect_2", 
                    "id": "effect_2:in", 
                    "name": "In", 
                    "number": 0, 
                    "portId": 12
                    }
                ], 
            "metadata": {
                "description": "", 
                "musics": [], 
                "tags": [], 
                "title": "Test TapTempo Binary"
                }, 
            "outputs": [
                {
                    "effect": "effect_2", 
                    "id": "effect_2:out", 
                    "name": "Out", 
                    "number": 0, 
                    "portId": 13
                    }
                ], 
            "width": 1194
            }

        binary = binary_pedalboard(pedalboard)
        expected = ''.join([ '5092a1c9a9a0190f985ced66\x00', # uid
                             'Test TapTempo Binary' + '\x00' * 5, # name 
                             '\x01', # effects count
                             '\x02', # instance id
                             '\x00', # not bypassed
                             '\xff\xff', # bypass not addressed
                             'efeito2' + '\x00' * 18, # bypass label
                             '\x01', # controls count

                             '\x00\x00', # hardware
                             '\x02', # actuator type
                             '\x01', # actuator id
                             'Ataque' + '\x00' * 19, #label
                             '\x00', # 2 steps
                             '\x02', # instance id
                             'attack' + '\x00' * 19, #symbol
                             '\x00\x00\x80?', # value 1
                             "\xcd\xccL>", # minimum 0.2
                             '\x00\x00\x00@', # maximum 2
                             '\x05', # tap tempo
                             'none\x00\x00\x00\x00\x00', # unit
                             '\x00', # scalepoints
                             ])

        self.assertEquals(binary, expected)

    def test_unicode_caracter_does_not_break_binary(self):
        pedalboard = {
            "_id": "5092a1c9a9a0190f985ced66", 
            "connections": [
                {
                    "destination": "system:playback_1", 
                    "origin": "effect_3:out"
                    }, 
                {
                    "destination": "effect_3:in", 
                    "origin": "system:capture_1"
                    }
                ], 
            "effects": [
                {
                    "bypass": 1, 
                    "id": "effect_3", 
                    "bypass_label": "efeito2",
                    "instanceId": 3, 
                    "parameters": [
                        {
                            "addressing": {
                                "actuator": [ -1 ],
                                "label": "Drive"
                                }, 
                            "symbol": "drive", 
                            "value": 0
                            }, 
                        {
                            "addressing": {
                                "actuator": [ -1 ],
                                "label": "DC Offset"
                                }, 
                            "symbol": "dcoffset", 
                            "value": 0
                            }, 
                        {
                            "addressing": {
                                "actuator": [ -1 ],
                                "label": "Tube Phase"
                                }, 
                            "symbol": "phase", 
                            "value": 0
                            }, 
                        {
                            "addressing": {
                                "actuator": [ -1 ],
                                "label": "Mix"
                                }, 
                            "symbol": "mix", 
                            "value": 75
                            }
                        ], 
                    "positionX": 406, 
                    "positionY": 92, 
                    "url": "http://portalmod.com/plugins/invada/tube/mono", 
                    }
                ], 
            "height": 640, 
            "inputs": [
                {
                    "effect": "effect_3", 
                    "id": "effect_3:in", 
                    "name": "In", 
                    "number": 0, 
                    "portId": 8
                    }
                ], 
            "metadata": {
                "description": "", 
                "musics": [], 
                "tags": [], 
                "title": u"Oné Wëiŕd Effeçtº",
                }, 
            "outputs": [
                {
                    "effect": "effect_3", 
                    "id": "effect_3:out", 
                    "name": "Out", 
                    "number": 0, 
                    "portId": 9
                    }
                ], 
            "width": 1194
            }

        binary = binary_pedalboard(pedalboard)

        expected = ''.join([ '5092a1c9a9a0190f985ced66\x00', # uid
                             'On? W?i?d Effe?t?' + '\x00' * 8, #name
                             '\x01', # effects count
                             '\x03', # instance id
                             '\x01', # bypassed
                             '\xff\xff', # bypass not addressed
                             'efeito2' + '\x00' * 18, # bypass label
                             '\x00', # controls count
                             ])

        self.assertEquals(binary, expected)

class BinaryBankTest(unittest.TestCase):
        
    def test_one_empty_bank(self):
        banks = [
            { 'title': 'um',
              'pedalboards': [],
              }
            ]
            
        binary = binary_banks(banks)
        self.assertEquals(binary, '\x01um' + '\x00' * 24)

    def test_one_bank_two_pedalboards(self):
        banks = [
            { 'title': 'um',
              'pedalboards': [
                    { 'id': '1' * 24,
                      'title': 'pedal um',
                      },
                    { 'id': '2' * 24,
                      'title': 'pedal dois',
                      }
                    ],
              }
            ]

        binary = binary_banks(banks)
        self.assertEquals(binary, '\x01um' + '\x00' * 23 + '\x02' + '1' * 24 + '\x00' + '2' * 24 + '\x00')

    def test_two_banks(self):
        banks = [
            { 'title': 'um',
              'pedalboards': [
                    { 'id': '1' * 24,
                      'title': 'pedal um',
                      },
                    { 'id': '2' * 24,
                      'title': 'pedal dois',
                      }
                    ],
              },
            { 'title': 'dois',
              'pedalboards': [
                    { 'id': '3' * 24,
                      'title': 'pedal um',
                      },
                    { 'id': '4' * 24,
                      'title': 'pedal dois',
                      },
                    { 'id': '5' * 24,
                      'title': 'pedal tres',
                      }
                    ],
              }
            ]
            
        binary = binary_banks(banks)
        self.assertEquals(binary, 
                          '\x02' +
                          'um' + '\x00' * 23 + '\x02' +
                          '1' * 24 + '\x00' +
                          '2' * 24 + '\x00' +
                          'dois' + '\x00' * 21 + '\x03' +
                          '3' * 24 + '\x00' +
                          '4' * 24 + '\x00' +
                          '5' * 24 + '\x00')

