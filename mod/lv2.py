import os, hashlib, re, random, shutil, subprocess
import lilv
import hashlib

from mod.lilvlib import LILV_FOREACH, get_category, get_port_unit, get_plugin_info

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
modgui = NS("http://moddevices.com/ns/modgui#")
modpedal = NS("http://moddevices.com/ns/modpedal#")

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

        if "http://moddevices.com/ns/modpedal#Pedalboard" not in plugin_types:
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

        self.data = get_plugin_info(W, self.p)

        minor = self.data['minorVersion']
        micro = self.data['microVersion']
        self.data['version'] = "%d.%d" % (micro, minor)

        if minor == 0 and micro == 0:
            self.data['stability'] = "experimental"
        #elif minor % 2 == 0 and micro % 2 == 0:
            #self.data['stability'] =
        elif minor % 2 == 0:
            self.data['stability'] = "stable" if micro % 2 == 0 else "testing"
        else:
            self.data['stability'] = "unstable"

        self.data['presets'] = self._get_presets()

        # FIXME - remote these later
        self.data['_id'          ] = hashlib.md5(uri.encode("utf-8")).hexdigest()[:24]
        self.data['bufsize'      ] = 128
        self.data['brand'        ] = ""
        self.data['author'       ] = ""
        self.data['developer'    ] = ""
        self.data['hidden'       ] = False
        self.data['label'        ] = ""
        self.data['package'      ] = lilv.lilv_uri_to_path(self.p.get_bundle_uri().as_string())
        self.data['package_id'   ] = ""
        self.data['url'          ] = self.data['uri']
        self.data['maintainer'   ] = dict()
        self.data['gui_structure'] = self.data['gui']

        if self.data['shortname']:
            self.data['name'     ] = self.data['shortname']

        for port in self.data['ports']['control']['input']:
            if "units" in port.keys() and port['units']:
                port['unit'] = port['units']

    def _get_presets(self):
        presets = self.p.get_related(pset.Preset)
        def get_preset_data(preset):
            W.load_resource(preset.me)
            label = W.find_nodes(preset.me, rdfs.label.me, None).get_first().as_string()
            return (preset.as_string(), { 'uri': preset.as_string(), 'label': label })
        return dict(LILV_FOREACH(presets, get_preset_data))

    def has_modgui(self):
        return bool(self.data['gui'])

    def save_json(self, directory):
        import json
        json.dump(self.data, open(os.path.join(directory, self.data['_id']), 'w'))
