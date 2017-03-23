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

function ControlChainDeviceManager(options) {
    var self = this;

    options = $.extend({
        devicesIcon: $('<div>'),
        updateInfoWindow: $('<div>'),
        setIconTooltip: function (msg) {},
        showNotification: function (msg, timeout) {},
    }, options)

    this.connectedDevices = []

    options.devicesIcon.statusTooltip()
    options.devicesIcon.statusTooltip('message', "No Control Chain devices connected", true)

    options.updateInfoWindow.find('.js-cancel').click(function () {
        options.updateInfoWindow.hide()
        return false
    })

    this.showUpdateWindow = function () {
        options.updateInfoWindow.show()
    }

    this.hideUpdateWindow = function () {
        options.updateInfoWindow.hide()
    }

    this.deviceAdded = function (dev_uri, label, version) {
        var item = [dev_uri, label, version]
        self.connectedDevices.push(item)
        self._devicesUpdated()

        options.showNotification('New Control Chain device connected:<br/>' + label + ' v' + version)
    }

    this.deviceRemoved = function (dev_uri, label, version) {
        var item
        for (var i in self.connectedDevices) {
            item = self.connectedDevices[i]
            if (item[0] == dev_uri && item[1] == label && item[2] == version) {
                self.connectedDevices.splice(i, 1)
                break
            }
        }
        self._devicesUpdated()

        options.showNotification('Control Chain device disconnected:<br/>' + label + ' v' + version)
    }

    this._devicesUpdated = function () {
        var count = self.connectedDevices.length
        if (count == 0) {
            options.devicesIcon
            .removeClass('ico_cpu')
            .removeClass('ico_faders')
            .removeClass('ico_knob')
            .removeClass('ico_switch')
            .statusTooltip('message', "No Control Chain devices connected", true)

        } else if (count == 1) {
            var icoclass, msg

            // set icon depending on label
            switch (self.connectedDevices[0][0]) {
            case "https://github.com/moddevices/cc-fw-footswitch":
                icoclass = 'ico_switch'
                msg = "1 MOD Footswitch connected"
                break
            default:
                icoclass = 'ico_cpu'
                msg = "1 Control Chain device connected"
                break
            }

            options.devicesIcon
            .removeClass('ico_cpu')
            .removeClass('ico_faders')
            .removeClass('ico_knob')
            .removeClass('ico_switch')
            .addClass(icoclass)
            .statusTooltip('message', msg, true)

        } else {
            var msg = sprintf("%d Control Chain devices connected", count)
            options.devicesIcon
            .removeClass('ico_cpu')
            .removeClass('ico_faders')
            .removeClass('ico_knob')
            .removeClass('ico_switch')
            .addClass('ico_faders')
            .statusTooltip('message', msg, true)
        }
    }
}
