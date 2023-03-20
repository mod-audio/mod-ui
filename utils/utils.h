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

#ifndef MOD_UTILS_H_INCLUDED
#define MOD_UTILS_H_INCLUDED

#ifdef __cplusplus
#include <cstdint>
extern "C" {
#else
#include <stdint.h>
#endif

#define MOD_API __attribute__ ((visibility("default")))

typedef enum {
    kPluginLicenseNonCommercial = 0,
    kPluginLicenseTrial = -1,
    kPluginLicensePaid = 1,
} PluginLicenseType;

typedef enum {
    kPluginIONull = 0,
    kPluginIOAudioMono = 1,
    kPluginIOAudioStereo = 2,
    kPluginIOInstrument = 3,
    kPluginIOMIDI = 4,
} PluginIOType;

typedef enum {
    kPedalboardInfoUserOnly = 0,
    kPedalboardInfoFactoryOnly = 1,
    kPedalboardInfoBoth = 2,
} PedalboardInfoType;

typedef struct {
    const char* name;
    const char* homepage;
    const char* email;
} PluginAuthor;

typedef struct {
    bool valid;
    unsigned int index;
    const char* name;
    const char* symbol;
} PluginGUIPort;

typedef struct {
    const char* resourcesDirectory;
    const char* iconTemplate;
    const char* settingsTemplate;
    const char* javascript;
    const char* stylesheet;
    const char* screenshot;
    const char* thumbnail;
    const char* discussionURL;
    const char* documentation;
    const char* brand;
    const char* label;
    const char* model;
    const char* panel;
    const char* color;
    const char* knob;
    PluginGUIPort* ports;
    const char* const* monitoredOutputs;
} PluginGUI;

typedef struct {
    const char* resourcesDirectory;
    const char* screenshot;
    const char* thumbnail;
} PluginGUI_Mini;

typedef struct {
    float min;
    float max;
    float def;
} PluginPortRanges;

typedef struct {
    const char* label;
    const char* render;
    const char* symbol;
    bool _custom; // internal
} PluginPortUnits;

typedef struct {
    bool valid;
    float value;
    const char* label;
} PluginPortScalePoint;

typedef struct {
    bool valid;
    unsigned int index;
    const char* name;
    const char* symbol;
    PluginPortRanges ranges;
    PluginPortUnits units;
    const char* comment;
    const char* designation;
    const char* const* properties;
    int rangeSteps;
    const PluginPortScalePoint* scalePoints;
    const char* shortName;
} PluginPort;

typedef struct {
    PluginPort* input;
    PluginPort* output;
} PluginPortsI;

typedef struct {
    PluginPortsI audio;
    PluginPortsI control;
    PluginPortsI cv;
    PluginPortsI midi;
} PluginPorts;

typedef struct {
    int64_t min;
    int64_t max;
    int64_t def;
} PluginLongParameterRanges;

typedef struct {
    char type;
    union {
        PluginPortRanges f;
        PluginLongParameterRanges l;
        const char* s;
    };
} PluginParameterRanges;

typedef struct {
    bool valid;
    bool readable;
    bool writable;
    const char* uri;
    const char* label;
    const char* type;
    // for regular controls
    PluginParameterRanges ranges;
    PluginPortUnits units;
    const char* comment;
    const char* shortName;
    // for path stuff
    const char* const* fileTypes;
    const char* const* supportedExtensions;
} PluginParameter;

typedef struct {
    bool valid;
    const char* uri;
    const char* label;
    const char* path;
} PluginPreset;

typedef struct {
    bool valid;
    const char* uri;
    const char* name;
    const char* binary;
    const char* brand;
    const char* label;
    const char* license;
    const char* comment;
    const char* buildEnvironment;
    const char* const* category;
    int microVersion;
    int minorVersion;
    int release;
    int builder;
    int licensed; // PluginLicenseType
    int iotype; // PluginIOType
    bool hasExternalUI;
    const char* version;
    const char* stability;
    PluginAuthor author;
    const char* const* bundles;
    PluginGUI gui;
    PluginPorts ports;
    const PluginParameter* parameters;
    const PluginPreset* presets;
} PluginInfo;

typedef struct {
    int licensed; // PluginLicenseType
    const PluginPreset* presets;
} NonCachedPluginInfo;

typedef struct {
    const char* uri;
    const char* name;
    const char* brand;
    const char* label;
    const char* comment;
    const char* buildEnvironment;
    const char* const* category;
    int microVersion;
    int minorVersion;
    int release;
    int builder;
    int licensed; // PluginLicenseType
    int iotype; // PluginIOType
    PluginGUI_Mini gui;
} PluginInfo_Mini;

typedef struct {
    const PluginPort* controlInputs;
    const char* const* monitoredOutputs;
    const PluginParameter* parameters;
    const char* buildEnvironment;
    int microVersion;
    int minorVersion;
    int release;
    int builder;
} PluginInfo_Essentials;

typedef struct {
    int8_t channel;
    uint8_t control;
    // ranges added in v1.2, flag needed for old format compatibility
    bool hasRanges;
    float minimum;
    float maximum;
} PedalboardMidiControl;

typedef struct {
    bool valid;
    const char* symbol;
    float value;
    PedalboardMidiControl midiCC;
} PedalboardPluginPort;

typedef struct {
    bool valid;
    bool bypassed;
    int instanceNumber;
    const char* instance;
    const char* uri;
    PedalboardMidiControl bypassCC;
    float x;
    float y;
    const PedalboardPluginPort* ports;
    const char* preset;
} PedalboardPlugin;

typedef struct {
    bool valid;
    const char* source;
    const char* target;
} PedalboardConnection;

typedef struct {
    bool valid;
    const char* symbol;
    const char* name;
} PedalboardHardwareMidiPort;

typedef struct {
    unsigned int audio_ins;
    unsigned int audio_outs;
    unsigned int cv_ins;
    unsigned int cv_outs;
    const PedalboardHardwareMidiPort* midi_ins;
    const PedalboardHardwareMidiPort* midi_outs;
    bool serial_midi_in;
    bool serial_midi_out;
    bool midi_merger_out;
    bool midi_broadcaster_in;
} PedalboardHardware;

typedef enum {
    kPedalboardTimeAvailableBPB     = 0x1,
    kPedalboardTimeAvailableBPM     = 0x2,
    kPedalboardTimeAvailableRolling = 0x4,
} PedalboardTimeInfoAvailableBits;

typedef struct {
    unsigned int available;
    float bpb;
    PedalboardMidiControl bpbCC;
    float bpm;
    PedalboardMidiControl bpmCC;
    bool rolling;
    PedalboardMidiControl rollingCC;
} PedalboardTimeInfo;

typedef struct {
    const char* title;
    int width, height;
    bool factory;
    bool midi_separated_mode;
    bool midi_loopback;
    const PedalboardPlugin* plugins;
    const PedalboardConnection* connections;
    PedalboardHardware hardware;
    PedalboardTimeInfo timeInfo;
    unsigned int version;
} PedalboardInfo;

typedef struct {
    bool broken;
    bool factory;
    bool hasTrialPlugins;
    const char* uri;
    const char* bundle;
    const char* title;
    unsigned int version;
} PedalboardInfo_Mini;

typedef struct {
    bool valid;
    const char* symbol;
    float value;
} StatePortValue;

typedef struct {
    bool valid;
    bool bypassed;
    const char* instance;
    const char* preset;
    const StatePortValue* ports;
} PedalboardPluginValues;

typedef struct {
    float cpuLoad;
    unsigned xruns;
    bool rolling;
    double bpb;
    double bpm;
} JackData;

typedef void (*JackBufSizeChanged)(unsigned bufsize);
typedef void (*JackPortAppeared)(const char* name, bool isOutput);
typedef void (*JackPortDeleted)(const char* name);
typedef void (*TrueBypassStateChanged)(bool left, bool right);
typedef void (*CvExpInputModeChanged)(bool expPedalMode);

// initialize
MOD_API void init(void);

// cleanup, cannot be used afterwards
MOD_API void cleanup(void);

// check if a bundle is loaded in our lilv world
MOD_API bool is_bundle_loaded(const char* bundle);

// add a bundle to our lilv world
// returns uri list of added plugins (null for none)
MOD_API const char* const* add_bundle_to_lilv_world(const char* bundle);

// remove a bundle from our lilv world
// returns uri list of removed plugins (null for none)
MOD_API const char* const* remove_bundle_from_lilv_world(const char* bundle, const char* resource);

// get list of all available plugins
MOD_API const char* const* get_plugin_list(void);

// get all available plugins
// this triggers short scanning of all plugins
MOD_API const PluginInfo_Mini* const* get_all_plugins(void);

// get a specific plugin
// NOTE: may return null
MOD_API const PluginInfo* get_plugin_info(const char* uri);

// get a specific plugin (non-cached specific info)
// NOTE: may return null
MOD_API const NonCachedPluginInfo* get_non_cached_plugin_info(const char* uri);

// get a specific plugin's modgui
// NOTE: may return null
MOD_API const PluginGUI* get_plugin_gui(const char* uri);

// get a specific plugin's modgui (mini)
// NOTE: may return null
MOD_API const PluginGUI_Mini* get_plugin_gui_mini(const char* uri);

// get all control inputs for a specific plugin
MOD_API const PluginPort* get_plugin_control_inputs(const char* uri);

// get essential plugin info for host control (control inputs, monitored outputs, parameters and build environment)
MOD_API const PluginInfo_Essentials* get_plugin_info_essentials(const char* uri);

// check if a plugin preset is valid (must exist)
MOD_API bool is_plugin_preset_valid(const char* plugin, const char* preset);

// trigger a preset rescan for a plugin the next time it's loaded
MOD_API void rescan_plugin_presets(const char* uri);

// get all available pedalboards (ie, plugins with pedalboard type)
MOD_API const PedalboardInfo_Mini* const* get_all_pedalboards(int ptype);

// get all currently "broken" pedalboards (ie, pedalboards which contain unavailable plugins)
MOD_API const char* const* get_broken_pedalboards(void);

// Get a specific pedalboard
// NOTE: may return null
MOD_API const PedalboardInfo* get_pedalboard_info(const char* bundle);

// Get the size of a specific pedalboard
// Returns a 2-size array with width and height
// NOTE: may return null
MOD_API int* get_pedalboard_size(const char* bundle);

// Get plugin port values of a pedalboard
// NOTE: may return null
MOD_API const PedalboardPluginValues* get_pedalboard_plugin_values(const char* bundle);

// Reset pedalboards related cache
// Needed when plugins are added, as previous "broken" PBs might have been fixed with the change.
MOD_API void reset_get_all_pedalboards_cache(int ptype);

// Get port values from a plugin state
MOD_API const StatePortValue* get_state_port_values(const char* state);

// list plugins present in a single bundle
MOD_API const char* const* list_plugins_in_bundle(const char* bundle);

// Convert a file URI to a local path string.
MOD_API const char* file_uri_parse(const char* fileuri);

// helper utilities
MOD_API void set_cpu_affinity(int cpu);

// jack stuff
MOD_API bool init_jack(void);
MOD_API void close_jack(void);
MOD_API JackData* get_jack_data(bool withTransport);
MOD_API unsigned get_jack_buffer_size(void);
MOD_API unsigned set_jack_buffer_size(unsigned size);
MOD_API float get_jack_sample_rate(void);
MOD_API const char* get_jack_port_alias(const char* portname);
MOD_API const char* const* get_jack_hardware_ports(const bool isAudio, bool isOutput);
MOD_API bool has_midi_beat_clock_sender_port(void);
MOD_API bool has_serial_midi_input_port(void);
MOD_API bool has_serial_midi_output_port(void);
MOD_API bool has_midi_merger_output_port(void);
MOD_API bool has_midi_broadcaster_input_port(void);
MOD_API bool has_duox_split_spdif(void);
MOD_API bool connect_jack_ports(const char* port1, const char* port2);
MOD_API bool connect_jack_midi_output_ports(const char* port);
MOD_API bool disconnect_jack_ports(const char* port1, const char* port2);
MOD_API bool disconnect_all_jack_ports(const char* port);
MOD_API void reset_xruns(void);

// alsa stuff
MOD_API void init_bypass(void);
MOD_API bool get_truebypass_value(bool right);
MOD_API bool set_truebypass_value(bool right, bool bypassed);
MOD_API float get_master_volume(bool right);

// callbacks
MOD_API void set_util_callbacks(JackBufSizeChanged bufSizeChanged,
                                JackPortAppeared portAppeared,
                                JackPortDeleted portDeleted,
                                TrueBypassStateChanged trueBypassChanged);

// special case until HMI<->system comm is not in place yet
MOD_API void set_extra_util_callbacks(CvExpInputModeChanged cvExpInputModeChanged);

#ifdef __cplusplus
} // extern "C"
#endif

#endif // MOD_UTILS_H_INCLUDED
