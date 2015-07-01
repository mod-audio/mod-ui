
# Copyright 2012-2013 AGR Audio, Industria e Comercio LTDA. <contato@moddevices.com>
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

import os, json, re
from mod.settings import HARDWARE_DIR, DEVICE_MODEL

"""
As it is implemented today by the JS UI:

A Hardware can be a Known Hardware, meaning it is described
by a class on ``hardware.py`` or a new hardware (still not working)

An Actuator also can be described here, basically it is an
Actuator Subclass. Actuator instances are grouped by it's
ACT_TYP attribute. This will change in the future as they can
be grouped by the class, so the ACT_TYP and HW_TYP
attributes can disappear

The actuator can be bound to a Hardware, this means that the
actuator will have an id which is a way to identify it,
together with it's class, inside the hardware

Known actuators and hardwares:
    Hardware
        MQ (Quadra)
        Pedal
        Touch
        Accel

    Actuator
        Knob
        FootSwitch
        Pot

"""

class Hardware(object):
    HW_TYP = -1

    def __init__(self, id, name, actuators=[]):
        self.name = name
        self.id = id
        self.actuators = []
        acts = {}
        for act in actuators:
            acts[act.__class__] = acts.get(act.__class__, -1) + 1
            act.bind_to_hw(self, acts[act.__class__])
            self.actuators.append(act)

    def get_label_for_actuator(self, actuator, addr_type):
        return actuator.get_label_by_addr_type(addr_type)

class Actuator(object):
    ACT_TYP = -1
    def __init__(self, name, addressing_type=[], exclusive=True):
        self.name = name
        self.addressing_type = addressing_type
        self.exclusive = exclusive
        self.hw = None
        self.id = -1

    def bind_to_hw(self, hw, actid):
        self.hw = hw
        self.id = actid

    @property
    def label(self):
        if self.id != -1:
            return "%s %d" % (self.name, self.id + 1)
        elif self.hw is not None:
            return "%s %d" % (self.hw.name, self.hw.id + 1)
        else:
            return self.name

    def get_label_by_addr_type(self, addr_type):
        return self.label

# Known actuators
class FootSwitch(Actuator):
    # Attention: this type is hardcoded in pedalboards.js
    ACT_TYP = 1

    def __init__(self, name="Foot", addressing_type=['switch', 'tap_tempo'], exclusive=True):
        super(FootSwitch, self).__init__(name, addressing_type, exclusive)

    def get_label_by_addr_type(self, addr_type):
        if addr_type == "tap_tempo":
            return "%s (Tap Tempo)" % self.label
        return self.label

class Knob(Actuator):
    ACT_TYP = 2

    def __init__(self, name="Knob", addressing_type=['range', 'select'], exclusive=False):
        super(Knob, self).__init__(name, addressing_type, exclusive)


class Pot(Actuator):
    ACT_TYP = 3

    def __init__(self, name="Pot", addressing_type=['range'], exclusive=True):
        super(Pot, self).__init__(name, addressing_type, exclusive)

# Known hardware definitions
class MQ(Hardware):
    "MOD Quadra"

    HW_TYP = 0
    def __init__(self, id):
        actuators = [
                    Knob(),
                    Knob(),
                    Knob(),
                    Knob(),
                    FootSwitch(),
                    FootSwitch(),
                    FootSwitch(),
                    FootSwitch(),
                ]
        super(MQ, self).__init__(id, "MOD Quadra", actuators)

class ExprPedal(Hardware):
    HW_TYP = 1
    def __init__(self, id):
        actuators = [
                    Pot("Exp."),
                    FootSwitch("Foot - Exp."),
                    ]
        super(ExprPedal, self).__init__(id, "Pedal", actuators)

    def get_label_for_actuator(self, actuator, addr_type):
        return "%s %d" % (actuator.name, self.id + 1)

class Touch(Hardware):
    HW_TYP = 2

    def __init__(self, id):
        actuators = [
                Pot("X"),
                Pot("Y")
            ]
        super(Touch, self).__init__(id, "Touch", actuators)

    def get_label_for_actuator(self, actuator, addr_type):
        return "%s: %s" % (self.name, actuator.name)


class Accel(Hardware):
    HW_TYP = 3

    def __init__(self, id):
        actuators = [
                Pot("X"),
                Pot("Y"),
                Pot("Z")
            ]
        super(Accel, self).__init__(id, "Accel", actuators)

    def get_label_for_actuator(self, actuator, addr_type):
        return "%s: %s" % (self.name, actuator.name)


HW_TYP_TO_CLS = dict((cls.HW_TYP, cls) for cls in Hardware.__subclasses__())

def add_hardware(hardware_type, hardware_id, hardware):
    try:
        hardware_cls = HW_TYP_TO_CLS[hardware_type]
    except (KeyError):
        return

    hw = hardware_cls(hardware_id)

    for actuator in hw.actuators:
        for addr_type in actuator.addressing_type:
            hardware[addr_type] = hardware.get(addr_type, [])
            hardware[addr_type].append([hw.HW_TYP,
                                        hw.id,
                                        actuator.ACT_TYP,
                                        actuator.id,
                                        actuator.exclusive,
                                        hw.get_label_for_actuator(actuator, addr_type) ])

def get_hardware():
    # TODO might deserve cache. inotify to expire cache?
    hardware = {}
    known_hws = dict( (cls.__name__.upper(), cls.HW_TYP) for cls in Hardware.__subclasses__() )
    try:
        model = open(DEVICE_MODEL).read()
        model = known_hws.get(model, 0)
    except IOError:
        model = 0

    add_hardware(model, 0, hardware)

    for extension in sorted(os.listdir(HARDWARE_DIR)):
        m = re.match('^(\d+)_(\d+)$', extension)
        if m:
            add_hardware(int(m.groups()[0]), int(m.groups()[1]), hardware)
    return hardware
