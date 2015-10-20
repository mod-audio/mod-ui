/*
 * MOD-UI utilities
 * Copyright (C) 2015 Filipe Coelho <falktx@falktx.com>
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License as
 * published by the Free Software Foundation; either version 2 of
 * the License, or any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 *
 * For a full copy of the GNU General Public License see the COPYING file.
 */

#include "utils.h"

#include <assert.h>
#include <libgen.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>
#include <lilv/lilv.h>

#include <algorithm>
#include <list>
#include <map>
#include <string>
#include <vector>

#define OS_SEP     '/'
#define OS_SEP_STR "/"

// our lilv world
LilvWorld* W = nullptr;

// list of loaded bundles
std::list<std::string> BUNDLES;

// list of lilv plugins
const LilvPlugins* PLUGINS = nullptr;

// plugin info, mapped to URIs
std::map<std::string, PluginInfo> PLUGNFO;

// some other cached values
static const char* const HOME = getenv("HOME");
static size_t HOMElen = strlen(HOME);

#define PluginInfo_Init {                            \
    false,                                           \
    nullptr, nullptr,                                \
    nullptr, nullptr, nullptr, nullptr, nullptr,     \
    nullptr, 0, 0,                                   \
    nullptr, nullptr,                                \
    { nullptr, nullptr, nullptr },                   \
    nullptr,                                         \
    {                                                \
        nullptr, nullptr, nullptr, nullptr, nullptr, \
        nullptr, nullptr,                            \
        nullptr, nullptr,                            \
        nullptr, nullptr, nullptr, nullptr,          \
        nullptr                                      \
    },                                               \
    {                                                \
        { nullptr, nullptr },                        \
        { nullptr, nullptr },                        \
        { nullptr, nullptr },                        \
        { nullptr, nullptr }                         \
    },                                               \
    nullptr                                          \
}

#if 0
// Blacklisted plugins, which don't work properly on MOD for various reasons
BLACKLIST = [
    "urn:50m30n3:plugins:SO-404",
    "urn:50m30n3:plugins:SO-666",
    "urn:50m30n3:plugins:SO-kl5",
    "urn:juce:JuceDemoHost",
    "urn:juced:DrumSynth",
    "file:///usr/lib/lv2/MonoEffect.ingen/MonoEffect.ttl",
    "file:///usr/lib/lv2/MonoInstrument.ingen/MonoInstrument.ttl",
    "file:///usr/lib/lv2/StereoEffect.ingen/StereoEffect.ttl",
    "file:///usr/lib/lv2/StereoInstrument.ingen/StereoInstrument.ttl",
    "http://calf.sourceforge.net/plugins/Analyzer",
    "http://distrho.sf.net/plugins/ProM",
    "http://drumgizmo.org/lv2",
    "http://drumkv1.sourceforge.net/lv2",
    "http://factorial.hu/plugins/lv2/ir",
    "http://gareus.org/oss/lv2/meters#BBCM6",
    "http://gareus.org/oss/lv2/meters#BBCmono",
    "http://gareus.org/oss/lv2/meters#BBCstereo",
    "http://gareus.org/oss/lv2/meters#bitmeter",
    "http://gareus.org/oss/lv2/meters#COR",
    "http://gareus.org/oss/lv2/meters#dBTPmono",
    "http://gareus.org/oss/lv2/meters#dBTPstereo",
    "http://gareus.org/oss/lv2/meters#DINmono",
    "http://gareus.org/oss/lv2/meters#DINstereo",
    "http://gareus.org/oss/lv2/meters#dr14mono",
    "http://gareus.org/oss/lv2/meters#dr14stereo",
    "http://gareus.org/oss/lv2/meters#EBUmono",
    "http://gareus.org/oss/lv2/meters#EBUr128",
    "http://gareus.org/oss/lv2/meters#EBUstereo",
    "http://gareus.org/oss/lv2/meters#goniometer",
    "http://gareus.org/oss/lv2/meters#K12mono",
    "http://gareus.org/oss/lv2/meters#K12stereo",
    "http://gareus.org/oss/lv2/meters#K14mono",
    "http://gareus.org/oss/lv2/meters#K14stereo",
    "http://gareus.org/oss/lv2/meters#K20mono",
    "http://gareus.org/oss/lv2/meters#K20stereo",
    "http://gareus.org/oss/lv2/meters#NORmono",
    "http://gareus.org/oss/lv2/meters#NORstereo",
    "http://gareus.org/oss/lv2/meters#phasewheel",
    "http://gareus.org/oss/lv2/meters#SigDistHist",
    "http://gareus.org/oss/lv2/meters#spectr30mono",
    "http://gareus.org/oss/lv2/meters#spectr30stereo",
    "http://gareus.org/oss/lv2/meters#stereoscope",
    "http://gareus.org/oss/lv2/meters#TPnRMSmono",
    "http://gareus.org/oss/lv2/meters#TPnRMSstereo",
    "http://gareus.org/oss/lv2/meters#VUmono",
    "http://gareus.org/oss/lv2/meters#VUstereo",
    "http://gareus.org/oss/lv2/mixtri#lv2",
    "http://gareus.org/oss/lv2/onsettrigger#bassdrum_mono",
    "http://gareus.org/oss/lv2/onsettrigger#bassdrum_stereo",
    "http://gareus.org/oss/lv2/sisco#3chan",
    "http://gareus.org/oss/lv2/sisco#4chan",
    "http://gareus.org/oss/lv2/sisco#Mono",
    "http://gareus.org/oss/lv2/sisco#Stereo",
    "http://gareus.org/oss/lv2/tuna#one",
    "http://gareus.org/oss/lv2/tuna#two",
    "http://github.com/nicklan/drmr",
    "http://invadarecords.com/plugins/lv2/meter",
    "http://kxstudio.sf.net/carla/plugins/carlapatchbay",
    "http://kxstudio.sf.net/carla/plugins/carlapatchbay16",
    "http://kxstudio.sf.net/carla/plugins/carlapatchbay32",
    "http://kxstudio.sf.net/carla/plugins/carlapatchbay3s",
    "http://kxstudio.sf.net/carla/plugins/carlarack",
    "http://kxstudio.sf.net/carla/plugins/bigmeter",
    "http://kxstudio.sf.net/carla/plugins/midipattern",
    "http://kxstudio.sf.net/carla/plugins/midisequencer",
    "http://kxstudio.sf.net/carla/plugins/notes",
    "http://linuxsampler.org/plugins/linuxsampler",
    "http://lv2plug.in/plugins/eg-scope#Mono",
    "http://lv2plug.in/plugins/eg-scope#Stereo",
    "http://pianoteq.com/lv2/Pianoteq4",
    "http://pianoteq.com/lv2/Pianoteq4_5chan",
    "http://samplv1.sourceforge.net/lv2",
    "http://teragonaudio.com/BeatCounter.html",
    "http://teragonaudio.com/ExtraNotes.html",
    "http://www.klangfreund.com/lufsmeter",
    "http://www.klangfreund.com/lufsmetermultichannel",
    "http://www.wodgod.com/newtonator/1.0",
    "https://github.com/HiFi-LoFi/KlangFalter",
]
#endif

