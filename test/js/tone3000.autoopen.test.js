// SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
// SPDX-License-Identifier: AGPL-3.0-or-later

/*
 * tone3000Box -- the auto-open preference and the popup's lifetime relative to the tab.
 *
 * Driven against the REAL html/js/tone3000.js. The popup is a stub (jsdom has no real
 * window.open), so this covers the wiring and the preference, not placement.
 *
 * Two behaviours pinned here, both of which were bugs at some point:
 *   - the "open automatically" checkbox persists in localStorage and gates windowopen;
 *   - selecting the tab while the popup is open FOCUSES it, never re-opens or re-navigates
 *     it -- there is deliberately no windowclose handler, because windowclose fires whenever
 *     the panel hides, including when another tab is raised.
 */

const { test, beforeEach } = require('node:test')
const assert = require('node:assert')
const { makeWindow, captureWindowOptions } = require('./harness')

const KEY = 't3k_auto_open'
const BODY = '<div id="t3k">' +
             '<div id="tone3000-wrapper"></div>' +
             '<button id="tone3000-browse"></button>' +
             '<input type="checkbox" id="tone3000-autoopen">' +
             '</div>' +
             '<div id="file-manager-library"><iframe></iframe></div>'

let ctx, $, getOptions
let opened, popups

// A stand-in popup. `location` is what a re-navigation would write; `focused` counts focus().
function makePopup() {
    const p = { closed: false, focused: 0, location: '',
                focus() { this.focused++ }, close() { this.closed = true } }
    popups.push(p)
    return p
}

beforeEach(() => {
    ctx = makeWindow({ url: 'http://localhost:8888/', body: BODY })
    $ = ctx.$
    getOptions = captureWindowOptions(ctx)

    opened = 0
    popups = []
    ctx.window.open = () => { opened++; return makePopup() }
    ctx.window.alert = () => {}
    ctx.window.TONE3000_CLIENT_ID = 'pk_test'
    ctx.window.TONE3000_API = 'https://www.tone3000.com'
    // crypto.subtle.digest never resolves here, so the authorize URL is never built and the
    // popup is never navigated -- exactly what lets us assert location stays ''. window.crypto
    // is a read-only accessor in jsdom, so define over it rather than assign.
    Object.defineProperty(ctx.window, 'crypto', {
        value: { getRandomValues: a => a, subtle: { digest: () => new Promise(() => {}) } },
        configurable: true,
    })
    ctx.window.btoa = s => Buffer.from(s, 'binary').toString('base64')

    ctx.load('js/tone3000.js')
})

const checkbox = () => $('#tone3000-autoopen')
const initBox = () => $('#t3k').tone3000Box({})
// The popup persists in module state across initBox(); close it so the next
// "does open() open one?" check starts clean, the way a fresh session would.
const closePopups = () => { popups.forEach(p => { p.closed = true }); opened = 0 }

test('checkbox is off and nothing auto-opens by default', () => {
    initBox()
    assert.equal(checkbox().prop('checked'), false)
    getOptions().open()
    assert.equal(opened, 0)
})

test('ticking the checkbox persists the preference', () => {
    initBox()
    checkbox().prop('checked', true).trigger('change')
    assert.equal(ctx.window.localStorage.getItem(KEY), '1')
})

test('when the preference is on, selecting the tab opens the popup', () => {
    ctx.window.localStorage.setItem(KEY, '1')
    initBox()
    assert.equal(checkbox().prop('checked'), true, 'checkbox restored from storage')
    closePopups()
    getOptions().open()
    assert.equal(opened, 1)
})

test('the preference survives a reload (a rebuild of the box)', () => {
    ctx.window.localStorage.setItem(KEY, '1')
    initBox()
    initBox()   // reload
    assert.equal(checkbox().prop('checked'), true)
    closePopups()
    getOptions().open()
    assert.equal(opened, 1)
})

test('unticking clears the preference and stops auto-open', () => {
    ctx.window.localStorage.setItem(KEY, '1')
    initBox()
    checkbox().prop('checked', false).trigger('change')
    assert.equal(ctx.window.localStorage.getItem(KEY), '0')
    initBox()
    assert.equal(checkbox().prop('checked'), false)
    closePopups()
    getOptions().open()
    assert.equal(opened, 0)
})

test('open() returns false so it does not swallow the panel-show', () => {
    initBox()
    closePopups()
    assert.equal(getOptions().open(), false)
})

test('refreshes the File Manager only when its iframe has loaded', () => {
    const manager = $('#file-manager-library')
    const iframe = manager.find('iframe')
    iframe.attr('src', 'http://localhost:8081/')

    assert.equal(ctx.window.tone3000RefreshFileManager(), false)
    assert.equal(iframe.attr('src'), 'http://localhost:8081/', 'unloaded iframe is untouched')

    manager.data('loaded', true)
    assert.equal(ctx.window.tone3000RefreshFileManager(), true)
    assert.match(iframe.attr('src'), /^http:\/\/localhost:8081\/\?_=/,
                 'loaded iframe is navigated with a cache-busting URL')
})

test('PKCE S256 works without crypto.subtle on a plain-HTTP device origin', async () => {
    Object.defineProperty(ctx.window, 'crypto', {
        value: { getRandomValues: a => a },
        configurable: true,
    })

    const challenge = await ctx.window.tone3000Sha256Base64Url('abc')
    assert.equal(challenge, 'ungWv48Bz-pBQUDeXa4iI7ADYaOWF3qctBD_YfIAFa0')
})

test('re-selecting the tab focuses the open popup, never re-opens or re-navigates it', () => {
    ctx.window.localStorage.setItem(KEY, '1')
    initBox()
    closePopups()
    popups = []

    getOptions().open()
    assert.equal(opened, 1, 'first selection opens it')
    const popup = popups[0]
    assert.equal(popup.location, '', 'not navigated (authorize URL never built here)')

    getOptions().open()   // leave to another tab, come back
    getOptions().open()
    assert.equal(opened, 1, 'no second popup')
    assert.equal(popup.focused, 2, 'focused each return')
    assert.equal(popup.location, '', 'never re-navigated')
})

test('there is no windowclose handler -- the popup outlives the panel', () => {
    initBox()
    assert.equal(getOptions().close, undefined)
})

test('once the user closes the popup, the tab opens a fresh one', () => {
    ctx.window.localStorage.setItem(KEY, '1')
    initBox()
    closePopups()
    popups = []
    getOptions().open()
    popups[0].closed = true
    getOptions().open()
    assert.equal(opened, 2, 'a closed popup is replaced, not focused')
    assert.equal(popups.length, 2)
})

test('a localStorage that throws (private mode) does not break the tab', () => {
    const real = Object.getOwnPropertyDescriptor(ctx.window, 'localStorage')
    Object.defineProperty(ctx.window, 'localStorage',
        { get() { throw new Error('denied') }, configurable: true })
    assert.doesNotThrow(() => { initBox(); getOptions().open() })
    Object.defineProperty(ctx.window, 'localStorage', real)
})
