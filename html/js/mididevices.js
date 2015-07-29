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

function MidiDevicesWindow(options) {
    var self = this;

    options = $.extend({
        midiDevicesWindow: $('<div>'),
        midiDevicesList: $('<div>'),
    }, options)

    options.midiDevicesWindow.find('.js-cancel').click(function () {
        options.midiDevicesWindow.hide()
        return false
    })

    options.midiDevicesWindow.find('.js-submit').click(function () {
        var devs = []
        self.selectedDevicesCallback(devs)

        options.midiDevicesWindow.hide()
        return false
    })

    this.selectedDevicesCallback = function () {}

    this.start = function (callback) {
        self.selectedDevicesCallback = callback

        // clear old entries
        options.midiDevicesList.find('input').remove()
        options.midiDevicesList.find('span').remove()

        self.getDeviceList(function (devs) {
            if (devs.length == 0)
                return new Notification("info", "No MIDI devices available")

            // add news ones
            for (var i in devs) {
                var elem = $('<input type="checkbox" name="" value="' + devs[i] + '" checked/><span>' + devs[i] + '<br/></span>')
                elem.appendTo(options.midiDevicesList)
            }

            options.midiDevicesWindow.show()
        })
    }

    this.getDeviceList = function (callback) {
        $.ajax({
            url: '/jack/midi_devices',
            type: 'GET',
            success: function (resp) {
                callback(resp)
            },
            error: function () {
                new Bug("Failed to get list of MIDI devices")
            },
            cache: false,
            dataType: 'json'
        })
    }
}
