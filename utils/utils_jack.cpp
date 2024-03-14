// SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
// SPDX-License-Identifier: AGPL-3.0-or-later

#include "utils.h"

#include <cstdio>
#include <cstring>

#ifdef HAVE_ALSA
#include <alsa/asoundlib.h>
#endif
#include <jack/jack.h>

#include <algorithm>
#include <mutex>
#include <string>
#include <vector>

#define ALSA_SOUNDCARD_DEFAULT_ID  "MODDUO"
#define ALSA_CONTROL_BYPASS_LEFT   "Left True-Bypass"
#define ALSA_CONTROL_BYPASS_RIGHT  "Right True-Bypass"
#define ALSA_CONTROL_LOOPBACK1     "LOOPBACK"
#define ALSA_CONTROL_LOOPBACK2     "Loopback Switch"
#define ALSA_CONTROL_SPDIF_ENABLE  "SPDIF Enable"
#define ALSA_CONTROL_MASTER_VOLUME "DAC"

#define JACK_EXTERNAL_PREFIX     "mod-external"
#define JACK_EXTERNAL_PREFIX_LEN 12

// --------------------------------------------------------------------------------------------------------

static jack_client_t* gClient = nullptr;
static volatile unsigned gNewBufSize = 0;
static volatile unsigned gXrunCount = 0;
static const char** gPortListRet = nullptr;

static std::mutex gPortRegisterMutex;
static std::vector<std::string> gRegisteredPorts;

static std::mutex gPortUnregisterMutex;
static std::vector<std::string> gUnregisteredPorts;

#ifdef HAVE_ALSA
static snd_mixer_t* gAlsaMixer = nullptr;
static snd_mixer_elem_t* gAlsaControlLeft  = nullptr;
static snd_mixer_elem_t* gAlsaControlRight = nullptr;
static snd_mixer_elem_t* gAlsaControlCvExp = nullptr;
static bool gLastAlsaValueLeft  = true;
static bool gLastAlsaValueRight = true;
static bool gLastAlsaValueCvExp = false;
#endif

static JackBufSizeChanged     jack_bufsize_changed_cb = nullptr;
static JackPortAppeared       jack_port_appeared_cb   = nullptr;
static JackPortDeleted        jack_port_deleted_cb    = nullptr;
static TrueBypassStateChanged true_bypass_changed_cb  = nullptr;
#ifdef HAVE_ALSA
static CvExpInputModeChanged  cv_exp_mode_changed_cb  = nullptr;
#endif

// --------------------------------------------------------------------------------------------------------

#ifdef HAVE_ALSA
static bool _get_alsa_switch_value(snd_mixer_elem_t* const elem)
{
    int val = 0;
    snd_mixer_selem_get_playback_switch(elem, SND_MIXER_SCHN_MONO, &val);
    return (val != 0);
}
#endif

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
                strncmp(port_name, JACK_EXTERNAL_PREFIX ":", JACK_EXTERNAL_PREFIX_LEN + 1) != 0 &&
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
#ifdef HAVE_ALSA
    if (gAlsaMixer == nullptr)
    {
        if (snd_mixer_open(&gAlsaMixer, SND_MIXER_ELEM_SIMPLE) == 0)
        {
            snd_mixer_selem_id_t* sid;

            char soundcard[32] = "hw:";

            if (const char* const cardname = getenv("MOD_SOUNDCARD"))
                strncat(soundcard, cardname, 28);
            else
                strncat(soundcard, ALSA_SOUNDCARD_DEFAULT_ID, 28);

            soundcard[31] = '\0';

            if (snd_mixer_attach(gAlsaMixer, soundcard) == 0 &&
                snd_mixer_selem_register(gAlsaMixer, nullptr, nullptr) == 0 &&
                snd_mixer_load(gAlsaMixer) == 0 &&
                snd_mixer_selem_id_malloc(&sid) == 0)
            {
                snd_mixer_selem_id_set_index(sid, 0);
                snd_mixer_selem_id_set_name(sid, ALSA_CONTROL_BYPASS_LEFT);
                gAlsaControlLeft = snd_mixer_find_selem(gAlsaMixer, sid);

                snd_mixer_selem_id_set_index(sid, 0);
                snd_mixer_selem_id_set_name(sid, ALSA_CONTROL_BYPASS_RIGHT);
                gAlsaControlRight = snd_mixer_find_selem(gAlsaMixer, sid);

#ifdef _MOD_DEVICE_DUOX
                // special case until HMI<->system comm is not in place yet
                snd_mixer_selem_id_set_index(sid, 0);
                snd_mixer_selem_id_set_name(sid, "CV/Exp.Pedal Mode");
                gAlsaControlCvExp = snd_mixer_find_selem(gAlsaMixer, sid);
#endif

                snd_mixer_selem_id_free(sid);
            }
            else
            {
                snd_mixer_close(gAlsaMixer);
                gAlsaMixer = nullptr;
            }
        }
    }