// --------------------------------------------------------------------------------------------------------

#define LILV_NS_MOD    "http://moddevices.com/ns/mod#"
#define LILV_NS_MODGUI "http://moddevices.com/ns/modgui#"

struct NamespaceDefinitions {
    LilvNode* doap_license;
    LilvNode* rdf_type;
    LilvNode* rdfs_comment;
    LilvNode* lv2core_microVersion;
    LilvNode* lv2core_minorVersion;
    LilvNode* mod_brand;
    LilvNode* mod_label;
    LilvNode* modgui_gui;
    LilvNode* modgui_resourcesDirectory;
    LilvNode* modgui_iconTemplate;
    LilvNode* modgui_settingsTemplate;
    LilvNode* modgui_javascript;
    LilvNode* modgui_stylesheet;
    LilvNode* modgui_screenshot;
    LilvNode* modgui_thumbnail;
    LilvNode* modgui_brand;
    LilvNode* modgui_label;
    LilvNode* modgui_model;
    LilvNode* modgui_panel;
    LilvNode* modgui_color;
    LilvNode* modgui_knob;

    NamespaceDefinitions()
        : doap_license             (lilv_new_uri(W, LILV_NS_DOAP   "license"           )),
          rdf_type                 (lilv_new_uri(W, LILV_NS_RDF    "type"              )),
          rdfs_comment             (lilv_new_uri(W, LILV_NS_RDFS   "comment"           )),
          lv2core_microVersion     (lilv_new_uri(W, LILV_NS_LV2    "microVersion"      )),
          lv2core_minorVersion     (lilv_new_uri(W, LILV_NS_LV2    "minorVersion"      )),
          mod_brand                (lilv_new_uri(W, LILV_NS_MOD    "brand"             )),
          mod_label                (lilv_new_uri(W, LILV_NS_MOD    "label"             )),
          modgui_gui               (lilv_new_uri(W, LILV_NS_MODGUI "gui"               )),
          modgui_resourcesDirectory(lilv_new_uri(W, LILV_NS_MODGUI "resourcesDirectory")),
          modgui_iconTemplate      (lilv_new_uri(W, LILV_NS_MODGUI "iconTemplate"      )),
          modgui_settingsTemplate  (lilv_new_uri(W, LILV_NS_MODGUI "settingsTemplate"  )),
          modgui_javascript        (lilv_new_uri(W, LILV_NS_MODGUI "javascript"        )),
          modgui_stylesheet        (lilv_new_uri(W, LILV_NS_MODGUI "stylesheet"        )),
          modgui_screenshot        (lilv_new_uri(W, LILV_NS_MODGUI "screenshot"        )),
          modgui_thumbnail         (lilv_new_uri(W, LILV_NS_MODGUI "thumbnail"         )),
          modgui_brand             (lilv_new_uri(W, LILV_NS_MODGUI "brand"             )),
          modgui_label             (lilv_new_uri(W, LILV_NS_MODGUI "label"             )),
          modgui_model             (lilv_new_uri(W, LILV_NS_MODGUI "model"             )),
          modgui_panel             (lilv_new_uri(W, LILV_NS_MODGUI "panel"             )),
          modgui_color             (lilv_new_uri(W, LILV_NS_MODGUI "color"             )),
          modgui_knob              (lilv_new_uri(W, LILV_NS_MODGUI "knob"              )) {}

