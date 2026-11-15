// SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
// SPDX-License-Identifier: AGPL-3.0-or-later

/*
 * DesktopApp update check: MOD Desktop asks GitHub for the releases of mod-audio/mod-desktop at
 * most once a day and offers a newer build for its OS in a banner (Gianfranco, 2026-10-25;
 * pre-releases and the two notice kinds 2026-11-07).
 *
 * Driven against the REAL html/js/desktop-app.js and the REAL update_banner partial;
 * the network is an $.ajax stub fed with the shape of the real releases list. Pinned here:
 *
 *   - versions are 0.<MOD OS line>.<build>, compared as numbers; old four-part builds count
 *     by their first three numbers;
 *   - a release tag holds several builds (pre-release "0.14"), so versions come from the
 *     asset names, and only the installer for this OS counts;
 *   - same line = "new build, bug fixes", higher line = "new version, new features";
 *   - switched off, unknown OS or a build with no release version: nothing is requested;
 *   - one request per day, the answer is remembered, offline is not retried until tomorrow;
 *   - "Skip this version" hides that version for good, a newer one still shows;
 *   - the link is the release page of the tag, and odd names never reach the page.
 */

const { test, beforeEach } = require('node:test')
const assert = require('node:assert')
const fs = require('fs')
const path = require('path')
const { makeWindow, HTML } = require('./harness')

const DAY = 24 * 60 * 60 * 1000
const T0 = Date.UTC(2026, 10, 13, 12, 0, 0)

const asset = name => ({ name: name, browser_download_url: 'https://example.com/' + name })
const release = (tag, names, extra) => Object.assign({ tag_name: tag, draft: false, prerelease: false, assets: names.map(asset) }, extra || {})

// GitHub's list as of 2026-11-13, newest first (shortened)
const REAL = [
    release('0.14', ['mod-desktop-0.14.1-macOS.pkg', 'SHA256SUMS-mod-desktop-0.14.1-macOS.txt'], { prerelease: true }),
    release('0.0.13', ['mod-desktop-0.0.13-linux-x86_64.tar.xz', 'mod-desktop-0.0.13-macOS.pkg',
                       'mod-desktop-0.0.13-win64-installer.exe', 'SHA256SUMS-mod-desktop-0.0.13.txt']),
    release('0.0.7', ['mod-desktop-8d4e2463-linux-x86_64.tar.xz', 'mod-desktop-8d4e2463-macOS.pkg', 'mod-desktop-8d4e2463-win64.exe']),
    release('0.0.4', ['mod-app-0.0.4-linux-x86_64.tar.xz', 'mod-app-0.0.4-macOS.dmg', 'mod-app-0.0.4-win64.exe']),
]

let ctx, $, DesktopApp, requests

function respondWith(releases) {
    requests = []
    ctx.$.ajax = opts => {
        requests.push(opts)
        if (releases === null) {
            opts.error()
        } else {
            opts.success(releases)
        }
    }
}

const banner = () => $('#desktop-app-update-banner')
// results come from the jsdom window (another Object prototype): compare plain copies
const newest = (releases, platform) => JSON.parse(JSON.stringify(DesktopApp.newestBuild(releases, platform)))

beforeEach(() => {
    // A real origin, so jsdom gives us localStorage.
    ctx = makeWindow({ url: 'http://127.0.0.1:18181/' })
    $ = ctx.$
    ctx.window.TEMPLATES = {
        desktop_app_update_banner: fs.readFileSync(path.join(HTML, 'include', 'desktop-app', 'update_banner.html'), 'utf8'),
    }
    ctx.load('js/desktop-app.js')
    DesktopApp = ctx.window.DesktopApp
    requests = []
})

