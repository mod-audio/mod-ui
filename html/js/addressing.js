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

function AddressingManager(options) {
    var self = this
    
    options = $.extend({
	// This is the function that will actually make the addressing
	address: function(instanceId, symbol, addressing, callback) { callback(true) },

	// Callback to get the GUI object of a plugin instance
	getGui: function(instanceId) { }

	// Callback to enable or disable a control in GUI

    }, options)

    this.reset = function() {
	/* All adressings indexed by actuator
	   key: "url,channel,actuatorId"
	   value: list of pairs ["instanceId,symbol"]
	*/
	self.addressings = {}

	/* All addressings indexed by instanceId and control port
	   key: [instanceId][symbol]
	   value: addressing structure
	*/
	self.controls = {}

	var actuatorKey, i, actuator
	for (var i=0; i<HARDWARE_PROFILE.length; i++) {
	    actuator = HARDWARE_PROFILE[i]
	    actuatorKey = [ actuator.url, actuator.channel, actuator.actuator_id ].join(',')
	    self.addressings[actuatorKey] = []
	}	    
    }

    this.reset()

    this.sameActuator = function(a, b) {
	if (a == b)
	    return true
	if (a == null || b == null)
	    return false
	return (a.url == b.url &&
		a.channel == b.channel &&
		a.actuator_id == c.actuator_id)
    }

    // Checks if an actuator is available for a port in given mode
    this.available = function(actuator, mode, instanceId, port) {
	// First check if this port is already addressed to this actuator.
	// If so, return true
	try {
	    var current = self.controls[instanceId][port.symbol]
	    if (self.sameActuator(current, actuator) && current.mode == mode.mask)
		return true
	} catch(e) {
	    // TypeError when self.controls[instanceId] is null or addressing is none.
	    // That's ok
	}

	// Check if there are available slots in this actuator
	var actuatorKey = [ actuator.url, actuator.channel, actuator.actuator_id ].join(',')
	if (self.addressings[actuatorKey].length >= actuator.slots)
	    return false;

	// Now let's see if the actuator supports this mode
	// Operate the three masks to check if port matches mode, as specified
	// by Control Chain protocol
	return (mode.relevant & port.property_mask) == mode.expected
    }

    // Gets a list of (actuator, mode) available for an instanceId and port
    this.availableActuators = function(instanceId, port) {
	var addressings = []
	var i, actuator, j, mode
	for (i=0; i<HARDWARE_PROFILE.length; i++) {
	    actuator = HARDWARE_PROFILE[i]
	    for (j=0; j<actuator.modes.length; j++) {
		mode = actuator.modes[j]
		if (self.available(actuator, mode, instanceId, port))
		    addressings.push([actuator, mode])
	    }
	}
	return addressings
    }

    // Opens an addressing window to address this port
    this.open = function(instanceId, port, currentValue) {
	var currentAddressing = {}
	if (self.controls[instanceId])
	    currentAddressing = self.controls[instanceId][port.symbol] || {}

	// Renders the window
	var form = $(options.renderForm(instanceId, port))

	var actuators = self.availableActuators(instanceId, port)
	var actuatorSelect = form.find('select[name=actuator]')
	$('<option value="-1">').text('None').appendTo(actuatorSelect)
	var i, actuator, mode, opt, label
	for (i=0; i<actuators.length; i++) {
	    actuator = actuators[i][0]
	    mode = actuators[i][1]
	    label = actuator.name
	    if (mode.label)
		label += ' (' + mode.label + ')'
	    opt = $('<option>').attr('value', i).text(label).appendTo(actuatorSelect)
	    if (self.sameActuator(currentAddressing, actuator) && addressing.mode == mode.mask) {
		actuatorSelect.val(i)
	    }
	}
	var gui = options.getGui(instanceId)
	var pluginName = gui.effect.label || gui.effect.name
	var portName
	if (port.symbol == ':bypass')
	    portName = pluginName
	else
	    portName = port.name

	var min = form.find('input[name=min]').val(currentAddressing.minimum || port.minimum)
	var max = form.find('input[name=max]').val(currentAddressing.maximum || port.maximum)
	var label = form.find('input[name=label]').val(currentAddressing.label || portName)

	var sensibility = form.find('select[name=steps]')
	self.buildSensibilityOptions(sensibility, port)
	if (currentAddressing.steps)
	    sensibility.val(currentAddressing.steps)

	form.find('.js-save').click(function() {
	    actuator = null
	    mode = null
	    if (actuatorSelect.val() >= 0) {
		actuator = actuators[actuatorSelect.val()][0]
		mode     = actuators[actuatorSelect.val()][1]
	    }

	    // Here the addressing structure is created
	    var addressing
	    if (actuator && mode)		
		addressing = { url: actuator.url,
			       channel: actuator.channel,
			       actuator_id: actuator.actuator_id,
			       mode: mode.mask,
			       port_properties: port.property_mask,
			       label: label.val(),
			       value: currentValue,
			       minimum: min.val(),
			       maximum: max.val(),
			       'default': port['default'],
			       steps: sensibility.val(),
			       scale_points: [] // the available options in case this is enumerated (no interface for that now)
			     }

	    self.setAddressing(instanceId, port.symbol, addressing,
			       function() {
				   form.remove()
			       })
	})
	form.find('.js-close').click(function() {
	    form.remove()
	})
	form.appendTo($('body'))
    }

    this.buildSensibilityOptions = function(select, port) {
	select.children().remove()

	if (port.integer) {
	    // If port is integer, step is always 1
	    $('<option value=0>').appendTo(select)
	    select.val(0)
	    select.hide()
	    return
	}

	var options = {  17: 'Low',
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

    // Does the addressing
    this.setAddressing = function(instanceId, symbol, addressing, callback) {

	options.address(instanceId, symbol, addressing, function(ok, result) {
	    var portKey = [ instanceId, symbol ].join(',')

	    // Get the current addressing
	    var current, currentKey
	    try {
		current = self.controls[instanceId][symbol]
		currentKey = [ current.url, current.channel, current.actuator_id ].join(',')
	    } catch(e) {
		// TypeError when self.controls[instanceId] is null, that's ok
	    }

	    if (ok) {
		var gui = options.getGui(instanceId)
		// First removes current addressing
		if (current) {
		    remove_from_array(self.addressings[currentKey], portKey)
		} 
		if (addressing) {
		    // We're addressing
		    var actuatorKey = [ addressing.url, addressing.channel, addressing.actuator_id ].join(',')
		    self.addressings[actuatorKey].push(portKey)
		    self.controls[instanceId] = self.controls[instanceId] || {}
		    self.controls[instanceId][symbol] = addressing
		    gui.disable(symbol)
		} else {
		    // We're unaddressing
		    if (!self.controls[instanceId] || !self.controls[instanceId][symbol])
			// not addressed, nothing to be done
			return callback(true)
		    delete self.controls[instanceId][symbol]
		    gui.enable(symbol)

		    // Set the returned value in GUI
		    gui.setPortValue(symbol, result.value)
		}
	    }
	    callback(ok)
	})
    }

    this.serializeInstance = function(instanceId) {
	return self.controls[instanceId]
    }

    this.unserializeInstance = function(instanceId, addressings, bypassApplication) {
	// Store the original options.change callback, to bypass application
	var callback = options.address
	if (bypassApplication)
	    options.address = function() { arguments[arguments.length-1](true) }
	var restore = function() {
	    options.address = callback
	}

	// Make a queue of symbols to be addressed and process the queue with
	// a recursive asynchronous function
	var queue = Object.keys(addressings)
	var symbol
	var processNext = function() {
	    if (queue.length == 0)
		return restore()
	    symbol = queue.pop()
	    self.setAddressing(instanceId, symbol, addressings[symbol], processNext)
	}

	processNext()
    }

    // Removes an instance
    this.removeInstance = function(instanceId) {
	var addressing, symbol, actuatorKey, ports, i
	for (symbol in self.controls[instanceId]) {
	    addressing = self.controls[instanceId][symbol]
	    actuatorKey = [ addressing.url, addressing.channel, addressing.actuator_id ]
	    ports = self.addressings[actuatorKey]
	    for (i=0; i<ports.length; i++) {
		if (parseInt(ports[i].split(/,/)[0]) == instanceId) {
		    ports.splice(i, 1)
		    i--
		}
	    }
	}
	delete self.controls[instanceId]
    }
}


    

    

    

    



