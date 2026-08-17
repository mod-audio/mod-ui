/*
 * Copyright 2012-2013 AGR Audio, Industria e Comercio LTDA. <contato@moddevices.com>
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

/*
 * MOD Desktop ("desktop-app") seam.
 *
 * Everything specific to the MOD Desktop application lives here. Note that
 * desktop.js, despite the name, is the shared web GUI controller and runs on
 * the hardware too -- "desktop" there is the pedalboard workspace metaphor,
 * and the file predates MOD Desktop by two years.
 *
 * Where a feature is genuinely exclusive to MOD hardware we now show it with
 * an explanation and a link to the store, rather than hiding it. Features that
 * are merely absent on desktop for unrelated reasons (file manager, settings,
 * status readouts) keep hiding -- advertising hardware for those would mislead.
 */

var DesktopApp = {

    STORE_URL: 'https://mod.audio/dwarf',

    /* Press photo from mod.audio/dwarf, bundled rather than hotlinked: MOD
     * Desktop runs offline, and fetching it would tell mod.audio who is
     * looking at these panels. It is shot on black, so it sits inside the dark
     * UI without a seam.
     */
    IMAGE_URL: 'img/desktop-app/dwarf-front.jpg',

    /* The addressing dialog is a white form, where a photo shot on black would
     * be the same mismatch the other way round. This is the press shot on
     * white, cropped to the pedal. */
    IMAGE_URL_LIGHT: 'img/desktop-app/dwarf-light.jpg',

    /* The cloud plugin store has no x86_64 builds at all -- every plugin in it
     * is built for arm-a7 (Duo), aarch64-a53 (Duo X), aarch64-a35 (Dwarf) or
     * aarch64-a76. Querying with MOD Desktop's own bin_compat (linux-x64_64)
     * returns an empty catalogue, which is why the store was hidden here.
     *
     * So we browse the store as a Dwarf. It is a non-functional preview:
     * nothing is installable and the desktop plugin set is static regardless.
     * Plugin URIs are shared between device and store, so the existing
     * local/cloud merge in cloudplugin.js still marks installed plugins.
     */
    STORE_BIN_COMPAT: 'aarch64-a35',

    active: false,

    isActive: function () {
        return DesktopApp.active
    },

    // Render helpers ------------------------------------------------------

    render: function (template, feature, message, extra) {
        return Mustache.render(TEMPLATES[template], $.extend({
            feature: feature,
            message: message,
            cta: 'Discover the MOD Dwarf',
            store_url: DesktopApp.STORE_URL,
            image_url: DesktopApp.IMAGE_URL,
            variant: '',
        }, extra || {}))
    },

    panel: function (feature, message) {
        return DesktopApp.render('desktop_app_exclusive_panel', feature, message)
    },

    /* Same card, laid out wide and light, for use inside a form. */
    formPanel: function (feature, message) {
        return DesktopApp.render('desktop_app_exclusive_panel', feature, message, {
            image_url: DesktopApp.IMAGE_URL_LIGHT,
            variant: 'desktop-app-exclusive-form',
        })
    },

    /* Same card again, short and horizontal, for a spot inside a page that already
     * has its own content -- the plugin page, where it stands in for a button. */
    compactPanel: function (feature, message) {
        return DesktopApp.render('desktop_app_exclusive_panel', feature, message, {
            variant: 'desktop-app-exclusive-compact',
        })
    },

    // Plugin store --------------------------------------------------------

    /* Rewrites an outgoing cloud store query so the catalogue is the Dwarf's.
     * image_version has to be deleted rather than overridden: MOD Desktop's
     * VERSION is its own release number, which matches no device image and
     * makes the API return nothing.
     */
    storeQuery: function (query) {
        if (! DesktopApp.active) {
            return query
        }
        query.bin_compat = DesktopApp.STORE_BIN_COMPAT
        delete query.image_version
        return query
    },

    /* Takes the Install button's place on the plugin page. Everything else on that
     * page -- screenshot, ports, description -- stays, because browsing the
     * catalogue is real; only installing is not. */
    pluginMessage: function () {
        return DesktopApp.compactPanel('Install this plugin',
            'Every plugin in this store is built for MOD Audio hardware. On a MOD ' +
            'device it installs in one click and plays standalone, with no computer.')
    },

    // Setup ---------------------------------------------------------------

    setup: function (desktop) {
        DesktopApp.active = true
        $('body').addClass('desktop-app')

        // Not available on desktop, and not a reason to buy hardware.
        $('#mod-file-manager').hide()
        $('#mod-settings').hide()
        $('#mod-status').hide()
        $('#mod-ram').hide()
        $('#mod-show-midi-port').hide()
        $('#pedalboards-library').find('a').hide()

        // Hidden by the USING_MOD_DEVICE branch in index.html, which runs
        // before us. Bring the store back as a browsable preview.
        $('#mod-cloud-plugins').show()

        DesktopApp.setupBanks()
        DesktopApp.setupControlChain()
        DesktopApp.setupAddressing()
    },

    setupBanks: function () {
        var box = $('#bank-library').find('.box').first()
        box.find('#bank-list, #bank-edit, #bank-pedalboards-search').hide()
        box.append(DesktopApp.panel('Banks',
            'Banks group your pedalboards so you can step through them with the ' +
            'footswitches on a MOD device, hands-free and without a screen.'))
    },

    setupControlChain: function () {
        var box = $('#mod-devices-window').find('.box').first()
        box.find('.mod-devices-window-list').hide()
        box.append(DesktopApp.panel('Control Chain',
            'Control Chain lets you plug expression pedals, footswitches and other ' +
            'controllers straight into a MOD device and assign them to any parameter.'))
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
