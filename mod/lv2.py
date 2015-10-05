#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import lilv

from mod.lilvlib import NS, LILV_FOREACH, plugin_has_modgui
from mod.lilvlib import get_plugin_info as get_plugin_info2
from mod.settings import MODGUI_SHOW_MODE

# global stuff
global W, BUNDLES, PLUGINS, PLUGNFO

# our lilv world
W = lilv.World()

# list of loaded bundles
BUNDLES = []

# list of lilv plugins
PLUGINS = []

# cached info about each plugin (using uri as key)
PLUGNFO = {}

# cached keys() of PLUGNFO, for performance
PLUGNFOk = []

# Blacklisted plugins, which don't work properly on MOD for various reasons
BLACKLIST = [
    "urn:50m30n3:plugins:SO-404",
    "urn:50m30n3:plugins:SO-666",
    "urn:50m30n3:plugins:SO-kl5",
    "urn:juce:JuceDemoHost",
    "urn:juced:DrumSynth",
    "file:///usr/lib/lv2/MonoEffect.ingen/MonoEffect.ttl",
    "file:///usr/lib/lv2/MonoInstrument.ingen/MonoInstrument.ttl",
    "file:///usr/lib/lv2/StereoEffect.ingen/StereoEffect.ttl",
    "file:///usr/lib/lv2/StereoInstrument.ingen/StereoInstrument.ttl",
    "http://calf.sourceforge.net/plugins/Analyzer",
    "http://distrho.sf.net/plugins/ProM",
    "http://drumgizmo.org/lv2",
    "http://drumkv1.sourceforge.net/lv2",
    "http://factorial.hu/plugins/lv2/ir",
    "http://gareus.org/oss/lv2/meters#BBCM6",
    "http://gareus.org/oss/lv2/meters#BBCmono",
    "http://gareus.org/oss/lv2/meters#BBCstereo",
    "http://gareus.org/oss/lv2/meters#bitmeter",
    "http://gareus.org/oss/lv2/meters#COR",
    "http://gareus.org/oss/lv2/meters#dBTPmono",
    "http://gareus.org/oss/lv2/meters#dBTPstereo",
    "http://gareus.org/oss/lv2/meters#DINmono",
    "http://gareus.org/oss/lv2/meters#DINstereo",
    "http://gareus.org/oss/lv2/meters#dr14mono",
    "http://gareus.org/oss/lv2/meters#dr14stereo",
    "http://gareus.org/oss/lv2/meters#EBUmono",
    "http://gareus.org/oss/lv2/meters#EBUr128",
    "http://gareus.org/oss/lv2/meters#EBUstereo",
    "http://gareus.org/oss/lv2/meters#goniometer",
    "http://gareus.org/oss/lv2/meters#K12mono",
    "http://gareus.org/oss/lv2/meters#K12stereo",
    "http://gareus.org/oss/lv2/meters#K14mono",
    "http://gareus.org/oss/lv2/meters#K14stereo",
    "http://gareus.org/oss/lv2/meters#K20mono",
    "http://gareus.org/oss/lv2/meters#K20stereo",
    "http://gareus.org/oss/lv2/meters#NORmono",
    "http://gareus.org/oss/lv2/meters#NORstereo",
    "http://gareus.org/oss/lv2/meters#phasewheel",
    "http://gareus.org/oss/lv2/meters#SigDistHist",
    "http://gareus.org/oss/lv2/meters#spectr30mono",
    "http://gareus.org/oss/lv2/meters#spectr30stereo",
    "http://gareus.org/oss/lv2/meters#stereoscope",
    "http://gareus.org/oss/lv2/meters#TPnRMSmono",
    "http://gareus.org/oss/lv2/meters#TPnRMSstereo",
    "http://gareus.org/oss/lv2/meters#VUmono",
    "http://gareus.org/oss/lv2/meters#VUstereo",
    "http://gareus.org/oss/lv2/mixtri#lv2",
    "http://gareus.org/oss/lv2/onsettrigger#bassdrum_mono",
    "http://gareus.org/oss/lv2/onsettrigger#bassdrum_stereo",
    "http://gareus.org/oss/lv2/sisco#3chan",
    "http://gareus.org/oss/lv2/sisco#4chan",
    "http://gareus.org/oss/lv2/sisco#Mono",
    "http://gareus.org/oss/lv2/sisco#Stereo",
    "http://gareus.org/oss/lv2/tuna#one",
    "http://gareus.org/oss/lv2/tuna#two",
    "http://github.com/nicklan/drmr",
    "http://invadarecords.com/plugins/lv2/meter",
    "http://kxstudio.sf.net/carla/plugins/carlapatchbay",
    "http://kxstudio.sf.net/carla/plugins/carlapatchbay16",
    "http://kxstudio.sf.net/carla/plugins/carlapatchbay32",
    "http://kxstudio.sf.net/carla/plugins/carlapatchbay3s",
    "http://kxstudio.sf.net/carla/plugins/carlarack",
    "http://kxstudio.sf.net/carla/plugins/bigmeter",
    "http://kxstudio.sf.net/carla/plugins/midipattern",
    "http://kxstudio.sf.net/carla/plugins/midisequencer",
    "http://kxstudio.sf.net/carla/plugins/notes",
    "http://linuxsampler.org/plugins/linuxsampler",
    "http://lv2plug.in/plugins/eg-scope#Mono",
    "http://lv2plug.in/plugins/eg-scope#Stereo",
    "http://pianoteq.com/lv2/Pianoteq4",
    "http://pianoteq.com/lv2/Pianoteq4_5chan",
    "http://samplv1.sourceforge.net/lv2",
    "http://teragonaudio.com/BeatCounter.html",
    "http://teragonaudio.com/ExtraNotes.html",
    "http://www.klangfreund.com/lufsmeter",
    "http://www.klangfreund.com/lufsmetermultichannel",
    "http://www.wodgod.com/newtonator/1.0",
    "https://github.com/HiFi-LoFi/KlangFalter",
# FIXME: These are temporarily blacklisted because they need fixing or the modguis are not good enough for the live-ISO
    #"http://calf.sourceforge.net/plugins/eq5",
    #"http://calf.sourceforge.net/plugins/Equalizer5Band",
    #"http://calf.sourceforge.net/plugins/Filter",
    #"http://calf.sourceforge.net/plugins/Filterclavier",
    #"http://calf.sourceforge.net/plugins/Flanger",
    #"http://calf.sourceforge.net/plugins/Monosynth",
    #"http://calf.sourceforge.net/plugins/Pulsator",
    #"http://distrho.sf.net/plugins/PingPongPan",
    #"http://drobilla.net/plugins/blop/sawtooth",
    #"http://drobilla.net/plugins/blop/square",
    #"http://drobilla.net/plugins/blop/triangle",
    #"http://drobilla.net/plugins/fomp/pulse_vco",
    #"http://drobilla.net/plugins/fomp/rec_vco",
    #"http://drobilla.net/plugins/fomp/saw_vco",
    #"http://guitarix.sourceforge.net/plugins/gx_amp_stereo#GUITARIX_ST",
    #"http://guitarix.sourceforge.net/plugins/gx_barkgraphiceq_#_barkgraphiceq_",
    #"http://guitarix.sourceforge.net/plugins/gx_cabinet#CABINET",
    #"http://guitarix.sourceforge.net/plugins/gx_chorus_stereo#_chorus_stereo",
    #"http://guitarix.sourceforge.net/plugins/gx_compressor#_compressor",
    #"http://guitarix.sourceforge.net/plugins/gx_cstb_#_cstb_",
    #"http://guitarix.sourceforge.net/plugins/gx_delay_stereo#_delay_stereo",
    #"http://guitarix.sourceforge.net/plugins/gx_detune_#_detune_",
    #"http://guitarix.sourceforge.net/plugins/gx_digital_delay_#_digital_delay_",
    #"http://guitarix.sourceforge.net/plugins/gx_digital_delay_st_#_digital_delay_st_",
    #"http://guitarix.sourceforge.net/plugins/gx_duck_delay_#_duck_delay_",
    #"http://guitarix.sourceforge.net/plugins/gx_duck_delay_st_#_duck_delay_st_",
    #"http://guitarix.sourceforge.net/plugins/gx_echo_stereo#_echo_stereo",
    #"http://guitarix.sourceforge.net/plugins/gx_expander#_expander",
    #"http://guitarix.sourceforge.net/plugins/gx_flanger#_flanger",
    #"http://guitarix.sourceforge.net/plugins/gx_fumaster_#_fumaster_",
    #"http://guitarix.sourceforge.net/plugins/gx_fuzz_#fuzz_",
    #"http://guitarix.sourceforge.net/plugins/gx_fuzzface_#_fuzzface_",
    #"http://guitarix.sourceforge.net/plugins/gx_fuzzfacefm_#_fuzzfacefm_",
    #"http://guitarix.sourceforge.net/plugins/gx_graphiceq_#_graphiceq_",
    #"http://guitarix.sourceforge.net/plugins/gx_hfb_#_hfb_",
    #"http://guitarix.sourceforge.net/plugins/gx_hornet_#_hornet_",
    #"http://guitarix.sourceforge.net/plugins/gx_jcm800pre_#_jcm800pre_",
    #"http://guitarix.sourceforge.net/plugins/gx_jcm800pre_st#_jcm800pre_st",
    #"http://guitarix.sourceforge.net/plugins/gx_livelooper_#_livelooper_",
    #"http://guitarix.sourceforge.net/plugins/gx_mbcompressor_#_mbcompressor_",
    #"http://guitarix.sourceforge.net/plugins/gx_mbdelay_#_mbdelay_",
    #"http://guitarix.sourceforge.net/plugins/gx_mbdistortion_#_mbdistortion_",
    #"http://guitarix.sourceforge.net/plugins/gx_mbecho_#_mbecho_",
    #"http://guitarix.sourceforge.net/plugins/gx_mbreverb_#_mbreverb_",
    #"http://guitarix.sourceforge.net/plugins/gx_muff_#_muff_",
    #"http://guitarix.sourceforge.net/plugins/gx_phaser#_phaser",
    #"http://guitarix.sourceforge.net/plugins/gx_redeye#bigchump",
    #"http://guitarix.sourceforge.net/plugins/gx_redeye#chump",
    #"http://guitarix.sourceforge.net/plugins/gx_redeye#vibrochump",
    #"http://guitarix.sourceforge.net/plugins/gx_reverb_stereo#_reverb_stereo",
    #"http://guitarix.sourceforge.net/plugins/gx_room_simulator_#_room_simulator_",
    #"http://guitarix.sourceforge.net/plugins/gx_scream_#_scream_",
    #"http://guitarix.sourceforge.net/plugins/gx_shimmizita_#_shimmizita_",
    #"http://guitarix.sourceforge.net/plugins/gx_studiopre#studiopre",
    #"http://guitarix.sourceforge.net/plugins/gx_studiopre_st#studiopre_st",
    #"http://guitarix.sourceforge.net/plugins/gx_susta_#_susta_",
    #"http://guitarix.sourceforge.net/plugins/gx_switched_tremolo_#_switched_tremolo_",
    #"http://guitarix.sourceforge.net/plugins/gx_tremolo#_tremolo",
    #"http://guitarix.sourceforge.net/plugins/gx_vibe_#_vibe_",
    #"http://guitarix.sourceforge.net/plugins/gx_vibe_#_vibe_mono",
    #"http://guitarix.sourceforge.net/plugins/gx_zita_rev1_stereo#_zita_rev1_stereo",
    #"http://guitarix.sourceforge.net/plugins/gxautowah#autowah",
    #"http://guitarix.sourceforge.net/plugins/gxautowah#wah",
    #"http://guitarix.sourceforge.net/plugins/gxbooster#booster",
    #"http://guitarix.sourceforge.net/plugins/gxechocat#echocat",
    #"http://guitarix.sourceforge.net/plugins/gxmetal_amp#metal_amp",
    #"http://guitarix.sourceforge.net/plugins/gxmetal_head#metal_head",
    #"http://guitarix.sourceforge.net/plugins/gxtilttone#tilttone",
    #"http://guitarix.sourceforge.net/plugins/gxts9#ts9sim",
    #"http://guitarix.sourceforge.net/plugins/gxtubedelay#tubedelay",
    #"http://guitarix.sourceforge.net/plugins/gxtubetremelo#tubetremelo",
    #"http://guitarix.sourceforge.net/plugins/gxtubevibrato#tubevibrato",
    #"http://guitarix.sourceforge.net/plugins/gxtuner#tuner",
    #"http://moddevices.com/plugins/caps/AmpVTS",
    #"http://moddevices.com/plugins/caps/AutoFilter",
    #"http://moddevices.com/plugins/caps/CabinetIV",
    #"http://moddevices.com/plugins/caps/ChorusI",
    #"http://moddevices.com/plugins/caps/Compress",
    #"http://moddevices.com/plugins/caps/CompressX2",
    #"http://moddevices.com/plugins/caps/Eq10",
    #"http://moddevices.com/plugins/caps/Eq10X2",
    #"http://moddevices.com/plugins/caps/Eq4p",
    #"http://moddevices.com/plugins/caps/Fractal",
    #"http://moddevices.com/plugins/caps/Narrower",
    #"http://moddevices.com/plugins/caps/Noisegate",
    #"http://moddevices.com/plugins/caps/PhaserII",
    #"http://moddevices.com/plugins/caps/Plate",
    #"http://moddevices.com/plugins/caps/PlateX2",
    #"http://moddevices.com/plugins/caps/Saturate",
    #"http://moddevices.com/plugins/caps/Scape",
    #"http://moddevices.com/plugins/caps/Spice",
    #"http://moddevices.com/plugins/caps/SpiceX2",
    #"http://moddevices.com/plugins/caps/ToneStack",
    #"http://moddevices.com/plugins/caps/White", # ??
    #"http://moddevices.com/plugins/caps/Wider",
    #"http://moddevices.com/plugins/mda/Delay",
    #"http://moddevices.com/plugins/mda/Overdrive",
    #"http://moddevices.com/plugins/mda/Tracker",
    #"http://moddevices.com/plugins/mda/VocInput",
    #"http://moddevices.com/plugins/mod-devel/Harmonizer2",
    #"http://moddevices.com/plugins/mod-devel/HarmonizerCS",
    #"http://moddevices.com/plugins/mod-devel/SwitchTrigger4",
    #"http://moddevices.com/plugins/mod-devel/SuperWhammy",
    #"http://plugin.org.uk/swh-plugins/analogueOsc",
    #"http://plugin.org.uk/swh-plugins/delayorama",
    #"http://plugin.org.uk/swh-plugins/tapeDelay",
    #"http://plugin.org.uk/swh-plugins/harmonicGen",
]