    ~NamespaceDefinitions()
    {
        lilv_node_free(doap_license);
        lilv_node_free(rdf_type);
        lilv_node_free(rdfs_comment);
        lilv_node_free(lv2core_microVersion);
        lilv_node_free(lv2core_minorVersion);
        lilv_node_free(mod_brand);
        lilv_node_free(mod_label);
        lilv_node_free(modgui_gui);
        lilv_node_free(modgui_resourcesDirectory);
        lilv_node_free(modgui_iconTemplate);
        lilv_node_free(modgui_settingsTemplate);
        lilv_node_free(modgui_javascript);
        lilv_node_free(modgui_stylesheet);
        lilv_node_free(modgui_screenshot);
        lilv_node_free(modgui_thumbnail);
        lilv_node_free(modgui_brand);
        lilv_node_free(modgui_label);
        lilv_node_free(modgui_model);
        lilv_node_free(modgui_panel);
        lilv_node_free(modgui_color);
        lilv_node_free(modgui_knob);
    }
};

static const char* kCategoryDelayPlugin[] = { "Delay", nullptr };
static const char* kCategoryDistortionPlugin[] = { "Distortion", nullptr };
static const char* kCategoryWaveshaperPlugin[] = { "Distortion", "Waveshaper", nullptr };
static const char* kCategoryDynamicsPlugin[] = { "Dynamics", nullptr };
static const char* kCategoryAmplifierPlugin[] = { "Dynamics", "Amplifier", nullptr };
static const char* kCategoryCompressorPlugin[] = { "Dynamics", "Compressor", nullptr };
static const char* kCategoryExpanderPlugin[] = { "Dynamics", "Expander", nullptr };
static const char* kCategoryGatePlugin[] = { "Dynamics", "Gate", nullptr };
static const char* kCategoryLimiterPlugin[] = { "Dynamics", "Limiter", nullptr };
static const char* kCategoryFilterPlugin[] = { "Filter", nullptr };
static const char* kCategoryAllpassPlugin[] = { "Filter", "Allpass", nullptr };
static const char* kCategoryBandpassPlugin[] = { "Filter", "Bandpass", nullptr };
static const char* kCategoryCombPlugin[] = { "Filter", "Comb", nullptr };
static const char* kCategoryEQPlugin[] = { "Filter", "Equaliser", nullptr };
static const char* kCategoryMultiEQPlugin[] = { "Filter", "Equaliser", "Multiband", nullptr };
static const char* kCategoryParaEQPlugin[] = { "Filter", "Equaliser", "Parametric", nullptr };
static const char* kCategoryHighpassPlugin[] = { "Filter", "Highpass", nullptr };
static const char* kCategoryLowpassPlugin[] = { "Filter", "Lowpass", nullptr };
static const char* kCategoryGeneratorPlugin[] = { "Generator", nullptr };
static const char* kCategoryConstantPlugin[] = { "Generator", "Constant", nullptr };
static const char* kCategoryInstrumentPlugin[] = { "Generator", "Instrument", nullptr };
static const char* kCategoryOscillatorPlugin[] = { "Generator", "Oscillator", nullptr };
static const char* kCategoryModulatorPlugin[] = { "Modulator", nullptr };
static const char* kCategoryChorusPlugin[] = { "Modulator", "Chorus", nullptr };
static const char* kCategoryFlangerPlugin[] = { "Modulator", "Flanger", nullptr };
static const char* kCategoryPhaserPlugin[] = { "Modulator", "Phaser", nullptr };
static const char* kCategoryReverbPlugin[] = { "Reverb", nullptr };
static const char* kCategorySimulatorPlugin[] = { "Simulator", nullptr };
static const char* kCategorySpatialPlugin[] = { "Spatial", nullptr };
static const char* kCategorySpectralPlugin[] = { "Spectral", nullptr };
static const char* kCategoryPitchPlugin[] = { "Spectral", "Pitch Shifter", nullptr };
static const char* kCategoryUtilityPlugin[] = { "Utility", nullptr };
static const char* kCategoryAnalyserPlugin[] = { "Utility", "Analyser", nullptr };
static const char* kCategoryConverterPlugin[] = { "Utility", "Converter", nullptr };
static const char* kCategoryFunctionPlugin[] = { "Utility", "Function", nullptr };
static const char* kCategoryMixerPlugin[] = { "Utility", "Mixer", nullptr };

