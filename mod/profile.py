# -*- coding: utf-8 -*-

import json
import os

from mod import TextFileFlusher, safe_json_load
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
    __index = 5
    __state_changed = False

    MIDI_BEAT_CLOCK_OFF                   = 0
    MIDI_BEAT_CLOCK_ON_WITHOUT_START_STOP = 1
    MIDI_BEAT_CLOCK_ON_WITH_START_STOP    = 2

    TRANSPORT_SYNC_INTERNAL     = 0
    TRANSPORT_SYNC_MIDI_SLAVE   = 1
    TRANSPORT_SYNC_ABLETON_LINK = 2

    INPUT_MODE_EXP_PEDAL = 0
    INPUT_MODE_CV        = 1

    OUTPUT_MODE_HEADPHONE = 0
    OUTPUT_MODE_CV        = 1

    MASTER_VOLUME_CHANNEL_MODE_1    = 0
    MASTER_VOLUME_CHANNEL_MODE_2    = 1
    MASTER_VOLUME_CHANNEL_MODE_BOTH = 2

    QUICK_BYPASS_MODE_BOTH = 0
    QUICK_BYPASS_MODE_1    = 1
    QUICK_BYPASS_MODE_2    = 2

    CONTROL_VOLTAGE_BIAS_0_to_5      = 0 # 0 to 5 volts
    CONTROL_VOLTAGE_BIAS_m2d5_TO_2d5 = 1 # 2.5 to 2.5 volts

    EXPRESSION_PEDAL_MODE_TIP    = 0 # signal on tip
    EXPRESSION_PEDAL_MODE_SLEEVE = 1 # signal on sleeve

    # MIDI channels. Range in [1,16] and 0 when "off".
    __midi_prgch_channel = {
        "pedalboard": 16,
        "snapshot": 15,
    }

    __footswitch_navigation = {
        "bank": False,
        "snapshot": False,
    }

    __stereo_link = {
        "input": False,
        "output": False,
    }

    __send_midi_beat_clock = MIDI_BEAT_CLOCK_OFF
    __sync_mode = TRANSPORT_SYNC_INTERNAL

    __headphone_volume = 0 # percentage 0-100
    __configurable_input_mode = INPUT_MODE_EXP_PEDAL
    __configurable_output_mode = OUTPUT_MODE_HEADPHONE
    __master_volume_channel_mode = MASTER_VOLUME_CHANNEL_MODE_BOTH
    __quick_bypass_mode = QUICK_BYPASS_MODE_BOTH
    __control_voltage_bias = CONTROL_VOLTAGE_BIAS_0_to_5
    __exp_mode = EXPRESSION_PEDAL_MODE_TIP

    def __changed(self):
        self.__state_changed = True
        self.store_intermediate()
        return True

    def set_midi_prgch_channel(self, what, value):
        if value >= 0 and value <= 16 and what in ("snapshot", "pedalboard") and value != self.__midi_prgch_channel[what]:
            self.__midi_prgch_channel[what] = value
            return self.__changed()
        return False

    def get_midi_prgch_channel(self, what):
        return self.__midi_prgch_channel.get(what, None)

    def set_footswitch_navigation(self, what, value):
        if what in ("bank", "snapshot") and isinstance(value, bool) and value != self.__footswitch_navigation[what]:
            self.__footswitch_navigation[what] = value
            return self.__changed()
        return False

    def get_footswitch_navigation(self, what):
        return self.__footswitch_navigation.get(what, None)

    def set_stereo_link(self, port_type, value):
        if value in (0, 1, 2) and port_type in ["input", "output"] and value != self.__stereo_link[port_type]:
            self.__stereo_link[port_type] = value
            return self.__changed()
        return False

    def get_stereo_link(self, port_type):
        return self.__stereo_link.get(port_type, None)

    def set_send_midi_beat_clock(self, value):
        if value != self.__send_midi_beat_clock and value in (self.MIDI_BEAT_CLOCK_OFF,
                                                              self.MIDI_BEAT_CLOCK_ON_WITHOUT_START_STOP,
                                                              self.MIDI_BEAT_CLOCK_ON_WITH_START_STOP):
            self.__send_midi_beat_clock = value
            return self.__changed()
        return False

    def set_sync_mode(self, value):
        if value != self.__sync_mode and value in (self.TRANSPORT_SYNC_INTERNAL,
                                                   self.TRANSPORT_SYNC_MIDI_SLAVE,
                                                   self.TRANSPORT_SYNC_ABLETON_LINK):
            self.__sync_mode = value
            return self.__changed()
        return False

    def get_sync_mode(self):
        return self.__sync_mode

    def set_headphone_volume(self, value):
        if value != self.__headphone_volume and value >= 0 and value <= 100:
            self.__headphone_volume = value
            return self.__changed()
        return False

    def get_headphone_volume(self):
        return self.__headphone_volume

    def set_configurable_input_mode(self, value):
        if value != self.__configurable_input_mode and value in (self.INPUT_MODE_EXP_PEDAL,
                                                                 self.INPUT_MODE_CV):
            self.__configurable_input_mode = value
            return self.__changed()
        return False

    def get_configurable_input_mode(self):
        return self.__configurable_input_mode

    def set_configurable_output_mode(self, value):
        if value != self.__configurable_output_mode and value in (self.OUTPUT_MODE_HEADPHONE,
                                                                  self.OUTPUT_MODE_CV):
            self.__configurable_output_mode = value
            return self.__changed()
        return False

    def get_configurable_output_mode(self):
        return self.__configurable_output_mode

    def set_master_volume_channel_mode(self, value):
        if value != self.__master_volume_channel_mode and value in (self.MASTER_VOLUME_CHANNEL_MODE_1,
                                                                    self.MASTER_VOLUME_CHANNEL_MODE_2,
                                                                    self.MASTER_VOLUME_CHANNEL_MODE_BOTH):
            self.__master_volume_channel_mode = value
            return self.__changed()
        return False

    def get_master_volume_channel_mode(self):
        return self.__master_volume_channel_mode

    def set_quick_bypass_mode(self, value):
        if value != self.__quick_bypass_mode and value in (self.QUICK_BYPASS_MODE_1,
                                                           self.QUICK_BYPASS_MODE_2,
                                                           self.QUICK_BYPASS_MODE_BOTH):
            self.__quick_bypass_mode = value
            return self.__changed()
        return False

    def get_quick_bypass_mode(self):
        return self.__quick_bypass_mode

    def set_control_voltage_bias(self, value):
        if value != self.__control_voltage_bias and value in (self.CONTROL_VOLTAGE_BIAS_0_to_5,
                                                              self.CONTROL_VOLTAGE_BIAS_m2d5_TO_2d5):
            self.__control_voltage_bias = value
            return self.__changed()
        return False

    def get_control_voltage_bias(self):
        return self.__control_voltage_bias

    def set_exp_mode(self, value):
        if value != self.__exp_mode and value in (self.EXPRESSION_PEDAL_MODE_TIP,
                                                  self.EXPRESSION_PEDAL_MODE_SLEEVE):
            self.__exp_mode = value
            result = self.__changed()
        return False

    def get_exp_mode(self):
        return self.__exp_mode

    def get_last_stored_profile_index(self):
        """Return the profile index that was stored latest and if it was changed since."""
        return self.__last_stored_profile_index, self.__state_changed

    def store_intermediate(self):
        self.__state_changed = True
        self.__store(self.__intermediate_profile_index)

    def store(self, index):
        self.__state_changed = False
        self.__store(index)
        return True

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
            "headphone_volume": self.__headphone_volume,
            "configurable_input_mode": self.__configurable_input_mode,
            "configurable_output_mode": self.__configurable_output_mode,
            "master_volume_channel_mode": self.__master_volume_channel_mode,
            "quick_bypass_mode": self.__quick_bypass_mode,
            "control_voltage_bias": self.__control_voltage_bias,
            "expression_pedal_mode": self.__exp_mode,
        }

        with TextFileFlusher(index_to_filepath(index)) as fh:
            json.dump(data, fh)

    def retrieve(self, index):
        """Deserialize the profile from JSON stored on harddisk."""
        data = safe_json_load(index_to_filepath(index), dict)

        # FIXME put default values in a static dict, and call update() on the data or something
        self.__index = data.get("index", 5)
        self.__headphone_volume = data.get("headphone_volume", 0)
        self.__midi_prgch_channel["pedalboard"] = data.get("midi_prgch_pedalboard_channel", 16)
        self.__midi_prgch_channel["snapshot"] = data.get("midi_prgch_snapshot_channel", 15)
        self.__footswitch_navigation["bank"] = data.get("bank_footswitch_navigation", False)
        self.__footswitch_navigation["snapshot"] = data.get("snapshot_footswitch_navigation", False)
        self.__stereo_link["input"] = data.get("input_stereo_link", False)
        self.__stereo_link["output"] = data.get("output_stereo_link", False)
        self.__send_midi_beat_clock = data.get("send_midi_beat_clock", self.MIDI_BEAT_CLOCK_OFF)
        self.__sync_mode = data.get("sync_mode", self.TRANSPORT_SYNC_INTERNAL)
        self.__configurable_input_mode = data.get("configurable_input_mode", self.INPUT_MODE_EXP_PEDAL)
        self.__configurable_output_mode = data.get("configurable_output_mode", self.OUTPUT_MODE_HEADPHONE)
        self.__master_volume_channel_mode = data.get("master_volume_channel_mode", self.MASTER_VOLUME_CHANNEL_MODE_BOTH)
        self.__quick_bypass_mode = data.get("quick_bypass_mode", self.QUICK_BYPASS_MODE_BOTH)
        self.__control_voltage_bias = data.get("control_voltage_bias", self.CONTROL_VOLTAGE_BIAS_0_to_5)
        self.__exp_mode = data.get("expression_pedal_mode", self.EXPRESSION_PEDAL_MODE_TIP)
        self.__state_changed = False

        return True
