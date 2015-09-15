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

ADDRESSING_TYPE_RANGE     = "range"
ADDRESSING_TYPE_SWITCH    = "switch"
ADDRESSING_TYPE_TAP_TEMPO = "tap_tempo"

ADDRESSING_TYPES = [
    ADDRESSING_TYPE_RANGE,
    ADDRESSING_TYPE_SWITCH,
    ADDRESSING_TYPE_TAP_TEMPO
]

ADDRESSING_CTYPE_LINEAR         = 0
ADDRESSING_CTYPE_BYPASS         = 1
ADDRESSING_CTYPE_TAP_TEMPO      = 2
ADDRESSING_CTYPE_ENUMERATION    = 4
ADDRESSING_CTYPE_SCALE_POINTS   = 8
ADDRESSING_CTYPE_TRIGGER        = 16
ADDRESSING_CTYPE_TOGGLED        = 32
ADDRESSING_CTYPE_LOGARITHMIC    = 64
ADDRESSING_CTYPE_INTEGER        = 128

ACTUATOR_TYPE_FOOTSWITCH = 1
ACTUATOR_TYPE_KNOB       = 2
ACTUATOR_TYPE_POT        = 3

function HardwareManager(options) {
    var self = this

    options = $.extend({
        // This is the function that will actually make the addressing
        address: function (instanceId, symbol, addressing, callback) {
            callback(true)
        },

        // Callback to get the GUI object of a plugin instance
        getGui: function (instanceId) {}

        // Callback to enable or disable a control in GUI

    }, options)

    this.reset = function () {
       /* All adressings indexed by actuator
           key: "hardwareType,hardwareId,actuatorType,actuatorId"
           value: ["instanceId,symbol"]
        */
        self.addressings = {}

       /* All addressings indexed by instanceId and control port
           key: [instanceId][symbol]
           value: complete addressing structure
        */
        self.controls = {}

        // Initializes addressings
        self.listActuators()
    }

    // Lists all available actuators and initializes the addressing structure
    this.listActuators = function () {
        if (Object.keys(HARDWARE_PROFILE).length == 0) {
            return []
        }
        var actuators = []
        var i, j, type, actuator, actuatorKey
        for (i = 0; i < ADDRESSING_TYPES.length; i++) {
            type = ADDRESSING_TYPES[i]
            for (j = 0; j < HARDWARE_PROFILE[type].length; j++) {
                actuatorData = HARDWARE_PROFILE[type][j]
                actuator = {}
                actuator.address = actuatorData.slice(0, 4)
                actuator.type = type
                actuator.exclusive = actuatorData[4]
                actuator.label = actuatorData[5]
                actuators.push(actuator)

                actuatorKey = actuator.address.join(',')
                if (!self.addressings[actuatorKey])
                    self.addressings[actuatorKey] = []
            }
        }
        return actuators
    }

    this.reset()

    // Get all addressing types that can be used for a port
    this.availableAddressingTypes = function (port) {
        var types = []
        if (port.toggled) {
            types.push(ADDRESSING_TYPE_SWITCH)
        } else if (port.enumeration) {
            types.push(ADDRESSING_TYPE_SWITCH)
            types.push(ADDRESSING_TYPE_RANGE)
        } else {
            types.push(ADDRESSING_TYPE_RANGE)
            if (port.tap_tempo)
                types.push(ADDRESSING_TYPE_TAP_TEMPO)
        }
        return types
    }

    // Checks if an actuator is available for a port
    this.available = function (actuator, instanceId, port) {
        var actuatorKey = actuator.address.join(',')
        var portKey = [instanceId, port.symbol].join(',')
        return (!actuator.exclusive || self.addressings[actuatorKey].length == 0 || self.addressings[actuatorKey].indexOf(portKey) >= 0)
    }

    // Gets a list of available actuators for a port
    this.availableActuators = function (instanceId, port) {
        var portKey = [instanceId, port.symbol].join(',')
        var types = self.availableAddressingTypes(port)
        var actuators = self.listActuators(instanceId, port)

        var available = []
        for (var i = 0; i < actuators.length; i++) {
            if (types.indexOf(actuators[i].type) < 0)
                continue
            if (!self.available(actuators[i], instanceId, port))
                continue
            available.push(actuators[i])
        }
        return available
    }

    // Opens an addressing window to address this a port
    this.open = function (instanceId, port, currentValue) {
        console.log('open')
        console.log(currentValue)
        var currentAddressing = {}
        if (self.controls[instanceId])
            currentAddressing = self.controls[instanceId][port.symbol] || {}

        // Renders the window
        var form = $(options.renderForm(instanceId, port))

        var actuators = self.availableActuators(instanceId, port)
        var actuatorSelect = form.find('select[name=actuator]')
        $('<option value="-1">').text('None').appendTo(actuatorSelect)
        var i, value, actuator, opt
        for (i = 0; i < actuators.length; i++) {
            opt = $('<option>').attr('value', i).text(actuators[i].label).appendTo(actuatorSelect)
            if (currentAddressing.actuator && currentAddressing.actuator.join(',') == actuators[i].address.join(',')) {
                actuatorSelect.val(i)
            }
        }
        var gui = options.getGui(instanceId)
        var pluginName = gui.effect.label || gui.effect.name
        var portName
        if (port.symbol == ":bypass")
            portName = pluginName
        else
            portName = port.name

        var min = form.find('input[name=min]').val(currentAddressing.minimum || port.ranges.minimum)
        var max = form.find('input[name=max]').val(currentAddressing.maximum || port.ranges.maximum)
        var label = form.find('input[name=label]').val(currentAddressing.label || portName)

        var sensibility = form.find('select[name=steps]')
        self.buildSensibilityOptions(sensibility, port)
        if (currentAddressing.steps)
            sensibility.val(currentAddressing.steps)

        form.find('.js-save').click(function () {
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

            self.setAddressing(instanceId, port, addressing, function () {
                form.remove()
            })
        })
        form.find('.js-close').click(function () {
            form.remove()
        })
        form.appendTo($('body'))
    }

    this.buildSensibilityOptions = function (select, port) {
        select.children().remove()

        if (port.integer || port.symbol == ":bypass") {
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
        var steps, i, label
        if (port.rangeSteps) {
            if (!(options[port.rangeSteps]))
                options[port.rangeSteps] = 'Default'
            def = port.rangeSteps
            for (steps in options) {
                if (steps > port.rangeSteps) {
                    delete options[steps]
                }
            }
        }
        var keys = Object.keys(options).sort()
        for (i in keys) {
            steps = keys[i]
            label = options[steps]
            label += ' (' + steps + ' steps)'
            $('<option>').attr('value', steps).html(label).appendTo(select)
        }
        select.val(def)
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
