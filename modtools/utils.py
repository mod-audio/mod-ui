#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from ctypes import *
from mod import get_unique_name

# ------------------------------------------------------------------------------------------------------------
# Convert a ctypes c_char_p into a python string

def charPtrToString(charPtr):
    if not charPtr:
        return ""
    if isinstance(charPtr, str):
        return charPtr
    return charPtr.decode("utf-8", errors="ignore")

# ------------------------------------------------------------------------------------------------------------
# Convert a ctypes POINTER(c_char_p) into a python string list

def charPtrPtrToStringList(charPtrPtr):
    if not charPtrPtr:
        return []

    i       = 0
    charPtr = charPtrPtr[0]
    strList = []

    while charPtr:
        strList.append(charPtr.decode("utf-8", errors="ignore"))

        i += 1
        charPtr = charPtrPtr[i]

    return strList

# ------------------------------------------------------------------------------------------------------------
# Convert a ctypes POINTER(c_<num>) into a python number list

def numPtrToList(numPtr):
    if not numPtr:
        return []

    i       = 0
    num     = numPtr[0] #.value
    numList = []

    while num not in (0, 0.0):
        numList.append(num)

        i += 1
        num = numPtr[i] #.value

    return numList

# ------------------------------------------------------------------------------------------------------------

def structPtrToList(structPtr):
    if not structPtr:
        return []

    i      = 0
    ret    = []
    struct = structPtr[0]

    while struct.valid:
        ret.append(structToDict(struct))

        i     += 1
        struct = structPtr[i]

    return ret

def structPtrPtrToList(structPtr):
    if not structPtr:
        return []

    i      = 0
    ret    = []
    struct = structPtr[0]

    while struct:
        ret.append(structToDict(struct.contents))

        i     += 1
        struct = structPtr[i]

    return ret

# ------------------------------------------------------------------------------------------------------------
# Convert a ctypes value into a python one

c_int_types      = (c_int, c_int8, c_int16, c_int32, c_int64, c_uint, c_uint8, c_uint16, c_uint32, c_uint64, c_long, c_longlong)
c_float_types    = (c_float, c_double, c_longdouble)
c_intp_types     = tuple(POINTER(i) for i in c_int_types)
c_floatp_types   = tuple(POINTER(i) for i in c_float_types)
c_struct_types   = () # redefined below
c_structp_types  = () # redefined below
c_structpp_types = () # redefined below
c_union_types    = ()

def toPythonType(value, attr):
    #if value is None:
        #return ""
    if isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, bytes):
        return charPtrToString(value)
    if isinstance(value, c_intp_types) or isinstance(value, c_floatp_types):
        return numPtrToList(value)
    if isinstance(value, POINTER(c_char_p)):
        return charPtrPtrToStringList(value)
    if isinstance(value, c_struct_types):
        return structToDict(value)
    if isinstance(value, c_structp_types):
        return structPtrToList(value)
    if isinstance(value, c_structpp_types):
        return structPtrPtrToList(value)
    if isinstance(value, c_union_types):
        return unionToDict(value)
    print("..............", attr, ".....................", value, ":", type(value))
    return value

# ------------------------------------------------------------------------------------------------------------
# Convert a ctypes struct into a python dict

def structToDict(struct):
    return dict((attr, toPythonType(getattr(struct, attr), attr)) for attr, value in struct._fields_)

def unionToDict(struct):
    if isinstance(struct, PluginParameterRanges):
        if struct.type == b'f':
            return structToDict(struct.f)
        if struct.type == b'l':
            return structToDict(struct.l)
        if struct.type == b's':
            return {
                'minimum': "",
                'maximum': "",
                'default': charPtrToString(struct.s),
            }
    return None

# ------------------------------------------------------------------------------------------------------------

tryPath1 = os.path.join(os.path.dirname(__file__), "libmod_utils.so")
tryPath2 = os.path.join(os.path.dirname(__file__), "..", "utils", "libmod_utils.so")

if os.path.exists(tryPath1):
    utils = cdll.LoadLibrary(tryPath1)
