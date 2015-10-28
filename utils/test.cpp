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

#include <stdio.h>
#include <unistd.h>

int main()
{
    init();

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
        }
    }

    if (const PedalboardInfo* const* const pedalboards = get_all_pedalboards())
    {
        for (int i=0; pedalboards[i] != nullptr; ++i)
        {
            if (! pedalboards[i]->valid)
            {
                printf("Invalid pedalboard found\n");
                break;
            }

            get_pedalboard_info(pedalboards[i]->bundle);
            get_pedalboard_name(pedalboards[i]->bundle);
        }
    }

    //sleep(10);

    cleanup();
    return 0;
}
