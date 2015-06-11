#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ------------------------------------------------------------------------------------------------------------
# Imports

import json
import lilv
import os

# ------------------------------------------------------------------------------------------------------------
# Utilities

def LILV_FOREACH(collection, func):
    itr = collection.begin()
    while itr:
        yield func(collection.get(itr))
        itr = collection.next(itr)

class NS(object):
    def __init__(self, world, base):
        self.world = world
        self.base = base
        self._cache = {}

    def __getattr__(self, attr):
        if attr.endswith("_"):
            attr = attr[:-1]
        if attr not in self._cache:
            self._cache[attr] = lilv.Node(self.world.new_uri(self.base+attr))
        return self._cache[attr]

# ------------------------------------------------------------------------------------------------------------

def get_category(nodes):
    category_indexes = {
        'DelayPlugin': ['Delay'],
        'DistortionPlugin': ['Distortion'],
        'WaveshaperPlugin': ['Distortion', 'Waveshaper'],
        'DynamicsPlugin': ['Dynamics'],
        'AmplifierPlugin': ['Dynamics', 'Amplifier'],
        'CompressorPlugin': ['Dynamics', 'Compressor'],
        'ExpanderPlugin': ['Dynamics', 'Expander'],
        'GatePlugin': ['Dynamics', 'Gate'],
        'LimiterPlugin': ['Dynamics', 'Limiter'],
        'FilterPlugin': ['Filter'],
        'AllpassPlugin': ['Filter', 'Allpass'],
        'BandpassPlugin': ['Filter', 'Bandpass'],
        'CombPlugin': ['Filter', 'Comb'],
        'EQPlugin': ['Filter', 'Equaliser'],
        'MultiEQPlugin': ['Filter', 'Equaliser', 'Multiband'],
        'ParaEQPlugin': ['Filter', 'Equaliser', 'Parametric'],
        'HighpassPlugin': ['Filter', 'Highpass'],
        'LowpassPlugin': ['Filter', 'Lowpass'],
        'GeneratorPlugin': ['Generator'],
        'ConstantPlugin': ['Generator', 'Constant'],
        'InstrumentPlugin': ['Generator', 'Instrument'],
        'OscillatorPlugin': ['Generator', 'Oscillator'],
        'ModulatorPlugin': ['Modulator'],
        'ChorusPlugin': ['Modulator', 'Chorus'],
        'FlangerPlugin': ['Modulator', 'Flanger'],
        'PhaserPlugin': ['Modulator', 'Phaser'],
        'ReverbPlugin': ['Reverb'],
        'SimulatorPlugin': ['Simulator'],
        'SpatialPlugin': ['Spatial'],
        'SpectralPlugin': ['Spectral'],
        'PitchPlugin': ['Spectral', 'Pitch Shifter'],
        'UtilityPlugin': ['Utility'],
        'AnalyserPlugin': ['Utility', 'Analyser'],
        'ConverterPlugin': ['Utility', 'Converter'],
        'FunctionPlugin': ['Utility', 'Function'],
        'MixerPlugin': ['Utility', 'Mixer'],
    }

    def fill_in_category(node):
        category = node.as_string().replace("http://lv2plug.in/ns/lv2core#","")
        if category in category_indexes.keys():
            return category_indexes[category]
        return []
    return [cat for catlist in LILV_FOREACH(nodes, fill_in_category) for cat in catlist]

def get_port_data(port, subj):
    nodes = port.get_value(subj.me)
    data  = []

    it = lilv.lilv_nodes_begin(nodes)
    while not lilv.lilv_nodes_is_end(nodes, it):
        dat = lilv.lilv_nodes_get(nodes, it)
        it  = lilv.lilv_nodes_next(nodes, it)
        if data is None:
            continue
        data.append(lilv.lilv_node_as_string(dat))

    return data

