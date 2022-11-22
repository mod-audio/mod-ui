# -*- coding: utf-8 -*-

import json
import os
import logging

try:
    from subprocess import getoutput
except:
    from commands import getoutput

from tornado.ioloop import IOLoop

from mod import TextFileFlusher, safe_json_load
from mod.settings import APP, DATA_DIR

def index_to_filepath(index):
    return os.path.join(DATA_DIR, "profile{0}.json".format(index))

def ensure_data_index_valid(data, fallback):
    index = data.get('index', None)
    if not isinstance(index, int) or index < 1 or index > Profile.NUM_PROFILES:
        data['index'] = fallback

def apply_mixer_values(values, platform):
    if not os.path.exists("/usr/bin/mod-amixer"):
        return
    if os.getenv("MOD_SOUNDCARD", None) is None:
        return
    if platform == "duo":
        os.system("/usr/bin/mod-amixer in 1 dvol %f" % values['input1volume'])
        os.system("/usr/bin/mod-amixer in 2 dvol %f" % values['input2volume'])
        os.system("/usr/bin/mod-amixer out 1 dvol %f" % values['output1volume'])
        os.system("/usr/bin/mod-amixer out 2 dvol %f" % values['output2volume'])
        os.system("/usr/bin/mod-amixer hp dvol %f" % values['headphoneVolume'])
        os.system("/usr/bin/mod-amixer hp byp %s" % Profile.value_to_string('headphoneBypass',
                                                                            values['headphoneBypass']))
        return
    if platform == "duox":
        os.system("/usr/bin/mod-amixer in 1 xvol %f" % values['input1volume'])
        os.system("/usr/bin/mod-amixer in 2 xvol %f" % values['input2volume'])
        os.system("/usr/bin/mod-amixer out 1 xvol %f" % values['output1volume'])
        os.system("/usr/bin/mod-amixer out 2 xvol %f" % values['output2volume'])
        os.system("/usr/bin/mod-amixer hp xvol %f" % values['headphoneVolume'])
        os.system("/usr/bin/mod-amixer cvhp %s" % Profile.value_to_string('outputMode', values['outputMode']))
        os.system("/usr/bin/mod-amixer cvexp %s" % Profile.value_to_string('inputMode', values['inputMode']))
        os.system("/usr/bin/mod-amixer exppedal %s" % Profile.value_to_string('expPedalMode', values['expPedalMode']))
        return
    if platform == "dwarf":
        os.system("/usr/bin/mod-amixer in 1 xvol %f" % values['input1volume'])
        os.system("/usr/bin/mod-amixer in 2 xvol %f" % values['input2volume'])
        os.system("/usr/bin/mod-amixer out 1 xvol %f" % values['output1volume'])
        os.system("/usr/bin/mod-amixer out 2 xvol %f" % values['output2volume'])
        os.system("/usr/bin/mod-amixer hp xvol %f" % values['headphoneVolume'])
        return
    if platform is None:
        logging.error("[profile] apply_mixer_values called without platform")
    else:
        logging.error("[profile] apply_mixer_values called with unknown platform %s", platform)

def fill_in_mixer_values(data, platform):
    if not os.path.exists("/usr/bin/mod-amixer"):
        return
    if os.getenv("MOD_SOUNDCARD", None) is None:
        return
    if platform == "duo":
        data['input1volume']    = float(getoutput("/usr/bin/mod-amixer in 1 dvol").strip())
        data['input2volume']    = float(getoutput("/usr/bin/mod-amixer in 2 dvol").strip())
        data['output1volume']   = float(getoutput("/usr/bin/mod-amixer out 1 dvol").strip())
        data['output1volume']   = float(getoutput("/usr/bin/mod-amixer out 2 dvol").strip())
        data['headphoneVolume'] = float(getoutput("/usr/bin/mod-amixer hp dvol").strip())
        data['headphoneBypass'] = Profile.string_to_value('headphoneBypass',
                                                          getoutput("/usr/bin/mod-amixer hp byp").strip())
        return
    if platform == "duox":
        data['input1volume']    = float(getoutput("/usr/bin/mod-amixer in 1 xvol").strip())
        data['input2volume']    = float(getoutput("/usr/bin/mod-amixer in 2 xvol").strip())
        data['output1volume']   = float(getoutput("/usr/bin/mod-amixer out 1 xvol").strip())
        data['output1volume']   = float(getoutput("/usr/bin/mod-amixer out 2 xvol").strip())
        data['headphoneVolume'] = float(getoutput("/usr/bin/mod-amixer hp xvol").strip())
        data['outputMode']      = Profile.string_to_value('outputMode', getoutput("/usr/bin/mod-amixer cvhp").strip())
        data['inputMode']       = Profile.string_to_value('inputMode', getoutput("/usr/bin/mod-amixer cvexp").strip())
        data['expPedalMode']    = Profile.string_to_value('expPedalMode',
                                                          getoutput("/usr/bin/mod-amixer exppedal").strip())
        return
    if platform == "dwarf":
        data['input1volume']    = float(getoutput("/usr/bin/mod-amixer in 1 xvol").strip())
        data['input2volume']    = float(getoutput("/usr/bin/mod-amixer in 2 xvol").strip())
        data['output1volume']   = float(getoutput("/usr/bin/mod-amixer out 1 xvol").strip())
        data['output1volume']   = float(getoutput("/usr/bin/mod-amixer out 2 xvol").strip())
        data['headphoneVolume'] = float(getoutput("/usr/bin/mod-amixer hp xvol").strip())
        return
    if platform is None:
        logging.error("[profile] fill_in_mixer_values called without platform")
    else:
        logging.error("[profile] fill_in_mixer_values called with unknown platform %s", platform)

