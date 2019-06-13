# -*- coding: utf-8 -*-

import json
import os
import logging

from subprocess import getoutput
from tornado import ioloop

from mod import TextFileFlusher, safe_json_load
from mod.settings import DATA_DIR

def index_to_filepath(index):
    return os.path.join(DATA_DIR, "profile{0}.json".format(index))

def ensure_data_index_valid(data, fallback):
    index = data.get('index', None)
    if not isinstance(index, int) or index < 1 or index > Profile.NUM_PROFILES:
        data['index'] = fallback

def fill_in_mixer_values(data):
    data['input1volume']    = float(getoutput("mod-amixer in 1 xvol").strip())
    data['input2volume']    = float(getoutput("mod-amixer in 2 xvol").strip())
    data['output1volume']   = float(getoutput("mod-amixer out 1 xvol").strip())
    data['output1volume']   = float(getoutput("mod-amixer out 2 xvol").strip())
    data['headphoneVolume'] = float(getoutput("mod-amixer hp xvol").strip())

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
        'cvBias': CONTROL_VOLTAGE_BIAS_0_to_5,
        'expressionPedalMode': EXPRESSION_PEDAL_MODE_TIP,
        'footswitchesNavigateBank': False,
        'footswitchesNavigateSnapshots': False,
        'headphoneVolume': -6.0, # 60%
        'inputMode': INPUT_MODE_EXP_PEDAL,
        'inputStereoLink': True,
        'masterVolumeChannelMode': MASTER_VOLUME_CHANNEL_MODE_BOTH,
        'midiChannelForPedalboardsNavigation': MIDI_CHANNEL_NAVIGATION_OFF,
        'midiChannelForSnapshotsNavigation': MIDI_CHANNEL_NAVIGATION_OFF,
        'midiClockSend': False,
        'output1volume': 0.0, # 100%
        'output2volume': 0.0,
        'outputMode': OUTPUT_MODE_HEADPHONE,
        'outputStereoLink': True,
        'transportBPM': 120,
        'transportBPB': 4,
        'transportSource': TRANSPORT_SOURCE_INTERNAL,
        # must contain extra stuff from profile 1
        'index': 1,
        'input1volume': 8.0, # 10%
        'input2volume': 8.0,
    }
    DEFAULTS_EXTRA = {
        1: {
            'index': 1,
            'input1volume': 8.0, # 10%
            'input2volume': 8.0,
        },
        2: {
            'index': 2,
            'input1volume': 78 * 0.2, # 20%
            'input2volume': 78 * 0.2,
        },
        3: {
            'index': 3,
            'input1volume': 78 * 0.8, # 80%
            'input2volume': 78 * 0.8,
        },
        4: {
            'index': 4,
            'input1volume': 0.0, # 0 %
            'input2volume': 0.0,
        },
    }

    def __init__(self, applyFn):
        self.applyFn = applyFn
        self.changed = False
        self.values  = self.DEFAULTS.copy()

        if os.path.exists(self.INTERMEDIATE_PROFILE_PATH):
            data = safe_json_load(self.INTERMEDIATE_PROFILE_PATH, dict)
            ensure_data_index_valid(data, 1)
            self.values.update(data)
        else:
            with TextFileFlusher(self.INTERMEDIATE_PROFILE_PATH) as fh:
                json.dump(self.values, fh, indent=4)

        fill_in_mixer_values(self.values)
        ioloop.IOLoop.instance().add_callback(self.apply_first)

    # -----------------------------------------------------------------------------------------------------------------
    # tools

    def apply_first(self):
        self.apply(True)

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
            json.dump(self.values, fh, indent=4)

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
        logging.error("[profile] get_footswitch_navigation called with invalid arg %s", what)
        return False

    def get_master_volume_channel_mode(self):
        return self.values['masterVolumeChannelMode']

    def get_midi_prgch_channel(self, what):
        if what == 'pedalboard':
            return self.values['midiChannelForPedalboardsNavigation']
        if what == 'snapshot':
            return self.values['midiChannelForSnapshotsNavigation']
        logging.error("[profile] get_midi_prgch_channel called with invalid arg %s", what)
        return self.MIDI_CHANNEL_NAVIGATION_OFF

    def get_stereo_link(self, port_type):
        if port_type == 'input':
            return self.values['inputStereoLink']
        if port_type == 'output':
            return self.values['outputStereoLink']
        logging.error("[profile] get_stereo_link called with invalid arg %s", port_type)
        return True

    def get_transport_source(self):
        return self.values['transportSource']

    # -----------------------------------------------------------------------------------------------------------------
    # setters

    def set_configurable_input_mode(self, value):
        if value not in (self.INPUT_MODE_EXP_PEDAL, self.INPUT_MODE_CV):
            logging.error("[profile] set_configurable_input_mode called with invalid value %s", value)
            return False
        return self._compare_and_set_value('inputMode', value)

    def set_configurable_output_mode(self, value):
        if value not in (self.OUTPUT_MODE_HEADPHONE, self.OUTPUT_MODE_CV):
            logging.error("[profile] set_configurable_output_mode called with invalid value %s", value)
            return False
        return self._compare_and_set_value('outputMode', value)

    def set_control_voltage_bias(self, value):
        if value not in (self.CONTROL_VOLTAGE_BIAS_0_to_5, self.CONTROL_VOLTAGE_BIAS_m2d5_TO_2d5):
            logging.error("[profile] set_control_voltage_bias called with invalid value %s", value)
            return False
        return self._compare_and_set_value('cvBias', value)

    def set_exp_mode(self, value):
        if value not in (self.EXPRESSION_PEDAL_MODE_TIP, self.EXPRESSION_PEDAL_MODE_SLEEVE):
            logging.error("[profile] set_exp_mode called with invalid value %s", value)
            return False
        return self._compare_and_set_value('expressionPedalMode', value)

    def set_footswitch_navigation(self, what, value):
        if not isinstance(value, bool):
            logging.error("[profile] set_footswitch_navigation called with non-boolean value")
            return False
        if what == 'bank':
            return self._compare_and_set_value('footswitchesNavigateBank', value)
        if what == 'snapshot':
            return self._compare_and_set_value('footswitchesNavigateSnapshots', value)
        logging.error("[profile] set_footswitch_navigation called with invalid arg %s", what)
        return False

    def set_headphone_volume(self, value):
        if value < 0 or value > 100:
            logging.error("[profile] set_headphone_volume called with invalid value %s", value)
            return False
        return self._compare_and_set_value('headphoneVolume', value)

    def set_master_volume_channel_mode(self, value):
        if value not in (self.MASTER_VOLUME_CHANNEL_MODE_1,
                         self.MASTER_VOLUME_CHANNEL_MODE_2,
                         self.MASTER_VOLUME_CHANNEL_MODE_BOTH):
            logging.error("[profile] set_master_volume_channel_mode called with invalid value %s", value)
            return False
        return self._compare_and_set_value('masterVolumeChannelMode', value)

    def set_midi_prgch_channel(self, what, value):
        if value != self.MIDI_CHANNEL_NAVIGATION_OFF and (value < 1 or value > 16):
            logging.error("[profile] set_midi_prgch_channel called with invalid value %s", value)
            return False
        if what == 'pedalboard':
            return self._compare_and_set_value('midiChannelForPedalboardsNavigation', value)
        if what == 'snapshot':
            return self._compare_and_set_value('midiChannelForSnapshotsNavigation', value)
        logging.error("[profile] set_midi_prgch_channel called with invalid arg %s", what)
        return False

    def set_stereo_link(self, port_type, value):
        if not isinstance(value, bool):
            logging.error("[profile] set_stereo_link called with non-boolean value")
            return False
        if port_type == 'input':
            return self._compare_and_set_value('inputStereoLink', value)
        if port_type == 'output':
            return self._compare_and_set_value('outputStereoLink', value)
        logging.error("[profile] set_stereo_link called with invalid port_type %s", port_type)
        return False

    def set_send_midi_beat_clock(self, value):
        if not isinstance(value, bool):
            logging.error("[profile] set_send_midi_beat_clock called with non-boolean value")
            return False
        return self._compare_and_set_value('outputStereoLink', value)

    def set_sync_mode(self, value):
        if value not in (self.TRANSPORT_SOURCE_INTERNAL,
                         self.TRANSPORT_SOURCE_MIDI_SLAVE,
                         self.TRANSPORT_SOURCE_ABLETON_LINK):
            logging.error("[profile] set_sync_mode called with invalid value %s", value)
            return False
        return self._compare_and_set_value('transportSource', value)

    def set_tempo_bpb(self, bpb):
        return self._compare_and_set_value('transportBPB', bpb)

    def set_tempo_bpm(self, bpm):
        return self._compare_and_set_value('transportBPM', bpm)

    # -----------------------------------------------------------------------------------------------------------------
    # persistent state

    def store(self, index):
        """Serialize the profile to JSON and store it on harddisk."""
        if index < 0 or index > 4:
            return False

        self.values['index'] = index

        # request and store mixer values
        fill_in_mixer_values(self.values)

        # save intermediate file first
        with TextFileFlusher(self.INTERMEDIATE_PROFILE_PATH) as fh:
            json.dump(self.values, fh, indent=4)

        # save real profile
        with TextFileFlusher(index_to_filepath(index)) as fh:
            json.dump(self.values, fh, indent=4)

        # done
        self.changed = False
        return True

    def retrieve(self, index):
        """Deserialize the profile from JSON stored on harddisk."""
        if index < 0 or index > 4:
            return False

        # load state
        filename = index_to_filepath(index)
        if os.path.exists(filename):
            data = safe_json_load(filename, dict)
            data['index'] = index
        else:
            data = self.DEFAULTS.copy()
            data.update(self.DEFAULTS_EXTRA[index])

        self.changed = False
        self.values.update(data)

        # store everything in intermediate file, now with new values
        with TextFileFlusher(self.INTERMEDIATE_PROFILE_PATH) as fh:
            json.dump(self.values, fh, indent=4)

        # apply the values
        self.apply(False)
        return True
