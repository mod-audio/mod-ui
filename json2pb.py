#!/usr/bin/env python3

import os

# configurable bits start here

pbname = "AI Generated Pedalboard"
pbjson = {
    "Mutant: Driven_Breakup": {
        "URI": "http://VeJaPlugins.com/plugins/Release/Mutant",
        "params": {
            "pregain": 60.0,
            "postgain": 90.0,
            "presence": 100.0,
            "depth": 50.0,
            "Bass": 50.0,
            "Mid": 50.75,
            "Treble": 50.0,
            "Drive": 1.0,
            "Drivegain": 30.0,
            "DriveVol": 25.0,
            "Volume": 60.0
        }
    },
    "faIR Modern: Tool Pot": {
        "URI": "http://http://JHLM.com/plugins/mod-devel/faIR-cabsim",
        "params": {
            "Model": 9.0
        }
    },
    # TESTING
    #"ir": { "URI": "http://gareus.org/oss/lv2/zeroconvolv#CfgMono" },
}

# configurable bits stop here

os.mkdir('aigen.pedalboard')

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
    # unused in MOD, used only for local testing
    'http://distrho.sf.net/plugins/Kars': {
        'in': [],
        'out': [ 'lv2_audio_out_1' ],
    },
    'https://distrho.kx.studio/plugins/oneknob#BrickWallLimiter': {
        'in': [ 'lv2_audio_in_1', 'lv2_audio_in_2' ],
        'out': [ 'lv2_audio_out_1', 'lv2_audio_out_2' ]
    },
}

pluginuris = tuple(plugin['URI'] for plugin in pbjson.values())

# create connections
connections = []
for i, pluginuri in enumerate(pluginuris):
    audioports = knownAudioPortSymbols[pluginuri]

    if len(audioports['out']) == 0:
        raise Exception('plugin has no output ports')

    if i == len(pbjson) - 1:
        connections.append(('playback_1', f"s{i+1}/{audioports['out'][0]}"))
        if len(audioports['in']) >= 2:
            connections.append(('playback_2', f"s{i+1}/{audioports['out'][1]}"))
        else:
            connections.append(('playback_2', f"s{i+1}/{audioports['out'][0]}"))
        break

    if i == 0:
        connections.append((f"s{i+1}/{audioports['in'][0]}", 'capture_1'))
        if len(audioports['in']) >= 2:
            connections.append((f"s{i+1}/{audioports['in'][1]}", 'capture_2'))

    nextaudioports = knownAudioPortSymbols[pluginuris[i+1]]

    if len(nextaudioports['in']) == 0:
        raise Exception('next plugin has no input ports')

    connections.append((f"s{i+2}/{nextaudioports['in'][0]}", f"s{i+1}/{audioports['out'][0]}"))

    if len(nextaudioports['in']) >= 2:
        if len(audioports['out']) >= 2:
            connections.append((f"s{i+2}/{nextaudioports['in'][1]}", f"s{i+1}/{audioports['out'][1]}"))
        else:
            connections.append((f"s{i+2}/{nextaudioports['in'][1]}", f"s{i+1}/{audioports['out'][0]}"))

    elif len(audioports['out']) >= 2:
        connections.append((f"s{i+2}/{nextaudioports['in'][0]}", f"s{i+1}/{audioports['out'][1]}"))

pedalboard = f'''
@prefix atom:  <http://lv2plug.in/ns/ext/atom#> .
@prefix doap:  <http://usefulinc.com/ns/doap#> .
@prefix ingen: <http://drobilla.net/ns/ingen#> .
@prefix lv2:   <http://lv2plug.in/ns/lv2core#> .
@prefix mod:   <http://moddevices.com/ns/mod#> .
@prefix pedal: <http://moddevices.com/ns/modpedal#> .

<>
    lv2:prototype ingen:GraphPrototype ;
    doap:name """{pbname}""" ;
    ingen:polyphony 1 ;
    lv2:port <capture_1> ,
             <capture_2> ,
             <playback_1> ,
             <playback_2> ,
             <midi_separated_mode> ;
    ingen:arc _:{',_:'.join('b'+str(i+1) for i in range(len(connections)))} ;
    ingen:block <{'>,<'.join('s'+str(i+1) for i in range(len(pbjson)))}> ;
    a lv2:Plugin ,
        ingen:Graph ,
        pedal:Pedalboard .

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

'''