#endif

    if (gClient != nullptr)
    {
        printf("jack client activated before, nothing to do\n");
        return true;
    }

#ifdef _MOD_DESKTOP
    const jack_options_t options = static_cast<jack_options_t>(JackNoStartServer|JackUseExactName|JackServerName);
    const char* servername = std::getenv("MOD_DESKTOP_SERVER_NAME");
    if (servername == nullptr)
        servername = "mod-desktop";
    jack_client_t* const client = jack_client_open("mod-ui", options, nullptr, servername);
#else
    const jack_options_t options = static_cast<jack_options_t>(JackNoStartServer|JackUseExactName);
    jack_client_t* const client = jack_client_open("mod-ui", options, nullptr);
#endif

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

#ifdef HAVE_ALSA
    if (gAlsaMixer != nullptr)
    {
        gAlsaControlLeft = nullptr;
        gAlsaControlRight = nullptr;
        snd_mixer_close(gAlsaMixer);
        gAlsaMixer = nullptr;
    }
#endif

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

#ifdef HAVE_ALSA
    if (gAlsaMixer != nullptr && (true_bypass_changed_cb != nullptr || cv_exp_mode_changed_cb != nullptr))
    {
        bool changedBypass = false;
        snd_mixer_handle_events(gAlsaMixer);

        if (gAlsaControlLeft != nullptr)
        {
            const bool newValue = _get_alsa_switch_value(gAlsaControlLeft);

            if (gLastAlsaValueLeft != newValue)
            {
                changedBypass = true;
                gLastAlsaValueLeft = newValue;
            }
        }

        if (gAlsaControlRight != nullptr)
        {
            const bool newValue = _get_alsa_switch_value(gAlsaControlRight);

            if (gLastAlsaValueRight != newValue)
            {
                changedBypass = true;
                gLastAlsaValueRight = newValue;
            }
        }

        if (changedBypass && true_bypass_changed_cb != nullptr)
            true_bypass_changed_cb(gLastAlsaValueLeft, gLastAlsaValueRight);

#ifdef _MOD_DEVICE_DUOX
        // special case until HMI<->system comm is not in place yet
        bool changedCvExpMode = false;

        if (gAlsaControlCvExp != nullptr)
        {
            bool newValue = gLastAlsaValueCvExp;

            // open new mixer to force read of cv/exp value
            snd_mixer_t* mixer;
            if (snd_mixer_open(&mixer, SND_MIXER_ELEM_SIMPLE) == 0)
            {
                snd_mixer_selem_id_t* sid;
                if (snd_mixer_attach(mixer, "hw:DUOX") == 0 &&
                    snd_mixer_selem_register(mixer, nullptr, nullptr) == 0 &&
                    snd_mixer_load(mixer) == 0 &&
                    snd_mixer_selem_id_malloc(&sid) == 0)
                {
                    snd_mixer_selem_id_set_index(sid, 0);
                    snd_mixer_selem_id_set_name(sid, "CV/Exp.Pedal Mode");

                    if (snd_mixer_elem_t* const elem = snd_mixer_find_selem(mixer, sid))
                        newValue = _get_alsa_switch_value(elem);

                    snd_mixer_selem_id_free(sid);
                }

                snd_mixer_close(mixer);
            }

            if (gLastAlsaValueCvExp != newValue)
            {
                changedCvExpMode = true;
                gLastAlsaValueCvExp = newValue;
            }
        }

        if (changedCvExpMode && cv_exp_mode_changed_cb != nullptr)
            cv_exp_mode_changed_cb(gLastAlsaValueCvExp);
#endif
    }