else:
    utils = cdll.LoadLibrary(tryPath2)

class PluginAuthor(Structure):
    _fields_ = [
        ("name", c_char_p),
        ("homepage", c_char_p),
        ("email", c_char_p),
    ]

class PluginGUIPort(Structure):
    _fields_ = [
        ("valid", c_bool),
        ("index", c_uint),
        ("name", c_char_p),
        ("symbol", c_char_p),
    ]

class PluginGUI(Structure):
    _fields_ = [
        ("resourcesDirectory", c_char_p),
        ("iconTemplate", c_char_p),
        ("settingsTemplate", c_char_p),
        ("javascript", c_char_p),
        ("stylesheet", c_char_p),
        ("screenshot", c_char_p),
        ("thumbnail", c_char_p),
        ("documentation", c_char_p),
        ("brand", c_char_p),
        ("label", c_char_p),
        ("model", c_char_p),
        ("panel", c_char_p),
        ("color", c_char_p),
        ("knob", c_char_p),
        ("ports", POINTER(PluginGUIPort)),
        ("monitoredOutputs", POINTER(c_char_p)),
    ]

class PluginGUI_Mini(Structure):
    _fields_ = [
        ("resourcesDirectory", c_char_p),
        ("screenshot", c_char_p),
        ("thumbnail", c_char_p),
    ]

class PluginPortRanges(Structure):
    _fields_ = [
        ("minimum", c_float),
        ("maximum", c_float),
        ("default", c_float),
    ]

class PluginPortUnits(Structure):
    _fields_ = [
        ("label", c_char_p),
        ("render", c_char_p),
        ("symbol", c_char_p),
        ("_custom", c_bool), # internal, do not use
    ]

class PluginPortScalePoint(Structure):
    _fields_ = [
        ("valid", c_bool),
        ("value", c_float),
        ("label", c_char_p),
    ]

class PluginPort(Structure):
    _fields_ = [
        ("valid", c_bool),
        ("index", c_uint),
        ("name", c_char_p),
        ("symbol", c_char_p),
        ("ranges", PluginPortRanges),
        ("units", PluginPortUnits),
        ("comment", c_char_p),
        ("designation", c_char_p),
        ("properties", POINTER(c_char_p)),
        ("rangeSteps", c_int),
        ("scalePoints", POINTER(PluginPortScalePoint)),
        ("shortName", c_char_p),
    ]

class PluginPortsI(Structure):
    _fields_ = [
        ("input", POINTER(PluginPort)),
        ("output", POINTER(PluginPort)),
    ]

class PluginPorts(Structure):
    _fields_ = [
        ("audio", PluginPortsI),
        ("control", PluginPortsI),
        ("cv", PluginPortsI),
        ("midi", PluginPortsI),
    ]

class PluginLongParameterRanges(Structure):
    _fields_ = [
        ("minimum", c_int64),
        ("maximum", c_int64),
        ("default", c_int64),
    ]

class _PluginParameterRangesU(Union):
    _fields_ = [
        ("f", PluginPortRanges),
        ("l", PluginLongParameterRanges),
        ("s", c_char_p),
    ]

class PluginParameterRanges(Structure):
    _anonymous_ = ("u",)
    _fields_ = [
        ("type", c_char),
        ("u", _PluginParameterRangesU),
    ]

class PluginParameter(Structure):
    _fields_ = [
        ("valid", c_bool),
        ("readable", c_bool),
        ("writable", c_bool),
        ("uri", c_char_p),
        ("label", c_char_p),
        ("type", c_char_p),
        ("ranges", PluginParameterRanges),
        ("units", PluginPortUnits),
        ("comment", c_char_p),
        ("shortName", c_char_p),
        ("fileTypes", POINTER(c_char_p)),
        ("supportedExtensions", POINTER(c_char_p)),
    ]

class PluginPreset(Structure):
    _fields_ = [
        ("valid", c_bool),
        ("uri", c_char_p),
        ("label", c_char_p),
        ("path", c_char_p),
    ]

