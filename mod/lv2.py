import os, hashlib, re, random, shutil, subprocess
import lilv
import hashlib

from mod.lilvlib import LILV_FOREACH, get_category, get_port_unit

# LILV stuff

W = lilv.World()
W.load_all()

PLUGINS = W.get_all_plugins()
BUNDLES = []

# Make a list of all installed bundles
for p in PLUGINS:
    bundles = lilv.lilv_plugin_get_data_uris(p.me)

    it = lilv.lilv_nodes_begin(bundles)
    while not lilv.lilv_nodes_is_end(bundles, it):
        bundle = lilv.lilv_nodes_get(bundles, it)
        it     = lilv.lilv_nodes_next(bundles, it)

        if bundle is None:
            continue
        if not lilv.lilv_node_is_uri(bundle):
            continue

        bundle = os.path.dirname(lilv.lilv_uri_to_path(lilv.lilv_node_as_uri(bundle)))

        if not bundle.endswith(os.sep):
            bundle += os.sep

        if bundle not in BUNDLES:
            BUNDLES.append(bundle)

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
            'name': pedalboard.get_name().as_string(),
            'uri':  pedalboard.get_uri().as_string(),
            'screenshot': lilv.lilv_uri_to_path(pedalboard.get_value(modpedal.screenshot).get_first().as_string() or ""),
            'thumbnail':  lilv.lilv_uri_to_path(pedalboard.get_value(modpedal.thumbnail).get_first().as_string() or ""),
            'width':  pedalboard.get_value(modpedal.width).get_first().as_int(),
            'height': pedalboard.get_value(modpedal.height).get_first().as_int(),
            'presets': get_presets(pedalboard)
        })

    return pedalboards

def add_bundle_to_lilv_world(bundlepath):
    # lilv wants the last character as the separator
    if not bundlepath.endswith(os.sep):
        bundlepath += os.sep

    # safety check
    if bundlepath in BUNDLES:
        return False

    # convert bundle string into a lilv node
    bundlenode = lilv.lilv_new_file_uri(W.me, None, bundlepath)

    # load the bundle
    W.load_bundle(bundlenode)

    # free bundlenode, no longer needed
    lilv.lilv_node_free(bundlenode)

    # add to world
    BUNDLES.append(bundlepath)
    return True

class PluginSerializer(object):
    def __init__(self, uri=None, plugin=None):
        if plugin:
            self.p = plugin
            uri = self.p.get_uri().as_string()
        else:
            self.p = PLUGINS.get_by_uri(W.new_uri(uri))
        self.uri = uri
        p = self.p

        self._modgui = None

        # find the best modgui
        guis = p.get_value(modgui.gui)
        it   = guis.begin()
        while not guis.is_end(it):
            gui = guis.get(it)
            it  = guis.next(it)
            if gui.me is None:
                continue
            resdir = W.find_nodes(gui.me, modgui.resourcesDirectory.me, None).get_first()
            if resdir.me is None:
                continue
            self._modgui = gui
            if os.path.expanduser("~") in lilv.lilv_uri_to_path(resdir.as_string()):
                # found a modgui in the home dir, stop here and use it
                break

        del guis, it

        self.data = dict(
                _id="",
                binary=(lilv.lilv_uri_to_path(p.get_library_uri().as_string() or "")),
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
        if self._modgui is None or self._modgui.me is None:
            return ""
        pred = getattr(modgui, predicate)
        n = W.find_nodes(self._modgui.me, pred.me, None).get_first()
        return lilv.lilv_uri_to_path(n.as_string() or "")

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
            unit_uri  = unit_node.as_string()

            # using pre-existing lv2 unit
            if unit_uri is not None and unit_uri.startswith("http://lv2plug.in/ns/extensions/units#"):
                ulabel, urender, usymbol = get_port_unit(unit_uri.replace("http://lv2plug.in/ns/extensions/units#","",1))
                unit_dict['label']  = ulabel
                unit_dict['render'] = urender
                unit_dict['symbol'] = usymbol

            # using custom unit
            else:
                unit_dict['label']  = W.find_nodes(unit_node.me, rdfs.label.me, None).get_first().as_string()
                unit_dict['render'] = W.find_nodes(unit_node.me, units.render.me, None).get_first().as_string()
                unit_dict['symbol'] = W.find_nodes(unit_node.me, units.symbol.me, None).get_first().as_string()

            d['unit'] = unit_dict
        return d

    def has_modgui(self):
        return self._modgui is not None and self._modgui.me is not None

    def save_json(self, directory):
        import json
        json.dump(self.data, open(os.path.join(directory, self.data['_id']), 'w'))