#endif

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
    static char  aliases[2][320];
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

    // hide midi-through capture ports
    if (!isAudio && !isOutput)
    {
        static char  aliases[2][320];
        static char* aliasesptr[2] = {
            aliases[0],
            aliases[1]
        };

        for (int i=0; ports[i] != nullptr; ++i)
        {
            if (strncmp(ports[i], "system:midi_capture_", 20))
                continue;

            jack_port_t* const port = jack_port_by_name(gClient, ports[i]);

            if (port == nullptr)
                continue;
            if (jack_port_get_aliases(port, aliasesptr) <= 0)
                continue;
            if (strncmp(aliases[0], "alsa_pcm:Midi-Through/", 22))
                continue;

            for (int j=i; ports[j] != nullptr; ++j)
                ports[j] = ports[j+1];
            --i;
        }
    }

#ifdef _MOD_DEVICE_DUOX
    // Duo X special case for SPDIF mirrored mode
    if (isAudio && isOutput && ! has_duox_split_spdif())
    {
        for (int i=0; ports[i] != nullptr; ++i)
        {
            if (ports[i+1] == nullptr)
                break;
            if (std::strcmp(ports[i], "system:playback_3") != 0)
                continue;
            if (std::strcmp(ports[i+1], "system:playback_4") != 0)
                continue;

            for (int j=i+2; ports[j] != nullptr; ++i, ++j)
                ports[i] = ports[j];

            ports[i] = nullptr;
            break;
        }
    }
#endif

    gPortListRet = ports;

    return ports;
}

// --------------------------------------------------------------------------------------------------------

bool has_midi_beat_clock_sender_port(void)
{
    if (gClient == nullptr)
        return false;

    // TODO: This must be the same as in `settings.py`!
    return (jack_port_by_name(gClient, "effect_9993:mclk") != nullptr);
}

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

/**
 * Ask the JACK server if there is the midi-merger client available.
 */
bool has_midi_merger_output_port(void)
{
    if (gClient == nullptr)
        return false;

    return (jack_port_by_name(gClient, "mod-midi-merger:out") != nullptr);
}

/**
 * Ask the JACK server if there is the midi-broadcaster client available.
 */
bool has_midi_broadcaster_input_port(void)
{
    if (gClient == nullptr)
        return false;

    return (jack_port_by_name(gClient, "mod-midi-broadcaster:in") != nullptr);
}

