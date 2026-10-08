// SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
// SPDX-License-Identifier: AGPL-3.0-or-later

/*
 * DesktopApp -- the MOD Desktop ("desktop-app") seam.
 *
 * Driven against the REAL html/js/desktop-app.js, the REAL mustache partials under
 * html/include/desktop-app/, and the REAL markup in html/index.html and
 * html/include/addressing.html. jsdom has no CSS, so what a greyed icon or the overlay
 * *looks* like is out of scope; what is pinned here is the wiring:
 *
 *   - Plugin Store, Banks and File Manager keep their icon, lose their window, and open
 *     the one shared overlay with their own copy.
 *   - Hardware addressing keeps the in-window card; the Control Chain icon is hidden; Share is greyed.
 *   - Settings, status, RAM and the MIDI-port toggle hide; the Constructor and the
 *     Pedalboard Library are untouched.
 *   - setup() is what flips the switch, and nothing else does. That a MOD device never
 *     meets any of this is pinned by desktop-app.scan.test.js, which needs no jsdom.
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

/*
 * html/index.html is a tornado template, so {{ }} and {% %} survive as text -- harmless
 * here, since we only assert on structure.
 */
function loadIndexBody(ctx) {
    const html = fs.readFileSync(path.join(HTML, 'index.html'), 'utf8')
    const body = html.slice(html.indexOf('<body'), html.lastIndexOf('</body>'))
    ctx.window.document.body.innerHTML = body.slice(body.indexOf('>') + 1)
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

// The card ----------------------------------------------------------------

test('the card renders the feature name, the sentence and the store link', () => {
    const panel = $(DesktopApp.panel('Banks', 'Step through pedalboards hands-free.'))
    assert.strictEqual(panel.find('h2').text(), 'Banks')
    assert.match(panel.find('.desktop-app-exclusive-eyebrow').text(), /Exclusive to MOD Audio devices/)
    assert.match(panel.find('p').text(), /Step through pedalboards hands-free\./)
    assert.strictEqual(panel.find('a').attr('href'), DesktopApp.STORE_URL)
    assert.strictEqual(panel.find('a').attr('target'), '_blank')
    assert.strictEqual(panel.find('img').attr('src'), DesktopApp.IMAGE_URL)
})

/* One card, two layouts: dark full-window, and light-on-white in a form. Only the
 * variant class and the photo differ, so a template change cannot leave one behind. */
test('the form variant is the same card with the light photo and a variant class', () => {
    const dark = $(DesktopApp.panel('Banks', 'x'))
    const light = $(DesktopApp.formPanel('Hardware addressing', 'x'))

    ;[dark, light].forEach(card => {
        assert.ok(card.hasClass('desktop-app-exclusive-panel'), 'shares the base class')
        assert.strictEqual(card.find('a').attr('href'), DesktopApp.STORE_URL)
    })
    assert.ok(!dark.hasClass('desktop-app-exclusive-form'))
    assert.strictEqual(dark.find('img').attr('src'), DesktopApp.IMAGE_URL)
    assert.ok(light.hasClass('desktop-app-exclusive-form'))
    assert.strictEqual(light.find('img').attr('src'), DesktopApp.IMAGE_URL_LIGHT)
})

/* The photos are bundled, not hotlinked: MOD Desktop runs offline, and a broken
 * image is the whole point of these panels failing. */
test('the panel images are bundled files', () => {
    ;[DesktopApp.IMAGE_URL, DesktopApp.IMAGE_URL_LIGHT].forEach(url => {
        assert.ok(!/^https?:/.test(url), url + ' must be bundled')
        assert.ok(fs.existsSync(path.join(HTML, url)), url + ' is missing from html/')
    })
})

// The main menu and the overlay --------------------------------------------

test('setup() finds every element it reaches for in index.html', () => {
    loadIndexBody(ctx)

    // Each of these is a selector crossing from desktop-app.js into index.html.
    const targets = ['#mod-cloud-plugins', '#mod-bank', '#mod-file-manager',
                     '#mod-settings', '#mod-status', '#mod-ram', '#mod-show-midi-port',
                     '#pedalboards-library', '#mod-devices', '#mod-devices-window',
                     '#pedalboard-info .js-cloud',
                     '#pedal-presets-window']
    targets.forEach(sel => {
        assert.strictEqual($(sel).length, 1, sel + ' is missing from index.html')
    })
    Object.keys(DesktopApp.EXCLUSIVE).forEach(id => {
        assert.strictEqual($('#main-menu #' + id).length, 1, '#' + id + ' is not a main-menu icon')
    })
})

test('Plugin Store, Banks and File Manager keep a greyed icon and open the overlay, not their window', () => {
    loadIndexBody(ctx)
    // index.html hides the store in its non-device branch, before setup() runs.
    $('#mod-cloud-plugins').hide()

    // What window.js binds on each icon when `desktop` constructs the boxes.
    const opened = []
    ;['mod-cloud-plugins', 'mod-bank', 'mod-file-manager'].forEach(id => {
        $('#' + id).click(() => opened.push(id))
    })

    DesktopApp.setup(null)
    assert.ok($('body').hasClass('desktop-app'))

    ;['mod-cloud-plugins', 'mod-bank', 'mod-file-manager'].forEach(id => {
        const icon = $('#' + id)
        assert.notStrictEqual(icon.css('display'), 'none', '#' + id + ' must stay visible')
        assert.ok(icon.hasClass('desktop-app-greyed'), '#' + id + ' must be greyed')

        icon.click()
        const overlay = $('#desktop-app-exclusive-overlay')
        assert.strictEqual(overlay.length, 1, 'one overlay, appended to the body')
        assert.strictEqual(overlay.css('display'), 'block', 'the overlay opens')
        assert.strictEqual(overlay.find('h2').text(), DesktopApp.EXCLUSIVE[id].feature)
        assert.strictEqual(overlay.find('p').text(), DesktopApp.EXCLUSIVE[id].message)
        assert.strictEqual(overlay.find('a').attr('href'), DesktopApp.STORE_URL)
        DesktopApp.hideUpsell()
    })

    assert.deepStrictEqual(opened, [], "the feature windows' own toggles no longer run")
    assert.strictEqual($('.desktop-app-exclusive-overlay').length, 1, 'the overlay is reused, not stacked')
})

test('the overlay closes on its button and on Escape', () => {
    loadIndexBody(ctx)
    DesktopApp.setup(null)

    $('#mod-bank').click()
    const overlay = $('#desktop-app-exclusive-overlay')
    assert.strictEqual(overlay.css('display'), 'block')

    overlay.find('.js-close').click()
    assert.strictEqual(overlay.css('display'), 'none')

    $('#mod-file-manager').click()
    assert.strictEqual(overlay.css('display'), 'block')
    $(ctx.window.document).trigger($.Event('keydown', { keyCode: 27 }))
    assert.strictEqual(overlay.css('display'), 'none')

    // Anywhere outside the card is backdrop; the card itself is not.
    $('#mod-cloud-plugins').click()
    assert.strictEqual(overlay.css('display'), 'block')
    overlay.find('.desktop-app-exclusive-card h2').click()
    assert.strictEqual(overlay.css('display'), 'block', 'a click inside the card keeps it open')
    overlay.find('.desktop-app-exclusive-panel').click()
    assert.strictEqual(overlay.css('display'), 'none', 'a click beside the card closes it')
})

test('setup() hides the device-only readouts, Control Chain included, and keeps the Constructor and the Library', () => {
    loadIndexBody(ctx)
    DesktopApp.setup(null)

    // Absent for unrelated reasons: hidden, no card.
    ;['#mod-settings', '#mod-status', '#mod-ram', '#mod-show-midi-port'].forEach(sel => {
        assert.strictEqual($(sel).css('display'), 'none', sel + ' must hide')
    })
    assert.strictEqual($('#pedal-presets-window .js-assign-all').css('display'), 'none')

    // What MOD Desktop is for.
    ;['#mod-plugins', '#mod-pedalboard'].forEach(sel => {
        assert.notStrictEqual($(sel).css('display'), 'none', sel + ' must stay')
        assert.ok(!$(sel).hasClass('desktop-app-greyed'), sel + ' must not be greyed')
    })

    // Control Chain is not advertised: icon and window gone, no card anywhere.
    assert.strictEqual($('#mod-devices').css('display'), 'none', 'the Control Chain icon must not show')
    assert.strictEqual($('#mod-devices-window').css('display'), 'none')
    assert.strictEqual($('#mod-devices-window .desktop-app-exclusive-panel').length, 0, 'no card in the window')
    $('#mod-devices').click()
    assert.strictEqual($('#mod-devices-window').css('display'), 'none', 'clicking the hidden icon opens nothing')
})

test('setup() greys the Share button and routes it to the overlay instead of the share window', () => {
    loadIndexBody(ctx)
    let shared = 0
    const button = $('#pedalboard-info .js-cloud')
    button.click(() => { shared++ })          // what desktop.js binds: the share window
    DesktopApp.setup(null)

    assert.notStrictEqual(button.css('display'), 'none', 'the button stays visible')
    assert.ok(button.hasClass('desktop-app-greyed'), 'and greyed like the other device-only entries')
    button.click()
    assert.strictEqual(shared, 0, 'the share window handler must be gone')
    const overlay = $('#desktop-app-exclusive-overlay')
    assert.strictEqual(overlay.length, 1, 'the shared overlay opened')
    assert.notStrictEqual(overlay.css('display'), 'none')
    assert.strictEqual(overlay.find('h2').text(), 'Share')
    assert.ok(overlay.find('a.desktop-app-exclusive-cta').attr('href').startsWith('https://mod.audio/'), 'button to the website')
})

test('setup() tells the shared controller it is the app and switches analytics off', () => {
    loadIndexBody(ctx)
    let tracked = 0
    const desktop = { isApp: false, setupMatomo: () => { tracked++ } }

    DesktopApp.setup(desktop)

    assert.strictEqual(desktop.isApp, true, 'hardware.js and installMissingPlugins ask desktop.isApp')
    desktop.setupMatomo()
    assert.strictEqual(tracked, 0, 'the Matomo loader must never run on MOD Desktop')
})

test('isActive stays false until setup runs', () => {
    loadIndexBody(ctx)
    assert.strictEqual(DesktopApp.isActive(), false)

    DesktopApp.setup(null)
    assert.strictEqual(DesktopApp.isActive(), true)
})

// Hardware addressing ------------------------------------------------------

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

test('the addressing upsell is inert when not active', () => {
    ctx.window.document.body.innerHTML =
        fs.readFileSync(path.join(HTML, 'include', 'addressing.html'), 'utf8')

    const form = $('form')
    DesktopApp.hideAddressingUpsell(form)

    assert.strictEqual(form.find('.desktop-app-exclusive').length, 0)
    assert.strictEqual(form.find('.js-save').attr('style'), undefined, 'Save is left alone')
})
