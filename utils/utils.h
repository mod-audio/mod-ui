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

typedef struct _PluginAuthor {
    const char* name;
    const char* homepage;
    const char* email;
} PluginAuthor;

typedef struct _PluginGUI {
    char dummy;
} PluginGUI;

typedef struct _PluginInfo {
    bool valid;
    const char* uri;
    const char* name;
    const char* binary;
    const char* license;
    const char* comment;
    const char* const* category;
    PluginAuthor author;
    PluginGUI gui;
} PluginInfo;

typedef struct _PedalboardInfo {
    bool valid;
} PedalboardInfo;

// initialize
MOD_API void init(void);

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