bool has_duox_split_spdif(void)
{
#ifdef _MOD_DEVICE_DUOX
    if (gClient == nullptr)
        return false;

    return (jack_port_by_name(gClient, "mod-monitor:in_3") != nullptr);
#else
    return false;
#endif
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

bool connect_jack_midi_output_ports(const char* port)
{
    if (gClient == nullptr)
        return false;

    int ret;

    if (jack_port_by_name(gClient, "mod-midi-broadcaster:in") != nullptr)
    {
        ret = jack_connect(gClient, port, "mod-midi-broadcaster:in");
        return (ret == 0 || ret == EEXIST);
    }

    if (const char** const ports = jack_get_ports(gClient, "",
                                                  JACK_DEFAULT_MIDI_TYPE,
                                                  JackPortIsPhysical | JackPortIsInput))
    {
        for (int i=0; ports[i] != nullptr; ++i)
            jack_connect(gClient, port, ports[i]);

        jack_free(ports);
        return true;
    }

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

bool disconnect_all_jack_ports(const char* portname)
{
    if (gClient == nullptr)
        return false;

    jack_port_t* const port = jack_port_by_name(gClient, portname);

    if (port == nullptr)
        return false;

    const bool isOutput = jack_port_flags(port) & JackPortIsOutput;

    if (const char** const ports = jack_port_get_all_connections(gClient, port))
    {
        for (int i=0; ports[i] != nullptr; ++i)
        {
            if (isOutput)
                jack_disconnect(gClient, portname, ports[i]);
            else
                jack_disconnect(gClient, ports[i], portname);
        }

        jack_free(ports);
    }

    return true;
}

void reset_xruns(void)
{
    gXrunCount = 0;
}

// --------------------------------------------------------------------------------------------------------

void init_bypass(void)
{
#ifdef HAVE_ALSA
    if (gAlsaMixer == nullptr)
        return;

    if (gAlsaControlLeft != nullptr)
        snd_mixer_selem_set_playback_switch_all(gAlsaControlLeft, 0);

    if (gAlsaControlRight != nullptr)
        snd_mixer_selem_set_playback_switch_all(gAlsaControlRight, 0);

#ifdef _MOD_DEVICE_DUOX
    // special case until HMI<->system comm is not in place yet
    if (gAlsaControlCvExp != nullptr)
        gLastAlsaValueCvExp = _get_alsa_switch_value(gAlsaControlCvExp);
#endif

    snd_mixer_selem_id_t* sid;
    if (snd_mixer_selem_id_malloc(&sid) == 0)
    {
        snd_mixer_selem_id_set_index(sid, 0);
        snd_mixer_selem_id_set_name(sid, ALSA_CONTROL_LOOPBACK1);

        if (snd_mixer_elem_t* const elem = snd_mixer_find_selem(gAlsaMixer, sid))
            snd_mixer_selem_set_playback_switch_all(elem, 0);

        snd_mixer_selem_id_set_index(sid, 0);
        snd_mixer_selem_id_set_name(sid, ALSA_CONTROL_LOOPBACK2);

        if (snd_mixer_elem_t* const elem = snd_mixer_find_selem(gAlsaMixer, sid))
            snd_mixer_selem_set_playback_switch_all(elem, 0);

        snd_mixer_selem_id_set_index(sid, 0);
        snd_mixer_selem_id_set_name(sid, ALSA_CONTROL_SPDIF_ENABLE);

        if (snd_mixer_elem_t* const elem = snd_mixer_find_selem(gAlsaMixer, sid))
            snd_mixer_selem_set_playback_switch_all(elem, 1);

        snd_mixer_selem_id_free(sid);
    }
#endif
}

bool get_truebypass_value(bool right)
{
#ifdef HAVE_ALSA
    return right ? gLastAlsaValueRight : gLastAlsaValueLeft;
#else
    return false;

    // unused
    (void)right;
#endif
}

bool set_truebypass_value(bool right, bool bypassed)
{
#ifdef HAVE_ALSA
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
#endif

    return false;

#ifndef HAVE_ALSA
    // unused
    (void)right;
    (void)bypassed;
#endif
}

float get_master_volume(bool right)
{
#ifdef HAVE_ALSA
    if (gAlsaMixer == nullptr)
        return -127.5f;

    snd_mixer_selem_id_t* sid;

    if (snd_mixer_selem_id_malloc(&sid) != 0)
        return -127.5f;

    snd_mixer_selem_id_set_index(sid, 0);
    snd_mixer_selem_id_set_name(sid, ALSA_CONTROL_MASTER_VOLUME);

    float val = -127.5f;

    if (snd_mixer_elem_t* const elem = snd_mixer_find_selem(gAlsaMixer, sid))
    {
        long aval = 0;
        snd_mixer_selem_get_playback_volume(elem,
                                            right ? SND_MIXER_SCHN_FRONT_RIGHT : SND_MIXER_SCHN_FRONT_LEFT,
                                            &aval);

        const float a = 127.5f / 255.f;
        const float b = - a * 255.f;
        val = a * aval + b;
    }

    snd_mixer_selem_id_free(sid);
    return val;
#else
    return -127.5f;

    // unused
    (void)right;
#endif
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


void set_extra_util_callbacks(CvExpInputModeChanged cvExpInputModeChanged)
{
#ifdef _MOD_DEVICE_DUOX
    cv_exp_mode_changed_cb = cvExpInputModeChanged;
#else
    // unused
    (void)cvExpInputModeChanged;
#ifdef HAVE_ALSA
    (void)gAlsaControlCvExp;
    (void)gLastAlsaValueCvExp;
#endif
#endif
}

// --------------------------------------------------------------------------------------------------------
