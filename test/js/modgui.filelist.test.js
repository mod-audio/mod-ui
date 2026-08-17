// SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
// SPDX-License-Identifier: AGPL-3.0-or-later

/*
 * GUI.refreshFileTypesLists / swapFileWidgets -- refreshing a plugin's file dropdown in
 * place after a download, without rebuilding the icon (which would cut its jsPlumb cables).
 *
 * Driven against the REAL html/js/modgui.js, rendered over two templates that nest the
 * option nodes differently: html/resources/settings.html (options are direct children of
 * the widget) and fixtures/icon-nested.html (options nested inside .mod-enumerated-list,
 * the shape NAM's icon uses). The point of the swap is to work for both without assuming
 * either.
 */

const { test, before } = require('node:test')
const assert = require('node:assert')
const fs = require('fs')
const path = require('path')
const { makeWindow, stubAjax, HTML } = require('./harness')

// The icon template nests the file options inside a .mod-enumerated-list; settings.html
// makes them direct children of the widget. Testing both is the point: the swap must not
// assume either shape. The icon fixture is vendored here (see fixtures/icon-nested.html for
// why); settings.html is the real shipped template, read from the checkout.
const ICON = path.resolve(__dirname, 'fixtures/icon-nested.html')

const URI = 'http://x#model'

let ctx, $, iconTemplate, settingsTemplate

before(() => {
    ctx = makeWindow({ url: 'http://localhost:8888/' })
    $ = ctx.$
    ctx.load('js/modgui.js')
    iconTemplate = fs.readFileSync(ICON, 'utf8')
    settingsTemplate = fs.readFileSync(path.join(HTML, 'resources/settings.html'), 'utf8')
})

// Fresh file listing the ajax stub serves; each test sets it.
let listing = []

function mkEffect() {
    return {
        uri: 'http://nam', label: 'NAM', name: 'NAM', renderedVersion: 1,
        ports: { audio: { input: [], output: [] }, midi: { input: [], output: [] },
                 cv: { input: [], output: [] }, control: { input: [], output: [] } },
        presets: [], parameters: [{
            uri: URI, label: 'Model', type: 'http://lv2plug.in/ns/ext/atom#Path',
            fileTypes: ['nam', 'nammodel'], ranges: { default: '' }, value: '',
            properties: [], units: {}, writable: true, readable: true, comment: '',
            shortName: 'Model', symbol: 'model',
        }],
        gui: { iconTemplate, settingsTemplate, templateData: {}, javascript: null },
    }
}

// Build a rendered GUI with an initially empty file list, the way loadDependencies would.
function build() {
    // loadDependencies re-fetches the templates over ajax even when effect.gui has them,
    // so the stub must answer per-URL, not hand everyone the file list.
    stubAjax(ctx, {
        '/files/list': () => ({ files: listing.slice() }),
        'iconTemplate': iconTemplate,
        'settingsTemplate': settingsTemplate,
    })
    const effect = mkEffect()
    const gui = new ctx.window.GUI(effect, {
        defaultIconTemplate: '<div></div>', defaultSettingsTemplate: '<div></div>',
        change() {}, patchGet() {}, patchSet() {}, presetLoad() {},
    })
    gui.dependenciesLoaded = true
    effect.parameters[0].files = []
    effect.parameters[0].path = true
    let icon, settings
    gui.render('graph/nam_1', (i, s) => { icon = i; settings = s }, false)
    return { gui, icon, settings }
}

const options = root => root.find('[mod-role=enumeration-option]')
const values = root => options(root).map((i, e) => $(e).attr('mod-parameter-value')).get()
const file = (full, base) => ({ fullname: full, basename: base, filetype: 'nammodel' })

test('starts with no options in either panel', () => {
    listing = []
    const { icon, settings } = build()
    assert.equal(options(icon).length, 0)
    assert.equal(options(settings).length, 0)
})

test('a download lands options inside each template\'s own container', () => {
    listing = []
    const { gui, icon, settings } = build()
    listing = [
        file('/u/NAM Models/T (1)/T - standard.nam', 'T - standard.nam'),
        file('/u/NAM Models/T (1)/T - lite.nam', 'T - lite.nam'),
    ]
    gui.refreshFileTypesLists('nammodel')

    const iconWidget = icon.find('[mod-widget=custom-select-path]')
    assert.equal(iconWidget.length, 1, 'icon widget still present')
    assert.equal(options(icon).length, 2, 'icon has both options')
    // The icon nests options one level down; they must be inside the list, not floating.
    assert.equal(iconWidget.find('.mod-enumerated-list [mod-role=enumeration-option]').length, 2)
    assert.equal(iconWidget.children('[mod-role=enumeration-option]').length, 0)
    assert.equal(iconWidget.find('[mod-role=input-parameter-value]').length, 1, 'kept value node')

    const setWidget = settings.find('[mod-widget=custom-select-path]')
    assert.equal(options(settings).length, 2, 'settings has both options')
    // settings.html makes options direct children of the widget.
    assert.equal(setWidget.children('[mod-role=enumeration-option]').length, 2)
})

