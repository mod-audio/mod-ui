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
var cached_cpuLoad = null,
    cached_xruns   = null,
    timeout_xruns  = null

$('document').ready(function() {
    ws = new WebSocket("ws://" + window.location.host + "/websocket")

    var loading  = false,
        empty    = false,
        modified = false

    ws.onclose = function (evt) {
        desktop.blockUI()
    }

    ws.onmessage = function (evt) {
        var data = evt.data.split(" ")

        if (!data.length) {
            return
        }

        var cmd = data[0]

        if (cmd == "stats") {
            var cpuLoad = parseFloat(data[1])
            var xruns   = parseInt(data[2])

            if (cpuLoad != cached_cpuLoad) {
                cached_cpuLoad = cpuLoad
                $("#cpu-bar").css("width", (100.0-cpuLoad).toFixed().toString()+"%")
                $("#cpu-bar-text").text("CPU "+cpuLoad.toString()+"%")
            }

            if (xruns != cached_xruns) {
                cached_xruns = xruns
                $("#mod-xruns").text(xruns == 1 ? (xruns.toString()+" Xrun") : (xruns.toString()+" Xruns"))

                if (timeout_xruns) {
                    clearTimeout(timeout_xruns)
                } else {
                    $("#cpu-bar-text").css({color:"red"})
                }
                timeout_xruns = setTimeout(function () {
                    $("#cpu-bar-text").css({color:"white"})
                    timeout_xruns = null
                }, 500)
            }

            desktop.networkStatus.timedOutPhase = 0
            return
        }

        if (cmd == "ping") {
            ws.send("pong")
            return
        }

        if (cmd == "mem_load") {
            var value = parseFloat(data[1])
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

        if (cmd == "output_set") {
            var instance = data[1]
            var symbol   = data[2]
            var value    = parseFloat(data[3])
            desktop.pedalboard.pedalboard("setOutputPortValue", instance, symbol, value);
            return
        }

        if (cmd == "preset") {
            var instance = data[1]
            var value    = data[2]
            if (value == "null") {
                value = ""
            }
            desktop.pedalboard.pedalboard("selectPreset", instance, value);
            return
        }

        if (cmd == "pedal_preset") {
            var index = parseInt(data[1])

            $.ajax({
                url: '/pedalpreset/name',
                type: 'GET',
                data: {
                    id: index,
                },
                success: function (resp) {
                    if (! resp.ok) {
                        return
                    }
                    desktop.pedalboardPresetId = index
                    desktop.titleBox.text((desktop.title || 'Untitled') + " - " + resp.name)
                },
                cache: false,
                dataType: 'json'
            })
            return
        }

        if (cmd == "hw_map") {
            var instance = data[1]
            var symbol   = data[2]
            var actuator = data[3]
            var label    = data[4]
            var minimum  = parseFloat(data[5])
            var maximum  = parseFloat(data[6])
            var steps    = parseInt(data[7])

            desktop.hardwareManager.addHardwareMapping(instance, symbol, actuator, label, minimum, maximum, steps)
            return
        }

        if (cmd == "midi_map") {
            var instance = data[1]
            var symbol   = data[2]
            var channel  = parseInt(data[3])
            var control  = parseInt(data[4])
            var minimum  = parseFloat(data[5])
            var maximum  = parseFloat(data[6])

            if (channel < 0 || control < 0 || minimum >= maximum) {
                console.log("WARNING: Received MIDI mapping with invalid values, ignored")
                return
            }

            desktop.hardwareManager.addMidiMapping(instance, symbol, channel, control, minimum, maximum)
            return
        }

        if (cmd == "connect") {
            var source  = data[1]
            var target  = data[2]
            var connMgr = desktop.pedalboard.data("connectionManager")

            if (! connMgr.connected(source, target)) {
                var sourceport = '[mod-port="' + source.replace(/\//g, "\\/") + '"]'
                var targetport = '[mod-port="' + target.replace(/\//g, "\\/") + '"]'

                var output       = $(sourceport)
                var skipModified = loading

                if (output.length) {
                    var input = $(targetport)

                    if (input.length) {
                        desktop.pedalboard.pedalboard('connect', output.find('[mod-role=output-jack]'), input, skipModified)
                    } else {
                        var cb = function () {
                            var input = $(targetport)
                            desktop.pedalboard.pedalboard('connect', output.find('[mod-role=output-jack]'), input, skipModified)
                            $(document).unbindArrive(targetport, cb)
                        }
                        $(document).arrive(targetport, cb)
                    }
                } else {
                    var cb = function () {
                        var output = $(sourceport)
                        var input  = $(targetport)

                        if (input.length) {
                            desktop.pedalboard.pedalboard('connect', output.find('[mod-role=output-jack]'), input, skipModified)
                        } else {
                            var incb = function () {
                                var input = $(targetport)
                                desktop.pedalboard.pedalboard('connect', output.find('[mod-role=output-jack]'), input, skipModified)
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
                var jack   = connMgr.origIndex[source][target]
                var output = jack.data('origin')
                desktop.pedalboard.pedalboard('destroyJack', jack)

                if (Object.keys(connMgr.origIndex[source]).length == 0) {
                    output.addClass('output-disconnected')
                    output.removeClass('output-connected')
                }
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
            var skipModified = loading

            if (plugins[instance] == null) {
                plugins[instance] = {} // register plugin

                $.ajax({
                    url: '/effect/get?uri=' + escape(uri),
                    success: function (pluginData) {
                        var instancekey = '[mod-instance="' + instance + '"]'

                        if (!$(instancekey).length) {
                            var cb = function () {
                                desktop.pedalboard.pedalboard('scheduleAdapt', false)
                                desktop.pedalboard.data('wait').stopPlugin(instance, !skipModified)

                                $(document).unbindArrive(instancekey, cb)
                            }
                            $(document).arrive(instancekey, cb)
                        }

                        desktop.pedalboard.pedalboard("addPlugin", pluginData, instance, bypassed, x, y, {}, null, skipModified)
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

            if (! loading) {
                desktop.pedalboard.pedalboard('positionHardwarePorts')
            }
            return
        }

        if (cmd == "remove_hw_port") {
            var port = data[1]
            desktop.pedalboard.pedalboard('removeItemFromCanvas', port)
            return
        }

        if (cmd == "loading_start") {
            loading  = true
            empty    = parseInt(data[1]) != 0
            modified = parseInt(data[2]) != 0
            desktop.pedalboard.data('wait').start('Loading pedalboard...')
            return
        }

        if (cmd == "loading_end") {
            var presetId = parseInt(data[1])

            $.ajax({
                url: '/pedalpreset/name',
                type: 'GET',
                data: {
                    id: presetId,
                },
                success: function (resp) {
                    desktop.pedalboard.pedalboard('scheduleAdapt', true)
                    desktop.pedalboardEmpty    = empty && !modified
                    desktop.pedalboardModified = modified
                    desktop.pedalboardPresetId = presetId

                    if (presetId >= 0) {
                        $('#js-preset-enabler').hide()
                        $('#js-preset-menu').show()

                        if (resp.ok) {
                            desktop.titleBox.text((desktop.title || 'Untitled') + " - " + resp.name)
                        }
                    }

                    loading = false
                    desktop.init();
                },
                cache: false,
                dataType: 'json'
            })
            return
        }

        if (cmd == "size") {
            var width  = data[1]
            var height = data[2]
            // TODO
            return
        }

        if (cmd == "truebypass") {
            var left  = parseInt(data[1]) != 0
            var right = parseInt(data[2]) != 0

            desktop.setTrueBypassButton("Left", left)
            desktop.setTrueBypassButton("Right", right)
            return
        }

        if (cmd == "stop") {
            desktop.blockUI()
            return
        }

        if (cmd == "rescan") {
            var resp = JSON.parse(atob(data[1]))
            desktop.updatePluginList(resp.installed, resp.removed)
            return
        }

        if (cmd == "load-pb-remote") {
            var pedalboard_id = data[1]
            desktop.loadRemotePedalboard(pedalboard_id)
            return
        }

        console.log(data)
    }
})
