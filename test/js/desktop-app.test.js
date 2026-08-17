// SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
// SPDX-License-Identifier: AGPL-3.0-or-later

/*
 * DesktopApp -- the MOD Desktop ("desktop-app") seam.
 *
 * Driven against the REAL html/js/desktop-app.js, the REAL mustache partials under
 * html/include/desktop-app/, and the REAL markup in html/index.html. jsdom has no CSS,
 * so what a locked tile or a hidden button *looks* like is out of scope; what is pinned
 * here is the wiring:
 *
 *   - storeQuery rewrites the cloud query to the Dwarf catalogue, and deletes
 *     image_version rather than overriding it. Sending MOD Desktop's own VERSION
 *     returns an empty catalogue from api.mod.audio, which is what made the store
 *     look broken; sending bin_compat=linux-x64_64 does the same.
 *   - storeQuery is inert when DesktopApp is not active, because cloudplugin.js calls
 *     it unconditionally and the pedals share that file.
 *   - setup() actually finds its targets in index.html. These are id selectors reaching
 *     across files, so a markup rename would otherwise fail silently at runtime.
 */

const { test, beforeEach } = require('node:test')
const assert = require('node:assert')
const fs = require('fs')
const path = require('path')
const { makeWindow, HTML } = require('./harness')

// Mirrors BulkTemplateLoader: html/include/desktop-app/<name>.html becomes
// TEMPLATES['desktop_app_<name>'].
function loadDesktopAppTemplates(window) {
    const dir = path.join(HTML, 'include', 'desktop-app')
    const templates = {}
    fs.readdirSync(dir).forEach(f => {
        if (!/^[a-z_]+\.html$/.test(f)) return
        templates['desktop_app_' + f.slice(0, -5)] = fs.readFileSync(path.join(dir, f), 'utf8')
    })
    window.TEMPLATES = templates
}

let ctx, $, DesktopApp

beforeEach(() => {
    ctx = makeWindow()
    $ = ctx.$
    loadDesktopAppTemplates(ctx.window)
    ctx.load('js/desktop-app.js')
    DesktopApp = ctx.window.DesktopApp
    DesktopApp.active = false
})

test('storeQuery leaves the query alone on a device', () => {
    const query = { text: 'reverb', image_version: '1.13.5', bin_compat: 'aarch64-a35' }
    const out = DesktopApp.storeQuery(query)

    assert.strictEqual(out.image_version, '1.13.5')
    assert.strictEqual(out.bin_compat, 'aarch64-a35')
})

test('storeQuery browses as a Dwarf and drops image_version on desktop', () => {
    DesktopApp.active = true

    // What cloudplugin.js would send from MOD Desktop: its own release number and
    // an x86_64 bin_compat, neither of which matches anything in the cloud.
    const out = DesktopApp.storeQuery({ text: '', image_version: '0.0.13', bin_compat: 'linux-x64_64' })

    assert.strictEqual(out.bin_compat, 'aarch64-a35')
    assert.ok(!('image_version' in out), 'image_version must be deleted, not overridden')
    assert.strictEqual(out.text, '', 'unrelated keys survive')
})

test('the exclusive widget renders the feature name and the store link', () => {
    const panel = $(DesktopApp.panel('Banks', 'Step through pedalboards hands-free.'))
    assert.strictEqual(panel.find('h2').text(), 'Banks')
    assert.match(panel.find('.desktop-app-exclusive-eyebrow').text(), /Exclusive to MOD Audio devices/)
    assert.match(panel.find('p').text(), /Step through pedalboards hands-free\./)
    assert.strictEqual(panel.find('a').attr('href'), DesktopApp.STORE_URL)
    assert.strictEqual(panel.find('img').attr('src'), DesktopApp.IMAGE_URL)
})

/* One card, three layouts: dark full-window, light-on-white in a form, and dark
 * and compact on the plugin page. Only the variant class and the photo differ,
 * so a template change cannot leave one of them behind. */