class PluginInfo(Structure):
    _fields_ = [
        ("valid", c_bool),
        ("uri", c_char_p),
        ("name", c_char_p),
        ("binary", c_char_p),
        ("brand", c_char_p),
        ("label", c_char_p),
        ("license", c_char_p),
        ("comment", c_char_p),
        ("buildEnvironment", c_char_p),
        ("category", POINTER(c_char_p)),
        ("microVersion", c_int),
        ("minorVersion", c_int),
        ("release", c_int),
        ("builder", c_int),
        ("licensed", c_int),
        ("version", c_char_p),
        ("stability", c_char_p),
        ("author", PluginAuthor),
        ("bundles", POINTER(c_char_p)),
        ("gui", PluginGUI),
        ("ports", PluginPorts),
        ("parameters", POINTER(PluginParameter)),
        ("presets", POINTER(PluginPreset)),
    ]

# a subset of PluginInfo
class NonCachedPluginInfo(Structure):
    _fields_ = [
        ("licensed", c_int),
        ("presets", POINTER(PluginPreset)),
    ]

class PluginInfo_Mini(Structure):
    _fields_ = [
        ("valid", c_bool),
        ("uri", c_char_p),
        ("name", c_char_p),
        ("brand", c_char_p),
        ("label", c_char_p),
        ("comment", c_char_p),
        ("buildEnvironment", c_char_p),
        ("category", POINTER(c_char_p)),
        ("microVersion", c_int),
        ("minorVersion", c_int),
        ("release", c_int),
        ("builder", c_int),
        ("licensed", c_int),
        ("gui", PluginGUI_Mini),
    ]

class PluginInfo_Essentials(Structure):
    _fields_ = [
        ("controlInputs", POINTER(PluginPort)),
        ("monitoredOutputs", POINTER(c_char_p)),
        ("parameters", POINTER(PluginParameter)),
        ("buildEnvironment", c_char_p),
        ("microVersion", c_int),
        ("minorVersion", c_int),
        ("release", c_int),
        ("builder", c_int),
    ]

class PedalboardMidiControl(Structure):
    _fields_ = [
        ("channel", c_int8),
        ("control", c_uint8),
        # ranges added in v1.2, flag needed for old format compatibility
        ("hasRanges", c_bool),
        ("minimum", c_float),
        ("maximum", c_float),
    ]

class PedalboardPluginPort(Structure):
    _fields_ = [
        ("valid", c_bool),
        ("symbol", c_char_p),
        ("value", c_float),
        ("midiCC", PedalboardMidiControl),
    ]

class PedalboardPlugin(Structure):
    _fields_ = [
        ("valid", c_bool),
        ("bypassed", c_bool),
        ("instanceNumber", c_int),
        ("instance", c_char_p),
        ("uri", c_char_p),
        ("bypassCC", PedalboardMidiControl),
        ("x", c_float),
        ("y", c_float),
        ("ports", POINTER(PedalboardPluginPort)),
        ("preset", c_char_p),
    ]

class PedalboardConnection(Structure):
    _fields_ = [
        ("valid", c_bool),
        ("source", c_char_p),
        ("target", c_char_p),
    ]

class PedalboardHardwareMidiPort(Structure):
    _fields_ = [
        ("valid", c_bool),
        ("symbol", c_char_p),
        ("name", c_char_p),
    ]

class PedalboardHardware(Structure):
    _fields_ = [
        ("audio_ins", c_uint),
        ("audio_outs", c_uint),
        ("cv_ins", c_uint),
        ("cv_outs", c_uint),
        ("midi_ins", POINTER(PedalboardHardwareMidiPort)),
        ("midi_outs", POINTER(PedalboardHardwareMidiPort)),
        ("serial_midi_in", c_bool),
        ("serial_midi_out", c_bool),
        ("midi_merger_out", c_bool),
        ("midi_broadcaster_in", c_bool),
    ]

kPedalboardTimeAvailableBPB     = 0x1
kPedalboardTimeAvailableBPM     = 0x2
kPedalboardTimeAvailableRolling = 0x4

