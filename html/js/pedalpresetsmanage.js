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
        presetsWindow: $('<div>'),
        presetsList: $('<div>'),
    }, options)

    options.presetsWindow.find('.js-cancel').click(function () {
        options.presetsWindow.hide()
        return false
    })

    options.presetsWindow.find('.js-submit').click(function () {
        var presets = []

        /*
        $.each(options.presetsList.find('input'), function (index, input) {
            var input = $(input)
            if (input.is(':checked'))
                devs.push(input.val())
        })
        */

        self.savePresets(presets)
        options.presetsWindow.hide()
        return false
    })

    this.start = function () {
        // clear old entries
        options.presetsList.find('input').remove()
        options.presetsList.find('span').remove()

        var presets = []

        if (presets.length == 0)
            return new Notification("info", "No pedalboard presets available")

        // add new ones
        for (var i in presets) {
            var preset = presets[i]
            var elem   = $('<input type="checkbox" name="' + name + '" value="' + dev + '" '
                       + (devsInUse.indexOf(dev) >= 0 ? "checked" : "") + '/><span>' + name + '<br/></span>')

            elem.appendTo(options.presetsList)
        }

        options.presetsWindow.show()
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
