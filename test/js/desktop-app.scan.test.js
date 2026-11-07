// SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
// SPDX-License-Identifier: AGPL-3.0-or-later

/*
 * Nothing of the MOD Desktop seam reaches a MOD device.
 *
 * The seam (html/js/desktop-app.js, its stylesheet, the desktop_app_* partials) is
 * only served with MOD_DESKTOP=1. These scans pin the two shared files that still
 * mention it to the shapes that keep a device's page clean. They read source only
 * and need no jsdom, so they run anywhere node does.
 */

const { test } = require('node:test')
const assert = require('node:assert')
const fs = require('fs')
const path = require('path')

const HTML = path.resolve(__dirname, '../../html')

/*
 * index.html is served to devices with desktop_app false. Every line that names
 * DesktopApp or a desktop-app asset must sit inside the true branch of a
 * {% if desktop_app %} block, so the rendered device page carries none of it.
 */
test('index.html only mentions the seam inside {% if desktop_app %}', () => {
    const src = fs.readFileSync(path.join(HTML, 'index.html'), 'utf8')
    const lines = src.split('\n')

    // Walk the template's block structure, tracking whether we are inside the
    // true branch of a desktop_app conditional. Other {% if %}s are tracked too,
    // so their {% else %} / {% end %} cannot be mistaken for ours.
    const stack = []
    const inDesktop = () => stack.some(b => b.desktop && b.branch === 'then')
    let seam = 0
    lines.forEach((line, i) => {
        const open = /\{%\s*if\s+(.*?)\s*%\}/.exec(line)
        if (open) stack.push({ desktop: open[1] === 'desktop_app', branch: 'then' })
        if (/\{%\s*else\s*%\}/.test(line)) stack[stack.length - 1].branch = 'else'

        const mentions = /DesktopApp|desktop-app\.(js|css)|desktop_app_templates/.test(line)
        if (mentions) {
            seam++
            assert.ok(inDesktop(), 'index.html:' + (i + 1) + ' reaches a device: ' + line.trim())
        }

        if (/\{%\s*end\s*%\}/.test(line)) stack.pop()
    })
    assert.strictEqual(stack.length, 0, 'unbalanced template blocks')
    assert.ok(seam >= 4, 'the scan found nothing -- it is broken')
})

/*
 * The seam is not served to devices, so no shared script may call DesktopApp on a
 * path a device can run. hardware.js is the one file that calls it, and only
 * behind isApp(), which desktop.js answers from desktop.isApp -- set by
 * DesktopApp.setup() and nothing else.
 */
test('shared scripts only call DesktopApp behind isApp()', () => {
    const dir = path.join(HTML, 'js')
    const callers = {}
    fs.readdirSync(dir)
        .filter(f => f.endsWith('.js') && f !== 'desktop-app.js')
        .forEach(f => {
            const lines = fs.readFileSync(path.join(dir, f), 'utf8').split('\n')
            lines.forEach((line, i) => {
                if (!/DesktopApp\./.test(line)) return
                callers[f] = (callers[f] || 0) + 1
                // The guard opens within a few lines above the call.
                const above = lines.slice(Math.max(0, i - 8), i).join('\n')
                assert.ok(/if \(options\.isApp\(\)\)/.test(above),
                          f + ':' + (i + 1) + ' calls DesktopApp outside isApp(): ' + line.trim())
            })
        })

    assert.deepStrictEqual(Object.keys(callers), ['hardware.js'],
                           'only hardware.js may call DesktopApp; found ' + JSON.stringify(callers))
    assert.strictEqual(callers['hardware.js'], 2, 'show + hide of the addressing upsell')
})

test('desktop.js no longer carries its own MOD Desktop setup', () => {
    const src = fs.readFileSync(path.join(HTML, 'js', 'desktop.js'), 'utf8')
    assert.ok(!/setupApp/.test(src), 'setupApp moved to DesktopApp.setup')
    assert.ok(/this\.isApp = false/.test(src), 'the controller still answers isApp for hardware.js')
})

test('the Desktop partials match what BulkTemplateLoader serves', () => {
    const dir = path.join(HTML, 'include', 'desktop-app')
    const names = fs.readdirSync(dir)
    names.forEach(f => assert.match(f, /^[a-z_]+\.html$/, f + ' would be skipped by the loader'))
    // What desktop-app.js renders by name.
    const src = fs.readFileSync(path.join(HTML, 'js', 'desktop-app.js'), 'utf8')
    for (const m of src.matchAll(/desktop_app_([a-z_]+)/g)) {
        assert.ok(names.includes(m[1] + '.html'), 'desktop-app.js renders desktop_app_' + m[1] + ', which has no partial')
    }
})
