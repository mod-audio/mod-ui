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

function PedalboardPresetsManager(options) {
    var self = this;

    options = $.extend({
        pedalPresetsWindow: $('<div>'),
        pedalPresetsList: $('<div>'),
    }, options)

    options.pedalPresetsWindow.find('.js-cancel').click(function () {
        options.pedalPresetsWindow.hide()
        return false
    })

    options.pedalPresetsWindow.find('.js-rename').click(function () {
        console.log(this)
        // TODO
        return false
    })

    options.pedalPresetsWindow.find('.js-delete').click(function () {
        console.log(this)
        // TODO
        return false
    })

    options.pedalPresetsWindow.find('.js-assign').click(function () {
        console.log(this)
        // TODO
        return false
    })

    options.pedalPresetsWindow.find('.js-assign-all').click(function () {
        console.log(this)
        // TODO
        return false
    })

    this.start = function () {
        // clear old entries
        //options.pedalPresetsList.find('input').remove()
        //options.pedalPresetsList.find('span').remove()

        console.log("here 001")

        var presets = []

        /*
        if (presets.length == 0)
            return new Notification("info", "No pedalboard presets available")
        */

        // add new ones
        for (var i in presets) {
            var preset = presets[i]
            var elem   = $('<input type="checkbox" name="' + name + '" value="' + dev + '" '
                       + (devsInUse.indexOf(dev) >= 0 ? "checked" : "") + '/><span>' + name + '<br/></span>')

            elem.appendTo(options.pedalPresetsList)
        }

        options.pedalPresetsWindow.show()
        console.log(options.pedalPresetsWindow[0])
    }

    this.savePresets = function (presets) {
        /*
        $.ajax({
            url: '/jack/set_midi_devices',
            type: 'POST',
            data: JSON.stringify(presets),
            error: function () {
                new Bug("Failed to save pedalboard presets")
            },
            cache: false,
            dataType: 'json'
        })
        */
    }
}
