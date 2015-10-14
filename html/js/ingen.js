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

var NS_rdf_type            = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
var NS_ingen_Arc           = "http://drobilla.net/ns/ingen#Arc"
var NS_ingen_Block         = "http://drobilla.net/ns/ingen#Block"
var NS_ingen_canvasX       = "http://drobilla.net/ns/ingen#canvasX"
var NS_ingen_canvasY       = "http://drobilla.net/ns/ingen#canvasY"
var NS_ingen_enabled       = "http://drobilla.net/ns/ingen#enabled"
var NS_ingen_file          = "http://drobilla.net/ns/ingen#file"
var NS_ingen_incidentTo    = "http://drobilla.net/ns/ingen#incidentTo"
var NS_ingen_head          = "http://drobilla.net/ns/ingen#head"
var NS_ingen_tail          = "http://drobilla.net/ns/ingen#tail"
var NS_ingen_value         = "http://drobilla.net/ns/ingen#value"
var NS_lv2core_AudioPort   = "http://lv2plug.in/ns/lv2core#AudioPort"
var NS_lv2core_ControlPort = "http://lv2plug.in/ns/lv2core#ControlPort"
var NS_lv2core_CVPort      = "http://lv2plug.in/ns/lv2core#CVPort"
var NS_lv2core_InputPort   = "http://lv2plug.in/ns/lv2core#InputPort"
var NS_lv2core_OutputPort  = "http://lv2plug.in/ns/lv2core#OutputPort"
var NS_lv2core_index       = "http://lv2plug.in/ns/lv2core#index"
var NS_lv2core_name        = "http://lv2plug.in/ns/lv2core#name"
var NS_lv2core_prototype   = "http://lv2plug.in/ns/lv2core#prototype"
var NS_atom_AtomPort       = "http://lv2plug.in/ns/ext/atom#AtomPort"
var NS_patch_Delete        = "http://lv2plug.in/ns/ext/patch#Delete"
var NS_patch_Patch         = "http://lv2plug.in/ns/ext/patch#Patch"
var NS_patch_Put           = "http://lv2plug.in/ns/ext/patch#Put"
var NS_patch_Set           = "http://lv2plug.in/ns/ext/patch#Set"
var NS_patch_body          = "http://lv2plug.in/ns/ext/patch#body"
var NS_patch_property      = "http://lv2plug.in/ns/ext/patch#property"
var NS_patch_subject       = "http://lv2plug.in/ns/ext/patch#subject"
var NS_patch_value         = "http://lv2plug.in/ns/ext/patch#value"

