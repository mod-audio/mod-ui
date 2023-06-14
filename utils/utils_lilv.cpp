/*
 * MOD-UI utilities
 * Copyright (C) 2015-2023 Filipe Coelho <falktx@falktx.com>
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

#include <lv2/core/lv2.h>
#include <lv2/atom/atom.h>
#include <lv2/midi/midi.h>
#include <lv2/morph/morph.h>
#include <lv2/patch/patch.h>
#include <lv2/port-props/port-props.h>
#include <lv2/presets/presets.h>
#include <lv2/state/state.h>
#include <lv2/units/units.h>

// do not enable external-ui support in embed targets
#if !(defined(_MOD_DEVICE_DUO) || defined(_MOD_DEVICE_DUOX) || defined(_MOD_DEVICE_DWARF))
#define WITH_EXTERNAL_UI_SUPPORT
#endif

#ifdef WITH_EXTERNAL_UI_SUPPORT
#include <lv2/ui/ui.h>
#endif

#include "sha1/sha1.h"

#include <algorithm>
#include <cassert>
#include <fstream>
#include <list>
#include <map>
#include <string>
#include <unordered_map>
#include <vector>

#ifdef __linux__
# include <sched.h>
#endif

#define OS_SEP '/'

#define MOD_LICENSE__interface "http://moddevices.com/ns/ext/license#interface"

#ifndef HAVE_NEW_LILV
#warning Your current lilv version is too old, please update it
char* lilv_file_uri_parse2(const char* uri, const char*)
{
    if (const char* const parsed = lilv_uri_to_path(uri))
        return strdup(parsed);
    return nullptr;
}

LilvNode* lilv_new_file_uri2(LilvWorld* world, const char*, const char* path)
{
    const size_t pathlen = strlen(path);
    char* const uripath = static_cast<char*>(malloc(pathlen+12));
    strcpy(uripath, "file://");
    strcat(uripath, path);

    LilvNode* const ret = lilv_new_uri(world, uripath);

    free(uripath);
    return ret;
}
#define lilv_free(x) free(x)
#define lilv_file_uri_parse(x,y) lilv_file_uri_parse2(x,y)
#define lilv_new_file_uri(x,y,z) lilv_new_file_uri2(x,y,z)
#endif

#ifndef LV2_CORE__Parameter
#define LV2_CORE__Parameter LV2_CORE_PREFIX "Parameter" // http://lv2plug.in/ns/lv2core#Parameter
#endif

// our lilv world
LilvWorld* W = nullptr;

// list of loaded bundles
std::list<std::string> BUNDLES;

// list of lilv plugins
const LilvPlugins* PLUGINS = nullptr;

// plugin info, mapped to URIs
std::unordered_map<std::string, PluginInfo> PLUGNFO;
std::unordered_map<std::string, const PluginInfo_Mini*> PLUGNFO_Mini;

// list of plugins that need reload (preset data only)
std::list<std::string> PLUGINStoReload;

// static factory info (only loaded once)
const PedalboardInfo_Mini** FACTORYINFO = nullptr;

// read KEYS_PATH. NOTE: assumes trailing separator
static const char* const KEYS_PATH = getenv("MOD_KEYS_PATH");
static const size_t KEYS_PATHlen = (KEYS_PATH != NULL && *KEYS_PATH != '\0') 
                                 ? strlen(KEYS_PATH)
                                 : 0;

// read FACTORY_PEDALBOARDS_DIR
static const char* const FACTORY_PEDALBOARDS_DIR = getenv("MOD_FACTORY_PEDALBOARDS_DIR");
static const size_t FACTORY_PEDALBOARDS_DIRlen = (FACTORY_PEDALBOARDS_DIR != NULL && *FACTORY_PEDALBOARDS_DIR != '\0')
                                               ? strlen(FACTORY_PEDALBOARDS_DIR)
                                               : 0;

// some other cached values
static const char* const HOME = getenv("HOME");
static size_t HOMElen = strlen(HOME);

// configuration
static const bool kAllowRegularCV = getenv("MOD_UI_ALLOW_REGULAR_CV") != nullptr;

#define PluginInfo_Mini_Init {                   \
    false,                                       \
    nullptr, nullptr, nullptr, nullptr, nullptr, \
    nullptr, nullptr, 0, 0, 0, 0, 0,             \
    { nullptr, nullptr, nullptr },               \
    false                                        \
}

#define PluginInfo_Init {                            \
    false,                                           \
    nullptr, nullptr,                                \
    nullptr, nullptr, nullptr, nullptr, nullptr,     \
    nullptr, nullptr, 0, 0, 0, 0, 0, false,          \
    nullptr, nullptr,                                \
    { nullptr, nullptr, nullptr },                   \
    nullptr,                                         \
    {                                                \
        nullptr, nullptr, nullptr, nullptr, nullptr, \
        nullptr, nullptr, nullptr, nullptr,          \
        nullptr, nullptr,                            \
        nullptr, nullptr, nullptr, nullptr,          \
        nullptr, nullptr                             \
    },                                               \
    {                                                \
        { nullptr, nullptr },                        \
        { nullptr, nullptr },                        \
        { nullptr, nullptr },                        \
        { nullptr, nullptr }                         \
    },                                               \
    nullptr,                                         \
    nullptr                                          \
}

// Blacklisted plugins, which don't work properly on MOD for various reasons
static const std::vector<std::string> BLACKLIST = {
    "urn:mod:mclk",
    "urn:mod:gxtuner",
    "urn:mod:tuna",
    "http://calf.sourceforge.net/plugins/Analyzer",
};

// --------------------------------------------------------------------------------------------------------

inline char* getenv_strdup_or_null(const char* const env)
{
    if (const char* const value = getenv(env))
        return strdup(value);
    return nullptr;
}

template<typename T>
inline bool contains(const std::map<std::string, T>& map, const std::string& value)
{
    return map.find(value) != map.end();
}

template<typename T>
inline bool contains(const std::unordered_map<std::string, T>& map, const std::string& value)
{
    return map.find(value) != map.end();
}

inline bool ends_with(const std::string& value, const std::string ending)
{
    if (ending.size() > value.size())
        return false;
    return std::equal(ending.rbegin(), ending.rend(), value.rbegin());
}

inline bool is_factory_pedalboard(const char* const bundle)
{
    if (FACTORY_PEDALBOARDS_DIRlen != 0)
        return strncmp(bundle, FACTORY_PEDALBOARDS_DIR, FACTORY_PEDALBOARDS_DIRlen) == 0;

    return strncmp(bundle, "/usr/share/mod/pedalboards/", 27) == 0;
}

inline std::string sha1(const char* const cstring)
{
    sha1nfo s;
    sha1_init(&s);
    sha1_write(&s, cstring, strlen(cstring));

    char hashdec[HASH_LENGTH*2+1];

    uint8_t* const hashenc = sha1_result(&s);
    for (int i=0; i<HASH_LENGTH; i++) {
        sprintf(hashdec+(i*2), "%02x", hashenc[i]);
    }
    hashdec[HASH_LENGTH*2] = '\0';

    return std::string(hashdec);
}

// --------------------------------------------------------------------------------------------------------

#define LILV_NS_INGEN    "http://drobilla.net/ns/ingen#"
#define LILV_NS_MOD      "http://moddevices.com/ns/mod#"
#define LILV_NS_MODGUI   "http://moddevices.com/ns/modgui#"
#define LILV_NS_MODPEDAL "http://moddevices.com/ns/modpedal#"

#define MOD__CVPort LILV_NS_MOD "CVPort"

struct NamespaceDefinitions_Mini {
    LilvNode* const rdf_type;
    LilvNode* const rdfs_comment;
    LilvNode* const lv2core_microVersion;
    LilvNode* const lv2core_minorVersion;
    LilvNode* const mod_brand;
    LilvNode* const mod_label;
    LilvNode* const mod_release;
    LilvNode* const mod_builder;
    LilvNode* const mod_buildEnvironment;
    LilvNode* const modlicense_interface;
    LilvNode* const modgui_gui;
    LilvNode* const modgui_resourcesDirectory;
    LilvNode* const modgui_screenshot;
    LilvNode* const modgui_thumbnail;

    NamespaceDefinitions_Mini(LilvWorld* const w)
        : rdf_type                 (lilv_new_uri(w, LILV_NS_RDF    "type"              )),
          rdfs_comment             (lilv_new_uri(w, LILV_NS_RDFS   "comment"           )),
          lv2core_microVersion     (lilv_new_uri(w, LILV_NS_LV2    "microVersion"      )),
          lv2core_minorVersion     (lilv_new_uri(w, LILV_NS_LV2    "minorVersion"      )),
          mod_brand                (lilv_new_uri(w, LILV_NS_MOD    "brand"             )),
          mod_label                (lilv_new_uri(w, LILV_NS_MOD    "label"             )),
          mod_release              (lilv_new_uri(w, LILV_NS_MOD    "releaseNumber"     )),
          mod_builder              (lilv_new_uri(w, LILV_NS_MOD    "builderVersion"    )),
          mod_buildEnvironment     (lilv_new_uri(w, LILV_NS_MOD    "buildEnvironment"  )),
          modlicense_interface     (lilv_new_uri(w, MOD_LICENSE__interface             )),
          modgui_gui               (lilv_new_uri(w, LILV_NS_MODGUI "gui"               )),
          modgui_resourcesDirectory(lilv_new_uri(w, LILV_NS_MODGUI "resourcesDirectory")),
          modgui_screenshot        (lilv_new_uri(w, LILV_NS_MODGUI "screenshot"        )),
          modgui_thumbnail         (lilv_new_uri(w, LILV_NS_MODGUI "thumbnail"         )) {}

    ~NamespaceDefinitions_Mini()
    {
        lilv_node_free(rdf_type);
        lilv_node_free(rdfs_comment);
        lilv_node_free(lv2core_microVersion);
        lilv_node_free(lv2core_minorVersion);
        lilv_node_free(mod_brand);
        lilv_node_free(mod_label);
        lilv_node_free(mod_release);
        lilv_node_free(mod_builder);
        lilv_node_free(mod_buildEnvironment);
        lilv_node_free(modlicense_interface);
        lilv_node_free(modgui_gui);
        lilv_node_free(modgui_resourcesDirectory);
        lilv_node_free(modgui_screenshot);
        lilv_node_free(modgui_thumbnail);
    }
};

struct NamespaceDefinitions {
    LilvNode* const doap_license;
    LilvNode* const doap_maintainer;
    LilvNode* const foaf_homepage;
    LilvNode* const rdf_type;
    LilvNode* const rdfs_comment;
    LilvNode* const rdfs_label;
    LilvNode* const rdfs_range;
    LilvNode* const lv2core_designation;
    LilvNode* const lv2core_index;
    LilvNode* const lv2core_microVersion;
    LilvNode* const lv2core_minorVersion;
    LilvNode* const lv2core_name;
    LilvNode* const lv2core_project;
    LilvNode* const lv2core_portProperty;
    LilvNode* const lv2core_shortName;
    LilvNode* const lv2core_symbol;
    LilvNode* const lv2core_default;
    LilvNode* const lv2core_minimum;
    LilvNode* const lv2core_maximum;
    LilvNode* const lv2core_extensionData;
    LilvNode* const mod_brand;
    LilvNode* const mod_label;
    LilvNode* const mod_default;
    LilvNode* const mod_default_custom;
    LilvNode* const mod_minimum;
    LilvNode* const mod_maximum;
    LilvNode* const mod_rangeSteps;
    LilvNode* const mod_release;
    LilvNode* const mod_builder;
    LilvNode* const mod_buildEnvironment;
    LilvNode* const mod_fileTypes;
    LilvNode* const mod_supportedExtensions;
    LilvNode* const mod_rawMIDIClockAccess;
    LilvNode* const modlicense_interface;
    LilvNode* const modgui_gui;
    LilvNode* const modgui_resourcesDirectory;
    LilvNode* const modgui_iconTemplate;
    LilvNode* const modgui_settingsTemplate;
    LilvNode* const modgui_javascript;
    LilvNode* const modgui_stylesheet;
    LilvNode* const modgui_screenshot;
    LilvNode* const modgui_thumbnail;
    LilvNode* const modgui_discussionURL;
    LilvNode* const modgui_documentation;
    LilvNode* const modgui_brand;
    LilvNode* const modgui_label;
    LilvNode* const modgui_model;
    LilvNode* const modgui_panel;
    LilvNode* const modgui_color;
    LilvNode* const modgui_knob;
    LilvNode* const modgui_port;
    LilvNode* const modgui_monitoredOutputs;
    LilvNode* const atom_bufferType;
    LilvNode* const atom_Sequence;
    LilvNode* const midi_MidiEvent;
    LilvNode* const pprops_rangeSteps;
    LilvNode* const patch_readable;
    LilvNode* const patch_writable;
    LilvNode* const pset_Preset;
    LilvNode* const state_state;
    LilvNode* const units_render;
    LilvNode* const units_symbol;
    LilvNode* const units_unit;

    NamespaceDefinitions(LilvWorld* const w)
        : doap_license             (lilv_new_uri(w, LILV_NS_DOAP   "license"           )),
          doap_maintainer          (lilv_new_uri(w, LILV_NS_DOAP   "maintainer"        )),
          foaf_homepage            (lilv_new_uri(w, LILV_NS_FOAF   "homepage"          )),
          rdf_type                 (lilv_new_uri(w, LILV_NS_RDF    "type"              )),
          rdfs_comment             (lilv_new_uri(w, LILV_NS_RDFS   "comment"           )),
          rdfs_label               (lilv_new_uri(w, LILV_NS_RDFS   "label"             )),
          rdfs_range               (lilv_new_uri(w, LILV_NS_RDFS   "range"             )),
          lv2core_designation      (lilv_new_uri(w, LILV_NS_LV2    "designation"       )),
          lv2core_index            (lilv_new_uri(w, LILV_NS_LV2    "index"             )),
          lv2core_microVersion     (lilv_new_uri(w, LILV_NS_LV2    "microVersion"      )),
          lv2core_minorVersion     (lilv_new_uri(w, LILV_NS_LV2    "minorVersion"      )),
          lv2core_name             (lilv_new_uri(w, LILV_NS_LV2    "name"              )),
          lv2core_project          (lilv_new_uri(w, LILV_NS_LV2    "project"           )),
          lv2core_portProperty     (lilv_new_uri(w, LILV_NS_LV2    "portProperty"      )),
          lv2core_shortName        (lilv_new_uri(w, LILV_NS_LV2    "shortName"         )),
          lv2core_symbol           (lilv_new_uri(w, LILV_NS_LV2    "symbol"            )),
          lv2core_default          (lilv_new_uri(w, LILV_NS_LV2    "default"           )),
          lv2core_minimum          (lilv_new_uri(w, LILV_NS_LV2    "minimum"           )),
          lv2core_maximum          (lilv_new_uri(w, LILV_NS_LV2    "maximum"           )),
          lv2core_extensionData    (lilv_new_uri(w, LILV_NS_LV2    "extensionData"     )),
          mod_brand                (lilv_new_uri(w, LILV_NS_MOD    "brand"             )),
          mod_label                (lilv_new_uri(w, LILV_NS_MOD    "label"             )),
          mod_default              (lilv_new_uri(w, LILV_NS_MOD    "default"           )),
#if defined(_MOD_DEVICE_DUO)
          mod_default_custom       (lilv_new_uri(w, LILV_NS_MOD    "default_duo"       )),
#elif defined(_MOD_DEVICE_DUOX)
          mod_default_custom       (lilv_new_uri(w, LILV_NS_MOD    "default_duox"      )),
#elif defined(_MOD_DEVICE_DWARF)
          mod_default_custom       (lilv_new_uri(w, LILV_NS_MOD    "default_dwarf"     )),
#elif defined(_MOD_DEVICE_X86_64)
          mod_default_custom       (lilv_new_uri(w, LILV_NS_MOD    "default_x64"       )),
#else
          mod_default_custom       (nullptr),
#endif
          mod_minimum              (lilv_new_uri(w, LILV_NS_MOD    "minimum"           )),
          mod_maximum              (lilv_new_uri(w, LILV_NS_MOD    "maximum"           )),
          mod_rangeSteps           (lilv_new_uri(w, LILV_NS_MOD    "rangeSteps"        )),
          mod_release              (lilv_new_uri(w, LILV_NS_MOD    "releaseNumber"     )),
          mod_builder              (lilv_new_uri(w, LILV_NS_MOD    "builderVersion"    )),
          mod_buildEnvironment     (lilv_new_uri(w, LILV_NS_MOD    "buildEnvironment"  )),
          mod_fileTypes            (lilv_new_uri(w, LILV_NS_MOD    "fileTypes"         )),
          mod_supportedExtensions  (lilv_new_uri(w, LILV_NS_MOD    "supportedExtensions")),
          mod_rawMIDIClockAccess   (lilv_new_uri(w, LILV_NS_MOD    "rawMIDIClockAccess")),
          modlicense_interface     (lilv_new_uri(w, MOD_LICENSE__interface             )),
          modgui_gui               (lilv_new_uri(w, LILV_NS_MODGUI "gui"               )),
          modgui_resourcesDirectory(lilv_new_uri(w, LILV_NS_MODGUI "resourcesDirectory")),
          modgui_iconTemplate      (lilv_new_uri(w, LILV_NS_MODGUI "iconTemplate"      )),
          modgui_settingsTemplate  (lilv_new_uri(w, LILV_NS_MODGUI "settingsTemplate"  )),
          modgui_javascript        (lilv_new_uri(w, LILV_NS_MODGUI "javascript"        )),
          modgui_stylesheet        (lilv_new_uri(w, LILV_NS_MODGUI "stylesheet"        )),
          modgui_screenshot        (lilv_new_uri(w, LILV_NS_MODGUI "screenshot"        )),
          modgui_thumbnail         (lilv_new_uri(w, LILV_NS_MODGUI "thumbnail"         )),
          modgui_discussionURL     (lilv_new_uri(w, LILV_NS_MODGUI "discussionURL"     )),
          modgui_documentation     (lilv_new_uri(w, LILV_NS_MODGUI "documentation"     )),
          modgui_brand             (lilv_new_uri(w, LILV_NS_MODGUI "brand"             )),
          modgui_label             (lilv_new_uri(w, LILV_NS_MODGUI "label"             )),
          modgui_model             (lilv_new_uri(w, LILV_NS_MODGUI "model"             )),
          modgui_panel             (lilv_new_uri(w, LILV_NS_MODGUI "panel"             )),
          modgui_color             (lilv_new_uri(w, LILV_NS_MODGUI "color"             )),
          modgui_knob              (lilv_new_uri(w, LILV_NS_MODGUI "knob"              )),
          modgui_port              (lilv_new_uri(w, LILV_NS_MODGUI "port"              )),
          modgui_monitoredOutputs  (lilv_new_uri(w, LILV_NS_MODGUI "monitoredOutputs"  )),
          atom_bufferType          (lilv_new_uri(w, LV2_ATOM__bufferType               )),
          atom_Sequence            (lilv_new_uri(w, LV2_ATOM__Sequence                 )),
          midi_MidiEvent           (lilv_new_uri(w, LV2_MIDI__MidiEvent                )),
          pprops_rangeSteps        (lilv_new_uri(w, LV2_PORT_PROPS__rangeSteps         )),
          patch_readable           (lilv_new_uri(w, LV2_PATCH__readable                )),
          patch_writable           (lilv_new_uri(w, LV2_PATCH__writable                )),
          pset_Preset              (lilv_new_uri(w, LV2_PRESETS__Preset                )),
          state_state              (lilv_new_uri(w, LV2_STATE__state                   )),
          units_render             (lilv_new_uri(w, LV2_UNITS__render                  )),
          units_symbol             (lilv_new_uri(w, LV2_UNITS__symbol                  )),
          units_unit               (lilv_new_uri(w, LV2_UNITS__unit                    )) {}

    ~NamespaceDefinitions()
    {
        lilv_node_free(doap_license);
        lilv_node_free(doap_maintainer);
        lilv_node_free(foaf_homepage);
        lilv_node_free(rdf_type);
        lilv_node_free(rdfs_comment);
        lilv_node_free(rdfs_label);
        lilv_node_free(rdfs_range);
        lilv_node_free(lv2core_designation);
        lilv_node_free(lv2core_index);
        lilv_node_free(lv2core_microVersion);
        lilv_node_free(lv2core_minorVersion);
        lilv_node_free(lv2core_name);
        lilv_node_free(lv2core_project);
        lilv_node_free(lv2core_portProperty);
        lilv_node_free(lv2core_shortName);
        lilv_node_free(lv2core_symbol);
        lilv_node_free(lv2core_default);
        lilv_node_free(lv2core_minimum);
        lilv_node_free(lv2core_maximum);
        lilv_node_free(lv2core_extensionData);
        lilv_node_free(mod_brand);
        lilv_node_free(mod_label);
        lilv_node_free(mod_default);
        lilv_node_free(mod_default_custom);
        lilv_node_free(mod_minimum);
        lilv_node_free(mod_maximum);
        lilv_node_free(mod_rangeSteps);
        lilv_node_free(mod_release);
        lilv_node_free(mod_builder);
        lilv_node_free(mod_buildEnvironment);
        lilv_node_free(mod_fileTypes);
        lilv_node_free(mod_supportedExtensions);
        lilv_node_free(mod_rawMIDIClockAccess);
        lilv_node_free(modlicense_interface);
        lilv_node_free(modgui_gui);
        lilv_node_free(modgui_resourcesDirectory);
        lilv_node_free(modgui_iconTemplate);
        lilv_node_free(modgui_settingsTemplate);
        lilv_node_free(modgui_javascript);
        lilv_node_free(modgui_stylesheet);
        lilv_node_free(modgui_screenshot);
        lilv_node_free(modgui_thumbnail);
        lilv_node_free(modgui_discussionURL);
        lilv_node_free(modgui_documentation);
        lilv_node_free(modgui_brand);
        lilv_node_free(modgui_label);
        lilv_node_free(modgui_model);
        lilv_node_free(modgui_panel);
        lilv_node_free(modgui_color);
        lilv_node_free(modgui_knob);
        lilv_node_free(modgui_port);
        lilv_node_free(modgui_monitoredOutputs);
        lilv_node_free(atom_bufferType);
        lilv_node_free(atom_Sequence);
        lilv_node_free(midi_MidiEvent);
        lilv_node_free(pprops_rangeSteps);
        lilv_node_free(patch_readable);
        lilv_node_free(patch_writable);
        lilv_node_free(pset_Preset);
        lilv_node_free(state_state);
        lilv_node_free(units_render);
        lilv_node_free(units_symbol);
        lilv_node_free(units_unit);
    }
};

enum PortDirection {
    kPortDirectionNull,
    kPortDirectionInput,
    kPortDirectionOutput,
};

enum PortType {
    kPortTypeNull,
    kPortTypeAudio,
    kPortTypeControl,
    kPortTypeCV,
    kPortTypeMIDI,
};

enum TimePortType {
    kTimePortTypeNull,
    kTimePortTypeBeatsPerBar,
    kTimePortTypeBeatsPerMinute,
    kTimePortTypeRolling,
};

static const char* const kCategoryDelayPlugin[] = { "Delay", nullptr };
static const char* const kCategoryDistortionPlugin[] = { "Distortion", nullptr };
static const char* const kCategoryWaveshaperPlugin[] = { "Distortion", "Waveshaper", nullptr };
static const char* const kCategoryDynamicsPlugin[] = { "Dynamics", nullptr };
static const char* const kCategoryAmplifierPlugin[] = { "Dynamics", "Amplifier", nullptr };
static const char* const kCategoryCompressorPlugin[] = { "Dynamics", "Compressor", nullptr };
static const char* const kCategoryExpanderPlugin[] = { "Dynamics", "Expander", nullptr };
static const char* const kCategoryGatePlugin[] = { "Dynamics", "Gate", nullptr };
static const char* const kCategoryLimiterPlugin[] = { "Dynamics", "Limiter", nullptr };
static const char* const kCategoryFilterPlugin[] = { "Filter", nullptr };
static const char* const kCategoryAllpassPlugin[] = { "Filter", "Allpass", nullptr };
static const char* const kCategoryBandpassPlugin[] = { "Filter", "Bandpass", nullptr };
static const char* const kCategoryCombPlugin[] = { "Filter", "Comb", nullptr };
static const char* const kCategoryEQPlugin[] = { "Filter", "Equaliser", nullptr };
static const char* const kCategoryMultiEQPlugin[] = { "Filter", "Equaliser", "Multiband", nullptr };
static const char* const kCategoryParaEQPlugin[] = { "Filter", "Equaliser", "Parametric", nullptr };
static const char* const kCategoryHighpassPlugin[] = { "Filter", "Highpass", nullptr };
static const char* const kCategoryLowpassPlugin[] = { "Filter", "Lowpass", nullptr };
static const char* const kCategoryGeneratorPlugin[] = { "Generator", nullptr };
static const char* const kCategoryConstantPlugin[] = { "Generator", "Constant", nullptr };
static const char* const kCategoryInstrumentPlugin[] = { "Generator", "Instrument", nullptr };
static const char* const kCategoryOscillatorPlugin[] = { "Generator", "Oscillator", nullptr };
static const char* const kCategoryModulatorPlugin[] = { "Modulator", nullptr };
static const char* const kCategoryChorusPlugin[] = { "Modulator", "Chorus", nullptr };
static const char* const kCategoryFlangerPlugin[] = { "Modulator", "Flanger", nullptr };
static const char* const kCategoryPhaserPlugin[] = { "Modulator", "Phaser", nullptr };
static const char* const kCategoryReverbPlugin[] = { "Reverb", nullptr };
static const char* const kCategorySimulatorPlugin[] = { "Simulator", nullptr };
static const char* const kCategorySpatialPlugin[] = { "Spatial", nullptr };
static const char* const kCategorySpectralPlugin[] = { "Spectral", nullptr };
static const char* const kCategoryPitchPlugin[] = { "Spectral", "Pitch Shifter", nullptr };
static const char* const kCategoryUtilityPlugin[] = { "Utility", nullptr };
static const char* const kCategoryAnalyserPlugin[] = { "Utility", "Analyser", nullptr };
static const char* const kCategoryConverterPlugin[] = { "Utility", "Converter", nullptr };
static const char* const kCategoryFunctionPlugin[] = { "Utility", "Function", nullptr };
static const char* const kCategoryMixerPlugin[] = { "Utility", "Mixer", nullptr };
static const char* const kCategoryMIDIPlugin[] = { "MIDI", "Utility", nullptr };
static const char* const kCategoryMIDIPluginMOD[] = { "MIDI", nullptr };
static const char* const kCategoryMaxGenPluginMOD[] = { "MaxGen", nullptr };
static const char* const kCategoryCamomilePluginMOD[] = { "Camomile", nullptr };
static const char* const kCategoryControlVoltagePluginMOD[] = { "ControlVoltage", nullptr };

static const char* const kBuildEnvironmentProd = "prod";
static const char* const kBuildEnvironmentDev = "dev";
static const char* const kBuildEnvironmentLabs = "labs";

static const char* const kStabilityExperimental = "experimental";
static const char* const kStabilityStable = "stable";
static const char* const kStabilityTesting = "testing";
// static const char* const kStabilityUnstable = "unstable";

static const char* const kUntitled = "Untitled";

// label, render, symbol
static const char* const kUnit_s[] = { "seconds", "%f s", "s" };
static const char* const kUnit_ms[] = { "milliseconds", "%f ms", "ms" };
static const char* const kUnit_min[] = { "minutes", "%f mins", "min" };
static const char* const kUnit_bar[] = { "bars", "%f bars", "bars" };
static const char* const kUnit_beat[] = { "beats", "%f beats", "beats" };
static const char* const kUnit_frame[] = { "audio frames", "%f frames", "frames" };
static const char* const kUnit_m[] = { "metres", "%f m", "m" };
static const char* const kUnit_cm[] = { "centimetres", "%f cm", "cm" };
static const char* const kUnit_mm[] = { "millimetres", "%f mm", "mm" };
static const char* const kUnit_km[] = { "kilometres", "%f km", "km" };
static const char* const kUnit_inch[] = { "inches", """%f\"""", "in" };
static const char* const kUnit_mile[] = { "miles", "%f mi", "mi" };
static const char* const kUnit_db[] = { "decibels", "%f dB", "dB" };
static const char* const kUnit_pc[] = { "percent", "%f%%", "%" };
static const char* const kUnit_coef[] = { "coefficient", "* %f", "*" };
static const char* const kUnit_hz[] = { "hertz", "%f Hz", "Hz" };
static const char* const kUnit_khz[] = { "kilohertz", "%f kHz", "kHz" };
static const char* const kUnit_mhz[] = { "megahertz", "%f MHz", "MHz" };
static const char* const kUnit_bpm[] = { "beats per minute", "%f BPM", "BPM" };
static const char* const kUnit_oct[] = { "octaves", "%f octaves", "oct" };
static const char* const kUnit_cent[] = { "cents", "%f ct", "ct" };
static const char* const kUnit_semitone12TET[] = { "semitones", "%f semi", "semi" };
static const char* const kUnit_degree[] = { "degrees", "%f deg", "deg" };
static const char* const kUnit_midiNote[] = { "MIDI note", "MIDI note %d", "note" };
static const char* const kUnit_volts[] = { "volts", "%f v", "v" };

static const char nc[1] = { '\0' };

static bool _isalnum(const char* const string)
{
    for (size_t i=0;; ++i)
    {
        if (string[i] == '\0')
            return (i != 0);
        if (! isalnum(string[i]))
            return false;
    }
}

static void _swap_preset_data(PluginPreset* preset1, PluginPreset* preset2)
{
    std::swap(preset1->uri,   preset2->uri);
    std::swap(preset1->label, preset2->label);
    std::swap(preset1->path,  preset2->path);
}

// adjusted from https://stackoverflow.com/questions/19612152/quicksort-string-array-in-c
static void _sort_presets_data(PluginPreset presets[], unsigned int count)
{
    if (count <= 1)
        return;

    unsigned int pvt = 0;

    // swap a randomly selected value to the last node
    _swap_preset_data(presets+(rand() % count), presets+(count-1));

    // reset the pivot index to zero, then scan
    for (unsigned int i=0; i<count-1; ++i)
    {
        if (strcmp(presets[i].uri, presets[count-1].uri) < 0)
            _swap_preset_data(presets+i, presets+(pvt++));
    }

    // move the pivot value into its place
    _swap_preset_data(presets+pvt, presets+count-1);

    // and invoke on the subsequences. does NOT include the pivot-slot
    _sort_presets_data(presets, pvt++);
    _sort_presets_data(presets+pvt, count - pvt);
}

// adjust bundle safely to lilv, as it wants the last character as the separator
// this also ensures paths are always written the same way
// NOTE: returned value must not be freed or cached
static const char* _get_safe_bundlepath(const char* const bundle, size_t& bundlepathsize)
{
    static char tmppath[PATH_MAX+2];
    char* bundlepath = realpath(bundle, tmppath);

    if (bundlepath == nullptr)
    {
        bundlepathsize = 0;
        return nullptr;
    }

    bundlepathsize = strlen(bundlepath);

    if (bundlepathsize <= 1)
        return nullptr;

    if (bundlepath[bundlepathsize] != OS_SEP)
    {
        bundlepath[bundlepathsize  ] = OS_SEP;
        bundlepath[bundlepathsize+1] = '\0';
    }

    return bundlepath;
}

// proper lilv_file_uri_parse function that returns absolute paths
static char* lilv_file_abspath(const char* const path)
{
    if (char* const lilvpath = lilv_file_uri_parse(path, nullptr))
    {
        char* const ret = realpath(lilvpath, nullptr);
        lilv_free(lilvpath);
        return ret;
    }

    return nullptr;
}

// fill in `bundles` vector with all known data bundles (main bundle + local presets)
static void _fill_bundles_for_plugin(std::list<std::string>& bundles, const LilvPlugin* const p, LilvNode* const pset_Preset)
{
    char* lilvparsed;
    const char* bundlepath;
    size_t bundlepathsize;

    if (const LilvNodes* const datanodes = lilv_plugin_get_data_uris(p))
    {
        LILV_FOREACH(nodes, itbnds, datanodes)
        {
            const LilvNode* const bundlenode = lilv_nodes_get(datanodes, itbnds);

            if (bundlenode == nullptr)
                continue;
            if (! lilv_node_is_uri(bundlenode))
                continue;

            lilvparsed = lilv_file_uri_parse(lilv_node_as_uri(bundlenode), nullptr);
            if (lilvparsed == nullptr)
                continue;

            bundlepath = dirname(lilvparsed);
            if (bundlepath == nullptr || strcmp(bundlepath, ".") == 0)
            {
                lilv_free(lilvparsed);
                continue;
            }

            bundlepath = _get_safe_bundlepath(bundlepath, bundlepathsize);
            lilv_free(lilvparsed);

            if (bundlepath == nullptr)
                continue;

            const std::string bundlestr = bundlepath;

            if (std::find(bundles.begin(), bundles.end(), bundlestr) == bundles.end())
                bundles.push_back(bundlestr);
        }
    }

    if (LilvNodes* const presetnodes = lilv_plugin_get_related(p, pset_Preset))
    {
        LILV_FOREACH(nodes, itprs, presetnodes)
        {
            const LilvNode* const presetnode = lilv_nodes_get(presetnodes, itprs);

            if (presetnode == nullptr)
                continue;
            if (! lilv_node_is_uri(presetnode))
                continue;

            lilvparsed = lilv_file_uri_parse(lilv_node_as_uri(presetnode), nullptr);
            if (lilvparsed == nullptr)
                continue;

            bundlepath = dirname(lilvparsed);
            if (bundlepath == nullptr || strcmp(bundlepath, ".") == 0)
            {
                lilv_free(lilvparsed);
                continue;
            }

            bundlepath = _get_safe_bundlepath(bundlepath, bundlepathsize);
            lilv_free(lilvparsed);

            if (bundlepath == nullptr)
                continue;

            const std::string bundlestr = bundlepath;

            if (std::find(bundles.begin(), bundles.end(), bundlestr) == bundles.end())
                bundles.push_back(bundlestr);
        }
        lilv_nodes_free(presetnodes);
    }
}

// used below
static void _fill_units(LilvWorld* const w, PluginPortUnits& portunits, LilvNode* const uunit, const NamespaceDefinitions& ns);

// fill in parameter data, defined as function because writable/readable code is pretty much the same
static void _fill_parameters_for_plugin(LilvWorld* const w,
                                        const LilvPlugin* const p,
                                        const NamespaceDefinitions& ns,
                                        std::map<std::string, PluginParameter>& usedParameters,
                                        const bool writable)
{
    if (LilvNodes* const patches = lilv_plugin_get_value(p, writable ? ns.patch_writable : ns.patch_readable))
    {
        if (lilv_nodes_size(patches) != 0)
        {
            // used to fetch default values
            LilvNode* const statenode = lilv_world_get(w, lilv_plugin_get_uri(p), ns.state_state, nullptr);

            LILV_FOREACH(nodes, itpatches, patches)
            {
                const LilvNode* const patch = lilv_nodes_get(patches, itpatches);
                const char* const patch_uri = lilv_node_as_uri(patch);

                if (contains(usedParameters, patch_uri))
                {
                    PluginParameter& param(usedParameters[patch_uri]);

                    if (writable)
                        param.writable = true;
                    else
                        param.readable = true;

                    continue;
                }

                LilvNode* const typeNode = lilv_world_get(w, patch, ns.rdf_type, nullptr);

                if (typeNode == nullptr)
                    continue;

                if (strcmp(lilv_node_as_uri(typeNode), LV2_CORE__Parameter) != 0)
                {
                    lilv_node_free(typeNode);
                    continue;
                }

                LilvNode* const rangeNode = lilv_world_get(w, patch, ns.rdfs_range, nullptr);

                if (rangeNode == nullptr)
                {
                    lilv_node_free(typeNode);
                    continue;
                }

                LilvNode* const labelNode = lilv_world_get(w, patch, ns.rdfs_label, nullptr);

                if (labelNode == nullptr)
                {
                    lilv_node_free(rangeNode);
                    lilv_node_free(typeNode);
                    continue;
                }

                PluginParameter param;
                memset(&param, 0, sizeof(PluginParameter));

                param.valid = true;
                param.uri   = strdup(patch_uri);
                param.label = strdup(lilv_node_as_string(labelNode));
                param.type  = strdup(lilv_node_as_string(rangeNode));

                if (writable)
                    param.writable = true;
                else
                    param.readable = true;

                const char* const atomType = (strncmp(param.type, LV2_ATOM_PREFIX, strlen(LV2_ATOM_PREFIX)) == 0)
                                           ? param.type + strlen(LV2_ATOM_PREFIX)
                                           : "";

                // ----------------------------------------------------------------------------------------------------
                // ranges

                if (strcmp(atomType, "Path") == 0 || strcmp(atomType, "String") == 0 || strcmp(atomType, "URI") == 0)
                {
                    param.ranges.type = 's';

                    if (LilvNode* const keynode = lilv_new_uri(w, param.uri))
                    {
                        if (LilvNode* const valuenode = lilv_world_get(w, statenode, keynode, nullptr))
                        {
                            if (strcmp(atomType, "Path") == 0)
                                param.ranges.s = lilv_file_abspath(lilv_node_as_string(valuenode));
                            else if (strcmp(atomType, "URI") == 0)
                                param.ranges.s = strdup(lilv_node_as_uri(valuenode));
                            else
                                param.ranges.s = strdup(lilv_node_as_string(valuenode));

                            lilv_node_free(valuenode);
                        }

                        lilv_node_free(keynode);
                    }
                }
                else
                {
                    LilvNode* xminimum = lilv_world_get(w, patch, ns.mod_minimum, nullptr);
                    if (xminimum == nullptr)
                        xminimum = lilv_world_get(w, patch, ns.lv2core_minimum, nullptr);

                    LilvNode* xmaximum = lilv_world_get(w, patch, ns.mod_maximum, nullptr);
                    if (xmaximum == nullptr)
                        xmaximum = lilv_world_get(w, patch, ns.lv2core_maximum, nullptr);

                    LilvNode* xdefault = ns.mod_default_custom != nullptr
                                       ? lilv_world_get(w, patch, ns.mod_default_custom, nullptr)
                                       : nullptr;
                    if (xdefault == nullptr)
                        xdefault = lilv_world_get(w, patch, ns.mod_default, nullptr);
                    if (xdefault == nullptr)
                        xdefault = lilv_world_get(w, patch, ns.lv2core_default, nullptr);

                    if (xminimum != nullptr && xmaximum != nullptr)
                    {
                        const bool isLong = strcmp(atomType, "Long") == 0;

                        if (isLong)
                        {
                            param.ranges.type = 'l';
                            param.ranges.l.min = atoll(lilv_node_as_string(xminimum));
                            param.ranges.l.max = atoll(lilv_node_as_string(xmaximum));

                            if (param.ranges.l.min >= param.ranges.l.max)
                                param.ranges.l.max = param.ranges.l.min + 1;
                        }
                        else
                        {
                            param.ranges.type = 'f';
                            param.ranges.f.min = lilv_node_as_float(xminimum);
                            param.ranges.f.max = lilv_node_as_float(xmaximum);

                            if (param.ranges.f.min >= param.ranges.f.max)
                                param.ranges.f.max = param.ranges.f.min + 1.0f;
                        }

                        if (xdefault != nullptr)
                        {
                            if (isLong)
                                param.ranges.l.def = atoll(lilv_node_as_string(xdefault));
                            else
                                param.ranges.f.def = lilv_node_as_float(xdefault);
                        }
                        else
                        {
                            if (isLong)
                                param.ranges.l.def = param.ranges.l.min;
                            else
                                param.ranges.f.def = param.ranges.f.min;
                        }
                    }
                    else if (strcmp(atomType, "Bool") == 0)
                    {
                        param.ranges.type = 'f';
                        param.ranges.f.min = 0.0f;
                        param.ranges.f.max = 1.0f;

                        if (xdefault != nullptr)
                            param.ranges.f.def = std::min(1.0f, std::max(0.0f, lilv_node_as_float(xdefault)));
                        else
                            param.ranges.f.def = param.ranges.f.min;
                    }

                    lilv_node_free(xminimum);
                    lilv_node_free(xmaximum);
                    lilv_node_free(xdefault);
                }

                // ----------------------------------------------------------------------------------------------------
                // units

                param.units.label  = nc;
                param.units.render = nc;
                param.units.symbol = nc;

                if (LilvNode* const uunit = lilv_world_get(w, patch, ns.units_unit, nullptr))
                {
                    _fill_units(w, param.units, uunit, ns);
                    lilv_node_free(uunit);
                }

                // ----------------------------------------------------------------------------------------------------
                // comment

                if (LilvNode* const node = lilv_world_get(w, patch, ns.rdfs_comment, nullptr))
                {
                    param.comment = strdup(lilv_node_as_string(node));
                    lilv_node_free(node);
                }
                else
                {
                    param.comment = nc;
                }

                // ----------------------------------------------------------------------------------------------------
                // short name

                if (LilvNode* const node = lilv_world_get(w, patch, ns.lv2core_shortName, nullptr))
                {
                    param.shortName = strdup(lilv_node_as_string(node));
                    lilv_node_free(node);
                }
                else
                {
                    param.shortName = strdup(param.label);
                }

                if (strlen(param.shortName) > 16)
                    ((char*)param.shortName)[16] = '\0';

                // ----------------------------------------------------------------------------------------------------
                // file types

                if (LilvNode* const fileTypesNode = lilv_world_get(w, patch, ns.mod_fileTypes, nullptr))
                {
                    if (char* const fileTypes = strdup(lilv_node_as_string(fileTypesNode)))
                    {
                        const size_t fileTypesLen = strlen(fileTypes);
                        uint fileTypesCount = 1;

                        // count number of items
                        for (size_t i=0; i<fileTypesLen; ++i)
                        {
                            if (fileTypes[i] == ',')
                                ++fileTypesCount;
                        }

                        const char** const fileTypesArray = new const char*[fileTypesCount+1U];
                        memset(fileTypesArray, 0, sizeof(const char*)*(fileTypesCount+1U));

                        // assign data, reusing fileTypes string pointer
                        fileTypesCount = 0;
                        fileTypesArray[0] = fileTypes;

                        for (size_t i=0; i<fileTypesLen; ++i)
                        {
                            if (fileTypes[i] == ',')
                            {
                                fileTypes[i] = '\0';
                                fileTypesArray[++fileTypesCount] = &fileTypes[i+1];
                            }
                        }

                        param.fileTypes = fileTypesArray;
                    }

                    lilv_node_free(fileTypesNode);
                }

                // ----------------------------------------------------------------------------------------------------
                // supported extensions

                if (LilvNode* const supportedExtensionsNode = lilv_world_get(w, patch, ns.mod_supportedExtensions, nullptr))
                {
                    if (char* const supportedExtensions = strdup(lilv_node_as_string(supportedExtensionsNode)))
                    {
                        const size_t supportedExtensionsLen = strlen(supportedExtensions);
                        uint supportedExtensionsCount = 1;

                        // count number of items
                        for (size_t i=0; i<supportedExtensionsLen; ++i)
                        {
                            if (supportedExtensions[i] == ',')
                                ++supportedExtensionsCount;
                        }

                        const char** const supportedExtensionsArray = new const char*[supportedExtensionsCount+1U];
                        memset(supportedExtensionsArray, 0, sizeof(const char*)*(supportedExtensionsCount+1U));

                        // assign data, reusing supportedExtensions string pointer
                        supportedExtensionsCount = 0;
                        supportedExtensionsArray[0] = supportedExtensions;

                        for (size_t i=0; i<supportedExtensionsLen; ++i)
                        {
                            if (supportedExtensions[i] == ',')
                            {
                                supportedExtensions[i] = '\0';
                                supportedExtensionsArray[++supportedExtensionsCount] = &supportedExtensions[i+1];
                            }
                        }

                        param.supportedExtensions = supportedExtensionsArray;
                    }

                    lilv_node_free(supportedExtensionsNode);
                }

                lilv_node_free(labelNode);
                lilv_node_free(rangeNode);
                lilv_node_free(typeNode);

                usedParameters[param.uri] = param;
            }

            lilv_node_free(statenode);
        }

        lilv_nodes_free(patches);
    }
}

// refresh everything
// plugins are not truly scanned here, only later per request
void _refresh()
{
    LilvWorld* const w = W;

    BUNDLES.clear();
    PLUGNFO.clear();
    PLUGNFO_Mini.clear();
    PLUGINS = lilv_world_get_all_plugins(w);

    LilvNode* const pset_Preset = lilv_new_uri(w, LV2_PRESETS__Preset);

    // Make a list of all installed bundles
    LILV_FOREACH(plugins, itpls, PLUGINS)
    {
        const LilvPlugin* const p = lilv_plugins_get(PLUGINS, itpls);
        const std::string uri = lilv_node_as_uri(lilv_plugin_get_uri(p));

        // store empty dict for later
        PLUGNFO[uri] = PluginInfo_Init;
        PLUGNFO_Mini[uri] = nullptr;

        _fill_bundles_for_plugin(BUNDLES, p, pset_Preset);
    }

    lilv_node_free(pset_Preset);
}

// common function used in 2 places
static void _place_preset_info(LilvWorld* const w,
                               PluginInfo& info,
                               const LilvPlugin* const p,
                               LilvNode* const pset_Preset,
                               LilvNode* const rdfs_label)
{
    LilvNodes* const presetnodes = lilv_plugin_get_related(p, pset_Preset);

    if (presetnodes == nullptr)
        return;

    const unsigned int presetcount = lilv_nodes_size(presetnodes);
    unsigned int prindex = 0;

    PluginPreset* const presets = new PluginPreset[presetcount+1];
    memset(presets, 0, sizeof(PluginPreset) * (presetcount+1));

    char lastSeenBundle[0xff];
    lastSeenBundle[0] = lastSeenBundle[0xff-1] = '\0';

    const char* const mainBundle(info.bundles[0]);

    std::vector<const LilvNode*> loadedPresetResourceNodes;

    LILV_FOREACH(nodes, itprs, presetnodes)
    {
        if (prindex >= presetcount)
            continue;

        const LilvNode* const presetnode = lilv_nodes_get(presetnodes, itprs);

        // try to find label without loading the preset resource first
        LilvNode* xlabel = lilv_world_get(w, presetnode, rdfs_label, nullptr);

        // failed, try loading resource
        if (xlabel == nullptr)
        {
            // if loading resource fails, skip this preset
            if (lilv_world_load_resource(w, presetnode) == -1)
                continue;

            // ok, let's try again
            xlabel = lilv_world_get(w, presetnode, rdfs_label, nullptr);

            // need to unload later
            loadedPresetResourceNodes.push_back(presetnode);
        }

        if (xlabel != nullptr)
        {
            const char* const preseturi  = lilv_node_as_uri(presetnode);
            const char*       presetpath = nc;

            // check if URI is a local file, to see if it's a user preset
            if (strncmp(preseturi, "file://", 7) == 0)
            {
                if (char* const lilvparsed = lilv_file_uri_parse(preseturi, nullptr))
                {
                    if (const char* bundlepath = dirname(lilvparsed))
                    {
                        // cache and compare last seen bundle
                        // bundles with more than 1 preset are not considered 'user' (ie, modifiable)

                        if (lastSeenBundle[0] != '\0' && strcmp(bundlepath, lastSeenBundle) == 0)
                        {
                            // invalidate previous one
                            if (presets[prindex-1].path != nc)
                            {
                                free((void*)presets[prindex-1].path);
                                presets[prindex-1].path = nc;
                            }
                        }
                        else
                        {
                            strncpy(lastSeenBundle, bundlepath, 0xff-1);

                            size_t bundlepathsize;
                            bundlepath = _get_safe_bundlepath(bundlepath, bundlepathsize);

                            if (strcmp(mainBundle, bundlepath) != 0)
                                presetpath = strdup(bundlepath);
                        }
                    }

                    lilv_free(lilvparsed);
                }
            }

            presets[prindex++] = {
                true,
                strdup(preseturi),
                strdup(lilv_node_as_string(xlabel)),
                presetpath
            };

            lilv_node_free(xlabel);
        }
    }

    if (prindex > 1)
        _sort_presets_data(presets, prindex);

#ifdef HAVE_NEW_LILV
    for (const LilvNode* presetnode : loadedPresetResourceNodes)
        lilv_world_unload_resource(w, presetnode);
#endif

    info.presets = presets;

    loadedPresetResourceNodes.clear();
    lilv_nodes_free(presetnodes);
}

static const char* const* _get_plugin_categories(const LilvPlugin* const p,
                                                 LilvNode* const rdf_type,
                                                 bool* const supported = nullptr)
{
    const char* const* category = nullptr;

    if (LilvNodes* const nodes = lilv_plugin_get_value(p, rdf_type))
    {
        LILV_FOREACH(nodes, it, nodes)
        {
            const LilvNode* const node2 = lilv_nodes_get(nodes, it);
            const char* const nodestr = lilv_node_as_string(node2);

            if (nodestr == nullptr)
                continue;

            if (strcmp(nodestr, LILV_NS_MODPEDAL "Pedalboard") == 0)
            {
                if (supported != nullptr)
                    *supported = false;
                category = nullptr;
                break;
            }

            if (const char* cat = strstr(nodestr, "http://lv2plug.in/ns/lv2core#"))
            {
                cat += 29; // strlen("http://lv2plug.in/ns/lv2core#")

                if (cat[0] == '\0')
                    continue;
                if (strcmp(cat, "Plugin") == 0)
                    continue;

                else if (strcmp(cat, "DelayPlugin") == 0)
                    category = kCategoryDelayPlugin;
                else if (strcmp(cat, "DistortionPlugin") == 0)
                    category = kCategoryDistortionPlugin;
                else if (strcmp(cat, "WaveshaperPlugin") == 0)
                    category = kCategoryWaveshaperPlugin;
                else if (strcmp(cat, "DynamicsPlugin") == 0)
                    category = kCategoryDynamicsPlugin;
                else if (strcmp(cat, "AmplifierPlugin") == 0)
                    category = kCategoryAmplifierPlugin;
                else if (strcmp(cat, "CompressorPlugin") == 0)
                    category = kCategoryCompressorPlugin;
                else if (strcmp(cat, "ExpanderPlugin") == 0)
                    category = kCategoryExpanderPlugin;
                else if (strcmp(cat, "GatePlugin") == 0)
                    category = kCategoryGatePlugin;
                else if (strcmp(cat, "LimiterPlugin") == 0)
                    category = kCategoryLimiterPlugin;
                else if (strcmp(cat, "FilterPlugin") == 0)
                    category = kCategoryFilterPlugin;
                else if (strcmp(cat, "AllpassPlugin") == 0)
                    category = kCategoryAllpassPlugin;
                else if (strcmp(cat, "BandpassPlugin") == 0)
                    category = kCategoryBandpassPlugin;
                else if (strcmp(cat, "CombPlugin") == 0)
                    category = kCategoryCombPlugin;
                else if (strcmp(cat, "EQPlugin") == 0)
                    category = kCategoryEQPlugin;
                else if (strcmp(cat, "MultiEQPlugin") == 0)
                    category = kCategoryMultiEQPlugin;
                else if (strcmp(cat, "ParaEQPlugin") == 0)
                    category = kCategoryParaEQPlugin;
                else if (strcmp(cat, "HighpassPlugin") == 0)
                    category = kCategoryHighpassPlugin;
                else if (strcmp(cat, "LowpassPlugin") == 0)
                    category = kCategoryLowpassPlugin;
                else if (strcmp(cat, "GeneratorPlugin") == 0)
                    category = kCategoryGeneratorPlugin;
                else if (strcmp(cat, "ConstantPlugin") == 0)
                    category = kCategoryConstantPlugin;
                else if (strcmp(cat, "InstrumentPlugin") == 0)
                    category = kCategoryInstrumentPlugin;
                else if (strcmp(cat, "OscillatorPlugin") == 0)
                    category = kCategoryOscillatorPlugin;
                else if (strcmp(cat, "ModulatorPlugin") == 0)
                    category = kCategoryModulatorPlugin;
                else if (strcmp(cat, "ChorusPlugin") == 0)
                    category = kCategoryChorusPlugin;
                else if (strcmp(cat, "FlangerPlugin") == 0)
                    category = kCategoryFlangerPlugin;
                else if (strcmp(cat, "PhaserPlugin") == 0)
                    category = kCategoryPhaserPlugin;
                else if (strcmp(cat, "ReverbPlugin") == 0)
                    category = kCategoryReverbPlugin;
                else if (strcmp(cat, "SimulatorPlugin") == 0)
                    category = kCategorySimulatorPlugin;
                else if (strcmp(cat, "SpatialPlugin") == 0)
                    category = kCategorySpatialPlugin;
                else if (strcmp(cat, "SpectralPlugin") == 0)
                    category = kCategorySpectralPlugin;
                else if (strcmp(cat, "PitchPlugin") == 0)
                    category = kCategoryPitchPlugin;
                else if (strcmp(cat, "UtilityPlugin") == 0)
                    category = kCategoryUtilityPlugin;
                else if (strcmp(cat, "AnalyserPlugin") == 0)
                    category = kCategoryAnalyserPlugin;
                else if (strcmp(cat, "ConverterPlugin") == 0)
                    category = kCategoryConverterPlugin;
                else if (strcmp(cat, "FunctionPlugin") == 0)
                    category = kCategoryFunctionPlugin;
                else if (strcmp(cat, "MixerPlugin") == 0)
                    category = kCategoryMixerPlugin;
                else if (strcmp(cat, "MIDIPlugin") == 0)
                    category = kCategoryMIDIPlugin;
            }
            else if (const char* cat2 = strstr(nodestr, LILV_NS_MOD))
            {
                cat2 += 29; // strlen("http://moddevices.com/ns/mod#")

                if (cat2[0] == '\0')
                    continue;

                else if (strcmp(cat2, "DelayPlugin") == 0)
                    category = kCategoryDelayPlugin;
                else if (strcmp(cat2, "DistortionPlugin") == 0)
                    category = kCategoryDistortionPlugin;
                else if (strcmp(cat2, "DynamicsPlugin") == 0)
                    category = kCategoryDynamicsPlugin;
                else if (strcmp(cat2, "FilterPlugin") == 0)
                    category = kCategoryFilterPlugin;
                else if (strcmp(cat2, "GeneratorPlugin") == 0)
                    category = kCategoryGeneratorPlugin;
                else if (strcmp(cat2, "ModulatorPlugin") == 0)
                    category = kCategoryModulatorPlugin;
                else if (strcmp(cat2, "ReverbPlugin") == 0)
                    category = kCategoryReverbPlugin;
                else if (strcmp(cat2, "SimulatorPlugin") == 0)
                    category = kCategorySimulatorPlugin;
                else if (strcmp(cat2, "SpatialPlugin") == 0)
                    category = kCategorySpatialPlugin;
                else if (strcmp(cat2, "SpectralPlugin") == 0)
                    category = kCategorySpectralPlugin;
                else if (strcmp(cat2, "UtilityPlugin") == 0)
                    category = kCategoryUtilityPlugin;
                else if (strcmp(cat2, "MIDIPlugin") == 0)
                    category = kCategoryMIDIPluginMOD;
                else if (strcmp(cat2, "MaxGenPlugin") == 0)
                    category = kCategoryMaxGenPluginMOD;
                else if (strcmp(cat2, "CamomilePlugin") == 0)
                    category = kCategoryCamomilePluginMOD;
                else if (strcmp(cat2, "ControlVoltagePlugin") == 0)
                    category = kCategoryControlVoltagePluginMOD;
                else
                    continue; // invalid mod category

                // if we reach this point we found a mod category.
                // we need to stop now, as only 1 mod category is allowed per plugin.
                break;
            }
        }
        lilv_nodes_free(nodes);
    }

    return category;
}

static const char* _get_lv2_pedalboards_path()
{
    static std::string path;

    if (path.empty())
    {
        if (const char* const pbdir = getenv("MOD_USER_PEDALBOARDS_DIR"))
            path = pbdir;
        else
            path = "~/.pedalboards";

        if (FACTORY_PEDALBOARDS_DIR != nullptr)
        {
            path += ":";
            path += FACTORY_PEDALBOARDS_DIR;
        }
        else
        {
            path += ":/usr/share/mod/pedalboards";
        }
    }

    return path.c_str();
}

const PluginInfo_Mini* _get_plugin_info_mini(LilvWorld* const w,
                                             const LilvPlugin* const p,
                                             const NamespaceDefinitions_Mini& ns)
{
    // --------------------------------------------------------------------------------------------------------
    // uri

    const char* const uri = lilv_node_as_uri(lilv_plugin_get_uri(p));

    // --------------------------------------------------------------------------------------------------------
    // check if plugin if supported

    bool supported = true;

    for (unsigned int i=0, numports=lilv_plugin_get_num_ports(p); i<numports; ++i)
    {
        const LilvPort* const port = lilv_plugin_get_port_by_index(p, i);

        if (LilvNodes* const typenodes = lilv_port_get_value(p, port, ns.rdf_type))
        {
            bool hasDirection = false;
            bool isGood = false;

            LILV_FOREACH(nodes, it, typenodes)
            {
                const char* const typestr = lilv_node_as_string(lilv_nodes_get(typenodes, it));

                if (typestr == nullptr)
                    continue;

                // ignore raw port type
                if (strcmp(typestr, LV2_CORE__Port) == 0)
                    continue;

                // direction (input or output) is required
                if (strcmp(typestr, LV2_CORE__InputPort) == 0) {
                    hasDirection = true;
                    continue;
                }
                if (strcmp(typestr, LV2_CORE__OutputPort) == 0) {
                    hasDirection = true;
                    continue;
                }

                // ignore morph ports if base type is supported
                if (strcmp(typestr, LV2_MORPH__MorphPort) == 0)
                    continue;

                // check base type, must be supported
                if (strcmp(typestr, LV2_CORE__AudioPort) == 0) {
                    isGood = true;
                    continue;
                }
                if (strcmp(typestr, LV2_CORE__ControlPort) == 0) {
                    isGood = true;
                    continue;
                }
                if (strcmp(typestr, LV2_CORE__CVPort) == 0) {
                    isGood = true;
                    continue;
                }
                if (strcmp(typestr, LV2_ATOM__AtomPort) == 0) {
                    isGood = true;
                    continue;
                }
                if (strcmp(typestr, MOD__CVPort) == 0) {
                    isGood = true;
                    continue;
                }
            }
            lilv_nodes_free(typenodes);

            if (! (hasDirection && isGood))
                supported = false;
        }
    }

    if (! supported)
    {
        printf("Plugin '%s' uses non-supported port types\n", uri);
        return nullptr;
    }

    // --------------------------------------------------------------------------------------------------------
    // category

    const char* const* const category = _get_plugin_categories(p, ns.rdf_type, &supported);

    if (! supported)
        return nullptr;

    // --------------------------------------------------------------------------------------------------------

    PluginInfo_Mini* const info = new PluginInfo_Mini;
    info->uri = uri;
    info->category = category;

    // --------------------------------------------------------------------------------------------------------
    // name

    if (LilvNode* const node = lilv_plugin_get_name(p))
    {
        if (const char* const name = lilv_node_as_string(node))
            info->name = strdup(name);
        else
            info->name = nc;

        lilv_node_free(node);
    }
    else
    {
        info->name = nc;
    }

    // --------------------------------------------------------------------------------------------------------
    // brand

    char brand[16+1] = {};

    if (LilvNodes* const nodes = lilv_plugin_get_value(p, ns.mod_brand))
    {
        strncpy(brand, lilv_node_as_string(lilv_nodes_get_first(nodes)), 16);
        info->brand = strdup(brand);
        lilv_nodes_free(nodes);
    }
    else if (LilvNode* const node = lilv_plugin_get_author_name(p))
    {
        strncpy(brand, lilv_node_as_string(node), 16);
        info->brand = strdup(brand);
        lilv_node_free(node);
    }
    else
    {
        info->brand = nc;
    }

    // --------------------------------------------------------------------------------------------------------
    // label

    char label[24+1] = {};

    if (LilvNodes* const nodes = lilv_plugin_get_value(p, ns.mod_label))
    {
        strncpy(label, lilv_node_as_string(lilv_nodes_get_first(nodes)), 24);
        info->label = strdup(label);
        lilv_nodes_free(nodes);
    }
    else if (info->name != nc)
    {
        if (strlen(info->name) <= 24)
        {
            info->label = strdup(info->name);
        }
        else
        {
            strncpy(label, info->name, 24);
            info->label = strdup(label);
        }
    }
    else
    {
        info->label = nc;
    }

    // --------------------------------------------------------------------------------------------------------
    // comment

    if (LilvNodes* const nodes = lilv_plugin_get_value(p, ns.rdfs_comment))
    {
        info->comment = strdup(lilv_node_as_string(lilv_nodes_get_first(nodes)));
        lilv_nodes_free(nodes);
    }
    else
    {
        info->comment = nc;
    }

    // --------------------------------------------------------------------------------------------------------
    // version

    if (LilvNodes* const minorvers = lilv_plugin_get_value(p, ns.lv2core_minorVersion))
    {
        info->minorVersion = lilv_node_as_int(lilv_nodes_get_first(minorvers));
        lilv_nodes_free(minorvers);
    }
    else
    {
        info->minorVersion = 0;
    }

    if (LilvNodes* const microvers = lilv_plugin_get_value(p, ns.lv2core_microVersion))
    {
        info->microVersion = lilv_node_as_int(lilv_nodes_get_first(microvers));
        lilv_nodes_free(microvers);
    }
    else
    {
        info->microVersion = 0;
    }

    if (LilvNodes* const releasenode = lilv_plugin_get_value(p, ns.mod_release))
    {
        info->release = lilv_node_as_int(lilv_nodes_get_first(releasenode));
        lilv_nodes_free(releasenode);
    }
    else
    {
        info->release = 0;
    }

    if (LilvNodes* const buildernode = lilv_plugin_get_value(p, ns.mod_builder))
    {
        info->builder = lilv_node_as_int(lilv_nodes_get_first(buildernode));
        lilv_nodes_free(buildernode);
    }
    else
    {
        info->builder = 0;
    }

    // --------------------------------------------------------------------------------------------------------
    // build environment

    if (LilvNodes* const nodes = lilv_plugin_get_value(p, ns.mod_buildEnvironment))
    {
        const char* const buildEnvironment = lilv_node_as_string(lilv_nodes_get_first(nodes));

        /**/ if (strcmp(buildEnvironment, "prod") == 0)
            info->buildEnvironment = kBuildEnvironmentProd;
        else if (strcmp(buildEnvironment, "dev") == 0)
            info->buildEnvironment = kBuildEnvironmentDev;
        else if (strcmp(buildEnvironment, "labs") == 0)
            info->buildEnvironment = kBuildEnvironmentLabs;
        else
            info->buildEnvironment = strdup(buildEnvironment);

        lilv_nodes_free(nodes);
    }
    // if cloud built the plugin, but no buildEnvironment was set, switch to prod for backwards compat
    else if (info->release >= 1 && info->builder >= 1)
    {
        info->buildEnvironment = kBuildEnvironmentProd;
    }
    else
    {
        info->buildEnvironment = nc;
    }

    // --------------------------------------------------------------------------------------------------------
    // licensed

    if (KEYS_PATHlen > 0 && lilv_plugin_has_extension_data(p, ns.modlicense_interface))
    {
        const std::string licensefile(KEYS_PATH + sha1(info->uri));

        info->licensed = std::ifstream(licensefile).good() ? kPluginLicensePaid : kPluginLicenseTrial;
    }
    else
    {
        info->licensed = kPluginLicenseNonCommercial;
    }

    // --------------------------------------------------------------------------------------------------------
    // gui

    LilvNode* modguigui = nullptr;
    char* resdir = nullptr;

    if (LilvNodes* const nodes = lilv_plugin_get_value(p, ns.modgui_gui))
    {
        LILV_FOREACH(nodes, it, nodes)
        {
            const LilvNode* const mgui = lilv_nodes_get(nodes, it);
            LilvNode* const resdirn = lilv_world_get(w, mgui, ns.modgui_resourcesDirectory, nullptr);
            if (resdirn == nullptr)
                continue;

            free(resdir);
            resdir = lilv_file_abspath(lilv_node_as_string(resdirn));

            lilv_node_free(modguigui);
            lilv_node_free(resdirn);

            if (resdir == nullptr)
            {
                modguigui = nullptr;
                continue;
            }

            modguigui = lilv_node_duplicate(mgui);

            if (strncmp(resdir, HOME, HOMElen) == 0)
                // found a modgui in the home dir, stop here and use it
                break;
        }

        lilv_nodes_free(nodes);
    }

    if (modguigui != nullptr && resdir != nullptr)
    {
        info->gui.resourcesDirectory = resdir;

        if (LilvNode* const modgui_scrn = lilv_world_get(w, modguigui, ns.modgui_screenshot, nullptr))
        {
            info->gui.screenshot = lilv_file_abspath(lilv_node_as_string(modgui_scrn));
            lilv_node_free(modgui_scrn);
        }
        if (info->gui.screenshot == nullptr)
            info->gui.screenshot = nc;

        if (LilvNode* const modgui_thumb = lilv_world_get(w, modguigui, ns.modgui_thumbnail, nullptr))
        {
            info->gui.thumbnail = lilv_file_abspath(lilv_node_as_string(modgui_thumb));
            lilv_node_free(modgui_thumb);
        }
        if (info->gui.thumbnail == nullptr)
            info->gui.thumbnail = nc;

        lilv_node_free(modguigui);
    }
    else
    {
        info->gui.resourcesDirectory = nc;
        info->gui.screenshot = nc;
        info->gui.thumbnail  = nc;
    }

    // --------------------------------------------------------------------------------------------------------

    return info;
}

