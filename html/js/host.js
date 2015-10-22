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

$('document').ready(function() {
    var ws = new WebSocket("ws://" + window.location.host + "/websocket");

    ws.onmessage = function (evt) {
        var data = evt.data.split(" ")

        if (!data.length) {
            return
        }

        var cmd = data[0]

        if (cmd == "cpu_load") {
            var value = data[1]
            $("#cpu-bar").css("width", (100.0-value).toFixed().toString()+"%")
            $("#cpu-bar-text").text("CPU "+value.toString()+"%")
            return
        }

        if (cmd == "param_set") {
            var instance = data[1]
            var symbol   = data[2]
            var value    = parseFloat(data[3])
            desktop.pedalboard.pedalboard("setPortWidgetsValue", instance, symbol, value);
            return
        }

        if (cmd == "add") {
            var instance = data[1]
            var uri      = data[2]
            var x        = parseFloat(data[3])
            var y        = parseFloat(data[4])
            var bypassed = parseInt(data[5]) != 0
            var plugins  = desktop.pedalboard.data('plugins')

            if (plugins[instance] == null) {
                plugins[instance] = {} // register plugin
                $.ajax({
                    url: '/effect/get?uri=' + escape(uri),
                    success: function (pluginData) {
                        var instancekey = '[mod-instance="' + instance + '"]'

                        if (!$(instancekey).length) {
                            var cb = function () {
                                desktop.pedalboard.pedalboard('adapt')

                                var waiter = desktop.pedalboard.data('wait')

                                if (waiter.plugins[instance])
                                    waiter.stopPlugin(instance)

                                $(document).unbindArrive(instancekey, cb)
                            }
                            $(document).arrive(instancekey, cb)
                        }

                        desktop.pedalboard.pedalboard("addPlugin", pluginData, instance, bypassed, x, y, {})
                    },
                    cache: false,
                    dataType: 'json'
                })
            }
            return
        }

        console.log(data)
    }
})
