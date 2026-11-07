// SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
// SPDX-License-Identifier: AGPL-3.0-or-later

/*
 * Test rig for the browser-global frontend.
 *
 * html/js/*.js is not modular -- it defines globals and assumes jQuery, Mustache and a few
 * page-scoped variables already exist. So it cannot be require()'d. Instead we stand up a
 * jsdom window, load the real vendored libraries into it, then load the real source file
 * under test with window.eval, and drive its now-global functions.
 *
 * What this reaches, it tests for real. What jsdom lacks, it cannot: there is no layout
 * (getBoundingClientRect is all zeros), no windowing (window.open is a stub), no network,
 * no CSS. Popup *placement*, cross-window behaviour and styling are out of scope here and
 * stay manual -- see README.md.
 */

const fs = require('fs')
const path = require('path')
const { JSDOM } = require('jsdom')

const HTML = path.resolve(__dirname, '../../html')

// Vendored libraries the frontend takes for granted, in load order.
const LIBS = [
    'js/lib/jquery-1.9.1.min.js',
    'js/lib/mustache.js',
    'js/lib/sprintf-0.6.js',
]

/*
 * Build a fresh window with jQuery + Mustache loaded and the globals the frontend expects
 * to find on the page. Returns { window, $, load } where load(relPath) evals a real source
 * file (path relative to html/) into the window.
 *
 * opts.url    -- document origin, e.g. 'http://localhost:8888/' (default about:blank)
 * opts.body   -- initial <body> innerHTML
 * opts.jqueryUI -- stub draggable/droppable/resizable (icons call these); default true
 */
function makeWindow(opts) {
    opts = opts || {}
    const dom = new JSDOM('<!doctype html><html><body>' + (opts.body || '') + '</body></html>', {
        runScripts: 'outside-only',
        url: opts.url || 'about:blank',
    })
    const window = dom.window
    const load = rel => window.eval(fs.readFileSync(path.join(HTML, rel), 'utf8'))

    LIBS.forEach(load)
    const $ = window.jQuery

    // Page-scoped globals index.html defines before any js/ file runs. modgui.js reads
    // VERSION/baseUrl at GUI-construction time; several files reference desktop/isSDK.
    window.eval('var desktop = null; var isSDK = false; var VERSION = 1; var baseUrl = "";')

    // jsdom has no TextEncoder on the window; PKCE code paths want it.
    if (!window.TextEncoder) {
        window.TextEncoder = require('util').TextEncoder
    }

    if (opts.jqueryUI !== false) {
        ['draggable', 'droppable', 'resizable'].forEach(m => { $.fn[m] = function () { return this } })
    }

    return { window, $, load }
}

/*
 * Capture what a JqueryClass box hands to self.window(options), without pulling in the real
 * window.js overlay machinery. Call before loading a file that defines a *Box widget; the
 * returned getter yields the latest options object the box registered.
 */
function captureWindowOptions(ctx) {
    let captured = null
    ctx.window.JqueryClass = function (name, methods) {
        ctx.$.fn[name] = function (o) { return methods.init.apply(this, [o]) }
    }
    ctx.$.fn.window = function (options) { captured = options; return this }
    return () => captured
}

/*
 * An $.ajax stub that answers by URL substring. routes is { substring: responseOrFn };
 * a function receives the ajax options and returns the response passed to success.
 * Unmatched URLs invoke opts.error if present. Returns a thenable-ish object like $.ajax.
 */
function stubAjax(ctx, routes) {
    ctx.$.ajax = opts => {
        const url = opts.url || ''
        for (const key in routes) {
            if (url.indexOf(key) >= 0) {
                const r = routes[key]
                opts.success(typeof r === 'function' ? r(opts) : r)
                return { done: () => {} }
            }
        }
        if (opts.error) opts.error()
        return { done: () => {} }
    }
}

module.exports = { makeWindow, captureWindowOptions, stubAjax, HTML }
