import os, hashlib, re, random, shutil, subprocess
import lilv
import hashlib

# LILV stuff

W = lilv.World()
W.load_all()

PLUGINS = W.get_all_plugins()

class NS(object):
    def __init__(self, base, world=W):
        self.base = base
        self.world = world
        self._cache = {}

    def __getattr__(self, attr):
        if attr.endswith("_"):
            attr = attr[:-1]
        if attr not in self._cache:
            self._cache[attr] = lilv.Node(self.world.new_uri(self.base+attr))
        return self._cache[attr]

def LILV_FOREACH(collection, func):
    l = []
    itr = collection.begin()
    while itr:
        yield func(collection.get(itr))
        itr = collection.next(itr)

doap = NS(lilv.LILV_NS_DOAP)
foaf = NS(lilv.LILV_NS_FOAF)
lilvns = NS(lilv.LILV_NS_LILV)
lv2core = NS(lilv.LILV_NS_LV2)
rdf = NS(lilv.LILV_NS_RDF)
rdfs = NS(lilv.LILV_NS_RDFS)
atom = NS("http://lv2plug.in/ns/ext/atom#")
units = NS("http://lv2plug.in/ns/extensions/units#")
pset = NS("http://lv2plug.in/ns/ext/presets#")
midi = NS("http://lv2plug.in/ns/ext/midi#")
pprops = NS("http://lv2plug.in/ns/ext/port-props#")
time = NS("http://lv2plug.in/ns/ext/time#")
modgui = NS("http://portalmod.com/ns/modgui#")
modpedal = NS("http://portalmod.com/ns/modpedal#")

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
        raise Exception('get_info_from_lv2_bundle(%s) - bundle has 0 or > 1 plugin'.format(bundle))

    # no indexing in python-lilv yet, just get the first item
    plugin = None
    for p in plugins:
        plugin = p
        break

    if plugin is None:
        raise Exception('get_info_from_lv2_bundle(%s) - failed to get plugin, you are using an old lilv!'.format(bundle))

    # define the needed stuff
    rdf = NS(lilv.LILV_NS_RDF, world)
    ingen = NS('http://drobilla.net/ns/ingen#', world)
    lv2core = NS(lilv.LILV_NS_LV2, world)
    modpedal = NS("http://portalmod.com/ns/modpedal#", world)

    # check if the plugin is a pedalboard
    def fill_in_type(node):
        return node.as_string()
    plugin_types = [i for i in LILV_FOREACH(plugin.get_value(rdf.type_), fill_in_type)]

    if "http://portalmod.com/ns/modpedal#Pedalboard" not in plugin_types:
        raise Exception('get_info_from_lv2_bundle(%s) - plugin has no mod:Pedalboard type'.format(bundle))

    # let's get all the info now
    ingenarcs   = []
    ingenblocks = []

    info = {
        'name':   plugin.get_value(modpedal.name).get_first().as_string(),
        'author': plugin.get_author_name().as_string() or '', # Might be empty
        'uri':    plugin.get_uri().as_string(),
        'hardware': {
            # we save this info later
            'audio': {
                'ins': 0,
                'outs': 0
             },
            'cv': {
                'ins': 0,
                'outs': 0
             },
            'midi': {
                'ins': 0,
                'outs': 0
             }
        },
        'size': {
            'width':  plugin.get_value(modpedal.width).get_first().as_int(),
            'height': plugin.get_value(modpedal.height).get_first().as_int(),
        },
        'screenshot': os.path.basename(plugin.get_value(modpedal.screenshot).get_first().as_string()),
        'thumbnail':  os.path.basename(plugin.get_value(modpedal.thumbnail).get_first().as_string()),
        'connections': [], # we save this info later
        'plugins':     []  # we save this info later
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
            "source": lilv.lilv_node_as_string(tail).replace("file://","",1).replace(bundle,"",1),
            "target": lilv.lilv_node_as_string(head).replace("file://","",1).replace(bundle,"",1)
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

        ingenblocks.append({
            "uri": uri,
            "x": lilv.lilv_node_as_float(lilv.lilv_world_get(world.me, block.me, ingen.canvasX.me, None)),
            "y": lilv.lilv_node_as_float(lilv.lilv_world_get(world.me, block.me, ingen.canvasY.me, None))
        })

    info['connections'] = ingenarcs
    info['plugins']     = ingenblocks

    return info

def get_pedalboards():
    def get_presets(p):
        presets = p.get_related(pset.Preset)
        def get_preset_data(preset):
            W.load_resource(preset.me)
            label = W.find_nodes(preset.me, rdfs.label.me, None).get_first().as_string()
            return dict(uri=preset.as_string(), label=label)
        return list(LILV_FOREACH(presets, get_preset_data))

    pedalboards = []

    for pedalboard in PLUGINS:
        # check if the plugin is a pedalboard
        def fill_in_type(node):
            return node.as_string()
        plugin_types = [i for i in LILV_FOREACH(pedalboard.get_value(rdf.type_), fill_in_type)]

        if "http://portalmod.com/ns/modpedal#Pedalboard" not in plugin_types:
            continue

        pedalboards.append({
            'bundlepath': lilv.lilv_uri_to_path(pedalboard.get_bundle_uri().as_string()),
            'uri':  pedalboard.get_uri().as_string(),
            'name': pedalboard.get_value(modpedal.name).get_first().as_string(),
            'screenshot': lilv.lilv_uri_to_path(pedalboard.get_value(modpedal.screenshot).get_first().as_string()),
            'thumbnail':  lilv.lilv_uri_to_path(pedalboard.get_value(modpedal.thumbnail).get_first().as_string()),
            'width':  pedalboard.get_value(modpedal.width).get_first().as_int(),
            'height': pedalboard.get_value(modpedal.height).get_first().as_int(),
            'presets': get_presets(pedalboard)
        })

    return pedalboards

def add_bundle_to_lilv_world(bundlepath):
    # lilv wants the last character as the separator
    if not bundlepath.endswith(os.sep):
        bundlepath += os.sep

    # convert bundle string into a lilv node
    bundlenode = lilv.lilv_new_file_uri(W.me, None, bundlepath)

    # load the bundle
    W.load_bundle(bundlenode)

    # free bundlenode, no longer needed
    lilv.lilv_node_free(bundlenode)

class PluginSerializer(object):
    def __init__(self, uri=None, plugin=None):
        if plugin:
            self.p = plugin
            uri = self.p.get_uri().as_string()
        else:
            self.p = PLUGINS.get_by_uri(W.new_uri(uri))
        self.uri = uri
        p = self.p
        self._modgui = p.get_value(modgui.gui).get_first()

        self.data = dict(
                _id="",
                binary=p.get_library_uri().as_string().replace("file://", ""),
                brand="",
                bufsize=128,
                category=get_category(p.get_value(rdf.type_)),
                description=None,
                developer=None,
                gui={},
                gui_structure={},
                hidden=False,
                label="",
                license=p.get_value(doap.license).get_first().as_string(),
                maintainer=dict(
                    homepage=p.get_author_homepage().as_string(),
                    mbox=p.get_author_email().as_string(),
                    name=p.get_author_name().as_string()),
                microVersion=self._get_micro_version(),
                minorVersion=self._get_minor_version(),
                name=p.get_name().as_string(),
                package=os.path.basename(os.path.dirname(p.get_bundle_uri().as_string())),
                package_id="",
                ports=self._get_ports(),
                presets=self._get_presets(),
                stability="",
                url=uri,
                version=None,
                )

        if self.has_modgui():
            self.data['gui_structure'] = dict(
                    iconTemplate=self._get_modgui('iconTemplate'),
                    resourcesDirectory=self._get_modgui('resourcesDirectory'),
                    screenshot=self._get_modgui('screenshot'),
                    settingsTemplate=self._get_modgui('settingsTemplate'),
                    templateData=self._get_modgui('templateData'),
                    thumbnail=self._get_modgui('thumbnail')
                )
            self.data['gui'] = self._get_gui_data()

        if self.data['license']:
            self.data['license'] = self.data['license'].split("/")[-1]
        minor = self.data['minorVersion']
        micro = self.data['microVersion']
        self.data['version'] = "%d.%d" % (micro, minor)

        if minor == 0 and micro == 0:
            self.data['stability'] = u'experimental'
        elif minor % 2 == 0 and micro % 2 == 0:
            self.data['stability'] = u'stable'
        elif minor % 2 == 0:
            self.data['stability'] = u'testing'
        else:
            self.data['stability'] = u'unstable'

        self.data['_id'] = hashlib.md5(uri.encode("utf-8")).hexdigest()[:24]

    def _get_file_data(self, fname, html=False, json=False):
        if fname is not None and os.path.exists(fname):
            f = open(fname)
            if html:
                return re.sub('<!--.+?-->', '', f.read()).strip()
            if json:
                import json as js
                return js.loads(f.read())
            return f.read()
        return None

    def _get_gui_data(self):
        d = dict(
            iconTemplate=self._get_file_data(self.data['gui_structure']['iconTemplate'], html=True),
            settingsTemplate=self._get_file_data(self.data['gui_structure']['settingsTemplate'], html=True),
            templateData=self._get_file_data(self.data['gui_structure']['templateData'], json=True),
            resourcesDirectory=self.data['gui_structure']['resourcesDirectory'],
            screenshot=self.data['gui_structure']['screenshot'],
            thumbnail=self.data['gui_structure']['thumbnail'],
            stylesheet=self._get_modgui('stylesheet')
        )
        return d

    def _get_presets(self):
        presets = self.p.get_related(pset.Preset)
        def get_preset_data(preset):
            W.load_resource(preset.me)
            label = W.find_nodes(preset.me, rdfs.label.me, None).get_first().as_string()
            return (preset.as_string(), dict(
                            uri  = preset.as_string(),
                            label=label,
                            ))
        return dict(LILV_FOREACH(presets, get_preset_data))

    def _get_modgui(self, predicate):
        if self._modgui.me is None:
            return ""
        pred = getattr(modgui, predicate)
        n = W.find_nodes(self._modgui.me, pred.me, None).get_first()
        return n.as_string().replace("file://", "") if n.as_string() is not None else n.as_string()

    def _get_micro_version(self):
        v = self.p.get_value(lv2core.microVersion).get_first().as_string()
        if v is not None and v.isdigit():
            return int(v)
        return 0

    def _get_minor_version(self):
        v = self.p.get_value(lv2core.minorVersion).get_first().as_string()
        if v is not None and v.isdigit():
            return int(v)
        return 0

    def _get_ports(self):
        ports = dict(
                audio=dict(
                    input=[],
                    output=[]
                    ),
                control=dict(
                    input=[],
                    output=[]
                    ),
                atom=dict(
                    input=[],
                    output=[]
                    ),
                midi=dict(
                    input=[],
                    output=[]
                    )
                )
        for idx in range(self.p.get_num_ports()):
            port = self.p.get_port_by_index(idx)
            port_dict = dict(
                            index=idx,
                            name=lilv.Node(port.get_name()).as_string(),
                            symbol=lilv.Node(port.get_symbol()).as_string()
                        )

            flow = typ = None

            if port.is_a(lv2core.InputPort.me):
                flow = 'input'
            elif port.is_a(lv2core.OutputPort.me):
                flow = 'output'

            if port.is_a(lv2core.AudioPort.me):
                typ = 'audio'
            elif port.is_a(lv2core.ControlPort.me):
                typ = 'control'
                port_dict.update(self._get_control_port_data(port))
            elif port.is_a(atom.AtomPort.me):
                if port.supports_event(midi.MidiEvent.me) and \
                        lilv.Nodes(port.get_value(atom.bufferType.me)).get_first() == atom.Sequence:
                    typ ='midi'
                else:
                    typ = 'atom'

            if flow is not None and typ is not None:
                ports[typ][flow].append(port_dict)
        return ports

    def _get_control_port_data(self, port):
        def get_value(pred, typ=None):
            value = lilv.Nodes(port.get_value(pred)).get_first().as_string()
            if typ is not None:
                try:
                    value = typ(value)
                except (ValueError, TypeError):
                    # TODO: should at least warn bad ttl
                    value = typ()
            return value

        d = dict(
            default=get_value(lv2core.default.me, float),
            minimum=get_value(lv2core.minimum.me, float),
            maximum=get_value(lv2core.maximum.me, float),

            enumeration=port.has_property(lv2core.enumeration.me),
            integer=port.has_property(lv2core.integer.me),
            logarithmic=port.has_property(pprops.logarithmic.me),
            trigger=port.has_property(pprops.trigger.me),
            toggled=port.has_property(lv2core.toggled.me),
            rangeSteps=port.has_property(pprops.rangeSteps.me),
            sampleRate=port.has_property(lv2core.sampleRate.me),
            tap_tempo = True if get_value(lv2core.designation.me) == time.beatsPerMinute.as_string() else False,
            )

        scale_points = lilv.ScalePoints(port.get_scale_points())
        def get_sp_data(sp):
            return dict(label=lilv.Node(sp.get_label()).as_string(),
                    value=float(lilv.Node(sp.get_value()).as_string()))
        d['scalePoints'] = list(LILV_FOREACH(scale_points, get_sp_data))

        d['unit'] = None
        unit = port.get_value(units.unit.me)
        if unit is not None:
            unit_dict = {}
            unit_node = lilv.Nodes(unit).get_first()
            unit_dict['label'] = W.find_nodes(unit_node.me, rdfs.label.me, None).get_first().as_string()
            unit_dict['render'] = W.find_nodes(unit_node.me, units.render.me, None).get_first().as_string()
            unit_dict['symbol'] = W.find_nodes(unit_node.me, rdfs.symbol.me, None).get_first().as_string()
            if unit_dict['label'] and unit_dict['render'] and unit_dict['symbol']:
                d['unit'] = unit_dict
        return d

    def has_modgui(self):
        return self._modgui.me is not None

    def save_json(self, directory):
        import json
        json.dump(self.data, open(os.path.join(directory, self.data['_id']), 'w'))