# Whitelisted plugins, for testing purposes
WHITELIST = [
    "http://distrho.sf.net/plugins/Nekobi",
    "http://moddevices.com/plugins/tap/autopan",
    "http://moddevices.com/plugins/tap/chorusflanger",
    #"http://moddevices.com/plugins/tap/deesser",
    "http://moddevices.com/plugins/tap/doubler",
    "http://moddevices.com/plugins/tap/dynamics",
    "http://moddevices.com/plugins/tap/dynamics-st",
    "http://moddevices.com/plugins/tap/echo",
    "http://moddevices.com/plugins/tap/eq",
    "http://moddevices.com/plugins/tap/eqbw",
    "http://moddevices.com/plugins/tap/limiter",
    "http://moddevices.com/plugins/tap/pinknoise",
    #"http://moddevices.com/plugins/tap/pitch",
    "http://moddevices.com/plugins/tap/reflector",
    "http://moddevices.com/plugins/tap/reverb",
    "http://moddevices.com/plugins/tap/rotspeak",
    "http://moddevices.com/plugins/tap/sigmoid",
    "http://moddevices.com/plugins/tap/tremolo",
    "http://moddevices.com/plugins/tap/tubewarmth",
    "http://moddevices.com/plugins/tap/vibrato",
    "http://moddevices.com/plugins/mod-devel/Gain",
    "http://moddevices.com/plugins/mod-devel/Gain2x2",
]

