# -*- coding: utf-8 -*-

#from mod.bank import list_banks, get_last_bank_and_pedalboard, save_last_bank_and_pedalboard


# The profile models environmental context. That is all settings that
# are related to the physical hookup of the device. For example the
# MIDI control channels are related to an external controler, not to
# the saved banks.
class Profile:
    """User profile of environmental context."""

    # MIDI channels range in [0,15]
    # TODO: None when not used? Or -1?
    midi_prgch_bank_channel = 15
    midi_prgch_snapshot_channel = 14

    offer_bank_footswitch_navigation = False
    offer_snapshot_footswitch_navigation = False
    
    # def __init__(self):
    #     self.reset()

    # def reset(self):
    #     pass
