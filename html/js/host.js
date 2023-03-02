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
    timeout_xruns  = null,
    pb_loading     = true

$('document').ready(function() {
    ws = new WebSocket("ws://" + window.location.host + "/websocket")

    var empty    = false,
        modified = false;
    var dataReadyCounter = '',
        dataReadyTimeout = null;

    function triggerDelayedReadyResponse (triggerNew) {
        if (dataReadyTimeout) {
            clearTimeout(dataReadyTimeout)
            triggerNew = true
        }
        if (triggerNew) {
            dataReadyTimeout = setTimeout(function() {
                dataReadyTimeout = null
                ws.send("data_ready " + dataReadyCounter)
            }, 50)
        }
    }

    ws.onclose = function (evt) {
        desktop && desktop.blockUI()
    }

    ws.onmessage = function (evt) {
        var data = evt.data
        var cmd = data.split(" ",1)

        if (!cmd.length) {
            return
        }

        cmd = cmd[0];

        // these first commands do not have any arguments
        if (cmd == "ping") {
            ws.send("pong")
            return
        }
        if (cmd == "stop") {
            desktop.blockUI()
            return
        }
        if (cmd == "cc-device-updated") {
            desktop.ccDeviceUpdateFinished()
            return
        }

        // everything from here onwards has at least 1 argument
        data = data.substr(cmd.length+1);

        if (cmd == "data_ready") {
            dataReadyCounter = data
            triggerDelayedReadyResponse(true)
            return
        }

        triggerDelayedReadyResponse(false)

        if (cmd == "stats") {
            data        = data.split(" ",2)
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

        if (cmd == "sys_stats") {
            data        = data.split(" ",3)
            var memload = parseFloat(data[0])
            var cpufreq = data[1]
            var cputemp = data[2]
            $("#ram-bar").css("width", (100.0-memload).toFixed().toString()+"%")
            $("#ram-bar-text").text("RAM "+memload.toString()+"%")

            if (cpufreq !== "0" && cputemp !== "0") {
                $("#mod-cpu-stats").html(sprintf("%.1f GHz / %d &deg;C",
                                                 parseInt(cpufreq)/1000000,
                                                 parseInt(cputemp)/1000))
            }
            return
        }

        if (cmd == "param_set") {
            data         = data.split(" ",3)
            var instance = data[0]
            var symbol   = data[1]
            var value    = parseFloat(data[2])

            desktop.pedalboard.pedalboard("setPortWidgetsValue", instance, symbol, value);
            return
        }

        if (cmd == "output_set") {
            data         = data.split(" ",3)
            var instance = data[0]
            var symbol   = data[1]
            var value    = parseFloat(data[2])
            desktop.pedalboard.pedalboard("setOutputPortValue", instance, symbol, value);
            return
        }

        if (cmd == "patch_set") {
            var sdata     = data.split(" ",4)
            var instance  = sdata[0]
            var writable  = parseInt(sdata[1]) != 0
            var uri       = sdata[2]
            var valuetype = sdata[3]
            var valuedata = data.substr(sdata.join(" ").length+1)

            if (writable) {
                desktop.pedalboard.pedalboard("setWritableParameterValue", instance, uri, valuetype, valuedata);
            } else {
                desktop.pedalboard.pedalboard("setReadableParameterValue", instance, uri, valuetype, valuedata);
            }
            return
        }

        if (cmd == "plugin_pos") {
            data = data.split(" ", 3)
            var instance = data[0]
            var x = parseInt(data[1])
            var y = parseInt(data[2])
            desktop.pedalboard.pedalboard("setPluginPosition", instance, x, y)
            return
        }

        if (cmd == "transport") {
            data         = data.split(" ",4)
            var rolling  = parseInt(data[0]) != 0
            var bpb      = parseFloat(data[1])
            var bpm      = parseFloat(data[2])
            var syncMode = data[3]
            desktop.transportControls.setValues(rolling, bpb, bpm, syncMode)
            return
        }

        if (cmd == "preset") {
            data         = data.split(" ",2)
            var instance = data[0]
            var value    = data[1]
            if (value == "null") {
                value = ""
            }
            desktop.pedalboard.pedalboard("selectPreset", instance, value);
            return
        }

        if (cmd == "pedal_snapshot") {
            cmd       = data.split(" ",1)
            var index = parseInt(cmd[0])
            var name  = data.substr(cmd.length+1);

            desktop.pedalboardPresetId = index
            desktop.pedalboardPresetName = name
            desktop.titleBox.text((desktop.title || 'Untitled') + " - " + name)
            return
        }

        if (cmd == "hw_map") {
            data         = data.split(" ", 15)
            var instance = data[0]
            var symbol   = data[1]
            var actuator = data[2]
            var minimum  = parseFloat(data[3])
            var maximum  = parseFloat(data[4])
            var steps    = parseInt(data[5])
            var label    = data[6].replace(/_/g," ")
            var tempo    = data[7] === "True" ? true : false
            var dividers = JSON.parse(data[8].replace(/'/g, '"'))
            var page     = data[9]
            if (page != "null") {
                page = parseInt(page)
            } else {
                page = null
            }
            var subpage  = data[10]
            if (subpage != "null") {
                subpage = parseInt(subpage)
            } else {
                subpage = null
            }
            var group = data[11]
            var feedback = parseInt(data[12]) == 1
            var coloured = parseInt(data[13]) == 1
            var momentary = parseInt(data[14])

            desktop.hardwareManager.addHardwareMapping(instance,
                                                       symbol,
                                                       actuator,
                                                       label,
                                                       minimum,
                                                       maximum,
                                                       steps,
                                                       tempo,
                                                       dividers,
                                                       page,
                                                       subpage,
                                                       group,
                                                       feedback,
                                                       coloured,
                                                       momentary)
            return
        }

        if (cmd == "cv_map") {
          data         = data.split(" ", 12)
          var instance = data[0]
          var symbol   = data[1]
          var actuator = data[2]
          var minimum  = parseFloat(data[3])
          var maximum  = parseFloat(data[4])
          var label    = data[5].replace(/_/g," ")
          var operationalMode = data[6]
          var feedback = parseInt(data[7]) == 1

          desktop.hardwareManager.addCvMapping(instance,
                                               symbol,
                                               actuator,
                                               label,
                                               minimum,
                                               maximum,
                                               operationalMode,
                                               feedback)
        }

        if (cmd == "midi_map") {
            data         = data.split(" ",6)
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
            data        = data.split(" ",2)
            var source  = data[0]
            var target  = data[1]
            var connMgr = desktop.pedalboard.data("connectionManager")

            if (! connMgr.connected(source, target)) {
                var sourceport = '[mod-port="' + source.replace(/\//g, "\\/") + '"]'
                var targetport = '[mod-port="' + target.replace(/\//g, "\\/") + '"]'

                var output       = $(sourceport)
                var skipModified = pb_loading

                if (output.length) {
                    var input = $(targetport)

                    if (input.length) {
                        desktop.pedalboard.pedalboard('connect', output.find('[mod-role=output-jack]'), input, skipModified)
                    } else {
                        var cb = function () {
                            var input = $(targetport)
                            desktop.pedalboard.pedalboard('connect', output.find('[mod-role=output-jack]'), input, skipModified)
                            $('#pedalboard-dashboard').unbindArrive(targetport, cb)
                        }
                        $('#pedalboard-dashboard').arrive(targetport, cb)
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
                                $('#pedalboard-dashboard').unbindArrive(targetport, incb)
                            }
                            $('#pedalboard-dashboard').arrive(targetport, incb)
                        }
                        $('#pedalboard-dashboard').unbindArrive(sourceport, cb)
                    }
                    $('#pedalboard-dashboard').arrive(sourceport, cb)
                }
            }
            return
        }

        if (cmd == "disconnect") {
            data        = data.split(" ",2)
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
            data         = data.split(" ",7)
            var instance = data[0]
            var uri      = data[1]
            var x        = parseFloat(data[2])
            var y        = parseFloat(data[3])
            var bypassed = parseInt(data[4]) != 0
            var pVersion = data[5]
            var offBuild = parseInt(data[6]) != 0 // official MOD build coming from store, can be cached
            var plugins  = desktop.pedalboard.data('plugins')
            var skipModified = pb_loading

            if (plugins[instance] == null) {
                plugins[instance] = {} // register plugin

                $.ajax({
                    url: '/effect/get',
                    data: {
                        uri: uri,
                        version: VERSION,
                        plugin_version: pVersion,
                    },
                    success: function (pluginData) {
                        var instancekey = '[mod-instance="' + instance + '"]'

                        if (!$(instancekey).length) {
                            var cb = function () {
                                desktop.pedalboard.pedalboard('scheduleAdapt', false)
                                desktop.pedalboard.data('wait').stopPlugin(instance, !skipModified)
                                $('#pedalboard-dashboard').unbindArrive(instancekey, cb)
                            }
                            $('#pedalboard-dashboard').arrive(instancekey, cb)
                        }

                        desktop.pedalboard.pedalboard("addPlugin", pluginData, instance, bypassed, x, y, {}, null, skipModified)
                    },
                    cache: offBuild,
                    dataType: 'json'
                })
            }
            return
        }

        if (cmd == "remove") {
            var instance = data

            if (instance == ":all") {
                desktop.pedalboard.pedalboard('resetData')
            } else {
                desktop.pedalboard.pedalboard('removeItemFromCanvas', instance)
            }
            return
        }

        if (cmd == "add_cv_port") {
            data         = data.split(" ", 3)
            var instance = data[0]
            var name     = data[1].replace(/_/g," ")
            var operationalMode = data[2]
            desktop.hardwareManager.addCvOutputPort(instance, name, operationalMode)
            return
        }

        if (cmd == "add_hw_port") {
            data         = data.split(" ",5)
            var instance = data[0]
            var type     = data[1]
            var isOutput = parseInt(data[2]) == 0 // reversed
            var name     = data[3].replace(/_/g," ")
            var index    = parseInt(data[4])

            if (isOutput) {
                var el = $('<div id="' + instance + '" class="hardware-output" mod-port-index=' + index + ' title="Hardware ' + name + '">')
                desktop.pedalboard.pedalboard('addHardwareOutput', el, instance, type)
                if (type === 'cv') {
                  desktop.hardwareManager.addCvOutputPort('/cv' + instance, name, '+')
                }
            } else {
                var prefix = name === 'MIDI Loopback' ? 'Virtual' : 'Hardware'
                var el = $('<div id="' + instance + '" class="hardware-input" mod-port-index=' + index + ' title="' + prefix + ' ' + name + '">')
                desktop.pedalboard.pedalboard('addHardwareInput', el, instance, type)
            }

            if (! pb_loading) {
                desktop.pedalboard.pedalboard('positionHardwarePorts')
            }
            return
        }

        if (cmd == "remove_hw_port") {
            var port = data
            desktop.pedalboard.pedalboard('removeItemFromCanvas', port)
            return
        }

        if (cmd == "act_add") {
            var metadata = JSON.parse(atob(data))
            desktop.hardwareManager.addActuator(metadata)
            return
        }

        if (cmd == "act_del") {
            var uri = data
            desktop.hardwareManager.removeActuator(uri)
            return
        }

        if (cmd == "hw_add") {
            data        = data.split(" ",4)
            var dev_uri = data[0]
            var label   = data[1].replace(/_/g," ")
            var lsuffix = data[2].replace(/_/g," ")
            var version = data[3]

            desktop.ccDeviceAdded(dev_uri, label, lsuffix, version)
            return
        }

        if (cmd == "hw_rem") {
            data        = data.split(" ",3)
            var dev_uri = data[0]
            var label   = data[1].replace(/_/g," ")
            var version = data[2]
            desktop.ccDeviceRemoved(dev_uri, label, version)
            return
        }

        if (cmd == "hw_con") {
            data        = data.split(" ",2)
            var label   = data[0].replace(/_/g," ")
            var version = data[1]
            desktop.ccDeviceConnected(label, version)
            return
        }

        if (cmd == "hw_dis") {
            data        = data.split(" ",2)
            var label   = data[0].replace(/_/g," ")
            var version = data[1]
            desktop.ccDeviceDisconnected(label, version)
            return
        }

        if (cmd == "loading_start") {
            data     = data.split(" ",2)
            empty    = parseInt(data[0]) != 0
            modified = parseInt(data[1]) != 0
            pb_loading = true
            desktop.pedalboard.data('wait').start('Loading pedalboard...')
            return
        }

        if (cmd == "loading_end") {
            var snapshotId = parseInt(data)

            $.ajax({
                url: '/snapshot/name',
                type: 'GET',
                data: {
                    id: snapshotId,
                },
                success: function (resp) {
                    desktop.pedalboard.pedalboard('scheduleAdapt', true)
                    desktop.pedalboardEmpty    = empty && !modified
                    desktop.pedalboardModified = modified
                    desktop.pedalboardPresetId = snapshotId
                    desktop.pedalboardPresetName = resp.name

                    if (resp.ok) {
                        desktop.titleBox.text((desktop.title || 'Untitled') + " - " + resp.name)
                    }

                    pb_loading = false
                    desktop.init();
                },
                cache: false,
                dataType: 'json'
            })
            return
        }

        if (cmd == "size") {
            data       = data.split(" ",2)
            var width  = data[0]
            var height = data[1]
            // TODO
            return
        }

        if (cmd == "truebypass") {
            data      = data.split(" ",2)
            var left  = parseInt(data[0]) != 0
            var right = parseInt(data[1]) != 0

            desktop.setTrueBypassButton("Left", left)
            desktop.setTrueBypassButton("Right", right)
            return
        }

        if (cmd == "log") {
            cmd       = data.split(" ",1)
            var ltype = parseInt(cmd[0])
            var lmsg  = data.substr(cmd.length+1);

            if (ltype == 0) {
                console.debug(lmsg);
            } else if (ltype == 1) {
                console.log(lmsg);
            } else if (ltype == 2) {
                console.warn(lmsg);
            } else if (ltype == 3) {
                console.error(lmsg);
            }
            return
        }

        if (cmd == "rescan") {
            var resp = JSON.parse(atob(data))
            desktop.updatePluginList(resp.installed, resp.removed)
            return
        }

        if (cmd == "load-pb-remote") {
            var pedalboard_id = data
            desktop.loadRemotePedalboard(pedalboard_id)
            return
        }

        if (cmd == "bufsize") {
            var bufsize = data
            $("#mod-buffersize").text(bufsize+" frames")
            return
        }
    }
})
