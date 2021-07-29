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

        var midiAggregatedMode = options.midiPortsWindow.find('input[name=midi-mode]:checked').val() === "aggregated";
        var midiLoopback = !!options.midiPortsWindow.find('#midi-loopback').prop('checked');

        $.each(options.midiPortsList.find('input'), function (index, input) {
            var input = $(input)
            if (input.is(':checked')) {
                devs.push(input.val())
            }
        })

        self.selectDevices(devs, midiAggregatedMode, midiLoopback)
        options.midiPortsWindow.hide()
        return false
    })

    this.start = function () {
        // clear old entries
        options.midiPortsList.find('input').remove()
        options.midiPortsList.find('span').remove()

        self.getDeviceList(function (devsInUse, devList, names, midiAggregatedMode) {
            hasMidiLoopback = false

            // add new ones
            for (var i in devList) {
                var dev  = devList[i]
                var name = names[dev]
                var elem = $('<input type="checkbox" name="' + name + '" value="' + dev + '" autocomplete="off"'
                         + (devsInUse.indexOf(dev) >= 0 ? ' checked="checked"' : '')
                         + '/><span>' + name + '<br/></span>')

                if (name === "MIDI Loopback") {
                    hasMidiLoopback = true
                    options.midiPortsWindow.find('#midi-loopback').prop('checked', devsInUse.indexOf(dev) >= 0).parent().show()
                } else {
                    elem.appendTo(options.midiPortsList)
                }
            }

            // Check midi mode
            var midiModeRadios = options.midiPortsWindow.find('input:radio[name=midi-mode]');
            if (midiAggregatedMode) {
                midiModeRadios.filter('[value=aggregated]').prop('checked', true);
            } else {
                midiModeRadios.filter('[value=separated]').prop('checked', true);
            }

            if (! hasMidiLoopback) {
                options.midiPortsWindow.find('#midi-loopback').prop('checked', false).parent().hide()
            }

            options.midiPortsWindow.show()
        })
    }

    this.getDeviceList = function (callback) {
        $.ajax({
            url: '/jack/get_midi_devices',
            type: 'GET',
            success: function (resp) {
                callback(resp.devsInUse, resp.devList, resp.names, resp.midiAggregatedMode)
            },
            error: function () {
                new Bug("Failed to get list of MIDI devices")
            },
            cache: false,
            dataType: 'json'
        })
    }

    this.selectDevices = function (devs, midiAggregatedMode, midiLoopback) {
        $.ajax({
            url: '/jack/set_midi_devices',
            type: 'POST',
            data: JSON.stringify({
                devs: devs,
                midiAggregatedMode: midiAggregatedMode,
                midiLoopback: midiLoopback,
            }),
            error: function () {
                new Bug("Failed to enable some MIDI devices")
            },
            cache: false,
            dataType: 'json'
        })
    }
}
