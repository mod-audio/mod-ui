# -*- coding: utf-8 -*-

#from mod.bank import list_banks, get_last_bank_and_pedalboard, save_last_bank_and_pedalboard


# The user profile models environmental context. That is all settings that
# are related to the physical hookup of the device. For example the
# MIDI control channels are related to an external controler, not to
# the saved banks, and they might change when the user moves.
class Profile:
    """User profile of environmental context."""

    name = "Default"
    
    # MIDI channels. Range in [0,15] -1 when off.
    midi_prgch_bank_channel = 15
    midi_prgch_snapshot_channel = 14

    bank_footswitch_navigation = False
    snapshot_footswitch_navigation = False

    stereo_link_input = False
    stereo_link_output = False

    send_midi_beat_clock = 0 # 0=off, 1=clock, 2=clock+transport
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
    
    additional_input_type = 0 # 0 expression pedal, 1 control voltage input
    additional_output_type = 0 # 0 headphone, 1 control voltage
    
    def set_midi_prgch_bank_channel(self, channel):
        result = False
        if 0 <= channel and channel < 16:
            if (channel != self.midi_prgch_snapshot_channel):
                midi_prgch_bank_channel = channel
                result = True                
        return result

    def set_midi_prgch_snapshot_channel(self, channel):
        result = False
        if 0 <= channel and channel < 16:
            if (channel != self.midi_prgch_bank_channel):
                midi_prgch_snapshot_channel = channel
                result = True
        return result