static const char* kStabilityExperimental = "experimental";
static const char* kStabilityStable = "stable";
static const char* kStabilityTesting = "testing";
static const char* kStabilityUnstable = "unstable";

static char nc[1] = { '\0' };

// refresh everything
// plugins are not truly scanned here, only later per request
void _refresh()
{
    char tmppath[PATH_MAX+1];

    BUNDLES.clear();
    PLUGNFO.clear();
    PLUGINS = lilv_world_get_all_plugins(W);

    // Make a list of all installed bundles
    LILV_FOREACH(plugins, itpls, PLUGINS)
    {
        const LilvPlugin* p = lilv_plugins_get(PLUGINS, itpls);

        const LilvNodes* bundles = lilv_plugin_get_data_uris(p);

        std::string uri = lilv_node_as_uri(lilv_plugin_get_uri(p));

        // store empty dict for later
        PLUGNFO[uri] = PluginInfo_Init;

        LILV_FOREACH(nodes, itbnds, bundles)
        {
            const LilvNode* bundle = lilv_nodes_get(bundles, itbnds);

            if (bundle == nullptr)
                continue;
            if (! lilv_node_is_uri(bundle))
                continue;

            char* bundleparsed;
            char* tmp;

            tmp = (char*)lilv_file_uri_parse(lilv_node_as_uri(bundle), nullptr);
            if (tmp == nullptr)
                  continue;

            bundleparsed = dirname(tmp);
            if (bundleparsed == nullptr)
            {
                  lilv_free(tmp);
                  continue;
            }

            bundleparsed = realpath(bundleparsed, tmppath);
            lilv_free(tmp);
            if (bundleparsed == nullptr)
                  continue;

            const size_t size = strlen(bundleparsed);
            if (size <= 1)
                continue;

            if (bundleparsed[size] != '/')
            {
                bundleparsed[size  ] = '/';
                bundleparsed[size+1] = '\0';
            }

            std::string bundlestr = bundleparsed;

            if (std::find(BUNDLES.begin(), BUNDLES.end(), bundlestr) == BUNDLES.end())
                BUNDLES.push_back(bundlestr);
        }
    }
}

