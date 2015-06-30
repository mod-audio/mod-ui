#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import lilv

from mod.lilvlib import NS, LILV_FOREACH, get_category, get_port_unit, get_plugin_info

# LILV stuff

W = lilv.World()

BUNDLES = []
PLUGINS = []

def init():
    W.load_all()
    refresh()

def refresh():
    BUNDLES = []
    PLUGINS = W.get_all_plugins()

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

def get_pedalboards():
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