class PedalboardTimeInfo(Structure):
    _fields_ = [
        ("available", c_uint),
        ("bpb", c_float),
        ("bpbCC", PedalboardMidiControl),
        ("bpm", c_float),
        ("bpmCC", PedalboardMidiControl),
        ("rolling", c_bool),
        ("rollingCC", PedalboardMidiControl),
    ]

class PedalboardInfo(Structure):
    _fields_ = [
        ("title", c_char_p),
        ("width", c_int),
        ("height", c_int),
        ("factory", c_bool),
        ("midi_separated_mode", c_bool),
        ("midi_loopback", c_bool),
        ("plugins", POINTER(PedalboardPlugin)),
        ("connections", POINTER(PedalboardConnection)),
        ("hardware", PedalboardHardware),
        ("timeInfo", PedalboardTimeInfo),
        ("version", c_uint),
    ]

class PedalboardInfo_Mini(Structure):
    _fields_ = [
        ("valid", c_bool),
        ("broken", c_bool),
        ("factory", c_bool),
        ("uri", c_char_p),
        ("bundle", c_char_p),
        ("title", c_char_p),
        ("version", c_uint),
    ]

class StatePortValue(Structure):
    _fields_ = [
        ("valid", c_bool),
        ("symbol", c_char_p),
        ("value", c_float),
    ]

class PedalboardPluginValues(Structure):
    _fields_ = [
        ("valid", c_bool),
        ("bypassed", c_bool),
        ("instance", c_char_p),
        ("preset", c_char_p),
        ("ports", POINTER(StatePortValue)),
    ]

class JackData(Structure):
    _fields_ = [
        ("cpuLoad", c_float),
        ("xruns", c_uint),
        ("rolling", c_bool),
        ("bpb", c_double),
        ("bpm", c_double),
    ]

JackBufSizeChanged = CFUNCTYPE(None, c_uint)
JackPortAppeared = CFUNCTYPE(None, c_char_p, c_bool)
JackPortDeleted = CFUNCTYPE(None, c_char_p)
TrueBypassStateChanged = CFUNCTYPE(None, c_bool, c_bool)
CvExpInputModeChanged = CFUNCTYPE(None, c_bool)

c_struct_types = (PluginAuthor,
                  PluginGUI,
                  PluginGUI_Mini,
                  PluginPortRanges,
                  PluginPortUnits,
                  PluginPortsI,
                  PluginPorts,
                  PluginLongParameterRanges,
                  PedalboardMidiControl,
                  PedalboardHardware,
                  PedalboardTimeInfo)

c_structp_types = (POINTER(PluginGUIPort),
                   POINTER(PluginPortScalePoint),
                   POINTER(PluginPort),
                   POINTER(PluginParameter),
                   POINTER(PluginPreset),
                   POINTER(PedalboardPlugin),
                   POINTER(PedalboardConnection),
                   POINTER(PedalboardPluginPort),
                   POINTER(PedalboardHardwareMidiPort),
                   POINTER(StatePortValue))

c_structpp_types = (POINTER(POINTER(PluginInfo_Mini)),
                    POINTER(POINTER(PedalboardInfo_Mini)))

c_union_types    = (PluginParameterRanges,)

utils.init.argtypes = None
utils.init.restype  = None

utils.cleanup.argtypes = None
utils.cleanup.restype  = None

utils.is_bundle_loaded.argtypes = [c_char_p]
utils.is_bundle_loaded.restype  = c_bool

utils.add_bundle_to_lilv_world.argtypes = [c_char_p]
utils.add_bundle_to_lilv_world.restype  = POINTER(c_char_p)

utils.remove_bundle_from_lilv_world.argtypes = [c_char_p, c_char_p]
utils.remove_bundle_from_lilv_world.restype  = POINTER(c_char_p)

utils.get_plugin_list.argtypes = None
utils.get_plugin_list.restype  = POINTER(c_char_p)

utils.get_all_plugins.argtypes = None
utils.get_all_plugins.restype  = POINTER(POINTER(PluginInfo_Mini))

utils.get_plugin_info.argtypes = [c_char_p]
utils.get_plugin_info.restype  = POINTER(PluginInfo)

