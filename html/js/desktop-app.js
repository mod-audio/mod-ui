// SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
// SPDX-License-Identifier: AGPL-3.0-or-later

/*
 * MOD Desktop ("desktop-app") seam.
 *
 * Everything specific to the MOD Desktop application lives here. Note that
 * desktop.js, despite the name, is the shared web GUI controller and runs on
 * the hardware too -- "desktop" there is the pedalboard workspace metaphor,
 * and the file predates MOD Desktop by years.
 *
 * This file is only served when mod-ui runs with MOD_DESKTOP=1: index.html
 * links it, its stylesheet and the desktop_app_* mustache templates behind
 * {% if desktop_app %}, so a MOD device never downloads any of it. The two
 * shared files that still mention DesktopApp (index.html, hardware.js) only do
 * so on paths that cannot run on a device -- see test/js/desktop-app.test.js.
 *
 * What MOD Desktop has: the Constructor (pedalboard editor) and the Pedalboard
 * Library, Tone3000 included. The set of plugins is fixed at build time.
 *
 * What it does not have, and how that shows:
 *
 *  - Plugin Store, Banks, File Manager: the icon stays in the main menu,
 *    greyed out, as is the Share button. Clicking one opens ONE shared overlay -- a Dwarf press shot,
 *    the feature name, one sentence on what it does on a MOD device and a
 *    button to the website -- instead of the feature's own window. No store
 *    preview, no store queries, no "locked" plugin cards.
 *  - Hardware addressing: the same card inside the addressing form, where the
 *    hardware-only options would be.
 *  - Control Chain: not advertised at all, icon and window hidden.
 *  - Settings, status and RAM readouts, MIDI-port toggle, snapshot "assign
 *    all": hidden, no card. They are absent for unrelated reasons, and
 *    advertising hardware for them would mislead.
 */

