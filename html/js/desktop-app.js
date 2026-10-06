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
 *    greyed out. Clicking it opens ONE shared overlay -- a Dwarf press shot,
 *    the feature name, one sentence on what it does on a MOD device and a
 *    button to the website -- instead of the feature's own window. No store
 *    preview, no store queries, no "locked" plugin cards.
 *  - Control Chain window and hardware addressing: the same card inside the
 *    window / the addressing form, where the hardware-only content would be.
 *  - Settings, status and RAM readouts, MIDI-port toggle, snapshot "assign
 *    all": hidden, no card. They are absent for unrelated reasons, and
 *    advertising hardware for them would mislead.
 */

var DesktopApp = {

    /* Where the overlay and the cards send people: the buy page (Gianfranco,
     * 2026-10-07). */
    STORE_URL: 'https://mod.audio/retailers/',

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
        DesktopApp.setupControlChain()
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

    /* The Control Chain icon keeps its window, which carries the card instead
     * of the device list. cc-manager.js only opens that window while a device
     * is connected -- never, here -- so the icon gets a plain toggle instead.
     * The window is a small white popup above the icon, hence the wide light
     * layout of the card. */
    setupControlChain: function () {
        var win = $('#mod-devices-window')
        var box = win.find('.box').first()
        box.find('.mod-devices-window-list').hide()
        box.append(DesktopApp.formPanel('Control Chain',
            'Control Chain lets you plug expression pedals, footswitches and other ' +
            'controllers straight into a MOD device and assign them to any parameter.'))

        $('#mod-devices').off('click').click(function () {
            if (win.css('display') !== 'none') {
                win.hide()
            } else {
                win.show()
            }
        })
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
}
