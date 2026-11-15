// SPDX-FileCopyrightText: 2012-2026 MOD Audio UG
// SPDX-License-Identifier: AGPL-3.0-or-later

// Run with: node test/test_stereo.js
//
// stereoCounterpart is the only guessing part of the stereo cable feature, so it is the
// only part worth a test. Everything downstream of it checks the guess against a port
// that either exists or does not.

const assert = require('assert')
const fs = require('fs')
const path = require('path')

// html/js/utils/*.js are plain globals, no module system
eval(fs.readFileSync(path.join(__dirname, '..', 'html', 'js', 'utils', 'stereo.js'), 'utf8'))

function pairs(symbol, partner, first) {
    const got = stereoCounterpart(symbol)
    assert.notStrictEqual(got, null, `${symbol} should have a counterpart`)
    assert.strictEqual(got.symbol, partner, `${symbol} -> ${got.symbol}, expected ${partner}`)
    assert.strictEqual(got.first, first, `${symbol} first=${got.first}, expected ${first}`)
}

function mono(symbol) {
    assert.strictEqual(stereoCounterpart(symbol), null, `${symbol} should have no counterpart`)
}

// A symbol that merely ends in l or r still yields a guess. That is deliberate: the
// caller only draws a pair when a port of that exact name, direction and type exists,
// and nothing is called "signar". Refusing to guess here is what broke real plugins.
function guessesNothingReal(symbol, guess) {
    const got = stereoCounterpart(symbol)
    assert.notStrictEqual(got, null, `${symbol} should still produce a guess`)
    assert.strictEqual(got.symbol, guess, `${symbol} -> ${got.symbol}, expected ${guess}`)
}

// separator-delimited sides, both directions
pairs('in_l', 'in_r', true)
pairs('in_r', 'in_l', false)
pairs('out-l', 'out-r', true)
pairs('audio_left', 'audio_right', true)
pairs('audio_right', 'audio_left', false)

// the whole symbol is the side
pairs('l', 'r', true)
pairs('R', 'L', false)
pairs('Left', 'Right', true)

// a case change is enough on its own, and casing is carried over
pairs('outL', 'outR', true)
pairs('InR', 'InL', false)
pairs('OUT_L', 'OUT_R', true)

// ...but so is no case change at all. Real symbols, from plugins installed here and
// from https://github.com/sejerpz/mod-ui/pull/12: tap/reverb names its ports inputl
// and inputr, and refusing those meant its cables never merged.
pairs('inputl', 'inputr', true)          // tap/reverb
pairs('inputr', 'inputl', false)
pairs('InputL', 'InputR', true)          // tap/autopan, the same plugin pair
pairs('outl', 'outr', true)              // caps Plate, Scape, Wider
pairs('inl', 'inr', true)                // caps SpiceX2, PlateX2
pairs('inputleft', 'inputright', true)   // tap-echo, a full word and no separator
pairs('OUT1L', 'OUT1R', true)            // switchbox, a digit before the side
pairs('In1L', 'In1R', true)

// numbered channels, including the second pair of a four-channel plugin
pairs('out1', 'out2', true)
pairs('out2', 'out1', false)
pairs('capture_1', 'capture_2', true)
pairs('playback_2', 'playback_1', false)
pairs('out_3', 'out_4', true)
pairs('out_4', 'out_3', false)
pairs('lv2_audio_out_01', 'lv2_audio_out_02', true)  // zero padding survives

// symbols that name no side at all
mono('in')
mono('output')
mono('sidechain')
mono('out_0')        // channel numbering starts at 1

// words that merely end in l or r: a guess is made, but it can never match a port
guessesNothingReal('signal', 'signar')
guessesNothingReal('SIGNAL', 'SIGNAR')
guessesNothingReal('pedal', 'pedar')
guessesNothingReal('mixer', 'mixel')
guessesNothingReal('monitor', 'monitol')
guessesNothingReal('bright', 'bleft')

// a guessed partner is not a real one: these only pair because the port exists
assert.strictEqual(stereoCounterpart('gain_1').symbol, 'gain_2')

console.log('stereo: all assertions passed')
