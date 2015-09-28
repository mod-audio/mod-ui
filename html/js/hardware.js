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

function HardwareManager(options) {
    var self = this

    options = $.extend({
        // This is the function that will actually make the addressing
        address: function (instance, symbol, addressing, callback) {
            callback(true)
        },

        // Callback to get the GUI object of a plugin instance
        getGui: function (instance) {}

        // Callback to enable or disable a control in GUI

    }, options)

    this.reset = function () {
       /* All adressings indexed by actuator
           key  : "/actuator-uri"
           value: ["/instance/symbol"]
        */
        self.addressings = {}

       /* All addressings indexed by instance and control port
           key  : "/instance":["symbol"]
           value: ["/actuator-uris"]
        */
        self.controls = {}

        // Initializes addressings
        self.initializeAddressingsAsNeeded()
    }

    // Fills in 'self.addressings' as needed
    this.initializeAddressingsAsNeeded = function () {
        if (HARDWARE_PROFILE.actuators == null) {
            return
        }
        var i, uri
        for (i in HARDWARE_PROFILE.actuators.length) {
            uri = HARDWARE_PROFILE.actuators[i].uri
            if (! self.addressings[uri])
                self.addressings[uri] = []
        }
    }

    this.reset()

    // Get all addressing types that can be used for a port
    // Most of these are 1:1 match to LV2 hints, but we have extra details.
    this.availableAddressingTypes = function (port) {
        var properties = port.properties
        var types = []

        if (properties.indexOf("integer") >= 0)
            types.push("integer")
        else
            types.push("float")

        if (properties.indexOf("enumeration") >= 0)
            types.push("enumeration")
        if (properties.indexOf("logarithmic") >= 0)
            types.push("logarithmic")
        if (properties.indexOf("toggled") >= 0)
            types.push("toggled")
        if (properties.indexOf("trigger") >= 0)
            types.push("trigger")
        if (properties.indexOf("taptempo") >= 0)
            types.push("taptempo")

        if (port.scalePoints.length >= 2)
            types.push("scalepoints")
        if (port.symbol == ":bypass")
            types.push("bypass")

        return types
    }

    // Checks if an actuator is available for a port
    this.available = function (actuator, instance, port) {
        // FIXME
        //var actuatorKey = actuator.address.join(',')
        //var portKey = [instanceId, port.symbol].join(',')
        return true //(!actuator.exclusive || self.addressings[actuatorKey].length == 0 || self.addressings[actuatorKey].indexOf(portKey) >= 0)
    }

    // Gets a list of available actuators for a port
    this.availableActuators = function (instance, port) {
        var available = []

        // FIXME
        /*var portKey = [instanceId, port.symbol].join(',')
        var types = self.availableAddressingTypes(port)
        var actuators = self.listActuators(instanceId, port)

        for (var i = 0; i < actuators.length; i++) {
            if (types.indexOf(actuators[i].type) < 0)
                continue
            if (!self.available(actuators[i], instanceId, port))
                continue
            available.push(actuators[i])
        }
        */
        return available
    }

    this.buildSensibilityOptions = function (select, port, curStep) {
        select.children().remove()

        if (port.properties.indexOf("integer") >= 0 || port.symbol == ":bypass") {
            // If port is integer or bypass, step is always 1
            $('<option value=0>').appendTo(select)
            select.val(0)
            select.hide()
            return
        }

        var options = {
            17: 'Low',
            33: 'Medium',
            65: 'High'
        }
        var def = 33
        var i, steps, label
        if (port.rangeSteps) {
            options[port.rangeSteps] = 'Default'
        }
        var keys = Object.keys(options).sort()
        for (i in keys) {
            steps = keys[i]
            label = options[steps]
            label += ' (' + steps + ' steps)'
            $('<option>').attr('value', steps).html(label).appendTo(select)
        }

        select.val(curStep || def)
    }

    // Opens an addressing window to address this a port
    this.open = function (pluginLabel, instance, port) {
        console.log('---------------------------- open')
        var currentAddressing = self.controls[instance] ? (self.controls[instance][port.symbol] || {}) : {}

        // Renders the window
        var form = $(options.renderForm(instance, port))

        var actuators = self.availableActuators(instance, port)
        var actuatorSelect = form.find('select[name=actuator]')
        $('<option value="-1">').text('None').appendTo(actuatorSelect)

        var i, value, actuator, opt
        for (i = 0; i < actuators.length; i++) {
            opt = $('<option>').attr('value', i).text(actuators[i].label).appendTo(actuatorSelect)
            if (currentAddressing.actuator && currentAddressing.actuator.join(',') == actuators[i].address.join(',')) {
                actuatorSelect.val(i)
            }
        }
        var portName = port.symbol == ":bypass" ? pluginLabel : port.name

        var minv  = currentAddressing.minimum || port.ranges.minimum
        var maxv  = currentAddressing.maximum || port.ranges.maximum
        var min   = form.find('input[name=min]').val(minv).attr("min", minv).attr("max", maxv)
        var max   = form.find('input[name=max]').val(maxv).attr("min", minv).attr("max", maxv)
        var label = form.find('input[name=label]').val(currentAddressing.label || portName)

        if (port.properties.indexOf("integer") < 0) {
            var step = (maxv-minv)/100
            min.attr("step", step)
            max.attr("step", step)
        }

        var sensibility = form.find('select[name=steps]')
        self.buildSensibilityOptions(sensibility, port, currentAddressing.steps)

        form.find('.js-save').click(function () {
            console.log('---------------------------- save')
            form.remove()
            return

            actuator = {}
            if (actuatorSelect.val() >= 0)
                actuator = actuators[actuatorSelect.val()]

            // Here the addressing structure is created
            var addressing = {
                actuator: actuator.address, // the actuator used
                addressing_type: actuator.type, // one of ADDRESSING_TYPES
                label: label.val() || port.name,
                minimum: min.val() || port.minimum,
                maximum: max.val() || port.maximum,
                value: currentValue,
                steps: sensibility.val(),
                options: [] // the available options in case this is enumerated (no interface for that now)
            }

            self.setAddressing(instance, port, addressing, function () {
                form.remove()
            })
        })
        form.find('.js-close').click(function () {
            form.remove()
        })
        form.appendTo($('body'))
    }

    /* Based on port data and addressingType chosen, creates the addressing data
     * structure that is expected by the server
     * TODO
     * This is very confusing. This method calculates firmware protocol parameters based on
     * user chosen values. These parameters shouldn't be part of the serialized data. The proper
     * place for this is the webserver, that should calculate this on demand.
     */
    this.setIHMParameters = function (instanceId, port, addressing) {
        /*
        addressing.options = []
        if (!addressing.actuator) {
            console.log("setIHMParameters: no actuator set")
            return
        }
        */

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
    }

    this.hardwareExists = function (addressing) {
        var actuator = addressing.actuator || [-1, -1, -1, -1]
        var actuatorKey = actuator.join(',')
        if (self.addressings[actuatorKey])
            return true
        else
            return false
    }

    // Does the addressing
    this.setAddressing = function (instanceId, port, addressing, callback) {
        self.setIHMParameters(instanceId, port, addressing)

        options.address(instanceId, port.symbol, addressing, function (ok) {
            var actuator = addressing.actuator || [-1, -1, -1, -1]
            var actuatorKey = actuator.join(',')
            var portKey = [instanceId, port.symbol].join(',')
            if (ok) {
                var gui = options.getGui(instanceId)
                if (actuator[0] >= 0) {
                    // We're addressing
                    try {
                        var currentAddressing = self.controls[instanceId][port.symbol]
                        remove_from_array(self.addressings[currentAddressing.actuator.join(',')], [instanceId, port.symbol].join(","))
                    } catch (e) {
                        // TypeError when self.controls[instanceId] is null, that's ok
                    }
                    self.addressings[actuatorKey].push(portKey)
                    self.controls[instanceId] = self.controls[instanceId] || {}
                    self.controls[instanceId][port.symbol] = addressing
                    gui.disable(port.symbol)
                } else {
                    // We're unaddressing
                    if (!self.controls[instanceId] || !self.controls[instanceId][port.symbol]) {
                        // not addressed, nothing to be done
                        return callback(true)
                    }
                    var currentAddressing = self.controls[instanceId][port.symbol]
                    actuatorKey = currentAddressing.actuator.join(',')
                    var portIndex = self.addressings[actuatorKey].indexOf(portKey)
                    self.addressings[actuatorKey].splice(portIndex, 1)
                    delete self.controls[instanceId][port.symbol]
                    gui.enable(port.symbol)

                    // Set the returned value in GUI
                    //gui.setPortValue(symbol, result.value)
                }
            } else {
                console.log("Addressing failed for port " + port.symbol)
            }
            callback(ok)
        })
    }

    /*
    this.serializeInstance = function (instanceId) {
        return self.controls[instanceId]
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

    // Removes an instance
    this.removeInstance = function (instanceId) {
        var actuator, symbol, actuatorKey, ports, i
        for (symbol in self.controls[instanceId]) {
            actuator = self.controls[instanceId][symbol].actuator
            actuatorKey = actuator.join(',')
            ports = self.addressings[actuatorKey]
            for (i = 0; i < ports.length; i++) {
                if (parseInt(ports[i].split(/,/)[0]) == instanceId) {
                    ports.splice(i, 1)
                    i--
                }
            }
        }
        delete self.controls[instanceId]
    }
}
