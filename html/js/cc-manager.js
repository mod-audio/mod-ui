// SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
// SPDX-License-Identifier: AGPL-3.0-or-later

function ControlChainDeviceManager(options) {
    var self = this;

    options = $.extend({
        devicesIcon: $('<div>'),
        devicesWindow: $('<div>'),
        updateInfoWindow: $('<div>'),
        setIconTooltip: function (msg) {},
        showNotification: function (msg, timeout) {},
        cancelDownload: function (callback) { callback() },
    }, options)

    this.connectedDevices = []
    this.devicesListElem = options.devicesWindow.find('.mod-devices-window-list > ul')

    options.devicesIcon.statusTooltip()
    options.devicesIcon.statusTooltip('message', "No Control Chain devices connected", true)

    options.devicesIcon.click(function () {
        if (options.devicesWindow.is(':visible')) {
            options.devicesWindow.hide()
        } else if (self.connectedDevices.length > 0) {
            options.devicesWindow.show()
        }
    })

    options.updateInfoWindow.find('.js-cancel').click(function () {
        options.cancelDownload(function () {
            options.updateInfoWindow.hide()
        })
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
        self.deviceConnected(label, version)
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
        self.deviceDisconnected(label, version)
    }

    this.deviceConnected = function (label, version) {
        options.showNotification('New Control Chain device connected:<br/>' + label + ' v' + version)
    }

    this.deviceDisconnected = function (label, version) {
        options.showNotification('Control Chain device disconnected:<br/>' + label + ' v' + version)
    }

    this._devicesUpdated = function () {
        var count = self.connectedDevices.length
        if (count == 0) {
            options.devicesIcon.statusTooltip('message', "No Control Chain devices connected", true)
            options.devicesWindow.hide()
            self.devicesListElem.html("<li>No Control Chain devices connected</li>")

        } else {
            var item, lihtml = ""
            for (var i in self.connectedDevices) {
                item = self.connectedDevices[i]
                lihtml += "<li>" +
                          "<b>" + item[1] + "</b><br/>" +
                          "URI: " + item[0] + "<br/>" +
                          "Version: " + item[2] +
                          "</li>"
            }
            self.devicesListElem.html(lihtml)

            var msg
            if (count == 1) {
                msg = "1 Control Chain device activated"
            } else {
                msg = sprintf("%d Control Chain devices activated", count)
            }
            options.devicesIcon.statusTooltip('message', msg, true)
        }
    }
}