instanceNumber = 0
for plugin in pbjson.values():
    instanceNumber += 1
    instanceSymbol = f's{instanceNumber}'
    pedalboard += f'''<{instanceSymbol}>
    ingen:canvasX {instanceNumber * 1000} ;
    ingen:canvasY 400 ;
    ingen:enabled true ;
    lv2:port <{">,<".join(instanceSymbol+"/"+s for s in plugin.get('params',{}).keys())}> ;
    lv2:prototype <{plugin['URI']}> ;
    pedal:instanceNumber {instanceNumber} ;
    pedal:preset <> ;
    a ingen:Block .

'''

    for symbol in knownAudioPortSymbols[plugin['URI']]['in']:
        pedalboard += f'''<{instanceSymbol}/{symbol}>
    a lv2:AudioPort ,
        lv2:InputPort .

'''

    for symbol in knownAudioPortSymbols[plugin['URI']]['out']:
        pedalboard += f'''<{instanceSymbol}/{symbol}>
    a lv2:AudioPort ,
        lv2:OutputPort .

'''

    for symbol, value in plugin.get('params',{}).items():
        pedalboard += f'''<{instanceSymbol}/{symbol}>
    ingen:value {value} ;
    a lv2:ControlPort ,
        lv2:InputPort .

'''

for i, (head, tail) in enumerate(connections):
    pedalboard += f'''_:b{i+1}
    ingen:tail <{tail}> ;
    ingen:head <{head}> .

'''

with open('aigen.pedalboard/manifest.ttl', 'w') as fh:
    fh.write(pedalboard)

if 'http://gareus.org/oss/lv2/zeroconvolv#CfgMono' in pluginuris:
    instanceNumber = pluginuris.index('http://gareus.org/oss/lv2/zeroconvolv#CfgMono') + 1
    os.mkdir(f'aigen.pedalboard/effect-{instanceNumber}')
    with open(f'aigen.pedalboard/effect-{instanceNumber}/manifest.ttl', 'w') as fh:
        fh.write('''\
<effect.ttl>
        a <http://lv2plug.in/ns/ext/presets#Preset> ;
        <http://lv2plug.in/ns/lv2core#appliesTo> <http://gareus.org/oss/lv2/zeroconvolv#CfgMono> ;
        <http://www.w3.org/2000/01/rdf-schema#seeAlso> <effect.ttl> .
''')
    with open(f'aigen.pedalboard/effect-{instanceNumber}/effect.ttl', 'w') as fh:
        fh.write('''\
@prefix atom: <http://lv2plug.in/ns/ext/atom#> .
@prefix lv2: <http://lv2plug.in/ns/lv2core#> .
@prefix pset: <http://lv2plug.in/ns/ext/presets#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix state: <http://lv2plug.in/ns/ext/state#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<>
        a pset:Preset ;
        lv2:appliesTo <http://gareus.org/oss/lv2/zeroconvolv#CfgMono> ;
        state:state [
                <http://gareus.org/oss/lv2/zeroconvolv#channel_predelay> [
                        a atom:Vector ;
                        atom:childType atom:Int ;
                        rdf:value (
                                "0"^^xsd:int
                                "0"^^xsd:int
                                "0"^^xsd:int
                                "0"^^xsd:int
                        )
                ] ;
                <http://gareus.org/oss/lv2/zeroconvolv#predelay> "0"^^xsd:int ;
                <http://gareus.org/oss/lv2/zeroconvolv#artificial_latency> "0"^^xsd:int ;
                <http://gareus.org/oss/lv2/zeroconvolv#channel_gain> [
                        a atom:Vector ;
                        atom:childType atom:Float ;
                        rdf:value (
                                "1.0"^^xsd:float
                                "1.0"^^xsd:float
                                "1.0"^^xsd:float
                                "1.0"^^xsd:float
                        )
                ] ;
                <http://gareus.org/oss/lv2/zeroconvolv#gain> "1.0"^^xsd:float ;
                <http://gareus.org/oss/lv2/zeroconvolv#sum_inputs> false ;
                <http://gareus.org/oss/lv2/zeroconvolv#ir> <ir.wav>
        ] .
''')
