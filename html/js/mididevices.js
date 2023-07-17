// SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
// SPDX-License-Identifier: AGPL-3.0-or-later

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