test('every variant is the same card with a variant class', () => {
    const cases = [
        [DesktopApp.panel('Banks', 'x'), '', DesktopApp.IMAGE_URL],
        [DesktopApp.formPanel('Hardware addressing', 'x'), 'desktop-app-exclusive-form', DesktopApp.IMAGE_URL_LIGHT],
        [DesktopApp.compactPanel('Install this plugin', 'x'), 'desktop-app-exclusive-compact', DesktopApp.IMAGE_URL],
    ]

    cases.forEach(([html, variant, image]) => {
        const card = $(html)
        assert.ok(card.hasClass('desktop-app-exclusive-panel'), 'shares the base class')
        assert.strictEqual(card.find('img').attr('src'), image)
        assert.strictEqual(card.find('a').attr('href'), DesktopApp.STORE_URL)

        const variants = ['desktop-app-exclusive-form', 'desktop-app-exclusive-compact']
        variants.forEach(v => assert.strictEqual(card.hasClass(v), v === variant, v))
    })

    // The plugin page card is what cloudplugin.js drops in for the Install button.
    const plugin = $(DesktopApp.pluginMessage())
    assert.ok(plugin.hasClass('desktop-app-exclusive-compact'))
    assert.strictEqual(plugin.find('h2').text(), 'Install this plugin')
})

/* The photos are bundled, not hotlinked: MOD Desktop runs offline, and a broken
 * image is the whole point of these panels failing. */
test('the panel images are local paths', () => {
    assert.ok(!/^https?:/.test(DesktopApp.IMAGE_URL), DesktopApp.IMAGE_URL + ' must be bundled')
    assert.ok(!/^https?:/.test(DesktopApp.IMAGE_URL_LIGHT), DesktopApp.IMAGE_URL_LIGHT + ' must be bundled')
})

/*
 * Selecting a hardware-only tab swaps the addressing options for the card, and
 * takes Save and Advanced with them -- there is nothing to save or configure.
 * Driven against the real html/include/addressing.html so a markup rename fails
 * here rather than silently at runtime.
 */
test('the addressing upsell replaces the options, and every tab switch undoes it', () => {
    ctx.window.document.body.innerHTML =
        fs.readFileSync(path.join(HTML, 'include', 'addressing.html'), 'utf8')
    DesktopApp.active = true

    const form = $('form')
    const dynamic = form.find('.dynamic-field').show()

    DesktopApp.showAddressingUpsell(form)

    const card = form.find('.main-form-container').find('.desktop-app-exclusive-form')
    assert.strictEqual(card.length, 1, 'the card lands inside the options area')
    assert.strictEqual(card.css('display'), 'block')
    dynamic.each((_, el) => assert.strictEqual($(el).css('display'), 'none'))
    assert.strictEqual(form.find('.js-save').css('display'), 'none')
    assert.strictEqual(form.find('.advanced-toggle').css('display'), 'none')

    DesktopApp.hideAddressingUpsell(form)

    assert.strictEqual(card.css('display'), 'none')
    assert.notStrictEqual(form.find('.js-save').css('display'), 'none')
    assert.notStrictEqual(form.find('.advanced-toggle').css('display'), 'none')

    // Re-selecting reuses the one card rather than stacking a second.
    DesktopApp.showAddressingUpsell(form)
    assert.strictEqual(form.find('.desktop-app-exclusive').length, 1)
})

test('the addressing upsell is inert on a device, where no tab is ever locked', () => {
    ctx.window.document.body.innerHTML =
        fs.readFileSync(path.join(HTML, 'include', 'addressing.html'), 'utf8')

    const form = $('form')
    DesktopApp.hideAddressingUpsell(form)

    assert.strictEqual(form.find('.desktop-app-exclusive').length, 0)
    assert.strictEqual(form.find('.js-save').attr('style'), undefined, 'Save is left alone')
})

/*
 * On hardware none of the seam is served: no js/desktop-app.js, no
 * css/desktop-app.css, no desktop_app_* templates. Shared code still calls
 * DesktopApp on paths that run there, so index.html carries a stub in the
 * {% else %} branch. This pins the stub to what the shared files actually call,
 * so adding an unguarded call without stubbing it fails here rather than
 * throwing ReferenceError on every MOD device.
 */
