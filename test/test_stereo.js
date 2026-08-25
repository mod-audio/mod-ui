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

// case change stands in for a separator, and casing is carried over
pairs('outL', 'outR', true)
pairs('InR', 'InL', false)
pairs('OUT_L', 'OUT_R', true)

// numbered channels, including the second pair of a four-channel plugin
pairs('out1', 'out2', true)
pairs('out2', 'out1', false)
pairs('capture_1', 'capture_2', true)
pairs('playback_2', 'playback_1', false)
pairs('out_3', 'out_4', true)
pairs('out_4', 'out_3', false)
pairs('lv2_audio_out_01', 'lv2_audio_out_02', true)  // zero padding survives

// mono, and words that merely end in l or r
mono('in')
mono('output')
mono('signal')       // trailing l, no separator, no case change
mono('SIGNAL')       // trailing L but the prefix is uppercase too
mono('pedal')
mono('sidechain')
mono('mixer')        // trailing r, same trap as signal
mono('monitor')
mono('out_0')        // channel numbering starts at 1

// a guessed partner is not a real one: these only pair because the port exists
assert.strictEqual(stereoCounterpart('gain_1').symbol, 'gain_2')

console.log('stereo: all assertions passed')
