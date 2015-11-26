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

#ifndef DEBUG
#define DEBUG
#endif

#include "utils.h"

#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

void scanPlugins()
{
#if 0
    if (const PluginInfo_Mini* const* const plugins = get_all_plugins())
    {
        for (int i=0; plugins[i] != nullptr; ++i)
        {
            if (! plugins[i]->valid)
            {
                printf("Invalid plugin found\n");
                break;
            }

            get_plugin_info(plugins[i]->uri);
            get_plugin_info_mini(plugins[i]->uri);
            get_plugin_control_input_ports(plugins[i]->uri);
        }
    }
#endif

#if 1
    if (const PedalboardInfo_Mini* const* const pedalboards = get_all_pedalboards())
    {
        for (int i=0; pedalboards[i] != nullptr; ++i)
        {
            if (! pedalboards[i]->valid)
            {
                printf("Invalid pedalboard found\n");
                break;
            }

            get_pedalboard_info(pedalboards[i]->bundle);
            get_pedalboard_size(pedalboards[i]->bundle);
        }
    }
#endif
}

int main()
{
#if 1
    init();
    scanPlugins();
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
    scanPlugins();
    cleanup();
#endif

    return 0;
}