test('the hardware stub answers every DesktopApp call that is not behind isActive()', () => {
    const html = fs.readFileSync(path.join(HTML, 'index.html'), 'utf8')

    const stubSource = /<script type="text\/javascript">\s*(var DesktopApp = \{[\s\S]*?\n\})\s*<\/script>/
        .exec(html)
    assert.ok(stubSource, 'index.html must carry a DesktopApp stub for hardware')
    const stub = new Function(stubSource[1] + '; return DesktopApp')()

    // Reached only after isActive(), or after a class only set when active, so the
    // stub deliberately does not answer them.
    const GUARDED = ['setup', 'pluginMessage', 'showAddressingUpsell']

    const shared = fs.readdirSync(path.join(HTML, 'js'))
        .filter(f => f.endsWith('.js') && f !== 'desktop-app.js')
        .map(f => path.join(HTML, 'js', f))
        .concat(path.join(HTML, 'index.html'))

    const called = new Set()
    shared.forEach(file => {
        const src = fs.readFileSync(file, 'utf8')
        // The stub's own definition is in index.html; skip past it.
        const body = file.endsWith('index.html') ? src.replace(stubSource[0], '') : src
        for (const m of body.matchAll(/DesktopApp\.([A-Za-z_]+)/g)) {
            called.add(m[1])
        }
    })

    assert.ok(called.size > 0, 'nothing calls DesktopApp -- the scan is broken')
    called.forEach(name => {
        assert.ok(typeof stub[name] === 'function' || GUARDED.includes(name),
                  'DesktopApp.' + name + ' is called by shared code but the hardware ' +
                  'stub does not answer it -- stub it, or guard it with isActive()')
    })

    // And the stub must not answer with something the real seam no longer has.
    Object.keys(stub).forEach(name => {
        assert.strictEqual(typeof DesktopApp[name], 'function',
                           'the stub answers ' + name + ', which desktop-app.js dropped')
    })

    // The device answers: inactive, and the cloud query untouched.
    assert.strictEqual(stub.isActive(), false)
    const query = { bin_compat: 'aarch64-a35', image_version: '1.13.5' }
    assert.strictEqual(stub.storeQuery(query), query)
})

/*
 * The rest run against html/index.html itself. It is a tornado template, so {{ }} and
 * {% %} survive as text -- harmless here, since we only assert on structure.
 */
function loadIndexBody(ctx) {
    const html = fs.readFileSync(path.join(HTML, 'index.html'), 'utf8')
    const body = html.slice(html.indexOf('<body'), html.lastIndexOf('</body>'))
    ctx.window.document.body.innerHTML = body.slice(body.indexOf('>') + 1)
}

test('setup() finds every element it reaches for in index.html', () => {
    loadIndexBody(ctx)

    // Each of these is an id selector crossing from desktop-app.js into index.html.
    const targets = ['#mod-file-manager', '#mod-settings', '#mod-status', '#mod-ram',
                     '#mod-show-midi-port', '#pedalboards-library', '#mod-cloud-plugins',
                     '#mod-bank', '#mod-devices', '#bank-library', '#mod-devices-window',
                     '#bank-list', '#bank-edit', '#bank-pedalboards-search',
                     '#pedal-presets-window']
    targets.forEach(sel => {
        assert.strictEqual($(sel).length, 1, sel + ' is missing from index.html')
    })
})

test('setup() shows the store, keeps Banks and Devices, and injects both panels', () => {
    loadIndexBody(ctx)
    // index.html hides the store in its USING_MOD_DEVICE branch, before setup() runs.
    $('#mod-cloud-plugins').hide()

    DesktopApp.setup(null)

    assert.ok($('body').hasClass('desktop-app'))

    // The store icon comes back, and Banks/Devices are no longer hidden outright.
    assert.notStrictEqual($('#mod-cloud-plugins').css('display'), 'none')
    assert.notStrictEqual($('#mod-bank').css('display'), 'none')
    assert.notStrictEqual($('#mod-devices').css('display'), 'none')

    // Genuinely-unavailable features still hide.
    assert.strictEqual($('#mod-file-manager').css('display'), 'none')
    assert.strictEqual($('#mod-settings').css('display'), 'none')

    // Both windows swap their contents for the widget.
    assert.strictEqual($('#bank-library').find('.desktop-app-exclusive-panel').length, 1)
    assert.strictEqual($('#bank-list').css('display'), 'none')
    assert.strictEqual($('#bank-edit').css('display'), 'none')
    assert.strictEqual($('#mod-devices-window').find('.desktop-app-exclusive-panel').length, 1)
    assert.strictEqual($('#mod-devices-window').find('.mod-devices-window-list').css('display'), 'none')
})

test('isActive stays false until setup runs, so shared files take the device path', () => {
    loadIndexBody(ctx)
    assert.strictEqual(DesktopApp.isActive(), false)

    DesktopApp.setup(null)
    assert.strictEqual(DesktopApp.isActive(), true)
})