utils.get_non_cached_plugin_info.argtypes = [c_char_p]
utils.get_non_cached_plugin_info.restype  = POINTER(NonCachedPluginInfo)

utils.get_plugin_gui.argtypes = [c_char_p]
utils.get_plugin_gui.restype  = POINTER(PluginGUI)

utils.get_plugin_gui_mini.argtypes = [c_char_p]
utils.get_plugin_gui_mini.restype  = POINTER(PluginGUI_Mini)

utils.get_plugin_control_inputs.argtypes = [c_char_p]
utils.get_plugin_control_inputs.restype  = POINTER(PluginPort)

utils.get_plugin_info_essentials.argtypes = [c_char_p]
utils.get_plugin_info_essentials.restype  = POINTER(PluginInfo_Essentials)

utils.is_plugin_preset_valid.argtypes = [c_char_p, c_char_p]
utils.is_plugin_preset_valid.restype  = c_bool

utils.rescan_plugin_presets.argtypes = [c_char_p]
utils.rescan_plugin_presets.restype  = None

utils.get_all_pedalboards.argtypes = None
utils.get_all_pedalboards.restype  = POINTER(POINTER(PedalboardInfo_Mini))

utils.get_broken_pedalboards.argtypes = None
utils.get_broken_pedalboards.restype  = POINTER(c_char_p)

utils.get_pedalboard_info.argtypes = [c_char_p]
utils.get_pedalboard_info.restype  = POINTER(PedalboardInfo)

utils.get_pedalboard_size.argtypes = [c_char_p]
utils.get_pedalboard_size.restype  = POINTER(c_int)

utils.get_pedalboard_plugin_values.argtypes = [c_char_p]
utils.get_pedalboard_plugin_values.restype  = POINTER(PedalboardPluginValues)

utils.get_state_port_values.argtypes = [c_char_p]
utils.get_state_port_values.restype  = POINTER(StatePortValue)

utils.list_plugins_in_bundle.argtypes = [c_char_p]
utils.list_plugins_in_bundle.restype  = POINTER(c_char_p)

utils.file_uri_parse.argtypes = [c_char_p]
utils.file_uri_parse.restype  = c_char_p

utils.set_cpu_affinity.argtypes = [c_int]
utils.set_cpu_affinity.restype  = None

utils.init_jack.argtypes = None
utils.init_jack.restype  = c_bool

utils.close_jack.argtypes = None
utils.close_jack.restype  = None

utils.get_jack_data.argtypes = [c_bool]
utils.get_jack_data.restype  = POINTER(JackData)

utils.get_jack_buffer_size.argtypes = None
utils.get_jack_buffer_size.restype  = c_uint

utils.set_jack_buffer_size.argtypes = [c_uint]
utils.set_jack_buffer_size.restype  = c_uint

utils.get_jack_sample_rate.argtypes = None
utils.get_jack_sample_rate.restype  = c_float

utils.get_jack_port_alias.argtypes = [c_char_p]
utils.get_jack_port_alias.restype  = c_char_p

utils.has_midi_beat_clock_sender_port.argtypes = None
utils.has_midi_beat_clock_sender_port.restype  = c_bool

utils.has_serial_midi_input_port.argtypes = None
utils.has_serial_midi_input_port.restype  = c_bool

utils.has_serial_midi_output_port.argtypes = None
utils.has_serial_midi_output_port.restype  = c_bool

utils.has_midi_merger_output_port.argtypes = None
utils.has_midi_merger_output_port.restype  = c_bool

utils.has_midi_broadcaster_input_port.argtypes = None
utils.has_midi_broadcaster_input_port.restype  = c_bool

utils.has_duox_split_spdif.argtypes = None
utils.has_duox_split_spdif.restype  = c_bool

utils.get_jack_hardware_ports.argtypes = [c_bool, c_bool]
utils.get_jack_hardware_ports.restype  = POINTER(c_char_p)

utils.connect_jack_ports.argtypes = [c_char_p, c_char_p]
utils.connect_jack_ports.restype  = c_bool

