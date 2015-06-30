#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import lilv

from mod.lilvlib import NS, LILV_FOREACH
from mod.lilvlib import get_plugin_info as get_plugin_info2
from mod.settings import MODGUIS_ONLY

# global stuff
global W, BUNDLES, PLUGINS, PLUGNFO

# our lilv world
W = lilv.World()

# list of loaded bundles
BUNDLES = []

# list of lilv plugins
PLUGINS = []

# cached info about each plugin (using uri as key)
PLUGNFO = {}

# initialize
def init():
    global W

    W.load_all()
    refresh()

# refresh everything
# plugins are not truly scanned here, only later per request
def refresh():
    global W, BUNDLES, PLUGINS, PLUGNFO

    BUNDLES = []
    PLUGINS = W.get_all_plugins()
    PLUGNFO = {}

    # Make a list of all installed bundles
    for p in PLUGINS:
        bundles = lilv.lilv_plugin_get_data_uris(p.me)

        # store empty dict for later
        PLUGNFO[p.get_uri().as_uri()] = {}

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

# get all available plugins
# this is trigger scanning of all plugins
# returned value depends on MODGUIS_ONLY value
def get_all_plugins():
    global W, PLUGINS, PLUGNFO

    ret  = []
    keys = PLUGNFO.keys()

    for p in PLUGINS:
        uri = p.get_uri().as_uri()

        # check if it's already cached
        if uri in keys and PLUGNFO[uri]:
            if PLUGNFO[uri]['gui'] or not MODGUIS_ONLY:
                ret.append(PLUGNFO[uri])
            continue

        # TODO - add lilvlib function for checking if a plugin has modgui (instead of full scan)

        # skip plugins without modgui if so requested
        if MODGUIS_ONLY and False:
            continue

        # get new info
        PLUGNFO[uri] = get_plugin_info2(W, p)
        ret.append(PLUGNFO[uri])

    return ret

# get a specific plugin
# NOTE: may throw
def get_plugin_info(uri):
    global W, PLUGINS, PLUGNFO

    # check if it exists
    if uri not in PLUGNFO.keys():
        raise Exception

    # check if it's already cached
    if PLUGNFO[uri]:
        return PLUGNFO[uri]

    # look for it
    for p in PLUGINS:
        if p.get_uri().as_uri() != uri:
            continue
        # found it
        PLUGNFO[uri] = get_plugin_info2(W, p)
        return PLUGNFO[uri]

    # not found
    raise Exception

# get all available pedalboards (ie, plugins with pedalboard type)
def get_pedalboards():
    global W, PLUGINS

    # define needed namespaces
    rdf      = NS(W, lilv.LILV_NS_RDF)
    rdfs     = NS(W, lilv.LILV_NS_RDFS)
    pset     = NS(W, "http://lv2plug.in/ns/ext/presets#")
    modpedal = NS(W, "http://moddevices.com/ns/modpedal#")

    # fill in presets for a plugin
    def get_presets(p):
        presets = p.get_related(pset.Preset)
        def get_preset_data(preset):
            W.load_resource(preset.me)
            label = W.find_nodes(preset.me, rdfs.label.me, None).get_first().as_string()
            return { 'uri': preset.as_string(), 'label': label }
        return list(LILV_FOREACH(presets, get_preset_data))

    # check each plugin for a pedalboard type
    pedalboards = []

    for pedalboard in PLUGINS:
        # check if the plugin is a pedalboard
        def fill_in_type(node):
            return node.as_string()
        plugin_types = [i for i in LILV_FOREACH(pedalboard.get_value(rdf.type_), fill_in_type)]

        if "http://moddevices.com/ns/modpedal#Pedalboard" not in plugin_types:
            continue

        # ready
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

# add a bundle to our lilv world
# returns true if the bundle was added
def add_bundle_to_lilv_world(bundlepath):
    global W, BUNDLES, PLUGINS, PLUGNFO

    # lilv wants the last character as the separator
    if not bundlepath.endswith(os.sep):
        bundlepath += os.sep

    # stop now if bundle is already loaded
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

    # fill in for any new plugins that appeared
    keys = PLUGNFO.keys()

    for p in PLUGINS:
        uri = p.get_uri().as_uri()

        # check if it's already cached
        if uri in keys and PLUGNFO[uri]:
            continue

        # get new info
        PLUGNFO[uri] = get_plugin_info2(W, p)

    return True
