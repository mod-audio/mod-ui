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

#ifndef MOD_UTILS_H_INCLUDED
#define MOD_UTILS_H_INCLUDED

#ifdef __cplusplus
extern "C" {
#endif

#define MOD_API __attribute__ ((visibility("default")))

typedef struct {
    const char* name;
    const char* homepage;
    const char* email;
} PluginAuthor;

typedef struct {
    int index;
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
    const char* brand;
    const char* label;
    const char* model;
    const char* panel;
    const char* color;
    const char* knob;
    const PluginGUIPort* ports;
} PluginGUI;

typedef struct {
    float min;
    float max;
    float def;
} PluginPortRanges;

typedef struct {
    const char* label;
    const char* render;
    const char* symbol;
} PluginPortUnits;

typedef struct {
    float value;
    const char* label;
} PluginPortScalePoint;

typedef struct {
    const char* name;
    const char* symbol;
    PluginPortRanges ranges;
    PluginPortUnits units;
    const char* designation;
    const char* const* properties;
    int rangeSteps;
    const PluginPortScalePoint* scalePoints;
    const char* shortname;
} PluginPort;

typedef struct {
    const PluginPort* input;
    const PluginPort* output;
} PluginPortsI;

typedef struct {
    PluginPortsI audio;
    PluginPortsI control;
    PluginPortsI cv;
    PluginPortsI midi;
} PluginPorts;

typedef struct {
    const char* uri;
    const char* label;
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
    const char* const* category;
    int microVersion;
    int minorVersion;
    const char* version;
    const char* stability;
    PluginAuthor author;
    const char* const* bundles;
    PluginGUI gui;
    PluginPorts ports;
    const PluginPreset* presets;
} PluginInfo;

typedef struct {
    bool valid;
} PedalboardInfo;

// initialize
MOD_API void init(void);

// cleanup, cannot be used afterwards
MOD_API void cleanup(void);

// add a bundle to our lilv world
// returns true if the bundle was added
MOD_API bool add_bundle_to_lilv_world(const char* bundle);

// remove a bundle from our lilv world
// returns true if the bundle was removed
MOD_API bool remove_bundle_from_lilv_world(const char* bundle);

// get all available plugins
// this triggers scanning of all plugins
MOD_API const PluginInfo* const* get_all_plugins(void);

// get a specific plugin
// NOTE: may return null
MOD_API const PluginInfo* get_plugin_info(const char* uri);

// get all available pedalboards (ie, plugins with pedalboard type)
MOD_API const PedalboardInfo* const* get_all_pedalboards(void);

// Get info from an lv2 bundle
// @a bundle is a string, consisting of a directory in the filesystem (absolute pathname).
MOD_API const PedalboardInfo* get_pedalboard_info(const char* bundle);

// Faster version of get_pedalboard_info when we just need to know the pedalboard name
// @a bundle is a string, consisting of a directory in the filesystem (absolute pathname).
MOD_API const char* get_pedalboard_name(const char* bundle);

#ifdef __cplusplus
} // extern "C"
#endif

#endif // MOD_UTILS_H_INCLUDED
