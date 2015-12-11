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

var ws

$('document').ready(function() {
    ws = new WebSocket("ws://" + window.location.host + "/websocket")

    var waiting = false

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

        if (cmd == "mem_load") {
            var value = data[1]
            $("#ram-bar").css("width", (100.0-value).toFixed().toString()+"%")
            $("#ram-bar-text").text("RAM "+value.toString()+"%")
            return
        }

        if (cmd == "param_set") {
            var instance = data[1]
            var symbol   = data[2]
            var value    = parseFloat(data[3])
            desktop.pedalboard.pedalboard("setPortWidgetsValue", instance, symbol, value);
            return
        }

        if (cmd == "connect") {
            var source  = data[1]
            var target  = data[2]
            var connMgr = desktop.pedalboard.data("connectionManager")

            if (! connMgr.connected(source, target)) {
                var sourceport = '[mod-port="' + source.replace(/\//g, "\\/") + '"]'
                var targetport = '[mod-port="' + target.replace(/\//g, "\\/") + '"]'

                var output = $(sourceport)

                if (output.length) {
                    var input = $(targetport)
                    var jack  = output.find('[mod-role=output-jack]')

                    if (input.length) {
                        desktop.pedalboard.pedalboard('connect', jack, input)
                    } else {
                        var cb = function () {
                            var input = $(targetport)
                            desktop.pedalboard.pedalboard('connect', jack, input)
                            $(document).unbindArrive(targetport, cb)
                        }
                        $(document).arrive(targetport, cb)
                    }
                } else {
                    var cb = function () {
                        var output = $(sourceport)
                        var input  = $(targetport)
                        var jack   = output.find('[mod-role=output-jack]')

                        if (input.length) {
                            desktop.pedalboard.pedalboard('connect', jack, input)
                        } else {
                            var incb = function () {
                                var input = $(targetport)
                                desktop.pedalboard.pedalboard('connect', jack, input)
                                $(document).unbindArrive(targetport, incb)
                            }
                            $(document).arrive(targetport, incb)
                        }
                        $(document).unbindArrive(sourceport, cb)
                    }
                    $(document).arrive(sourceport, cb)
                }
            }
            return
        }

        if (cmd == "disconnect") {
            var source  = data[1]
            var target  = data[2]
            var connMgr = desktop.pedalboard.data("connectionManager")

            if (connMgr.connected(source, target)) {
                var jack = connMgr.origIndex[source][target]
                desktop.pedalboard.pedalboard('destroyJack', jack)
            }
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
                        if (! waiting) {
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
                        }

                        desktop.pedalboard.pedalboard("addPlugin", pluginData, instance, bypassed, x, y, {})
                    },
                    cache: false,
                    dataType: 'json'
                })
            }
            return
        }

        if (cmd == "remove") {
            var instance = data[1]

            if (instance == ":all") {
                desktop.pedalboard.pedalboard('resetData')
            } else {
                desktop.pedalboard.pedalboard('removeItemFromCanvas', instance)
            }
            return
        }

        if (cmd == "add_hw_port") {
            var instance = data[1]
            var type     = data[2]
            var isOutput = parseInt(data[3]) == 0 // reversed
            var name     = data[4].replace(/_/g," ")
            var index    = parseInt(data[5])

            if (isOutput) {
                var el = $('<div id="' + instance + '" class="hardware-output" mod-port-index=' + index + ' title="Hardware ' + name + '">')
                desktop.pedalboard.pedalboard('addHardwareOutput', el, instance, type)
            } else {
                var el = $('<div id="' + instance + '" class="hardware-input" mod-port-index=' + index + ' title="Hardware ' + name + '">')
                desktop.pedalboard.pedalboard('addHardwareInput', el, instance, type)
            }

            desktop.pedalboard.pedalboard('positionHardwarePorts')
            return
        }

        if (cmd == "remove_hw_port") {
            var port = data[1]
            desktop.pedalboard.pedalboard('removeItemFromCanvas', port)
            return
        }

        if (cmd == "wait_start") {
            waiting = true
            desktop.pedalboard.data('wait').start('Loading pedalboard...')
            return
        }

        if (cmd == "wait_end") {
            waiting = false

            // load new possible addressings
            $.ajax({
                url: '/hardware',
                success: function (data) {
                    HARDWARE_PROFILE = data
                    if (desktop.hardwareManager)
                        desktop.hardwareManager.registerAllAddressings()

                    desktop.pedalboard.pedalboard('adapt')
                    desktop.pedalboard.data('wait').stop()
                },
                cache: false,
                dataType: 'json'
            })
            return
        }

        if (cmd == "disconnected") {
            desktop.disconnect()
            return
        }

        if (cmd == "stop") {
            desktop.blockUI()
            return
        }

        console.log(data)
    }
})