test('versions compare as numbers; same line = build, higher line = version', () => {
    const kind = DesktopApp.updateKind
    assert.strictEqual(kind('0.14.2', '0.14.1'), 'build')
    assert.strictEqual(kind('0.14.10', '0.14.9'), 'build', 'numeric, not string order')
    assert.strictEqual(kind('0.15.1', '0.14.9'), 'version')
    assert.strictEqual(kind('1.0.1', '0.99.9'), 'version')
    assert.strictEqual(kind('0.14.1', '0.0.13'), 'version', 'from the old scheme')
    assert.strictEqual(kind('0.14.2', '0.0.14.37'), 'version', 'old four-part internal build')
    assert.strictEqual(kind('v0.14.2', '0.14.1'), 'build')
    assert.strictEqual(kind('0.14.2', '0.14.2'), null)
    assert.strictEqual(kind('0.14.9', '0.15.1'), null)
    assert.strictEqual(kind('nightly', '0.14.1'), null)
    assert.strictEqual(kind('0.14.2', '1761393600'), null, 'dev runs use a timestamp')
    assert.strictEqual(kind('0.14.2', ''), null)
})

test('the newest build for this OS comes from the asset names', () => {
    assert.deepStrictEqual(newest(REAL, 'macos'), { version: '0.14.1', tag: '0.14' })
    assert.deepStrictEqual(newest(REAL, 'linux'), { version: '0.0.13', tag: '0.0.13' },
                           'a Mac-only pre-release is not offered on Linux')
    assert.deepStrictEqual(newest(REAL, 'windows'), { version: '0.0.13', tag: '0.0.13' })

    const several = [release('0.14', ['mod-desktop-0.14.1-macOS.pkg', 'mod-desktop-0.14.10-macOS.pkg', 'mod-desktop-0.14.9-macOS.pkg'])]
    assert.deepStrictEqual(newest(several, 'macos'), { version: '0.14.10', tag: '0.14' })

    assert.strictEqual(newest([release('0.14', ['mod-desktop-0.14.2-win64.zip'])], 'windows'), null, 'zip is not offered')
    assert.strictEqual(newest([release('0.14', ['mod-desktop-0.14.2-macOS.pkg'], { draft: true })], 'macos'), null)
    assert.strictEqual(newest(REAL, 'amiga'), null)
    assert.strictEqual(newest({ message: 'API rate limit exceeded' }, 'macos'), null)
})

test('a newer build shows the banner with its kind, linked to the release page', () => {
    respondWith(REAL)
    DesktopApp.checkForUpdate('0.0.13', true, 'macos', T0)

    assert.strictEqual(requests.length, 1)
    assert.strictEqual(requests[0].url, 'https://api.github.com/repos/mod-audio/mod-desktop/releases?per_page=20')
    assert.strictEqual(requests[0].global, false, 'no loading bar')
    assert.ok(!requests[0].headers, 'no custom headers')
    assert.strictEqual(banner().length, 1)
    assert.match(banner().text(), /MOD Desktop 0\.14\.1 is available \(new version, new features\)/)
    const link = banner().find('.desktop-app-update-download')
    assert.strictEqual(link.attr('href'), 'https://github.com/mod-audio/mod-desktop/releases/tag/0.14')
    assert.strictEqual(link.attr('target'), '_blank')
})

test('a higher build on the same line says bug fixes', () => {
    respondWith([release('0.14', ['mod-desktop-0.14.1-macOS.pkg', 'mod-desktop-0.14.2-macOS.pkg'], { prerelease: true })])
    DesktopApp.checkForUpdate('0.14.1', true, 'macos', T0)
    assert.match(banner().text(), /MOD Desktop 0\.14\.2 is available \(new build, bug fixes\)/)
})

test('nothing newer for this OS: no banner', () => {
    respondWith(REAL)
    DesktopApp.checkForUpdate('0.0.13', true, 'linux', T0)
    assert.strictEqual(requests.length, 1)
    assert.strictEqual(banner().length, 0)

    ctx.window.localStorage.clear()
    respondWith(REAL)
    DesktopApp.checkForUpdate('0.14.1', true, 'macos', T0)
    assert.strictEqual(banner().length, 0)
})

