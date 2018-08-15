/*
 * MOD-UI utilities
 * Copyright (C) 2015-2016 Filipe Coelho <falktx@falktx.com>
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

#include <cstdio>
#include <cstring>

#include <alsa/asoundlib.h>
#include <jack/jack.h>

#include <algorithm>
#include <mutex>
#include <string>
#include <vector>

#define ALSA_SOUNDCARD_ID         "hw:MODDUO"
#define ALSA_CONTROL_BYPASS_LEFT  "Left True-Bypass"
#define ALSA_CONTROL_BYPASS_RIGHT "Right True-Bypass"
#define ALSA_CONTROL_LOOPBACK     "LOOPBACK"

#define JACK_SLAVE_PREFIX     "mod-slave"
#define JACK_SLAVE_PREFIX_LEN 9

// --------------------------------------------------------------------------------------------------------

static jack_client_t* gClient = nullptr;
static volatile unsigned gNewBufSize = 0;
static volatile unsigned gXrunCount = 0;
static const char** gPortListRet = nullptr;

static std::mutex gPortRegisterMutex;
static std::vector<std::string> gRegisteredPorts;

static std::mutex gPortUnregisterMutex;
static std::vector<std::string> gUnregisteredPorts;

static snd_mixer_t* gAlsaMixer = nullptr;
static snd_mixer_elem_t* gAlsaControlLeft  = nullptr;
static snd_mixer_elem_t* gAlsaControlRight = nullptr;
static bool gLastAlsaValueLeft  = false;
static bool gLastAlsaValueRight = false;

static JackBufSizeChanged     jack_bufsize_changed_cb = nullptr;
static JackPortAppeared       jack_port_appeared_cb   = nullptr;
static JackPortDeleted        jack_port_deleted_cb    = nullptr;
static TrueBypassStateChanged true_bypass_changed_cb  = nullptr;

// --------------------------------------------------------------------------------------------------------

static bool _get_alsa_switch_value(snd_mixer_elem_t* const elem)
{
    int val = 0;
    snd_mixer_selem_get_playback_switch(elem, SND_MIXER_SCHN_MONO, &val);
    return (val != 0);
}

// --------------------------------------------------------------------------------------------------------

static int JackBufSize(jack_nframes_t frames, void*)
{
    gNewBufSize = frames;
    return 0;
}

static void JackPortRegistration(jack_port_id_t port_id, int reg, void*)
{
    if (gClient == nullptr)
        return;

    if (reg)
    {
        if (jack_port_appeared_cb == nullptr)
            return;
    }
    else
    {
        if (jack_port_deleted_cb == nullptr)
            return;
    }

    if (const jack_port_t* const port = jack_port_by_id(gClient, port_id))
    {
        if ((jack_port_flags(port) & JackPortIsPhysical) == 0x0 && reg != 0)
            return;

        if (const char* const port_name = jack_port_name(port))
        {
            if (strncmp(port_name, "system:midi_", 12) != 0 &&
                strncmp(port_name, JACK_SLAVE_PREFIX ":", JACK_SLAVE_PREFIX_LEN + 1) != 0 &&
                strncmp(port_name, "nooice", 5) != 0)
                return;

            const std::string portName(port_name);

            if (reg)
            {
                const std::lock_guard<std::mutex> clg(gPortRegisterMutex);

                if (std::find(gRegisteredPorts.begin(), gRegisteredPorts.end(), portName) == gRegisteredPorts.end())
                    gRegisteredPorts.push_back(portName);
            }
            else
            {
                const std::lock_guard<std::mutex> clgr(gPortRegisterMutex);
                const std::lock_guard<std::mutex> clgu(gPortUnregisterMutex);

                if (std::find(gUnregisteredPorts.begin(), gUnregisteredPorts.end(), portName) == gUnregisteredPorts.end())
                    gUnregisteredPorts.push_back(portName);

                const std::vector<std::string>::iterator portNameItr =
                    std::find(gRegisteredPorts.begin(), gRegisteredPorts.end(), portName);
                if (portNameItr != gRegisteredPorts.end())
                    gRegisteredPorts.erase(portNameItr);
            }
        }
    }
}

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
    if (gAlsaMixer == nullptr)
    {
        if (snd_mixer_open(&gAlsaMixer, SND_MIXER_ELEM_SIMPLE) == 0)
        {
            snd_mixer_selem_id_t* sid;

            if (snd_mixer_attach(gAlsaMixer, ALSA_SOUNDCARD_ID) == 0 &&
                snd_mixer_selem_register(gAlsaMixer, nullptr, nullptr) == 0 &&
                snd_mixer_load(gAlsaMixer) == 0 &&
                snd_mixer_selem_id_malloc(&sid) == 0)
            {
                snd_mixer_selem_id_set_index(sid, 0);
                snd_mixer_selem_id_set_name(sid, ALSA_CONTROL_BYPASS_LEFT);

                if ((gAlsaControlLeft = snd_mixer_find_selem(gAlsaMixer, sid)) != nullptr)
                    gLastAlsaValueLeft = _get_alsa_switch_value(gAlsaControlLeft);

                snd_mixer_selem_id_set_index(sid, 0);
                snd_mixer_selem_id_set_name(sid, ALSA_CONTROL_BYPASS_RIGHT);

                if ((gAlsaControlRight = snd_mixer_find_selem(gAlsaMixer, sid)) != nullptr)
                    gLastAlsaValueRight = _get_alsa_switch_value(gAlsaControlRight);

                snd_mixer_selem_id_free(sid);
            }
            else
            {
                snd_mixer_close(gAlsaMixer);
                gAlsaMixer = nullptr;
            }
        }
    }

    if (gClient != nullptr)
    {
        printf("jack client activated before, nothing to do\n");
        return true;
    }

    const jack_options_t options = static_cast<jack_options_t>(JackNoStartServer|JackUseExactName);
    jack_client_t* const client = jack_client_open("mod-ui", options, nullptr);

    if (client == nullptr)
        return false;

    jack_set_buffer_size_callback(client, JackBufSize, nullptr);
    jack_set_port_registration_callback(client, JackPortRegistration, nullptr);
    jack_set_xrun_callback(client, JackXRun, nullptr);
    jack_on_shutdown(client, JackShutdown, nullptr);

    gClient = client;
    gNewBufSize = 0;
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

    if (gAlsaMixer != nullptr)
    {
        gAlsaControlLeft = nullptr;
        gAlsaControlRight = nullptr;
        snd_mixer_close(gAlsaMixer);
        gAlsaMixer = nullptr;
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

JackData* get_jack_data(bool withTransport)
{
    static JackData data = { 0.0f, 0, false, 4.0, 120.0 };
    static std::vector<std::string> localPorts;

    if (gClient != nullptr)
    {
        if (gXrunCount != 0 && data.xruns != gXrunCount)
            data.cpuLoad = 100.0f;
        else
            data.cpuLoad = jack_cpu_load(gClient);

        data.xruns = gXrunCount;

        if (withTransport)
        {
            jack_position_t pos;
            data.rolling = jack_transport_query(gClient, &pos) == JackTransportRolling;

            if (pos.valid & JackTransportBBT)
            {
                data.bpb = pos.beats_per_bar;
                data.bpm = pos.beats_per_minute;
            }
            else
            {
                data.bpb = 4.0;
                data.bpm = 120.0;
            }
        }

        if (jack_port_deleted_cb != nullptr)
        {
            // See if any new ports have been unregistered
            {
                const std::lock_guard<std::mutex> clg(gPortUnregisterMutex);

                if (gUnregisteredPorts.size() > 0)
                    gUnregisteredPorts.swap(localPorts);
            }

            for (const std::string& portName : localPorts)
                jack_port_deleted_cb(portName.c_str());

            localPorts.clear();
        }

        if (jack_port_appeared_cb != nullptr)
        {
            // See if any new ports have been registered
            {
                const std::lock_guard<std::mutex> clg(gPortRegisterMutex);

                if (gRegisteredPorts.size() > 0)
                    gRegisteredPorts.swap(localPorts);
            }

            for (const std::string& portName : localPorts)
            {
                if (jack_port_t* const port = jack_port_by_name(gClient, portName.c_str()))
                {
                    const bool isOutput = jack_port_flags(port) & JackPortIsInput; // inverted on purpose
                    jack_port_appeared_cb(portName.c_str(), isOutput);
                }
            }

            localPorts.clear();
        }
    }
    else
    {
        data.cpuLoad = 0.0f;
        data.xruns   = 0;
        data.rolling = false;
        data.bpb     = 4.0;
        data.bpm     = 120.0;
    }

    if (gNewBufSize > 0 && jack_bufsize_changed_cb != nullptr)
    {
        const unsigned int bufsize = gNewBufSize;
        gNewBufSize = 0;

        jack_bufsize_changed_cb(bufsize);
    }

    if (gAlsaMixer != nullptr && true_bypass_changed_cb != nullptr)
    {
        bool changed = false;
        snd_mixer_handle_events(gAlsaMixer);

        if (gAlsaControlLeft != nullptr)
        {
            const bool newValue = _get_alsa_switch_value(gAlsaControlLeft);

            if (gLastAlsaValueLeft != newValue)
            {
                changed = true;
                gLastAlsaValueLeft = newValue;
            }
        }

        if (gAlsaControlRight != nullptr)
        {
            const bool newValue = _get_alsa_switch_value(gAlsaControlRight);

            if (gLastAlsaValueRight != newValue)
            {
                changed = true;
                gLastAlsaValueRight = newValue;
            }
        }

        if (changed)
            true_bypass_changed_cb(gLastAlsaValueLeft, gLastAlsaValueRight);
    }

    return &data;
}

unsigned get_jack_buffer_size(void)
{
    if (gClient == nullptr)
        return 128;

    return jack_get_buffer_size(gClient);
}

unsigned set_jack_buffer_size(unsigned size)
{
    if (gClient == nullptr)
        return 0;

    if (jack_set_buffer_size(gClient, size) == 0)
        return size;

    return jack_get_buffer_size(gClient);
}

float get_jack_sample_rate(void)
{
    if (gClient == nullptr)
        return 48000.0f;

    return jack_get_sample_rate(gClient);
}

const char* get_jack_port_alias(const char* portname)
{
    static char  aliases[2][0xff];
    static char* aliasesptr[2] = {
        aliases[0],
        aliases[1]
    };

    if (gClient != nullptr)
        if (jack_port_t* const port = jack_port_by_name(gClient, portname))
            if (jack_port_get_aliases(port, aliasesptr) > 0)
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
    const char** const ports  = jack_get_ports(gClient, "", type, flags);

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

bool connect_jack_ports(const char* port1, const char* port2)
{
    if (gClient == nullptr)
        return false;

    int ret;

    ret = jack_connect(gClient, port1, port2);
    if (ret == 0 || ret == EEXIST)
        return true;

    ret = jack_connect(gClient, port2, port1);
    if (ret == 0 || ret == EEXIST)
        return true;

    return false;
}

bool disconnect_jack_ports(const char* port1, const char* port2)
{
    if (gClient == nullptr)
        return false;

    if (jack_disconnect(gClient, port1, port2) == 0)
        return true;
    if (jack_disconnect(gClient, port2, port1) == 0)
        return true;

    return false;
}

void reset_xruns(void)
{
    gXrunCount = 0;
}

// --------------------------------------------------------------------------------------------------------

void init_bypass(void)
{
    if (gAlsaMixer == nullptr)
        return;

    if (gAlsaControlLeft != nullptr)
    {
        gLastAlsaValueLeft = false;
        snd_mixer_selem_set_playback_switch_all(gAlsaControlLeft, 0);
    }

    if (gAlsaControlRight != nullptr)
    {
        gLastAlsaValueRight = false;
        snd_mixer_selem_set_playback_switch_all(gAlsaControlRight, 0);
    }

    snd_mixer_selem_id_t* sid;
    if (snd_mixer_selem_id_malloc(&sid) == 0)
    {
        snd_mixer_selem_id_set_index(sid, 0);
        snd_mixer_selem_id_set_name(sid, ALSA_CONTROL_LOOPBACK);

        if (snd_mixer_elem_t* const elem = snd_mixer_find_selem(gAlsaMixer, sid))
            snd_mixer_selem_set_playback_switch_all(elem, 0);

        snd_mixer_selem_id_free(sid);
    }
}

bool get_truebypass_value(bool right)
{
    return right ? gLastAlsaValueRight : gLastAlsaValueLeft;
}

bool set_truebypass_value(bool right, bool bypassed)
{
    if (gAlsaMixer == nullptr)
        return false;

    if (right)
    {
        if (gAlsaControlRight != nullptr)
            return (snd_mixer_selem_set_playback_switch_all(gAlsaControlRight, bypassed) == 0);
    }
    else
    {
        if (gAlsaControlLeft != nullptr)
            return (snd_mixer_selem_set_playback_switch_all(gAlsaControlLeft, bypassed) == 0);
    }

    return false;
}

// --------------------------------------------------------------------------------------------------------

void set_util_callbacks(JackBufSizeChanged bufSizeChanged,
                        JackPortAppeared portAppeared,
                        JackPortDeleted portDeleted,
                        TrueBypassStateChanged trueBypassChanged)
{
    jack_bufsize_changed_cb = bufSizeChanged;
    jack_port_appeared_cb   = portAppeared;
    jack_port_deleted_cb    = portDeleted;
    true_bypass_changed_cb  = trueBypassChanged;
}

// --------------------------------------------------------------------------------------------------------
