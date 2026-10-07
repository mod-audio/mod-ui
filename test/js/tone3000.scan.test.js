// Tone3000 integration: static checks on the shipped sources (plain node, no jsdom).
// Tone3000 hosts NAM captures (amp heads, pedals, amps+cabs, outboard) and cabinet IRs, and
// nothing for AIDA-X; its browse view locks a `gears` filter but only restricts by `format`.
const { test } = require('node:test')
const assert = require('node:assert')
const fs = require('fs')
const path = require('path')

const HTML = path.join(__dirname, '..', '..', 'html')
const modgui = fs.readFileSync(path.join(HTML, 'js', 'modgui.js'), 'utf8')
const pedalboard = fs.readFileSync(path.join(HTML, 'js', 'pedalboard.js'), 'utf8')

function body(src, name) {
    const start = src.indexOf('function ' + name + '(')
    assert.notStrictEqual(start, -1, name + ' not found')
    const open = src.indexOf('{', start)
    let depth = 0
    for (let i = open; i < src.length; i++) {
        if (src[i] === '{') depth++
        else if (src[i] === '}' && --depth === 0) return src.slice(open, i + 1)
    }
    assert.fail(name + ' has no closing brace')
}

test('the Tone3000 entry is offered for NAM, cabinet and IR ports, not for AIDA-X', () => {
    const fn = body(modgui, 'supportsT3K')
    for (const type of ['nammodel', 'cabsim', 'ir']) {
        assert.ok(fn.includes(`'${type}'`), type + ' missing from supportsT3K')
    }
    assert.ok(!fn.includes('aidadspmodel'), 'AIDA-X ports must not get the Tone3000 entry')
})

test('the Tone3000 browse is restricted by format, never by a locked gears filter', () => {
    const start = pedalboard.indexOf('this.startSelectFlow = function')
    const end = pedalboard.indexOf('.startSelectFlowPopup(', start)
    assert.ok(start !== -1 && end !== -1, 'startSelectFlow not found')
    const flow = pedalboard.slice(start, end)
    assert.ok(!/\bgears\s*:/.test(flow) && !/options\.gears\b/.test(flow), 'startSelectFlow must not pass a gears filter')
    assert.ok(flow.includes("options.format = 'nam'"), 'NAM ports ask for format nam')
    assert.ok(flow.includes("options.format = 'ir'"), 'cabinet/IR ports ask for format ir')
    assert.ok(flow.includes('options.architecture = 2'), 'NAM ports ask for A2 (omitted = A1 only)')
})

test('a download goes where the picker was: the folder travels from the click to the upload', () => {
    assert.ok(modgui.includes('function t3kCurrentFolder('), 'modgui computes the current folder')
    assert.ok(/startSelectFlow\(instance, parameter, false, t3kCurrentFolder\(/.test(modgui),
        'both Tone3000 click sites pass the current folder')
    assert.ok(pedalboard.includes('popup: data, folder: folder'), 'the folder is kept with the open popup')
    assert.ok(/downloadModelsFiles\(auth\.tokens\.access_token, tone, models, function[\s\S]*?\}, t3kinfo\.parameter, t3kinfo\.folder\)/.test(pedalboard),
        'the download receives the port and the folder')
})
