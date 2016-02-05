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

// #include <stdlib.h>
#include <stdio.h>
// #include <string.h>

#include <jack/jack.h>

#include <algorithm>

// --------------------------------------------------------------------------------------------------------

static jack_client_t* gClient = nullptr;
static volatile unsigned gXrunCount = 0;
static const char** gPortListRet = nullptr;

// --------------------------------------------------------------------------------------------------------

/*
static void JackPortRegistration(jack_port_id_t port, int reg, void*)
{
    if (reg == 0)
        return;
}
*/

static int JackXRun(void*)
{
    gXrunCount += 1;
    return 0;
}

static void JackShutdown(void*)
{
    gClient = nullptr;
}

// --------------------------------------------------------------------------------------------------------

bool init_jack(void)
{
    const jack_options_t options = static_cast<jack_options_t>(JackNoStartServer|JackUseExactName);
    jack_client_t* const client = jack_client_open("mod-ui", options, nullptr);

    if (client == nullptr)
        return false;

    //jack_set_port_registration_callback(client, JackPortRegistration, nullptr);
    jack_set_xrun_callback(client, JackXRun, nullptr);
    jack_on_shutdown(client, JackShutdown, nullptr);

    gClient = client;
    gXrunCount = 0;
    jack_activate(client);

    printf("jack client activated\n");
    return true;
}

void close_jack(void)
{
    if (gPortListRet != nullptr)
    {
        jack_free(gPortListRet);
        gPortListRet = nullptr;
    }

    if (gClient == nullptr)
    {
        printf("jack client deactivated NOT\n");
        return;
    }

    jack_client_t* const client = gClient;
    gClient = nullptr;

    jack_deactivate(client);
    jack_client_close(client);

    printf("jack client deactivated\n");
}

// --------------------------------------------------------------------------------------------------------

JackData* get_jack_data(void)
{
    static JackData data;

    if (gClient != nullptr)
    {
        data.cpuLoad = jack_cpu_load(gClient);
        data.xruns   = gXrunCount;
    }
    else
    {
        data.cpuLoad = 0.0f;
        data.xruns   = 0;
    }

    return &data;
}

float get_jack_sample_rate(void)
{
    if (gClient == nullptr)
        return 48000.0f;

    return jack_get_sample_rate(gClient);
}

const char* get_jack_port_alias(const char* portname)
{
    static char aliases[0xff][2];
    char* aliasesptr[2] = {
        aliases[0],
        aliases[1]
    };

    if (gClient != nullptr && jack_port_get_aliases(jack_port_by_name(gClient, portname), aliasesptr) > 0)
        return aliases[0];

    return nullptr;
}

const char* const* get_jack_hardware_ports(const bool isAudio, bool isOutput)
{
    if (gPortListRet != nullptr)
    {
        jack_free(gPortListRet);
        gPortListRet = nullptr;
    }

    if (gClient == nullptr)
        return nullptr;

    const unsigned long flags = JackPortIsPhysical | (isOutput ? JackPortIsInput : JackPortIsOutput);
    const char* const type    = isAudio ? JACK_DEFAULT_AUDIO_TYPE : JACK_DEFAULT_MIDI_TYPE;
    const char** const ports  = jack_get_ports(gClient, "system:", type, flags);

    if (ports == nullptr)
        return nullptr;

    gPortListRet = ports;

    return ports;
}

// --------------------------------------------------------------------------------------------------------

bool has_serial_midi_input_port(void)
{
    if (gClient == nullptr)
        return false;

    return (jack_port_by_name(gClient, "ttymidi:MIDI_in") != nullptr);
}

bool has_serial_midi_output_port(void)
{
    if (gClient == nullptr)
        return false;

    return (jack_port_by_name(gClient, "ttymidi:MIDI_out") != nullptr);
}

// --------------------------------------------------------------------------------------------------------

void connect_jack_ports(const char* port1, const char* port2)
{
    if (gClient != nullptr)
        jack_connect(gClient, port1, port2);
}

void disconnect_jack_ports(const char* port1, const char* port2)
{
    if (gClient != nullptr)
        jack_disconnect(gClient, port1, port2);
}

// --------------------------------------------------------------------------------------------------------