utils.connect_jack_midi_output_ports.argtypes = [c_char_p]
utils.connect_jack_midi_output_ports.restype  = c_bool

utils.disconnect_jack_ports.argtypes = [c_char_p, c_char_p]
utils.disconnect_jack_ports.restype  = c_bool

utils.disconnect_all_jack_ports.argtypes = [c_char_p]
utils.disconnect_all_jack_ports.restype  = c_bool

utils.reset_xruns.argtypes = None
utils.reset_xruns.restype  = None

utils.init_bypass.argtypes = None
utils.init_bypass.restype  = None

utils.get_truebypass_value.argtypes = [c_bool]
utils.get_truebypass_value.restype  = c_bool

utils.set_truebypass_value.argtypes = [c_bool, c_bool]
utils.set_truebypass_value.restype  = c_bool

utils.get_master_volume.argtypes = [c_bool]
utils.get_master_volume.restype  = c_float

utils.set_util_callbacks.argtypes = [JackBufSizeChanged, JackPortAppeared, JackPortDeleted, TrueBypassStateChanged]
utils.set_util_callbacks.restype  = None

utils.set_extra_util_callbacks.argtypes = [CvExpInputModeChanged]
utils.set_extra_util_callbacks.restype  = None

# ------------------------------------------------------------------------------------------------------------

# initialize
def init():
    utils.init()

# cleanup, cannot be used afterwards
def cleanup():
    utils.cleanup()

# ------------------------------------------------------------------------------------------------------------

# check if a bundle is loaded in our lilv world
def is_bundle_loaded(bundlepath):
    return bool(utils.is_bundle_loaded(bundlepath.encode("utf-8")))

# add a bundle to our lilv world
# returns uri list of added plugins
def add_bundle_to_lilv_world(bundlepath):
    return charPtrPtrToStringList(utils.add_bundle_to_lilv_world(bundlepath.encode("utf-8")))

# remove a bundle to our lilv world
# returns uri list of removed plugins
def remove_bundle_from_lilv_world(bundlepath, resource):
    return charPtrPtrToStringList(utils.remove_bundle_from_lilv_world(bundlepath.encode("utf-8"),
                                                                      resource.encode("utf-8") if resource else None))

# ------------------------------------------------------------------------------------------------------------

# get all available plugins
# this triggers short scanning of all plugins
def get_plugin_list():
    return charPtrPtrToStringList(utils.get_plugin_list())

# get all available plugins
# this triggers short scanning of all plugins
def get_all_plugins():
    return structPtrPtrToList(utils.get_all_plugins())

# get a specific plugin
# NOTE: may throw
def get_plugin_info(uri):
    info = utils.get_plugin_info(uri.encode("utf-8"))
    if not info:
        raise Exception
    return structToDict(info.contents)

# get a specific plugin (non-cached specific info)
# NOTE: may throw
def get_non_cached_plugin_info(uri):
    info = utils.get_non_cached_plugin_info(uri.encode("utf-8"))
    if not info:
        raise Exception
    return structToDict(info.contents)

# get a specific plugin's modgui
# NOTE: may throw
def get_plugin_gui(uri):
    info = utils.get_plugin_gui(uri.encode("utf-8"))
    if not info:
        raise Exception
    return structToDict(info.contents)

# get a specific plugin's modgui (mini)
# NOTE: may throw
def get_plugin_gui_mini(uri):
    info = utils.get_plugin_gui_mini(uri.encode("utf-8"))
    if not info:
        raise Exception
    return structToDict(info.contents)

def get_plugin_control_inputs(uri):
    return structPtrToList(utils.get_plugin_control_inputs(uri.encode("utf-8")))

# get essential plugin info for host control (control inputs, monitored outputs, parameters and build environment)
def get_plugin_info_essentials(uri):
    info = utils.get_plugin_info_essentials(uri.encode("utf-8"))
    if not info:
        return {
            'error': True,
            'controlInputs': [],
            'monitoredOutputs': [],
            'parameters': [],
            'buildEnvironment': '',
            'microVersion': 0,
            'minorVersion': 0,
            'release': 0,
            'builder': 0,
        }
    return structToDict(info.contents)

