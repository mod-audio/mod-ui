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
        var parser = N3.Parser();
        var store  = N3.Store();
        parser.parse(evt.data,
            function (error, triple, prefixes) {
                if (error) {
                    console.log("N3: " + error)
                }
                if (triple) {
                    store.addTriple(triple.subject, triple.predicate, triple.object);
                } else if (triple == null) {
                    // Delete messages
                    store.find(null,
                        "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                        "http://lv2plug.in/ns/ext/patch#Delete").forEach(function (msg) {
                        var body = store.find(msg.subject, "http://lv2plug.in/ns/ext/patch#body", null);
                        if (body.length) {
                            var type = store.find(body[0].object, "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", null);
                            if (type.length && type[0].object == "http://drobilla.net/ns/ingen#Arc") {
                                // Deletes a connection between ports
                                var cm = desktop.pedalboard.data("connectionManager")
                                var incidentTo = store.find(body[0].object, "http://drobilla.net/ns/ingen#incidentTo", null);
                                if (incidentTo.length) {
                                    var instance = incidentTo[0].object;
                                    cm.iterateInstance(instance, function (jack) {
                                        desktop.pedalboard.pedalboard('destroyJack', jack)
                                    })
                                } else {
                                    var tail = store.find(body[0].object, "http://drobilla.net/ns/ingen#tail", null)[0].object
                                    var head = store.find(body[0].object, "http://drobilla.net/ns/ingen#head", null)[0].object
                                    if (cm.connected(tail, head)) {
                                        var jack = cm.origIndex[tail][head]
                                        desktop.pedalboard.pedalboard('destroyJack', jack)
                                    }
                                }
                            } else {
                                    console.log("TESTING: Received unhandled patch:Delete message:" + type[0].object)
                            }
                        } else {
                            var subject = store.find(msg.subject, "http://lv2plug.in/ns/ext/patch#subject", null);
                            if (subject.length) {
                                desktop.pedalboard.pedalboard('removeItemFromCanvas', subject[0].object)
                            }
                        }
                    });

                    // Put messages
                    store.find(null,
                        "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                        "http://lv2plug.in/ns/ext/patch#Put").forEach(function (msg) {
                        var subject = store.find(msg.subject, "http://lv2plug.in/ns/ext/patch#subject", null);
                        var body = store.find(msg.subject, "http://lv2plug.in/ns/ext/patch#body", null);
                        var type = store.find(body[0].object, "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", null);
                        if (subject.length && body.length && subject[0].object) {
                            var prototype = store.find(body[0].object, "http://lv2plug.in/ns/lv2core#prototype");
                            if (type.length && type[0].object == "http://drobilla.net/ns/ingen#Block" && prototype.length) {
                                // add a new plugin
                                var instance = subject[0].object;
                                var uri = prototype[0].object;
                                var canvasX = store.find(body[0].object, "http://drobilla.net/ns/ingen#canvasX");
                                var canvasY = store.find(body[0].object, "http://drobilla.net/ns/ingen#canvasY");
                                var x = canvasX.length ? N3.Util.getLiteralValue(canvasX[0].object) : 0;
                                var y = canvasY.length ? N3.Util.getLiteralValue(canvasY[0].object) : 0;
                                var waiter =desktop.pedalboard.data('wait')
                                var plugins = desktop.pedalboard.data('plugins')
                                if (plugins[instance] == null) {
                                    plugins[instance] = {} // register plugin
                                    $.ajax({
                                        url: '/effect/get?uri=' + escape(uri),
                                        success: function (pluginData) {
                                            desktop.pedalboard.pedalboard("addPlugin", pluginData, instance, parseInt(x), parseInt(y))
                                            $("#pedalboard-dashboard").arrive('[mod-instance="' + instance + '"]', function () {
                                                desktop.pedalboard.pedalboard('adapt')
                                                if (waiter.plugins[instance])
                                                    waiter.stopPlugin(instance)
                                                $("#pedalboard-dashboard").unbindArrive('[mod-instance="' + instance + '"]')
                                            })
                                        },
                                        cache: false,
                                        'dataType': 'json'
                                    })
                                }
                            } else if (type.length == 2 && (type[0].object == "http://lv2plug.in/ns/lv2core#AudioPort" ||
                                                            type[1].object == "http://lv2plug.in/ns/lv2core#AudioPort" ||
                                                            type[0].object == "http://lv2plug.in/ns/lv2core#CVPort"    ||
                                                            type[1].object == "http://lv2plug.in/ns/lv2core#CVPort"    ||
                                                            type[0].object == "http://lv2plug.in/ns/ext/atom#AtomPort" ||
                                                            type[1].object == "http://lv2plug.in/ns/ext/atom#AtomPort"
                                                            )) {
                                // new port
                                var sub = subject[0].object;
                                if (sub.split("/").length != 3) {
                                    // not a system/hardware port
                                    return
                                }
                                if (sub == "/graph/control_in" || sub == "/graph/control_out") {
                                    // skip special ingen control ports
                                    return
                                }

                                var nameObj = store.find(body[0].object, "http://lv2plug.in/ns/lv2core#name")[0]
                                if (nameObj == null)
                                    return

                                var indexObj = store.find(body[0].object, "http://lv2plug.in/ns/lv2core#index")[0]
                                if (indexObj == null)
                                    return

                                var name = N3.Util.getLiteralValue(nameObj.object)
                                var index = N3.Util.getLiteralValue(indexObj.object)
                                var types = [type[0].object, type[1].object]

                                var port_type
                                if (types.indexOf("http://lv2plug.in/ns/ext/atom#AtomPort") > -1) {
                                    // atom
                                    port_type = "midi"
                                } else if (types.indexOf("http://lv2plug.in/ns/lv2core#CVPort") > -1) {
                                    // cv
                                    port_type = "cv"
                                } else {
                                    // audio
                                    port_type = "audio"
                                }

                                var el = $('[id="' + sub + '"]')
                                if (el.length > 0) {
                                    return
                                }

                                if (types.indexOf("http://lv2plug.in/ns/lv2core#InputPort") > -1) {
                                    el = $('<div id="' + sub + '" class="hardware-output" mod-port-index=' + index + ' title="Hardware ' + name + '">')
                                    desktop.pedalboard.pedalboard('addHardwareOutput', el, sub, port_type)
                                } else {
                                    el = $('<div id="' + sub + '" class="hardware-input" mod-port-index=' + index + ' title="Hardware ' + name + '">')
                                    desktop.pedalboard.pedalboard('addHardwareInput', el, sub, port_type)
                                }
                                desktop.pedalboard.pedalboard('positionHardwarePorts')

                            } else if (type.length == 2 && (type[0].object == "http://lv2plug.in/ns/lv2core#ControlPort" ||
                                                            type[1].object == "http://lv2plug.in/ns/lv2core#ControlPort")) {
                                // set the value for the port
                                var value = store.find(body[0].object, "http://drobilla.net/ns/ingen#value");
                                var sub = subject[0].object;
                                var last_slash = sub.lastIndexOf("/");
                                var instance = sub.substring(0, last_slash);
                                var port = sub.substring(last_slash+1);
                                var symbol = '[mod-port="' + sub.replace("/", "\\/") + '"]'
                                if (!$(symbol).length) {
                                    var cb = function () {
                                        setTimeout(function() {
                                            var gui = desktop.pedalboard.pedalboard("getGui", instance);
                                            gui.setPortWidgetsValue(port, N3.Util.getLiteralValue(value[0].object), undefined, true);
                                        }, 100)
                                        $(document).unbindArrive(symbol, cb)
                                    }
                                    $(document).arrive(symbol, cb)
                                } else {
                                    var gui = desktop.pedalboard.pedalboard("getGui", instance);
                                    gui.setPortWidgetsValue(port, N3.Util.getLiteralValue(value[0].object), undefined, true);
                                }
                            } else if (type.length && type[0].object == "http://drobilla.net/ns/ingen#Arc") {
                                // new port connection
                                var tail = store.find(body[0].object, "http://drobilla.net/ns/ingen#tail", null)[0].object
                                var head = store.find(body[0].object, "http://drobilla.net/ns/ingen#head", null)[0].object
                                var cm = desktop.pedalboard.data("connectionManager")
                                if (!cm.connected(tail, head)) {
                                    var output = $('[mod-port="' + tail.replace("/", "\\/") + '"]')
                                    if(!output.length) {
                                        var cb = function () {
                                            var output = $('[mod-port="' + tail.replace("/", "\\/") + '"]')
                                            var jack = output.find('[mod-role=output-jack]')
                                            var input =  $('[mod-port="' + head.replace("/", "\\/") + '"]')
                                            if (!input.length) {
                                                var incb = function () {
                                                    var input =  $('[mod-port="' + head.replace("/", "\\/") + '"]')
                                                    desktop.pedalboard.pedalboard('connect', jack, input)
                                                    $(document).unbindArrive('[mod-port="' + head.replace("/", "\\/") + '"]', incb)
                                                }
                                                $(document).arrive('[mod-port="' + head.replace("/", "\\/") + '"]', incb)
                                            } else {
                                                desktop.pedalboard.pedalboard('connect', jack, input)
                                            }
                                            $(document).unbindArrive('[mod-port="' + tail.replace("/", "\\/") + '"]', cb)
                                        }
                                        $(document).arrive('[mod-port="' + tail.replace("/", "\\/") + '"]', cb)
                                    } else {
                                        var jack = output.find('[mod-role=output-jack]')
                                        var input =  $('[mod-port="' + head.replace("/", "\\/") + '"]')
                                        if (!input.length) {
                                            var cb = function () {
                                                var input =  $('[mod-port="' + head.replace("/", "\\/") + '"]')
                                                desktop.pedalboard.pedalboard('connect', jack, input)
                                                $(document).unbindArrive('[mod-port="' + head.replace("/", "\\/") + '"]', cb)
                                            }
                                            $(document).arrive('[mod-port="' + head.replace("/", "\\/") + '"]', cb)
                                        } else {
                                            desktop.pedalboard.pedalboard('connect', jack, input)
                                        }
                                    }
                                }
                            }
                        }
                    });

                    // Patch messages
                    store.find(null,
                        "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                        "http://lv2plug.in/ns/ext/patch#Patch").forEach(function (msg) {
                        var subject = store.find(msg.subject, "http://lv2plug.in/ns/ext/patch#subject", null);
                        if (subject.length)
                            console.log("Patch: " + subject[0]);
                    });

                    // Set messages
                    store.find(null,
                        "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                        "http://lv2plug.in/ns/ext/patch#Set").forEach(function (msg) {
                        var subject = store.find(msg.subject, "http://lv2plug.in/ns/ext/patch#subject", null);
                        if (subject.length) {
                            var property = store.find(msg.subject, "http://lv2plug.in/ns/ext/patch#property");
                            var value = store.find(msg.subject, "http://lv2plug.in/ns/ext/patch#value");
                            if (property.length && value.length) {
                                var prop = property[0].object
                                if (prop == "http://drobilla.net/ns/ingen#value")
                                {
                                    // setting a port value
                                    var sub = subject[0].object;
                                    var last_slash = sub.lastIndexOf("/");
                                    var instance = sub.substring(0, last_slash);
                                    var port = sub.substring(last_slash+1);
                                    var gui = desktop.pedalboard.pedalboard("getGui", instance);
                                    gui.setPortWidgetsValue(port, N3.Util.getLiteralValue(value[0].object), undefined, true);
                                }
                                else if (prop == "http://drobilla.net/ns/ingen#enabled")
                                {
                                    // setting bypass
                                    var instance = subject[0].object
                                    var gui = desktop.pedalboard.pedalboard("getGui", instance);
                                    gui.setPortWidgetsValue(":bypass", value[0].object == "true" ? 0 : 1, undefined, true);
                                }
                                else if (prop == "http://moddevices/ns/mod#cpuload")
                                {
                                    // setting cpuload
                                    var value = value[0].object
                                    $("#cpu-bar").css("width", value.substring(1, value.length-1)+"%")
                                }
                                else
                                {
                                    // ignore some properties
                                    if (prop == "http://drobilla.net/ns/ingen#canvasX"     ||
                                        prop == "http://drobilla.net/ns/ingen#canvasY"     ||
                                        prop == "http://moddevices.com/ns/modpedal#width"  ||
                                        prop == "http://moddevices.com/ns/modpedal#height" ||
                                        prop == "http://moddevices.com/ns/modpedal#screenshot" ||
                                        prop == "http://moddevices.com/ns/modpedal#thumbnail"  ||
                                        prop == "http://www.w3.org/1999/02/22-rdf-syntax-ns#type") {
                                        return
                                    }

                                    console.log("TESTING: Received unhandled patch:Set message")
                                    console.log(subject[0])
                                    console.log(property[0])
                                }
                            }
                        }
                    });
                }
            });
    };
});