# The user profile models environmental context.
# That is all settings that are related to the physical hookup of the device.
# For example the MIDI control channels are related to an external controler,
# not to the saved banks, and they might change when the user moves.
#
# To be persistent, this needs to be written to disk on every change.
class Profile(object):
    NUM_PROFILES = 4
    INTERMEDIATE_PROFILE_PATH = index_to_filepath(NUM_PROFILES + 1)

    EXPRESSION_PEDAL_MODE_TIP  = 0 # signal on tip
    EXPRESSION_PEDAL_MODE_RING = 1 # signal on ring/sleeve

    INPUT_MODE_CV        = 0
    INPUT_MODE_EXP_PEDAL = 1

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
        'expPedalMode': EXPRESSION_PEDAL_MODE_RING,
        'headphoneBypass': False,
        'headphoneVolume': -24.0,
        'inputMode': INPUT_MODE_CV,
        'inputStereoLink': True,
        'masterVolumeChannelMode': MASTER_VOLUME_CHANNEL_MODE_BOTH,
        'midiChannelForPedalboardsNavigation': MIDI_CHANNEL_NAVIGATION_OFF,
        'midiChannelForSnapshotsNavigation': MIDI_CHANNEL_NAVIGATION_OFF,
        'midiClockSend': False,
        'output1volume': 0.0, # 0dB
        'output2volume': 0.0,
        'outputMode': OUTPUT_MODE_HEADPHONE,
        'outputStereoLink': True,
        'transportBPM': 120,
        'transportBPB': 4,
        'transportSource': TRANSPORT_SOURCE_INTERNAL,
        # must contain extra stuff from profile 1
        'index': 1,
        'input1volume': 24.0, # 0dB
        'input2volume': 24.0,
    }
    DEFAULTS_EXTRA = {
        1: {
            'index': 1,
            'input1volume': 24.0, # 0dB
            'input2volume': 24.0,
        },
        2: {
            'index': 2,
            'input1volume': 24.0, # 0dB
            'input2volume': 24.0,
        },
        3: {
            'index': 3,
            'input1volume': 60.0, # 18dB
            'input2volume': 60.0,
        },
        4: {
            'index': 4,
            'input1volume': 24.0, # 0dB
            'input2volume': 24.0,
        },
    }

    @classmethod
    def string_to_value(cls, key, string):
        if key == "headphoneBypass":
            if string == "on":
                return True
            if string == "off":
                return False
        if key == "expPedalMode":
            if string == "ring":
                return cls.EXPRESSION_PEDAL_MODE_RING
            if string == "tip":
                return cls.EXPRESSION_PEDAL_MODE_TIP
        if key == "inputMode":
            if string == "cv":
                return cls.INPUT_MODE_CV
            if string == "exp":
                return cls.INPUT_MODE_EXP_PEDAL
        if key == "outputMode":
            if string == "cv":
                return cls.OUTPUT_MODE_CV
            if string == "hp":
                return cls.OUTPUT_MODE_HEADPHONE

        logging.error("[profile] string_to_value called with invalid arg '%s' '%s'", key, string)
        return cls.DEFAULTS.get(key, None)

    @classmethod
    def value_to_string(cls, key, value):
        if key == "headphoneBypass":
            if value == True:
                return "on"
            if value == False:
                return "off"
        if key == "expPedalMode":
            if value == cls.EXPRESSION_PEDAL_MODE_RING:
                return "ring"
            if value == cls.EXPRESSION_PEDAL_MODE_TIP:
                return "tip"
        if key == "inputMode":
            if value == cls.INPUT_MODE_CV:
                return "cv"
            if value == cls.INPUT_MODE_EXP_PEDAL:
                return "exp"
        if key == "outputMode":
            if value == cls.OUTPUT_MODE_CV:
                return "cv"
            if value == cls.OUTPUT_MODE_HEADPHONE:
                return "hp"

        logging.error("[profile] value_to_string called with invalid arg '%s' '%s'", key, value)
        return ""

    def __init__(self, applyFn, hwdescriptor):
        self.applyFn  = applyFn
        self.platform = hwdescriptor.get("platform", None)
        self.changed  = False
        self.values   = self.DEFAULTS.copy()

        if os.path.exists(self.INTERMEDIATE_PROFILE_PATH):
            data = safe_json_load(self.INTERMEDIATE_PROFILE_PATH, dict)
            ensure_data_index_valid(data, 1)
            self.values.update(data)
        else:
            try:
                with TextFileFlusher(self.INTERMEDIATE_PROFILE_PATH) as fh:
                    json.dump(self.values, fh, indent=4)
            except IOError:
                pass

        fill_in_mixer_values(self.values, self.platform)
        IOLoop.instance().add_callback(self.apply_first)

    # -----------------------------------------------------------------------------------------------------------------
    # tools

    def apply_first(self):
        self.apply(True)

    def apply(self, isIntermediate):
        self.applyFn(self.values, isIntermediate)

    def get_index(self):
        return self.values['index']

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

    def get_exp_mode(self):
        return self.values['expPedalMode']

    def get_master_volume_channel_mode(self):
        return self.values['masterVolumeChannelMode']

    def get_midi_prgch_channel(self, what):
        if what == 'pedalboard':
            return self.values['midiChannelForPedalboardsNavigation']
        if what == 'snapshot':
            return self.values['midiChannelForSnapshotsNavigation']
        logging.error("[profile] get_midi_prgch_channel called with invalid arg %s", what)
        return self.MIDI_CHANNEL_NAVIGATION_OFF

    def get_midi_prgch_channels(self):
        return (self.values['midiChannelForPedalboardsNavigation'], self.values['midiChannelForSnapshotsNavigation'])

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
        if value not in (self.INPUT_MODE_CV, self.INPUT_MODE_EXP_PEDAL):
            logging.error("[profile] set_configurable_input_mode called with invalid value %s", value)
            return False
        os.system("/usr/bin/mod-amixer cvexp %s" % self.value_to_string('inputMode', value))
        return self._compare_and_set_value('inputMode', value)

    def set_configurable_output_mode(self, value):
        if value not in (self.OUTPUT_MODE_HEADPHONE, self.OUTPUT_MODE_CV):
            logging.error("[profile] set_configurable_output_mode called with invalid value %s", value)
            return False
        os.system("/usr/bin/mod-amixer cvhp %s" % self.value_to_string('outputMode', value))
        return self._compare_and_set_value('outputMode', value)

    def set_exp_mode(self, value):
        if value not in (self.EXPRESSION_PEDAL_MODE_RING, self.EXPRESSION_PEDAL_MODE_TIP):
            logging.error("[profile] set_exp_mode called with invalid value %s", value)
            return False
        os.system("/usr/bin/mod-amixer exppedal %s" % self.value_to_string('expPedalMode', value))
        return self._compare_and_set_value('expPedalMode', value)

    def set_headphone_bypass(self, value):
        if not isinstance(value, bool):
            logging.error("[profile] set_headphone_bypass called with non-boolean value")
            return False
        return self._compare_and_set_value('headphoneBypass', value)

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

    def set_tempo_bpb(self, value):
        if value < 1 or value > 16:
            logging.error("[profile] set_tempo_bpb called with invalid value %s", value)
            return False
        return self._compare_and_set_value('transportBPB', value)

    def set_tempo_bpm(self, value):
        if value < 20 or value > 280:
            logging.error("[profile] set_tempo_bpm called with invalid value %s", value)
            return False
        return self._compare_and_set_value('transportBPM', value)

    def set_send_midi_clk(self, value):
        if not isinstance(value, bool):
            logging.error("[profile] set_send_midi_clk called with non-boolean value")
            return False
        return self._compare_and_set_value('midiClockSend', value)

    # -----------------------------------------------------------------------------------------------------------------
    # persistent state

    def store(self, index):
        """Serialize the profile to JSON and store it on harddisk."""
        if index < 1 or index > 4:
            return False

        self.values['index'] = index

        # request and store mixer values
        fill_in_mixer_values(self.values, self.platform)

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
        if index < 1 or index > 4:
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
