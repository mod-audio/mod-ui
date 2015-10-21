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

#include <libgen.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>

#include <lilv/lilv.h>

#include "lv2/lv2plug.in/ns/ext/atom/atom.h"
#include "lv2/lv2plug.in/ns/ext/midi/midi.h"
#include "lv2/lv2plug.in/ns/ext/port-props/port-props.h"
#include "lv2/lv2plug.in/ns/extensions/units/units.h"
#include "lv2/lv2plug.in/ns/lv2core/lv2.h"

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
    LilvNode* rdfs_label;
    LilvNode* lv2core_designation;
    LilvNode* lv2core_index;
    LilvNode* lv2core_microVersion;
    LilvNode* lv2core_minorVersion;
    LilvNode* lv2core_name;
    LilvNode* lv2core_shortname;
    LilvNode* lv2core_symbol;
    LilvNode* mod_brand;
    LilvNode* mod_label;
    LilvNode* mod_rangeSteps;
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
    LilvNode* modgui_port;
    LilvNode* atom_bufferType;
    LilvNode* atom_Sequence;
    LilvNode* midi_MidiEvent;
    LilvNode* pprops_rangeSteps;
    LilvNode* units_render;
    LilvNode* units_symbol;
    LilvNode* units_unit;

    NamespaceDefinitions()
        : doap_license             (lilv_new_uri(W, LILV_NS_DOAP   "license"           )),
          rdf_type                 (lilv_new_uri(W, LILV_NS_RDF    "type"              )),
          rdfs_comment             (lilv_new_uri(W, LILV_NS_RDFS   "comment"           )),
          rdfs_label               (lilv_new_uri(W, LILV_NS_RDFS   "label"             )),
          lv2core_designation      (lilv_new_uri(W, LILV_NS_LV2    "designation"       )),
          lv2core_index            (lilv_new_uri(W, LILV_NS_LV2    "index"             )),
          lv2core_microVersion     (lilv_new_uri(W, LILV_NS_LV2    "microVersion"      )),
          lv2core_minorVersion     (lilv_new_uri(W, LILV_NS_LV2    "minorVersion"      )),
          lv2core_name             (lilv_new_uri(W, LILV_NS_LV2    "name"              )),
          lv2core_shortname        (lilv_new_uri(W, LILV_NS_LV2    "shortname"         )),
          lv2core_symbol           (lilv_new_uri(W, LILV_NS_LV2    "symbol"            )),
          mod_brand                (lilv_new_uri(W, LILV_NS_MOD    "brand"             )),
          mod_label                (lilv_new_uri(W, LILV_NS_MOD    "label"             )),
          mod_rangeSteps           (lilv_new_uri(W, LILV_NS_MOD    "rangeSteps"        )),
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
          modgui_knob              (lilv_new_uri(W, LILV_NS_MODGUI "knob"              )),
          modgui_port              (lilv_new_uri(W, LILV_NS_MODGUI "port"              )),
          atom_bufferType          (lilv_new_uri(W, LV2_ATOM__bufferType               )),
          atom_Sequence            (lilv_new_uri(W, LV2_ATOM__Sequence                 )),
          midi_MidiEvent           (lilv_new_uri(W, LV2_MIDI__MidiEvent                )),
          pprops_rangeSteps        (lilv_new_uri(W, LV2_PORT_PROPS__rangeSteps         )),
          units_render             (lilv_new_uri(W, LV2_UNITS__render                  )),
          units_symbol             (lilv_new_uri(W, LV2_UNITS__symbol                  )),
          units_unit               (lilv_new_uri(W, LV2_UNITS__unit                    )) {}

    ~NamespaceDefinitions()
    {
        lilv_node_free(doap_license);
        lilv_node_free(rdf_type);
        lilv_node_free(rdfs_comment);
        lilv_node_free(rdfs_label);
        lilv_node_free(lv2core_designation);
        lilv_node_free(lv2core_index);
        lilv_node_free(lv2core_microVersion);
        lilv_node_free(lv2core_minorVersion);
        lilv_node_free(lv2core_name);
        lilv_node_free(lv2core_shortname);
        lilv_node_free(lv2core_symbol);
        lilv_node_free(mod_brand);
        lilv_node_free(mod_label);
        lilv_node_free(mod_rangeSteps);
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
        lilv_node_free(modgui_port);
        lilv_node_free(atom_bufferType);
        lilv_node_free(atom_Sequence);
        lilv_node_free(midi_MidiEvent);
        lilv_node_free(pprops_rangeSteps);
        lilv_node_free(units_render);
        lilv_node_free(units_symbol);
        lilv_node_free(units_unit);
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
    static PluginInfo info;
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
        info.gui.resourcesDirectory = resdir;
        resdir = nullptr;

        // icon and settings templates
        if (LilvNodes* modgui_icon = lilv_world_find_nodes(W, modguigui, ns.modgui_iconTemplate, nullptr))
        {
            info.gui.iconTemplate = lilv_file_uri_parse(lilv_node_as_string(lilv_nodes_get_first(modgui_icon)), nullptr);
            lilv_nodes_free(modgui_icon);
        }
        else
            info.gui.iconTemplate = nc;

        if (LilvNodes* modgui_setts = lilv_world_find_nodes(W, modguigui, ns.modgui_settingsTemplate, nullptr))
        {
            info.gui.settingsTemplate = lilv_file_uri_parse(lilv_node_as_string(lilv_nodes_get_first(modgui_setts)), nullptr);
            lilv_nodes_free(modgui_setts);
        }
        else
            info.gui.settingsTemplate = nc;

        // javascript and stylesheet files
        if (LilvNodes* modgui_script = lilv_world_find_nodes(W, modguigui, ns.modgui_javascript, nullptr))
        {
            info.gui.javascript = lilv_file_uri_parse(lilv_node_as_string(lilv_nodes_get_first(modgui_script)), nullptr);
            lilv_nodes_free(modgui_script);
        }
        else
            info.gui.javascript = nc;

        if (LilvNodes* modgui_style = lilv_world_find_nodes(W, modguigui, ns.modgui_stylesheet, nullptr))
        {
            info.gui.stylesheet = lilv_file_uri_parse(lilv_node_as_string(lilv_nodes_get_first(modgui_style)), nullptr);
            lilv_nodes_free(modgui_style);
        }
        else
            info.gui.stylesheet = nc;

        // screenshot and thumbnail
        if (LilvNodes* modgui_scrn = lilv_world_find_nodes(W, modguigui, ns.modgui_screenshot, nullptr))
        {
            info.gui.screenshot = lilv_file_uri_parse(lilv_node_as_string(lilv_nodes_get_first(modgui_scrn)), nullptr);
            lilv_nodes_free(modgui_scrn);
        }
        else
            info.gui.screenshot = nc;

        if (LilvNodes* modgui_thumb = lilv_world_find_nodes(W, modguigui, ns.modgui_thumbnail, nullptr))
        {
            info.gui.thumbnail = lilv_file_uri_parse(lilv_node_as_string(lilv_nodes_get_first(modgui_thumb)), nullptr);
            lilv_nodes_free(modgui_thumb);
        }
        else
            info.gui.thumbnail = nc;

        // extra stuff, all optional
        if (LilvNodes* modgui_brand = lilv_world_find_nodes(W, modguigui, ns.modgui_brand, nullptr))
        {
            info.gui.brand = strdup(lilv_node_as_string(lilv_nodes_get_first(modgui_brand)));
            lilv_nodes_free(modgui_brand);
        }
        else
            info.gui.brand = nc;

        if (LilvNodes* modgui_label = lilv_world_find_nodes(W, modguigui, ns.modgui_label, nullptr))
        {
            info.gui.label = strdup(lilv_node_as_string(lilv_nodes_get_first(modgui_label)));
            lilv_nodes_free(modgui_label);
        }
        else
            info.gui.label = nc;

        if (LilvNodes* modgui_model = lilv_world_find_nodes(W, modguigui, ns.modgui_model, nullptr))
        {
            info.gui.model = strdup(lilv_node_as_string(lilv_nodes_get_first(modgui_model)));
            lilv_nodes_free(modgui_model);
        }
        else
            info.gui.model = nc;

        if (LilvNodes* modgui_panel = lilv_world_find_nodes(W, modguigui, ns.modgui_panel, nullptr))
        {
            info.gui.panel = strdup(lilv_node_as_string(lilv_nodes_get_first(modgui_panel)));
            lilv_nodes_free(modgui_panel);
        }
        else
            info.gui.panel = nc;

        if (LilvNodes* modgui_color = lilv_world_find_nodes(W, modguigui, ns.modgui_color, nullptr))
        {
            info.gui.color = strdup(lilv_node_as_string(lilv_nodes_get_first(modgui_color)));
            lilv_nodes_free(modgui_color);
        }
        else
            info.gui.color = nc;

        if (LilvNodes* modgui_knob = lilv_world_find_nodes(W, modguigui, ns.modgui_knob, nullptr))
        {
            info.gui.knob = strdup(lilv_node_as_string(lilv_nodes_get_first(modgui_knob)));
            lilv_nodes_free(modgui_knob);
        }
        else
            info.gui.knob = nc;

        {
            if (LilvNodes* modgui_ports = lilv_world_find_nodes(W, modguigui, ns.modgui_port, nullptr))
            {
                const unsigned int guiportscount = lilv_nodes_size(modgui_ports);
                PluginGUIPort* guiports(new PluginGUIPort[guiportscount+1]);
                memset(guiports, 0, sizeof(PluginGUIPort) * (guiportscount+1));

                int index;
                const LilvNode* modgui_port;

                LILV_FOREACH(nodes, it, modgui_ports)
                {
                    modgui_port = lilv_nodes_get(modgui_ports, it);

                    if (LilvNodes* guiports_index = lilv_world_find_nodes(W, modgui_port, ns.lv2core_index, nullptr))
                    {
                        index = lilv_node_as_int(lilv_nodes_get_first(guiports_index));
                        lilv_nodes_free(guiports_index);
                    }
                    else
                    {
                        continue;
                    }

                    if (index < 0)
                        continue;
                    if (index >= (int)guiportscount)
                        continue;

                    PluginGUIPort& guiport(guiports[index]);
                    if (guiport.valid)
                        continue;

                    if (LilvNodes* guiports_symbol = lilv_world_find_nodes(W, modgui_port, ns.lv2core_symbol, nullptr))
                    {
                        guiport.symbol = strdup(lilv_node_as_string(lilv_nodes_get_first(guiports_symbol)));
                        lilv_nodes_free(guiports_symbol);
                    }
                    else
                    {
                        guiport.symbol = nc;
                    }

                    if (LilvNodes* guiports_name = lilv_world_find_nodes(W, modgui_port, ns.lv2core_name, nullptr))
                    {
                        guiport.name = strdup(lilv_node_as_string(lilv_nodes_get_first(guiports_name)));
                        lilv_nodes_free(guiports_name);
                    }
                    else
                    {
                        guiport.name = nc;
                    }

                    guiport.valid = true;
                }

                info.gui.ports = guiports;

                lilv_nodes_free(modgui_ports);
            }
        }

        lilv_node_free(modguigui);
    }
    else
    {
        info.gui.resourcesDirectory = nc;
        info.gui.iconTemplate = nc;
        info.gui.settingsTemplate = nc;
        info.gui.javascript = nc;
        info.gui.stylesheet = nc;
        info.gui.screenshot = nc;
        info.gui.thumbnail = nc;
        info.gui.brand = nc;
        info.gui.label = nc;
        info.gui.model = nc;
        info.gui.panel = nc;
        info.gui.color = nc;
        info.gui.knob = nc;
    }

    // --------------------------------------------------------------------------------------------------------
    // ports

    if (const uint32_t count = lilv_plugin_get_num_ports(p))
    {
        uint32_t countAudioInput=0,   countAudioOutput=0;
        uint32_t countControlInput=0, countControlOutput=0;
        uint32_t countCvInput=0,      countCvOutput=0;
        uint32_t countMidiInput=0,    countMidiOutput=0;

        // precalculate port counts first
        for (uint32_t i=0; i<count; ++i)
        {
            const LilvPort* port = lilv_plugin_get_port_by_index(p, i);

            int direction = 0; // using -1 = input, +1 = output
            int type      = 0; // using by order1-4: audio, control, cv, midi

            nodes = lilv_port_get_value(p, port, ns.rdf_type);
            LILV_FOREACH(nodes, it, nodes)
            {
                const LilvNode* node2 = lilv_nodes_get(nodes, it);
                const char* nodestr = lilv_node_as_string(node2);

                if (nodestr == nullptr)
                    continue;

                else if (strcmp(nodestr, LV2_CORE__InputPort) == 0)
                    direction = -1;
                else if (strcmp(nodestr, LV2_CORE__OutputPort) == 0)
                    direction = +1;
                else if (strcmp(nodestr, LV2_CORE__AudioPort) == 0)
                    type = 1;
                else if (strcmp(nodestr, LV2_CORE__ControlPort) == 0)
                    type = 2;
                else if (strcmp(nodestr, LV2_CORE__CVPort) == 0)
                    type = 3;
                else if (strcmp(nodestr, LV2_ATOM__AtomPort) == 0 && lilv_port_supports_event(p, port, ns.midi_MidiEvent))
                {
                    if (LilvNodes* nodes2 = lilv_port_get_value(p, port, ns.atom_bufferType))
                    {
                        if (lilv_node_equals(lilv_nodes_get_first(nodes2), ns.atom_Sequence))
                            type = 4;
                        lilv_nodes_free(nodes2);
                    }
                }
            }
            lilv_nodes_free(nodes);

            if (direction == 0 || type == 0)
                continue;

            switch (type)
            {
            case 1: // audio
                if (direction == 1)
                    ++countAudioOutput;
                else
                    ++countAudioInput;
                break;
            case 2: // control
                if (direction == 1)
                    ++countControlOutput;
                else
                    ++countControlInput;
                break;
            case 3: // cv
                if (direction == 1)
                    ++countCvOutput;
                else
                    ++countCvInput;
                break;
            case 4: // midi
                if (direction == 1)
                    ++countMidiOutput;
                else
                    ++countMidiInput;
                break;
            }
        }

        // allocate stuff
        if (countAudioInput > 0)
        {
            info.ports.audio.input = new PluginPort[countAudioInput+1];
            memset(info.ports.audio.input, 0, sizeof(PluginPort) * (countAudioInput+1));
        }
        if (countAudioOutput > 0)
        {
            info.ports.audio.output = new PluginPort[countAudioOutput+1];
            memset(info.ports.audio.output, 0, sizeof(PluginPort) * (countAudioOutput+1));
        }
        if (countControlInput > 0)
        {
            info.ports.control.input = new PluginPort[countControlInput+1];
            memset(info.ports.control.input, 0, sizeof(PluginPort) * (countControlInput+1));
        }
        if (countControlOutput > 0)
        {
            info.ports.control.output = new PluginPort[countControlOutput+1];
            memset(info.ports.control.output, 0, sizeof(PluginPort) * (countControlOutput+1));
        }
        if (countCvInput > 0)
        {
            info.ports.cv.input = new PluginPort[countCvInput+1];
            memset(info.ports.cv.input, 0, sizeof(PluginPort) * (countCvInput+1));
        }
        if (countCvOutput > 0)
        {
            info.ports.cv.output = new PluginPort[countCvOutput+1];
            memset(info.ports.cv.output, 0, sizeof(PluginPort) * (countCvOutput+1));
        }
        if (countMidiInput > 0)
        {
            info.ports.midi.input = new PluginPort[countMidiInput+1];
            memset(info.ports.midi.input, 0, sizeof(PluginPort) * (countMidiInput+1));
        }
        if (countMidiOutput > 0)
        {
            info.ports.midi.output = new PluginPort[countMidiOutput+1];
            memset(info.ports.midi.output, 0, sizeof(PluginPort) * (countMidiOutput+1));
        }

        // use counters as indexes now
        countAudioInput=countAudioOutput=countControlInput=countControlOutput=0;
        countCvInput=countCvOutput=countMidiInput=countMidiOutput=0;

        // now fill info
        for (uint32_t i=0; i<count; ++i)
        {
            const LilvPort* port = lilv_plugin_get_port_by_index(p, i);

            // ----------------------------------------------------------------------------------------------------

            int direction = 0; // using -1 = input, +1 = output
            int type      = 0; // using by order1-4: audio, control, cv, midi

            nodes = lilv_port_get_value(p, port, ns.rdf_type);
            LILV_FOREACH(nodes, it, nodes)
            {
                const LilvNode* node2 = lilv_nodes_get(nodes, it);
                const char* nodestr = lilv_node_as_string(node2);

                if (nodestr == nullptr)
                    continue;

                else if (strcmp(nodestr, LV2_CORE__InputPort) == 0)
                    direction = -1;
                else if (strcmp(nodestr, LV2_CORE__OutputPort) == 0)
                    direction = +1;
                else if (strcmp(nodestr, LV2_CORE__AudioPort) == 0)
                    type = 1;
                else if (strcmp(nodestr, LV2_CORE__ControlPort) == 0)
                    type = 2;
                else if (strcmp(nodestr, LV2_CORE__CVPort) == 0)
                    type = 3;
                else if (strcmp(nodestr, LV2_ATOM__AtomPort) == 0 && lilv_port_supports_event(p, port, ns.midi_MidiEvent))
                {
                    if (LilvNodes* nodes2 = lilv_port_get_value(p, port, ns.atom_bufferType))
                    {
                        if (lilv_node_equals(lilv_nodes_get_first(nodes2), ns.atom_Sequence))
                            type = 4;
                        lilv_nodes_free(nodes2);
                    }
                }
            }
            lilv_nodes_free(nodes);

            if (direction == 0 || type == 0)
                continue;

            // ----------------------------------------------------------------------------------------------------

            PluginPort portinfo;
            memset(&portinfo, 0, sizeof(PluginPort));

            // ----------------------------------------------------------------------------------------------------
            // name

            node = lilv_port_get_name(p, port);
            if (node != nullptr)
            {
                portinfo.name = strdup(lilv_node_as_string(node));
                lilv_node_free(node);
            }
            else
            {
                portinfo.name = nc;
            }

            // ----------------------------------------------------------------------------------------------------
            // symbol

            if (const LilvNode* symbolnode = lilv_port_get_symbol(p, port))
                portinfo.symbol = strdup(lilv_node_as_string(symbolnode));
            else
                portinfo.symbol = nc;

            // ----------------------------------------------------------------------------------------------------
            // short name

            nodes = lilv_port_get_value(p, port, ns.lv2core_shortname);
            if (nodes != nullptr)
            {
                portinfo.shortname = strdup(lilv_node_as_string(lilv_nodes_get_first(nodes)));
                lilv_nodes_free(nodes);
            }
            else
            {
                portinfo.shortname = strdup(portinfo.name);
            }

            if (strlen(portinfo.shortname) > 16)
                ((char*)portinfo.shortname)[16] = '\0';

            // ----------------------------------------------------------------------------------------------------
            // designation

            nodes = lilv_port_get_value(p, port, ns.lv2core_designation);
            if (nodes != nullptr)
            {
                portinfo.designation = strdup(lilv_node_as_string(lilv_nodes_get_first(nodes)));
                lilv_nodes_free(nodes);
            }
            else
            {
                portinfo.designation = nc;
            }

            // ----------------------------------------------------------------------------------------------------
            // range steps

            nodes = lilv_port_get_value(p, port, ns.mod_rangeSteps);
            if (nodes != nullptr)
            {
                portinfo.rangeSteps = lilv_node_as_int(lilv_nodes_get_first(nodes));
                lilv_nodes_free(nodes);
            }
            else
            {
                nodes = lilv_port_get_value(p, port, ns.pprops_rangeSteps);
                if (nodes != nullptr)
                {
                    portinfo.rangeSteps = lilv_node_as_int(lilv_nodes_get_first(nodes));
                    lilv_nodes_free(nodes);
                }
            }

            // ----------------------------------------------------------------------------------------------------
            // port properties

            {
                // TODO
                //properties = [typ.rsplit("#",1)[-1] for typ in get_port_data(port, ns_lv2core.portProperty)]
            }

            // ----------------------------------------------------------------------------------------------------

            // TODO
            portinfo.ranges.max = 1.0f;

            if (type == 2 || type == 3)
            {
            }

            // ----------------------------------------------------------------------------------------------------
            // control ports might contain unit

            portinfo.units.label  = nc;
            portinfo.units.render = nc;
            portinfo.units.symbol = nc;

            if (type == 2)
            {
                LilvNodes* uunits = lilv_port_get_value(p, port, ns.units_unit);
                if (uunits != nullptr)
                {
                    LilvNode* uunit = lilv_nodes_get_first(uunits);
                    const char* uuri = lilv_node_as_uri(uunit);

                    // using pre-existing lv2 unit
                    if (uuri != nullptr && strncmp(uuri, LV2_UNITS_PREFIX, 38) == 0)
                    {
                        uuri += 38; // strlen(LV2_UNITS_PREFIX)

                        // TODO
                        //if uuri.isalnum():
                        //    ulabel, urender, usymbol = get_port_unit(uuri)
                    }
                    // using custom unit
                    else
                    {
                        nodes = lilv_world_find_nodes(W, uunit, ns.rdfs_label, nullptr);
                        if (nodes != nullptr)
                        {
                            portinfo.units.label = strdup(lilv_node_as_string(lilv_nodes_get_first(nodes)));
                            lilv_nodes_free(nodes);
                        }

                        nodes = lilv_world_find_nodes(W, uunit, ns.units_render, nullptr);
                        if (nodes != nullptr)
                        {
                            portinfo.units.render = strdup(lilv_node_as_string(lilv_nodes_get_first(nodes)));
                            lilv_nodes_free(nodes);
                        }

                        nodes = lilv_world_find_nodes(W, uunit, ns.units_symbol, nullptr);
                        if (nodes != nullptr)
                        {
                            portinfo.units.symbol = strdup(lilv_node_as_string(lilv_nodes_get_first(nodes)));
                            lilv_nodes_free(nodes);
                        }
                    }

                    lilv_nodes_free(uunits);
                }
            }

            // ----------------------------------------------------------------------------------------------------

            portinfo.valid = true;

            switch (type)
            {
            case 1: // audio
                if (direction == 1)
                    info.ports.audio.output[countAudioOutput++] = portinfo;
                else
                    info.ports.audio.input[countAudioInput++] = portinfo;
                break;
            case 2: // control
                if (direction == 1)
                    info.ports.control.output[countControlOutput++] = portinfo;
                else
                    info.ports.control.input[countControlInput++] = portinfo;
                break;
            case 3: // cv
                if (direction == 1)
                    info.ports.cv.output[countCvOutput++] = portinfo;
                else
                    info.ports.cv.input[countCvInput++] = portinfo;
                break;
            case 4: // midi
                if (direction == 1)
                    info.ports.midi.output[countMidiOutput++] = portinfo;
                else
                    info.ports.midi.input[countMidiInput++] = portinfo;
                break;
            }
        }
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

void _clear_gui_port_info(const PluginGUIPort& guiportinfo)
{
    if (guiportinfo.name != nullptr && guiportinfo.name != nc)
        free((void*)guiportinfo.name);
    if (guiportinfo.symbol != nullptr && guiportinfo.symbol != nc)
        free((void*)guiportinfo.symbol);
}

void _clear_port_info(const PluginPort& portinfo)
{
    if (portinfo.name != nullptr && portinfo.name != nc)
        free((void*)portinfo.name);
    if (portinfo.symbol != nullptr && portinfo.symbol != nc)
        free((void*)portinfo.symbol);
    if (portinfo.designation != nullptr && portinfo.designation != nc)
        free((void*)portinfo.designation);
    if (portinfo.shortname != nullptr && portinfo.shortname != nc)
        free((void*)portinfo.shortname);
    if (portinfo.units.label != nullptr && portinfo.units.label != nc)
        free((void*)portinfo.units.label);
    if (portinfo.units.render != nullptr && portinfo.units.render != nc)
        free((void*)portinfo.units.render);
    if (portinfo.units.symbol != nullptr && portinfo.units.symbol != nc)
        free((void*)portinfo.units.symbol);
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
            lilv_free((void*)info.gui.resourcesDirectory);
        if (info.gui.iconTemplate != nullptr && info.gui.iconTemplate != nc)
            lilv_free((void*)info.gui.iconTemplate);
        if (info.gui.settingsTemplate != nullptr && info.gui.settingsTemplate != nc)
            lilv_free((void*)info.gui.settingsTemplate);
        if (info.gui.javascript != nullptr && info.gui.javascript != nc)
            lilv_free((void*)info.gui.javascript);
        if (info.gui.stylesheet != nullptr && info.gui.stylesheet != nc)
            lilv_free((void*)info.gui.stylesheet);
        if (info.gui.screenshot != nullptr && info.gui.screenshot != nc)
            lilv_free((void*)info.gui.screenshot);
        if (info.gui.thumbnail != nullptr && info.gui.thumbnail != nc)
            lilv_free((void*)info.gui.thumbnail);
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

        if (info.gui.ports != nullptr)
        {
            for (int i=0; info.gui.ports[i].valid; ++i)
                _clear_gui_port_info(info.gui.ports[i]);
            delete[] info.gui.ports;
        }

        if (info.ports.audio.input != nullptr)
        {
            for (int i=0; info.ports.audio.input[i].valid; ++i)
                _clear_port_info(info.ports.audio.input[i]);
            delete[] info.ports.audio.input;
        }
        if (info.ports.audio.output != nullptr)
        {
            for (int i=0; info.ports.audio.output[i].valid; ++i)
                _clear_port_info(info.ports.audio.output[i]);
            delete[] info.ports.audio.output;
        }
        if (info.ports.control.input != nullptr)
        {
            for (int i=0; info.ports.control.input[i].valid; ++i)
                _clear_port_info(info.ports.control.input[i]);
            delete[] info.ports.control.input;
        }
        if (info.ports.control.output != nullptr)
        {
            for (int i=0; info.ports.control.output[i].valid; ++i)
                _clear_port_info(info.ports.control.output[i]);
            delete[] info.ports.control.output;
        }
        if (info.ports.cv.input != nullptr)
        {
            for (int i=0; info.ports.cv.input[i].valid; ++i)
                _clear_port_info(info.ports.cv.input[i]);
            delete[] info.ports.cv.input;
        }
        if (info.ports.cv.output != nullptr)
        {
            for (int i=0; info.ports.cv.output[i].valid; ++i)
                _clear_port_info(info.ports.cv.output[i]);
            delete[] info.ports.cv.output;
        }
        if (info.ports.midi.input != nullptr)
        {
            for (int i=0; info.ports.midi.input[i].valid; ++i)
                _clear_port_info(info.ports.midi.input[i]);
            delete[] info.ports.midi.input;
        }
        if (info.ports.midi.output != nullptr)
        {
            for (int i=0; info.ports.midi.output[i].valid; ++i)
                _clear_port_info(info.ports.midi.output[i]);
            delete[] info.ports.midi.output;
        }
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
        if (retIndex >= newsize)
            continue;

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
        _plug_ret[retIndex++] = &PLUGNFO[uri];
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
