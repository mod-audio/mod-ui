# -*- coding: utf-8 -*-

import json
import os
from mod.settings import DATA_DIR

def index_to_filepath(index):
    return os.path.join(DATA_DIR, "profile{0}.json".format(index))

# The user profile models environmental context. That is all settings that
# are related to the physical hookup of the device. For example the
# MIDI control channels are related to an external controler, not to
# the saved banks, and they might change when the user moves.
#
# To be persistent, this needs to be written to disk on every
# change. Do not access private attributes from outside! Use the "set"
# functions!
class Profile:
    """User profile of environmental context."""

    __intermediate_profile_index = "5"
    __last_stored_profile_index = "1"
    __state_changed = False

    def __changed(self):
        self.__state_changed = True
        self.store_intermediate()
        return True

    # MIDI channels. Range in [1,16] and 0 when "off".
    __midi_prgch_channel = {
        "pedalboard": 16,
        "snapshot": 15,
    }

    def set_midi_prgch_channel(self, what, value):
        result = False
        if 0 <= value and value <= 16 and what in ["snapshot", "pedalboard"]:
            if value != self.__midi_prgch_channel[what]:
                self.__midi_prgch_channel[what] = value
                result = self.__changed()
        return result

    def get_midi_prgch_channel(self, what):
        result = None
        if what in ["snapshot", "pedalboard"]:
            result = self.__midi_prgch_channel[what]
        return result

    __footswitch_navigation = {
        "bank": False,
        "snapshot": False,
    }

    def set_footswitch_navigation(self, what, value):
        result = False
        if isinstance(value, bool) and what in ["bank", "snapshot"]:
            if value != self.__footswitch_navigation[what]:
                self.__footswitch_navigation[what] = value
                result = self.__changed()
        return result

    def get_footswitch_navigation(self, what):
        result = None
        if what in ["bank", "snapshot"]:
            result = self.__footswitch_navigation[what]
        return result

    __stereo_link = {
        "input": False,
        "output": False,
    }

    def set_stereo_link(self, port_type, value):
        result = False
        if value in [0, 1, 2] and port_type in ["input", "output"]:
            if value != self.__stereo_link[port_type]:
                self.__stereo_link[port_type] = value
                result = self.__changed()
        return result

    def get_stereo_link(self, port_type):
        if port_type in ["input", "output"]:
            return self.__stereo_link[port_type]

    __send_midi_beat_clock = 0 # 0=off, 1=MIDI clock, 2=MIDI clock + Start + Stop

    def set_send_midi_beat_clock(self, value):
        result = False
        if value in [0, 1, 2]:
            if value != self.__send_midi_beat_clock:
                self.__send_midi_beat_clock = value
                result = self.__changed()
        return result

    __sync_mode = 0 # 0=internal, 1=MBC slave, 2=Ableton Link

    def set_sync_mode(self, value):
        result = False
        if value in [0, 1, 2]:
            if value != self.__sync_mode:
                self.__sync_mode = value
                result = self.__changed()
        return result

    def get_sync_mode(self):
        return self.__sync_mode

    # In hardware we have a gain stage and fine level parameters. For
    # the user it should be just one continuous value range.  The
    # function to translate between the two domains must be bijective,
    # so we can store just the value form the user domain.
    #
    # 0: "0dB", 1: "6dB", 2: "15dB", 3: "20dB"
    __gain = {
        "input": [0, 0],
        "output": [0, 0],
    }

    def set_gain(self, port_type, channel, value):
        result = False
        if 0 <= value and value <= 3 and port_type in ["input", "output"] and channel in [0, 1]:
            if value != self.__gain[port_type][channel]:
                self.__gain[port_type][channel] = value
                result = self.__changed()
        return result

    def get_gain(self, port_type, channel):
        result = False
        if port_type in ["input", "output"] and channel in [0, 1]:
            return self.__gain[port_type][channel]

    __headphone_volume = 0 # percentage 0-100

    def set_headphone_volume(self, value):
        result = False
        if 0 <= value and value <= 100:
            if value != self.__headphone_volume:
                self.__headphone_volume = value
                result = self.__changed()
        return result

    def get_headphone_volume(self):
        return self.__headphone_volume

    __configurable_input_mode = 0 # 0 expression pedal, 1 control voltage input

    def set_configurable_input_mode(self, value):
        result = False
        if value in [0, 1]:
            if value != self.__configurable_input_mode:
                self.__configurable_input_mode = value
                result = self.__changed()
        return result

    def get_configurable_input_mode(self):
        return self.__configurable_input_mode

    __configurable_output_mode = 0 # 0 headphone, 1 control voltage

    def set_configurable_output_mode(self, value):
        result = False
        if value in [0, 1]:
            if value != self.__configurable_output_mode:
                self.__configurable_output_mode = value
                result = self.__changed()
        return result

    def get_configurable_output_mode(self):
        return self.__configurable_output_mode

    __master_volume_channel_mode = 0 # 0 for master linked to out 1
                                     # 1 for master linked to out 2
                                     # 2 for master linked to both out 1 and out 2.

    def set_master_volume_channel_mode(self, value):
        result = False
        if value in [0, 1, 2]:
            if value != self.__master_volume_channel_mode:
                self.__master_volume_channel_mode = value
                result = self.__changed()
        return result

    def get_master_volume_channel_mode(self):
        return self.__master_volume_channel_mode

    __quick_bypass_mode = 0 # 0 for "change both 1&2"
                            # 1 for "change channel 1"
                            # 2 for "change channel 2"

    def set_quick_bypass_mode(self, value):
        result = False
        if value in [0, 1, 2]:
            if value != self.__quick_bypass_mode:
                self.__quick_bypass_mode = value
                result = self.__changed()
        return result

    def get_quick_bypass_mode(self):
        return self.__quick_bypass_mode

    __control_voltage_bias = 0 # 0="0 to 5 volts", 1="-2.5 to 2.5 volts"

    def set_control_voltage_bias(self, value):
        result = False
        if value in [0, 1]:
            if value != self.__control_voltage_bias:
                self.__control_voltage_bias = value
                result = self.__changed()
        return result

    def get_control_voltage_bias(self):
        return self.__control_voltage_bias

    __exp_mode = 0 # 0="singnal on tip", 1="signal on sleeve"
    def set_exp_mode(self, value):
        result = False
        if value in [0, 1]:
            if value != self.__exp_mode:
                self.__exp_mode = value
                result = self.__changed()
        return result

    def get_exp_mode(self):
        return self.__exp_mode

    def get_last_stored_profile_index(self):
        """Return the profile index that was stored latest and if it was changed since."""
        return self.__last_stored_profile_index, self.__state_changed

    def store_intermediate(self):
        self.__state_changed == True
        self.__store(self.__intermediate_profile_index)

    def store(self, index):
        self.__state_changed == False
        return self.__store(index)

    def __store(self, index):
        """Serialize the profile to JSON and store it on harddisk."""
        data = {
            "index": index,
            "headphone_volume": self.__headphone_volume,
            "midi_prgch_pedalboard_channel": self.__midi_prgch_channel["pedalboard"],
            "midi_prgch_snapshot_channel": self.__midi_prgch_channel["snapshot"],
            "bank_footswitch_navigation": self.__footswitch_navigation["bank"],
            "snapshot_footswitch_navigation": self.__footswitch_navigation["snapshot"],
            "input_stereo_link": self.__stereo_link["input"],
            "output_stereo_link": self.__stereo_link["output"],
            "send_midi_beat_clock": self.__send_midi_beat_clock,
            "sync_mode": self.__sync_mode,
            "gain_in_1": self.__gain["input"][0],
            "gain_in_2": self.__gain["input"][1],
            "gain_out_1": self.__gain["output"][0],
            "gain_out_2": self.__gain["output"][1],
            "headphone_volume": self.__headphone_volume,
            "configurable_input_mode": self.__configurable_input_mode,
            "configurable_output_mode": self.__configurable_output_mode,
            "quick_bypass_mode": self.__quick_bypass_mode,
            "control_voltage_bias": self.__control_voltage_bias,
            "expression_pedal_mode": self.__exp_mode,
        }
        result = False
        try:
            with open(index_to_filepath(index), 'w+') as outfile:
                json.dump(data, outfile)
            result = True
        except FileNotFoundError as e:
            pass
        return result

    def retrieve(self, index):
        """Deserialize the profile from JSON stored on harddisk."""
        data = None
        result = False
        try:
            with open(index_to_filepath(index), 'r') as infile:
                data = json.load(infile)

            self.__index = data["index"]
            self.__headphone_volume = data["headphone_volume"]
            self.__midi_prgch_channel["pedalboard"] = data["midi_prgch_pedalboard_channel"]
            self.__midi_prgch_channel["snapshot"] = data["midi_prgch_snapshot_channel"]
            self.__footswitch_navigation["bank"] = data["bank_footswitch_navigation"]
            self.__footswitch_navigation["snapshot"] = data["snapshot_footswitch_navigation"]
            self.__stereo_link["input"] = data["input_stereo_link"]
            self.__stereo_link["output"] = data["output_stereo_link"]
            self.__send_midi_beat_clock = data["send_midi_beat_clock"]
            self.__sync_mode = data["sync_mode"]
            self.__gain["input"][0] = data["gain_in_1"]
            self.__gain["input"][1] = data["gain_in_2"]
            self.__gain["output"][0] = data["gain_out_1"]
            self.__gain["output"][1] = data["gain_out_2"]
            self.__headphone_volume = data["headphone_volume"]
            self.__configurable_input_mode = data["configurable_input_mode"]
            self.__configurable_output_mode = data["configurable_output_mode"]
            self.__quick_bypass_mode = data["quick_bypass_mode"]
            self.__control_voltage_bias = data["control_voltage_bias"]
            self.__exp_mode = data["expression_pedal_mode"]

            self.__state_changed == False
            result = True

        except FileNotFoundError as e:
            pass

        return result
