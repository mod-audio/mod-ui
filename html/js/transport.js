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

function TransportControls(options) {
    var self = this;

    options = $.extend({
        transportButton: $('<div>'),
        transportWindow: $('<div>'),
        transportPlay: $('<div>'),
        transportBPB: $('<div>'),
        transportBPM: $('<div>'),
        transportSyncMode: $('<div>'),
        openAddressingDialog: function (port, label) {
        },
        unaddressPort: function (portSymbol, callback) {
            callback()
        },
    }, options)

    this.rollingPort = {
        name: 'Rolling',
        shortName: 'Rolling',
        symbol: ':rolling',
        ranges: {
            minimum: 0.0,
            maximum: 1.0,
            default: 0.0,
        },
        comment: "",
        designation: "",
        properties: ["toggled"],
        enabled: true,
        value: 0.0,
        format: null,
        units: {},
        scalePoints: [],
        widget: options.transportPlay.find(".mod-switch-image"),
    }
    this.rollingPort.widget.controlWidget({
        dummy: false,
        port: self.rollingPort,
        change: function (e, value) {
            var rolling = (value > 0.5)
            ws.send("transport-rolling " + (rolling ? "1" : "0"))
            self.setPlaybackState(rolling, false, true)
        }
    })
    options.transportPlay.find(".mod-address").click(function (e) {
        options.openAddressingDialog(self.rollingPort, "Global-Rolling")
    })

    this.beatsPerBarPort = {
        name: 'Beats Per Bar',
        shortName: 'Beats Per Bar',
        symbol: ':bpb',
        ranges: {
            minimum: 1.0,
            maximum: 16.0,
            default: 4.0,
        },
        comment: "",
        designation: "",
        properties: ["integer"],
        enabled: true,
        value: null,
        format: null,
        units: {},
        scalePoints: [],
        widget: options.transportBPB.find(".mod-knob-image"),
    }
    this.beatsPerBarPort.widget.controlWidget({
        dummy: false,
        port: self.beatsPerBarPort,
        change: function (e, value) {
            ws.send("transport-bpb " + value)
            self.setBeatsPerBarValue(value, false, true)
        }
    })
    options.transportBPB.find(".mod-address").click(function (e) {
        options.openAddressingDialog(self.beatsPerBarPort, "Global-BPB")
    })
    options.transportBPB.find(".mod-knob-current-value")
    .attr('contenteditable', true)
    .focus(function () {
        self.setBeatsPerBarValue(self.beatsPerBarPort.value, false, false)
    })
    .keydown(function (e) {
        // enter
        if (e.keyCode == 13) {
            $(this).blur()
            return false
        }
        // numbers
        if (e.keyCode >= 48 && e.keyCode <= 57) {
            return true;
        }
        if (e.keyCode >= 96 && e.keyCode <= 105) {
            return true;
        }
        // backspace and delete
        if (e.keyCode == 8 || e.keyCode == 46 || e.keyCode == 110) {
            return true;
        }
        // left, right
        if (e.keyCode == 37 || e.keyCode == 39) {
            return true;
        }
        // prevent key
        e.preventDefault();
        return false
    })
    .blur(function () {
        var value = parseFloat($(this).text())
        if (isNaN(value)) {
            value = self.beatsPerBarPort.value
        } else if (value < self.beatsPerBarPort.ranges.minimum) {
            value = self.beatsPerBarPort.ranges.minimum
        } else if (value > self.beatsPerBarPort.ranges.maximum) {
            value = self.beatsPerBarPort.ranges.maximum
        }
        ws.send("transport-bpb " + value)
        self.setBeatsPerBarValue(value, true, true)
    })

    this.beatsPerMinutePort = {
        name: 'Beats Per Minute',
        shortName: 'Beats Per Minute',
        symbol: ':bpm',
        ranges: {
            minimum: 20.0,
            maximum: 280.0,
            default: 120.0,
        },
        comment: "",
        designation: "",
        properties: ["integer", "tapTempo"],
        enabled: true,
        value: null,
        format: null,
        units: {
            symbol: "bpm",
        },
        scalePoints: [],
        widget: options.transportBPM.find(".mod-knob-image"),
    }
    this.beatsPerMinutePort.widget.controlWidget({
        dummy: false,
        port: self.beatsPerMinutePort,
        change: function (e, value) {
            ws.send("transport-bpm " + value)
            self.setBeatsPerMinuteValue(value, false, true)
        }
    })
    options.transportBPM.find(".mod-address").click(function (e) {
        if ($(this).hasClass('link-enabled') || $(this).hasClass('midi-clock-slave-enabled')) {
            var img = $('<img>').attr('src', 'img/icn-blocked.png')
            $('body').append(img)
            img.css({
                position: 'absolute',
                top: e.pageY - img.height() / 2,
                left: e.pageX - img.width() / 2,
                zIndex: 99999
            })
            setTimeout(function () {
                img.remove()
            }, 500)
            var message
            if ($(this).hasClass('link-enabled')) {
              message = "Cannot address BPM parameter with Link enabled"
            } else if ($(this).hasClass('midi-clock-slave-enabled')) {
              message = "Cannot address BPM parameter with MIDI Clock Slave enabled"
            }
            new Notification("warn", message, 5000)
            return false
        }
        options.openAddressingDialog(self.beatsPerMinutePort, "Global-BPM")
    })
    options.transportBPM.find(".mod-knob-current-value")
    .attr('contenteditable', true)
    .focus(function () {
        self.setBeatsPerMinuteValue(self.beatsPerMinutePort.value, false, false)
    })
    .keydown(function (e) {
        // enter
        if (e.keyCode == 13) {
            $(this).blur()
            return false
        }
        // numbers
        if (e.keyCode >= 48 && e.keyCode <= 57) {
            return true;
        }
        if (e.keyCode >= 96 && e.keyCode <= 105) {
            return true;
        }
        // backspace and delete
        if (e.keyCode == 8 || e.keyCode == 46 || e.keyCode == 110) {
            return true;
        }
        // left, right, dot
        if (e.keyCode == 37 || e.keyCode == 39 || e.keyCode == 190) {
            return true;
        }
        // prevent key
        e.preventDefault();
        return false
    })
    .blur(function () {
        var value = parseFloat($(this).text())
        if (isNaN(value)) {
            value = self.beatsPerMinutePort.value
        } else if (value < self.beatsPerMinutePort.ranges.minimum) {
            value = self.beatsPerMinutePort.ranges.minimum
        } else if (value > self.beatsPerMinutePort.ranges.maximum) {
            value = self.beatsPerMinutePort.ranges.maximum
        }
        ws.send("transport-bpm " + value)
        self.setBeatsPerMinuteValue(value, true, true)
    })

    var syncMode,
        syncModeWidgets = options.transportSyncMode.find('.mod-enumerated-list').children()
    syncModeWidgets.each(function() {
        var opt = $(this)
        opt.click(function (e) {
            var newSyncMode = opt.attr('mod-sync-mode')
            if (newSyncMode === "link") {
                options.unaddressPort(":bpm", function (ok) {
                    if (! ok) {
                        return
                    }
                    ws.send("midi_clock_slave_enable 0")
                    ws.send("link_enable 1")

                    self.setControlEnabled(":bpm", true)
                    self.setSyncMode(newSyncMode)
                })
            } else if (newSyncMode === "midi_clock_slave") {
                options.unaddressPort(":bpm", function (ok) {
                    if (! ok) {
                        return
                    }
                    // Send commands to host to disable link if needed and enable MIDI clock slave
                    ws.send("link_enable 0")
                    ws.send("midi_clock_slave_enable 1")
                    // Disable BPM control from mod-ui (resulting in BPM knob being greyed out and unresponsive)
                    self.setControlEnabled(":bpm", false, false)
                    // Set new sync mode to disable addressing from mod-ui
                    self.setSyncMode(newSyncMode)
                })
            } else {
                ws.send("link_enable 0")
                ws.send("midi_clock_slave_enable 0")
                self.setControlEnabled(":bpm", true)
                self.setSyncMode(newSyncMode)
            }
        })
    })

    options.transportButton.click(function (e) {
        if (options.transportWindow.is(":visible")){
            options.transportWindow.hide()
        } else {
            options.transportWindow.show()
        }
    })

    this.address = function (el, enabled, feedback) {
      var addressEl = el.find('.mod-address')
      if (enabled) {
        addressEl.removeClass('addressed')
      } else {
        if (feedback) {
          addressEl.addClass('addressed')
        } else {
          addressEl.removeClass('addressed')
        }
      }
    }

    this.setControlEnabled = function (portSymbol, enabled, feedback) {
        var disableClassname = feedback ? 'address' : 'disable'
        if (portSymbol == ":bpb") {
            self.address(options.transportBPB, enabled, feedback)
            self.beatsPerBarPort.widget.controlWidget(enabled ? 'enable' : disableClassname)
            options.transportBPB.find(".mod-knob-current-value").attr('contenteditable', enabled || feedback)
        } else if (portSymbol == ":bpm") {
            self.address(options.transportBPM, enabled, feedback)
            self.beatsPerMinutePort.widget.controlWidget(enabled ? 'enable' : disableClassname)
            options.transportBPM.find(".mod-knob-current-value").attr('contenteditable', enabled || feedback)
        } else if (portSymbol == ":rolling") {
            self.address(options.transportPlay, enabled, feedback)
            self.rollingPort.widget.controlWidget(enabled ? 'enable' : disableClassname)
        }
    }

    this.resetControlsEnabled = function () {
        self.setControlEnabled(":bpb", true)
        self.setControlEnabled(":bpm", true)
        self.setControlEnabled(":rolling", true)
    }

    this.setPlaybackState = function (playing, set_control, set_hmi) {
        var value = playing ? 1.0 : 0.0
        if (self.rollingPort.value == value) {
            return
        }
        self.rollingPort.value = value

        if (set_control) {
            self.rollingPort.widget.controlWidget('setValue', value, true)
        }
        if (set_hmi) {
          portSymbol = '/pedalboard/:rolling'
          if (desktop.hardwareManager.addressingsByPortSymbol[portSymbol]) {
              paramchange = (portSymbol + '/' + value)
              desktop.ParameterSet(paramchange)
          }
        }

        if (playing) {
            options.transportButton.addClass("playing")
        } else {
            options.transportButton.removeClass("playing")
        }
    }

    this.setBeatsPerBarValue = function (bpb, set_control, set_hmi) {
        if (self.beatsPerBarPort.value == bpb) {
            return
        }
        self.beatsPerBarPort.value = bpb

        var text = sprintf("%d/4", bpb)
        if (bpb < 10) {
            text = "&nbsp;" + text
        }
        self.beatsPerBarPort.value = bpb

        if (set_control) {
            self.beatsPerBarPort.widget.controlWidget('setValue', bpb, true)
        }
        if (set_hmi) {
          portSymbol = '/pedalboard/:bpb'
          if (desktop.hardwareManager.addressingsByPortSymbol[portSymbol]) {
              paramchange = (portSymbol + '/' + bpb)
              desktop.ParameterSet(paramchange)
          }
        }

      options.transportBPB.find(".mod-knob-current-value").html(text)
    }

    this.setBeatsPerMinuteValue = function (bpm, set_control, set_hmi) {
        if (self.beatsPerMinutePort.value == bpm) {
            return
        }
        var text = sprintf("%.2f BPM", bpm)
        if (bpm < 100.0) {
            text = "&nbsp;" + text
        }
        self.beatsPerMinutePort.value = bpm
        options.setNewBeatsPerMinuteValue(bpm)

        if (set_control) {
            self.beatsPerMinutePort.widget.controlWidget('setValue', bpm, true)
        }
        if (set_hmi) {
          portSymbol = '/pedalboard/:bpm'
          if (desktop.hardwareManager.addressingsByPortSymbol[portSymbol]) {
              paramchange = (portSymbol + '/' + bpm)
              desktop.ParameterSet(paramchange)
          }
        }

        options.transportButton.find('span').html(text)
        options.transportBPM.find(".mod-knob-current-value").html(text)
    }

    this.setSyncMode = function (newSyncMode) {
        if (newSyncMode == syncMode) {
            return
        }
        syncMode = newSyncMode

        syncModeWidgets.removeClass('selected')
        options.transportSyncMode.find('[mod-sync-mode="'+newSyncMode+'"]').addClass('selected')

        if (newSyncMode == "link") {
            // TODO: remove addressings
            options.transportBPM.find(".mod-address").addClass('link-enabled')
        } else {
            options.transportBPM.find(".mod-address").removeClass('link-enabled')
        }

        if (newSyncMode == "midi_clock_slave") {
          options.transportBPM.find(".mod-address").addClass('midi-clock-slave-enabled')
        } else {
          options.transportBPM.find(".mod-address").removeClass('midi-clock-slave-enabled')
        }
    }

    this.setValues = function (playing, bpb, bpm, newSyncMode) {
        self.setPlaybackState(playing, true, false)
        self.setBeatsPerBarValue(bpb, true, false)
        self.setBeatsPerMinuteValue(bpm, true, false)
        self.setSyncMode(newSyncMode)
    }
}
