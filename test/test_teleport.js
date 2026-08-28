// SPDX-FileCopyrightText: 2012-2026 MOD Audio UG
// SPDX-License-Identifier: AGPL-3.0-or-later

// Run with: node test/test_teleport.js

const assert = require('assert')
const fs = require('fs')
const path = require('path')

// html/js/utils/*.js are plain globals, no module system
eval(fs.readFileSync(path.join(__dirname, '..', 'html', 'js', 'utils', 'teleport.js'), 'utf8'))

// --- default names ---------------------------------------------------------
// plugin name and port name together, because the port name alone collides at once:
// two reverbs both have an "Out L"
assert.equal(teleportDefaultName('Reverb', 'Out L', {}), 'Reverb Out L')

// a hardware port has no plugin, so the port name stands alone
assert.equal(teleportDefaultName('', 'Capture 1', {}), 'Capture 1')

// two instances of one plugin: the generated name disambiguates itself, silently,
// because the user did not type it
assert.equal(teleportDefaultName('Reverb', 'Out L', { 'graph/a/out_l': 'Reverb Out L' }),
             'Reverb Out L 2')
assert.equal(teleportDefaultName('Reverb', 'Out L', { 'graph/a/out_l': 'Reverb Out L',
                                                      'graph/b/out_l': 'Reverb Out L 2' }),
             'Reverb Out L 3')

// --- names in use ----------------------------------------------------------
const names = { 'graph/rev/out_l': 'verb L', 'graph/dly/out': 'delay' }
assert.deepEqual(teleportNamesInUse(names, null), { 'verb L': true, 'delay': true })
assert.deepEqual(teleportNamesInUse(names, 'graph/dly/out'), { 'verb L': true })

// --- what the user may type ------------------------------------------------
// a free name is fine
assert.equal(teleportNameAvailable('chorus', 'graph/cho/out', names), true)

// another port's name is refused
assert.equal(teleportNameAvailable('verb L', 'graph/cho/out', names), false)

// a port's OWN current name is not a collision with itself: renaming something to
// what it is already called must be accepted, not rejected
assert.equal(teleportNameAvailable('verb L', 'graph/rev/out_l', names), true)

// empty is not a name; it is how you ask for the teleport to go away
assert.equal(teleportNameAvailable('', 'graph/cho/out', names), false)
assert.equal(teleportNameAvailable('   ', 'graph/cho/out', names), false)

// surrounding space is not significant, so it cannot be used to sneak a duplicate past
assert.equal(teleportNameAvailable('  verb L  ', 'graph/cho/out', names), false)

// --- the lifetime rule -----------------------------------------------------
// THE invariant: a name exists exactly as long as at least one of its output's cables
// is teleported. Everything that removes a cable relies on this and nothing else.
{
    const n = { 'graph/rev/out_l': 'verb L', 'graph/dly/out': 'delay' }
    const c = [{ from: 'graph/rev/out_l', to: 'graph/cho/in' }]
    const out = teleportSerialise(n, c)
    assert.deepEqual(out.names, { 'graph/rev/out_l': 'verb L' },
                     'a name with no teleported cable must not be written')
    assert.deepEqual(out.cables, ['graph/rev/out_l -> graph/cho/in'])
}

// the freed name is then available to another output -- the case the rule exists for
{
    const n = { 'graph/dly/out': 'delay' }
    const c = []
    assert.deepEqual(teleportSerialise(n, c).names, {})
    // and having been dropped, nothing is holding "delay" any more
    assert.equal(teleportNameAvailable('delay', 'graph/other/out', teleportSerialise(n, c).names),
                 true)
}

// symmetric safety net: a cable whose output has no name cannot be drawn as a
// teleport, so it is not written either
{
    const out = teleportSerialise({}, [{ from: 'graph/x/out', to: 'graph/y/in' }])
    assert.deepEqual(out.cables, [])
    assert.deepEqual(out.names, {})
}

// --- round trip ------------------------------------------------------------
{
    const n = { 'graph/rev/out_l': 'verb L' }
    const c = [{ from: 'graph/rev/out_l', to: 'graph/cho/in' }]
    const back = teleportDeserialise(teleportSerialise(n, c))
    assert.deepEqual(back.names, n)
    assert.deepEqual(back.cables, c)
}

// junk from disk must not throw; an unreadable file is the same as no teleports
assert.deepEqual(teleportDeserialise(null), { names: {}, cables: [] })
assert.deepEqual(teleportDeserialise({}), { names: {}, cables: [] })
assert.deepEqual(teleportDeserialise({ names: 'nope', cables: 5 }), { names: {}, cables: [] })
assert.deepEqual(teleportDeserialise({ names: {}, cables: ['malformed'] }).cables, [])

console.log('teleport: all assertions passed')
