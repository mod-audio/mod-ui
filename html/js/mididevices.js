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

function MidiPortsWindow(options) {
    var self = this;

    options = $.extend({
        midiPortsWindow: $('<div>'),
        midiPortsList: $('<div>'),
    }, options)

    options.midiPortsWindow.find('.js-cancel').click(function () {
        options.midiPortsWindow.hide()
        return false
    })

    options.midiPortsWindow.find('.js-submit').click(function () {
        var devs = []

        $.each(options.midiPortsList.find('input'), function (index, input) {
            var input = $(input)
            if (input.is(':checked'))
                devs.push(input.val())
        })

        self.selectDevices(devs)
        options.midiPortsWindow.hide()
        return false
    })

    this.start = function () {
        // clear old entries
        options.midiPortsList.find('input').remove()
        options.midiPortsList.find('span').remove()

        self.getDeviceList(function (devsInUse, devList, names) {
            if (devList.length == 0)
                return new Notification("info", "No MIDI devices available")

            // add new ones
            for (var i in devList) {
                var dev  = devList[i]
                var name = names[dev]
                var elem = $('<input type="checkbox" name="' + name + '" value="' + dev + '" autocomplete="off"'
                         + (devsInUse.indexOf(dev) >= 0 ? 'checked="checked"' : '') + '/><span>' + name + '<br/></span>')

                elem.appendTo(options.midiPortsList)
            }

            options.midiPortsWindow.show()
        })
    }

    this.getDeviceList = function (callback) {
        $.ajax({
            url: '/jack/get_midi_devices',
            type: 'GET',
            success: function (resp) {
                callback(resp.devsInUse, resp.devList, resp.names)
            },
            error: function () {
                new Bug("Failed to get list of MIDI devices")
            },
            cache: false,
            dataType: 'json'
        })
    }

    this.selectDevices = function (devs) {
        $.ajax({
            url: '/jack/set_midi_devices',
            type: 'POST',
            data: JSON.stringify(devs),
            error: function () {
                new Bug("Failed to enable some MIDI devices")
            },
            cache: false,
            dataType: 'json'
        })
    }
}