static void _fill_units(LilvWorld* const w,
                        PluginPortUnits& portunits,
                        LilvNode* const uunit,
                        const NamespaceDefinitions& ns)
{
    const char* uuri = lilv_node_as_uri(uunit);

    // using pre-existing lv2 unit
    if (uuri != nullptr && strncmp(uuri, LV2_UNITS_PREFIX, 38) == 0)
    {
        uuri += 38; // strlen(LV2_UNITS_PREFIX)

        if (_isalnum(uuri))
        {
            const char* const* unittable;

            if (strcmp(uuri, "s") == 0)
                unittable = kUnit_s;
            else if (strcmp(uuri, "ms") == 0)
                unittable = kUnit_ms;
            else if (strcmp(uuri, "min") == 0)
                unittable = kUnit_min;
            else if (strcmp(uuri, "bar") == 0)
                unittable = kUnit_bar;
            else if (strcmp(uuri, "beat") == 0)
                unittable = kUnit_beat;
            else if (strcmp(uuri, "frame") == 0)
                unittable = kUnit_frame;
            else if (strcmp(uuri, "m") == 0)
                unittable = kUnit_m;
            else if (strcmp(uuri, "cm") == 0)
                unittable = kUnit_cm;
            else if (strcmp(uuri, "mm") == 0)
                unittable = kUnit_mm;
            else if (strcmp(uuri, "km") == 0)
                unittable = kUnit_km;
            else if (strcmp(uuri, "inch") == 0)
                unittable = kUnit_inch;
            else if (strcmp(uuri, "mile") == 0)
                unittable = kUnit_mile;
            else if (strcmp(uuri, "db") == 0)
                unittable = kUnit_db;
            else if (strcmp(uuri, "pc") == 0)
                unittable = kUnit_pc;
            else if (strcmp(uuri, "coef") == 0)
                unittable = kUnit_coef;
            else if (strcmp(uuri, "hz") == 0)
                unittable = kUnit_hz;
            else if (strcmp(uuri, "khz") == 0)
                unittable = kUnit_khz;
            else if (strcmp(uuri, "mhz") == 0)
                unittable = kUnit_mhz;
            else if (strcmp(uuri, "bpm") == 0)
                unittable = kUnit_bpm;
            else if (strcmp(uuri, "oct") == 0)
                unittable = kUnit_oct;
            else if (strcmp(uuri, "cent") == 0)
                unittable = kUnit_cent;
            else if (strcmp(uuri, "semitone12TET") == 0)
                unittable = kUnit_semitone12TET;
            else if (strcmp(uuri, "degree") == 0)
                unittable = kUnit_degree;
            else if (strcmp(uuri, "midiNote") == 0)
                unittable = kUnit_midiNote;
            else
                unittable = nullptr;

            if (unittable != nullptr)
            {
                portunits.label  = unittable[0];
                portunits.render = unittable[1];
                portunits.symbol = unittable[2];
            }
        }
    }
    // using mod:volts unit
    else if (uuri != nullptr && strcmp(uuri, LILV_NS_MOD "volts") == 0)
    {
        portunits.label  = kUnit_volts[0];
        portunits.render = kUnit_volts[1];
        portunits.symbol = kUnit_volts[2];
    }
    // using custom unit
    else
    {
        if (LilvNode* const node = lilv_world_get(w, uunit, ns.rdfs_label, nullptr))
        {
            portunits.label = strdup(lilv_node_as_string(node));
            lilv_node_free(node);
        }

        if (LilvNode* const node = lilv_world_get(w, uunit, ns.units_render, nullptr))
        {
            portunits.render = strdup(lilv_node_as_string(node));
            lilv_node_free(node);
        }

        if (LilvNode* const node = lilv_world_get(w, uunit, ns.units_symbol, nullptr))
        {
            portunits.symbol = strdup(lilv_node_as_string(node));
            lilv_node_free(node);
        }

        portunits._custom = true;
    }

}