def get_port_unit(miniuri):
  # using label, render, symbol
  units = {
      's': ["seconds", "%f s", "s"],
      'ms': ["milliseconds", "%f ms", "ms"],
      'min': ["minutes", "%f mins", "min"],
      'bar': ["bars", "%f bars", "bars"],
      'beat': ["beats", "%f beats", "beats"],
      'frame': ["audio frames", "%f frames", "frames"],
      'm': ["metres", "%f m", "m"],
      'cm': ["centimetres", "%f cm", "cm"],
      'mm': ["millimetres", "%f mm", "mm"],
      'km': ["kilometres", "%f km", "km"],
      'inch': ["inches", """%f\"""", "in"],
      'mile': ["miles", "%f mi", "mi"],
      'db': ["decibels", "%f dB", "dB"],
      'pc': ["percent", "%f%%", "%"],
      'coef': ["coefficient", "* %f", ""],
      'hz': ["hertz", "%f Hz", "Hz"],
      'khz': ["kilohertz", "%f kHz", "kHz"],
      'mhz': ["megahertz", "%f MHz", "MHz"],
      'bpm': ["beats per minute", "%f BPM", "BPM"],
      'oct': ["octaves", "%f octaves", "oct"],
      'cent': ["cents", "%f ct", "ct"],
      'semitone12TET': ["semitones", "%f semi", "semi"],
      'degree': ["degrees", "%f deg", "deg"],
      'midiNote': ["MIDI note", "MIDI note %d", "note"],
  }
  if miniuri in units.keys():
      return units[miniuri]
  return ("","","")

# ------------------------------------------------------------------------------------------------------------
# get_bundle_dirname

def get_bundle_dirname(bundleuri):
    bundle = lilv.lilv_uri_to_path(bundleuri)

    if not os.path.exists(bundle):
        raise IOError(bundleuri)
    if os.path.isfile(bundle):
        bundle = os.path.dirname(bundle)

    return bundle

# ------------------------------------------------------------------------------------------------------------
# get_pedalboard_info

