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

$(document).ready(function() {
    var ws = new WebSocket("ws://" + window.location.host + "/websocket");
    var parser = N3.Parser();
    ws.onmessage = function (evt) {
        var msgs = evt.data;
        var store = N3.Store();
        parser.parse(msgs,
                 function (error, triple, prefixes) {
                    if (triple) {
                        store.addTriple(triple.subject, triple.predicate, triple.object);
                    } else {
                        // Delete messages
                        store.find(null,
                                "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                                "http://lv2plug.in/ns/ext/patch#Delete").forEach(function (msg) {
                                var subject = store.find(msg.subject, "http://lv2plug.in/ns/ext/patch#subject", null);
                                if(subject.length)
                                    console.log("Delete: " + subject[0]);
                        });

                        // Put messages
                        store.find(null,
                                "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                                "http://lv2plug.in/ns/ext/patch#Put").forEach(function (msg) {
                                var subject = store.find(msg.subject, "http://lv2plug.in/ns/ext/patch#subject", null);
                                if(subject.length)
                                    console.log("Put: " + subject[0]);

                        });

                        // Patch messages
                        store.find(null,
                                "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                                "http://lv2plug.in/ns/ext/patch#Patch").forEach(function (msg) {
                                var subject = store.find(msg.subject, "http://lv2plug.in/ns/ext/patch#subject", null);
                                if(subject.length)
                                    console.log("Patch: " + subject[0]);

                        });

                        // Set messages
                        store.find(null,
                                "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                                "http://lv2plug.in/ns/ext/patch#Set").forEach(function (msg) {
                                var subject = store.find(msg.subject, "http://lv2plug.in/ns/ext/patch#subject", null);
                                if(subject.length) {
                                    var property = store.find(msg.subject, "http://lv2plug.in/ns/ext/patch#property");
                                    var value = store.find(msg.subject, "http://lv2plug.in/ns/ext/patch#value");
                                    if (property.length && value.length) {
                                        // setting a port value
                                        if (property[0].object == "http://drobilla.net/ns/ingen#value") {
                                            var sub = subject[0].object;
                                            var instance = sub.split("/")[0];
                                            var port = sub.split("/")[1];
                                            var gui = desktop.pedalboard.pedalboard("getGui", instance.replace("instance", ""));
                                            gui.setPortWidgetsValue(port, N3.Util.getLiteralValue(value[0].object), undefined, true);
                                        }
                                    }
                                }
                        });
                    }
                });
    };
});