const PluginInfo& _get_plugin_info2(const LilvPlugin* p, const NamespaceDefinitions& ns)
{
    static PluginInfo info = PluginInfo_Init;

    // reset
    memset(&info, 0, sizeof(PluginInfo));

    LilvNode* node;
    LilvNodes* nodes;

    const char* bundleuri = lilv_node_as_uri(lilv_plugin_get_bundle_uri(p));
    const char* bundle    = lilv_file_uri_parse(bundleuri, nullptr);

    const size_t bundleurilen = strlen(bundleuri);

    // --------------------------------------------------------------------------------------------------------
    // uri

    info.uri = lilv_node_as_uri(lilv_plugin_get_uri(p));

    // --------------------------------------------------------------------------------------------------------
    // name

    node = lilv_plugin_get_name(p);
    if (node != nullptr)
    {
        const char* name = lilv_node_as_string(node);
        info.name = (name != nullptr) ? strdup(name) : nc;
        lilv_node_free(node);
    }
    else
    {
        info.name = nc;
    }

    // --------------------------------------------------------------------------------------------------------
    // binary

    info.binary = lilv_node_as_string(lilv_plugin_get_library_uri(p));
    if (info.binary != nullptr)
        info.binary = lilv_file_uri_parse(info.binary, NULL);
    else
        info.binary = nc;

    // --------------------------------------------------------------------------------------------------------
    // license

    nodes = lilv_plugin_get_value(p, ns.doap_license);
    if (nodes != nullptr)
    {
        const char* license = lilv_node_as_string(lilv_nodes_get_first(nodes));

        if (strncmp(license, bundleuri, bundleurilen) == 0)
            license += bundleurilen;

        info.license = strdup(license);
        lilv_nodes_free(nodes);
    }
    else
    {
        info.license = nc;
    }

    // --------------------------------------------------------------------------------------------------------
    // comment

    nodes = lilv_plugin_get_value(p, ns.rdfs_comment);
    if (nodes != nullptr)
    {
        info.comment = strdup(lilv_node_as_string(lilv_nodes_get_first(nodes)));
        lilv_nodes_free(nodes);
    }
    else
    {
        info.comment = nc;
    }

    // --------------------------------------------------------------------------------------------------------
    // categories

    nodes = lilv_plugin_get_value(p, ns.rdf_type);
    LILV_FOREACH(nodes, it, nodes)
    {
        const LilvNode* node2 = lilv_nodes_get(nodes, it);
        const char* nodestr = lilv_node_as_string(node2);

        if (nodestr == nullptr)
            continue;

        if (const char* cat = strstr(nodestr, "http://lv2plug.in/ns/lv2core#"))
        {
            cat += 29; // strlen("http://lv2plug.in/ns/lv2core#")

            if (cat[0] == '\0')
                continue;
            if (strcmp(cat, "Plugin") == 0)
                continue;

            else if (strcmp(cat, "DelayPlugin") == 0)
                info.category = kCategoryDelayPlugin;
            else if (strcmp(cat, "DistortionPlugin") == 0)
                info.category = kCategoryDistortionPlugin;
            else if (strcmp(cat, "WaveshaperPlugin") == 0)
                info.category = kCategoryWaveshaperPlugin;
            else if (strcmp(cat, "DynamicsPlugin") == 0)
                info.category = kCategoryDynamicsPlugin;
            else if (strcmp(cat, "AmplifierPlugin") == 0)
                info.category = kCategoryAmplifierPlugin;
            else if (strcmp(cat, "CompressorPlugin") == 0)
                info.category = kCategoryCompressorPlugin;
            else if (strcmp(cat, "ExpanderPlugin") == 0)
                info.category = kCategoryExpanderPlugin;
            else if (strcmp(cat, "GatePlugin") == 0)
                info.category = kCategoryGatePlugin;
            else if (strcmp(cat, "LimiterPlugin") == 0)
                info.category = kCategoryLimiterPlugin;
            else if (strcmp(cat, "FilterPlugin") == 0)
                info.category = kCategoryFilterPlugin;
            else if (strcmp(cat, "AllpassPlugin") == 0)
                info.category = kCategoryAllpassPlugin;
            else if (strcmp(cat, "BandpassPlugin") == 0)
                info.category = kCategoryBandpassPlugin;
            else if (strcmp(cat, "CombPlugin") == 0)
                info.category = kCategoryCombPlugin;
            else if (strcmp(cat, "EQPlugin") == 0)
                info.category = kCategoryEQPlugin;
            else if (strcmp(cat, "MultiEQPlugin") == 0)
                info.category = kCategoryMultiEQPlugin;
            else if (strcmp(cat, "ParaEQPlugin") == 0)
                info.category = kCategoryParaEQPlugin;
            else if (strcmp(cat, "HighpassPlugin") == 0)
                info.category = kCategoryHighpassPlugin;
            else if (strcmp(cat, "LowpassPlugin") == 0)
                info.category = kCategoryLowpassPlugin;
            else if (strcmp(cat, "GeneratorPlugin") == 0)
                info.category = kCategoryGeneratorPlugin;
            else if (strcmp(cat, "ConstantPlugin") == 0)
                info.category = kCategoryConstantPlugin;
            else if (strcmp(cat, "InstrumentPlugin") == 0)
                info.category = kCategoryInstrumentPlugin;
            else if (strcmp(cat, "OscillatorPlugin") == 0)
                info.category = kCategoryOscillatorPlugin;
            else if (strcmp(cat, "ModulatorPlugin") == 0)
                info.category = kCategoryModulatorPlugin;
            else if (strcmp(cat, "ChorusPlugin") == 0)
                info.category = kCategoryChorusPlugin;
            else if (strcmp(cat, "FlangerPlugin") == 0)
                info.category = kCategoryFlangerPlugin;
            else if (strcmp(cat, "PhaserPlugin") == 0)
                info.category = kCategoryPhaserPlugin;
            else if (strcmp(cat, "ReverbPlugin") == 0)
                info.category = kCategoryReverbPlugin;
            else if (strcmp(cat, "SimulatorPlugin") == 0)
                info.category = kCategorySimulatorPlugin;
            else if (strcmp(cat, "SpatialPlugin") == 0)
                info.category = kCategorySpatialPlugin;
            else if (strcmp(cat, "SpectralPlugin") == 0)
                info.category = kCategorySpectralPlugin;
            else if (strcmp(cat, "PitchPlugin") == 0)
                info.category = kCategoryPitchPlugin;
            else if (strcmp(cat, "UtilityPlugin") == 0)
                info.category = kCategoryUtilityPlugin;
            else if (strcmp(cat, "AnalyserPlugin") == 0)
                info.category = kCategoryAnalyserPlugin;
            else if (strcmp(cat, "ConverterPlugin") == 0)
                info.category = kCategoryConverterPlugin;
            else if (strcmp(cat, "FunctionPlugin") == 0)
                info.category = kCategoryFunctionPlugin;
            else if (strcmp(cat, "MixerPlugin") == 0)
                info.category = kCategoryMixerPlugin;
        }
    }
    lilv_nodes_free(nodes);

    // --------------------------------------------------------------------------------------------------------
    // version

    {
        LilvNodes* microvers = lilv_plugin_get_value(p, ns.lv2core_microVersion);
        LilvNodes* minorvers = lilv_plugin_get_value(p, ns.lv2core_minorVersion);

        if (microvers == nullptr && minorvers == nullptr)
        {
            info.microVersion = 0;
            info.minorVersion = 0;
        }
        else
        {
            if (microvers == nullptr)
                info.microVersion = 0;
            else
                info.microVersion = lilv_node_as_int(lilv_nodes_get_first(microvers));

            if (minorvers == nullptr)
                info.minorVersion = 0;
            else
                info.minorVersion = lilv_node_as_int(lilv_nodes_get_first(minorvers));

            lilv_nodes_free(microvers);
            lilv_nodes_free(minorvers);
        }

        char versiontmpstr[32+1] = { '\0' };
        snprintf(versiontmpstr, 32, "%d.%d", info.microVersion, info.minorVersion);
        info.version = strdup(versiontmpstr);
    }

    if (info.minorVersion == 0 && info.microVersion == 0)
        info.stability = kStabilityExperimental;
    else if (info.minorVersion % 2 == 0)
        info.stability = info.microVersion % 2 == 0 ? kStabilityStable : kStabilityTesting;
    else
        info.stability = kStabilityUnstable;

    // --------------------------------------------------------------------------------------------------------
    // author name

    node = lilv_plugin_get_author_name(p);
    if (node != nullptr)
    {
        info.author.name = strdup(lilv_node_as_string(node));
        lilv_node_free(node);
    }
    else
    {
        info.author.name = nc;
    }

    // --------------------------------------------------------------------------------------------------------
    // author homepage

    node = lilv_plugin_get_author_homepage(p);
    if (node != nullptr)
    {
        info.author.homepage = strdup(lilv_node_as_string(node));
        lilv_node_free(node);
    }
    else
    {
        info.author.homepage = nc;
    }

    // --------------------------------------------------------------------------------------------------------
    // author email

    node = lilv_plugin_get_author_email(p);
    if (node != nullptr)
    {
        info.author.email = strdup(lilv_node_as_string(node));
        lilv_node_free(node);
    }
    else
    {
        info.author.email = nc;
    }

    // --------------------------------------------------------------------------------------------------------
    // brand

    nodes = lilv_plugin_get_value(p, ns.mod_brand);
    if (nodes != nullptr)
    {
        info.brand = strdup(lilv_node_as_string(lilv_nodes_get_first(nodes)));

        if (strlen(info.brand) > 10)
           ((char*)info.brand)[10] = '\0';

        lilv_nodes_free(nodes);
    }
    else if (info.author.name == nc)
    {
        info.brand = nc;
    }
    else
    {
        if (strlen(info.author.name) <= 10)
        {
            info.brand = strdup(info.author.name);
        }
        else
        {
            char brand[10+1] = { '\0' };
            strncpy(brand, info.author.name, 10);
            info.brand = strdup(brand);
        }
    }

    // --------------------------------------------------------------------------------------------------------
    // label

    nodes = lilv_plugin_get_value(p, ns.mod_label);

    if (nodes != nullptr)
    {
        info.label = strdup(lilv_node_as_string(lilv_nodes_get_first(nodes)));

        if (strlen(info.label) > 16)
           ((char*)info.label)[16] = '\0';

        lilv_nodes_free(nodes);
    }
    else if (info.name == nc)
    {
        info.label = nc;
    }
    else
    {
        if (strlen(info.name) <= 16)
        {
            info.label = strdup(info.name);
        }
        else
        {
            char label[16+1] = { '\0' };
            strncpy(label, info.name, 16);
            info.label = strdup(label);
        }
    }

    // --------------------------------------------------------------------------------------------------------
    // get the proper modgui

    LilvNode* modguigui = nullptr;
    const char* resdir = nullptr;

    nodes = lilv_plugin_get_value(p, ns.modgui_gui);

    LILV_FOREACH(nodes, it, nodes)
    {
        const LilvNode* mgui = lilv_nodes_get(nodes, it);
        LilvNodes* resdirs = lilv_world_find_nodes(W, mgui, ns.modgui_resourcesDirectory, nullptr);
        if (resdirs == nullptr)
            continue;

        lilv_free((void*)resdir);
        resdir = lilv_file_uri_parse(lilv_node_as_string(lilv_nodes_get_first(resdirs)), nullptr);

        lilv_node_free(modguigui);
        modguigui = lilv_node_duplicate(mgui);

        lilv_nodes_free(resdirs);

        if (strncmp(resdir, HOME, HOMElen) == 0)
            // found a modgui in the home dir, stop here and use it
            break;
    }

    lilv_nodes_free(nodes);

    // --------------------------------------------------------------------------------------------------------
    // gui

    if (modguigui != nullptr)
    {
        info.gui.resourcesDirectory = strdup(resdir);
        lilv_free((void*)resdir);
        resdir = nullptr;

        // icon and settings templates
        if (LilvNodes* modgui_icon = lilv_world_find_nodes(W, modguigui, ns.modgui_iconTemplate, nullptr))
        {
            info.gui.iconTemplate = lilv_file_uri_parse(lilv_node_as_string(lilv_nodes_get_first(modgui_icon)), nullptr);
            lilv_nodes_free(modgui_icon);
        }

        if (LilvNodes* modgui_setts = lilv_world_find_nodes(W, modguigui, ns.modgui_settingsTemplate, nullptr))
        {
            info.gui.settingsTemplate = lilv_file_uri_parse(lilv_node_as_string(lilv_nodes_get_first(modgui_setts)), nullptr);
            lilv_nodes_free(modgui_setts);
        }

        // javascript and stylesheet files
        if (LilvNodes* modgui_script = lilv_world_find_nodes(W, modguigui, ns.modgui_javascript, nullptr))
        {
            info.gui.javascript = lilv_file_uri_parse(lilv_node_as_string(lilv_nodes_get_first(modgui_script)), nullptr);
            lilv_nodes_free(modgui_script);
        }

        if (LilvNodes* modgui_style = lilv_world_find_nodes(W, modguigui, ns.modgui_stylesheet, nullptr))
        {
            info.gui.stylesheet = lilv_file_uri_parse(lilv_node_as_string(lilv_nodes_get_first(modgui_style)), nullptr);
            lilv_nodes_free(modgui_style);
        }

        // screenshot and thumbnail
        if (LilvNodes* modgui_scrn = lilv_world_find_nodes(W, modguigui, ns.modgui_screenshot, nullptr))
        {
            info.gui.screenshot = lilv_file_uri_parse(lilv_node_as_string(lilv_nodes_get_first(modgui_scrn)), nullptr);
            lilv_nodes_free(modgui_scrn);
        }

        if (LilvNodes* modgui_thumb = lilv_world_find_nodes(W, modguigui, ns.modgui_thumbnail, nullptr))
        {
            info.gui.thumbnail = lilv_file_uri_parse(lilv_node_as_string(lilv_nodes_get_first(modgui_thumb)), nullptr);
            lilv_nodes_free(modgui_thumb);
        }

        // extra stuff, all optional
        if (LilvNodes* modgui_brand = lilv_world_find_nodes(W, modguigui, ns.modgui_brand, nullptr))
        {
            info.gui.brand = strdup(lilv_node_as_string(lilv_nodes_get_first(modgui_brand)));
            lilv_nodes_free(modgui_brand);
        }

        if (LilvNodes* modgui_label = lilv_world_find_nodes(W, modguigui, ns.modgui_label, nullptr))
        {
            info.gui.label = strdup(lilv_node_as_string(lilv_nodes_get_first(modgui_label)));
            lilv_nodes_free(modgui_label);
        }

        if (LilvNodes* modgui_model = lilv_world_find_nodes(W, modguigui, ns.modgui_model, nullptr))
        {
            info.gui.model = strdup(lilv_node_as_string(lilv_nodes_get_first(modgui_model)));
            lilv_nodes_free(modgui_model);
        }

        if (LilvNodes* modgui_panel = lilv_world_find_nodes(W, modguigui, ns.modgui_panel, nullptr))
        {
            info.gui.panel = strdup(lilv_node_as_string(lilv_nodes_get_first(modgui_panel)));
            lilv_nodes_free(modgui_panel);
        }

        if (LilvNodes* modgui_color = lilv_world_find_nodes(W, modguigui, ns.modgui_color, nullptr))
        {
            info.gui.color = strdup(lilv_node_as_string(lilv_nodes_get_first(modgui_color)));
            lilv_nodes_free(modgui_color);
        }

        if (LilvNodes* modgui_knob = lilv_world_find_nodes(W, modguigui, ns.modgui_knob, nullptr))
        {
            info.gui.knob = strdup(lilv_node_as_string(lilv_nodes_get_first(modgui_knob)));
            lilv_nodes_free(modgui_knob);
        }

        // TODO - ports

        lilv_node_free(modguigui);
    }

    // --------------------------------------------------------------------------------------------------------

    lilv_free((void*)bundle);

    info.valid = true;
    return info;
}

