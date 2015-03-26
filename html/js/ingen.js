/*
 * Copyright 2012-2013 AGR Audio, Industria e Comercio LTDA. <contato@portalmod.com>
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

$(document).ready(function () {
    var ws = new WebSocket("ws://" + window.location.host + "/websocket");
    ws.onmessage = function (evt) {
        var parser = N3.Parser();
        var msgs = evt.data;
        var store = N3.Store();
        parser.parse(msgs,
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
                                var tail = store.find(body[0].object, "http://drobilla.net/ns/ingen#tail", null)[0].object.split("/")
                                var head = store.find(body[0].object, "http://drobilla.net/ns/ingen#head", null)[0].object.split("/")
                                var cm = desktop.pedalboard.data("connectionManager")
                                var jack = cm.origIndex[tail[0]][tail[1]][head[0]][head[1]]
                                desktop.pedalboard.pedalboard('disconnect', jack)
                            }
                        }
                    });

                    // Put messages
                    store.find(null,
                        "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                        "http://lv2plug.in/ns/ext/patch#Put").forEach(function (msg) {
                        var subject = store.find(msg.subject, "http://lv2plug.in/ns/ext/patch#subject", null);
                        var body = store.find(msg.subject, "http://lv2plug.in/ns/ext/patch#body", null);
                        if (subject.length && body.length && subject[0].object) {
                            var type = store.find(body[0].object, "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", null);
                            var prototype = store.find(body[0].object, "http://drobilla.net/ns/ingen#prototype");
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
                                        url: '/effect/get?url=' + escape(uri),
                                        success: function (pluginData) {
                                            desktop.pedalboard.pedalboard("addPlugin", pluginData, instance, parseInt(x), parseInt(y))
                                            $("#pedalboard-dashboard").arrive("[mod-instance=" + instance + "]", function () {
                                                desktop.pedalboard.pedalboard('adapt')
                                                if (waiter.plugins[instance])
                                                    waiter.stopPlugin(instance)
                                                $("#pedalboard-dashboard").unbindArrive("[mod-instance=" + instance + "]")
                                            })
                                        },
                                        cache: false,
                                        'dataType': 'json'
                                    })
                                }
                            } else if (type[0].object == "http://lv2plug.in/ns/lv2core#ControlPort") {
                                // set the value for the port
                                var value = store.find(body[0].object, "http://drobilla.net/ns/ingen#value");
                                var sub = subject[0].object;
                                var instance = sub.split("/")[0];
                                var port = sub.split("/")[1];
                                if (!$("." + sub)) {
                                    var cb = function () {
                                        var gui = desktop.pedalboard.pedalboard("getGui", instance);
                                        gui.setPortWidgetsValue(port, N3.Util.getLiteralValue(value[0].object), undefined, true);
                                        $(document).unbindArrive('[mod-port=' + sub.replace("/", "\\/") + "]", cb)
                                    }
                                    $(document).arrive('[mod-port=' + sub.replace("/", "\\/") + "]", cb)
                                } else {
                                    var gui = desktop.pedalboard.pedalboard("getGui", instance);
                                    gui.setPortWidgetsValue(port, N3.Util.getLiteralValue(value[0].object), undefined, true);
                                }
                            }
                        } else if (body.length) {
                            var type = store.find(body[0].object, "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", null);
                            if (type[0].object == "http://drobilla.net/ns/ingen#Arc") {
                                // new port connection
                                var tail = store.find(body[0].object, "http://drobilla.net/ns/ingen#tail", null)[0].object
                                var head = store.find(body[0].object, "http://drobilla.net/ns/ingen#head", null)[0].object
                                var output = $('[mod-port=' + tail.replace("/", "\\/") + "]")
                                if(!output.length) {
                                    var cb = function () {
                                        var output = $('[mod-port=' + tail.replace("/", "\\/") + "]")
                                        var jack = output.find('[mod-role=output-jack]')
                                        var input =  $('[mod-port=' + head.replace("/", "\\/") + "]")
                                        if (!input.length) {
                                            var incb = function () {
                                                var input =  $('[mod-port=' + head.replace("/", "\\/") + "]")
                                                desktop.pedalboard.pedalboard('connect', jack, input)
                                                $(document).unbindArrive('[mod-port=' + head.replace("/", "\\/") + "]", incb)
                                            }
                                            $(document).arrive('[mod-port=' + head.replace("/", "\\/") + "]", incb)
                                        } else {
                                            desktop.pedalboard.pedalboard('connect', jack, input)
                                        }
                                        $(document).unbindArrive('[mod-port=' + tail.replace("/", "\\/") + "]", cb)
                                    }
                                    $(document).arrive('[mod-port=' + tail.replace("/", "\\/") + "]", cb)
                                } else {
                                    var jack = output.find('[mod-role=output-jack]')
                                    var input =  $('[mod-port=' + head.replace("/", "\\/") + "]")
                                    if (!input.length) {
                                        var cb = function () {
                                            var input =  $('[mod-port=' + head.replace("/", "\\/") + "]")
                                            desktop.pedalboard.pedalboard('connect', jack, input)
                                            $(document).unbindArrive('[mod-port=' + head.replace("/", "\\/") + "]", cb)
                                        }
                                        $(document).arrive('[mod-port=' + head.replace("/", "\\/") + "]", cb)
                                    } else {
                                        desktop.pedalboard.pedalboard('connect', jack, input)
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
                                // setting a port value
                                if (property[0].object == "http://drobilla.net/ns/ingen#value") {
                                    var sub = subject[0].object;
                                    var instance = sub.split("/")[0];
                                    var port = sub.split("/")[1];
                                    var gui = desktop.pedalboard.pedalboard("getGui", instance);
                                    gui.setPortWidgetsValue(port, N3.Util.getLiteralValue(value[0].object), undefined, true);
                                }
                            }
                        }
                    });
                }
            });
    };
});