# List of plugins available in the mod cloud
CLOUD_PLUGINS = [
    "http://distrho.sf.net/plugins/MVerb",
    "http://distrho.sf.net/plugins/PingPongPan",
    "http://drobilla.net/plugins/blop/sawtooth",
    "http://drobilla.net/plugins/blop/square",
    "http://drobilla.net/plugins/blop/triangle",
    "http://drobilla.net/plugins/fomp/autowah",
    "http://drobilla.net/plugins/fomp/cs_phaser1",
    "http://drobilla.net/plugins/fomp/pulse_vco",
    "http://drobilla.net/plugins/fomp/rec_vco",
    "http://drobilla.net/plugins/fomp/saw_vco",
    "http://moddevices.com/plugins/caps/AmpVTS",
    "http://moddevices.com/plugins/caps/AutoFilter",
    "http://moddevices.com/plugins/caps/CEO",
    "http://moddevices.com/plugins/caps/CabinetIV",
    "http://moddevices.com/plugins/caps/ChorusI",
    "http://moddevices.com/plugins/caps/Click",
    "http://moddevices.com/plugins/caps/Compress",
    "http://moddevices.com/plugins/caps/CompressX2",
    "http://moddevices.com/plugins/caps/Eq10",
    "http://moddevices.com/plugins/caps/Eq10X2",
    "http://moddevices.com/plugins/caps/Eq4p",
    "http://moddevices.com/plugins/caps/Fractal",
    "http://moddevices.com/plugins/caps/Narrower",
    "http://moddevices.com/plugins/caps/Noisegate",
    "http://moddevices.com/plugins/caps/PhaserII",
    "http://moddevices.com/plugins/caps/Plate",
    "http://moddevices.com/plugins/caps/PlateX2",
    "http://moddevices.com/plugins/caps/Saturate",
    "http://moddevices.com/plugins/caps/Scape",
    "http://moddevices.com/plugins/caps/Sin",
    "http://moddevices.com/plugins/caps/Spice",
    "http://moddevices.com/plugins/caps/SpiceX2",
    "http://moddevices.com/plugins/caps/ToneStack",
    "http://moddevices.com/plugins/caps/White",
    "http://moddevices.com/plugins/caps/Wider",
    "http://moddevices.com/plugins/mda/Ambience",
    "http://moddevices.com/plugins/mda/Bandisto",
    "http://moddevices.com/plugins/mda/BeatBox",
    "http://moddevices.com/plugins/mda/Combo",
    "http://moddevices.com/plugins/mda/DX10",
    "http://moddevices.com/plugins/mda/DeEss",
    "http://moddevices.com/plugins/mda/Degrade",
    "http://moddevices.com/plugins/mda/Delay",
    "http://moddevices.com/plugins/mda/Detune",
    "http://moddevices.com/plugins/mda/Dither",
    "http://moddevices.com/plugins/mda/DubDelay",
    "http://moddevices.com/plugins/mda/Dynamics",
    "http://moddevices.com/plugins/mda/EPiano",
    "http://moddevices.com/plugins/mda/Image",
    "http://moddevices.com/plugins/mda/JX10",
    "http://moddevices.com/plugins/mda/Leslie",
    "http://moddevices.com/plugins/mda/Limiter",
    "http://moddevices.com/plugins/mda/Loudness",
    "http://moddevices.com/plugins/mda/MultiBand",
    "http://moddevices.com/plugins/mda/Overdrive",
    "http://moddevices.com/plugins/mda/Piano",
    "http://moddevices.com/plugins/mda/RePsycho",
    "http://moddevices.com/plugins/mda/RezFilter",
    "http://moddevices.com/plugins/mda/RingMod",
    "http://moddevices.com/plugins/mda/RoundPan",
    "http://moddevices.com/plugins/mda/Shepard",
    "http://moddevices.com/plugins/mda/Splitter",
    "http://moddevices.com/plugins/mda/Stereo",
    "http://moddevices.com/plugins/mda/SubSynth",
    "http://moddevices.com/plugins/mda/TalkBox",
    "http://moddevices.com/plugins/mda/TestTone",
    "http://moddevices.com/plugins/mda/ThruZero",
    "http://moddevices.com/plugins/mda/Tracker",
    "http://moddevices.com/plugins/mda/Transient",
    "http://moddevices.com/plugins/mda/VocInput",
    "http://moddevices.com/plugins/mda/Vocoder",
    #"http://moddevices.com/plugins/mod-devel/2Voices",
    "http://moddevices.com/plugins/mod-devel/BandPassFilter",
    #"http://moddevices.com/plugins/mod-devel/Capo",
    "http://moddevices.com/plugins/mod-devel/CrossOver2",
    "http://moddevices.com/plugins/mod-devel/CrossOver3",
    #"http://moddevices.com/plugins/mod-devel/Drop",
    "http://moddevices.com/plugins/mod-devel/Gain",
    "http://moddevices.com/plugins/mod-devel/Gain2x2",
    #"http://moddevices.com/plugins/mod-devel/Harmonizer",
    #"http://moddevices.com/plugins/mod-devel/Harmonizer2",
    #"http://moddevices.com/plugins/mod-devel/HarmonizerCS",
    "http://moddevices.com/plugins/mod-devel/HighPassFilter",
    "http://moddevices.com/plugins/mod-devel/LowPassFilter",
    #"http://moddevices.com/plugins/mod-devel/SuperCapo",
    #"http://moddevices.com/plugins/mod-devel/SuperWhammy",
    "http://moddevices.com/plugins/mod-devel/SwitchBox2",
    "http://moddevices.com/plugins/mod-devel/SwitchTrigger4",
    "http://moddevices.com/plugins/mod-devel/ToggleSwitch4",
    "http://moddevices.com/plugins/sooperlooper",
    "http://moddevices.com/plugins/tap/autopan",
    "http://moddevices.com/plugins/tap/chorusflanger",
    "http://moddevices.com/plugins/tap/deesser",
    "http://moddevices.com/plugins/tap/doubler",
    "http://moddevices.com/plugins/tap/dynamics",
    "http://moddevices.com/plugins/tap/dynamics-st",
    "http://moddevices.com/plugins/tap/echo",
    "http://moddevices.com/plugins/tap/eq",
    "http://moddevices.com/plugins/tap/eqbw",
    "http://moddevices.com/plugins/tap/limiter",
    "http://moddevices.com/plugins/tap/pinknoise",
    "http://moddevices.com/plugins/tap/pitch",
    "http://moddevices.com/plugins/tap/reflector",
    "http://moddevices.com/plugins/tap/reverb",
    "http://moddevices.com/plugins/tap/rotspeak",
    "http://moddevices.com/plugins/tap/sigmoid",
    "http://moddevices.com/plugins/tap/tremolo",
    "http://moddevices.com/plugins/tap/tubewarmth",
    "http://moddevices.com/plugins/tap/vibrato",
]