# Get info from an lv2 bundle
# @a bundle is a string, consisting of a directory in the filesystem (absolute pathname).
def get_pedalboard_info(bundle):
    # lilv wants the last character as the separator
    if not bundle.endswith(os.sep):
        bundle += os.sep

    # Create our own unique lilv world
    # We'll load a single bundle and get all plugins from it
    world = lilv.World()

    # this is needed when loading specific bundles instead of load_all
    # (these functions are not exposed via World yet)
    lilv.lilv_world_load_specifications(world.me)
    lilv.lilv_world_load_plugin_classes(world.me)

    # convert bundle string into a lilv node
    bundlenode = lilv.lilv_new_file_uri(world.me, None, bundle)

    # load the bundle
    world.load_bundle(bundlenode)

    # free bundlenode, no longer needed
    lilv.lilv_node_free(bundlenode)

    # get all plugins in the bundle
    plugins = world.get_all_plugins()

    # make sure the bundle includes 1 and only 1 plugin (the pedalboard)
    if plugins.size() != 1:
        raise Exception('get_pedalboard_info(%s) - bundle has 0 or > 1 plugin'.format(bundle))

    # no indexing in python-lilv yet, just get the first item
    plugin = None
    for p in plugins:
        plugin = p
        break

    if plugin is None:
        raise Exception('get_pedalboard_info(%s) - failed to get plugin, you are using an old lilv!'.format(bundle))

    # define the needed stuff
    rdf      = NS(world, lilv.LILV_NS_RDF)
    lv2core  = NS(world, lilv.LILV_NS_LV2)
    ingen    = NS(world, "http://drobilla.net/ns/ingen#")
    modpedal = NS(world, "http://portalmod.com/ns/modpedal#")

    # check if the plugin is a pedalboard
    def fill_in_type(node):
        return node.as_string()
    plugin_types = [i for i in LILV_FOREACH(plugin.get_value(rdf.type_), fill_in_type)]

    if "http://portalmod.com/ns/modpedal#Pedalboard" not in plugin_types:
        raise Exception('get_pedalboard_info(%s) - plugin has no mod:Pedalboard type'.format(bundle))

    # let's get all the info now
    ingenarcs   = []
    ingenblocks = []

    info = {
        'name'  : plugin.get_name().as_string(),
        'uri'   : plugin.get_uri().as_string(),
        'author': plugin.get_author_name().as_string() or "", # Might be empty
        'hardware': {
            # we save this info later
            'audio': {
                'ins' : 0,
                'outs': 0
             },
            'cv': {
                'ins' : 0,
                'outs': 0
             },
            'midi': {
                'ins' : 0,
                'outs': 0
             }
        },
        'size': {
            'width' : plugin.get_value(modpedal.width).get_first().as_int(),
            'height': plugin.get_value(modpedal.height).get_first().as_int(),
        },
        'screenshot' : os.path.basename(plugin.get_value(modpedal.screenshot).get_first().as_string()),
        'thumbnail'  : os.path.basename(plugin.get_value(modpedal.thumbnail).get_first().as_string()),
        'connections': [], # we save this info later
        'plugins'    : []  # we save this info later
    }

    # connections
    arcs = plugin.get_value(ingen.arc)
    it = arcs.begin()
    while not arcs.is_end(it):
        arc = arcs.get(it)
        it  = arcs.next(it)

        if arc.me is None:
            continue

        head = lilv.lilv_world_get(world.me, arc.me, ingen.head.me, None)
        tail = lilv.lilv_world_get(world.me, arc.me, ingen.tail.me, None)

        if head is None or tail is None:
            continue

        ingenarcs.append({
            "source": lilv.lilv_uri_to_path(lilv.lilv_node_as_string(tail)).replace(bundle,"",1),
            "target": lilv.lilv_uri_to_path(lilv.lilv_node_as_string(head)).replace(bundle,"",1)
        })

    # hardware ports
    handled_port_uris = []
    ports = plugin.get_value(lv2core.port)
    it = ports.begin()
    while not ports.is_end(it):
        port = ports.get(it)
        it   = ports.next(it)

        if port.me is None:
            continue

        # check if we already handled this port
        port_uri = port.as_uri()
        if port_uri in handled_port_uris:
            continue
        handled_port_uris.append(port_uri)

        # get types
        port_types = lilv.lilv_world_find_nodes(world.me, port.me, rdf.type_.me, None)

        if port_types is None:
            continue

        portDir  = "" # input or output
        portType = "" # atom, audio or cv

        it2 = lilv.lilv_nodes_begin(port_types)
        while not lilv.lilv_nodes_is_end(port_types, it2):
            port_type = lilv.lilv_nodes_get(port_types, it2)
            it2 = lilv.lilv_nodes_next(port_types, it2)

            if port_type is None:
                continue

            port_type_uri = lilv.lilv_node_as_uri(port_type)

            if port_type_uri == "http://lv2plug.in/ns/lv2core#InputPort":
                portDir = "input"
            elif port_type_uri == "http://lv2plug.in/ns/lv2core#OutputPort":
                portDir = "output"
            elif port_type_uri == "http://lv2plug.in/ns/lv2core#AudioPort":
                portType = "audio"
            elif port_type_uri == "http://lv2plug.in/ns/lv2core#CVPort":
                portType = "cv"
            elif port_type_uri == "http://lv2plug.in/ns/ext/atom#AtomPort":
                portType = "atom"

        if not (portDir or portType):
            continue

        if portType == "audio":
            if portDir == "input":
                info['hardware']['audio']['ins'] += 1
            else:
                info['hardware']['audio']['outs'] += 1

        elif portType == "atom":
            if portDir == "input":
                info['hardware']['midi']['ins'] += 1
            else:
                info['hardware']['midi']['outs'] += 1

        elif portType == "cv":
            if portDir == "input":
                info['hardware']['cv']['ins'] += 1
            else:
                info['hardware']['cv']['outs'] += 1

    # plugins
    blocks = plugin.get_value(ingen.block)
    it = blocks.begin()
    while not blocks.is_end(it):
        block = blocks.get(it)
        it    = blocks.next(it)

        if block.me is None:
            continue

        protouri1 = lilv.lilv_world_get(world.me, block.me, lv2core.prototype.me, None)
        protouri2 = lilv.lilv_world_get(world.me, block.me, ingen.prototype.me, None)

        if protouri1 is not None:
            proto = protouri1
        elif protouri2 is not None:
            proto = protouri2
        else:
            continue

        uri = lilv.lilv_node_as_uri(proto)

        microver = lilv.lilv_world_get(world.me, block.me, lv2core.microVersion.me, None)
        minorver = lilv.lilv_world_get(world.me, block.me, lv2core.minorVersion.me, None)

        ingenblocks.append({
            "uri": uri,
            "x": lilv.lilv_node_as_float(lilv.lilv_world_get(world.me, block.me, ingen.canvasX.me, None)),
            "y": lilv.lilv_node_as_float(lilv.lilv_world_get(world.me, block.me, ingen.canvasY.me, None)),
            "microVersion": lilv.lilv_node_as_int(microver) if microver else 0,
            "minorVersion": lilv.lilv_node_as_int(minorver) if minorver else 0,
        })

    info['connections'] = ingenarcs
    info['plugins']     = ingenblocks

    return info

