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

#ifndef DEBUG
#define DEBUG
#endif

#include "utils.h"

#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

void scanPlugins()
{
#if 1
    if (const char* const* const uris = get_plugin_list())
    {
        for (int i=0; uris[i] != nullptr; ++i)
            // do nothing
            continue;
    }

    if (const PluginInfo_Mini* const* const plugins = get_all_plugins())
    {
        for (int i=0; plugins[i] != nullptr; ++i)
        {
            if (! plugins[i])
            {
                printf("Invalid plugin found\n");
                break;
            }

            get_plugin_info(plugins[i]->uri);
            get_plugin_gui(plugins[i]->uri);
            get_plugin_gui_mini(plugins[i]->uri);
            get_plugin_control_inputs(plugins[i]->uri);
            get_plugin_info_essentials(plugins[i]->uri);
        }
    }
#endif

#if 1
    if (const char* const* const pedalboards = get_broken_pedalboards())
    {
        for (int i=0; pedalboards[i] != nullptr; ++i)
            // do nothing
            continue;
    }

    if (const PedalboardInfo_Mini* const* const pedalboards = get_all_pedalboards(kPedalboardInfoBoth))
    {
        for (int i=0; pedalboards[i] != nullptr; ++i)
        {
            if (! pedalboards[i])
            {
                printf("Invalid pedalboard found\n");
                break;
            }

            get_pedalboard_info(pedalboards[i]->bundle);
            get_pedalboard_size(pedalboards[i]->bundle);
            get_pedalboard_plugin_values(pedalboards[i]->bundle);
        }
    }
#endif
}

int main()
{
#if 1
    init();
    scanPlugins();
# if 1
# define PLUGIN_TEST_URI "http://code.google.com/p/amsynth/amsynth"
    rescan_plugin_presets(PLUGIN_TEST_URI);
    get_plugin_info(PLUGIN_TEST_URI);
    get_plugin_gui(PLUGIN_TEST_URI);
    get_plugin_gui_mini(PLUGIN_TEST_URI);
    get_plugin_control_inputs(PLUGIN_TEST_URI);
    get_plugin_info_essentials(PLUGIN_TEST_URI);
# undef PLUGIN_TEST_URI
# endif
    cleanup();
#endif

#if 0
    setenv("LV2_PATH", "/NOT", 1);
    init();
    get_state_port_values("@prefix just_a_test: <urn:ignore:me>.");
    assert(get_all_plugins() == nullptr);
    assert(add_bundle_to_lilv_world("/NOT") == nullptr);
    assert(add_bundle_to_lilv_world("/NOT/") == nullptr);
    assert(add_bundle_to_lilv_world("/usr/lib/lv2/calf.lv2") != nullptr);
    assert(add_bundle_to_lilv_world("/usr/lib/lv2/calf.lv2/") == nullptr);
    assert(get_all_plugins() != nullptr);
    scanPlugins();
    assert(remove_bundle_from_lilv_world("/usr/lib/lv2/calf.lv2") != nullptr);
    assert(remove_bundle_from_lilv_world("/usr/lib/lv2/calf.lv2") == nullptr);
    assert(get_all_plugins() == nullptr);
    assert(add_bundle_to_lilv_world("/NOT") == nullptr);
    assert(remove_bundle_from_lilv_world("/NOT") == nullptr);
    assert(add_bundle_to_lilv_world("/usr/lib/lv2/calf.lv2/") != nullptr);
    assert(add_bundle_to_lilv_world("/usr/lib/lv2/calf.lv2") == nullptr);
    assert(get_all_plugins() != nullptr);
    scanPlugins();
    cleanup();
#endif

#if 0
    const PluginInfo* info;
    setenv("LV2_PATH", "/NOT", 1);
    init();

    // no plugins available
    assert(get_all_plugins() == nullptr);
    // trying to get the plugin fails
    assert(get_plugin_info("http://guitarix.sourceforge.net/plugins/gx_voxtb_#_voxtb_") == nullptr);

    // add plugin bundle
    assert(add_bundle_to_lilv_world("/usr/lib/lv2/gx_voxtb.lv2") != nullptr);
    // get the plugin
    info = get_plugin_info("http://guitarix.sourceforge.net/plugins/gx_voxtb_#_voxtb_");
    assert(info != nullptr);
    assert(strcmp(info->name, "GxVoxTonebender") == 0);
    assert(info->ports.control.input != nullptr);

    // remove bundle, must return some plugins
    assert(remove_bundle_from_lilv_world("/usr/lib/lv2/gx_voxtb.lv2/") != nullptr);
    // plugin is now null
    info = get_plugin_info("http://guitarix.sourceforge.net/plugins/gx_voxtb_#_voxtb_");
    assert(get_plugin_info("http://guitarix.sourceforge.net/plugins/gx_voxtb_#_voxtb_") == nullptr);

    // remove bundle again, must return empty
    assert(remove_bundle_from_lilv_world("/usr/lib/lv2/gx_voxtb.lv2") == nullptr);
    // plugin is still null
    info = get_plugin_info("http://guitarix.sourceforge.net/plugins/gx_voxtb_#_voxtb_");
    assert(info == nullptr);

    // re-add plugin bundle
    assert(add_bundle_to_lilv_world("/usr/lib/lv2/gx_voxtb.lv2") != nullptr);
    // get the plugin
    info = get_plugin_info("http://guitarix.sourceforge.net/plugins/gx_voxtb_#_voxtb_");
    assert(info != nullptr);
    assert(strcmp(info->name, "GxVoxTonebender") == 0);
    assert(info->ports.control.input != nullptr);

    // re-re-add plugin bundle, because it's already loaded it must return no plugins
    assert(add_bundle_to_lilv_world("/usr/lib/lv2/gx_voxtb.lv2/") == nullptr);
    // get the plugin, still valid as expected
    info = get_plugin_info("http://guitarix.sourceforge.net/plugins/gx_voxtb_#_voxtb_");
    assert(info != nullptr);
    assert(strcmp(info->name, "GxVoxTonebender") == 0);
    assert(info->ports.control.input != nullptr);

    cleanup();
#endif

#if 0
    assert(init_jack());
    assert(get_jack_data(true) != nullptr);
    get_jack_sample_rate();
    get_jack_port_alias("system:capture_1");
    get_jack_hardware_ports(false, false);
    get_jack_hardware_ports(false, true);
    get_jack_hardware_ports(true, true);
    get_jack_hardware_ports(true, false);
    has_serial_midi_input_port();
    has_serial_midi_output_port();
    connect_jack_ports("not", "not2");
    disconnect_jack_ports("not", "not2");
    close_jack();
#endif

    return 0;
}