# initialize
def init():
    global W

    W.load_all()
    refresh()

# refresh everything
# plugins are not truly scanned here, only later per request
def refresh():
    global W, BUNDLES, PLUGINS, PLUGNFO, PLUGNFOk

    BUNDLES  = []
    PLUGINS  = W.get_all_plugins()
    PLUGNFO  = {}
    PLUGNFOk = []

    # Make a list of all installed bundles
    for p in PLUGINS:
        bundles = lilv.lilv_plugin_get_data_uris(p.me)

        # store empty dict for later
        uri = p.get_uri().as_uri()
        PLUGNFO[uri] = {}
        PLUGNFOk.append(uri)

        it = lilv.lilv_nodes_begin(bundles)
        while not lilv.lilv_nodes_is_end(bundles, it):
            bundle = lilv.lilv_nodes_get(bundles, it)
            it     = lilv.lilv_nodes_next(bundles, it)

            if bundle is None:
                continue
            if not lilv.lilv_node_is_uri(bundle):
                continue

            bundle = os.path.dirname(lilv.lilv_uri_to_path(lilv.lilv_node_as_uri(bundle)))

            if not bundle.endswith(os.sep):
                bundle += os.sep

            if bundle not in BUNDLES:
                BUNDLES.append(bundle)

# get all available plugins
# this is trigger scanning of all plugins
# returned value depends on MODGUI_SHOW_MODE
def get_all_plugins():
    global W, PLUGINS, PLUGNFO, PLUGNFOk

    ret = []

    for p in PLUGINS:
        uri = p.get_uri().as_uri()

        if uri in BLACKLIST:
            continue
        if MODGUI_SHOW_MODE == 2 and uri not in CLOUD_PLUGINS:
            continue
        if MODGUI_SHOW_MODE == 3 and uri not in WHITELIST:
            continue

        # check if it's already cached
        if uri in PLUGNFOk and PLUGNFO[uri]:
            if PLUGNFO[uri]['gui'] or MODGUI_SHOW_MODE != 1:
                ret.append(PLUGNFO[uri])
            continue

        # skip plugins without modgui if so requested
        if MODGUI_SHOW_MODE == 1 and not plugin_has_modgui(W, p):
            continue

        # get new info
        PLUGNFO[uri] = get_plugin_info2(W, p)
        ret.append(PLUGNFO[uri])

    return ret