// --------------------------------------------------------------------------------------------------------

static const PluginInfo** _plug_ret = nullptr;
static unsigned int _plug_lastsize = 0;

void init(void)
{
    lilv_world_free(W);
    W = lilv_world_new();
    lilv_world_load_all(W);
    _refresh();
}

void cleanup(void)
{
    if (_plug_ret != nullptr)
    {
        delete[] _plug_ret;
        _plug_ret = nullptr;
    }

    _plug_lastsize = 0;

    PLUGINS = nullptr;
    BUNDLES.clear();

    for (auto& map : PLUGNFO)
    {
        PluginInfo& info = map.second;

        if (info.name != nullptr && info.name != nc)
            lilv_free((void*)info.name);
        if (info.binary != nullptr && info.binary != nc)
            lilv_free((void*)info.binary);
        if (info.license != nullptr && info.license != nc)
            free((void*)info.license);
        if (info.comment != nullptr && info.comment != nc)
            free((void*)info.comment);
        if (info.version != nullptr && info.version != nc)
            free((void*)info.version);
        if (info.brand != nullptr && info.brand != nc)
            free((void*)info.brand);
        if (info.label != nullptr && info.label != nc)
            free((void*)info.label);
        if (info.author.name != nullptr && info.author.name != nc)
            free((void*)info.author.name);
        if (info.author.homepage != nullptr && info.author.homepage != nc)
            free((void*)info.author.homepage);
        if (info.author.email != nullptr && info.author.email != nc)
            free((void*)info.author.email);
        if (info.gui.resourcesDirectory != nullptr && info.gui.resourcesDirectory != nc)
            free((void*)info.gui.resourcesDirectory);
        if (info.gui.iconTemplate != nullptr && info.gui.iconTemplate != nc)
            free((void*)info.gui.iconTemplate);
        if (info.gui.settingsTemplate != nullptr && info.gui.settingsTemplate != nc)
            free((void*)info.gui.settingsTemplate);
        if (info.gui.javascript != nullptr && info.gui.javascript != nc)
            free((void*)info.gui.javascript);
        if (info.gui.stylesheet != nullptr && info.gui.stylesheet != nc)
            free((void*)info.gui.stylesheet);
        if (info.gui.screenshot != nullptr && info.gui.screenshot != nc)
            free((void*)info.gui.screenshot);
        if (info.gui.thumbnail != nullptr && info.gui.thumbnail != nc)
            free((void*)info.gui.thumbnail);
        if (info.gui.brand != nullptr && info.gui.brand != nc)
            free((void*)info.gui.brand);
        if (info.gui.label != nullptr && info.gui.label != nc)
            free((void*)info.gui.label);
        if (info.gui.model != nullptr && info.gui.model != nc)
            free((void*)info.gui.model);
        if (info.gui.panel != nullptr && info.gui.panel != nc)
            free((void*)info.gui.panel);
        if (info.gui.color != nullptr && info.gui.color != nc)
            free((void*)info.gui.color);
        if (info.gui.knob != nullptr && info.gui.knob != nc)
            free((void*)info.gui.knob);
    }

    PLUGNFO.clear();

    lilv_world_free(W);
    W = nullptr;
}

