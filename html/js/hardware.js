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

// Special URI for non-addressed controls
var nullAddressURI = "null"

function HardwareManager(options) {
    var self = this

    options = $.extend({
        // This is the function that will actually make the addressing
        address: function (instanceAndSymbol, addressing, callback) { callback(true) },

        // Callback to enable or disable a control in GUI
        setEnabled: function (instance, portSymbol, enabled) {},

        // Renders the address html template
        renderForm: function (instance, port) {},
    }, options)

    this.reset = function () {
       /* All adressings indexed by actuator
           key  : "/actuator-uri"
           value: list("/instance/symbol")
        */
        self.addressingsByActuator = {}

       /* All addressings indexed by instance + port symbol
           key  : "/instance/symbol"
           value: "/actuator-uri"
        */
        self.addressingsByPortSymbol = {}

       /* Saved addressing data
           key  : "/instance/symbol"
           value: dict(AddressData)
        */
        self.addressingsData = {}

        // Initializes actuators
        if (HARDWARE_PROFILE.actuators) {
            var uri
            for (var i in HARDWARE_PROFILE.actuators) {
                uri = HARDWARE_PROFILE.actuators[i].uri
                self.addressingsByActuator[uri] = []
            }
        }
    }

    this.reset()

    // Get all addressing types that can be used for a port
    // Most of these are 1:1 match to LV2 hints, but we have extra details.
    this.availableAddressingTypes = function (port) {
        var properties = port.properties
        var available  = []

        if (properties.indexOf("toggled") >= 0) {
            available.push("toggled")
        } else if (properties.indexOf("integer") >= 0) {
            available.push("integer")
        } else {
            available.push("float")
        }

        if (properties.indexOf("enumeration") >= 0)
            available.push("enumeration")
        if (properties.indexOf("logarithmic") >= 0)
            available.push("logarithmic")
        if (properties.indexOf("trigger") >= 0)
            available.push("trigger")
        if (properties.indexOf("taptempo") >= 0)
            available.push("taptempo")

        if (port.scalePoints.length >= 2)
            available.push("scalepoints")
        if (port.symbol == ":bypass")
            available.push("bypass")

        return available
    }

    // Gets a list of available actuators for a port
    this.availableActuators = function (instance, port) {
        var key   = instance+"/"+port.symbol
        var types = self.availableAddressingTypes(port)

        var available = {}

        var actuator, modes, usedAddressings
        for (var i in HARDWARE_PROFILE.actuators) {
            actuator = HARDWARE_PROFILE.actuators[i]
            modes    = actuator.modes

            usedAddressings = self.addressingsByActuator[actuator.uri]
            if (usedAddressings.length >= actuator.max_assigns && usedAddressings.indexOf(key) < 0) {
                continue
            }

            if (
                (types.indexOf("integer"    ) >= 0 && modes.search(":integer:"    ) >= 0) ||
                (types.indexOf("float"      ) >= 0 && modes.search(":float:"      ) >= 0) ||
                (types.indexOf("enumeration") >= 0 && modes.search(":enumeration:") >= 0) ||
                (types.indexOf("logarithmic") >= 0 && modes.search(":logarithmic:") >= 0) ||
                (types.indexOf("toggled"    ) >= 0 && modes.search(":toggled:"    ) >= 0) ||
                (types.indexOf("trigger"    ) >= 0 && modes.search(":trigger:"    ) >= 0) ||
                (types.indexOf("taptempo"   ) >= 0 && modes.search(":taptempo:"   ) >= 0) ||
                (types.indexOf("scalepoints") >= 0 && modes.search(":scalepoints:") >= 0) ||
                (types.indexOf("bypass"     ) >= 0 && modes.search(":bypass:"     ) >= 0)
               )
            {
                available[actuator.uri] = actuator
            }
        }

        return available
    }

    this.buildSensibilityOptions = function (select, port, curStep) {
        select.children().remove()

        if (port.properties.indexOf("integer") >= 0 || port.properties.indexOf("toggled") >= 0 || port.properties.indexOf("trigger") >= 0) {
            var value
            if (port.properties.indexOf("integer") >= 0) {
                value = port.ranges.maximum-port.ranges.minimum
            } else {
                value = 1
            }
            $('<option value='+value+'>').appendTo(select)
            select.val(value)
            select.hide()
            if (port.symbol != ":bypass") {
                select.parent().parent().hide()
            }
            return
        }

        var options = {
            17: 'Low',
            33: 'Medium',
            65: 'High'
        }
        var def = 33

        if (port.rangeSteps) {
            def = port.rangeSteps
            options[def] = 'Default'
        }

        var steps, label, keys = Object.keys(options).sort()
        for (var i in keys) {
            steps  = keys[i]
            label  = options[steps]
            label += ' (' + steps + ' steps)'
            $('<option>').attr('value', steps).html(label).appendTo(select)
        }

        select.val(curStep != null ? curStep : def)
    }

    // Opens an addressing window to address this a port
    this.open = function (instance, port, pluginLabel) {
        var instanceAndSymbol = instance+"/"+port.symbol
        var currentAddressing = self.addressingsData[instanceAndSymbol] || {}

        // Renders the window
        var form = $(options.renderForm(instance, port))

        var actuators = self.availableActuators(instance, port)
        var actuatorSelect = form.find('select[name=actuator]')
        $('<option value="'+nullAddressURI+'">').text('None').appendTo(actuatorSelect)

        var actuator
        for (var i in actuators) {
            actuator = actuators[i]
            $('<option>').attr('value', actuator.uri).text(actuator.name).appendTo(actuatorSelect)
            if (currentAddressing.uri && currentAddressing.uri == actuator.uri) {
                actuatorSelect.val(currentAddressing.uri)
            }
        }

        var pname = port.symbol == ":bypass" ? pluginLabel : port.shortName
        var minv  = currentAddressing.minimum != null ? currentAddressing.minimum : port.ranges.minimum
        var maxv  = currentAddressing.maximum != null ? currentAddressing.maximum : port.ranges.maximum
        var min   = form.find('input[name=min]').val(minv).attr("min", port.ranges.minimum).attr("max", port.ranges.maximum)
        var max   = form.find('input[name=max]').val(maxv).attr("min", port.ranges.minimum).attr("max", port.ranges.maximum)
        var label = form.find('input[name=label]').val(currentAddressing.label || pname)

        if (port.properties.indexOf("toggled") >= 0 || port.properties.indexOf("trigger") >= 0) {
            // boolean, always min or max value
            var step = maxv-minv
            min.attr("step", step)
            max.attr("step", step)
            // hide ranges
            form.find('.range').hide()
        } else if (port.properties.indexOf("integer") < 0) {
            // float, allow non-integer stepping
            var step = (maxv-minv)/100
            min.attr("step", step)
            max.attr("step", step)
        }

        var sensibility = form.find('select[name=steps]')
        self.buildSensibilityOptions(sensibility, port, currentAddressing.steps)

        form.find('.js-save').click(function () {
            actuator = actuators[actuatorSelect.val()] || {}

            minv = min.val()
            if (minv == undefined || minv == "")
                minv = port.ranges.minimum

            maxv = max.val()
            if (maxv == undefined || maxv == "")
                maxv = port.ranges.maximum

            if (parseFloat(minv) >= parseFloat(maxv)) {
                alert("The minimum value is equal or higher than the maximum. We cannot address a control like this!")
                return
            }

            // Here the addressing structure is created
            var addressing = {
                uri    : actuator.uri || nullAddressURI,
                label  : label.val() || pname,
                minimum: minv,
                maximum: maxv,
                value  : port.value,
                steps  : sensibility.val(),
            }
            console.log("STEPS:", addressing['steps'])

            options.address(instanceAndSymbol, addressing, function (ok) {
                if (ok) {
                    // We're addressing
                    if (actuator.uri && actuator.uri != nullAddressURI)
                    {
                        // add new only if needed, addressing might have been updated
                        if (self.addressingsByActuator[actuator.uri].indexOf(instanceAndSymbol) < 0) {
                            self.addressingsByActuator[actuator.uri].push(instanceAndSymbol)
                        }

                        // remove data needed by the server, useless for us
                        delete addressing.value

                        // now save
                        self.addressingsByPortSymbol[instanceAndSymbol] = actuator.uri
                        self.addressingsData        [instanceAndSymbol] = addressing

                        // disable this control
                        options.setEnabled(instance, port.symbol, false)
                    }
                    // We're unaddressing
                    else if (currentAddressing.uri && currentAddressing.uri != nullAddressURI)
                    {
                        // remove old one
                        remove_from_array(self.addressingsByActuator[currentAddressing.uri], instanceAndSymbol)
                        //var index = self.addressingsByActuator[currentAddressing.uri].indexOf(instanceAndSymbol)
                        //self.addressingsByActuator[actuator.uri].splice(index, 1)

                        delete self.addressingsByPortSymbol[instanceAndSymbol]
                        delete self.addressingsData        [instanceAndSymbol]

                        // enable this control
                        options.setEnabled(instance, port.symbol, true)
                    }
                } else {
                    console.log("Addressing failed for port " + port.symbol)
                }

                form.remove()
            })
        })

        form.find('.js-close').click(function () {
            form.remove()
        })

        form.appendTo($('body'))
    }

    // Callback from pedalboard.js for when a plugin instance is added
    this.instanceAdded = function (instance) {
        if (HARDWARE_PROFILE.addressings) {
            var addressing, addressings, instanceAndSymbol
            for (var uri in HARDWARE_PROFILE.addressings) {
                addressings = HARDWARE_PROFILE.addressings[uri]
                for (var i in addressings) {
                    addressing = addressings[i]

                    if (instance != ":all" && addressing.instance != instance)
                        continue

                    instanceAndSymbol = addressing.instance+"/"+addressing.port

                    self.addressingsByActuator  [uri].push(instanceAndSymbol)
                    self.addressingsByPortSymbol[instanceAndSymbol] = uri
                    self.addressingsData        [instanceAndSymbol] = {
                        uri    : uri,
                        label  : addressing.label,
                        minimum: addressing.minimum,
                        maximum: addressing.maximum,
                        steps  : addressing.steps,
                    }

                    // disable this control
                    options.setEnabled(addressing.instance, addressing.port, false)
                }
            }
        }
    }

    this.registerAllAddressings = function () {
        self.reset()
        self.instanceAdded(":all")
    }

    // Removes an instance
    this.removeInstance = function (instance) {
        var i, j, index, actuator, instanceAndSymbol, instanceAndSymbols = []
        var instanceSansGraph = instance.replace("/graph/","")

        var keys = Object.keys(self.addressingsByPortSymbol)
        for (i in keys) {
            instanceAndSymbol = keys[i]
            if (instanceAndSymbol.replace("/graph/","").split(/\//)[0] == instanceSansGraph) {
                if (instanceAndSymbols.indexOf(instanceAndSymbol) < 0) {
                    instanceAndSymbols.push(instanceAndSymbol)
                }
            }
        }

        for (i in instanceAndSymbols) {
            instanceAndSymbol = instanceAndSymbols[i]
            delete self.addressingsByPortSymbol[instanceAndSymbol]
            delete self.addressingsData        [instanceAndSymbol]

            for (j in HARDWARE_PROFILE.actuators) {
                actuator = HARDWARE_PROFILE.actuators[j]
                index    = self.addressingsByActuator[actuator.uri].indexOf(instanceAndSymbol)
                if (index >= 0) {
                    self.addressingsByActuator[actuator.uri].splice(index, 1)
                }
            }
        }
    }

    /*
    // Does the addressing
    this.setAddressing = function (instance, symbol, addressing, callback) {
        //self.setIHMParameters(instanceId, port, addressing)

    }
    */

    /* Based on port data and addressingType chosen, creates the addressing data
     * structure that is expected by the server
     * TODO
     * This is very confusing. This method calculates firmware protocol parameters based on
     * user chosen values. These parameters shouldn't be part of the serialized data. The proper
     * place for this is the webserver, that should calculate this on demand.
     */
    //this.setIHMParameters = function (instanceId, port, addressing) {
        /*
        addressing.options = []
        if (!addressing.actuator) {
            console.log("setIHMParameters: no actuator set")
            return
        }
        */

        /*
        addressing.unit = port.units ? port.units.symbol : null

        if (port.symbol == ":bypass") {
            addressing.type = ADDRESSING_CTYPE_BYPASS
        } else if (port.toggled) {
            addressing.type = ADDRESSING_CTYPE_TOGGLED
        } else if (port.integer) {
            addressing.type = ADDRESSING_CTYPE_INTEGER
        } else {
            addressing.type = ADDRESSING_CTYPE_LINEAR
        }

        if (port.enumeration) {
            addressing.type |= ADDRESSING_CTYPE_ENUMERATION|ADDRESSING_CTYPE_SCALE_POINTS
            if (!addressing.options || addressing.options.length == 0) {
                addressing.options = port.scalePoints.map(function (point) {
                    return [point.value, point.label]
                })
            }
        }
        if (port.logarithmic) {
            addressing.type |= ADDRESSING_CTYPE_LOGARITHMIC
        }
        if (port.trigger) {
            addressing.type |= ADDRESSING_CTYPE_TRIGGER
        }
        if (addressing.addressing_type == ADDRESSING_TYPE_TAP_TEMPO) {
            addressing.type |= ADDRESSING_CTYPE_TAP_TEMPO
        }

            console.log("setIHMParameters: type = " + addressing.type)
    }*/

    /*
    this.hardwareExists = function (addressing) {
        var actuator = addressing.actuator || [-1, -1, -1, -1]
        var actuatorKey = actuator.join(',')
        if (self.addressingsByActuator[actuatorKey])
            return true
        else
            return false
    }
    */

    /*
    this.serializeInstance = function (instanceId) {
        return self.addressingsByPortSymbol[instanceId]
    }*/

    /*
    this.unserializeInstance = function (instanceId, addressings, bypassApplication, addressingErrors) {
        // Store the original options.change callback, to bypass application
        var callback = options.address

        // addressingErrors is an array where we should append controls addressed to unknown hardware
        if (!addressingErrors)
            addressingErrors = []

        if (bypassApplication) {
            options.address = function () {
                arguments[arguments.length - 1](true)
            }
        }
        var restore = function () {
            options.address = callback
        }

        // Make a queue of symbols to be addressed and process the queue with
        // a recursive asynchronous function
        var queue = Object.keys(addressings)
        var symbol

        var processNext = function () {
            if (queue.length == 0)
                return restore()
            symbol = queue.pop()
            if (self.hardwareExists(addressings[symbol]))
                self.setAddressing(instanceId, symbol, addressings[symbol], processNext)
            else {
                addressingErrors.push([instanceId, symbol])
                processNext()
            }
        }

        processNext()
    }*/
}