# get a specific plugin
# NOTE: may throw
def get_plugin_info(uri):
    global W, PLUGINS, PLUGNFO, PLUGNFOk

    # check if it exists
    if uri not in PLUGNFOk:
        raise Exception

    # check if it's already cached
    if PLUGNFO[uri]:
        return PLUGNFO[uri]

    # look for it
    for p in PLUGINS:
        if p.get_uri().as_uri() != uri:
            continue
        # found it
        print("NOTICE: Plugin '%s' was not cached, scanning it now..." % uri)
        PLUGNFO[uri] = get_plugin_info2(W, p)
        return PLUGNFO[uri]

    # not found
    raise Exception

# get all available pedalboards (ie, plugins with pedalboard type)
def get_pedalboards(asDictionary):
    global W, PLUGINS

    # define needed namespaces
    rdf      = NS(W, lilv.LILV_NS_RDF)
    rdfs     = NS(W, lilv.LILV_NS_RDFS)
    pset     = NS(W, "http://lv2plug.in/ns/ext/presets#")
    modpedal = NS(W, "http://moddevices.com/ns/modpedal#")

    # fill in presets for a plugin
    def get_presets(p):
        presets = p.get_related(pset.Preset)
        def get_preset_data(preset):
            W.load_resource(preset.me)
            label = W.find_nodes(preset.me, rdfs.label.me, None).get_first().as_string()
            return { 'uri': preset.as_string(), 'label': label }
        return list(LILV_FOREACH(presets, get_preset_data))

    # check each plugin for a pedalboard type
    if asDictionary:
        pedalboards = {}
    else:
        pedalboards = []

    for pedalboard in PLUGINS:
        # check if the plugin is a pedalboard
        def fill_in_type(node):
            return node.as_string()
        plugin_types = [i for i in LILV_FOREACH(pedalboard.get_value(rdf.type_), fill_in_type)]

        if "http://moddevices.com/ns/modpedal#Pedalboard" not in plugin_types:
            continue

        # ready
        pedalboard = {
            'bundlepath': lilv.lilv_uri_to_path(pedalboard.get_bundle_uri().as_string()),
            'name': pedalboard.get_name().as_string(),
            'uri':  pedalboard.get_uri().as_string(),
            'screenshot': lilv.lilv_uri_to_path(pedalboard.get_value(modpedal.screenshot).get_first().as_string() or ""),
            'thumbnail':  lilv.lilv_uri_to_path(pedalboard.get_value(modpedal.thumbnail).get_first().as_string() or ""),
            'width':  pedalboard.get_value(modpedal.width).get_first().as_int(),
            'height': pedalboard.get_value(modpedal.height).get_first().as_int(),
            'presets': get_presets(pedalboard)
        }

        if asDictionary:
            pedalboards[pedalboard['uri']] = pedalboard
        else:
            pedalboards.append(pedalboard)

    return pedalboards

