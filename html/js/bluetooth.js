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

function Bluetooth(options) {

    options = $.extend({
        icon: null, // jquery dom element
        frequency: 5000,
        status: function (status) {}
,        notify: function (msg) {
            console.log(msg)
        },
    }, options)

    var icon = options.icon
    var frequency = options.frequency

    var self = this

    this.ping = function () {
        var start = Date.now()
        $.ajax({
            url: '/ping',
            global: false,
            success: function (result) {
                var time = Date.now() - start - result.ihm_time
                self.status(true, time, result.ihm_time)
                setTimeout(self.ping, frequency)
            },
            error: function () {
                self.status(false)
                setTimeout(self.ping, frequency)
            },
            dataType: 'json'
        })
    }

    this.status = function (online, bluetooth, ihm) {
        var msg
        if (online) {
            msg = sprintf('Bluetooth: %dms Controls: %dms', bluetooth, ihm)
            options.status(true)
        } else {
            msg = 'OFFLINE'
            options.status(false)
        }

        options.notify(msg)
    }

    this.ping()
}