# ------------------------------------------------------------------------------------------------------------
# get_pedalboard_name

# Faster version of get_pedalboard_info when we just need to know the pedalboard name
# @a bundle is a string, consisting of a directory in the filesystem (absolute pathname).
def get_pedalboard_name(bundle):
    # lilv wants the last character as the separator
    if not bundle.endswith(os.sep):
        bundle += os.sep

    # Create our own unique lilv world
    # We'll load a single bundle and get all plugins from it
    world = lilv.World()

    # this is needed when loading specific bundles instead of load_all
    # (these functions are not exposed via World yet)
    lilv.lilv_world_load_specifications(world.me)
    lilv.lilv_world_load_plugin_classes(world.me)

    # convert bundle string into a lilv node
    bundlenode = lilv.lilv_new_file_uri(world.me, None, bundle)

    # load the bundle
    world.load_bundle(bundlenode)

    # free bundlenode, no longer needed
    lilv.lilv_node_free(bundlenode)

    # get all plugins in the bundle
    plugins = world.get_all_plugins()

    # make sure the bundle includes 1 and only 1 plugin (the pedalboard)
    if plugins.size() != 1:
        raise Exception('get_pedalboard_info(%s) - bundle has 0 or > 1 plugin'.format(bundle))

    # no indexing in python-lilv yet, just get the first item
    plugin = None
    for p in plugins:
        plugin = p
        break

    if plugin is None:
        raise Exception('get_pedalboard_info(%s) - failed to get plugin, you are using an old lilv!'.format(bundle))

    # define the needed stuff
    rdf      = NS(world, lilv.LILV_NS_RDF)
    lv2core  = NS(world, lilv.LILV_NS_LV2)
    ingen    = NS(world, "http://drobilla.net/ns/ingen#")
    modpedal = NS(world, "http://portalmod.com/ns/modpedal#")

    # check if the plugin is a pedalboard
    def fill_in_type(node):
        return node.as_string()
    plugin_types = [i for i in LILV_FOREACH(plugin.get_value(rdf.type_), fill_in_type)]

    if "http://portalmod.com/ns/modpedal#Pedalboard" not in plugin_types:
        raise Exception('get_pedalboard_info(%s) - plugin has no mod:Pedalboard type'.format(bundle))

    return plugin.get_name().as_string()

# ------------------------------------------------------------------------------------------------------------
# get_plugin_info

# Get info from a lilv plugin
# This is used in get_plugins_info below and MOD-SDK

