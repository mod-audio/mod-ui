// SPDX-FileCopyrightText: 2012-2026 MOD Audio UG
// SPDX-License-Identifier: AGPL-3.0-or-later

// Run with: node test/test_criticalpath.js
//
// graphSlack decides which plugins the CPU panel marks as worth optimising, so a
// wrong answer here is a wrong answer in front of the user. Everything else in the
// panel is display.

const assert = require('assert')
const fs = require('fs')
const path = require('path')

// html/js/utils/*.js are plain globals, no module system
eval(fs.readFileSync(path.join(__dirname, '..', 'html', 'js', 'utils', 'criticalpath.js'), 'utf8'))

function check(name, weights, edges, critical, slack) {
    const got = graphSlack(weights, edges)
    assert.strictEqual(got.critical, critical, `${name}: critical ${got.critical}, expected ${critical}`)
    for (const n in slack) {
        assert.strictEqual(got.slack[n], slack[n], `${name}: slack[${n}] ${got.slack[n]}, expected ${slack[n]}`)
    }
}

// a plain chain: everything is critical, nothing has slack
check('chain',
      {a: 10, b: 20, c: 5}, [['a','b'], ['b','c']],
      35, {a: 0, b: 0, c: 0})

// two branches off one source: only the slower branch is critical
check('branches',
      {src: 0, slow: 30, fast: 10, sink: 5},
      [['src','slow'], ['src','fast'], ['slow','sink'], ['fast','sink']],
      35, {slow: 0, fast: 20, sink: 0})

// the expensive plugin is NOT the critical one -- the whole point of the panel
check('hog off the critical path',
      {src: 0, hog: 40, a: 25, b: 25, sink: 0},
      [['src','hog'], ['src','a'], ['a','b'], ['hog','sink'], ['b','sink']],
      50, {hog: 10, a: 0, b: 0})

// disconnected plugins still get measured, and are their own path
check('island',
      {a: 10, island: 3}, [],
      10, {a: 0, island: 7})

// nodes named only by an edge (hardware ports) count as free
check('unweighted node',
      {a: 10}, [['capture', 'a'], ['a', 'playback']],
      10, {capture: 0, a: 0, playback: 0})

// a feedback loop must not hang or produce a negative slack
const loop = graphSlack({a: 10, b: 20, c: 5},
                        [['a','b'], ['b','c'], ['c','a']])
assert.ok(loop.critical > 0, 'feedback loop should still yield a path')
for (const n in loop.slack) {
    assert.ok(loop.slack[n] >= 0, `feedback loop gave node ${n} negative slack ${loop.slack[n]}`)
}

// A real 21-plugin board, captured off a Dwarf: per-client cpu in microseconds per
// 2667us cycle, and the audio connection graph. This is the case the panel exists for
// -- the biggest plugin is not the one holding up the cycle.
const DWARF_US = {
    'effect_79': 510, 'effect_5': 447, 'effect_71': 407, 'effect_50': 397, 'effect_27': 360,
    'effect_70': 250, 'effect_54': 210, 'effect_11': 147, 'effect_3': 123, 'mod-host': 87,
    'effect_81': 83, 'effect_4': 73, 'effect_30': 70, 'effect_44': 63, 'effect_83': 63,
    'effect_84': 57, 'mod-monitor': 57, 'effect_41': 57, 'mod-peakmeter': 57, 'effect_82': 53,
    'effect_85': 53, 'effect_77': 50, 'effect_31': 47, 'ttymidi': 47, 'mod-midi-merger': 47,
    'effect_78': 37, 'mod-midi-broadcaster': 37,
}
const DWARF_EDGES = [
    // jack's capture and playback are one client but opposite ends of the cycle;
    // collapsing them into a single node would invent a loop through the whole graph
    ['capture','mod-host'], ['capture','mod-peakmeter'], ['mod-host','effect_3'],
    ['mod-monitor','playback'], ['mod-monitor','mod-peakmeter'], ['effect_82','effect_27'],
    ['effect_83','effect_5'], ['effect_44','effect_70'], ['effect_5','effect_71'],
    ['effect_84','effect_44'], ['effect_85','effect_79'], ['effect_71','mod-monitor'],
    ['effect_11','effect_70'], ['effect_70','mod-monitor'], ['effect_70','effect_78'],
    ['effect_54','effect_77'], ['effect_54','effect_50'], ['effect_27','effect_71'],
    ['effect_27','effect_83'], ['effect_27','effect_84'], ['effect_3','effect_4'],
    ['effect_4','effect_41'], ['effect_81','effect_70'], ['effect_79','effect_71'],
    ['effect_30','effect_81'], ['effect_30','effect_84'], ['effect_30','effect_82'],
    ['effect_30','effect_83'], ['effect_30','effect_85'], ['effect_30','effect_11'],
    ['effect_50','effect_31'], ['effect_50','effect_70'], ['effect_41','effect_54'],
]
const dwarf = graphSlack(DWARF_US, DWARF_EDGES)

// no node may end up with negative slack
for (const n in dwarf.slack) {
    assert.ok(dwarf.slack[n] >= 0, `${n} got negative slack ${dwarf.slack[n]}`)
}

// jack reported ~63% DSP load while this was measured; the longest chain should land
// near that, and never below the single most expensive plugin
assert.ok(dwarf.critical > 1200 && dwarf.critical < 1900,
          `critical path ${dwarf.critical}us should land near the 1670us (63%) jack measured`)

assert.strictEqual(dwarf.slack['effect_5'], 0, 'effect_5 should be on the critical path')
assert.ok(dwarf.slack['effect_79'] > 300,
          `effect_79 is the top cpu consumer but off the critical path, got slack ${dwarf.slack['effect_79']}`)

// The answer must not depend on the order plugins happen to arrive in. Breaking a
// cycle at a different edge silently changes the whole ranking, which is exactly the
// kind of bug nobody notices in a UI.
const reversedWeights = {}
Object.keys(DWARF_US).reverse().forEach(k => { reversedWeights[k] = DWARF_US[k] })
const shuffled = graphSlack(reversedWeights, DWARF_EDGES.slice().reverse())
assert.strictEqual(shuffled.critical, dwarf.critical,
                   `critical path changed with input order: ${shuffled.critical} vs ${dwarf.critical}`)
for (const n in dwarf.slack) {
    assert.strictEqual(shuffled.slack[n], dwarf.slack[n], `slack[${n}] changed with input order`)
}

console.log(`  dwarf board: critical path ${dwarf.critical}us of a 2667us cycle ` +
            `(${(dwarf.critical / 2667 * 100).toFixed(0)}%, jack measured 63%)`)

console.log('criticalpath: all assertions passed')