// --------------------------------------------------------------------------------------------------------

bool add_bundle_to_lilv_world(const char* /*bundle*/)
{
    return false;
}

bool remove_bundle_from_lilv_world(const char* /*bundle*/)
{
    return false;
}

const PluginInfo* const* get_all_plugins(void)
{
    unsigned int newsize = lilv_plugins_size(PLUGINS);

    if (newsize == 0 && _plug_lastsize != 0)
    {
        if (_plug_ret != nullptr)
        {
            delete[] _plug_ret;
            _plug_ret = nullptr;
        }
        return nullptr;
    }

    if (newsize > _plug_lastsize)
    {
        _plug_lastsize = newsize;

        if (_plug_ret != nullptr)
            delete[] _plug_ret;

        _plug_ret = new const PluginInfo*[newsize+1];
        memset(_plug_ret, 0, sizeof(void*) * (newsize+1));
    }

    const NamespaceDefinitions ns;
    unsigned int retIndex = 0;

    // Make a list of all installed bundles
    LILV_FOREACH(plugins, itpls, PLUGINS)
    {
        assert(retIndex < newsize);

        const LilvPlugin* p = lilv_plugins_get(PLUGINS, itpls);

        std::string uri = lilv_node_as_uri(lilv_plugin_get_uri(p));

        //if (uri in BLACKLIST)
        //    continue;
        //if (MODGUI_SHOW_MODE == 3 and uri not in WHITELIST)
        //    continue;

        // check if it's already cached
        if (PLUGNFO.count(uri) > 0 && PLUGNFO[uri].valid)
        {
            _plug_ret[retIndex++] = &PLUGNFO[uri];
            continue;
        }

        // get new info
        const PluginInfo& info = _get_plugin_info2(p, ns);
        PLUGNFO[uri] = info;
        _plug_ret[retIndex++] = &info;
    }

    return _plug_ret;
}