def get_plugin_info(world, plugin):
    # define the needed stuff
    doap    = NS(world, lilv.LILV_NS_DOAP)
    rdf     = NS(world, lilv.LILV_NS_RDF)
    rdfs    = NS(world, lilv.LILV_NS_RDFS)
    lv2core = NS(world, lilv.LILV_NS_LV2)
    pprops  = NS(world, "http://lv2plug.in/ns/ext/port-props#")
    units   = NS(world, "http://lv2plug.in/ns/extensions/units#")
    modgui  = NS(world, "http://portalmod.com/ns/modgui#")

    global index
    index = -1

    # function for filling port info
    def fill_port_info(plugin, port):
        global index
        index += 1

        # port types
        types = [typ.rsplit("#",1)[-1].replace("Port","",1) for typ in get_port_data(port, rdf.type_)]

        # port value ranges
        ranges = {}

        # unit block
        uunit = lilv.lilv_nodes_get_first(port.get_value(units.unit.me))

        # contains unit
        if "Control" in types:
            if uunit is not None:
                uuri = lilv.lilv_node_as_uri(uunit)

                # using pre-existing lv2 unit
                if uuri is not None and uuri.startswith("http://lv2plug.in/ns/extensions/units#"):
                    ulabel, urender, usymbol = get_port_unit(uuri.replace("http://lv2plug.in/ns/extensions/units#","",1))

                # using custom unit
                else:
                    xlabel  = world.find_nodes(uunit, rdfs  .label.me, None).get_first()
                    xrender = world.find_nodes(uunit, units.render.me, None).get_first()
                    xsymbol = world.find_nodes(uunit, units.symbol.me, None).get_first()

                    ulabel  = xlabel .as_string() if xlabel .me else ""
                    urender = xrender.as_string() if xrender.me else ""
                    usymbol = xsymbol.as_string() if xsymbol.me else ""

            # no unit
            else:
                ulabel  = ""
                urender = ""
                usymbol = ""

            xdefault = lilv.lilv_nodes_get_first(port.get_value(lv2core.default.me))
            xminimum = lilv.lilv_nodes_get_first(port.get_value(lv2core.minimum.me))
            xmaximum = lilv.lilv_nodes_get_first(port.get_value(lv2core.maximum.me))

            if xminimum is not None and xmaximum is not None:
                ranges['minimum'] = lilv.lilv_node_as_float(xminimum)
                ranges['maximum'] = lilv.lilv_node_as_float(xmaximum)

                if xdefault is not None:
                    ranges['default'] = lilv.lilv_node_as_float(xdefault)

        return (types, {
            'index'  : index,
            'name'   : lilv.lilv_node_as_string(port.get_name()),
            'symbol' : lilv.lilv_node_as_string(port.get_symbol()),
            'ranges' : ranges,
            'units'  : {
                'label' : ulabel,
                'render': urender,
                'symbol': usymbol,
            } if "Control" in types and (ulabel or urender or usymbol) else {},
            'designation': (get_port_data(port, lv2core.designation) or [None])[0],
            'properties' : [typ.rsplit("#",1)[-1] for typ in get_port_data(port, lv2core.portProperty)],
            'rangeSteps' : (get_port_data(port, pprops.rangeSteps) or [None])[0],
            "scalePoints": [],
        })

    bundleuri = plugin.get_bundle_uri().as_string()
    microver  = plugin.get_value(lv2core.microVersion).get_first()
    minorver  = plugin.get_value(lv2core.minorVersion).get_first()
    modguigui = plugin.get_value(modgui.gui).get_first()

    if modguigui.me is not None:
        modgui_resdir = world.find_nodes(modguigui.me, modgui.resourcesDirectory.me, None).get_first()
        modgui_scrn   = world.find_nodes(modguigui.me, modgui.screenshot        .me, None).get_first()
        modgui_thumb  = world.find_nodes(modguigui.me, modgui.thumbnail         .me, None).get_first()
        modgui_icon   = world.find_nodes(modguigui.me, modgui.iconTemplate      .me, None).get_first()
        modgui_setts  = world.find_nodes(modguigui.me, modgui.settingsTemplate  .me, None).get_first()
        modgui_data   = world.find_nodes(modguigui.me, modgui.templateData      .me, None).get_first()

        iconTemplate = ""
        settingsTmpl = ""
        templateData = {}

        if modgui_icon.me:
            iconFile = lilv.lilv_uri_to_path(modgui_icon.as_string())
            if os.path.exists(iconFile):
                with open(iconFile, 'r') as fd:
                    iconTemplate = fd.read()
            del iconFile

        if modgui_setts.me:
            settingsFile = lilv.lilv_uri_to_path(modgui_setts.as_string())
            if os.path.exists(settingsFile):
                with open(settingsFile, 'r') as fd:
                    settingsTmpl = fd.read()
            del settingsFile

        if modgui_data.me:
            templateFile = lilv.lilv_uri_to_path(modgui_data.as_string())
            if os.path.exists(templateFile):
                with open(templateFile, 'r') as fd:
                    templateData = json.load(fd)
            del templateFile

    ports = {
        'audio':   { 'input': [], 'output': [] },
        'control': { 'input': [], 'output': [] }
    }

    for p in (plugin.get_port_by_index(i) for i in range(plugin.get_num_ports())):
        types, info = fill_port_info(plugin, p)

        isInput = "Input" in types
        types.remove("Input" if isInput else "Output")

        # FIXME: this is needed by SDK, but it's not pretty
        if "Control" in types:
            info['enumeration'] = bool("enumeration" in info['properties'])
            info['trigger'    ] = bool("trigger"     in info['properties'])
            info['toggled'    ] = bool("toggled"     in info['properties'])

        for typ in [typl.lower() for typl in types]:
            if typ not in ports.keys():
                ports[typ] = { 'input': [], 'output': [] }
            ports[typ]["input" if isInput else "output"].append(info)

    return {
        'name': plugin.get_name().as_string(),
        'uri' : plugin.get_uri().as_string(),
        'author': {
            'name'    : plugin.get_author_name().as_string() or "",
            'homepage': plugin.get_author_homepage().as_string() or "",
            'email'   : (plugin.get_author_email().as_string() or "").replace(bundleuri,"",1),
        },

        'ports': ports,

        'gui': {
            'resourcesDirectory': lilv.lilv_uri_to_path(modgui_resdir.as_string()) if modgui_resdir.me else "",
            'screenshot'        : lilv.lilv_uri_to_path(modgui_scrn  .as_string()) if modgui_scrn  .me else "",
            'thumbnail'         : lilv.lilv_uri_to_path(modgui_thumb .as_string()) if modgui_thumb .me else "",
            'iconTemplate'      : iconTemplate,
            'settingsTemplate'  : settingsTmpl,
            'templateData'      : templateData,
        } if modguigui.me is not None else {},

        'binary'  : lilv.lilv_uri_to_path(plugin.get_library_uri().as_string() or ""),
        'category': get_category(plugin.get_value(rdf.type_)),
        'license' : (plugin.get_value(doap.license).get_first().as_string() or "").replace(bundleuri,"",1),

        'description'  : plugin.get_value(rdfs.comment).get_first().as_string() or "",
        'documentation': plugin.get_value(lv2core.documentation).get_first().as_string() or "",
        'microVersion' : microver.as_int() if microver.me else 0,
        'minorVersion' : minorver.as_int() if minorver.me else 0,
    }

