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
# Convert a ctypes value into a python one

c_int_types    = (c_int, c_int8, c_int16, c_int32, c_int64, c_uint, c_uint8, c_uint16, c_uint32, c_uint64, c_long, c_longlong)
c_float_types  = (c_float, c_double, c_longdouble)
c_intp_types   = tuple(POINTER(i) for i in c_int_types)
c_floatp_types = tuple(POINTER(i) for i in c_float_types)

def toPythonType(value, attr):
    if isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, bytes):
        return charPtrToString(value)
    if isinstance(value, c_intp_types) or isinstance(value, c_floatp_types):
        return numPtrToList(value)
    if isinstance(value, POINTER(c_char_p)):
        return charPtrPtrToStringList(value)
    if isinstance(value, Structure):
        return structToDict(value)
    print("..............", attr, ".....................", value, ":", type(value))
    return value

# ------------------------------------------------------------------------------------------------------------
# Convert a ctypes struct into a python dict

def structToDict(struct):
    return dict((attr, toPythonType(getattr(struct, attr), attr)) for attr, value in struct._fields_)

# ------------------------------------------------------------------------------------------------------------

utils = cdll.LoadLibrary(os.path.join(os.path.dirname(__file__), "..", "utils", "libmod_utils.so"))

class PluginAuthor(Structure):
    _fields_ = [
        ("name", c_char_p),
    ]

class PluginGUI(Structure):
    _fields_ = [
        ("dummy", c_char),
    ]

class PluginInfo(Structure):
    _fields_ = [
        ("valid", c_bool),
        ("uri", c_char_p),
        ("name", c_char_p),
        ("binary", c_char_p),
        ("license", c_char_p),
        ("comment", c_char_p),
        ("category", POINTER(c_char_p)),
        ("author", PluginAuthor),
        ("gui", PluginGUI),
    ]

class PedalboardInfo(Structure):
    _fields_ = [
        ("valid", c_bool),
    ]

utils.init.argtypes = None
utils.init.restype  = None

utils.add_bundle_to_lilv_world.argtypes = [c_char_p]
utils.add_bundle_to_lilv_world.restype  = c_bool

utils.remove_bundle_from_lilv_world.argtypes = [c_char_p]
utils.remove_bundle_from_lilv_world.restype  = c_bool

utils.get_all_plugins.argtypes = None
utils.get_all_plugins.restype  = POINTER(POINTER(PluginInfo))

utils.get_plugin_info.argtypes = [c_char_p]
utils.get_plugin_info.restype  = POINTER(PluginInfo)

utils.get_all_pedalboards.argtypes = None
utils.get_all_pedalboards.restype  = POINTER(POINTER(PedalboardInfo))

utils.get_pedalboard_info.argtypes = [c_char_p]
utils.get_pedalboard_info.restype  = POINTER(PedalboardInfo)

utils.get_pedalboard_name.argtypes = [c_char_p]
utils.get_pedalboard_name.restype  = c_char_p

# ------------------------------------------------------------------------------------------------------------

# initialize
def init():
    utils.init()

# add a bundle to our lilv world
# returns true if the bundle was added
def add_bundle_to_lilv_world(bundlepath, returnPlugins = False):
    ret = utils.add_bundle_to_lilv_world(bundlepath.encode("utf-8"))
    return [] if returnPlugins else ret

# remove a bundle to our lilv world
# returns true if the bundle was removed
def remove_bundle_from_lilv_world(bundlepath, returnPlugins = False):
    ret = utils.remove_bundle_from_lilv_world(bundlepath.encode("utf-8"))
    return [] if returnPlugins else ret

# get all available plugins
# this triggers scanning of all plugins
# returned value depends on MODGUI_SHOW_MODE
def get_all_plugins():
    plugs = utils.get_all_plugins()

    if not plugs:
        return []

    i    = 0
    ret  = []
    plug = plugs[0]

    while plug:
        ret.append(structToDict(plug.contents))
        i   += 1
        plug = plugs[i]

    return ret

# get a specific plugin
# NOTE: may throw
def get_plugin_info(uri):
    info = utils.get_plugin_info(uri.encode("utf-8"))
    if not info:
        raise Exception
    return structToDict(info)

# ------------------------------------------------------------------------------------------------------------

# get all available pedalboards (ie, plugins with pedalboard type)
def get_all_pedalboards(asDictionary):
    pbs = utils.get_all_pedalboards()
    ret = {} if asDictionary else []
    # TODO
    return ret

# Get info from an lv2 bundle
# @a bundle is a string, consisting of a directory in the filesystem (absolute pathname).
# NOTE: may throw
def get_pedalboard_info(bundle):
    info = utils.get_pedalboard_info(bundle.encode("utf-8"))
    if not info:
        raise Exception
    return structToDict(info)

# Faster version of get_pedalboard_info when we just need to know the pedalboard name
# @a bundle is a string, consisting of a directory in the filesystem (absolute pathname).
def get_pedalboard_name(bundle):
    return charPtrToString(utils.get_pedalboard_name(bundle.encode("utf-8")))

# ------------------------------------------------------------------------------------------------------------
