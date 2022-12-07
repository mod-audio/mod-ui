#!/usr/bin/env python3

pbjson = {
    'plugins': {
        'http://distrho.sf.net/plugins/Kars': {
            'release': 5,
            'volume': 17
        },
        'https://distrho.kx.studio/plugins/oneknob#BrickWallLimiter': {
            'threshold': -5
        }
    }
}

pbname = 'Default'
pbfilename = 'default'

# configurable bits stop here

knownAudioPortSymbols = {
    'https://github.com/michaelwillis/dragonfly-reverb': {
        'in': [ 'lv2_audio_in_1', 'lv2_audio_in_2' ],
        'out': [ 'lv2_audio_out_1', 'lv2_audio_out_2' ]
    },
    'urn:dragonfly:early': {
        'in': [ 'lv2_audio_in_1', 'lv2_audio_in_2' ],
        'out': [ 'lv2_audio_out_1', 'lv2_audio_out_2' ]
    },
    'urn:dragonfly:plate': {
        'in': [ 'lv2_audio_in_1', 'lv2_audio_in_2' ],
        'out': [ 'lv2_audio_out_1', 'lv2_audio_out_2' ]
    },
    'urn:dragonfly:room': {
        'in': [ 'lv2_audio_in_1', 'lv2_audio_in_2' ],
        'out': [ 'lv2_audio_out_1', 'lv2_audio_out_2' ]
    },
    'https://github.com/ninodewit/SHIRO-Plugins/plugins/shiroverb': {
        'in': [ 'lv2_audio_in_1' ],
        'out': [ 'lv2_audio_out_1', 'lv2_audio_out_2' ]
    },
    'http://VeJaPlugins.com/plugins/Release/Mutant': {
        'in': [ 'In' ],
        'out': [ 'Out' ]
    },
    'http://http://JHLM.com/plugins/mod-devel/faIR-cabsim': {
        'in': [ 'In' ],
        'out': [ 'Out' ]
    },
    'http://gareus.org/oss/lv2/zeroconvolv#CfgMono': {
        'in': [ 'in' ],
        'out': [ 'out' ]
    },
    # unused in MOD, only for local testing
    'http://distrho.sf.net/plugins/Kars': {
        'in': [],
        'out': [ 'lv2_audio_out_1' ],
    },
    'https://distrho.kx.studio/plugins/oneknob#BrickWallLimiter': {
        'in': [ 'lv2_audio_in_1', 'lv2_audio_in_2' ],
        'out': [ 'lv2_audio_out_1', 'lv2_audio_out_2' ]
    },
}

pedalboard = f'''
@prefix atom:  <http://lv2plug.in/ns/ext/atom#> .
@prefix doap:  <http://usefulinc.com/ns/doap#> .
@prefix ingen: <http://drobilla.net/ns/ingen#> .
@prefix lv2:   <http://lv2plug.in/ns/lv2core#> .
@prefix mod:   <http://moddevices.com/ns/mod#> .
@prefix pedal: <http://moddevices.com/ns/modpedal#> .

<capture_1>
    lv2:index 0 ;
    lv2:name "Capture 1" ;
    lv2:portProperty lv2:connectionOptional ;
    lv2:symbol "capture_1" ;
    a lv2:AudioPort ,
        lv2:InputPort .

<capture_2>
    lv2:index 1 ;
    lv2:name "Capture 2" ;
    lv2:portProperty lv2:connectionOptional ;
    lv2:symbol "capture_2" ;
    a lv2:AudioPort ,
        lv2:InputPort .

<playback_1>
    lv2:index 2 ;
    lv2:name "Playback 1" ;
    lv2:portProperty lv2:connectionOptional ;
    lv2:symbol "playback_1" ;
    a lv2:AudioPort ,
        lv2:OutputPort .

<playback_2>
    lv2:index 3 ;
    lv2:name "Playback 2" ;
    lv2:portProperty lv2:connectionOptional ;
    lv2:symbol "playback_2" ;
    a lv2:AudioPort ,
        lv2:OutputPort .

<midi_separated_mode>
    ingen:value 0 ;
    lv2:index 4 ;
    a atom:AtomPort ,
        lv2:InputPort .

<{pbfilename}.ttl>
    lv2:prototype ingen:GraphPrototype ;
    doap:name "{pbname}" ;
    ingen:polyphony 1 ;
    lv2:port <capture_1> ,
             <capture_2> ,
             <playback_1> ,
             <playback_2> ,
             <midi_separated_mode> ;
    ingen:block <{">,<".join("s"+str(i+1) for i in range(len(pbjson['plugins'])))}> ;
    a lv2:Plugin ,
        ingen:Graph ,
        pedal:Pedalboard .

'''

instanceNumber = 0
for uri, ports in pbjson['plugins'].items():
    instanceNumber += 1
    instanceSymbol = f's{instanceNumber}'
    pedalboard += f'''<{instanceSymbol}>
    ingen:canvasX {200 + instanceNumber * 500} ;
    ingen:canvasY 400 ;
    ingen:enabled true ;
    lv2:port <{">,<".join(instanceSymbol+"/"+s for s in ports.keys())}> ;
    lv2:prototype <{uri}> ;
    pedal:instanceNumber {instanceNumber} ;
    pedal:preset <> ;
    a ingen:Block .

'''

    for symbol, value in ports.items():
        pedalboard += f'''<{instanceSymbol}/{symbol}>
    ingen:value {value} ;
    a lv2:ControlPort ,
        lv2:InputPort .

'''

print(pedalboard)