$('document').ready(function() {
    var ws = new WebSocket("ws://" + window.location.host + "/websocket");
    var body, subject, type, type1, type2, property, value

    ws.onmessage = function (evt) {
        var parser = N3.Parser();
        var store  = N3.Store();
        parser.parse(evt.data,
            function (error, triple, prefixes) {
                if (error) {
                    console.log("N3: " + error)
                }

                if (triple)
                {
                    store.addTriple(triple.subject, triple.predicate, triple.object);
                }
                else if (triple == null)
                {
                    /**
                      Delete messages
                    */
                    store.find(null, NS_rdf_type, NS_patch_Delete).forEach(function (msg)
                    {
                        body = store.find(msg.subject, NS_patch_body, null)

                        if (body.length)
                        {
                            body = body[0].object
                            type = store.find(body, NS_rdf_type, null)

                            if (type.length)
                            {
                                type = type[0].object

                                if (type == NS_ingen_Arc)
                                {
                                    // Deletes a connection between ports
                                    var connMgr    = desktop.pedalboard.data("connectionManager")
                                    var incidentTo = store.find(body, NS_ingen_incidentTo, null)

                                    if (incidentTo.length) {
                                        incidentTo = incidentTo[0].object
                                        connMgr.iterateInstance(incidentTo, function (jack) {
                                            desktop.pedalboard.pedalboard('destroyJack', jack)
                                        })
                                    } else {
                                        var tail = store.find(body, NS_ingen_tail, null)
                                        var head = store.find(body, NS_ingen_head, null)

                                        if (head.length && tail.length) {
                                            tail = tail[0].object
                                            head = head[0].object

                                            if (connMgr.connected(tail, head)) {
                                                var jack = connMgr.origIndex[tail][head]
                                                desktop.pedalboard.pedalboard('destroyJack', jack)
                                            }
                                        } else {
                                            console.log("ERROR: Received patch:Delete ingen:Arg without incidentTo or tail&head")
                                        }
                                    }
                                }
                                else
                                {
                                        console.log("TESTING: Received unhandled patch:Delete message: " + type)
                                }
                            }
                            else
                            {
                                console.log("ERROR: Received patch:Delete message without type")
                            }
                        }
                        else
                        {
                            subject = store.find(msg.subject, NS_patch_subject, null)

                            if (subject.length) {
                                subject = subject[0].object
                                desktop.pedalboard.pedalboard('removeItemFromCanvas', subject)
                            } else {
                                console.log("ERROR: Received patch:Delete message without body or subject")
                            }
                        }
                    })

                    /**
                      Patch messages
                    */
                    store.find(null, NS_rdf_type, NS_patch_Patch).forEach(function (msg) {
                        subject = store.find(msg.subject, NS_patch_subject, null)

                        if (subject.length) {
                            subject = subject[0].object
                            console.log("TESTING: Received unhandled patch:Patch message: " + subject)
                        } else {
                            console.log("ERROR: Received patch:Patch message without subject")
                        }
                    })

                    /**
                      Put messages
                    */
                    store.find(null, NS_rdf_type, NS_patch_Put).forEach(function (msg)
                    {
                        subject = store.find(msg.subject, NS_patch_subject, null)
                        body    = store.find(msg.subject, NS_patch_body, null)

                        if (subject.length && body.length)
                        {
                            subject = subject[0].object
                            body    = body[0].object
                            type    = store.find(body, NS_rdf_type, null)

                            if (type.length == 0)
                            {
                                console.log("ERROR: Received patch:Put message without type")
                            }
                            else if (type.length == 1)
                            {
                                type = type[0].object

                                if (type == NS_ingen_Block)
                                {
                                    // add a new plugin
                                    var prototype = store.find(body, NS_lv2core_prototype, null)

                                    if (prototype.length) {
                                        prototype = prototype[0].object

                                        var instance = subject
                                        var uri = prototype

                                        var enabled = store.find(body, NS_ingen_enabled);
                                        enabled = enabled.length ? enabled[0].object.indexOf("true") >= 0 : false;

                                        var canvasX = store.find(body, NS_ingen_canvasX);
                                        canvasX = canvasX.length ? N3.Util.getLiteralValue(canvasX[0].object) : 0;

                                        var canvasY = store.find(body, NS_ingen_canvasY);
                                        canvasY = canvasY.length ? N3.Util.getLiteralValue(canvasY[0].object) : 0;

                                        var plugins = desktop.pedalboard.data('plugins')

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

                                                    desktop.pedalboard.pedalboard("addPlugin", pluginData, instance, !enabled, parseInt(canvasX), parseInt(canvasY), {})
                                                },
                                                cache: false,
                                                dataType: 'json'
                                            })
                                        }
                                    } else {
                                        console.log("ERROR: Received patch:Put message without subject")
                                    }
                                }
                                else if (type == NS_ingen_Arc)
                                {
                                    // add new port connection
                                    var tail = store.find(body, NS_ingen_tail, null)
                                    var head = store.find(body, NS_ingen_head, null)

                                    if (head.length && tail.length) {
                                        tail = tail[0].object
                                        head = head[0].object

                                        var connMgr = desktop.pedalboard.data("connectionManager")

                                        if (! connMgr.connected(tail, head)) {
                                            var tailport = '[mod-port="' + tail.replace("/", "\\/") + '"]'
                                            var headport = '[mod-port="' + head.replace("/", "\\/") + '"]'

                                            var output = $(tailport)

                                            if (output.length) {
                                                var input = $(headport)
                                                var jack  = output.find('[mod-role=output-jack]')

                                                if (input.length) {
                                                    desktop.pedalboard.pedalboard('connect', jack, input)
                                                } else {
                                                    var cb = function () {
                                                        var input = $(headport)
                                                        desktop.pedalboard.pedalboard('connect', jack, input)
                                                        $(document).unbindArrive(headport, cb)
                                                    }
                                                    $(document).arrive(headport, cb)
                                                }
                                            } else {
                                                var cb = function () {
                                                    var output = $(tailport)
                                                    var input  = $(headport)
                                                    var jack   = output.find('[mod-role=output-jack]')

                                                    if (input.length) {
                                                        desktop.pedalboard.pedalboard('connect', jack, input)
                                                    } else {
                                                        var incb = function () {
                                                            var input = $(headport)
                                                            desktop.pedalboard.pedalboard('connect', jack, input)
                                                            $(document).unbindArrive(headport, incb)
                                                        }
                                                        $(document).arrive(headport, incb)
                                                    }
                                                    $(document).unbindArrive(tailport, cb)
                                                }
                                                $(document).arrive(tailport, cb)
                                            }
                                        }
                                    } else {
                                        console.log("ERROR: Received patch:Put ingen:Arg without tail&head")
                                    }
                                }
                                else
                                {
                                    console.log("TESTING: Received unhandled patch:Put (size 1) message type: '" + type + "', subject '" + subject + "'")
                                }
                            }
                            else if (type.length == 2)
                            {
                                type1 = type[0].object
                                type2 = type[1].object

                                // one of the types is Input|OutputPort
                                if (type1 == NS_lv2core_AudioPort || type1 == NS_lv2core_CVPort || type1 == NS_atom_AtomPort ||
                                    type2 == NS_lv2core_AudioPort || type2 == NS_lv2core_CVPort || type2 == NS_atom_AtomPort)
                                {
                                    // new port
                                    if (subject.split("/").length != 3) {
                                        // not a system/hardware port
                                        return
                                    }
                                    if (subject == "/graph/control_in" || subject == "/graph/control_out") {
                                        // skip special ingen control ports
                                        return
                                    }

                                    var name  = store.find(body, NS_lv2core_name)
                                    var index = store.find(body, NS_lv2core_index)

                                    if (name.length == 0 || name[0] == null) {
                                        console.log("ERROR: Received patch:Put ControlPort without name")
                                        return
                                    }
                                    if (index.length == 0 || index[0] == null) {
                                        console.log("ERROR: Received patch:Put ControlPort without index")
                                        return
                                    }

                                    name  = N3.Util.getLiteralValue(name[0].object)
                                    index = N3.Util.getLiteralValue(index[0].object)

                                    var port_type, types = [type1, type2]

                                    /*  */ if (types.indexOf(NS_lv2core_AudioPort) > -1) {
                                        port_type = "audio"
                                    } else if (types.indexOf(NS_lv2core_CVPort) > -1) {
                                        port_type = "cv"
                                    } else if (types.indexOf(NS_atom_AtomPort) > -1) {
                                        port_type = "midi"
                                    } else {
                                        console.log("ERROR: Received patch:Put Port with unknown port type")
                                        return
                                    }

                                    var el = $('[id="' + subject + '"]')
                                    if (el.length > 0) {
                                        // already created
                                        return
                                    }

                                    if (types.indexOf(NS_lv2core_InputPort) > -1) {
                                        el = $('<div id="' + subject + '" class="hardware-output" mod-port-index=' + index + ' title="Hardware ' + name + '">')
                                        desktop.pedalboard.pedalboard('addHardwareOutput', el, subject, port_type)
                                    } else {
                                        el = $('<div id="' + subject + '" class="hardware-input" mod-port-index=' + index + ' title="Hardware ' + name + '">')
                                        desktop.pedalboard.pedalboard('addHardwareInput', el, subject, port_type)
                                    }

                                    desktop.pedalboard.pedalboard('positionHardwarePorts')
                                }
                                else if (type1 == NS_lv2core_ControlPort || type2 == NS_lv2core_ControlPort)
                                {
                                    // set the value for the port
                                    value = store.find(body, NS_ingen_value);

                                    if (value.length) {
                                        value = value[0].object
                                        value = N3.Util.getLiteralValue(value)

                                        var last_slash = subject.lastIndexOf("/");
                                        var instance   = subject.substring(0, last_slash);
                                        var symbol     = subject.substring(last_slash+1);

                                        desktop.pedalboard.pedalboard("setPortWidgetsValue", instance, symbol, value);

                                        /*
                                        var symbolport = '[mod-port="' + subject.replace("/", "\\/") + '"]'
                                        if ($(symbolport).length) {
                                            console.log(symbol)
                                            console.log(instance)
                                            var instancekey = '[mod-instance="' + instance + '"]'

                                            if ($(instancekey).length) {
                                                setTimeout(function() {
                                                    var gui =
                                                    gui.setPortWidgetsValue(symbol, value, undefined, true);
                                                }, 100)
                                            } else {
                                                var cb = function () {
                                                    setTimeout(function() {
                                                        var gui = desktop.pedalboard.pedalboard("getGui", instance);
                                                        gui.setPortWidgetsValue(symbol, value, undefined, true);
                                                    }, 100)
                                                    $(document).unbindArrive(instancekey, cb)
                                                }
                                                $(document).arrive(instancekey, cb)
                                            }
                                        } else {
                                            var cb = function () {
                                                setTimeout(function() {
                                                    var gui = desktop.pedalboard.pedalboard("getGui", instance);
                                                    gui.setPortWidgetsValue(symbol, value, undefined, true);
                                                }, 100)
                                                $(document).unbindArrive(symbolport, cb)
                                            }
                                            $(document).arrive(symbolport, cb)
                                        }*/
                                    } else  {
                                        console.log("ERROR: Received patch:Put ControlPort without value")
                                    }
                                }
                            }
                            else
                            {
                                console.log("TESTING: Received unhandled patch:Put message with many types, subject: '" + subject + "'")
                                console.log(type)
                            }
                        }
                        else
                        {
                            console.log("ERROR: Received patch:Put message without subject or body")
                        }
                    });

                    /**
                      Set messages
                    */
                    store.find(null, NS_rdf_type, NS_patch_Set).forEach(function (msg) {
                        subject = store.find(msg.subject, NS_patch_subject, null)

                        if (subject.length)
                        {
                            subject  = subject[0].object
                            property = store.find(msg.subject, NS_patch_property, null);
                            value    = store.find(msg.subject, NS_patch_value, null);

                            if (property.length && value.length)
                            {
                                property = property[0].object
                                value    = value[0].object

                                if (property == "http://moddevices/ns/modpedal#cpuload")
                                {
                                    // setting cpuload
                                    value = N3.Util.getLiteralValue(value)
                                    $("#cpu-bar").css("width", (100.0-value).toFixed().toString()+"%")
                                    $("#cpu-bar-text").text("CPU "+value.toString()+"%")
                                }
                                else if (property == NS_ingen_value)
                                {
                                    // setting a port value
                                    var last_slash = subject.lastIndexOf("/");
                                    var instance = subject.substring(0, last_slash);
                                    var symbol = subject.substring(last_slash+1);
                                    desktop.pedalboard.pedalboard("setPortWidgetsValue", instance, symbol, N3.Util.getLiteralValue(value));
                                }
                                else if (property == NS_ingen_enabled)
                                {
                                    // setting bypass
                                    desktop.pedalboard.pedalboard("gsetPortWidgetsValue", subject, ":bypass", value.indexOf("false") >= 0 ? 1 : 0);
                                }
                                else if (property == NS_ingen_file)
                                {
                                    // Pedalboard changed, load new possible addressings
                                    $.ajax({
                                        url: '/hardware',
                                        success: function (data) {
                                            HARDWARE_PROFILE = data
                                            if (desktop.hardwareManager)
                                                desktop.hardwareManager.registerAllAddressings()
                                        },
                                        cache: false,
                                        dataType: 'json'
                                    })
                                }
                                else
                                {
                                    // ignore some properties
                                    if (property == NS_ingen_canvasX ||
                                        property == NS_ingen_canvasY ||
                                        property == "http://moddevices.com/ns/modpedal#width"  ||
                                        property == "http://moddevices.com/ns/modpedal#height" ||
                                        property == "http://moddevices.com/ns/modpedal#addressing" ||
                                        property == "http://moddevices.com/ns/modpedal#screenshot" ||
                                        property == "http://moddevices.com/ns/modpedal#thumbnail"  ||
                                        property == NS_rdf_type) {
                                        return
                                    }

                                    console.log("TESTING: Received unhandled patch:Set message subject: '" + subject + "', property '" + property + "'")
                                }
                            }
                            else
                            {
                                console.log("ERROR: Received patch:Set message without property or value")
                            }
                        }
                        else
                        {
                            console.log("ERROR: Received patch:Set message without subject")
                        }
                    });
                }
            });
    };
});