var DesktopApp = {

    /* Where the overlay and the cards send people: the MOD Dwarf product page
     * (Gianfranco, 2026-10-11; it was the retailers page, 2026-10-07). */
    STORE_URL: 'https://mod.audio/dwarf/',

    /* Press photo from mod.audio/dwarf, bundled rather than hotlinked: MOD
     * Desktop runs offline, and fetching it would tell mod.audio who is
     * looking at these panels. It is shot on black, so it sits inside the dark
     * UI without a seam. */
    IMAGE_URL: 'img/desktop-app/dwarf-front.jpg',

    /* The addressing dialog is a white form, where a photo shot on black would
     * be the same mismatch the other way round. This is the press shot on
     * white, cropped to the pedal. */
    IMAGE_URL_LIGHT: 'img/desktop-app/dwarf-light.jpg',

    CTA: 'Discover the MOD Dwarf',

    /* Device-only features that keep their main-menu icon, greyed out. Keyed by
     * the icon's id; clicking one opens the shared overlay with this copy. */
    EXCLUSIVE: {
        'mod-cloud-plugins': {
            feature: 'Plugin Store',
            message: 'The Plugin Store downloads new plugins from the MOD cloud straight ' +
                     'into a MOD device, in one click and with no computer in between. ' +
                     'MOD Desktop ships with a fixed set of plugins.',
        },
        'mod-bank': {
            feature: 'Banks',
            message: 'Banks group your pedalboards so you can step through them with the ' +
                     'footswitches on a MOD device, hands-free and without a screen.',
        },
        'mod-file-manager': {
            feature: 'File Manager',
            message: 'The File Manager puts IRs, NAM captures, audio loops and MIDI files on ' +
                     'a MOD device\'s own storage, where its plugins use them on stage with ' +
                     'no computer attached.',
        },
    },

    /* The Share button on the pedalboard title bar: not an icon with an id, but
     * the same treatment -- greyed, overlay on click. */
    SHARE: {
        feature: 'Share',
        message: 'Sharing publishes a pedalboard to your MOD account, where it joins the ' +
                 'pedalboards other MOD device owners browse and load straight onto their ' +
                 'device. Pedalboards made on MOD Desktop stay on this computer.',
    },

    active: false,

    isActive: function () {
        return DesktopApp.active
    },

    // Render helpers ------------------------------------------------------

    render: function (template, feature, message, extra) {
        return Mustache.render(TEMPLATES[template], $.extend({
            feature: feature,
            message: message,
            cta: DesktopApp.CTA,
            store_url: DesktopApp.STORE_URL,
            image_url: DesktopApp.IMAGE_URL,
            variant: '',
        }, extra || {}))
    },

    /* The card: eyebrow, feature, one sentence, one button, over the photo.
     * Dark and full-window; used inside the Control Chain window and the
     * overlay. */
    panel: function (feature, message) {
        return DesktopApp.render('desktop_app_exclusive_panel', feature, message)
    },

    /* Same card, laid out wide and light, for use inside the addressing form. */
    formPanel: function (feature, message) {
        return DesktopApp.render('desktop_app_exclusive_panel', feature, message, {
            image_url: DesktopApp.IMAGE_URL_LIGHT,
            variant: 'desktop-app-exclusive-form',
        })
    },

    // Overlay -------------------------------------------------------------

    /* One overlay for the three greyed icons, created on first use and reused.
     * Closes on its button, on a click outside the card, and on Escape. */
    overlay: function () {
        var overlay = $('#desktop-app-exclusive-overlay')
        if (overlay.length === 0) {
            overlay = $(Mustache.render(TEMPLATES['desktop_app_exclusive_overlay'], {}))
            overlay.hide().appendTo('body')
            overlay.find('.js-close').click(function () {
                DesktopApp.hideUpsell()
                return false
            })
            // Anywhere outside the card is backdrop: the panel wrapper fills
            // the overlay, so the target is rarely the overlay element itself.
            overlay.click(function (e) {
                if ($(e.target).closest('.desktop-app-exclusive-card').length === 0) {
                    DesktopApp.hideUpsell()
                }
            })
            $(document).keydown(function (e) {
                if (e.keyCode == 27 && overlay.css('display') !== 'none') {
                    DesktopApp.hideUpsell()
                }
            })
        }
        return overlay
    },

    showUpsell: function (feature, message) {
        var overlay = DesktopApp.overlay()
        overlay.find('.desktop-app-exclusive-overlay-content').html(DesktopApp.panel(feature, message))
        overlay.show()
    },

    hideUpsell: function () {
        $('#desktop-app-exclusive-overlay').hide()
    },

    // Setup ---------------------------------------------------------------

    /* Called from index.html, after `desktop` is constructed, only when
     * mod-ui runs as MOD Desktop. */
    setup: function (desktop) {
        DesktopApp.active = true
        $('body').addClass('desktop-app')

        if (desktop) {
            // Shared code (hardware.js through the hardwareManager's isApp
            // option, installMissingPlugins) still asks the controller.
            desktop.isApp = true

            // No analytics on MOD Desktop: the Matomo tag manager is never
            // loaded, whatever the acceptance preference says. The terms
            // popup itself is untouched.
            desktop.setupMatomo = function () {}
        }

        // Not available on desktop, and not a reason to buy hardware.
        $('#mod-settings').hide()
        $('#mod-status').hide()
        $('#mod-ram').hide()
        $('#mod-show-midi-port').hide()
        $('#pedalboards-library').find('a').hide()

        DesktopApp.setupExclusiveIcons()
        DesktopApp.setupShare()
        DesktopApp.hideControlChain()
        DesktopApp.setupAddressing()
    },

    /* Plugin Store, Banks, File Manager: greyed icon, overlay on click, and the
     * feature's own window never opens. window.js bound each window's toggle
     * to its icon when `desktop` constructed the boxes, so that handler goes. */
    setupExclusiveIcons: function () {
        $.each(DesktopApp.EXCLUSIVE, function (id, copy) {
            var icon = $('#' + id)
            icon.off('click')
            icon.addClass('desktop-app-greyed')
            // The store icon is hidden by the non-device branch in index.html,
            // which runs before us.
            icon.show()
            icon.click(function () {
                DesktopApp.showUpsell(copy.feature, copy.message)
                return false
            })
        })
    },

    /* The Share button: desktop.js bound the share window to it; that handler
     * goes, the button stays visible but greyed and opens the overlay. */
    setupShare: function () {
        var button = $('#pedalboard-info').find('.js-cloud')
        button.off('click')
        button.addClass('desktop-app-greyed')
        button.show()
        button.click(function () {
            DesktopApp.showUpsell(DesktopApp.SHARE.feature, DesktopApp.SHARE.message)
            return false
        })
    },

    /* Control Chain is not advertised on MOD Desktop (Gianfranco, 2026-10-08):
     * the status-bar icon and its window are simply gone. cc-manager.js keeps
     * its tooltip on the hidden icon, harmless. */
    hideControlChain: function () {
        $('#mod-devices').hide()
        $('#mod-devices-window').hide()
    },

    setupAddressing: function () {
        // The snapshot "assign all" button drives hardware addressing.
        $('#pedal-presets-window').find('.js-assign-all').hide()
    },

    /* Hardware-only addressing targets stay selectable in the dialog. Picking one
     * puts this card where its addressing options would have been, rather than
     * greying the button out and explaining the refusal somewhere else.
     *
     * There is nothing to save in that state, so the Save button goes with them.
     */
    showAddressingUpsell: function (form) {
        var container = form.find('.main-form-container')
        var card = container.find('.desktop-app-exclusive')

        if (card.length === 0) {
            card = $(DesktopApp.formPanel('Hardware addressing',
                'Assign this parameter to a knob or footswitch and control it with ' +
                'your hands, eyes up, without touching the computer.'))
            container.append(card)
        }

        container.find('.dynamic-field').hide()
        card.show()
        form.find('.js-save').hide()

        // The advanced pane holds label, range, LED colour and sensitivity: all
        // settings of an addressing that cannot be made here. Collapse it through
        // its own toggle, which owns the dialog-width animation.
        var advanced = form.find('.advanced-toggle')
        if (form.find('.advanced-container').is(':visible')) {
            advanced.trigger('click')
        }
        advanced.hide()
    },

    hideAddressingUpsell: function (form) {
        if (! DesktopApp.active) {
            return
        }
        form.find('.main-form-container').find('.desktop-app-exclusive').hide()
        form.find('.js-save').show()
        form.find('.advanced-toggle').show()
    },

    // Update check --------------------------------------------------------

    /* Is a newer MOD Desktop build out for this OS? Builds are GitHub release
     * assets on mod-audio/mod-desktop; pre-releases count (Gianfranco,
     * 2026-11-07), drafts are never listed. A release tag can hold several
     * builds (pre-release "0.14" holds 0.14.1, 0.14.2, ...), so the version is
     * read from the asset names, never from the tag. At most one anonymous
     * request a day, no custom headers, nothing about the user. The
     * launcher's "Check for updates" box turns it off (index.html passes the
     * flag and this OS). */
    RELEASES_API_URL: 'https://api.github.com/repos/mod-audio/mod-desktop/releases?per_page=20',
    RELEASES_TAG_URL: 'https://github.com/mod-audio/mod-desktop/releases/tag/',
    UPDATE_CHECK_INTERVAL: 24 * 60 * 60 * 1000,
    UPDATE_STORAGE_KEY: 'mod-desktop-update-check',

    // the installer each OS downloads; the Windows zip is not offered
    UPDATE_ASSET_SUFFIX: {
        macos: '-macOS.pkg',
        linux: '-linux-x86_64.tar.xz',
        windows: '-win64-installer.exe',
    },

    /* "0.14.2", "v0.14.2" or "0.0.14.37" -> [0, 14, 2] / [0, 0, 14]; else null.
     * Versions are 0.<MOD OS line>.<build> since 2026-11-03; older internal
     * builds had four numbers and only their first three count. */
    parseVersion: function (version) {
        var m = /^v?(\d+)\.(\d+)\.(\d+)(\.\d+)?$/.exec(String(version || '').trim())
        return m ? [parseInt(m[1], 10), parseInt(m[2], 10), parseInt(m[3], 10)] : null
    },

    // numbers, not strings: 0.14.10 is newer than 0.14.9
    compareVersions: function (a, b) {
        for (var i = 0; i < 3; i++) {
            if (a[i] !== b[i]) {
                return a[i] > b[i] ? 1 : -1
            }
        }
        return 0
    },

    /* null when `latest` is not newer than `running`; 'build' when it is the
     * same line (first two numbers) with a higher build, i.e. bug fixes;
     * 'version' when the line is higher, i.e. new features. */
    updateKind: function (latest, running) {
        var a = DesktopApp.parseVersion(latest)
        var b = DesktopApp.parseVersion(running)
        if (!a || !b || DesktopApp.compareVersions(a, b) <= 0) {
            return null
        }
        return (a[0] === b[0] && a[1] === b[1]) ? 'build' : 'version'
    },

    /* The newest build for `platform` in a GitHub releases list:
     * {version: '0.14.2', tag: '0.14'}, or null. Anything that does not look
     * like one of our assets is ignored. */
    newestBuild: function (releases, platform) {
        var suffix = DesktopApp.UPDATE_ASSET_SUFFIX[platform]
        if (!suffix || !Array.isArray(releases)) {
            return null
        }
        var best = null, bestParsed = null
        releases.forEach(function (release) {
            if (!release || release.draft || typeof release.tag_name !== 'string' ||
                !/^v?\d+(\.\d+){1,3}$/.test(release.tag_name) || !Array.isArray(release.assets)) {
                return
            }
            release.assets.forEach(function (asset) {
                var name = asset && typeof asset.name === 'string' ? asset.name : ''
                if (name.indexOf('mod-desktop-') !== 0 || name.slice(-suffix.length) !== suffix) {
                    return
                }
                var version = name.slice('mod-desktop-'.length, -suffix.length)
                var parsed = /^\d+\.\d+\.\d+$/.test(version) ? DesktopApp.parseVersion(version) : null
                if (parsed && (!bestParsed || DesktopApp.compareVersions(parsed, bestParsed) > 0)) {
                    best = { version: version, tag: release.tag_name }
                    bestParsed = parsed
                }
            })
        })
        return best
    },

    /* Per-browser memory: when we last asked, the newest build seen, the
     * version the user skipped. Storage can be missing or throw (private
     * window, blocked site data): then we simply ask on every start. */
    loadUpdateState: function () {
        try {
            var state = JSON.parse(window.localStorage.getItem(DesktopApp.UPDATE_STORAGE_KEY))
            return (state && typeof state === 'object') ? state : {}
        } catch (e) {
            return {}
        }
    },

    saveUpdateState: function (state) {
        try {
            window.localStorage.setItem(DesktopApp.UPDATE_STORAGE_KEY, JSON.stringify(state))
        } catch (e) {}
    },

    /* Called from index.html right after setup(). `running` is this build's
     * VERSION (dev runs use a timestamp: never ask), `platform` is 'macos',
     * 'linux' or 'windows'. */
    checkForUpdate: function (running, enabled, platform, now) {
        if (!enabled || !DesktopApp.parseVersion(running) || !DesktopApp.UPDATE_ASSET_SUFFIX[platform]) {
            return
        }
        now = now || Date.now()

        var state = DesktopApp.loadUpdateState()

        if (state.checkedAt && now - state.checkedAt >= 0 && now - state.checkedAt < DesktopApp.UPDATE_CHECK_INTERVAL) {
            DesktopApp.offerUpdate(running, state)
            return
        }

        $.ajax({
            url: DesktopApp.RELEASES_API_URL,
            type: 'GET',
            dataType: 'json',
            timeout: 15000,
            global: false, // no loading bar for a background request
            success: function (releases) {
                state.checkedAt = now
                var newest = DesktopApp.newestBuild(releases, platform)
                if (newest) {
                    state.latest = newest
                }
                DesktopApp.saveUpdateState(state)
                DesktopApp.offerUpdate(running, state)
            },
            error: function () {
                // Offline or rate-limited: try again tomorrow, keep what we knew.
                state.checkedAt = now
                DesktopApp.saveUpdateState(state)
                DesktopApp.offerUpdate(running, state)
            },
        })
    },

    offerUpdate: function (running, state) {
        var latest = state.latest
        if (!latest || typeof latest !== 'object' || latest.version === state.skipped) {
            return
        }
        var kind = DesktopApp.updateKind(latest.version, running)
        if (kind) {
            DesktopApp.showUpdateBanner(latest.version, latest.tag, kind)
        }
    },

    /* A small bar at the top: what kind of update it is, the release page
     * (notes + downloads), "Skip this version", and a close button that only
     * hides it until the next start. Version and tag were checked against
     * strict patterns before they get here. */
    showUpdateBanner: function (version, tag, kind) {
        if ($('#desktop-app-update-banner').length !== 0) {
            return
        }
        var banner = $(Mustache.render(TEMPLATES['desktop_app_update_banner'], {
            version: version,
            kind: kind === 'build' ? 'new build, bug fixes' : 'new version, new features',
            url: DesktopApp.RELEASES_TAG_URL + encodeURIComponent(tag),
        }))
        banner.find('.js-skip').click(function () {
            var state = DesktopApp.loadUpdateState()
            state.skipped = version
            DesktopApp.saveUpdateState(state)
            banner.remove()
            return false
        })
        banner.find('.js-close').click(function () {
            banner.remove()
            return false
        })
        banner.appendTo('body')
    },
}