test('switched off, unknown OS or no release version: nothing is requested', () => {
    respondWith(REAL)
    DesktopApp.checkForUpdate('0.0.13', false, 'macos', T0)
    DesktopApp.checkForUpdate('0.0.13', true, '', T0)
    DesktopApp.checkForUpdate('1761393600', true, 'macos', T0)
    DesktopApp.checkForUpdate('', true, 'macos', T0)
    assert.strictEqual(requests.length, 0)
    assert.strictEqual(banner().length, 0)
})

test('one request a day; the remembered answer still shows the banner', () => {
    respondWith(REAL)
    DesktopApp.checkForUpdate('0.0.13', true, 'macos', T0)
    banner().find('.js-close').click()
    assert.strictEqual(banner().length, 0, 'close hides it')

    DesktopApp.checkForUpdate('0.0.13', true, 'macos', T0 + DAY - 1)
    assert.strictEqual(requests.length, 1, 'no second request within a day')
    assert.strictEqual(banner().length, 1, 'shown again on the next start, from memory')

    banner().remove()
    DesktopApp.checkForUpdate('0.0.13', true, 'macos', T0 + DAY)
    assert.strictEqual(requests.length, 2, 'asks again after a day')
})

test('offline: no retry until tomorrow, last answer kept', () => {
    respondWith(REAL)
    DesktopApp.checkForUpdate('0.0.13', true, 'macos', T0)
    banner().remove()

    respondWith(null)
    DesktopApp.checkForUpdate('0.0.13', true, 'macos', T0 + DAY)
    assert.strictEqual(requests.length, 1)
    assert.strictEqual(banner().length, 1, 'the build known from yesterday still shows')

    banner().remove()
    DesktopApp.checkForUpdate('0.0.13', true, 'macos', T0 + DAY + 1000)
    assert.strictEqual(requests.length, 1, 'not retried within the day')
})

test('"Skip this version" hides that build for good, a newer one still shows', () => {
    respondWith([release('0.14', ['mod-desktop-0.14.2-macOS.pkg'])])
    DesktopApp.checkForUpdate('0.14.1', true, 'macos', T0)
    banner().find('.js-skip').click()
    assert.strictEqual(banner().length, 0)

    DesktopApp.checkForUpdate('0.14.1', true, 'macos', T0 + DAY)
    assert.strictEqual(banner().length, 0, '0.14.2 skipped')

    respondWith([release('0.14', ['mod-desktop-0.14.2-macOS.pkg', 'mod-desktop-0.14.3-macOS.pkg'])])
    DesktopApp.checkForUpdate('0.14.1', true, 'macos', T0 + 2 * DAY)
    assert.strictEqual(banner().length, 1)
    assert.match(banner().text(), /0\.14\.3/)
})

test('a malformed or hostile answer is ignored', () => {
    respondWith({ message: 'API rate limit exceeded' })
    DesktopApp.checkForUpdate('0.0.13', true, 'macos', T0)
    assert.strictEqual(banner().length, 0)

    respondWith([
        release('<img src=x onerror=alert(1)>', ['mod-desktop-0.99.1-macOS.pkg']),
        release('0.99', ['mod-desktop-<b>0.99.2</b>-macOS.pkg', 'mod-desktop-0.99.3.4-macOS.pkg', { name: 42 }]),
        null,
        { tag_name: '0.99' },
    ])
    DesktopApp.checkForUpdate('0.0.13', true, 'macos', T0 + DAY)
    assert.strictEqual(banner().length, 0)
})

test('no storage (private window): still works, asks every start', () => {
    Object.defineProperty(ctx.window, 'localStorage', { get() { throw new Error('blocked') } })
    respondWith(REAL)
    DesktopApp.checkForUpdate('0.0.13', true, 'macos', T0)
    assert.strictEqual(banner().length, 1)
    banner().remove()
    DesktopApp.checkForUpdate('0.0.13', true, 'macos', T0 + 1000)
    assert.strictEqual(requests.length, 2)
})

test('only one banner at a time', () => {
    respondWith(REAL)
    DesktopApp.checkForUpdate('0.0.13', true, 'macos', T0)
    DesktopApp.showUpdateBanner('0.14.1', '0.14', 'version')
    assert.strictEqual(banner().length, 1)
})
