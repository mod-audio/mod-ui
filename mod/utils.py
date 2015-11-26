#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from ctypes import *
import os

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
    print("..............", attr, ".....................", value, ":", type(value))
    return value

# ------------------------------------------------------------------------------------------------------------
# Convert a ctypes struct into a python dict

def structToDict(struct):
    return dict((attr, toPythonType(getattr(struct, attr), attr)) for attr, value in struct._fields_)

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
        ("brand", c_char_p),
        ("label", c_char_p),
        ("model", c_char_p),
        ("panel", c_char_p),
        ("color", c_char_p),
        ("knob", c_char_p),
        ("ports", POINTER(PluginGUIPort)),
    ]

class PluginGUI_Mini(Structure):
    _fields_ = [
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
        ("_custom", c_bool),
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

class PluginPreset(Structure):
    _fields_ = [
        ("valid", c_bool),
        ("uri", c_char_p),
        ("label", c_char_p),
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
        ("category", POINTER(c_char_p)),
        ("microVersion", c_int),
        ("minorVersion", c_int),
        ("release", c_int),
        ("version", c_char_p),
        ("stability", c_char_p),
        ("author", PluginAuthor),
        ("bundles", POINTER(c_char_p)),
        ("gui", PluginGUI),
        ("ports", PluginPorts),
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
        ("category", POINTER(c_char_p)),
        ("microVersion", c_int),
        ("minorVersion", c_int),
        ("release", c_int),
        ("gui", PluginGUI_Mini),
    ]

class PedalboardPluginPort(Structure):
    _fields_ = [
        ("valid", c_bool),
        ("symbol", c_char_p),
        ("value", c_float),
    ]

class PedalboardPlugin(Structure):
    _fields_ = [
        ("valid", c_bool),
        ("instance", c_char_p),
        ("uri", c_char_p),
        ("bypassed", c_bool),
        ("x", c_float),
        ("y", c_float),
        ("ports", POINTER(PedalboardPluginPort)),
    ]

class PedalboardConnection(Structure):
    _fields_ = [
        ("valid", c_bool),
        ("source", c_char_p),
        ("target", c_char_p),
    ]

class PedalboardHardware(Structure):
    _fields_ = [
        ("audio_ins", POINTER(c_char_p)),
        ("audio_outs", POINTER(c_char_p)),
        ("midi_ins", POINTER(c_char_p)),
        ("midi_outs", POINTER(c_char_p)),
    ]

class PedalboardInfo(Structure):
    _fields_ = [
        ("title", c_char_p),
        ("plugins", POINTER(PedalboardPlugin)),
        ("connections", POINTER(PedalboardConnection)),
        ("hardware", PedalboardHardware),
    ]

class PedalboardInfo_Mini(Structure):
    _fields_ = [
        ("valid", c_bool),
        ("uri", c_char_p),
        ("bundle", c_char_p),
        ("title", c_char_p),
    ]

class StatePortValue(Structure):
    _fields_ = [
        ("valid", c_bool),
        ("symbol", c_char_p),
        ("value", c_float),
    ]

c_struct_types = (PluginAuthor,
                  PluginGUI,
                  PluginGUI_Mini,
                  PluginPortRanges,
                  PluginPortUnits,
                  PluginPortsI,
                  PluginPorts,
                  PedalboardHardware)

c_structp_types = (POINTER(PluginGUIPort),
                   POINTER(PluginPortScalePoint),
                   POINTER(PluginPort),
                   POINTER(PluginPreset),
                   POINTER(PedalboardPlugin),
                   POINTER(PedalboardConnection),
                   POINTER(PedalboardPluginPort),
                   POINTER(StatePortValue))

c_structpp_types = (POINTER(POINTER(PluginInfo_Mini)),
                    POINTER(POINTER(PedalboardInfo_Mini)))

utils.init.argtypes = None
utils.init.restype  = None

utils.cleanup.argtypes = None
utils.cleanup.restype  = None

utils.is_bundle_loaded.argtypes = [c_char_p]
utils.is_bundle_loaded.restype  = c_bool

utils.add_bundle_to_lilv_world.argtypes = [c_char_p]
utils.add_bundle_to_lilv_world.restype  = POINTER(c_char_p)

utils.remove_bundle_from_lilv_world.argtypes = [c_char_p]
utils.remove_bundle_from_lilv_world.restype  = POINTER(c_char_p)

utils.get_all_plugins.argtypes = None
utils.get_all_plugins.restype  = POINTER(POINTER(PluginInfo_Mini))

utils.get_plugin_info.argtypes = [c_char_p]
utils.get_plugin_info.restype  = POINTER(PluginInfo)

utils.get_plugin_info_mini.argtypes = [c_char_p]
utils.get_plugin_info_mini.restype  = POINTER(PluginInfo_Mini)

utils.get_plugin_control_input_ports.argtypes = [c_char_p]
utils.get_plugin_control_input_ports.restype  = POINTER(PluginPort)

utils.get_all_pedalboards.argtypes = None
utils.get_all_pedalboards.restype  = POINTER(POINTER(PedalboardInfo_Mini))

utils.get_pedalboard_info.argtypes = [c_char_p]
utils.get_pedalboard_info.restype  = POINTER(PedalboardInfo)

utils.get_pedalboard_size.argtypes = [c_char_p]
utils.get_pedalboard_size.restype  = POINTER(c_int)

utils.get_state_port_values.argtypes = [c_char_p]
utils.get_state_port_values.restype  = POINTER(StatePortValue)

utils.file_uri_parse.argtypes = [c_char_p]
utils.file_uri_parse.restype  = c_char_p

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
def remove_bundle_from_lilv_world(bundlepath):
    return charPtrPtrToStringList(utils.remove_bundle_from_lilv_world(bundlepath.encode("utf-8")))

# ------------------------------------------------------------------------------------------------------------

# get all available plugins
# this triggers scanning of all plugins
# returned value depends on MODGUI_SHOW_MODE
def get_all_plugins():
    return structPtrPtrToList(utils.get_all_plugins())

# get a specific plugin
# NOTE: may throw
def get_plugin_info(uri):
    info = utils.get_plugin_info(uri.encode("utf-8"))
    if not info:
        raise Exception
    return structToDict(info.contents)

# get a specific plugin
# NOTE: may throw
def get_plugin_info_mini(uri):
    info = utils.get_plugin_info_mini(uri.encode("utf-8"))
    if not info:
        raise Exception
    return structToDict(info.contents)

def get_plugin_control_input_ports(uri):
    return structPtrToList(utils.get_plugin_control_input_ports(uri.encode("utf-8")))

# ------------------------------------------------------------------------------------------------------------

# get all available pedalboards (ie, plugins with pedalboard type)
def get_all_pedalboards(asDictionary):
    pbs = structPtrPtrToList(utils.get_all_pedalboards())
    if not asDictionary:
        return pbs
    return dict((pb['uri'], pb) for pb in pbs)

# Get a specific pedalboard
# NOTE: may throw
def get_pedalboard_info(bundle):
    info = utils.get_pedalboard_info(bundle.encode("utf-8"))
    if not info:
        raise Exception
    ret = structToDict(info.contents)
    from pprint import PrettyPrinter
    pp = PrettyPrinter(width=120, indent=4)
    pp.pprint(ret)
    return ret

# Get the size of a specific pedalboard
# Returns a 2-size array with width and height
# NOTE: may throw
def get_pedalboard_size(bundle):
    size = utils.get_pedalboard_size(bundle.encode("utf-8"))
    if not size:
        raise Exception
    width  = int(size[0])
    height = int(size[1])
    if 0 in (width, height):
        raise Exception
    return (width, height)

# Get port values from a plugin state
def get_state_port_values(state):
    values = structPtrToList(utils.get_state_port_values(state.encode("utf-8")))
    return dict((v['symbol'], v['value']) for v in values)

# ------------------------------------------------------------------------------------------------------------

# Get the absolute directory of a file or bundle uri.
def get_bundle_dirname(bundleuri):
    bundle = utils.file_uri_parse(bundleuri)

    if not bundle:
        raise IOError(bundleuri)
    if not os.path.exists(bundle):
        raise IOError(bundleuri)
    if os.path.isfile(bundle):
        bundle = os.path.dirname(bundle)

    return bundle

# ------------------------------------------------------------------------------------------------------------
