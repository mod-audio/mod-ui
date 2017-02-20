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
var kNullAddressURI = "null"

// Special URIs for midi-learn
var kMidiLearnURI = "/midi-learn"
var kMidiUnlearnURI = "/midi-unlearn"
var kMidiCustomPrefixURI = "/midi-custom_" // to show current one, ignored on save

function create_midi_cc_uri (channel, controller) {
    return sprintf("%sCh.%d_CC#%d", kMidiCustomPrefixURI, channel+1, controller)
}

// Units supported for tap tempo (lowercase)
var kTapTempoUnits = ['ms','s','hz','bpm']

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
        if (HARDWARE_PROFILE) {
            var uri
            for (var i in HARDWARE_PROFILE) {
                uri = HARDWARE_PROFILE[i].uri
                self.addressingsByActuator[uri] = []
            }
        }
        self.addressingsByActuator[kMidiLearnURI] = []
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
        if (properties.indexOf("tapTempo") >= 0 && kTapTempoUnits.indexOf(port.units.symbol.toLowerCase()) >= 0)
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

        if (HARDWARE_PROFILE) {
            var actuator, modes, usedAddressings
            for (var i in HARDWARE_PROFILE) {
                actuator = HARDWARE_PROFILE[i]
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
        }

        // midi-learn is always available, except for enumeration
        if (types.indexOf("enumeration") < 0 || port.scalePoints.length == 2)
        {
            available[kMidiLearnURI] = {
                uri  : kMidiLearnURI,
                name : "MIDI Learn...",
                modes: ":float:trigger:bypass:integer:toggled:",
                steps: [],
                max_assigns: 99
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
            if (port.symbol != ":bypass" && port.symbol != ":presets") {
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
        var midiLearnHint = form.find('.midi-learn-hint');
        actuatorSelect.on('change', function() {
            midiLearnHint.toggle(actuatorSelect.val() === '/midi-learn');
        });
        $('<option value="'+kNullAddressURI+'">').text('None').appendTo(actuatorSelect)

        var actuator
        for (var i in actuators) {
            actuator = actuators[i]
            $('<option>').attr('value', actuator.uri).text(actuator.name).appendTo(actuatorSelect)
            if (currentAddressing.uri && currentAddressing.uri == actuator.uri) {
                actuatorSelect.val(currentAddressing.uri)
            }
        }

        if (currentAddressing.uri && currentAddressing.uri.lastIndexOf(kMidiCustomPrefixURI, 0) === 0) { // startsWith
            var label = "MIDI " + currentAddressing.uri.replace(kMidiCustomPrefixURI,"").replace(/_/g," ")
            $('<option value="'+currentAddressing.uri+'">').text(label).appendTo(actuatorSelect)
            actuatorSelect.val(currentAddressing.uri)
            actuators[currentAddressing.uri] = {
                uri  : currentAddressing.uri,
                name : label,
                modes: ":float:trigger:bypass:integer:toggled:",
                steps: [],
                max_assigns: 99
            }
        }

        var pname = (port.symbol == ":bypass" || port.symbol == ":presets") ? pluginLabel : port.shortName
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

            // Hide sensibility options for MIDI
            var act = actuatorSelect.val()
            if (act == kMidiLearnURI || act.lastIndexOf(kMidiCustomPrefixURI, 0) === 0) {
                form.find('.sensibility').css({visibility:"hidden"})
            }

            actuatorSelect.bind('change keyup', function () {
                var act = $(this).val()
                if (act == kMidiLearnURI || act.lastIndexOf(kMidiCustomPrefixURI, 0) === 0) {
                    form.find('.sensibility').css({visibility:"hidden"})
                } else {
                    form.find('.sensibility').css({visibility:"visible"})
                }
            })
        }

        var sensibility = form.find('select[name=steps]')
        self.buildSensibilityOptions(sensibility, port, currentAddressing.steps)

        var addressNow = function (actuator) {
            var addressing = {
                uri    : actuator.uri || kNullAddressURI,
                label  : label.val() || pname,
                minimum: minv,
                maximum: maxv,
                value  : port.value,
                steps  : sensibility.val(),
            }

            options.address(instanceAndSymbol, addressing, function (ok) {
                if (!ok) {
                    console.log("Addressing failed for port " + port.symbol);
                    return;
                }

                // remove old one first
                var unaddressing = false
                if (currentAddressing.uri && currentAddressing.uri != kNullAddressURI) {
                    unaddressing = true
                    if (currentAddressing.uri.lastIndexOf(kMidiCustomPrefixURI, 0) === 0) { // startsWith
                        currentAddressing.uri = kMidiLearnURI
                    }
                    remove_from_array(self.addressingsByActuator[currentAddressing.uri], instanceAndSymbol)
                }

                // We're addressing
                if (actuator.uri && actuator.uri != kNullAddressURI)
                {
                    var actuator_uri = actuator.uri
                    if (actuator_uri.lastIndexOf(kMidiCustomPrefixURI, 0) === 0) { // startsWith
                        actuator_uri = kMidiLearnURI
                    }
                    // add new one, print and error if already there
                    if (self.addressingsByActuator[actuator_uri].indexOf(instanceAndSymbol) < 0) {
                        self.addressingsByActuator[actuator_uri].push(instanceAndSymbol)
                    } else {
                        console.log("ERROR HERE, please fix!")
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
                else if (unaddressing)
                {
                    delete self.addressingsByPortSymbol[instanceAndSymbol]
                    delete self.addressingsData        [instanceAndSymbol]

                    // enable this control
                    options.setEnabled(instance, port.symbol, true)
                }

                form.remove()
            })
        }

        var saveAddressing = function () {
            var actuator = actuators[actuatorSelect.val()] || {}

            // no actuator selected or old one exists, do nothing
            if (actuator.uri == null && currentAddressing.uri == null) {
                console.log("Nothing to do")
                form.remove()
                return
            }

            // Check values
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

            // if changing from midi-learn, unlearn first
            if (currentAddressing.uri == kMidiLearnURI) {
                var addressing = {
                    uri    : kMidiUnlearnURI,
                    label  : label.val() || pname,
                    minimum: minv,
                    maximum: maxv,
                    value  : port.value,
                    steps  : sensibility.val(),
                }
                options.address(instanceAndSymbol, addressing, function (ok) {
                    if (!ok) {
                        console.log("Failed to unmap for port " + port.symbol);
                        return;
                    }

                    // remove old one
                    remove_from_array(self.addressingsByActuator[kMidiLearnURI], instanceAndSymbol)

                    delete self.addressingsByPortSymbol[instanceAndSymbol]
                    delete self.addressingsData        [instanceAndSymbol]

                    // enable this control
                    options.setEnabled(instance, port.symbol, true)

                    // now we can address if needed
                    if (actuator.uri) {
                        addressNow(actuator)
                    // if not, just close the form
                    } else {
                        form.remove()
                    }
                })
            }
            // otherwise just address it now
            else {
                addressNow(actuator)
            }
        }

        form.find('.js-save').click(function () {
            saveAddressing()
        })

        form.find('.js-close').click(function () {
            form.remove()
        })

        form.keydown(function (e) {
            if (e.keyCode == 27) {
                form.remove()
                return false
            }
            if (e.keyCode == 13) {
                saveAddressing()
                return false
            }
        })

        form.appendTo($('body'))

        form.focus()
        actuatorSelect.focus()
    }

    this.addHardwareMapping = function (instance, portSymbol, actuator_uri, label, minimum, maximum, steps) {
        var instanceAndSymbol = instance+"/"+portSymbol

        self.addressingsByActuator  [actuator_uri].push(instanceAndSymbol)
        self.addressingsByPortSymbol[instanceAndSymbol] = actuator_uri
        self.addressingsData        [instanceAndSymbol] = {
            uri    : actuator_uri,
            label  : label,
            minimum: minimum,
            maximum: maximum,
            steps  : steps,
        }

        // disable this control
        options.setEnabled(instance, portSymbol, false)
    }

    this.addMidiMapping = function (instance, portSymbol, channel, control, minimum, maximum) {
        var instanceAndSymbol = instance+"/"+portSymbol
        var actuator_uri = create_midi_cc_uri(channel, control)

        self.addressingsByActuator  [kMidiLearnURI].push(instanceAndSymbol)
        self.addressingsByPortSymbol[instanceAndSymbol] = actuator_uri
        self.addressingsData        [instanceAndSymbol] = {
            uri    : actuator_uri,
            label  : null,
            minimum: minimum,
            maximum: maximum,
            steps  : null,
        }

        // disable this control
        options.setEnabled(instance, portSymbol, false)
    }

    this.addActuator = function (actuator) {
        HARDWARE_PROFILE.push(actuator)
        self.addressingsByActuator[actuator.uri] = []
    }

    this.removeActuator = function (actuator_uri) {
        var addressings = self.addressingsByActuator[actuator_uri]

        for (var i in addressings) {
            var instanceAndSymbol = addressings[i]
            var instance          = instanceAndSymbol.substring(0, instanceAndSymbol.lastIndexOf("/"))
            var portsymbol        = instanceAndSymbol.replace(instance+"/", "")

            delete self.addressingsByPortSymbol[instanceAndSymbol]
            delete self.addressingsData        [instanceAndSymbol]

            // enable this control
            options.setEnabled(instance, portsymbol, true)
        }

        delete self.addressingsByActuator[actuator_uri]

        for (var i in HARDWARE_PROFILE) {
            var actuator = HARDWARE_PROFILE[i]
            if (actuator.uri == actuator_uri) {
                remove_from_array(HARDWARE_PROFILE, actuator)
                break
            }
        }
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

            for (j in HARDWARE_PROFILE) {
                actuator = HARDWARE_PROFILE[j]
                remove_from_array(self.addressingsByActuator[actuator.uri], instanceAndSymbol)
            }
        }
    }

    // used only for global pedalboard addressings
    // don't use it for normal operations, as it skips setEnabled()
    this.removeHardwareMappping = function (instanceAndSymbol) {
        var actuator_uri = self.addressingsByPortSymbol[instanceAndSymbol]
        if (actuator_uri && actuator_uri != kNullAddressURI) {
            remove_from_array(self.addressingsByActuator[actuator_uri], instanceAndSymbol)
        }

        delete self.addressingsByPortSymbol[instanceAndSymbol]
        delete self.addressingsData        [instanceAndSymbol]
    }

    /*
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

                    if (self.addressingsByActuator[uri].indexOf(instanceAndSymbol) >= 0) {
                        continue
                    }

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
        // save current midi maps
        var instanceAndSymbol, addressingsData, mappingURI, midiBackup = {}
        self.addressingsByActuator[kMidiLearnURI]
        for (var i in self.addressingsByActuator[kMidiLearnURI]) {
            instanceAndSymbol = self.addressingsByActuator[kMidiLearnURI][i]
            mappingURI        = self.addressingsByPortSymbol[instanceAndSymbol]
            midiBackup[mappingURI] = [instanceAndSymbol, self.addressingsData[instanceAndSymbol]]
        }

        // reset and register all HW
        self.reset()
        self.instanceAdded(":all")

        // restore midi maps
        for (mappingURI in midiBackup) {
            instanceAndSymbol = midiBackup[mappingURI][0]
            addressingsData   = midiBackup[mappingURI][1]
            self.addressingsByActuator  [kMidiLearnURI].push(instanceAndSymbol)
            self.addressingsByPortSymbol[instanceAndSymbol] = mappingURI
            self.addressingsData        [instanceAndSymbol] = {
                uri    : mappingURI,
                label  : null,
                minimum: addressingsData.minimum,
                maximum: addressingsData.maximum,
                steps  : null,
            }
        }
    }
    */

}