test('parameter.widgets holds exactly the live nodes, no stale entries', () => {
    listing = []
    const { gui, icon, settings } = build()
    listing = [file('/u/NAM Models/T (1)/T - a.nam', 'T - a.nam')]
    gui.refreshFileTypesLists('nammodel')

    const param = gui.parameters[URI]
    assert.equal(param.widgets.length, 2, 'one per panel')
    assert.ok(param.widgets.every(w =>
        $.contains(icon[0], w[0]) || $.contains(settings[0], w[0])), 'all in the document')

    // A second refresh must not accumulate widgets.
    gui.refreshFileTypesLists('nammodel')
    assert.equal(gui.parameters[URI].widgets.length, 2)
})

test('the current selection survives a refresh, in both panels', () => {
    listing = [
        file('/u/NAM Models/T (1)/T - lite.nam', 'T - lite.nam'),
        file('/u/NAM Models/T (1)/T - standard.nam', 'T - standard.nam'),
    ]
    const { gui, icon, settings } = build()
    gui.refreshFileTypesLists('nammodel')
    const param = gui.parameters[URI]
    param.value = '/u/NAM Models/T (1)/T - lite.nam'
    gui.setWritableParameterValue(URI, 'p', param.value, null, true)

    listing.push(file('/u/NAM Models/T (2)/T - nano.nam', 'T - nano.nam'))
    gui.refreshFileTypesLists('nammodel')

    assert.equal(options(icon).length, 3)
    assert.equal(icon.find('.selected').attr('mod-parameter-value'), param.value)
    assert.equal(settings.find('.selected').attr('mod-parameter-value'), param.value)
})

test('a value that no longer exists selects nothing, like a fresh build', () => {
    listing = [file('/u/a.nam', 'a.nam'), file('/u/b.nam', 'b.nam')]
    const { gui, icon } = build()
    gui.refreshFileTypesLists('nammodel', ['/u/gone.nam'])
    // hoisting a missing file is a no-op; selection was never set, so nothing is selected
    gui.parameters[URI].value = '/u/gone.nam'
    gui.setWritableParameterValue(URI, 'p', '/u/gone.nam', null, true)
    assert.equal(icon.find('.selected').length, 0)
})

test('clicking a freshly-swapped option fires exactly one patch_set', () => {
    listing = [file('/u/a.nam', 'a.nam'), file('/u/b.nam', 'b.nam')]
    const { gui, icon } = build()
    gui.refreshFileTypesLists('nammodel')
    const sets = []
    gui.lv2PatchSet = (uri, vt, v) => sets.push(v)
    icon.find('[mod-parameter-value="/u/b.nam"]').click()
    assert.deepEqual(sets, ['/u/b.nam'])
})

test('hoisted files lead the list, in both panels', () => {
    const LITE = '/u/NAM Models/T (1)/T - lite.nam'
    const NANO = '/u/NAM Models/T (2)/T - nano.nam'
    listing = [
        file(LITE, 'T - lite.nam'),
        file('/u/NAM Models/T (1)/T - standard.nam', 'T - standard.nam'),
        file(NANO, 'T - nano.nam'),
    ]
    const { gui, icon, settings } = build()
    gui.refreshFileTypesLists('nammodel', [NANO])

    assert.equal(values(icon)[0], NANO, 'hoisted file first in icon')
    assert.equal(values(settings)[0], NANO, 'hoisted file first in settings')
    assert.equal(values(icon).length, 3, 'no options lost')
    // non-hoisted keep their /files/list (alphabetical) order after the hoisted ones
    assert.equal(values(icon)[1], LITE)
    assert.ok(values(icon)[2].endsWith('standard.nam'))
})

test('two hoisted files both lead, keeping /files/list order among themselves', () => {
    const LITE = '/u/NAM Models/T (1)/T - lite.nam'
    const NANO = '/u/NAM Models/T (2)/T - nano.nam'
    listing = [
        file(LITE, 'T - lite.nam'),
        file('/u/NAM Models/T (1)/T - standard.nam', 'T - standard.nam'),
        file(NANO, 'T - nano.nam'),
    ]
    const { gui, icon } = build()
    gui.refreshFileTypesLists('nammodel', [NANO, LITE])
    const lead = values(icon).slice(0, 2)
    // passed [NANO, LITE] but the list order is lite-before-nano, and that is what's kept
    assert.deepEqual(lead, [LITE, NANO])
    assert.ok(values(icon)[2].endsWith('standard.nam'))
})

test('without a hoist argument the list keeps /files/list order', () => {
    const LITE = '/u/NAM Models/T (1)/T - lite.nam'
    listing = [
        file(LITE, 'T - lite.nam'),
        file('/u/NAM Models/T (2)/T - nano.nam', 'T - nano.nam'),
    ]
    const { gui, icon } = build()
    gui.refreshFileTypesLists('nammodel')
    assert.equal(values(icon)[0], LITE)
})