# add a bundle to our lilv world
# returns true if the bundle was added
def add_bundle_to_lilv_world(bundlepath, returnPlugins = False):
    global W, BUNDLES, PLUGINS, PLUGNFO, PLUGNFOk

    # lilv wants the last character as the separator
    if not bundlepath.endswith(os.sep):
        bundlepath += os.sep

    # stop now if bundle is already loaded
    if bundlepath in BUNDLES:
        return [] if returnPlugins else False

    # In case returnPlugins is used
    addedPlugins = []

    # convert bundle string into a lilv node
    bundlenode = lilv.lilv_new_file_uri(W.me, None, bundlepath)

    # load the bundle
    W.load_bundle(bundlenode)

    # free bundlenode, no longer needed
    lilv.lilv_node_free(bundlenode)

    # add to loaded list
    BUNDLES.append(bundlepath)

    # fill in for any new plugins that appeared
    for p in PLUGINS:
        uri = p.get_uri().as_uri()

        # check if it's already cached
        if uri in PLUGNFOk and PLUGNFO[uri]:
            continue

        # get new info
        PLUGNFO[uri] = get_plugin_info2(W, p)
        PLUGNFOk.append(uri)

        if returnPlugins:
            addedPlugins.append(uri)

    return addedPlugins if returnPlugins else True

