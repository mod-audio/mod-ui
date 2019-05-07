# -*- coding: utf-8 -*-

import json
from mod.settings import DATA_DIR

def index_to_filepath(index):
    return DATA_DIR + "/profile{0}.json".format(index)

# The user profile models environmental context. That is all settings that
# are related to the physical hookup of the device. For example the
# MIDI control channels are related to an external controler, not to
# the saved banks, and they might change when the user moves.
class Profile:
    """User profile of environmental context."""

    index = "Default"
    
    # MIDI channels. Range in [0,15] -1 when off.
    midi_prgch_pedalboard_channel = 15
    midi_prgch_snapshot_channel = 14

    bank_footswitch_navigation = False
    snapshot_footswitch_navigation = False

    input_stereo_link = False
    output_stereo_link = False

    send_midi_beat_clock = 0 # 0=off, 1=MIDI clock, 2=MIDI clock + Start + Stop
    sync_mode = 0 # 0=internal, 1=MBC slave, 2=Ableton Link

    # In hardware we have a gain stage and fine level parameters. For
    # the user it should be just one continuous value range.  The
    # function to translate between the two domains must be bijective,
    # so we can store just the value form the user domain.    
    gain_in_1 = 0
    gain_in_2 = 0
    gain_out_1 = 0
    gain_out_2 = 0
    
    headphone_volume = 0 # percentage 0-100
    
    configurable_input_mode = 0 # 0 expression pedal, 1 control voltage input
    configurable_output_mode = 0 # 0 headphone, 1 control voltage

    display_brightness = 4 # percentage in dict{0: 0%, 1: 25%, 2: 50%, 3:75% , 4:100%}

    master_volume_channel_mode = 0 # 0 for master linked to out 1; 1
                                   # for master linked to out 2; 2 for
                                   # master linked to both out 1 and
                                   # out 2.

    quick_bypass_mode = 0 # 0 for "change both 1&2", 1 for "change
                          # channel 1" and 2 for "change channel 2".

    control_voltage_bias = 0 # 0="0 to 5 volts", 1="-2.5 to 2.5 volts"

    def set_midi_prgch_pedalboard_channel(self, channel):
        result = False
        if 0 <= channel and channel < 16:
            if (channel != self.midi_prgch_snapshot_channel):
                midi_prgch_pedalboard_channel = channel
                result = True                
        return result

    def set_midi_prgch_snapshot_channel(self, channel):
        result = False
        if 0 <= channel and channel < 16:
            if (channel != self.midi_prgch_pedalboard_channel):
                midi_prgch_snapshot_channel = channel
                result = True
        return result

    def current(self):
        """Return the current profile index."""
        return self.index
        
    def store(self, index):
        """Serialize the profile to JSON and store it on harddisk."""
        data = {
            "index": self.index,
            "headphone_volume": self.headphone_volume,
            "midi_prgch_pedalboard_channel": self.midi_prgch_pedalboard_channel,
            "midi_prgch_snapshot_channel": self.midi_prgch_snapshot_channel,
            "bank_footswitch_navigation": self.bank_footswitch_navigation,
            "snapshot_footswitch_navigation": self.snapshot_footswitch_navigation,
            "input_stereo_link": self.input_stereo_link,
            "output_stereo_link": self.output_stereo_link,
            "send_midi_beat_clock": self.send_midi_beat_clock,
            "sync_mode": self.sync_mode,
            "gain_in_1": self.gain_in_1,
            "gain_in_2": self.gain_in_2,
            "gain_out_1": self.gain_out_1,
            "gain_out_2": self.gain_out_2,
            "headphone_volume": self.headphone_volume,
            "configurable_input_mode": self.configurable_input_mode,
            "configurable_output_mode": self.configurable_output_mode,
            "display_brightness": self.display_brightness,
            "quick_bypass_mode": self.quick_bypass_mode,
            "control_voltage_bias": self.control_voltage_bias,
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

            self.index = data["index"]
            self.headphone_volume = data["headphone_volume"]
            self.midi_prgch_pedalboard_channel = data["midi_prgch_pedalboard_channel"]
            self.midi_prgch_snapshot_channel = data["midi_prgch_snapshot_channel"]
            self.bank_footswitch_navigation = data["bank_footswitch_navigation"]
            self.snapshot_footswitch_navigation = data["snapshot_footswitch_navigation"]
            self.input_stereo_link = data["input_stereo_link"]
            self.output_stereo_link = data["output_stereo_link"]
            self.send_midi_beat_clock = data["send_midi_beat_clock"]
            self.sync_mode = data["sync_mode"]
            self.gain_in_1 = data["gain_in_1"]
            self.gain_in_2 = data["gain_in_2"]
            self.gain_out_1 = data["gain_out_1"]
            self.gain_out_2 = data["gain_out_2"]
            self.headphone_volume = data["headphone_volume"]
            self.configurable_input_mode = data["configurable_input_mode"]
            self.configurable_output_mode = data["configurable_output_mode"]
            self.display_brightness = data["display_brightness"]
            self.quick_bypass_mode = data["quick_bypass_mode"]
            self.control_voltage_bias = data["control_voltage_bias"]
            result = True
            
        except FileNotFoundError as e:
            pass
        
        return result
