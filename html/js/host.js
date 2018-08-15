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
        var data = evt.data
        var cmd  = data.split(" ",1)

        if (!cmd.length) {
            return
        }

        var cmd = cmd[0]

        if (cmd == "stats") {
            data        = data.substr(cmd.length+1).split(" ",2)
            var cpuLoad = parseFloat(data[0])
            var xruns   = parseInt(data[1])

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
            var value = parseFloat(data.substr(cmd.length+1))
            $("#ram-bar").css("width", (100.0-value).toFixed().toString()+"%")
            $("#ram-bar-text").text("RAM "+value.toString()+"%")
            return
        }

        if (cmd == "param_set") {
            data         = data.substr(cmd.length+1).split(" ",3)
            var instance = data[0]
            var symbol   = data[1]
            var value    = parseFloat(data[2])
            desktop.pedalboard.pedalboard("setPortWidgetsValue", instance, symbol, value);
            return
        }

        if (cmd == "output_set") {
            data         = data.substr(cmd.length+1).split(" ",3)
            var instance = data[0]
            var symbol   = data[1]
            var value    = parseFloat(data[2])
            desktop.pedalboard.pedalboard("setOutputPortValue", instance, symbol, value);
            return
        }

        if (cmd == "output_atom") {
            data         = data.substr(cmd.length+1).split(" ",3)
            var instance = data[0]
            var symbol   = data[1]
            var atom     = data[2]
            desktop.pedalboard.pedalboard("setOutputPortValue", instance, symbol, JSON.parse(atom))
            return
        }

        if (cmd == "transport") {
            data         = data.substr(cmd.length+1).split(" ",4)
            var rolling  = parseInt(data[0]) != 0
            var bpb      = parseFloat(data[1])
            var bpm      = parseFloat(data[2])
            var syncMode = data[3]
            desktop.transportControls.setValues(rolling, bpb, bpm, syncMode)
            return
        }

        if (cmd == "preset") {
            data         = data.substr(cmd.length+1).split(" ",2)
            var instance = data[0]
            var value    = data[1]
            if (value == "null") {
                value = ""
            }
            desktop.pedalboard.pedalboard("selectPreset", instance, value);
            return
        }

        if (cmd == "pedal_preset") {
            var index = parseInt(data.substr(cmd.length+1))

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
            data         = data.substr(cmd.length+1).split(" ",7)
            var instance = data[0]
            var symbol   = data[1]
            var actuator = data[2]
            var minimum  = parseFloat(data[3])
            var maximum  = parseFloat(data[4])
            var steps    = parseInt(data[5])
            var label    = data[6].replace(/_/g," ")
            desktop.hardwareManager.addHardwareMapping(instance, symbol, actuator, label, minimum, maximum, steps)
            return
        }

        if (cmd == "midi_map") {
            data         = data.substr(cmd.length+1).split(" ",6)
            var instance = data[0]
            var symbol   = data[1]
            var channel  = parseInt(data[2])
            var control  = parseInt(data[3])
            var minimum  = parseFloat(data[4])
            var maximum  = parseFloat(data[5])

            if (channel < 0 || control < 0 || minimum >= maximum) {
                console.log("WARNING: Received MIDI mapping with invalid values, ignored")
                return
            }

            desktop.hardwareManager.addMidiMapping(instance, symbol, channel, control, minimum, maximum)
            return
        }

        if (cmd == "connect") {
            data        = data.substr(cmd.length+1).split(" ",2)
            var source  = data[0]
            var target  = data[1]
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
            data        = data.substr(cmd.length+1).split(" ",2)
            var source  = data[0]
            var target  = data[1]
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
            data         = data.substr(cmd.length+1).split(" ",5)
            var instance = data[0]
            var uri      = data[1]
            var x        = parseFloat(data[2])
            var y        = parseFloat(data[3])
            var bypassed = parseInt(data[4]) != 0
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
            var instance = data.substr(cmd.length+1)

            if (instance == ":all") {
                desktop.pedalboard.pedalboard('resetData')
            } else {
                desktop.pedalboard.pedalboard('removeItemFromCanvas', instance)
            }
            return
        }

        if (cmd == "add_hw_port") {
            data         = data.substr(cmd.length+1).split(" ",5)
            var instance = data[0]
            var type     = data[1]
            var isOutput = parseInt(data[2]) == 0 // reversed
            var name     = data[3].replace(/_/g," ")
            var index    = parseInt(data[4])

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
            var port = data.substr(cmd.length+1)
            desktop.pedalboard.pedalboard('removeItemFromCanvas', port)
            return
        }

        if (cmd == "act_add") {
            var metadata = JSON.parse(atob(data.substr(cmd.length+1)))
            desktop.hardwareManager.addActuator(metadata)
            return
        }

        if (cmd == "act_del") {
            var uri = data.substr(cmd.length+1)
            desktop.hardwareManager.removeActuator(uri)
            return
        }

        if (cmd == "resetConnections") {
            desktop.pedalboard.pedalboard("resetConnections")
            return
        }

        if (cmd == "hw_add") {
            data        = data.substr(cmd.length+1).split(" ",4)
            var dev_uri = data[0]
            var label   = data[1].replace(/_/g," ")
            var lsuffix = data[2].replace(/_/g," ")
            var version = data[3]

            desktop.ccDeviceAdded(dev_uri, label, lsuffix, version)
            return
        }

        if (cmd == "hw_rem") {
            data        = data.substr(cmd.length+1).split(" ",3)
            var dev_uri = data[0]
            var label   = data[1].replace(/_/g," ")
            var version = data[2]
            desktop.ccDeviceRemoved(dev_uri, label, version)
            return
        }

        if (cmd == "loading_start") {
            data     = data.substr(cmd.length+1).split(" ",2)
            empty    = parseInt(data[0]) != 0
            modified = parseInt(data[1]) != 0
            loading  = true
            desktop.pedalboard.data('wait').start('Loading pedalboard...')
            return
        }

        if (cmd == "loading_end") {
            var presetId = parseInt(data.substr(cmd.length+1))

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
            data       = data.substr(cmd.length+1).split(" ",2)
            var width  = data[0]
            var height = data[1]
            // TODO
            return
        }

        if (cmd == "truebypass") {
            data      = data.substr(cmd.length+1).split(" ",2)
            var left  = parseInt(data[0]) != 0
            var right = parseInt(data[1]) != 0

            desktop.setTrueBypassButton("Left", left)
            desktop.setTrueBypassButton("Right", right)
            return
        }

        if (cmd == "stop") {
            desktop.blockUI()
            return
        }

        if (cmd == "rescan") {
            var resp = JSON.parse(atob(data.substr(cmd.length+1)))
            desktop.updatePluginList(resp.installed, resp.removed)
            return
        }

        if (cmd == "cc-device-updated") {
            desktop.ccDeviceUpdateFinished()
            return
        }

        if (cmd == "load-pb-remote") {
            var pedalboard_id = data.substr(cmd.length+1)
            desktop.loadRemotePedalboard(pedalboard_id)
            return
        }

        if (cmd == "bufsize") {
            var bufsize = data.substr(cmd.length+1)
            $("#mod-buffersize").text(bufsize+" frames")
            return
        }

        console.log(data)
    }
})