# check if a plugin preset uri is valid (must exist)
def is_plugin_preset_valid(plugin, preset):
    return bool(utils.is_plugin_preset_valid(plugin.encode("utf-8"), preset.encode("utf-8")))

# trigger a preset rescan for a plugin the next time it's loaded
def rescan_plugin_presets(uri):
    utils.rescan_plugin_presets(uri.encode("utf-8"))

# ------------------------------------------------------------------------------------------------------------

_allpedalboards = None

# get all available pedalboards (ie, plugins with pedalboard type)
def get_all_pedalboards():
    global _allpedalboards
    if _allpedalboards is None:
        pbs = structPtrPtrToList(utils.get_all_pedalboards())
        utitles = []
        for pb in pbs:
            if not pb['valid']:
                continue
            if pb['factory']:
                continue
            ntitle = get_unique_name(pb['title'], utitles)
            if ntitle is not None:
                pb['title'] = ntitle
            utitles.append(pb['title'])
        _allpedalboards = pbs
    return _allpedalboards

# handy function to reset our last call value
def reset_get_all_pedalboards_cache():
    global _allpedalboards
    _allpedalboards = None

# handy function to update cached pedalboard version
def update_cached_pedalboard_version(bundle):
    global _allpedalboards
    if _allpedalboards is None:
        return
    for pedalboard in _allpedalboards:
        if pedalboard['bundle'] == bundle:
            pedalboard['version'] += 1
            return
    print("ERROR: update_cached_pedalboard_version() failed", bundle)

# handy function to get only the names from all user pedalboards
def get_all_user_pedalboard_names():
    return tuple(pb['title'] for pb in get_all_pedalboards() if not pb['factory'])

# get all currently "broken" pedalboards (ie, pedalboards which contain unavailable plugins)
def get_broken_pedalboards():
    return charPtrPtrToStringList(utils.get_broken_pedalboards())

# Get a specific pedalboard
# NOTE: may throw
def get_pedalboard_info(bundle):
    info = utils.get_pedalboard_info(bundle.encode("utf-8"))
    if not info:
        raise Exception
    return structToDict(info.contents)

# Get the size of a specific pedalboard
# Returns a 2-size array with width and height
# NOTE: may throw
def get_pedalboard_size(bundle):
    size = utils.get_pedalboard_size(bundle.encode("utf-8"))
    if not size:
        raise Exception
    width  = int(size[0])
    height = int(size[1])
    return (width, height)

# Get plugin port values of a pedalboard
def get_pedalboard_plugin_values(bundle):
    return structPtrToList(utils.get_pedalboard_plugin_values(bundle.encode("utf-8")))

# Get port values from a plugin state
def get_state_port_values(state):
    values = structPtrToList(utils.get_state_port_values(state.encode("utf-8")))
    return dict((v['symbol'], v['value']) for v in values)

# list plugins present in a single bundle
def list_plugins_in_bundle(bundle):
    return charPtrPtrToStringList(utils.list_plugins_in_bundle(bundle.encode("utf-8")))

# ------------------------------------------------------------------------------------------------------------

# Get the absolute directory of a file or bundle uri.
def get_bundle_dirname(bundleuri):
    bundle = charPtrToString(utils.file_uri_parse(bundleuri))

    if not bundle:
        raise IOError(bundleuri)
    if not os.path.exists(bundle):
        raise IOError(bundleuri)
    if os.path.isfile(bundle):
        bundle = os.path.dirname(bundle)

    return bundle

# ------------------------------------------------------------------------------------------------------------
# helper utilities

def set_cpu_affinity(cpu):
    utils.set_cpu_affinity(cpu)

# ------------------------------------------------------------------------------------------------------------
# jack stuff

def init_jack():
    return bool(utils.init_jack())

def close_jack():
    utils.close_jack()

def get_jack_data(withTransport):
    data = utils.get_jack_data(withTransport)
    if not data:
        raise Exception
    return {
        'cpuLoad': data.contents.cpuLoad,
        'xruns'  : data.contents.xruns,
        'rolling': data.contents.rolling,
        'bpb'    : data.contents.bpb,
        'bpm'    : data.contents.bpm
    }

