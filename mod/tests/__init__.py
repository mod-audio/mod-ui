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

effects = {
    'compressor': {
        "_id": u"50881b691a62ee4e0719a4ba", 
        "binary": u"compressor.so", 
        "category": [
            "Dynamics > Compressor"
            ], 
        "developer": {
            "homepage": u"https://launchpad.net/invada-studio", 
            "mbox": u"fraser@arkhostings.com", 
            "name": u"Fraser Stuart"
            }, 
        "instanceId": 2, 
        "license": u"gpl", 
        "maintainer": {
            "homepage": u"http://www.invadarecords.com/Downloads.php?ID=00000264", 
            "mbox": u"fraser@arkhostings.com", 
            "name": u"Invada"
            }, 
        "microVersion": 1, 
        "minorVersion": 0, 
        "name": u"Invada Compressor (mono)", 
        "optionalFeature": u"hardRtCapable", 
        "package": u"mod-plugins-invada-compressor.lv2", 
        "package_id": u"50881b681a62ee4e0719a4b9", 
        "ports": {
            "audio": {
                "input": [
                    {
                        "index": 12, 
                        "name": u"In", 
                        "symbol": u"in", 
                        "types": [
                            "InputPort", 
                            "AudioPort"
                            ]
                        }
                    ], 
                "output": [
                    {
                        "index": 13, 
                        "name": u"Out", 
                        "symbol": u"out", 
                        "types": [
                            "OutputPort", 
                            "AudioPort"
                            ]
                        }
                    ]
                }, 
            "control": {
                "input": [
                    {
                        "default": 0.0, 
                        "index": 0, 
                        "maximum": 1.0, 
                        "minimum": 0.0, 
                        "name": u"Bypass", 
                        "symbol": u"bypass", 
                        "toggled": True, 
                        "types": [
                            "ControlPort", 
                            "InputPort"
                            ]
                        }, 
                    {
                        "default": 0.5, 
                        "index": 1, 
                        "maximum": 1.0, 
                        "minimum": 0.0, 
                        "name": u"RMS", 
                        "symbol": u"rms", 
                        "types": [
                            "ControlPort", 
                            "InputPort"
                            ]
                        }, 
                    {
                        "default": 0.015, 
                        "index": 2, 
                        "logarithmic": True, 
                        "maximum": 0.75, 
                        "minimum": 1e-05, 
                        "name": u"Attack", 
                        "symbol": u"attack", 
                        "types": [
                            "ControlPort", 
                            "InputPort"
                            ], 
                        "unit": {
                            "name": u"second", 
                            "render": u"%f s", 
                            "symbol": u"s"
                            }
                        }, 
                    {
                        "default": 0.05, 
                        "index": 3, 
                        "logarithmic": True, 
                        "maximum": 5.0, 
                        "minimum": 0.001, 
                        "name": u"Release", 
                        "symbol": u"release", 
                        "types": [
                            "ControlPort", 
                            "InputPort"
                            ], 
                        "unit": {
                            "name": u"second", 
                            "render": u"%f s", 
                            "symbol": u"s"
                            }
                        }, 
                    {
                        "default": -27, 
                        "index": 4, 
                        "maximum": 0.0, 
                        "minimum": -36.0, 
                        "name": u"Threshold", 
                        "symbol": u"threshold", 
                        "types": [
                            "ControlPort", 
                            "InputPort"
                            ], 
                        "unit": {
                            "name": u"decibel", 
                            "render": u"%f dB", 
                            "symbol": u"dB"
                            }
                        }, 
                    {
                        "default": 15, 
                        "index": 5, 
                        "maximum": 20.0, 
                        "minimum": 1.0, 
                        "name": u"Ratio", 
                        "symbol": u"ratio", 
                        "types": [
                            "ControlPort", 
                            "InputPort"
                            ]
                        }, 
                    {
                        "default": 14, 
                        "index": 6, 
                        "maximum": 36.0, 
                        "minimum": -6.0, 
                        "name": u"Gain", 
                        "symbol": u"gain", 
                        "types": [
                            "ControlPort", 
                            "InputPort"
                            ], 
                        "unit": {
                            "name": u"decibel", 
                            "render": u"%f dB", 
                            "symbol": u"dB"
                            }
                        }, 
                    {
                        "default": 1.0, 
                        "index": 7, 
                        "maximum": 1.0, 
                        "minimum": 0.0, 
                        "name": u"Soft Clip", 
                        "symbol": u"noClip", 
                        "toggled": True, 
                        "types": [
                            "ControlPort", 
                            "InputPort"
                            ]
                        }
                    ], 
                "output": [
                    {
                        "default": 0.0, 
                        "index": 8, 
                        "maximum": 0.0, 
                        "minimum": -36.0, 
                        "name": u"Gain Reduction", 
                        "symbol": u"grmeter", 
                        "types": [
                            "OutputPort", 
                            "ControlPort"
                            ], 
                        "unit": {
                            "name": u"decibel", 
                            "render": u"%f dB", 
                            "symbol": u"dB"
                            }
                        }, 
                    {
                        "default": 0.0, 
                        "index": 9, 
                        "maximum": 10.0, 
                        "minimum": 0.0, 
                        "name": u"Drive", 
                        "symbol": u"lampDrive", 
                        "types": [
                            "OutputPort", 
                            "ControlPort"
                            ]
                        }, 
                    {
                        "default": -60.0, 
                        "index": 10, 
                        "maximum": 6.0, 
                        "minimum": -60.0, 
                        "name": u"In", 
                        "symbol": u"meterIn", 
                        "types": [
                            "OutputPort", 
                            "ControlPort"
                            ], 
                        "unit": {
                            "name": u"decibel", 
                            "render": u"%f dB", 
                            "symbol": u"dB"
                            }
                        }, 
                    {
                        "default": -60.0, 
                        "index": 11, 
                        "maximum": 6.0, 
                        "minimum": -60.0, 
                        "name": u"Out", 
                        "symbol": u"meterOut", 
                        "types": [
                            "OutputPort", 
                            "ControlPort"
                            ], 
                        "unit": {
                            "name": u"decibel", 
                            "render": u"%f dB", 
                            "symbol": u"dB"
                            }
                        }
                    ]
                }
            }, 
        "replaces": u"urn:ladspa:3308", 
        "score": 7, 
        "stability": u"testing", 
        "ui": u"http://invadarecords.com/plugins/lv2/compressor/gui", 
        "url": u"http://portalmod.com/plugins/invada/compressor/mono", 
        "version": u"0.1"
        },
    'tube': {
        "_id": "50dde90a11c2604552135e78", 
        "binary": "tube.so", 
        "brand": u"invada", 
        "bypassLedPosition": "118-83", 
        "category": [
            "Distortion"
            ], 
        "connectionOptional": False, 
        "developer": {
            "connectionOptional": False, 
            "enumeration": False, 
            "hasStrictBounds": False, 
            "homepage": "https://launchpad.net/invada-studio", 
            "integer": False, 
            "logarithmic": False, 
            "mbox": "fraser@arkhostings.com", 
            "name": "Fraser Stuart", 
            "notAutomatic": False, 
            "outputGain": False, 
            "reportsBpm": False, 
            "reportsLatency": False, 
            "sampleRate": False, 
            "toggled": False, 
            "trigger": False
            }, 
        "enumeration": False, 
        "hasStrictBounds": False, 
        "instanceId": 0, 
        "integer": False, 
        "license": "gpl", 
        "logarithmic": False, 
        "maintainer": {
            "connectionOptional": False, 
            "enumeration": False, 
            "hasStrictBounds": False, 
            "homepage": "http://portalmod.com", 
            "integer": False, 
            "logarithmic": False, 
            "mbox": "devel@portalmod.com", 
            "name": "MOD Team", 
            "notAutomatic": False, 
            "outputGain": False, 
            "reportsBpm": False, 
            "reportsLatency": False, 
            "sampleRate": False, 
            "toggled": False, 
            "trigger": False
            }, 
        "microVersion": 6, 
        "minorVersion": 0, 
        "name": u"Invada Tube Distortion (mono)", 
        "notAutomatic": False, 
        "optionalFeature": "hardRtCapable", 
        "outputGain": False, 
        "package": u"invada-tube.lv2", 
        "package_id": "50dde90a11c2604552135e76", 
        "pedalColor": "orange", 
        "pedalLabel": u"Tube Distortion", 
        "pedalModel": "japanese", 
        "ports": {
            "audio": {
                "input": [
                    {
                        "connectionOptional": False, 
                        "enumeration": False, 
                        "hasStrictBounds": False, 
                        "index": 8, 
                        "integer": False, 
                        "logarithmic": False, 
                        "name": "In", 
                        "notAutomatic": False, 
                        "outputGain": False, 
                        "reportsBpm": False, 
                        "reportsLatency": False, 
                        "sampleRate": False, 
                        "symbol": "in", 
                        "toggled": False, 
                        "trigger": False, 
                        "types": [
                            "InputPort", 
                            "AudioPort"
                            ]
                        }
                    ], 
                "output": [
                    {
                        "connectionOptional": False, 
                        "enumeration": False, 
                        "hasStrictBounds": False, 
                        "index": 9, 
                        "integer": False, 
                        "logarithmic": False, 
                        "name": "Out", 
                        "notAutomatic": False, 
                        "outputGain": False, 
                        "reportsBpm": False, 
                        "reportsLatency": False, 
                        "sampleRate": False, 
                        "symbol": "out", 
                        "toggled": False, 
                        "trigger": False, 
                        "types": [
                            "OutputPort", 
                            "AudioPort"
                            ]
                        }
                    ]
                }, 
            "control": {
                "input": [
                    {
                        "connectionOptional": False, 
                        "default": 0.0, 
                        "enumeration": False, 
                        "hasStrictBounds": False, 
                        "index": 0, 
                        "integer": False, 
                        "logarithmic": False, 
                        "maximum": 1.0, 
                        "minimum": 0.0, 
                        "name": "Bypass", 
                        "notAutomatic": False, 
                        "outputGain": False, 
                        "reportsBpm": False, 
                        "reportsLatency": False, 
                        "sampleRate": False, 
                        "symbol": "bypass", 
                        "toggled": False, 
                        "trigger": False, 
                        "types": [
                            "InputPort", 
                            "ControlPort"
                            ]
                        }, 
                    {
                        "connectionOptional": False, 
                        "default": 0.0, 
                        "enumeration": False, 
                        "hasStrictBounds": False, 
                        "index": 1, 
                        "integer": False, 
                        "logarithmic": False, 
                        "maximum": 18.0, 
                        "minimum": 0.0, 
                        "name": "Drive", 
                        "notAutomatic": False, 
                        "outputGain": False, 
                        "pedalButton": "1-0", 
                        "reportsBpm": False, 
                        "reportsLatency": False, 
                        "sampleRate": False, 
                        "symbol": "drive", 
                        "toggled": False, 
                        "trigger": False, 
                        "types": [
                            "InputPort", 
                            "ControlPort"
                            ], 
                        "unit": {
                            "name": "decibel", 
                            "render": "%f dB", 
                            "symbol": "dB"
                            }
                        }, 
                    {
                        "connectionOptional": False, 
                        "default": 0.0, 
                        "enumeration": False, 
                        "hasStrictBounds": False, 
                        "index": 2, 
                        "integer": False, 
                        "logarithmic": False, 
                        "maximum": 1.0, 
                        "minimum": -1.0, 
                        "name": "DC Offset", 
                        "notAutomatic": False, 
                        "outputGain": False, 
                        "pedalButton": "1-2", 
                        "reportsBpm": False, 
                        "reportsLatency": False, 
                        "sampleRate": False, 
                        "symbol": "dcoffset", 
                        "toggled": False, 
                        "trigger": False, 
                        "types": [
                            "InputPort", 
                            "ControlPort"
                            ]
                        }, 
                    {
                        "connectionOptional": False, 
                        "default": 0.0, 
                        "enumeration": False, 
                        "hasStrictBounds": False, 
                        "iconLabel": "Phase", 
                        "index": 3, 
                        "integer": False, 
                        "logarithmic": False, 
                        "maximum": 1.0, 
                        "minimum": 0.0, 
                        "name": "Tube Phase", 
                        "notAutomatic": False, 
                        "outputGain": False, 
                        "pedalButton": "1-4", 
                        "reportsBpm": False, 
                        "reportsLatency": False, 
                        "sampleRate": False, 
                        "symbol": "phase", 
                        "toggled": True, 
                        "trigger": False, 
                        "types": [
                            "InputPort", 
                            "ControlPort"
                            ]
                        }, 
                    {
                        "connectionOptional": False, 
                        "default": 75.0, 
                        "enumeration": False, 
                        "hasStrictBounds": False, 
                        "index": 4, 
                        "integer": False, 
                        "logarithmic": False, 
                        "maximum": 100.0, 
                        "minimum": 0.0, 
                        "name": "Mix", 
                        "notAutomatic": False, 
                        "outputGain": False, 
                        "pedalButton": "1-6", 
                        "reportsBpm": False, 
                        "reportsLatency": False, 
                        "sampleRate": False, 
                        "symbol": "mix", 
                        "toggled": False, 
                        "trigger": False, 
                        "types": [
                            "InputPort", 
                            "ControlPort"
                            ], 
                        "unit": {
                            "name": "percent", 
                            "render": "%f%%", 
                            "symbol": "%"
                            }
                        }
                    ], 
                "output": [
                    {
                        "connectionOptional": False, 
                        "default": 0.0, 
                        "enumeration": False, 
                        "hasStrictBounds": False, 
                        "index": 5, 
                        "integer": False, 
                        "logarithmic": False, 
                        "maximum": 10.0, 
                        "minimum": 0.0, 
                        "name": "Drive Lamp", 
                        "notAutomatic": False, 
                        "outputGain": False, 
                        "reportsBpm": False, 
                        "reportsLatency": False, 
                        "sampleRate": False, 
                        "symbol": "meterDrive", 
                        "toggled": False, 
                        "trigger": False, 
                        "types": [
                            "OutputPort", 
                            "ControlPort"
                            ]
                        }, 
                    {
                        "connectionOptional": False, 
                        "default": -60.0, 
                        "enumeration": False, 
                        "hasStrictBounds": False, 
                        "index": 6, 
                        "integer": False, 
                        "logarithmic": False, 
                        "maximum": 6.0, 
                        "minimum": -60.0, 
                        "name": "In", 
                        "notAutomatic": False, 
                        "outputGain": False, 
                        "reportsBpm": False, 
                        "reportsLatency": False, 
                        "sampleRate": False, 
                        "symbol": "meterIn", 
                        "toggled": False, 
                        "trigger": False, 
                        "types": [
                            "OutputPort", 
                            "ControlPort"
                            ], 
                        "unit": {
                            "name": "decibel", 
                            "render": "%f dB", 
                            "symbol": "dB"
                            }
                        }, 
                    {
                        "connectionOptional": False, 
                        "default": -60.0, 
                        "enumeration": False, 
                        "hasStrictBounds": False, 
                        "index": 7, 
                        "integer": False, 
                        "logarithmic": False, 
                        "maximum": 6.0, 
                        "minimum": -60.0, 
                        "name": "Out", 
                        "notAutomatic": False, 
                        "outputGain": False, 
                        "reportsBpm": False, 
                        "reportsLatency": False, 
                        "sampleRate": False, 
                        "symbol": "meterOut", 
                        "toggled": False, 
                        "trigger": False, 
                        "types": [
                            "OutputPort", 
                            "ControlPort"
                            ], 
                        "unit": {
                            "name": "decibel", 
                            "render": "%f dB", 
                            "symbol": "dB"
                            }
                        }
                    ]
                }
            }, 
        "replaces": "urn:ladspa:3306", 
        "reportsBpm": False, 
        "reportsLatency": False, 
        "sampleRate": False, 
        "score": 1, 
        "smallLabel": "TubeDist", 
        "stability": u"stable", 
        "toggled": False, 
        "trigger": False, 
        "url": u"http://portalmod.com/plugins/invada/tube/mono", 
        "version": u"0.6"
        },
    'cabinet': {
        "_id": u"50ddeca595b54730aecb8a01", 
        "binary": u"cabinet.so", 
        "brand": u"caps", 
        "bypassLedPosition": u"118-83", 
        "category": [
            "Simulator"
            ], 
        "connectionOptional": False, 
        "developer": {
            "connectionOptional": False, 
            "enumeration": False, 
            "hasStrictBounds": False, 
            "homepage": u"http://quitte.de/dsp/caps.html", 
            "integer": False, 
            "logarithmic": False, 
            "mbox": u"tim@quitte.de", 
            "name": u"Tim Goetze", 
            "notAutomatic": False, 
            "outputGain": False, 
            "reportsBpm": False, 
            "reportsLatency": False, 
            "sampleRate": False, 
            "toggled": False, 
            "trigger": False
            }, 
        "enumeration": False, 
        "hasStrictBounds": False, 
        "integer": False, 
        "license": u"gpl", 
        "logarithmic": False, 
        "maintainer": {
            "connectionOptional": False, 
            "enumeration": False, 
            "hasStrictBounds": False, 
            "homepage": u"http://portalmod.com", 
            "integer": False, 
            "logarithmic": False, 
            "mbox": u"devel@portalmod.com", 
            "name": u"MOD Team", 
            "notAutomatic": False, 
            "outputGain": False, 
            "reportsBpm": False, 
            "reportsLatency": False, 
            "sampleRate": False, 
            "toggled": False, 
            "trigger": False
            }, 
        "microVersion": 4, 
        "minorVersion": 0, 
        "name": u"C* CabinetI - Loudspeaker cabinet emulation", 
        "notAutomatic": False, 
        "optionalFeature": u"hardRtCapable", 
        "outputGain": False, 
        "package": u"mod-plugins-caps-cabinet.lv2", 
        "package_id": u"50ddeca595b54730aecb8a00", 
        "pedalColor": u"brown", 
        "pedalLabel": u"Cabinet I", 
        "pedalModel": u"japanese", 
        "ports": {
            "audio": {
                "input": [
                    {
                        "connectionOptional": False, 
                        "enumeration": False, 
                        "hasStrictBounds": False, 
                        "index": 0, 
                        "integer": False, 
                        "logarithmic": False, 
                        "name": u"in", 
                        "notAutomatic": False, 
                        "outputGain": False, 
                        "reportsBpm": False, 
                        "reportsLatency": False, 
                        "sampleRate": False, 
                        "symbol": u"in", 
                        "toggled": False, 
                        "trigger": False, 
                        "types": [
                            "InputPort", 
                            "AudioPort"
                            ]
                        }
                    ], 
                "output": [
                    {
                        "connectionOptional": False, 
                        "enumeration": False, 
                        "hasStrictBounds": False, 
                        "index": 3, 
                        "integer": False, 
                        "logarithmic": False, 
                        "name": u"out", 
                        "notAutomatic": False, 
                        "outputGain": False, 
                        "reportsBpm": False, 
                        "reportsLatency": False, 
                        "sampleRate": False, 
                        "symbol": u"out", 
                        "toggled": False, 
                        "trigger": False, 
                        "types": [
                            "AudioPort", 
                            "OutputPort"
                            ]
                        }
                    ]
                }, 
            "control": {
                "input": [
                    {
                        "connectionOptional": False, 
                        "default": 4, 
                        "enumeration": True, 
                        "hasStrictBounds": False, 
                        "index": 1, 
                        "integer": True, 
                        "logarithmic": False, 
                        "maximum": 7, 
                        "minimum": 0, 
                        "name": u"model", 
                        "notAutomatic": False, 
                        "outputGain": False, 
                        "pedalButton": u"1-1", 
                        "reportsBpm": False, 
                        "reportsLatency": False, 
                        "sampleRate": False, 
                        "scalePoints": [
                            {
                                "connectionOptional": False, 
                                "enumeration": False, 
                                "hasStrictBounds": False, 
                                "integer": False, 
                                "label": u"Little Wing 68", 
                                "logarithmic": False, 
                                "notAutomatic": False, 
                                "outputGain": False, 
                                "reportsBpm": False, 
                                "reportsLatency": False, 
                                "sampleRate": False, 
                                "toggled": False, 
                                "trigger": False, 
                                "value": 4
                                }, 
                            {
                                "connectionOptional": False, 
                                "enumeration": False, 
                                "hasStrictBounds": False, 
                                "integer": False, 
                                "label": u"Pro Jr", 
                                "logarithmic": False, 
                                "notAutomatic": False, 
                                "outputGain": False, 
                                "reportsBpm": False, 
                                "reportsLatency": False, 
                                "sampleRate": False, 
                                "toggled": False, 
                                "trigger": False, 
                                "value": 7
                                }, 
                            {
                                "connectionOptional": False, 
                                "enumeration": False, 
                                "hasStrictBounds": False, 
                                "integer": False, 
                                "label": u"Supertramp", 
                                "logarithmic": False, 
                                "notAutomatic": False, 
                                "outputGain": False, 
                                "reportsBpm": False, 
                                "reportsLatency": False, 
                                "sampleRate": False, 
                                "toggled": False, 
                                "trigger": False, 
                                "value": 3
                                }, 
                            {
                                "connectionOptional": False, 
                                "enumeration": False, 
                                "hasStrictBounds": False, 
                                "integer": False, 
                                "label": u"Martial", 
                                "logarithmic": False, 
                                "notAutomatic": False, 
                                "outputGain": False, 
                                "reportsBpm": False, 
                                "reportsLatency": False, 
                                "sampleRate": False, 
                                "toggled": False, 
                                "trigger": False, 
                                "value": 5
                                }, 
                            {
                                "connectionOptional": False, 
                                "enumeration": False, 
                                "hasStrictBounds": False, 
                                "integer": False, 
                                "label": u"Mesa", 
                                "logarithmic": False, 
                                "notAutomatic": False, 
                                "outputGain": False, 
                                "reportsBpm": False, 
                                "reportsLatency": False, 
                                "sampleRate": False, 
                                "toggled": False, 
                                "trigger": False, 
                                "value": 6
                                }, 
                            {
                                "connectionOptional": False, 
                                "enumeration": False, 
                                "hasStrictBounds": False, 
                                "integer": False, 
                                "label": u"Unmatched off-axis", 
                                "logarithmic": False, 
                                "notAutomatic": False, 
                                "outputGain": False, 
                                "reportsBpm": False, 
                                "reportsLatency": False, 
                                "sampleRate": False, 
                                "toggled": False, 
                                "trigger": False, 
                                "value": 1
                                }, 
                            {
                                "connectionOptional": False, 
                                "enumeration": False, 
                                "hasStrictBounds": False, 
                                "integer": False, 
                                "label": u"Unmatched on-axis", 
                                "logarithmic": False, 
                                "notAutomatic": False, 
                                "outputGain": False, 
                                "reportsBpm": False, 
                                "reportsLatency": False, 
                                "sampleRate": False, 
                                "toggled": False, 
                                "trigger": False, 
                                "value": 2
                                }
                            ], 
                        "symbol": u"model", 
                        "toggled": False, 
                        "trigger": False, 
                        "types": [
                            "InputPort", 
                            "ControlPort"
                            ]
                        }, 
                    {
                        "connectionOptional": False, 
                        "default": 0.0, 
                        "enumeration": False, 
                        "hasStrictBounds": False, 
                        "index": 2, 
                        "integer": False, 
                        "logarithmic": False, 
                        "maximum": 24, 
                        "minimum": -24, 
                        "name": u"gain", 
                        "notAutomatic": False, 
                        "outputGain": False, 
                        "pedalButton": u"1-5", 
                        "reportsBpm": False, 
                        "reportsLatency": False, 
                        "sampleRate": False, 
                        "symbol": u"gain", 
                        "toggled": False, 
                        "trigger": False, 
                        "types": [
                            "InputPort", 
                            "ControlPort"
                            ], 
                        "unit": {
                            "name": u"decibel", 
                            "render": u"%f dB", 
                            "symbol": u"dB"
                            }
                        }
                    ], 
                "output": []
                }
            }, 
        "reportsBpm": False, 
        "reportsLatency": False, 
        "sampleRate": False, 
        "smallLabel": u"CabinetI", 
        "stability": u"stable", 
        "toggled": False, 
        "trigger": False, 
        "url": u"http://portalmod.com/plugins/caps/CabinetI", 
        "version": u"0.4"
        }

    
    }