const PluginInfo& _get_plugin_info(LilvWorld* const w,
                                   const LilvPlugin* const p,
                                   const NamespaceDefinitions& ns)
{
    static PluginInfo info;
    memset(&info, 0, sizeof(PluginInfo));

    const char* const bundleuri = lilv_node_as_uri(lilv_plugin_get_bundle_uri(p));
    const char* const bundle    = lilv_file_uri_parse(bundleuri, nullptr);

    const size_t bundleurilen = strlen(bundleuri);

    // --------------------------------------------------------------------------------------------------------
    // uri

    info.uri = lilv_node_as_uri(lilv_plugin_get_uri(p));

    printf("NOTICE: Now scanning plugin '%s'...\n", info.uri);

    // --------------------------------------------------------------------------------------------------------
    // name

    if (LilvNode* const node = lilv_plugin_get_name(p))
    {
        const char* const name = lilv_node_as_string(node);
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
        info.binary = lilv_file_abspath(info.binary);
    if (info.binary == nullptr)
        info.binary = nc;

    // --------------------------------------------------------------------------------------------------------
    // license

    if (LilvNodes* const nodes = lilv_plugin_get_value(p, ns.doap_license))
    {
        const char* license = lilv_node_as_string(lilv_nodes_get_first(nodes));

        if (strncmp(license, bundleuri, bundleurilen) == 0)
            license += bundleurilen;

        info.license = strdup(license);
        lilv_nodes_free(nodes);
    }
    else if (LilvNodes* const nodes2 = lilv_plugin_get_value(p, ns.lv2core_project))
    {
        if (LilvNode* const lcsnode = lilv_world_get(w, lilv_nodes_get_first(nodes2), ns.doap_license, nullptr))
        {
            const char* license = lilv_node_as_string(lcsnode);

            if (strncmp(license, bundleuri, bundleurilen) == 0)
                license += bundleurilen;

            info.license = strdup(license);
            lilv_node_free(lcsnode);
        }
        else
        {
            info.license = nc;
        }
        lilv_nodes_free(nodes2);
    }
    else
    {
        info.license = nc;
    }

    // --------------------------------------------------------------------------------------------------------
    // comment

    if (LilvNodes* const nodes = lilv_plugin_get_value(p, ns.rdfs_comment))
    {
        info.comment = strdup(lilv_node_as_string(lilv_nodes_get_first(nodes)));
        lilv_nodes_free(nodes);
    }
    else
    {
        info.comment = nc;
    }

    // --------------------------------------------------------------------------------------------------------
    // category

    info.category = _get_plugin_categories(p, ns.rdf_type);

    // --------------------------------------------------------------------------------------------------------
    // version

    if (LilvNodes* const minorvers = lilv_plugin_get_value(p, ns.lv2core_minorVersion))
    {
        info.minorVersion = lilv_node_as_int(lilv_nodes_get_first(minorvers));
        lilv_nodes_free(minorvers);
    }

    if (LilvNodes* const microvers = lilv_plugin_get_value(p, ns.lv2core_microVersion))
    {
        info.microVersion = lilv_node_as_int(lilv_nodes_get_first(microvers));
        lilv_nodes_free(microvers);
    }

    if (LilvNodes* const releasenode = lilv_plugin_get_value(p, ns.mod_release))
    {
        info.release = lilv_node_as_int(lilv_nodes_get_first(releasenode));
        lilv_nodes_free(releasenode);
    }

    if (LilvNodes* const buildernode = lilv_plugin_get_value(p, ns.mod_builder))
    {
        info.builder = lilv_node_as_int(lilv_nodes_get_first(buildernode));
        lilv_nodes_free(buildernode);
    }

    {
        char versiontmpstr[32+1] = {};
        snprintf(versiontmpstr, 32, "%d.%d", info.minorVersion, info.microVersion);
        info.version = strdup(versiontmpstr);
    }

    // 0.x is experimental
    if (info.minorVersion == 0)
        info.stability = kStabilityExperimental;

    // odd x.2 or 2.x is testing/development
    else if (info.minorVersion % 2 != 0 || info.microVersion % 2 != 0)
        info.stability = kStabilityTesting;

    // otherwise it's stable
    else
        info.stability = kStabilityStable;

    // --------------------------------------------------------------------------------------------------------
    // build environment

    if (LilvNodes* const nodes = lilv_plugin_get_value(p, ns.mod_buildEnvironment))
    {
        const char* const buildEnvironment = lilv_node_as_string(lilv_nodes_get_first(nodes));

        /**/ if (strcmp(buildEnvironment, "prod") == 0)
            info.buildEnvironment = kBuildEnvironmentProd;
        else if (strcmp(buildEnvironment, "dev") == 0)
            info.buildEnvironment = kBuildEnvironmentDev;
        else if (strcmp(buildEnvironment, "labs") == 0)
            info.buildEnvironment = kBuildEnvironmentLabs;
        else
            info.buildEnvironment = strdup(buildEnvironment);

        lilv_nodes_free(nodes);
    }
    // if cloud built the plugin, but no buildEnvironment was set, switch to prod for backwards compat
    else if (info.release >= 1 && info.builder >= 1)
    {
        info.buildEnvironment = kBuildEnvironmentProd;
    }
    else
    {
        info.buildEnvironment = nc;
    }

    // --------------------------------------------------------------------------------------------------------
    // licensed

    if (KEYS_PATHlen > 0 && lilv_plugin_has_extension_data(p, ns.modlicense_interface))
    {
        const std::string licensefile(KEYS_PATH + sha1(info.uri));

        info.licensed = std::ifstream(licensefile).good() ? kPluginLicensePaid : kPluginLicenseTrial;
    }

    // --------------------------------------------------------------------------------------------------------
    // hasExternalUI

#ifdef WITH_EXTERNAL_UI_SUPPORT
    if (LilvUIs* const uis = lilv_plugin_get_uis(p))
    {
        LILV_FOREACH(nodes, i, uis)
        {
            const LilvUI* const ui = lilv_uis_get(uis, i);
            const LilvNode* const uinode = lilv_ui_get_uri(ui);

            if (lilv_world_load_resource(W, uinode) == -1)
                continue;

            if (LilvNodes* const uiexts = lilv_world_find_nodes(W, uinode, ns.lv2core_extensionData, nullptr))
            {
                bool hasIdle = false;
                bool hasShow = false;

                LILV_FOREACH(nodes, j, uiexts)
                {
                    const LilvNode* const uiext = lilv_nodes_get(uiexts, j);
                    const char* const uiexturi = lilv_node_as_uri(uiext);
                    /**/ if (strcmp(uiexturi, LV2_UI__idleInterface))
                        hasIdle = true;
                    else if (strcmp(uiexturi, LV2_UI__showInterface))
                        hasShow = true;
                }

                lilv_nodes_free(uiexts);

                if (hasIdle && hasShow)
                    info.hasExternalUI = true;
            }

            if (info.hasExternalUI)
                break;
        }

        lilv_uis_free(uis);
    }
#endif

    // --------------------------------------------------------------------------------------------------------
    // author name

    if (LilvNode* const node = lilv_plugin_get_author_name(p))
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

    if (LilvNode* const node = lilv_plugin_get_author_homepage(p))
    {
        info.author.homepage = strdup(lilv_node_as_string(node));
        lilv_node_free(node);
    }
    else if (LilvNodes* const nodes2 = lilv_plugin_get_value(p, ns.lv2core_project))
    {
        if (LilvNode* const mntnr = lilv_world_get(w, lilv_nodes_get_first(nodes2), ns.doap_maintainer, nullptr))
        {
            if (LilvNode* const hmpg = lilv_world_get(w, lilv_nodes_get_first(mntnr), ns.foaf_homepage, nullptr))
            {
                info.author.homepage = strdup(lilv_node_as_string(hmpg));
                lilv_node_free(hmpg);
            }
            else
            {
                info.author.homepage = nc;
            }
            lilv_node_free(mntnr);
        }
        else
        {
            info.author.homepage = nc;
        }
        lilv_nodes_free(nodes2);
    }
    else
    {
        info.author.homepage = nc;
    }

    // --------------------------------------------------------------------------------------------------------
    // author email

    if (LilvNode* const node = lilv_plugin_get_author_email(p))
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

    if (LilvNodes* const nodes = lilv_plugin_get_value(p, ns.mod_brand))
    {
        char* const brand = strdup(lilv_node_as_string(lilv_nodes_get_first(nodes)));

        /* NOTE: this gives a false positive on valgrind.
                 see https://bugzilla.redhat.com/show_bug.cgi?id=678518 */
        if (strlen(brand) > 16)
            brand[16] = '\0';

        info.brand = brand;
        lilv_nodes_free(nodes);
    }
    else if (info.author.name == nc)
    {
        info.brand = nc;
    }
    else
    {
        if (strlen(info.author.name) <= 16)
        {
            info.brand = strdup(info.author.name);
        }
        else
        {
            char brand[16+1] = {};
            strncpy(brand, info.author.name, 16);
            info.brand = strdup(brand);
        }
    }

    // --------------------------------------------------------------------------------------------------------
    // label

    if (LilvNodes* const nodes = lilv_plugin_get_value(p, ns.mod_label))
    {
        char* const label = strdup(lilv_node_as_string(lilv_nodes_get_first(nodes)));

        /* NOTE: this gives a false positive on valgrind.
                 see https://bugzilla.redhat.com/show_bug.cgi?id=678518 */
        if (strlen(label) > 24)
            label[24] = '\0';

        info.label = label;
        lilv_nodes_free(nodes);
    }
    else if (info.name == nc)
    {
        info.label = nc;
    }
    else
    {
        if (strlen(info.name) <= 24)
        {
            info.label = strdup(info.name);
        }
        else
        {
            char label[24+1] = {};
            strncpy(label, info.name, 24);
            info.label = strdup(label);
        }
    }

    // --------------------------------------------------------------------------------------------------------
    // bundles

    {
        std::list<std::string> bundles;

        // make sure the main bundle is the first in the list
        size_t bundlepathsize;
        const char* bundlepath = _get_safe_bundlepath(bundle, bundlepathsize);

        if (bundlepath != nullptr)
        {
            const std::string bundlestr = bundlepath;
            bundles.push_back(bundlestr);
        }

        // now add everything else
        _fill_bundles_for_plugin(bundles, p, ns.pset_Preset);

        size_t count = bundles.size();
        const char** const cbundles = new const char*[count+1];
        memset(cbundles, 0, sizeof(const char*) * (count+1));

        count = 0;
        for (const std::string& b : bundles)
            cbundles[count++] = strdup(b.c_str());

        info.bundles = cbundles;
    }

    // --------------------------------------------------------------------------------------------------------
    // gui

    LilvNode* modguigui = nullptr;
    char* resdir = nullptr;

    if (LilvNodes* const nodes = lilv_plugin_get_value(p, ns.modgui_gui))
    {
        LILV_FOREACH(nodes, it, nodes)
        {
            const LilvNode* const mgui = lilv_nodes_get(nodes, it);
            LilvNode* const resdirn = lilv_world_get(w, mgui, ns.modgui_resourcesDirectory, nullptr);
            if (resdirn == nullptr)
                continue;

            free(resdir);
            resdir = lilv_file_abspath(lilv_node_as_string(resdirn));

            lilv_node_free(modguigui);
            lilv_node_free(resdirn);

            if (resdir == nullptr)
            {
                modguigui = nullptr;
                continue;
            }

            modguigui = lilv_node_duplicate(mgui);

            if (strncmp(resdir, HOME, HOMElen) == 0)
                // found a modgui in the home dir, stop here and use it
                break;
        }

        lilv_nodes_free(nodes);
    }

    if (modguigui != nullptr && resdir != nullptr)
    {
        info.gui.resourcesDirectory = resdir;

        // icon and settings templates
        if (LilvNode* const modgui_icon = lilv_world_get(w, modguigui, ns.modgui_iconTemplate, nullptr))
        {
            info.gui.iconTemplate = lilv_file_abspath(lilv_node_as_string(modgui_icon));
            lilv_node_free(modgui_icon);
        }
        if (info.gui.iconTemplate == nullptr)
            info.gui.iconTemplate = nc;

        if (LilvNode* const modgui_setts = lilv_world_get(w, modguigui, ns.modgui_settingsTemplate, nullptr))
        {
            info.gui.settingsTemplate = lilv_file_abspath(lilv_node_as_string(modgui_setts));
            lilv_node_free(modgui_setts);
        }
        if (info.gui.settingsTemplate == nullptr)
            info.gui.settingsTemplate = nc;

        // javascript and stylesheet files
        if (LilvNode* const modgui_script = lilv_world_get(w, modguigui, ns.modgui_javascript, nullptr))
        {
            info.gui.javascript = lilv_file_abspath(lilv_node_as_string(modgui_script));
            lilv_node_free(modgui_script);
        }
        if (info.gui.javascript == nullptr)
            info.gui.javascript = nc;

        if (LilvNode* const modgui_style = lilv_world_get(w, modguigui, ns.modgui_stylesheet, nullptr))
        {
            info.gui.stylesheet = lilv_file_abspath(lilv_node_as_string(modgui_style));
            lilv_node_free(modgui_style);
        }
        if (info.gui.stylesheet == nullptr)
            info.gui.stylesheet = nc;

        // screenshot and thumbnail
        if (LilvNode* const modgui_scrn = lilv_world_get(w, modguigui, ns.modgui_screenshot, nullptr))
        {
            info.gui.screenshot = lilv_file_abspath(lilv_node_as_string(modgui_scrn));
            lilv_node_free(modgui_scrn);
        }
        if (info.gui.screenshot == nullptr)
            info.gui.screenshot = nc;

        if (LilvNode* const modgui_thumb = lilv_world_get(w, modguigui, ns.modgui_thumbnail, nullptr))
        {
            info.gui.thumbnail = lilv_file_abspath(lilv_node_as_string(modgui_thumb));
            lilv_node_free(modgui_thumb);
        }
        if (info.gui.thumbnail == nullptr)
            info.gui.thumbnail = nc;

        // discussionURL, optional
        if (LilvNode* const modgui_discussionURL = lilv_world_get(w, modguigui, ns.modgui_discussionURL, nullptr))
        {
            info.gui.discussionURL = strdup(lilv_node_as_uri(modgui_discussionURL));
            lilv_node_free(modgui_discussionURL);
        }
        if (info.gui.discussionURL == nullptr)
            info.gui.discussionURL = nc;

        // documentation, optional
        if (LilvNode* const modgui_documentation = lilv_world_get(w, modguigui, ns.modgui_documentation, nullptr))
        {
            info.gui.documentation = lilv_file_abspath(lilv_node_as_string(modgui_documentation));
            lilv_node_free(modgui_documentation);
        }
        if (info.gui.documentation == nullptr)
            info.gui.documentation = nc;

        // extra stuff, all optional
        if (LilvNode* const modgui_brand = lilv_world_get(w, modguigui, ns.modgui_brand, nullptr))
        {
            info.gui.brand = strdup(lilv_node_as_string(modgui_brand));
            lilv_node_free(modgui_brand);
        }
        if (info.gui.brand == nullptr)
            info.gui.brand = nc;

        if (LilvNode* const modgui_label = lilv_world_get(w, modguigui, ns.modgui_label, nullptr))
        {
            info.gui.label = strdup(lilv_node_as_string(modgui_label));
            lilv_node_free(modgui_label);
        }
        if (info.gui.label == nullptr)
            info.gui.label = nc;

        if (LilvNode* const modgui_model = lilv_world_get(w, modguigui, ns.modgui_model, nullptr))
        {
            info.gui.model = strdup(lilv_node_as_string(modgui_model));
            lilv_node_free(modgui_model);
        }
        if (info.gui.model == nullptr)
            info.gui.model = nc;

        if (LilvNode* const modgui_panel = lilv_world_get(w, modguigui, ns.modgui_panel, nullptr))
        {
            info.gui.panel = strdup(lilv_node_as_string(modgui_panel));
            lilv_node_free(modgui_panel);
        }
        if (info.gui.panel == nullptr)
            info.gui.panel = nc;

        if (LilvNode* const modgui_color = lilv_world_get(w, modguigui, ns.modgui_color, nullptr))
        {
            info.gui.color = strdup(lilv_node_as_string(modgui_color));
            lilv_node_free(modgui_color);
        }
        if (info.gui.color == nullptr)
            info.gui.color = nc;

        if (LilvNode* const modgui_knob = lilv_world_get(w, modguigui, ns.modgui_knob, nullptr))
        {
            info.gui.knob = strdup(lilv_node_as_string(modgui_knob));
            lilv_node_free(modgui_knob);
        }
        if (info.gui.knob == nullptr)
            info.gui.knob = nc;

        if (LilvNodes* const modgui_ports = lilv_world_find_nodes(w, modguigui, ns.modgui_port, nullptr))
        {
            const unsigned int guiportscount = lilv_nodes_size(modgui_ports);

            PluginGUIPort* const guiports = new PluginGUIPort[guiportscount+1];
            memset(guiports, 0, sizeof(PluginGUIPort) * (guiportscount+1));

            for (unsigned int i=0; i<guiportscount; ++i)
                guiports[i] = { true, i, nc, nc };

            int index;

            LILV_FOREACH(nodes, it, modgui_ports)
            {
                const LilvNode* const modgui_port = lilv_nodes_get(modgui_ports, it);

                if (LilvNode* const guiports_index = lilv_world_get(w, modgui_port, ns.lv2core_index, nullptr))
                {
                    index = lilv_node_as_int(guiports_index);
                    lilv_node_free(guiports_index);
                }
                else
                {
                    continue;
                }

                if (index < 0 || index >= (int)guiportscount)
                    continue;

                PluginGUIPort& guiport(guiports[index]);

                if (LilvNode* const guiports_symbol = lilv_world_get(w, modgui_port, ns.lv2core_symbol, nullptr))
                {
                    // in case of duplicated indexes
                    if (guiport.symbol != nullptr && guiport.symbol != nc)
                        free((void*)guiport.symbol);

                    guiport.symbol = strdup(lilv_node_as_string(guiports_symbol));
                    lilv_node_free(guiports_symbol);
                }

                if (LilvNode* const guiports_name = lilv_world_get(w, modgui_port, ns.lv2core_name, nullptr))
                {
                    // in case of duplicated indexes
                    if (guiport.name != nullptr && guiport.name != nc)
                        free((void*)guiport.name);

                    guiport.name = strdup(lilv_node_as_string(guiports_name));
                    lilv_node_free(guiports_name);
                }
            }

            info.gui.ports = guiports;

            lilv_nodes_free(modgui_ports);
        }

        if (LilvNodes* const modgui_monitors = lilv_world_find_nodes(w, modguigui, ns.modgui_monitoredOutputs, nullptr))
        {
            unsigned int monitorcount = lilv_nodes_size(modgui_monitors);

            const char** monitors = new const char*[monitorcount+1];
            memset(monitors, 0, sizeof(const char*) * (monitorcount+1));

            monitorcount = 0;
            LILV_FOREACH(nodes, it, modgui_monitors)
            {
                const LilvNode* const modgui_monitor = lilv_nodes_get(modgui_monitors, it);

                if (LilvNode* const monitor_symbol = lilv_world_get(w, modgui_monitor, ns.lv2core_symbol, nullptr))
                {
                    monitors[monitorcount++] = strdup(lilv_node_as_string(monitor_symbol));
                    lilv_node_free(monitor_symbol);
                }
            }

            info.gui.monitoredOutputs = monitors;

            lilv_nodes_free(modgui_monitors);
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
        info.gui.discussionURL = nc;
        info.gui.documentation = nc;
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
            const LilvPort* const port = lilv_plugin_get_port_by_index(p, i);

            PortDirection direction = kPortDirectionNull;
            PortType type = kPortTypeNull;

            if (LilvNodes* const nodes = lilv_port_get_value(p, port, ns.rdf_type))
            {
                LILV_FOREACH(nodes, it, nodes)
                {
                    const LilvNode* const node2 = lilv_nodes_get(nodes, it);
                    const char* const nodestr = lilv_node_as_string(node2);

                    if (nodestr == nullptr)
                        continue;

                    else if (strcmp(nodestr, LV2_CORE__InputPort) == 0)
                        direction = kPortDirectionInput;
                    else if (strcmp(nodestr, LV2_CORE__OutputPort) == 0)
                        direction = kPortDirectionOutput;
                    else if (strcmp(nodestr, LV2_CORE__AudioPort) == 0)
                        type = kPortTypeAudio;
                    else if (strcmp(nodestr, LV2_CORE__ControlPort) == 0)
                        type = kPortTypeControl;
                    else if (strcmp(nodestr, MOD__CVPort) == 0 || (kAllowRegularCV && strcmp(nodestr, LV2_CORE__CVPort) == 0))
                        type = kPortTypeCV;
                    else if (strcmp(nodestr, LV2_ATOM__AtomPort) == 0 && lilv_port_supports_event(p, port, ns.midi_MidiEvent))
                    {
                        if (LilvNodes* const nodes2 = lilv_port_get_value(p, port, ns.atom_bufferType))
                        {
                            if (lilv_node_equals(lilv_nodes_get_first(nodes2), ns.atom_Sequence))
                                if (! lilv_port_has_property(p, port, ns.mod_rawMIDIClockAccess))
                                    type = kPortTypeMIDI;
                            lilv_nodes_free(nodes2);
                        }
                    }
                }
                lilv_nodes_free(nodes);
            }

            if (direction == kPortDirectionNull || type == kPortTypeNull)
                continue;

            switch (type)
            {
            case kPortTypeNull:
                break;
            case kPortTypeAudio:
                if (direction == kPortDirectionOutput)
                    ++countAudioOutput;
                else
                    ++countAudioInput;
                break;
            case kPortTypeControl:
                if (direction == kPortDirectionOutput)
                    ++countControlOutput;
                else
                    ++countControlInput;
                break;
            case kPortTypeCV:
                if (direction == kPortDirectionOutput)
                    ++countCvOutput;
                else
                    ++countCvInput;
                break;
            case kPortTypeMIDI:
                if (direction == kPortDirectionOutput)
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
        countAudioInput = countAudioOutput = countControlInput = countControlOutput = 0;
        countCvInput = countCvOutput = countMidiInput = countMidiOutput = 0;

        // now fill info
        for (uint32_t i=0; i<count; ++i)
        {
            const LilvPort* const port = lilv_plugin_get_port_by_index(p, i);

            // ----------------------------------------------------------------------------------------------------

            PortDirection direction = kPortDirectionNull;
            PortType type = kPortTypeNull;

            if (LilvNodes* const nodes = lilv_port_get_value(p, port, ns.rdf_type))
            {
                LILV_FOREACH(nodes, it, nodes)
                {
                    const LilvNode* const node2 = lilv_nodes_get(nodes, it);
                    const char* const nodestr = lilv_node_as_string(node2);

                    if (nodestr == nullptr)
                        continue;

                    else if (strcmp(nodestr, LV2_CORE__InputPort) == 0)
                        direction = kPortDirectionInput;
                    else if (strcmp(nodestr, LV2_CORE__OutputPort) == 0)
                        direction = kPortDirectionOutput;
                    else if (strcmp(nodestr, LV2_CORE__AudioPort) == 0)
                        type = kPortTypeAudio;
                    else if (strcmp(nodestr, LV2_CORE__ControlPort) == 0)
                        type = kPortTypeControl;
                    else if (strcmp(nodestr, MOD__CVPort) == 0 || (kAllowRegularCV && strcmp(nodestr, LV2_CORE__CVPort) == 0))
                        type = kPortTypeCV;
                    else if (strcmp(nodestr, LV2_ATOM__AtomPort) == 0 && lilv_port_supports_event(p, port, ns.midi_MidiEvent))
                    {
                        if (LilvNodes* const nodes2 = lilv_port_get_value(p, port, ns.atom_bufferType))
                        {
                            if (lilv_node_equals(lilv_nodes_get_first(nodes2), ns.atom_Sequence))
                                if (! lilv_port_has_property(p, port, ns.mod_rawMIDIClockAccess))
                                    type = kPortTypeMIDI;
                            lilv_nodes_free(nodes2);
                        }
                    }
                }
                lilv_nodes_free(nodes);
            }

            if (direction == kPortDirectionNull || type == kPortTypeNull)
                continue;

            // ----------------------------------------------------------------------------------------------------

            PluginPort portinfo;
            memset(&portinfo, 0, sizeof(PluginPort));

            portinfo.index = i;

            // ----------------------------------------------------------------------------------------------------
            // name

            if (LilvNode* const node = lilv_port_get_name(p, port))
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

            if (const LilvNode* const symbolnode = lilv_port_get_symbol(p, port))
                portinfo.symbol = strdup(lilv_node_as_string(symbolnode));
            else
                portinfo.symbol = nc;

            // ----------------------------------------------------------------------------------------------------
            // short name

            if (LilvNodes* const nodes = lilv_port_get_value(p, port, ns.lv2core_shortName))
            {
                portinfo.shortName = strdup(lilv_node_as_string(lilv_nodes_get_first(nodes)));
                lilv_nodes_free(nodes);
            }
            else
            {
                portinfo.shortName = strdup(portinfo.name);
            }

            if (strlen(portinfo.shortName) > 16)
                ((char*)portinfo.shortName)[16] = '\0';

            // ----------------------------------------------------------------------------------------------------
            // comment

            if (LilvNodes* const nodes = lilv_port_get_value(p, port, ns.rdfs_comment))
            {
                portinfo.comment = strdup(lilv_node_as_string(lilv_nodes_get_first(nodes)));
                lilv_nodes_free(nodes);
            }
            else
            {
                portinfo.comment = nc;
            }

            // ----------------------------------------------------------------------------------------------------
            // designation

            if (LilvNodes* const nodes = lilv_port_get_value(p, port, ns.lv2core_designation))
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

            if (LilvNodes* const nodes = lilv_port_get_value(p, port, ns.mod_rangeSteps))
            {
                portinfo.rangeSteps = lilv_node_as_int(lilv_nodes_get_first(nodes));
                lilv_nodes_free(nodes);
            }
            else if (LilvNodes* const nodes2 = lilv_port_get_value(p, port, ns.pprops_rangeSteps))
            {
                portinfo.rangeSteps = lilv_node_as_int(lilv_nodes_get_first(nodes2));
                lilv_nodes_free(nodes2);
            }

            // ----------------------------------------------------------------------------------------------------
            // port properties

            if (LilvNodes* const nodes = lilv_port_get_value(p, port, ns.lv2core_portProperty))
            {
                const unsigned int propcount = lilv_nodes_size(nodes);
                unsigned int pindex = 0;

                const char** const props = new const char*[propcount+1];
                memset(props, 0, sizeof(const char*) * (propcount+1));

                LILV_FOREACH(nodes, itprop, nodes)
                {
                    if (pindex >= propcount)
                        continue;

                    if (const char* prop = strrchr(lilv_node_as_string(lilv_nodes_get(nodes, itprop)), '#'))
                    {
                        prop += 1;
                        if (prop[0] != '\0')
                            props[pindex++] = strdup(prop);
                    }
                }

                portinfo.properties = props;
                lilv_nodes_free(nodes);
            }

            // ----------------------------------------------------------------------------------------------------

            if (type == kPortTypeControl || type == kPortTypeCV)
            {
                LilvNodes* xminimum = lilv_port_get_value(p, port, ns.mod_minimum);
                if (xminimum == nullptr)
                    xminimum = lilv_port_get_value(p, port, ns.lv2core_minimum);

                LilvNodes* xmaximum = lilv_port_get_value(p, port, ns.mod_maximum);
                if (xmaximum == nullptr)
                    xmaximum = lilv_port_get_value(p, port, ns.lv2core_maximum);

                LilvNodes* xdefault = ns.mod_default_custom != nullptr
                                    ? lilv_port_get_value(p, port, ns.mod_default_custom)
                                    : nullptr;
                if (xdefault == nullptr)
                    xdefault = lilv_port_get_value(p, port, ns.mod_default);
                if (xdefault == nullptr)
                    xdefault = lilv_port_get_value(p, port, ns.lv2core_default);

                if (xminimum != nullptr && xmaximum != nullptr)
                {
                    portinfo.ranges.min = lilv_node_as_float(lilv_nodes_get_first(xminimum));
                    portinfo.ranges.max = lilv_node_as_float(lilv_nodes_get_first(xmaximum));

                    if (portinfo.ranges.min >= portinfo.ranges.max)
                        portinfo.ranges.max = portinfo.ranges.min + 1.0f;

                    if (xdefault != nullptr)
                        portinfo.ranges.def = lilv_node_as_float(lilv_nodes_get_first(xdefault));
                    else
                        portinfo.ranges.def = portinfo.ranges.min;

                    if (portinfo.properties != nullptr)
                    {
                        for (int j=0; portinfo.properties[j] != nullptr; ++j)
                        {
                            if (strcmp(portinfo.properties[j], "preferMomentaryOffByDefault") == 0)
                            {
                                portinfo.ranges.def = portinfo.ranges.max;
                                break;
                            }
                            if (strcmp(portinfo.properties[j], "preferMomentaryOnByDefault") == 0)
                            {
                                portinfo.ranges.def = portinfo.ranges.min;
                                break;
                            }
                        }
                    }
                }
                else
                {
                    if (type == kPortTypeCV)
                    {
                        portinfo.ranges.min = -5.0f;
                        portinfo.ranges.max = 5.0f;
                    }
                    else
                    {
                        portinfo.ranges.min = 0.0f;
                        portinfo.ranges.max = 1.0f;
                    }
                    portinfo.ranges.def = 0.0f;
                }

                lilv_nodes_free(xminimum);
                lilv_nodes_free(xmaximum);
                lilv_nodes_free(xdefault);

                if (LilvScalePoints* const scalepoints = lilv_port_get_scale_points(p, port))
                {
                    if (const unsigned int scalepointcount = lilv_scale_points_size(scalepoints))
                    {
                        PluginPortScalePoint* const portsps = new PluginPortScalePoint[scalepointcount+1];
                        memset(portsps, 0, sizeof(PluginPortScalePoint) * (scalepointcount+1));

                        // get all scalepoints and sort them by value
                        std::map<double,const LilvScalePoint*> sortedpoints;

                        LILV_FOREACH(scale_points, itscl, scalepoints)
                        {
                            const LilvScalePoint* const scalepoint = lilv_scale_points_get(scalepoints, itscl);
                            const LilvNode* const xlabel = lilv_scale_point_get_label(scalepoint);
                            const LilvNode* const xvalue = lilv_scale_point_get_value(scalepoint);

                            if (xlabel == nullptr || xvalue == nullptr)
                                continue;

                            const double valueid = lilv_node_as_float(xvalue);
                            sortedpoints[valueid] = scalepoint;
                        }

                        // now store them sorted
                        unsigned int spindex = 0;
                        for (auto& scalepoint : sortedpoints)
                        {
                            if (spindex >= scalepointcount)
                                continue;

                            const LilvNode* const xlabel = lilv_scale_point_get_label(scalepoint.second);
                            const LilvNode* const xvalue = lilv_scale_point_get_value(scalepoint.second);

                            portsps[spindex++] = {
                                true,
                                lilv_node_as_float(xvalue),
                                strdup(lilv_node_as_string(xlabel)),
                            };
                        }

                        portinfo.scalePoints = portsps;
                    }

                    lilv_scale_points_free(scalepoints);
                }
            }

            // ----------------------------------------------------------------------------------------------------
            // control ports might contain unit

            portinfo.units.label  = nc;
            portinfo.units.render = nc;
            portinfo.units.symbol = nc;

            if (type == 2)
            {
                if (LilvNodes* const uunits = lilv_port_get_value(p, port, ns.units_unit))
                {
                    LilvNode* const uunit = lilv_nodes_get_first(uunits);
                    _fill_units(w, portinfo.units, uunit, ns);
                    lilv_nodes_free(uunits);
                }
            }

            // ----------------------------------------------------------------------------------------------------

            portinfo.valid = true;

            switch (type)
            {
            case kPortTypeNull:
                break;
            case kPortTypeAudio:
                if (direction == kPortDirectionOutput)
                    info.ports.audio.output[countAudioOutput++] = portinfo;
                else
                    info.ports.audio.input[countAudioInput++] = portinfo;
                break;
            case kPortTypeControl:
                if (direction == kPortDirectionOutput)
                    info.ports.control.output[countControlOutput++] = portinfo;
                else
                    info.ports.control.input[countControlInput++] = portinfo;
                break;
            case kPortTypeCV:
                if (direction == kPortDirectionOutput)
                    info.ports.cv.output[countCvOutput++] = portinfo;
                else
                    info.ports.cv.input[countCvInput++] = portinfo;
                break;
            case kPortTypeMIDI:
                if (direction == kPortDirectionOutput)
                    info.ports.midi.output[countMidiOutput++] = portinfo;
                else
                    info.ports.midi.input[countMidiInput++] = portinfo;
                break;
            }
        }
    }

    // --------------------------------------------------------------------------------------------------------
    // parameters

    std::map<std::string, PluginParameter> usedParameters;

    _fill_parameters_for_plugin(w, p, ns, usedParameters, true);
    _fill_parameters_for_plugin(w, p, ns, usedParameters, false);

    if (size_t count = usedParameters.size())
    {
        PluginParameter* const params = new PluginParameter[count+1];

        count = 0;
        for (auto& param : usedParameters)
            params[count++] = param.second;

        memset(&params[count], 0, sizeof(PluginParameter));

        info.parameters = params;
    }

    // --------------------------------------------------------------------------------------------------------
    // presets

    _place_preset_info(w, info, p, ns.pset_Preset, ns.rdfs_label);

    // --------------------------------------------------------------------------------------------------------

    lilv_free((void*)bundle);

    info.valid = true;
    printf("NOTICE: Finished scanning '%s'\n", info.uri);

    return info;
}

// --------------------------------------------------------------------------------------------------------

static void _clear_plugin_info_mini(const PluginInfo_Mini* const info)
{
    if (info->brand != nc)
        free((void*)info->brand);
    if (info->label != nc)
        free((void*)info->label);
    if (info->name != nc)
        free((void*)info->name);
    if (info->comment != nc)
        free((void*)info->comment);
    if (info->buildEnvironment != nc &&
        info->buildEnvironment != kBuildEnvironmentProd &&
        info->buildEnvironment != kBuildEnvironmentDev &&
        info->buildEnvironment != kBuildEnvironmentLabs)
        free((void*)info->buildEnvironment);
    if (info->gui.resourcesDirectory != nc)
        free((void*)info->gui.resourcesDirectory);
    if (info->gui.screenshot != nc)
        free((void*)info->gui.screenshot);
    if (info->gui.thumbnail != nc)
        free((void*)info->gui.thumbnail);

    delete info;
}

static void _fill_plugin_info_mini_from_full(const PluginInfo& info2, const PluginInfo_Mini** const miniInfo)
{
    if (*miniInfo != nullptr || !info2.valid)
        return;

    PluginInfo_Mini* const info = new PluginInfo_Mini;
    *miniInfo = info;

    info->uri              = info2.uri;
    info->name             = info2.name != nc ? strdup(info2.name) : nc;
    info->brand            = info2.brand != nc ? strdup(info2.brand) : nc;
    info->label            = info2.label != nc ? strdup(info2.label) : nc;
    info->comment          = info2.comment != nc ? strdup(info2.comment) : nc;
    info->buildEnvironment = info2.buildEnvironment == kBuildEnvironmentProd ? kBuildEnvironmentProd :
                             info2.buildEnvironment == kBuildEnvironmentDev ? kBuildEnvironmentDev :
                             info2.buildEnvironment == kBuildEnvironmentLabs ? kBuildEnvironmentLabs :
                             info2.buildEnvironment != nc ? strdup(info2.buildEnvironment) : nc;
    info->category         = info2.category;
    info->microVersion     = info2.microVersion;
    info->minorVersion     = info2.minorVersion;
    info->release          = info2.release;
    info->builder          = info2.builder;
    info->licensed         = info2.licensed;

    info->gui.resourcesDirectory = info2.gui.resourcesDirectory != nc ? strdup(info2.gui.resourcesDirectory) : nc;
    info->gui.screenshot         = info2.gui.screenshot         != nc ? strdup(info2.gui.screenshot)         : nc;
    info->gui.thumbnail          = info2.gui.thumbnail          != nc ? strdup(info2.gui.thumbnail)          : nc;
}

// --------------------------------------------------------------------------------------------------------

static const PedalboardInfo_Mini* _get_pedalboard_info_mini(LilvWorld* const w,
                                                            const LilvPlugin* const p,
                                                            const LilvNode* const versiontypenode,
                                                            const LilvNode* const rdftypenode,
                                                            const LilvNode* const ingenblocknode,
                                                            const LilvNode* const lv2protonode,
                                                            const PedalboardInfoType ptype)
{
    // --------------------------------------------------------------------------------------------------------
    // check if plugin is pedalboard

    bool isPedalboard = false;

    if (LilvNodes* const nodes = lilv_plugin_get_value(p, rdftypenode))
    {
        LILV_FOREACH(nodes, it, nodes)
        {
            const LilvNode* const node = lilv_nodes_get(nodes, it);

            if (const char* const nodestr = lilv_node_as_string(node))
            {
                if (strcmp(nodestr, LILV_NS_MODPEDAL "Pedalboard") == 0)
                {
                    isPedalboard = true;
                    break;
                }
            }
        }

        lilv_nodes_free(nodes);
    }

    if (! isPedalboard)
        return nullptr;

    // --------------------------------------------------------------------------------------------------------
    // bundle (required)

    char* bundle;

    if (const LilvNode* const node = lilv_plugin_get_bundle_uri(p))
    {
        bundle = lilv_file_abspath(lilv_node_as_string(node));

        if (bundle == nullptr)
            return nullptr;
    }
    else
    {
        return nullptr;
    }

    // --------------------------------------------------------------------------------------------------------
    // title (required)

    const char* title;

    if (LilvNode* const node = lilv_plugin_get_name(p))
    {
        if (const char* const name = lilv_node_as_string(node))
            title = name[0] != '\0' ? strdup(name) : kUntitled;
        else
            title = kUntitled;

        lilv_node_free(node);
    }
    else
    {
        free(bundle);
        return nullptr;
    }

    // --------------------------------------------------------------------------------------------------------

    PedalboardInfo_Mini* const info = new PedalboardInfo_Mini;
    info->bundle = bundle;
    info->title = title;

    // --------------------------------------------------------------------------------------------------------
    // uri

    info->uri = strdup(lilv_node_as_uri(lilv_plugin_get_uri(p)));

    // --------------------------------------------------------------------------------------------------------
    // factory

    switch (ptype)
    {
    case kPedalboardInfoUserOnly:
        info->factory = false;
        break;
    case kPedalboardInfoFactoryOnly:
        info->factory = true;
        break;
    default:
        info->factory = is_factory_pedalboard(bundle);
        break;
    }

    // --------------------------------------------------------------------------------------------------------
    // check if all plugins in the pedalboard exist in our world, also if licensed

    info->broken = info->hasTrialPlugins = false;

    if (LilvNodes* const blocks = lilv_plugin_get_value(p, ingenblocknode))
    {
        LilvWorld* const w2 = W;
        const NamespaceDefinitions_Mini ns(w2);

        LILV_FOREACH(nodes, itblocks, blocks)
        {
            const LilvNode* const block = lilv_nodes_get(blocks, itblocks);

            if (LilvNode* const proto = lilv_world_get(w, block, lv2protonode, nullptr))
            {
                const std::string uri = lilv_node_as_uri(proto);

                if (! contains(PLUGNFO_Mini, uri))
                {
                    info->broken = true;
                    lilv_node_free(proto);
                    break;
                }

                // checking for trial plugins, only needs to be done once
                if (!info->hasTrialPlugins && !info->factory)
                {
                    if (PLUGNFO_Mini[uri] == nullptr)
                    {
                        LilvNode* const urinode = lilv_new_uri(w2, uri.c_str());
                        PLUGNFO_Mini[uri] = _get_plugin_info_mini(w2, lilv_plugins_get_by_uri(PLUGINS, urinode), ns);
                        lilv_node_free(urinode);
                    }

                    if (const PluginInfo_Mini* const miniInfo = PLUGNFO_Mini[uri])
                        if (miniInfo->licensed == kPluginLicenseTrial)
                            info->hasTrialPlugins = true;
                }

                lilv_node_free(proto);
            }
        }

        lilv_nodes_free(blocks);
    }

    // --------------------------------------------------------------------------------------------------------
    // version

    info->version = 0;

    if (!info->factory)
    {
        if (LilvNodes* const nodes = lilv_plugin_get_value(p, versiontypenode))
        {
            info->version = lilv_node_as_int(lilv_nodes_get_first(nodes));
            lilv_nodes_free(nodes);
        }
    }

    return info;
}

bool _is_pedalboard_broken(const LilvPlugin* const p,
                           LilvWorld* const w,
                           const LilvNode* const ingenblocknode,
                           const LilvNode* const lv2protonode)
{
    bool broken = false;

    if (LilvNodes* const blocks = lilv_plugin_get_value(p, ingenblocknode))
    {
        LILV_FOREACH(nodes, itblocks, blocks)
        {
            const LilvNode* const block = lilv_nodes_get(blocks, itblocks);

            if (LilvNode* const proto = lilv_world_get(w, block, lv2protonode, nullptr))
            {
                const std::string uri = lilv_node_as_uri(proto);
                lilv_node_free(proto);

                if (! contains(PLUGNFO, uri))
                {
                    broken = true;
                    break;
                }
            }
        }

        lilv_nodes_free(blocks);
    }

    return broken;
}

// --------------------------------------------------------------------------------------------------------

// get_plugin_list
static const char** _get_plug_list_ret = nullptr;
static int _get_plug_list_lastsize = 0;

// get_all_plugins
static const PluginInfo_Mini** _get_plugs_mini_ret = nullptr;
static int _get_plugs_mini_lastsize = 0;

// get_all_pedalboards
static const PedalboardInfo_Mini** _get_pedals_mini_ret = nullptr;

// get_broken_pedalboards
static const char** _get_broken_pedals_ret = nullptr;

// get_pedalboard_info
static PedalboardInfo* _get_pedal_info_ret;

// add_bundle_to_lilv_world/remove_bundle_from_lilv_world
static const char** _add_remove_bundles_ret = nullptr;

// get_pedalboard_plugin_values
static const PedalboardPluginValues* _get_pedal_values_ret = nullptr;

// get_state_port_values
static StatePortValue* _get_state_values_ret = nullptr;

// file_uri_parse
static char* _file_uri_parse_ret = nullptr;

// --------------------------------------------------------------------------------------------------------

static void _clear_gui_port_info(PluginGUIPort& guiportinfo)
{
    if (guiportinfo.name != nc)
        free((void*)guiportinfo.name);
    if (guiportinfo.symbol != nc)
        free((void*)guiportinfo.symbol);

    memset(&guiportinfo, 0, sizeof(PluginGUIPort));
}

static void _clear_port_info(PluginPort& portinfo)
{
    if (portinfo.name != nc)
        free((void*)portinfo.name);
    if (portinfo.symbol != nc)
        free((void*)portinfo.symbol);
    if (portinfo.comment != nc)
        free((void*)portinfo.comment);
    if (portinfo.designation != nc)
        free((void*)portinfo.designation);
    if (portinfo.shortName != nc)
        free((void*)portinfo.shortName);

    if (portinfo.properties != nullptr)
    {
        for (int i=0; portinfo.properties[i] != nullptr; ++i)
            free((void*)portinfo.properties[i]);
        delete[] portinfo.properties;
    }

    if (portinfo.scalePoints != nullptr)
    {
        for (int i=0; portinfo.scalePoints[i].valid; ++i)
            free((void*)portinfo.scalePoints[i].label);
        delete[] portinfo.scalePoints;
    }

    if (portinfo.units._custom)
    {
        if (portinfo.units.label != nc)
            free((void*)portinfo.units.label);
        if (portinfo.units.render != nc)
            free((void*)portinfo.units.render);
        if (portinfo.units.symbol != nc)
            free((void*)portinfo.units.symbol);
    }

    memset(&portinfo, 0, sizeof(PluginPort));
}

static void _clear_parameter_info(const PluginParameter& parameter)
{
    free((void*)parameter.uri);
    free((void*)parameter.label);
    free((void*)parameter.type);

    if (parameter.comment != nc)
        free((void*)parameter.comment);
    if (parameter.shortName != nc)
        free((void*)parameter.shortName);

    if (parameter.fileTypes != nullptr)
    {
        free((void*)parameter.fileTypes[0]);
        delete[] parameter.fileTypes;
    }

    if (parameter.supportedExtensions != nullptr)
    {
        free((void*)parameter.supportedExtensions[0]);
        delete[] parameter.supportedExtensions;
    }

    if (parameter.ranges.type == 's')
    {
        free((void*)parameter.ranges.s);
    }

    if (parameter.units._custom)
    {
        if (parameter.units.label != nc)
            free((void*)parameter.units.label);
        if (parameter.units.render != nc)
            free((void*)parameter.units.render);
        if (parameter.units.symbol != nc)
            free((void*)parameter.units.symbol);
    }

    // memset(&parameter, 0, sizeof(PluginParameter));
}

static void _clear_plugin_info(PluginInfo& info)
{
    if (info.name != nc)
        lilv_free((void*)info.name);
    if (info.binary != nc)
        free((void*)info.binary);
    if (info.license != nc)
        free((void*)info.license);
    if (info.comment != nc)
        free((void*)info.comment);
    if (info.buildEnvironment != nc &&
        info.buildEnvironment != kBuildEnvironmentProd &&
        info.buildEnvironment != kBuildEnvironmentDev &&
        info.buildEnvironment != kBuildEnvironmentLabs)
        free((void*)info.buildEnvironment);
    if (info.version != nc)
        free((void*)info.version);
    if (info.brand != nc)
        free((void*)info.brand);
    if (info.label != nc)
        free((void*)info.label);
    if (info.author.name != nc)
        free((void*)info.author.name);
    if (info.author.homepage != nc)
        free((void*)info.author.homepage);
    if (info.author.email != nc)
        free((void*)info.author.email);
    if (info.gui.resourcesDirectory != nc)
        free((void*)info.gui.resourcesDirectory);
    if (info.gui.iconTemplate != nc)
        free((void*)info.gui.iconTemplate);
    if (info.gui.settingsTemplate != nc)
        free((void*)info.gui.settingsTemplate);
    if (info.gui.javascript != nc)
        free((void*)info.gui.javascript);
    if (info.gui.stylesheet != nc)
        free((void*)info.gui.stylesheet);
    if (info.gui.screenshot != nc)
        free((void*)info.gui.screenshot);
    if (info.gui.thumbnail != nc)
        free((void*)info.gui.thumbnail);
    if (info.gui.discussionURL != nc)
        free((void*)info.gui.discussionURL);
    if (info.gui.documentation != nc)
        free((void*)info.gui.documentation);
    if (info.gui.brand != nc)
        free((void*)info.gui.brand);
    if (info.gui.label != nc)
        free((void*)info.gui.label);
    if (info.gui.model != nc)
        free((void*)info.gui.model);
    if (info.gui.panel != nc)
        free((void*)info.gui.panel);
    if (info.gui.color != nc)
        free((void*)info.gui.color);
    if (info.gui.knob != nc)
        free((void*)info.gui.knob);

    if (info.gui.ports != nullptr)
    {
        for (int i=0; info.gui.ports[i].valid; ++i)
            _clear_gui_port_info(info.gui.ports[i]);
        delete[] info.gui.ports;
    }

    if (info.gui.monitoredOutputs != nullptr)
    {
        for (int i=0; info.gui.monitoredOutputs[i]; ++i)
            free((void*)info.gui.monitoredOutputs[i]);
        delete[] info.gui.monitoredOutputs;
    }

    if (info.bundles != nullptr)
    {
        for (int i=0; info.bundles[i]; ++i)
            free((void*)info.bundles[i]);
        delete[] info.bundles;
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

    if (info.parameters != nullptr)
    {
        for (int i=0; info.parameters[i].valid; ++i)
            _clear_parameter_info(info.parameters[i]);
        delete[] info.parameters;
    }

    if (info.presets != nullptr)
    {
        for (int i=0; info.presets[i].valid; ++i)
        {
            free((void*)info.presets[i].uri);
            free((void*)info.presets[i].label);
            if (info.presets[i].path != nc)
                free((void*)info.presets[i].path);
        }
        delete[] info.presets;
    }

    memset(&info, 0, sizeof(PluginInfo));
}

static void _clear_pedalboard_info(PedalboardInfo& info)
{
    if (info.title != nc && info.title != kUntitled)
        free((void*)info.title);

    if (info.connections != nullptr)
    {
        for (int i=0; info.connections[i].valid; ++i)
        {
            lilv_free((void*)info.connections[i].source);
            lilv_free((void*)info.connections[i].target);
        }
        delete[] info.connections;
    }

    if (info.plugins != nullptr)
    {
        for (int i=0; info.plugins[i].valid; ++i)
        {
            const PedalboardPlugin& p(info.plugins[i]);

            free((void*)p.instance);
            free((void*)p.uri);

            if (p.preset != nc)
                free((void*)p.preset);

            if (p.ports != nullptr)
            {
                for (int j=0; p.ports[j].valid; ++j)
                    lilv_free((void*)p.ports[j].symbol);
                delete[] p.ports;
            }
        }
        delete[] info.plugins;
    }

    if (info.hardware.midi_ins != nullptr)
    {
        for (int i=0; info.hardware.midi_ins[i].valid; ++i)
        {
            lilv_free((void*)info.hardware.midi_ins[i].symbol);

            if (info.hardware.midi_ins[i].name != nc)
                free((void*)info.hardware.midi_ins[i].name);
        }

        delete[] info.hardware.midi_ins;
    }

    if (info.hardware.midi_outs != nullptr)
    {
        for (int i=0; info.hardware.midi_outs[i].valid; ++i)
        {
            lilv_free((void*)info.hardware.midi_outs[i].symbol);

            if (info.hardware.midi_outs[i].name != nc)
                free((void*)info.hardware.midi_outs[i].name);
        }

        delete[] info.hardware.midi_outs;
    }

    memset(&info, 0, sizeof(PedalboardInfo));
}

// --------------------------------------------------------------------------------------------------------

static void _clear_pedalboards(const PedalboardInfo_Mini** const pedalboards)
{
    if (pedalboards == nullptr)
        return;

    const PedalboardInfo_Mini* info;

    for (int i=0;; ++i)
    {
        info = pedalboards[i];
        if (info == nullptr)
            break;

        free((void*)info->uri);
        free((void*)info->bundle);
        if (info->title != nc && info->title != kUntitled)
            free((void*)info->title);

        delete info;
    }

    delete[] pedalboards;
}

static void _clear_pedalboard_plugin_values()
{
    if (_get_pedal_values_ret == nullptr)
        return;

    for (int i=0; _get_pedal_values_ret[i].valid; ++i)
    {
        const PedalboardPluginValues& pvals(_get_pedal_values_ret[i]);

        free((void*)pvals.instance);

        if (pvals.preset != nc)
            free((void*)pvals.preset);

        if (pvals.ports != nullptr)
        {
            for (int j=0; pvals.ports[j].valid; ++j)
                lilv_free((void*)pvals.ports[j].symbol);
            delete[] pvals.ports;
        }
    }

    delete[] _get_pedal_values_ret;
    _get_pedal_values_ret = nullptr;
}

static void _clear_state_values()
{
    if (_get_state_values_ret == nullptr)
        return;

    for (int i=0; _get_state_values_ret[i].valid; ++i)
        free((void*)_get_state_values_ret[i].symbol);

    delete[] _get_state_values_ret;
    _get_state_values_ret = nullptr;
}

// --------------------------------------------------------------------------------------------------------

static const PluginInfo* _fill_plugin_info_with_presets(LilvWorld* const w, PluginInfo& info, const std::string& uri)
{
    if (std::find(PLUGINStoReload.begin(), PLUGINStoReload.end(), uri) == PLUGINStoReload.end())
        return &info;

    PLUGINStoReload.remove(uri);

    LilvNode* const node = lilv_new_uri(w, uri.c_str());

    if (node == nullptr)
        return &info;

    const LilvPlugin* const p = lilv_plugins_get_by_uri(PLUGINS, node);
    lilv_node_free(node);

    if (p == nullptr)
        return &info;

    if (info.presets != nullptr)
    {
        for (int i=0; info.presets[i].valid; ++i)
        {
            free((void*)info.presets[i].uri);
            free((void*)info.presets[i].label);
            if (info.presets[i].path != nc)
                free((void*)info.presets[i].path);
        }
        delete[] info.presets;
        info.presets = nullptr;
    }

    LilvNode* const pset_Preset = lilv_new_uri(w, LV2_PRESETS__Preset);
    LilvNode* const rdfs_label  = lilv_new_uri(w, LILV_NS_RDFS "label");

    _place_preset_info(w, info, p, pset_Preset, rdfs_label);

    lilv_node_free(pset_Preset);
    lilv_node_free(rdfs_label);

    return &info;
}

// --------------------------------------------------------------------------------------------------------

void init(void)
{
    lilv_world_free(W);
    W = lilv_world_new();
    lilv_world_load_all(W);
    _refresh();
}

void cleanup(void)
{
    if (_add_remove_bundles_ret != nullptr)
    {
        for (int i=0; _add_remove_bundles_ret[i] != nullptr; ++i)
            free((void*)_add_remove_bundles_ret[i]);
        delete[] _add_remove_bundles_ret;
        _add_remove_bundles_ret = nullptr;
    }

    if (_get_broken_pedals_ret != nullptr)
    {
        for (int i=0; _get_broken_pedals_ret[i] != nullptr; ++i)
            free((void*)_get_broken_pedals_ret[i]);
        delete[] _get_broken_pedals_ret;
        _get_broken_pedals_ret = nullptr;
    }

    if (_get_plug_list_ret != nullptr)
    {
        delete[] _get_plug_list_ret;
        _get_plug_list_ret = nullptr;
    }

    if (_get_plugs_mini_ret != nullptr)
    {
        delete[] _get_plugs_mini_ret;
        _get_plugs_mini_ret = nullptr;
    }

    _get_plug_list_lastsize = 0;
    _get_plugs_mini_lastsize = 0;

    PLUGINS = nullptr;
    BUNDLES.clear();

    for (auto& map : PLUGNFO_Mini)
    {
        if (const PluginInfo_Mini* const info = map.second)
            _clear_plugin_info_mini(info);
    }

    for (auto& map : PLUGNFO)
    {
        PluginInfo& info = map.second;
        _clear_plugin_info(info);
    }

    PLUGNFO_Mini.clear();
    PLUGNFO.clear();

    lilv_world_free(W);
    W = nullptr;

    if (_file_uri_parse_ret != nullptr)
    {
        free(_file_uri_parse_ret);
        _file_uri_parse_ret = nullptr;
    }

    _clear_pedalboards(_get_pedals_mini_ret);
    _get_pedals_mini_ret = nullptr;

    _clear_pedalboards(FACTORYINFO);
    FACTORYINFO = nullptr;

    if (_get_pedal_info_ret != nullptr)
    {
        _clear_pedalboard_info(*_get_pedal_info_ret);
        _get_pedal_info_ret = nullptr;
    }

    _clear_pedalboard_plugin_values();
    _clear_state_values();
}

// --------------------------------------------------------------------------------------------------------

bool is_bundle_loaded(const char* const bundle)
{
    // lilv wants the last character as the separator
    char tmppath[PATH_MAX+2];
    char* cbundlepath = realpath(bundle, tmppath);

    if (cbundlepath == nullptr)
        return false;

    {
        const size_t size = strlen(cbundlepath);
        if (size <= 1)
            return false;

        if (cbundlepath[size] != OS_SEP)
        {
            cbundlepath[size  ] = OS_SEP;
            cbundlepath[size+1] = '\0';
        }
    }

    std::string bundlepath(cbundlepath);

    return (std::find(BUNDLES.begin(), BUNDLES.end(), bundlepath) != BUNDLES.end());
}

const char* const* add_bundle_to_lilv_world(const char* const bundle)
{
#ifdef HAVE_NEW_LILV
    // lilv wants the last character as the separator
    char tmppath[PATH_MAX+2];
    char* cbundlepath = realpath(bundle, tmppath);

    if (cbundlepath == nullptr)
        return nullptr;

    {
        const size_t size = strlen(cbundlepath);
        if (size <= 1)
            return nullptr;

        if (cbundlepath[size] != OS_SEP)
        {
            cbundlepath[size  ] = OS_SEP;
            cbundlepath[size+1] = '\0';
        }
    }

    std::string bundlepath(cbundlepath);

    // stop now if bundle is already loaded
    if (std::find(BUNDLES.begin(), BUNDLES.end(), bundlepath) != BUNDLES.end())
        return nullptr;

    LilvWorld* const w = W;

    // convert bundle string into a lilv node
    LilvNode* const bundlenode = lilv_new_file_uri(w, nullptr, cbundlepath);

    // load the bundle
    lilv_world_load_bundle(w, bundlenode);

    // free bundlenode, no longer needed
    lilv_node_free(bundlenode);

    // refresh PLUGINS
    PLUGINS = lilv_world_get_all_plugins(w);

    // add to loaded list
    BUNDLES.push_back(bundlepath);

    // fill in for any new plugins that appeared
    std::vector<const char*> addedPlugins;

    // check plugins provided by this bundle
    if (LilvWorld* const w2 = lilv_world_new())
    {
#ifdef HAVE_NEW_LILV
        lilv_world_load_specifications(w2);
        lilv_world_load_plugin_classes(w2);
#endif

        LilvNode* const b = lilv_new_file_uri(w2, nullptr, cbundlepath);
        lilv_world_load_bundle(w2, b);
        lilv_node_free(b);

        const LilvPlugins* const plugins = lilv_world_get_all_plugins(w2);

        LILV_FOREACH(plugins, itpls, plugins)
        {
            const LilvPlugin* const p = lilv_plugins_get(plugins, itpls);

            const std::string uri = lilv_node_as_uri(lilv_plugin_get_uri(p));

            if (std::find(BLACKLIST.begin(), BLACKLIST.end(), uri) != BLACKLIST.end())
                continue;

            // store new empty data
            PLUGNFO[uri] = PluginInfo_Init;
            PLUGNFO_Mini[uri] = nullptr;

            addedPlugins.push_back(strdup(uri.c_str()));
        }

        lilv_world_free(w2);
    }

    if (size_t plugCount = addedPlugins.size())
    {
        if (_add_remove_bundles_ret != nullptr)
        {
            for (int i=0; _add_remove_bundles_ret[i] != nullptr; ++i)
                free((void*)_add_remove_bundles_ret[i]);
            delete[] _add_remove_bundles_ret;
        }

        _add_remove_bundles_ret = new const char*[plugCount+1];

        plugCount = 0;
        for (const char* uri : addedPlugins)
            _add_remove_bundles_ret[plugCount++] = uri;

        _add_remove_bundles_ret[plugCount] = nullptr;

        return _add_remove_bundles_ret;
    }
#endif

    return nullptr;

#ifndef HAVE_NEW_LILV
    // unused
    (void)bundle;
#endif
}

const char* const* remove_bundle_from_lilv_world(const char* const bundle, const char* const resource)
{
#ifdef HAVE_NEW_LILV
    // lilv wants the last character as the separator
    char tmppath[PATH_MAX+2];
    char* cbundlepath = realpath(bundle, tmppath);

    if (cbundlepath == nullptr)
        return nullptr;

    {
        const size_t size = strlen(cbundlepath);
        if (size <= 1)
            return nullptr;

        if (cbundlepath[size] != OS_SEP)
        {
            cbundlepath[size  ] = OS_SEP;
            cbundlepath[size+1] = '\0';
        }
    }

    std::string bundlepath(cbundlepath);

    // stop now if bundle is not loaded
    if (std::find(BUNDLES.begin(), BUNDLES.end(), bundlepath) == BUNDLES.end())
        return nullptr;

    LilvWorld* const w = W;

    // unload resource if requested
    if (resource != NULL && resource[0] != '\0')
    {
        if (LilvNode* const resourcenode = lilv_new_uri(w, resource))
        {
            lilv_world_unload_resource(w, resourcenode);
            lilv_node_free(resourcenode);
        }
    }

    // remove from loaded list
    BUNDLES.remove(bundlepath);

    std::vector<const char*> removedPlugins;

    // remove all plugins that are present on that bundle
    LILV_FOREACH(plugins, itpls, PLUGINS)
    {
        const LilvPlugin* const p = lilv_plugins_get(PLUGINS, itpls);
        const std::string uri = lilv_node_as_uri(lilv_plugin_get_uri(p));

        if (! contains(PLUGNFO, uri))
            continue;

        const LilvNodes* const bundles = lilv_plugin_get_data_uris(p);

        LILV_FOREACH(nodes, itbnds, bundles)
        {
            const LilvNode* const bundlenode = lilv_nodes_get(bundles, itbnds);

            if (bundlenode == nullptr)
                continue;
            if (! lilv_node_is_uri(bundlenode))
                continue;

            char* bundleparsed;
            char* tmp;

            tmp = lilv_file_uri_parse(lilv_node_as_uri(bundlenode), nullptr);
            if (tmp == nullptr)
                continue;

            bundleparsed = dirname(tmp);
            if (bundleparsed == nullptr)
            {
                lilv_free(tmp);
                continue;
            }

            bundleparsed = realpath(bundleparsed, tmppath); // note: this invalidates cbundlepath
            lilv_free(tmp);
            if (bundleparsed == nullptr)
                continue;

            const size_t size = strlen(bundleparsed);
            if (size <= 1)
                continue;

            if (bundleparsed[size] != OS_SEP)
            {
                bundleparsed[size  ] = OS_SEP;
                bundleparsed[size+1] = '\0';
            }

            if (bundlepath != bundleparsed)
                continue;

            _clear_plugin_info(PLUGNFO[uri]);
            PLUGNFO.erase(uri);

            if (const PluginInfo_Mini* const info = PLUGNFO_Mini[uri])
                _clear_plugin_info_mini(info);

            PLUGNFO_Mini.erase(uri);

            removedPlugins.push_back(strdup(uri.c_str()));
            break;
        }
    }

    // convert bundle string into a lilv node
    LilvNode* const bundlenode = lilv_new_file_uri(w, nullptr, bundlepath.c_str());

    // unload the bundle
    lilv_world_unload_bundle(w, bundlenode);

    // free bundlenode, no longer needed
    lilv_node_free(bundlenode);

    // refresh PLUGINS
    PLUGINS = lilv_world_get_all_plugins(w);

    if (size_t plugCount = removedPlugins.size())
    {
        if (_add_remove_bundles_ret != nullptr)
        {
            for (int i=0; _add_remove_bundles_ret[i] != nullptr; ++i)
                free((void*)_add_remove_bundles_ret[i]);
            delete[] _add_remove_bundles_ret;
        }

        _add_remove_bundles_ret = new const char*[plugCount+1];

        plugCount = 0;
        for (const char* uri : removedPlugins)
            _add_remove_bundles_ret[plugCount++] = uri;

        _add_remove_bundles_ret[plugCount] = nullptr;

        // force get_plugin_list/get_all_plugins to reload info next time
        _get_plug_list_lastsize = -1;
        _get_plugs_mini_lastsize = -1;

        return _add_remove_bundles_ret;
    }
#endif

    return nullptr;

#ifndef HAVE_NEW_LILV
    // unused
    (void)bundle;
#endif
}

const char* const* get_plugin_list(void)
{
    const int newsize = (int)lilv_plugins_size(PLUGINS);

    if (newsize == 0)
    {
        if (_get_plug_list_ret != nullptr)
        {
            delete[] _get_plug_list_ret;
            _get_plug_list_ret = nullptr;
        }
        _get_plug_list_lastsize = 0;
        return nullptr;
    }

    if (newsize > _get_plug_list_lastsize)
    {
        _get_plug_list_lastsize = newsize;

        if (_get_plug_list_ret != nullptr)
            delete[] _get_plug_list_ret;

        _get_plug_list_ret = new const char*[newsize+1];
        memset(_get_plug_list_ret, 0, sizeof(void*) * (newsize+1));
    }
    else if (newsize < _get_plug_list_lastsize)
    {
        memset(_get_plug_list_ret, 0, sizeof(void*) * (newsize+1));
    }

    int curIndex = 0;
    LILV_FOREACH(plugins, itpls, PLUGINS)
    {
        if (curIndex >= newsize)
            break;

        const LilvPlugin* const p = lilv_plugins_get(PLUGINS, itpls);

        const char* const uri = lilv_node_as_uri(lilv_plugin_get_uri(p));
        const std::string uri2(uri);

        if (std::find(BLACKLIST.begin(), BLACKLIST.end(), uri2) != BLACKLIST.end())
            continue;

        _get_plug_list_ret[curIndex++] = uri;
    }

    return _get_plug_list_ret;
}

const PluginInfo_Mini* const* get_all_plugins(void)
{
    const int newsize = (int)lilv_plugins_size(PLUGINS);

    if (newsize == 0)
    {
        if (_get_plugs_mini_ret != nullptr)
        {
            delete[] _get_plugs_mini_ret;
            _get_plugs_mini_ret = nullptr;
        }
        _get_plugs_mini_lastsize = 0;
        return nullptr;
    }

    if (newsize > _get_plugs_mini_lastsize)
    {
        _get_plugs_mini_lastsize = newsize;

        if (_get_plugs_mini_ret != nullptr)
            delete[] _get_plugs_mini_ret;

        _get_plugs_mini_ret = new const PluginInfo_Mini*[newsize+1];
        memset(_get_plugs_mini_ret, 0, sizeof(void*) * (newsize+1));
    }
    else if (newsize < _get_plugs_mini_lastsize)
    {
        memset(_get_plugs_mini_ret, 0, sizeof(void*) * (newsize+1));
    }

    LilvWorld* const w = W;

    const NamespaceDefinitions_Mini ns(w);

    int curIndex = 0;
    LILV_FOREACH(plugins, itpls, PLUGINS)
    {
        if (curIndex >= newsize)
            break;

        const LilvPlugin* const p = lilv_plugins_get(PLUGINS, itpls);

        const std::string uri = lilv_node_as_uri(lilv_plugin_get_uri(p));

        if (std::find(BLACKLIST.begin(), BLACKLIST.end(), uri) != BLACKLIST.end())
            continue;

        // check if it's already cached
        if (! contains(PLUGNFO_Mini, uri) || PLUGNFO_Mini[uri] == nullptr)
            PLUGNFO_Mini[uri] = _get_plugin_info_mini(w, p, ns);

        if (const PluginInfo_Mini* const miniInfo = PLUGNFO_Mini[uri])
        {
#if SHOW_ONLY_PLUGINS_WITH_MODGUI
            if (miniInfo->gui.resourcesDirectory == nc)
                continue;
#endif
            _get_plugs_mini_ret[curIndex++] = PLUGNFO_Mini[uri];
        }
    }

    return _get_plugs_mini_ret;
}

const PluginInfo* get_plugin_info(const char* const uri_)
{
    const std::string uri = uri_;

    // check if it exists
    if (! contains(PLUGNFO, uri))
        return nullptr;

    LilvWorld* const w = W;

    // check if it's already cached
    if (PLUGNFO[uri].valid)
        return _fill_plugin_info_with_presets(w, PLUGNFO[uri], uri);

    LilvNode* const urinode = lilv_new_uri(w, uri_);

    if (urinode == nullptr)
        return nullptr;

    const LilvPlugin* const p = lilv_plugins_get_by_uri(PLUGINS, urinode);
    lilv_node_free(urinode);

    if (p != nullptr)
    {
        const NamespaceDefinitions ns(w);
        const PluginInfo& pInfo(_get_plugin_info(w, p, ns));

        PLUGNFO[uri] = pInfo;
        _fill_plugin_info_mini_from_full(pInfo, &PLUGNFO_Mini[uri]);

        return &PLUGNFO[uri];
    }

    return nullptr;
}

const NonCachedPluginInfo* get_non_cached_plugin_info(const char* uri)
{
    const PluginInfo* const info = get_plugin_info(uri);

    if (info == nullptr || ! info->valid)
        return nullptr;

    static NonCachedPluginInfo ncInfo;
    ncInfo.licensed = info->licensed;
    ncInfo.presets = info->presets;
    return &ncInfo;
}

const PluginGUI* get_plugin_gui(const char* uri_)
{
    const std::string uri = uri_;

    // check if it exists
    if (! contains(PLUGNFO, uri))
        return nullptr;

    // check if it's already cached
    if (PLUGNFO[uri].valid)
        return &PLUGNFO[uri].gui;

    LilvWorld* const w = W;

    LilvNode* const urinode = lilv_new_uri(w, uri_);

    if (urinode == nullptr)
        return nullptr;

    const LilvPlugin* const p = lilv_plugins_get_by_uri(PLUGINS, urinode);
    lilv_node_free(urinode);

    if (p != nullptr)
    {
        const NamespaceDefinitions ns(w);
        const PluginInfo& pInfo(_get_plugin_info(w, p, ns));

        PLUGNFO[uri] = pInfo;
        _fill_plugin_info_mini_from_full(pInfo, &PLUGNFO_Mini[uri]);

        return &PLUGNFO[uri].gui;
    }

    // not found
    return nullptr;
}

const PluginGUI_Mini* get_plugin_gui_mini(const char* uri_)
{
    const std::string uri = uri_;

    // check if it exists
    if (! contains(PLUGNFO_Mini, uri))
        return nullptr;

    // check if it's already cached
    if (const PluginInfo_Mini* const miniInfo = PLUGNFO_Mini[uri])
        return &miniInfo->gui;

    LilvWorld* const w = W;

    const NamespaceDefinitions_Mini ns(w);

    // look for it
    LILV_FOREACH(plugins, itpls, PLUGINS)
    {
        const LilvPlugin* const p = lilv_plugins_get(PLUGINS, itpls);

        std::string uri2 = lilv_node_as_uri(lilv_plugin_get_uri(p));

        if (uri2 != uri)
            continue;

        // found it
        printf("NOTICE: Plugin '%s' was not (small) cached, scanning it now...\n", uri_);
        if (const PluginInfo_Mini* const miniInfo = _get_plugin_info_mini(w, p, ns))
        {
            PLUGNFO_Mini[uri] = miniInfo;
            return &miniInfo->gui;
        }

        // error
        return nullptr;
    }

    // not found
    return nullptr;
}

// --------------------------------------------------------------------------------------------------------

const PluginPort* get_plugin_control_inputs(const char* const uri_)
{
    const std::string uri = uri_;

    // check if plugin exists
    if (! contains(PLUGNFO, uri))
        return nullptr;

    // return right-away if already cached
    if (PLUGNFO[uri].valid)
    {
        const PluginInfo& pInfo = PLUGNFO[uri];
        return pInfo.ports.control.input;
    }

    LilvWorld* const w = W;

    // look for it
    LILV_FOREACH(plugins, itpls, PLUGINS)
    {
        const LilvPlugin* const p = lilv_plugins_get(PLUGINS, itpls);

        const char* const uri2 = lilv_node_as_uri(lilv_plugin_get_uri(p));

        if (uri != uri2)
            continue;

        // found the plugin
        const NamespaceDefinitions ns(w);
        const PluginInfo& pInfo = _get_plugin_info(w, p, ns);

        PLUGNFO[uri] = pInfo;
        _fill_plugin_info_mini_from_full(pInfo, &PLUGNFO_Mini[uri]);

        return pInfo.ports.control.input;
    }

    // plugin not found
    return nullptr;
}

const PluginInfo_Essentials* get_plugin_info_essentials(const char* const uri_)
{
    static PluginInfo_Essentials info;

    const std::string uri = uri_;

    // check if plugin exists
    if (! contains(PLUGNFO, uri))
        return nullptr;

    // check if plugin is already cached
    if (PLUGNFO[uri].valid)
    {
        const PluginInfo& pInfo = PLUGNFO[uri];

        info.controlInputs    = pInfo.ports.control.input;
        info.monitoredOutputs = pInfo.gui.monitoredOutputs;
        info.parameters       = pInfo.parameters;
        info.buildEnvironment = pInfo.buildEnvironment;
        info.microVersion     = pInfo.microVersion;
        info.minorVersion     = pInfo.minorVersion;
        info.release          = pInfo.release;
        info.builder          = pInfo.builder;
        return &info;
    }

    LilvWorld* const w = W;

    // look for it
    LILV_FOREACH(plugins, itpls, PLUGINS)
    {
        const LilvPlugin* const p = lilv_plugins_get(PLUGINS, itpls);

        const char* const uri2 = lilv_node_as_uri(lilv_plugin_get_uri(p));

        if (uri != uri2)
            continue;

        // found the plugin
        const NamespaceDefinitions ns(w);
        const PluginInfo& pInfo = _get_plugin_info(w, p, ns);

        PLUGNFO[uri] = pInfo;
        _fill_plugin_info_mini_from_full(pInfo, &PLUGNFO_Mini[uri]);

        info.controlInputs    = pInfo.ports.control.input;
        info.monitoredOutputs = pInfo.gui.monitoredOutputs;
        info.parameters       = pInfo.parameters;
        info.buildEnvironment = pInfo.buildEnvironment;
        info.microVersion     = pInfo.microVersion;
        info.minorVersion     = pInfo.minorVersion;
        info.release          = pInfo.release;
        info.builder          = pInfo.builder;
        return &info;
    }

    // plugin not found
    return nullptr;
}

// --------------------------------------------------------------------------------------------------------

// check if a plugin preset is valid (must exist)
bool is_plugin_preset_valid(const char* const plugin_, const char* const preset)
{
    const std::string plugin(plugin_);

    // check if plugin exists
    if (! contains(PLUGNFO, plugin))
        return false;

    // plugin must have been cached before
    if (! PLUGNFO[plugin].valid)
        return false;

    const PluginInfo& pInfo = PLUGNFO[plugin];

    if (pInfo.presets == nullptr)
        return false;

    for (int i=0;; ++i)
    {
        const PluginPreset& prInfo(pInfo.presets[i]);

        if (! prInfo.valid)
            return false;

        if (strcmp(prInfo.uri, preset) == 0)
            return true;
    }

    return false;
}

// trigger a preset rescan for a plugin the next time it's loaded
void rescan_plugin_presets(const char* const uri_)
{
    const std::string uri(uri_);

    if (std::find(PLUGINStoReload.begin(), PLUGINStoReload.end(), uri) == PLUGINStoReload.end())
        PLUGINStoReload.push_back(uri);
}

// --------------------------------------------------------------------------------------------------------

const PedalboardInfo_Mini* const* get_all_pedalboards(const int ptype)
{
    // factory pedalboards do not change, so return cached value directly
    if (ptype == kPedalboardInfoFactoryOnly && FACTORYINFO != nullptr)
        return FACTORYINFO;

    char* const oldlv2path = getenv_strdup_or_null("LV2_PATH");

    const char* pedalboard_lv2_path;
    switch (ptype)
    {
    case kPedalboardInfoUserOnly:
        if (const char* const pbdir = getenv("MOD_USER_PEDALBOARDS_DIR"))
            pedalboard_lv2_path = pbdir;
        else
            pedalboard_lv2_path = "~/.pedalboards";
        break;
    case kPedalboardInfoFactoryOnly:
        if (FACTORY_PEDALBOARDS_DIRlen != 0)
            pedalboard_lv2_path = FACTORY_PEDALBOARDS_DIR;
        else
            pedalboard_lv2_path = "/usr/share/mod/pedalboards";
        break;
    default:
        pedalboard_lv2_path = _get_lv2_pedalboards_path();
        break;
    }

    setenv("LV2_PATH", pedalboard_lv2_path, 1);

    LilvWorld* const w = lilv_world_new();
    lilv_world_load_all(w);

    if (oldlv2path != nullptr)
    {
        setenv("LV2_PATH", oldlv2path, 1);
        free(oldlv2path);
    }
    else
    {
        unsetenv("LV2_PATH");
    }

    LilvNode* const versiontypenode = lilv_new_uri(w, LILV_NS_MODPEDAL "version");
    LilvNode* const rdftypenode = lilv_new_uri(w, LILV_NS_RDF "type");
    LilvNode* const ingenblocknode = lilv_new_uri(w, LILV_NS_INGEN "block");
    LilvNode* const lv2protonode = lilv_new_uri(w, LILV_NS_LV2 "prototype");
    const LilvPlugins* const plugins = lilv_world_get_all_plugins(w);

    std::vector<const PedalboardInfo_Mini*> allpedals;
    allpedals.reserve(lilv_plugins_size(plugins));

    LILV_FOREACH(plugins, itpls, plugins)
    {
        const LilvPlugin* const p = lilv_plugins_get(plugins, itpls);

        if (const PedalboardInfo_Mini* info = _get_pedalboard_info_mini(w, p,
                                                                        versiontypenode, rdftypenode, ingenblocknode, lv2protonode,
                                                                        static_cast<PedalboardInfoType>(ptype)))
        {
            allpedals.push_back(info);
        }
    }

    lilv_free(versiontypenode);
    lilv_free(rdftypenode);
    lilv_free(ingenblocknode);
    lilv_free(lv2protonode);
    lilv_world_free(w);

    if (size_t pbcount = allpedals.size())
    {
        const PedalboardInfo_Mini** pedals = new const PedalboardInfo_Mini*[pbcount+1];

        pbcount = 0;
        for (const PedalboardInfo_Mini* info : allpedals)
            pedals[pbcount++] = info;

        pedals[pbcount] = nullptr;

        if (ptype == kPedalboardInfoFactoryOnly)
        {
            FACTORYINFO = pedals;
            return pedals;
        }

        _clear_pedalboards(_get_pedals_mini_ret);
        _get_pedals_mini_ret = pedals;
        return _get_pedals_mini_ret;
    }

    return nullptr;
}

const char* const* get_broken_pedalboards(void)
{
    return nullptr;
    // Custom path for pedalboards
    char* const oldlv2path = getenv_strdup_or_null("LV2_PATH");
    setenv("LV2_PATH", _get_lv2_pedalboards_path(), 1);

    LilvWorld* const w = lilv_world_new();
    lilv_world_load_all(w);

    if (oldlv2path != nullptr)
    {
        setenv("LV2_PATH", oldlv2path, 1);
        free(oldlv2path);
    }
    else
    {
        unsetenv("LV2_PATH");
    }

    LilvNode* const ingenblocknode = lilv_new_uri(w, LILV_NS_INGEN "block");
    LilvNode* const lv2protonode = lilv_new_uri(w, LILV_NS_LV2 "prototype");
    const LilvPlugins* const plugins = lilv_world_get_all_plugins(w);

    std::vector<const char*> brokenpedals;
    brokenpedals.reserve(lilv_plugins_size(plugins));

    LILV_FOREACH(plugins, itpls, plugins)
    {
        const LilvPlugin* const p = lilv_plugins_get(plugins, itpls);

        // get new info
        if (_is_pedalboard_broken(p, w, ingenblocknode, lv2protonode))
            brokenpedals.push_back(strdup(lilv_node_as_uri(lilv_plugin_get_uri(p))));
    }

    lilv_free(ingenblocknode);
    lilv_free(lv2protonode);
    lilv_world_free(w);

    if (size_t pbcount = brokenpedals.size())
    {
        if (_get_broken_pedals_ret != nullptr)
        {
            for (int i=0; _get_broken_pedals_ret[i] != nullptr; ++i)
                free((void*)_get_broken_pedals_ret[i]);
            delete[] _get_broken_pedals_ret;
        }

        _get_broken_pedals_ret = new const char*[pbcount+1];

        pbcount = 0;
        for (const char* pedal : brokenpedals)
            _get_broken_pedals_ret[pbcount++] = pedal;

        _get_broken_pedals_ret[pbcount] = nullptr;

        return _get_broken_pedals_ret;
    }

    return nullptr;
}

const PedalboardInfo* get_pedalboard_info(const char* const bundle)
{
    static PedalboardInfo info;

    size_t bundlepathsize;
    const char* const bundlepath = _get_safe_bundlepath(bundle, bundlepathsize);

    if (bundlepath == nullptr)
        return nullptr;

    LilvWorld* const w = lilv_world_new();
#ifdef HAVE_NEW_LILV
    lilv_world_load_specifications(w);
    lilv_world_load_plugin_classes(w);
#endif

    LilvNode* const b = lilv_new_file_uri(w, nullptr, bundlepath);
    lilv_world_load_bundle(w, b);
    lilv_node_free(b);

    const LilvPlugins* const plugins = lilv_world_get_all_plugins(w);

    if (lilv_plugins_size(plugins) != 1)
    {
        lilv_world_free(w);
        return nullptr;
    }

    const LilvPlugin* p = nullptr;

    LILV_FOREACH(plugins, itpls, plugins) {
        p = lilv_plugins_get(plugins, itpls);
        break;
    }

    if (p == nullptr)
    {
        lilv_world_free(w);
        return nullptr;
    }

    bool isPedalboard = false;
    LilvNode* const rdftypenode = lilv_new_uri(w, LILV_NS_RDF "type");

    if (LilvNodes* const nodes = lilv_plugin_get_value(p, rdftypenode))
    {
        LILV_FOREACH(nodes, it, nodes)
        {
            const LilvNode* const node = lilv_nodes_get(nodes, it);

            if (const char* const nodestr = lilv_node_as_string(node))
            {
                if (strcmp(nodestr, LILV_NS_MODPEDAL "Pedalboard") == 0)
                {
                    isPedalboard = true;
                    break;
                }
            }
        }

        lilv_nodes_free(nodes);
    }

    if (! isPedalboard)
    {
        lilv_node_free(rdftypenode);
        lilv_world_free(w);
        return nullptr;
    }

    if (_get_pedal_info_ret != nullptr)
    {
        _clear_pedalboard_info(*_get_pedal_info_ret);
        _get_pedal_info_ret = nullptr;
    }

    memset(&info, 0, sizeof(PedalboardInfo));
    info.midi_separated_mode = true;

    // define the needed stuff
    LilvNode* const ingen_arc       = lilv_new_uri(w, LILV_NS_INGEN "arc");
    LilvNode* const ingen_block     = lilv_new_uri(w, LILV_NS_INGEN "block");
    LilvNode* const ingen_canvasX   = lilv_new_uri(w, LILV_NS_INGEN "canvasX");
    LilvNode* const ingen_canvasY   = lilv_new_uri(w, LILV_NS_INGEN "canvasY");
    LilvNode* const ingen_enabled   = lilv_new_uri(w, LILV_NS_INGEN "enabled");
    LilvNode* const ingen_head      = lilv_new_uri(w, LILV_NS_INGEN "head");
    LilvNode* const ingen_tail      = lilv_new_uri(w, LILV_NS_INGEN "tail");
    LilvNode* const ingen_value     = lilv_new_uri(w, LILV_NS_INGEN "value");
    LilvNode* const lv2_maximum     = lilv_new_uri(w, LV2_CORE__maximum);
    LilvNode* const lv2_minimum     = lilv_new_uri(w, LV2_CORE__minimum);
    LilvNode* const lv2_name        = lilv_new_uri(w, LV2_CORE__name);
    LilvNode* const lv2_port        = lilv_new_uri(w, LV2_CORE__port);
    LilvNode* const lv2_prototype   = lilv_new_uri(w, LV2_CORE__prototype);
    LilvNode* const midi_binding    = lilv_new_uri(w, LV2_MIDI__binding);
    LilvNode* const midi_channel    = lilv_new_uri(w, LV2_MIDI__channel);
    LilvNode* const midi_controlNum = lilv_new_uri(w, LV2_MIDI__controllerNumber);
    LilvNode* const modpedal_preset = lilv_new_uri(w, LILV_NS_MODPEDAL "preset");
    LilvNode* const modpedal_width  = lilv_new_uri(w, LILV_NS_MODPEDAL "width");
    LilvNode* const modpedal_height = lilv_new_uri(w, LILV_NS_MODPEDAL "height");
    LilvNode* const modpedal_version = lilv_new_uri(w, LILV_NS_MODPEDAL "version");
    LilvNode* const modpedal_instanceNumber = lilv_new_uri(w, LILV_NS_MODPEDAL "instanceNumber");

    // --------------------------------------------------------------------------------------------------------
    // uri node (ie, "this")

    const LilvNode* const urinode = lilv_plugin_get_uri(p);

    // --------------------------------------------------------------------------------------------------------
    // title

    if (LilvNode* const node = lilv_plugin_get_name(p))
    {
        if (const char* const name = lilv_node_as_string(node))
            info.title = name[0] != '\0' ? strdup(name) : kUntitled;
        else
            info.title = kUntitled;

        lilv_node_free(node);
    }
    else
    {
        info.title = kUntitled;
    }

    // --------------------------------------------------------------------------------------------------------
    // size

    if (LilvNodes* const widthnodes = lilv_plugin_get_value(p, modpedal_width))
    {
        if (LilvNodes* const heightnodes = lilv_plugin_get_value(p, modpedal_height))
        {
            info.width  = lilv_node_as_int(lilv_nodes_get_first(widthnodes));
            info.height = lilv_node_as_int(lilv_nodes_get_first(heightnodes));

            lilv_nodes_free(heightnodes);
        }

        lilv_nodes_free(widthnodes);
    }

    // --------------------------------------------------------------------------------------------------------
    // factory

    if (const LilvNode* const bundlenode = lilv_plugin_get_bundle_uri(p))
    {
        if (char* const bundleabspath = lilv_file_abspath(lilv_node_as_string(bundlenode)))
        {
            info.factory = is_factory_pedalboard(bundleabspath);
            free(bundleabspath);
        }
    }

    // --------------------------------------------------------------------------------------------------------
    // plugins

    if (LilvNodes* const blocks = lilv_plugin_get_value(p, ingen_block))
    {
        if (unsigned int count = lilv_nodes_size(blocks))
        {
            PedalboardPlugin* const plugs = new PedalboardPlugin[count+1];
            memset(plugs, 0, sizeof(PedalboardPlugin) * (count+1));

            count = 0;
            LILV_FOREACH(nodes, itblocks, blocks)
            {
                const LilvNode* const block = lilv_nodes_get(blocks, itblocks);

                if (LilvNode* const proto = lilv_world_get(w, block, lv2_prototype, nullptr))
                {
                    const char* const uri = lilv_node_as_uri(proto);
                    char* full_instance = lilv_file_uri_parse(lilv_node_as_string(block), nullptr);
                    char* instance;

                    if (strstr(full_instance, bundlepath) != nullptr)
                        instance = strdup(full_instance+(bundlepathsize+1));
                    else
                        instance = strdup(full_instance);

                    LilvNode* const enabled = lilv_world_get(w, block, ingen_enabled, nullptr);
                    LilvNode* const x       = lilv_world_get(w, block, ingen_canvasX, nullptr);
                    LilvNode* const y       = lilv_world_get(w, block, ingen_canvasY, nullptr);
                    LilvNode* const preset  = lilv_world_get(w, block, modpedal_preset, nullptr);
                    LilvNode* const instId  = lilv_world_get(w, block, modpedal_instanceNumber, nullptr);

                    PedalboardMidiControl bypassCC = { -1, 0, false, 0.0f, 1.0f };
                    PedalboardPluginPort* ports = nullptr;

                    if (LilvNodes* const portnodes = lilv_world_find_nodes(w, block, lv2_port, nullptr))
                    {
                        unsigned int portcount = lilv_nodes_size(portnodes);

                        ports = new PedalboardPluginPort[portcount+1];
                        memset(ports, 0, sizeof(PedalboardPluginPort) * (portcount+1));

                        const size_t full_instance_size = strlen(full_instance);

                        portcount = 0;
                        LILV_FOREACH(nodes, itport, portnodes)
                        {
                              const LilvNode* const portnode = lilv_nodes_get(portnodes, itport);

                              LilvNode* const portvalue = lilv_world_get(w, portnode, ingen_value, nullptr);

                              if (portvalue == nullptr)
                                  continue;

                              int8_t mchan = -1;
                              uint8_t mctrl = 0;
                              float minimum = 0.0f, maximum = 1.0f;
                              bool hasRanges = false;

                              if (LilvNode* const bind = lilv_world_get(w, portnode, midi_binding, nullptr))
                              {
                                  LilvNode* const bindChan = lilv_world_get(w, bind, midi_channel, nullptr);
                                  LilvNode* const bindCtrl = lilv_world_get(w, bind, midi_controlNum, nullptr);

                                  if (bindChan != nullptr && bindCtrl != nullptr)
                                  {
                                      const int mchantest = lilv_node_as_int(bindChan);
                                      const int mctrltest = lilv_node_as_int(bindCtrl);

                                      if (mchantest >= 0 && mchantest < 16 && mctrltest >= 0 && mctrltest < 255)
                                      {
                                          mchan = (int8_t)mchantest;
                                          mctrl = (uint8_t)mctrltest;

                                          LilvNode* const bindMin = lilv_world_get(w, bind, lv2_minimum, nullptr);
                                          LilvNode* const bindMax = lilv_world_get(w, bind, lv2_maximum, nullptr);

                                          if (bindMin != nullptr && bindMax != nullptr)
                                          {
                                              hasRanges = true;
                                              minimum = lilv_node_as_float(bindMin);
                                              maximum = lilv_node_as_float(bindMax);
                                          }

                                          lilv_node_free(bindMin);
                                          lilv_node_free(bindMax);
                                      }
                                  }

                                  lilv_node_free(bindCtrl);
                                  lilv_node_free(bindChan);
                                  lilv_node_free(bind);
                              }

                              char* portsymbol = lilv_file_uri_parse(lilv_node_as_string(portnode), nullptr);

                              if (strstr(portsymbol, full_instance) != nullptr)
                                  memmove(portsymbol, portsymbol+(full_instance_size+1), strlen(portsymbol)-full_instance_size);

                              if (strcmp(portsymbol, ":bypass") == 0)
                              {
                                  bypassCC.channel = mchan;
                                  bypassCC.control = mctrl;
                                  lilv_free(portsymbol);
                              }
                              else
                              {
                                  ports[portcount++] = {
                                      true,
                                      portsymbol,
                                      lilv_node_as_float(portvalue),
                                      { mchan, mctrl, hasRanges, minimum, maximum }
                                  };
                              }

                              lilv_node_free(portvalue);
                        }

                        lilv_nodes_free(portnodes);
                    }

                    plugs[count++] = {
                        true,
                        enabled != nullptr ? !lilv_node_as_bool(enabled) : true,
                        instId != nullptr ? lilv_node_as_int(instId) : -1,
                        instance,
                        strdup(uri),
                        bypassCC,
                        x != nullptr ? lilv_node_as_float(x) : 0.0f,
                        y != nullptr ? lilv_node_as_float(y) : 0.0f,
                        ports,
                        (preset != nullptr && !lilv_node_equals(preset, urinode)) ? strdup(lilv_node_as_uri(preset)) : nc
                    };

                    lilv_free(full_instance);
                    lilv_node_free(enabled);
                    lilv_node_free(x);
                    lilv_node_free(y);
                    lilv_node_free(proto);
                    lilv_node_free(preset);
                    lilv_node_free(instId);
                }
            }

            info.plugins = plugs;
        }

        lilv_nodes_free(blocks);
    }

    // --------------------------------------------------------------------------------------------------------
    // connections

    if (LilvNodes* const arcs = lilv_plugin_get_value(p, ingen_arc))
    {
        if (unsigned int count = lilv_nodes_size(arcs))
        {
            PedalboardConnection* conns = new PedalboardConnection[count+1];
            memset(conns, 0, sizeof(PedalboardConnection) * (count+1));

            count = 0;
            LILV_FOREACH(nodes, itarcs, arcs)
            {
                const LilvNode* const arc  = lilv_nodes_get(arcs, itarcs);

                LilvNode* const head = lilv_world_get(w, arc, ingen_head, nullptr);

                if (head == nullptr)
                    continue;

                LilvNode* const tail = lilv_world_get(w, arc, ingen_tail, nullptr);

                if (head == nullptr)
                {
                    lilv_node_free(head);
                    continue;
                }

                char* tailstr = lilv_file_uri_parse(lilv_node_as_string(tail), nullptr);
                char* headstr = lilv_file_uri_parse(lilv_node_as_string(head), nullptr);

                if (strstr(tailstr, bundlepath) != nullptr)
                    memmove(tailstr, tailstr+(bundlepathsize+1), strlen(tailstr)-bundlepathsize);

                if (strstr(headstr, bundlepath) != nullptr)
                    memmove(headstr, headstr+(bundlepathsize+1), strlen(headstr)-bundlepathsize);

                conns[count++] = {
                    true,
                    tailstr,
                    headstr
                };

                lilv_node_free(head);
                lilv_node_free(tail);
            }

            info.connections = conns;
        }

        lilv_nodes_free(arcs);
    }

    // --------------------------------------------------------------------------------------------------------
    // hardware ports and time info

    if (LilvNodes* const hwports = lilv_plugin_get_value(p, lv2_port))
    {
#if 0
        std::vector<std::string> handled_port_uris;
#endif
        std::vector<PedalboardHardwareMidiPort> midi_ins;
        std::vector<PedalboardHardwareMidiPort> midi_outs;

        LILV_FOREACH(nodes, ithwp, hwports)
        {
            const LilvNode* const hwport = lilv_nodes_get(hwports, ithwp);

            char* portsym = lilv_file_uri_parse(lilv_node_as_uri(hwport), nullptr);

            if (portsym == nullptr)
                continue;
            if (strstr(portsym, bundlepath) != nullptr)
                memmove(portsym, portsym+(bundlepathsize+1), strlen(portsym)-bundlepathsize);

            // check if we already handled this port
            if (strcmp(portsym, "control_in") == 0 || strcmp(portsym, "control_out") == 0)
            {
                lilv_free(portsym);
                continue;
            }

#if 0
            {
                const std::string portsym_s = portsym;
                if (std::find(handled_port_uris.begin(), handled_port_uris.end(), portsym_s) != handled_port_uris.end())
                {
                    lilv_free(portsym);
                    continue;
                }
                handled_port_uris.push_back(portsym_s);
            }
#endif
            // we began calling it legacy first, but separated makes more sense
            if (strcmp(portsym, "midi_legacy_mode") == 0 || strcmp(portsym, "midi_separated_mode") == 0)
            {
                if (LilvNode* const separated = lilv_world_get(w, hwport, ingen_value, nullptr))
                {
                    info.midi_separated_mode = lilv_node_as_int(separated) != 0;
                    lilv_node_free(separated);
                }
                lilv_free(portsym);
                continue;
            }

            if (strcmp(portsym, "midi_loopback") == 0)
            {
                if (LilvNode* const loopback = lilv_world_get(w, hwport, ingen_value, nullptr))
                {
                    info.midi_loopback = lilv_node_as_int(loopback) != 0;
                    lilv_node_free(loopback);
                }
                lilv_free(portsym);
                continue;
            }

            TimePortType timePortType;
            /**/ if (strcmp(portsym, ":bpb") == 0)
                timePortType = kTimePortTypeBeatsPerBar;
            else if (strcmp(portsym, ":bpm") == 0)
                timePortType = kTimePortTypeBeatsPerMinute;
            else if (strcmp(portsym, ":rolling") == 0)
                timePortType = kTimePortTypeRolling;
            else
                timePortType = kTimePortTypeNull;

            if (timePortType != kTimePortTypeNull)
            {
                if (LilvNode* const portvalue = lilv_world_get(w, hwport, ingen_value, nullptr))
                {
                    float value;
                    int8_t mchan = -1;
                    uint8_t mctrl = 0;
                    float minimum = 0.0f, maximum = 0.0f;
                    bool hasRanges = false;

                    if (LilvNode* const bind = lilv_world_get(w, hwport, midi_binding, nullptr))
                    {
                        LilvNode* const bindChan = lilv_world_get(w, bind, midi_channel, nullptr);
                        LilvNode* const bindCtrl = lilv_world_get(w, bind, midi_controlNum, nullptr);

                        if (bindChan != nullptr && bindCtrl != nullptr)
                        {
                            const int mchantest = lilv_node_as_int(bindChan);
                            const int mctrltest = lilv_node_as_int(bindCtrl);

                            if (mchantest >= 0 && mchantest < 16 && mctrltest >= 0 && mctrltest < 255)
                            {
                                mchan = (int8_t)mchantest;
                                mctrl = (uint8_t)mctrltest;

                                LilvNode* const bindMin = lilv_world_get(w, bind, lv2_minimum, nullptr);
                                LilvNode* const bindMax = lilv_world_get(w, bind, lv2_maximum, nullptr);

                                if (bindMin != nullptr && bindMax != nullptr)
                                {
                                    hasRanges = true;
                                    minimum = lilv_node_as_float(bindMin);
                                    maximum = lilv_node_as_float(bindMax);
                                }

                                lilv_node_free(bindMin);
                                lilv_node_free(bindMax);
                            }
                        }

                        lilv_node_free(bindCtrl);
                        lilv_node_free(bindChan);
                        lilv_node_free(bind);
                    }

                    switch (timePortType)
                    {
                    case kTimePortTypeNull:
                        break;

                    case kTimePortTypeBeatsPerBar:
                        value = lilv_node_as_float(portvalue);
                        if (value >= 1.0f && value <= 16.0f)
                        {
                            info.timeInfo.bpb = value;
                            info.timeInfo.bpbCC = { mchan, mctrl, hasRanges, minimum, maximum };
                            info.timeInfo.available |= kPedalboardTimeAvailableBPB;
                        }
                        break;

                    case kTimePortTypeBeatsPerMinute:
                        value = lilv_node_as_float(portvalue);
                        if (value >= 20.0f && value <= 280.0f)
                        {
                            info.timeInfo.bpm = value;
                            info.timeInfo.bpmCC = { mchan, mctrl, hasRanges, minimum, maximum };
                            info.timeInfo.available |= kPedalboardTimeAvailableBPM;
                        }
                        break;

                    case kTimePortTypeRolling:
                        info.timeInfo.rolling = lilv_node_as_int(portvalue) != 0;
                        info.timeInfo.rollingCC = { mchan, mctrl, hasRanges, minimum, maximum };
                        info.timeInfo.available |= kPedalboardTimeAvailableRolling;
                        break;
                    }

                    lilv_node_free(portvalue);
                }

                lilv_free(portsym);
                continue;
            }

            // get types
            if (LilvNodes* const port_types = lilv_world_find_nodes(w, hwport, rdftypenode, NULL))
            {
                PortDirection direction = kPortDirectionNull;
                PortType portType = kPortTypeNull;

                LILV_FOREACH(nodes, itptyp, port_types)
                {
                    const LilvNode* const ptyp = lilv_nodes_get(port_types, itptyp);

                    if (const char* port_type_uri = lilv_node_as_uri(ptyp))
                    {
                        if (strcmp(port_type_uri, MOD__CVPort) == 0)
                        {
                            portType = kPortTypeCV;
                        }
                        else if (strncmp(port_type_uri, "http://lv2plug.in/ns/", 21) == 0)
                        {
                            port_type_uri += 21; // http://lv2plug.in/ns/

                            /**/ if (strcmp(port_type_uri, "lv2core#InputPort") == 0)
                                direction = kPortDirectionInput;
                            else if (strcmp(port_type_uri, "lv2core#OutputPort") == 0)
                                direction = kPortDirectionOutput;
                            else if (strcmp(port_type_uri, "lv2core#AudioPort") == 0)
                                portType = kPortTypeAudio;
                            else if (strcmp(port_type_uri, "lv2core#CVPort") == 0)
                                portType = kPortTypeCV;
                            else if (strcmp(port_type_uri, "ext/atom#AtomPort") == 0)
                                portType = kPortTypeMIDI;
                        }
                    }
                }

                if (direction == kPortDirectionNull || portType == kPortTypeNull)
                {
                    lilv_free(portsym);
                    continue;
                }

                switch (portType)
                {
                case kPortTypeNull:
                case kPortTypeControl:
                    break;

                case kPortTypeAudio:
                    if (direction == kPortDirectionInput)
                        ++info.hardware.audio_ins;
                    else
                        ++info.hardware.audio_outs;
                    break;

                case kPortTypeMIDI:
                    if (direction == kPortDirectionInput)
                    {
                        if (strcmp(portsym, "serial_midi_in") == 0)
                        {
                            info.hardware.serial_midi_in = true;
                        }
                        else
                        {
                            LilvNode* const hwportname = lilv_world_get(w, hwport, lv2_name, nullptr);

                            PedalboardHardwareMidiPort mport = {
                                true,
                                portsym,
                                nc,
                            };

                            if (hwportname != nullptr && lilv_node_is_string(hwportname))
                                mport.name = strdup(lilv_node_as_string(hwportname));

                            lilv_node_free(hwportname);

                            portsym = nullptr;
                            midi_ins.push_back(mport);
                        }
                    }
                    else
                    {
                        if (strcmp(portsym, "serial_midi_out") == 0)
                        {
                            info.hardware.serial_midi_out = true;
                        }
                        else
                        {
                            LilvNode* const hwportname = lilv_world_get(w, hwport, lv2_name, nullptr);

                            PedalboardHardwareMidiPort mport = {
                                true,
                                portsym,
                                nc,
                            };

                            if (hwportname != nullptr && lilv_node_is_string(hwportname))
                                mport.name = strdup(lilv_node_as_string(hwportname));

                            lilv_node_free(hwportname);

                            portsym = nullptr;
                            midi_outs.push_back(mport);
                        }
                    }
                    break;

                case kPortTypeCV:
                    if (direction == kPortDirectionInput)
                        ++info.hardware.cv_ins;
                    else
                        ++info.hardware.cv_outs;
                    break;
                }

                lilv_free(portsym);
                lilv_nodes_free(port_types);
            }
        }

        if (size_t count = midi_ins.size())
        {
            PedalboardHardwareMidiPort* mins = new PedalboardHardwareMidiPort[count+1];

            count = 0;
            for (const PedalboardHardwareMidiPort& min : midi_ins)
                mins[count++] = min;

            memset(&mins[count], 0, sizeof(PedalboardHardwareMidiPort));

            info.hardware.midi_ins = mins;
        }

        if (size_t count = midi_outs.size())
        {
            PedalboardHardwareMidiPort* mouts = new PedalboardHardwareMidiPort[count+1];

            count = 0;
            for (const PedalboardHardwareMidiPort& mout : midi_outs)
                mouts[count++] = mout;

            memset(&mouts[count], 0, sizeof(PedalboardHardwareMidiPort));

            info.hardware.midi_outs = mouts;
        }

        lilv_nodes_free(hwports);
    }

    // --------------------------------------------------------------------------------------------------------
    // version

    if (LilvNodes* const nodes = lilv_plugin_get_value(p, modpedal_version))
    {
        info.version = lilv_node_as_int(lilv_nodes_get_first(nodes));

        lilv_nodes_free(nodes);
    }

    // --------------------------------------------------------------------------------------------------------

    lilv_node_free(ingen_arc);
    lilv_node_free(ingen_block);
    lilv_node_free(ingen_canvasX);
    lilv_node_free(ingen_canvasY);
    lilv_node_free(ingen_enabled);
    lilv_node_free(ingen_head);
    lilv_node_free(ingen_tail);
    lilv_node_free(ingen_value);
    lilv_node_free(lv2_maximum);
    lilv_node_free(lv2_minimum);
    lilv_node_free(lv2_name);
    lilv_node_free(lv2_port);
    lilv_node_free(lv2_prototype);
    lilv_node_free(midi_binding);
    lilv_node_free(midi_channel);
    lilv_node_free(midi_controlNum);
    lilv_node_free(modpedal_preset);
    lilv_node_free(modpedal_width);
    lilv_node_free(modpedal_height);
    lilv_node_free(modpedal_version);
    lilv_node_free(modpedal_instanceNumber);
    lilv_node_free(rdftypenode);
    lilv_world_free(w);

    _get_pedal_info_ret = &info;
    return &info;
}

int* get_pedalboard_size(const char* const bundle)
{
    size_t bundlepathsize;
    const char* const bundlepath = _get_safe_bundlepath(bundle, bundlepathsize);

    if (bundlepath == nullptr)
        return nullptr;

    LilvWorld* const w = lilv_world_new();
    LilvNode*  const b = lilv_new_file_uri(w, nullptr, bundlepath);
    lilv_world_load_bundle(w, b);
    lilv_node_free(b);

    const LilvPlugins* const plugins = lilv_world_get_all_plugins(w);

    if (lilv_plugins_size(plugins) != 1)
    {
        lilv_world_free(w);
        return nullptr;
    }

    const LilvPlugin* p = nullptr;

    LILV_FOREACH(plugins, itpls, plugins) {
        p = lilv_plugins_get(plugins, itpls);
        break;
    }

    if (p == nullptr)
    {
        lilv_world_free(w);
        return nullptr;
    }

    LilvNode* const widthnode  = lilv_new_uri(w, LILV_NS_MODPEDAL "width");
    LilvNode* const heightnode = lilv_new_uri(w, LILV_NS_MODPEDAL "height");

    LilvNodes* const widthnodes  = lilv_plugin_get_value(p, widthnode);
    LilvNodes* const heightnodes = lilv_plugin_get_value(p, heightnode);

    if (widthnodes == nullptr || heightnodes == nullptr)
    {
        lilv_nodes_free(widthnodes);
        lilv_nodes_free(heightnodes);
        lilv_node_free(widthnode);
        lilv_node_free(heightnode);
        lilv_world_free(w);
        return nullptr;
    }

    static int size[2];
    size[0] = lilv_node_as_int(lilv_nodes_get_first(widthnodes));
    size[1] = lilv_node_as_int(lilv_nodes_get_first(heightnodes));

    lilv_nodes_free(widthnodes);
    lilv_nodes_free(heightnodes);
    lilv_node_free(widthnode);
    lilv_node_free(heightnode);
    lilv_world_free(w);

    return size;
}

const PedalboardPluginValues* get_pedalboard_plugin_values(const char* bundle)
{
    // NOTE: most of this code is duplicated from get_pedalboard_info

    size_t bundlepathsize;
    const char* const bundlepath = _get_safe_bundlepath(bundle, bundlepathsize);

    if (bundlepath == nullptr)
        return nullptr;

    LilvWorld* const w = lilv_world_new();
#ifdef HAVE_NEW_LILV
    lilv_world_load_specifications(w);
    lilv_world_load_plugin_classes(w);
#endif

    LilvNode* const b = lilv_new_file_uri(w, nullptr, bundlepath);
    lilv_world_load_bundle(w, b);
    lilv_node_free(b);

    const LilvPlugins* const plugins = lilv_world_get_all_plugins(w);

    if (lilv_plugins_size(plugins) != 1)
    {
        lilv_world_free(w);
        return nullptr;
    }

    const LilvPlugin* p = nullptr;

    LILV_FOREACH(plugins, itpls, plugins) {
        p = lilv_plugins_get(plugins, itpls);
        break;
    }

    if (p == nullptr)
    {
        lilv_world_free(w);
        return nullptr;
    }

    bool isPedalboard = false;
    LilvNode* const rdftypenode = lilv_new_uri(w, LILV_NS_RDF "type");

    if (LilvNodes* const nodes = lilv_plugin_get_value(p, rdftypenode))
    {
        LILV_FOREACH(nodes, it, nodes)
        {
            const LilvNode* const node = lilv_nodes_get(nodes, it);

            if (const char* const nodestr = lilv_node_as_string(node))
            {
                if (strcmp(nodestr, LILV_NS_MODPEDAL "Pedalboard") == 0)
                {
                    isPedalboard = true;
                    break;
                }
            }
        }

        lilv_nodes_free(nodes);
    }

    if (! isPedalboard)
    {
        lilv_node_free(rdftypenode);
        lilv_world_free(w);
        return nullptr;
    }

    // --------------------------------------------------------------------------------------------------------
    // plugins

    LilvNode* const ingen_block = lilv_new_uri(w, LILV_NS_INGEN "block");
    LilvNodes* const blocks = lilv_plugin_get_value(p, ingen_block);

    if (blocks == nullptr)
    {
        lilv_node_free(ingen_block);
        lilv_node_free(rdftypenode);
        lilv_world_free(w);
        return nullptr;
    }

    unsigned int blockCount = lilv_nodes_size(blocks);

    if (blockCount == 0)
    {
        lilv_nodes_free(blocks);
        lilv_node_free(ingen_block);
        lilv_node_free(rdftypenode);
        lilv_world_free(w);
        return nullptr;
    }

    LilvNode* const ingen_enabled   = lilv_new_uri(w, LILV_NS_INGEN "enabled");
    LilvNode* const ingen_value     = lilv_new_uri(w, LILV_NS_INGEN "value");
    LilvNode* const lv2_port        = lilv_new_uri(w, LV2_CORE__port);
    LilvNode* const modpedal_preset = lilv_new_uri(w, LILV_NS_MODPEDAL "preset");

    // --------------------------------------------------------------------------------------------------------
    // uri node (ie, "this")

    const LilvNode* const urinode = lilv_plugin_get_uri(p);

    // --------------------------------------------------------------------------------------------------------
    // ready to parse

    _clear_pedalboard_plugin_values();

    PedalboardPluginValues* const plugs = new PedalboardPluginValues[blockCount+1];
    memset(plugs, 0, sizeof(PedalboardPluginValues) * (blockCount+1));

    blockCount = 0;
    LILV_FOREACH(nodes, itblocks, blocks)
    {
        const LilvNode* const block = lilv_nodes_get(blocks, itblocks);
        char* full_instance = lilv_file_uri_parse(lilv_node_as_string(block), nullptr);
        char* instance;

        if (strstr(full_instance, bundlepath) != nullptr)
            instance = strdup(full_instance+(bundlepathsize+1));
        else
            instance = strdup(full_instance);

        LilvNode* const enabled = lilv_world_get(w, block, ingen_enabled, nullptr);
        LilvNode* const preset  = lilv_world_get(w, block, modpedal_preset, nullptr);

        StatePortValue* ports = nullptr;

        if (LilvNodes* const portnodes = lilv_world_find_nodes(w, block, lv2_port, nullptr))
        {
            unsigned int portCount = lilv_nodes_size(portnodes);

            ports = new StatePortValue[portCount+1];
            memset(ports, 0, sizeof(StatePortValue) * (portCount+1));

            const size_t full_instance_size = strlen(full_instance);

            portCount = 0;
            LILV_FOREACH(nodes, itport, portnodes)
            {
                  const LilvNode* const portnode = lilv_nodes_get(portnodes, itport);

                  LilvNode* const portvalue = lilv_world_get(w, portnode, ingen_value, nullptr);

                  if (portvalue == nullptr)
                      continue;

                  char* portsymbol = lilv_file_uri_parse(lilv_node_as_string(portnode), nullptr);

                  if (strstr(portsymbol, full_instance) != nullptr)
                      memmove(portsymbol, portsymbol+(full_instance_size+1), strlen(portsymbol)-full_instance_size);

                  if (strcmp(portsymbol, ":bypass") == 0)
                  {
                      lilv_free(portsymbol);
                  }
                  else
                  {
                      ports[portCount++] = {
                          true,
                          portsymbol,
                          lilv_node_as_float(portvalue)
                      };
                  }

                  lilv_node_free(portvalue);
            }

            lilv_nodes_free(portnodes);
        }

        plugs[blockCount++] = {
            true,
            enabled != nullptr ? !lilv_node_as_bool(enabled) : true,
            instance,
            (preset != nullptr && !lilv_node_equals(preset, urinode)) ? strdup(lilv_node_as_uri(preset)) : nc,
            ports,
        };

        lilv_free(full_instance);
        lilv_node_free(enabled);
        lilv_node_free(preset);
    }

    lilv_nodes_free(blocks);
    lilv_node_free(ingen_block);
    lilv_node_free(ingen_enabled);
    lilv_node_free(ingen_value);
    lilv_node_free(lv2_port);
    lilv_node_free(modpedal_preset);
    lilv_node_free(rdftypenode);
    lilv_world_free(w);

    _get_pedal_values_ret = plugs;

    return plugs;
}

void reset_get_all_pedalboards_cache(int ptype)
{
    if (ptype == kPedalboardInfoUserOnly || ptype == kPedalboardInfoBoth)
    {
        _clear_pedalboards(_get_pedals_mini_ret);
        _get_pedals_mini_ret = nullptr;
    }

    if (ptype == kPedalboardInfoUserOnly || ptype == kPedalboardInfoBoth)
    {
        _clear_pedalboards(FACTORYINFO);
        FACTORYINFO = nullptr;
    }
}

// --------------------------------------------------------------------------------------------------------

#ifdef HAVE_NEW_LILV
// note: these ids must match the ones on the mapping (see 'kMapping')
static const uint32_t k_urid_null        = 0;
static const uint32_t k_urid_atom_bool   = 1;
static const uint32_t k_urid_atom_int    = 2;
static const uint32_t k_urid_atom_long   = 3;
static const uint32_t k_urid_atom_float  = 4;
static const uint32_t k_urid_atom_double = 5;

static LV2_URID lv2_urid_map(LV2_URID_Map_Handle, const char* const uri_)
{
    if (uri_ == nullptr || uri_[0] == '\0')
        return k_urid_null;

    static std::vector<std::string> kMapping = {
        LV2_ATOM__Bool,
        LV2_ATOM__Int,
        LV2_ATOM__Long,
        LV2_ATOM__Float,
        LV2_ATOM__Double,
    };

    const std::string uri(uri_);

    LV2_URID urid = 1;
    for (const std::string& uri2 : kMapping)
    {
        if (uri2 == uri)
            return urid;
        ++urid;
    }

    kMapping.push_back(uri);
    return urid;
}

static void lilv_set_port_value(const char* const portSymbol, void* const userData,
                                const void* const value, const uint32_t size, const uint32_t type)
{
    std::vector<StatePortValue>* const values = (std::vector<StatePortValue>*)userData;

    switch (type)
    {
    case k_urid_atom_bool:
    case k_urid_atom_int:
        if (size == sizeof(int32_t))
        {
            int32_t ivalue = *(const int32_t*)value;
            values->push_back({ true, strdup(portSymbol), (float)ivalue });
            return;
        }
        break;

    case k_urid_atom_long:
        if (size == sizeof(int64_t))
        {
            int64_t ivalue = *(const int64_t*)value;
            values->push_back({ true, strdup(portSymbol), (float)ivalue });
            return;
        }
        break;

    case k_urid_atom_float:
        if (size == sizeof(float))
        {
            float fvalue = *(const float*)value;
            values->push_back({ true, strdup(portSymbol), fvalue });
            return;
        }
        break;

    case k_urid_atom_double:
        if (size == sizeof(double))
        {
            double dvalue = *(const double*)value;
            values->push_back({ true, strdup(portSymbol), (float)dvalue });
            return;
        }
        break;
    }

    printf("lilv_set_port_value called with unknown type: %u %u\n", type, size);
}
#endif

const StatePortValue* get_state_port_values(const char* const state)
{
#ifdef HAVE_NEW_LILV
    static LV2_URID_Map uridMap = {
        (void*)0x1, // non-null
        lv2_urid_map
    };

    LilvWorld* const w = W;

    setenv("LILV_STATE_SKIP_PROPERTIES", "2", 1);

    LilvState* const lstate = lilv_state_new_from_string(w, &uridMap, state);

    unsetenv("LILV_STATE_SKIP_PROPERTIES");

    if (lstate != nullptr)
    {
        std::vector<StatePortValue> values;
        lilv_state_emit_port_values(lstate, lilv_set_port_value, &values);
        lilv_state_free(lstate);

        if (size_t count = values.size())
        {
            _clear_state_values();

            _get_state_values_ret = new StatePortValue[count+1];

            count = 0;
            for (const StatePortValue& v : values)
                _get_state_values_ret[count++] = v;

            memset(&_get_state_values_ret[count], 0, sizeof(StatePortValue));

            return _get_state_values_ret;
        }
    }
#endif

    return nullptr;

#ifndef HAVE_NEW_LILV
    // unused
    (void)state;
#endif
}

// --------------------------------------------------------------------------------------------------------

const char* const* list_plugins_in_bundle(const char* bundle)
{
    size_t bundlepathsize;
    const char* const bundlepath = _get_safe_bundlepath(bundle, bundlepathsize);

    if (bundlepath == nullptr)
        return nullptr;

    LilvWorld* const w = lilv_world_new();
    LilvNode*  const b = lilv_new_file_uri(w, nullptr, bundlepath);
    lilv_world_load_bundle(w, b);
    lilv_node_free(b);

    const LilvPlugins* const plugins = lilv_world_get_all_plugins(w);

    if (lilv_plugins_size(plugins) == 0)
    {
        lilv_world_free(w);
        return nullptr;
    }

    const LilvPlugin* p;
    std::vector<const char*> pluginURIs;

    LILV_FOREACH(plugins, itpls, plugins)
    {
        p = lilv_plugins_get(plugins, itpls);
        pluginURIs.push_back(strdup(lilv_node_as_uri(lilv_plugin_get_uri(p))));
    }

    lilv_world_free(w);

    if (size_t count = pluginURIs.size())
    {
        if (_add_remove_bundles_ret != nullptr)
        {
            for (int i=0; _add_remove_bundles_ret[i] != nullptr; ++i)
                free((void*)_add_remove_bundles_ret[i]);
            delete[] _add_remove_bundles_ret;
        }

        _add_remove_bundles_ret = new const char*[count+1];

        count = 0;
        for (const char* uri : pluginURIs)
            _add_remove_bundles_ret[count++] = uri;

        _add_remove_bundles_ret[count] = nullptr;

        return _add_remove_bundles_ret;
    }

    return nullptr;
}

const char* file_uri_parse(const char* const fileuri)
{
    if (_file_uri_parse_ret)
        free(_file_uri_parse_ret);

    _file_uri_parse_ret = lilv_file_abspath(fileuri);

    return _file_uri_parse_ret != nullptr ? _file_uri_parse_ret : nc;
}

void set_cpu_affinity(const int cpu)
{
#ifdef __linux__
     printf("NOTE: Running pinned to core #%d\n", cpu+1);
     cpu_set_t cpuset;
     CPU_ZERO(&cpuset);
     CPU_SET(cpu, &cpuset);
     sched_setaffinity(0, sizeof(cpuset), &cpuset);
#endif
}

// --------------------------------------------------------------------------------------------------------
