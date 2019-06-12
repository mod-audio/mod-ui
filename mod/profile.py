# -*- coding: utf-8 -*-

import json
import os

from mod import TextFileFlusher, safe_json_load
from mod.settings import DATA_DIR

def index_to_filepath(index):
    return os.path.join(DATA_DIR, "profile{0}.json".format(index))

def ensure_data_index_valid(data):
    index = data.get('index', None)
    if not isinstance(index, int) or index < 1 or index > Profile.NUM_PROFILES:
        data['index'] = 1

# The user profile models environmental context.
# That is all settings that are related to the physical hookup of the device.
# For example the MIDI control channels are related to an external controler,
# not to the saved banks, and they might change when the user moves.
#
# To be persistent, this needs to be written to disk on every change.
class Profile(object):
    NUM_PROFILES = 4
    INTERMEDIATE_PROFILE_PATH = index_to_filepath(NUM_PROFILES + 1)

    CONTROL_VOLTAGE_BIAS_0_to_5      = 0 # 0 to 5 volts
    CONTROL_VOLTAGE_BIAS_m2d5_TO_2d5 = 1 # 2.5 to 2.5 volts

    EXPRESSION_PEDAL_MODE_TIP    = 0 # signal on tip
    EXPRESSION_PEDAL_MODE_SLEEVE = 1 # signal on sleeve

    INPUT_MODE_EXP_PEDAL = 0
    INPUT_MODE_CV        = 1

    MASTER_VOLUME_CHANNEL_MODE_BOTH = 0
    MASTER_VOLUME_CHANNEL_MODE_1    = 1
    MASTER_VOLUME_CHANNEL_MODE_2    = 2

    # 1-16 midi channel, 0 being off
    MIDI_CHANNEL_NAVIGATION_OFF = 0

    OUTPUT_MODE_HEADPHONE = 0
    OUTPUT_MODE_CV        = 1

    TRANSPORT_SOURCE_INTERNAL     = 0
    TRANSPORT_SOURCE_MIDI_SLAVE   = 1
    TRANSPORT_SOURCE_ABLETON_LINK = 2

    DEFAULTS = {
        'index': 1,
        'cvBias': CONTROL_VOLTAGE_BIAS_0_to_5,
        'expressionPedalMode': EXPRESSION_PEDAL_MODE_TIP,
        'footswitchesNavigateBank': False,
        'footswitchesNavigateSnapshots': False,
        'headphoneVolume': 0.0, # TODO
        'input1gain': 0.0, # TODO
        'input2gain': 0.0, # TODO
        'inputMode': INPUT_MODE_EXP_PEDAL,
        'inputStereoLink': True,
        'masterVolumeChannelMode': MASTER_VOLUME_CHANNEL_MODE_BOTH,
        'midiChannelForPedalboardsNavigation': MIDI_CHANNEL_NAVIGATION_OFF,
        'midiChannelForSnapshotsNavigation': MIDI_CHANNEL_NAVIGATION_OFF,
        'midiClockSend': False,
        'output1volume': 78, # TODO
        'output2volume': 78, # TODO
        'outputMode': OUTPUT_MODE_HEADPHONE,
        'outputStereoLink': True,
        'transportBPM': 120,
        'transportBPB': 4,
        'transportSource': TRANSPORT_SOURCE_INTERNAL,
    }

    def __init__(self, applyFn):
        self.applyFn = applyFn
        self.changed = False
        self.values  = self.DEFAULTS.copy()

        if os.path.exists(self.INTERMEDIATE_PROFILE_PATH):
            data = safe_json_load(self.INTERMEDIATE_PROFILE_PATH, dict)
            ensure_data_index_valid(data)
            self.values.update(data)
        else:
            with TextFileFlusher(self.INTERMEDIATE_PROFILE_PATH) as fh:
                json.dump(self.values, fh)

        self.apply(True)

    # -----------------------------------------------------------------------------------------------------------------
    # tools

    def apply(self, isIntermediate):
        self.applyFn(self.values, isIntermediate)

    def get_last_stored_profile_index(self):
        """Return the profile index that was stored latest and if it was changed since."""
        return (self.values['index'], self.changed)

    def _compare_and_set_value(self, key, value):
        if value == self.values[key]:
            return False
        self.changed = True
        self.values[key] = value

        with TextFileFlusher(self.INTERMEDIATE_PROFILE_PATH) as fh:
            json.dump(self.values, fh)

        return True

    # -----------------------------------------------------------------------------------------------------------------
    # getters

    def get_configurable_input_mode(self):
        return self.values['inputMode']

    def get_configurable_output_mode(self):
        return self.values['outputMode']

    def get_control_voltage_bias(self):
        return self.values['cvBias']

    def get_exp_mode(self):
        return self.values['expressionPedalMode']

    def get_footswitch_navigation(self, what):
        if what == 'bank':
            return self.values['footswitchesNavigateBank']
        if what == 'snapshot':
            return self.values['footswitchesNavigateSnapshots']
        return False

    def get_headphone_volume(self):
        return self.values['headphoneVolume']

    def get_master_volume_channel_mode(self):
        return self.values['masterVolumeChannelMode']

    def get_midi_prgch_channel(self, what):
        if what == 'pedalboard':
            return self.values['midiChannelForPedalboardsNavigation']
        if what == 'snapshot':
            return self.values['midiChannelForSnapshotsNavigation']
        return self.MIDI_CHANNEL_NAVIGATION_OFF

    def get_stereo_link(self, port_type):
        if port_type == 'input':
            return self.values['inputStereoLink']
        if port_type == 'ouput':
            return self.values['outputStereoLink']
        return True

    def get_transport_source(self):
        return self.values['transportSource']

    # -----------------------------------------------------------------------------------------------------------------
    # setters

    def set_configurable_input_mode(self, value):
        if value not in (self.INPUT_MODE_EXP_PEDAL, self.INPUT_MODE_CV):
            print("set_configurable_input_mode invalid")
            return False
        return self._compare_and_set_value('inputMode', value)

    def set_configurable_output_mode(self, value):
        if value not in (self.OUTPUT_MODE_HEADPHONE, self.OUTPUT_MODE_CV):
            print("set_configurable_output_mode invalid")
            return False
        return self._compare_and_set_value('outputMode', value)

    def set_control_voltage_bias(self, value):
        if value not in (self.CONTROL_VOLTAGE_BIAS_0_to_5, self.CONTROL_VOLTAGE_BIAS_m2d5_TO_2d5):
            print("set_control_voltage_bias invalid")
            return False
        return self._compare_and_set_value('cvBias', value)

    def set_exp_mode(self, value):
        if value not in (self.EXPRESSION_PEDAL_MODE_TIP, self.EXPRESSION_PEDAL_MODE_SLEEVE):
            print("set_exp_mode invalid")
            return False
        return self._compare_and_set_value('expressionPedalMode', value)

    def set_footswitch_navigation(self, what, value):
        if not isinstance(value, bool):
            print("set_footswitch_navigation invalid")
            return False
        if what == 'bank':
            return self._compare_and_set_value('footswitchesNavigateBank', value)
        if what == 'snapshot':
            return self._compare_and_set_value('footswitchesNavigateSnapshots', value)
        return False

    def set_headphone_volume(self, value):
        if value < 0 or value > 100:
            print("set_headphone_volume invalid")
            return False
        return self._compare_and_set_value('headphoneVolume', value)

    def set_master_volume_channel_mode(self, value):
        if value not in (self.MASTER_VOLUME_CHANNEL_MODE_1,
                         self.MASTER_VOLUME_CHANNEL_MODE_2,
                         self.MASTER_VOLUME_CHANNEL_MODE_BOTH):
            print("set_master_volume_channel_mode invalid")
            return False
        return self._compare_and_set_value('masterVolumeChannelMode', value)

    def set_midi_prgch_channel(self, what, value):
        if value != self.MIDI_CHANNEL_NAVIGATION_OFF and (value < 1 or value > 16):
            print("set_midi_prgch_channel invalid")
            return False
        if what == 'pedalboard':
            return self._compare_and_set_value('midiChannelForPedalboardsNavigation', value)
        if what == 'snapshot':
            return self._compare_and_set_value('midiChannelForSnapshotsNavigation', value)
        return False

    def set_stereo_link(self, port_type, value):
        if not isinstance(value, bool):
            print("set_stereo_link invalid")
            return False
        if port_type == 'input':
            return self._compare_and_set_value('inputStereoLink', value)
        if port_type == 'output':
            return self._compare_and_set_value('outputStereoLink', value)
        return False

    def set_send_midi_beat_clock(self, value):
        if not isinstance(value, bool):
            print("set_send_midi_beat_clock invalid")
            return False
        return self._compare_and_set_value('outputStereoLink', value)

    def set_sync_mode(self, value):
        if value not in (self.TRANSPORT_SOURCE_INTERNAL,
                         self.TRANSPORT_SOURCE_MIDI_SLAVE,
                         self.TRANSPORT_SOURCE_ABLETON_LINK):
            print("set_sync_mode invalid")
            return False
        return self._compare_and_set_value('transportSource', value)

    # -----------------------------------------------------------------------------------------------------------------
    # persistent state

    def store(self, index):
        """Serialize the profile to JSON and store it on harddisk."""
        self.changed = False
        with TextFileFlusher(index_to_filepath(self.values['index'])) as fh:
            json.dump(self.values, fh)
        return True

    def retrieve(self, index):
        """Deserialize the profile from JSON stored on harddisk."""
        data = safe_json_load(index_to_filepath(index), dict)
        ensure_data_index_valid(data)
        self.changed = False
        self.values.update(data)
        return True