const PluginInfo* get_plugin_info(const char* uri_)
{
    std::string uri = uri_;

    // check if it exists
    if (PLUGNFO.count(uri) == 0)
        return nullptr;

    // check if it's already cached
    if (PLUGNFO[uri].valid)
        return &PLUGNFO[uri];

    const NamespaceDefinitions ns;

    // look for it
    LILV_FOREACH(plugins, itpls, PLUGINS)
    {
        const LilvPlugin* p = lilv_plugins_get(PLUGINS, itpls);

        std::string uri2 = lilv_node_as_uri(lilv_plugin_get_uri(p));

        if (uri2 != uri)
            continue;

        // found it
        printf("NOTICE: Plugin '%s' was not cached, scanning it now...\n", uri_);
        PLUGNFO[uri] = _get_plugin_info2(p, ns);
        return &PLUGNFO[uri];
    }

    // not found
    return nullptr;
}

// --------------------------------------------------------------------------------------------------------

const PedalboardInfo* const* get_all_pedalboards(void)
{
    return nullptr;
}

const PedalboardInfo* get_pedalboard_info(const char* /*bundle*/)
{
    return nullptr;
}

const char* get_pedalboard_name(const char* /*bundle*/)
{
    return nullptr;
}

// --------------------------------------------------------------------------------------------------------