def get_jack_buffer_size():
    return int(utils.get_jack_buffer_size())

def set_jack_buffer_size(size):
    return int(utils.set_jack_buffer_size(size))

def get_jack_sample_rate():
    return float(utils.get_jack_sample_rate())

def get_jack_port_alias(portname):
    return charPtrToString(utils.get_jack_port_alias(portname.encode("utf-8")))

def has_midi_beat_clock_sender_port():
    return bool(utils.has_midi_beat_clock_sender_port())

def has_serial_midi_input_port():
    return bool(utils.has_serial_midi_input_port())

def has_serial_midi_output_port():
    return bool(utils.has_serial_midi_output_port())

def has_midi_merger_output_port():
    return bool(utils.has_midi_merger_output_port())

def has_midi_broadcaster_input_port():
    return bool(utils.has_midi_broadcaster_input_port())

def has_duox_split_spdif():
    return bool(utils.has_duox_split_spdif())

def get_jack_hardware_ports(isAudio, isOutput):
    return charPtrPtrToStringList(utils.get_jack_hardware_ports(isAudio, isOutput))

def connect_jack_ports(port1, port2):
    return bool(utils.connect_jack_ports(port1.encode("utf-8"), port2.encode("utf-8")))

def connect_jack_midi_output_ports(port):
    return bool(utils.connect_jack_midi_output_ports(port.encode("utf-8")))

def disconnect_jack_ports(port1, port2):
    return bool(utils.disconnect_jack_ports(port1.encode("utf-8"), port2.encode("utf-8")))

def disconnect_all_jack_ports(port):
    return bool(utils.disconnect_all_jack_ports(port.encode("utf-8")))

def reset_xruns():
    utils.reset_xruns()

# ------------------------------------------------------------------------------------------------------------
# alsa stuff

def init_bypass():
    utils.init_bypass()

def get_truebypass_value(right):
    return bool(utils.get_truebypass_value(right))

def set_truebypass_value(right, bypassed):
    return bool(utils.set_truebypass_value(right, bypassed))

def get_master_volume(right):
    return float(utils.get_master_volume(right))

# ------------------------------------------------------------------------------------------------------------
# callbacks

global bufSizeChangedCb, portAppearedCb, portDeletedCb, trueBypassChangedCb
bufSizeChangedCb = portAppearedCb = portDeletedCb = trueBypassChangedCb = None

def set_util_callbacks(bufSizeChanged, portAppeared, portDeleted, trueBypassChanged):
    global bufSizeChangedCb, portAppearedCb, portDeletedCb, trueBypassChangedCb
    bufSizeChangedCb    = JackBufSizeChanged(bufSizeChanged)
    portAppearedCb      = JackPortAppeared(portAppeared)
    portDeletedCb       = JackPortDeleted(portDeleted)
    trueBypassChangedCb = TrueBypassStateChanged(trueBypassChanged)
    utils.set_util_callbacks(bufSizeChangedCb, portAppearedCb, portDeletedCb, trueBypassChangedCb)

# ------------------------------------------------------------------------------------------------------------
# special case until HMI<->system comm is not in place yet

global cvExpInputModeChangedCb
cvExpInputModeChangedCb = None

def set_extra_util_callbacks(cvExpInputModeChanged):
    global cvExpInputModeChangedCb
    cvExpInputModeChangedCb = CvExpInputModeChanged(cvExpInputModeChanged)
    utils.set_extra_util_callbacks(cvExpInputModeChangedCb)

# ------------------------------------------------------------------------------------------------------------
# set process name

def set_process_name(newname):
    PR_SET_NAME = 15
    try:
        libc = cdll.LoadLibrary("libc.so.6")
    except:
        return
    libc.prctl.argtypes = [c_int, c_void_p, c_int, c_int, c_int]
    libc.prctl.restype  = c_int
    libc.prctl(PR_SET_NAME, newname.encode("utf-8"), 0, 0, 0)

# ------------------------------------------------------------------------------------------------------------