# ------------------------------------------------------------------------------------------------------------
# get_plugins_info

# Get plugin-related info from a list of lv2 bundles
# @a bundles is a list of strings, consisting of directories in the filesystem (absolute pathnames).
def get_plugins_info(bundles):
    # if empty, do nothing
    if len(bundles) == 0:
        raise Exception('get_plugins_info() - no bundles provided')

    # Create our own unique lilv world
    # We'll load the selected bundles and get all plugins from it
    world = lilv.World()

    # this is needed when loading specific bundles instead of load_all
    # (these functions are not exposed via World yet)
    lilv.lilv_world_load_specifications(world.me)
    lilv.lilv_world_load_plugin_classes(world.me)

    # load all bundles
    for bundle in bundles:
        # lilv wants the last character as the separator
        if not bundle.endswith(os.sep):
            bundle += os.sep

        # convert bundle string into a lilv node
        bundlenode = lilv.lilv_new_file_uri(world.me, None, bundle)

        # load the bundle
        world.load_bundle(bundlenode)

        # free bundlenode, no longer needed
        lilv.lilv_node_free(bundlenode)

    # get all plugins available in the selected bundles
    plugins = world.get_all_plugins()

    # make sure the bundles include something
    if plugins.size() == 0:
        raise Exception('get_plugins_info() - selected bundles have no plugins')

    # return all the info
    return [get_plugin_info(world, p) for p in plugins]

# ------------------------------------------------------------------------------------------------------------

if __name__ == '__main__':
    from sys import argv
    from pprint import pprint
    #get_plugins_info(argv[1:])
    for i in get_plugins_info(argv[1:]): pprint(i)

# ------------------------------------------------------------------------------------------------------------