# remove a bundle to our lilv world
# returns true if the bundle was removed
def remove_bundle_to_lilv_world(bundlepath, returnPlugins = False):
    global W, BUNDLES, PLUGINS, PLUGNFO, PLUGNFOk

    # lilv wants the last character as the separator
    if not bundlepath.endswith(os.sep):
        bundlepath += os.sep

    # stop now if bundle is not loaded
    if bundlepath not in BUNDLES:
        return [] if returnPlugins else False

    # In case returnPlugins is used
    removedPlugins = []

    # remove from loaded list
    BUNDLES.remove(bundlepath)

    # remove all plugins that are present on that bundle
    for p in PLUGINS:
        uri = p.get_uri().as_uri()

        if uri not in PLUGNFOk:
            continue

        bundles = lilv.lilv_plugin_get_data_uris(p.me)

        it = lilv.lilv_nodes_begin(bundles)
        while not lilv.lilv_nodes_is_end(bundles, it):
            bundle = lilv.lilv_nodes_get(bundles, it)
            it     = lilv.lilv_nodes_next(bundles, it)

            if bundle is None:
                continue
            if not lilv.lilv_node_is_uri(bundle):
                continue

            bundle = os.path.dirname(lilv.lilv_uri_to_path(lilv.lilv_node_as_uri(bundle)))

            if not bundle.endswith(os.sep):
                bundle += os.sep

            if bundlepath != bundle:
                continue

            PLUGNFOk.remove(uri)
            PLUGNFO.pop(uri)

            if returnPlugins:
                removedPlugins.append(uri)

    # convert bundle string into a lilv node
    bundlenode = lilv.lilv_new_file_uri(W.me, None, bundlepath)

    # unload the bundle
    lilv.lilv_world_unload_bundle(W.me, bundlenode)

    # free bundlenode, no longer needed
    lilv.lilv_node_free(bundlenode)

    # refresh lilv plugins
    PLUGINS = W.get_all_plugins()

    return removedPlugins if returnPlugins else True
