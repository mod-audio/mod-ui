import os, hashlib, re, random, shutil, subprocess
import lilv
import hashlib

# LILV stuff

W = lilv.World()
W.load_all()

PLUGINS = W.get_all_plugins()

class NS(object):
    def __init__(self, base):
        self.base = base
        self._cache = {}

    def __getattr__(self, attr):
        if attr not in self._cache:
            self._cache[attr] = lilv.Node(W.new_uri(self.base+attr))
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

category_index = {
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

def get_pedalboards():
    def get_presets(p):
        presets = p.get_related(pset.Preset)
        def get_preset_data(preset):
            W.load_resource(preset.me)
            label = W.find_nodes(preset.me, rdfs.label.me, None).get_first().as_string()
            return dict(uri=preset.as_string(), label=label)
        return list(LILV_FOREACH(presets, get_preset_data))

    pedalboards = []
    tester = modgui.thumbnail

    for plugin in PLUGINS:
        t = plugin.get_value(tester).get_first()

        if t.me is None:
            continue

        name = plugin.get_name().as_string()
        uri  = plugin.get_uri().as_string()
        thum = t.as_string()

        pedalboards.append((name, uri, thum, get_presets(plugin)))

    return pedalboards

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
                category=category_index.get("%sPlugin" % p.get_class().get_label().as_string(), []),
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
            d['unit'] = {}
            unit_node = lilv.Nodes(unit).get_first()
            d['unit']['label'] = W.find_nodes(unit_node.me, rdfs.label.me, None).get_first().as_string()
            d['unit']['render'] = W.find_nodes(unit_node.me, units.render.me, None).get_first().as_string()
            d['unit']['symbol'] = W.find_nodes(unit_node.me, rdfs.symbol.me, None).get_first().as_string()
        return d

    def has_modgui(self):
        return self._modgui.me is not None

    def save_json(self, directory):
        import json
        json.dump(self.data, open(os.path.join(directory, self.data['_id']), 'w'))
