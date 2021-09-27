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

// URI for BPM sync (for non-addressed control ports)
var kBpmURI ="/bpm"

// Grouped options
var deviceOption = "/hmi"
var ccOption = "/cc"
var cvOption = "/cv"

// Port types supported by cv addressing
var cvModes = ":float:integer:bypass:toggled:"

// use pitchbend as midi cc, with an invalid MIDI controller number
var MIDI_PITCHBEND_AS_CC = 131

function create_midi_cc_uri (channel, controller) {
    if (controller == MIDI_PITCHBEND_AS_CC) {
        return sprintf("%sCh.%d_Pbend", kMidiCustomPrefixURI, channel+1)
    }
    return sprintf("%sCh.%d_CC#%d", kMidiCustomPrefixURI, channel+1, controller)
}

function startsWith (value, pattern) {
    return value != null && value.indexOf(pattern) === 0;
};

function is_control_chain_uri (uri) {
  if (startsWith(uri, deviceOption)) {
    return false;
  }
  if (uri == kMidiLearnURI || startsWith(uri, kMidiCustomPrefixURI)) {
    return false;
  }
  if (isCvUri(uri)) {
    return false;
  }
  return true;
}

function isCvUri (uri) {
  if (startsWith(uri, cvOption)) {
    return true;
  }
  return false;
}

function isHwCvUri (uri) {
  if (startsWith(uri, cvOption + '/graph/cv_')) {
    return true;
  }
  return false;
}

// Units supported for tap tempo (lowercase)
var kTapTempoUnits = ['bpm']

function HardwareManager(options) {
    var self = this

    options = $.extend({
        // This is the function that will actually make the addressing
        address: function (instanceAndSymbol, addressing, callback) { callback(true) },

        // Callback to enable or disable a control in GUI
        setEnabled: function (instance, portSymbol, enabled, feedback, momentaryMode) {},

        // Renders the address html template
        renderForm: function (instance, port) {},

        // Running as mod-app
        isApp: function () { return false },

    }, options)

    this.beatsPerMinutePort = {
      ranges: { // XXX would be good to have a centralized place for this data, currently it's also in transport.js and others
          minimum: 20.0,
          maximum: 280.0
      },
      value: null
    }

    this.cvOutputPorts = []

    this.setBeatsPerMinuteValue = function (bpm) {
      if (self.beatsPerMinutePort.value === bpm) {
          return
      }
      self.beatsPerMinutePort.value = bpm
    }

    this.reset = function () {
        var addressingsByActuator = $.extend({}, self.addressingsByActuator)
        var cvOutputPorts = self.cvOutputPorts.slice()

        /* All adressings indexed by actuator
            key  : "/actuator-uri"
            value: list("/instance/symbol")
         */
         self.addressingsByActuator = {}
         self.cvOutputPorts = []

         if (cvOutputPorts) {
           for (var i = 0; i < cvOutputPorts.length; i++) {
             // if hw cv port, keep it
             if (isHwCvUri(cvOutputPorts[i].uri)) {
               self.cvOutputPorts.push(cvOutputPorts[i])
             }
           }
         }

        if (addressingsByActuator) {
          for (var act in addressingsByActuator) {
            if (isCvUri(act) && cvOutputPorts.find(function (port) { return port.uri === act })) {
              self.addressingsByActuator[act] = []
            }
          }
        }

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
        self.addressingsByActuator[kBpmURI] = []
    }

    this.reset()

    // Get all addressing types that can be used for a port
    // Most of these are 1:1 match to LV2 hints, but we have extra details.
    this.availableAddressingTypes = function (port, tempo) {
        if (tempo) {
            return ["enumeration"]
        }

        var properties = port.properties
        var available  = []

        // prevent some properties from going together
        if (properties.indexOf("trigger") >= 0) {
            available.push("trigger")
        } else if (properties.indexOf("enumeration") >= 0) {
            available.push("enumeration")
        } else if (properties.indexOf("toggled") >= 0) {
            available.push("toggled")
        } else if (properties.indexOf("integer") >= 0) {
            available.push("integer")
        } else {
            available.push("float")
        }

        if (properties.indexOf("logarithmic") >= 0)
            available.push("logarithmic")

        if (port.symbol === ":bpm" && properties.indexOf("tapTempo") >= 0 && kTapTempoUnits.indexOf(port.units.symbol.toLowerCase()) >= 0)
            available.push("taptempo")

        if (port.scalePoints.length >= 2)
            available.push("scalepoints")
        if (port.symbol == ":bypass")
            available.push("bypass")

        return available
    }

    this.availableActuatorsWithModes = function (list, types) {
      var available = {}
      if (list) {
        for (var i in list) {
            actuator = list[i]
            modes    = actuator.modes

            // usedAddressings = self.addressingsByActuator[actuator.uri]
            // if (ADDRESSING_PAGES == 0 && usedAddressings.length >= actuator.max_assigns && usedAddressings.indexOf(key) < 0) {
            //     continue
            // }

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
      return available
    }

    this.isCvAvailable = function (port) {
      var defaultTypes = self.availableAddressingTypes(port, false)
      var available = self.availableActuatorsWithModes([{ uri: cvOption, modes: cvModes }], defaultTypes)
      return available.hasOwnProperty(cvOption)
    }

    // Gets a list of available actuators for a port
    this.availableActuators = function (instance, port, tempo) {
        var key   = instance+"/"+port.symbol
        var defaultTypes = self.availableAddressingTypes(port, false)
        var types = tempo ? self.availableAddressingTypes(port, tempo) : defaultTypes

        var available = self.availableActuatorsWithModes(HARDWARE_PROFILE, types)

        // midi-learn is always available, except for enumeration
        if (defaultTypes.indexOf("enumeration") < 0 || port.scalePoints.length == 2)
        {
            available[kMidiLearnURI] = {
                uri  : kMidiLearnURI,
                name : "MIDI Learn...",
                modes: ":float:trigger:bypass:integer:toggled:",
                steps: [],
                max_assigns: 99
            }
        }

        available = $.extend(self.availableActuatorsWithModes(self.cvOutputPorts, defaultTypes), available)

        return available
    }

    this.buildDividerOptions = function (select, port, curDividers) {
        select.children().remove()

        var filteredDividers = getDividerOptions(port, self.beatsPerMinutePort.ranges.minimum, self.beatsPerMinutePort.ranges.maximum)

        // And build html select options
        for (i = 0; i < filteredDividers.length; i++) {
          $('<option>').attr('value', filteredDividers[i].value).html(filteredDividers[i].label).appendTo(select)
        }

        // Select previously saved divider or set first divider as default
        if (filteredDividers.length > 0) {
          var def = (curDividers !== null && curDividers !== undefined) ? curDividers : filteredDividers[0].value
          select.val(def)
        }

        return filteredDividers
    }

    this.buildSensitivityOptions = function (select, port, actuatorSteps, curStep) {
        select.children().remove()

        if (port.properties.indexOf("enumeration") >= 0 ||
            port.properties.indexOf("integer") >= 0 ||
            port.properties.indexOf("toggled") >= 0 ||
            port.properties.indexOf("trigger") >= 0)
        {
            var value
            if (port.properties.indexOf("enumeration") >= 0) {
                value = port.scalePoints.length - 1
            } else if (port.properties.indexOf("integer") >= 0) {
                value = port.ranges.maximum - port.ranges.minimum
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

        var def, soptions = {}

        switch ((actuatorSteps ? actuatorSteps.length : null))
        {
        case 1:
            def = actuatorSteps[0]
            soptions[def] = 'Default'
            break
        case 2:
            def = actuatorSteps[0]
            soptions[actuatorSteps[0]] = 'Medium'
            soptions[actuatorSteps[1]] = 'High'
            break
        case 3:
            def = actuatorSteps[1]
            soptions[actuatorSteps[0]] = 'Low'
            soptions[actuatorSteps[1]] = 'Medium'
            soptions[actuatorSteps[2]] = 'High'
            break
        default:
            def = 33
            soptions = {
                17: 'Low',
                33: 'Medium',
                65: 'High',
            }
            break
        }

        if (port.rangeSteps) {
            def = port.rangeSteps
            soptions[def] = 'Default'
        }

        var steps, label, keys = Object.keys(soptions).sort()
        for (var i in keys) {
            steps  = keys[i]
            label  = soptions[steps]
            label += ' (' + steps + ' steps)'
            $('<option>').attr('value', steps).html(label).appendTo(select)
        }

        select.val(curStep != null ? curStep : def)

        if (keys.length === 1) {
            select.parent().parent().hide()
        }
    }

    this.disableMinMaxSteps = function (form, disabled) {
      form.find('select[name=steps]').prop('disabled', disabled)
      form.find('input[name=min]').prop('disabled', disabled)
      form.find('input[name=max]').prop('disabled', disabled)
    }

    this.portSupportsSensitivity = function(port) {
      if (port.properties.indexOf("integer") >= 0)
        return false;
      if (port.properties.indexOf("toggled") >= 0)
        return false;
      if (port.properties.indexOf("trigger") >= 0)
        return false;
      if (port.symbol == ":bypass")
        return false;
      if (port.symbol == ":presets")
        return false;
      return true;
    }

    this.toggleAdvancedItemsVisibility = function (port,
                                                   sensitivity, ledColourMode, momentarySwMode,
                                                   currentActuator, curStep) {
      if (currentActuator && currentActuator.steps.length !== 0 && this.portSupportsSensitivity(port)) {
        sensitivity.removeClass('disabled').parent().parent().show()
      } else {
        sensitivity.addClass('disabled').parent().parent().hide()
      }

      if (currentActuator && currentActuator.modes.indexOf(":colouredlist:") >= 0 &&
          port.properties.indexOf("enumeration") >= 0)
      {
        ledColourMode.removeClass('disabled').parent().parent().show()
      }
      else
      {
        ledColourMode.addClass('disabled').parent().parent().hide()
      }

      if (currentActuator && currentActuator.modes.indexOf(":momentarytoggle:") >= 0 &&
          port.properties.indexOf("enumeration") < 0 &&
          port.properties.indexOf("tapTempo") < 0 &&
          port.properties.indexOf("trigger") < 0)
      {
        momentarySwMode.removeClass('disabled').parent().parent().show()
      }
      else
      {
        momentarySwMode.addClass('disabled').parent().parent().hide()
      }

      self.buildSensitivityOptions(sensitivity,
                                   port,
                                   currentActuator ? currentActuator.steps : null,
                                   curStep)
    }

    // Show dynamic field content based on selected type of addressing
    this.showDynamicField = function (form, typeInputVal, currentAddressing, port, cvUri, firstOpen) {
      // Hide all then show the relevant content
      form.find('.dynamic-field').hide()
      // Hide led-color and momentary modes, only usable for a few selections
      // These are enabled by various event triggers below as needed
      form.find('select[name=led-color-mode]').addClass('disabled').parent().parent().hide()
      form.find('select[name=momentary-sw-mode]').addClass('disabled').parent().parent().hide()

      if (typeInputVal === kMidiLearnURI)
      {
        form.find('.midi-learn-hint').show()
        if (currentAddressing && currentAddressing.uri && currentAddressing.uri.lastIndexOf(kMidiCustomPrefixURI, 0) === 0) {
          form.find('.midi-learn-hint').hide()
          var midiCustomLabel = "MIDI " + currentAddressing.uri.replace(kMidiCustomPrefixURI,"").replace(/_/g," ")
          form.find('.midi-custom-uri').text(midiCustomLabel)
          form.find('.midi-learn-custom').show()
        }
      }
      else if (typeInputVal === deviceOption)
      {
        form.find('.device-table').find('.selected').click()
        form.find('.device-table').show()
      }
      else if (typeInputVal === ccOption)
      {
        var ccActuatorSelect = form.find('select[name=cc-actuator]')
        if (ccActuatorSelect.children('option').length) {
          ccActuatorSelect.change()
          form.find('.cc-select').show()
        } else if (self.hasControlChainDevice()) {
          form.find('.cc-in-use').show()
        } else {
          form.find('.no-cc').show()
        }
      }
      else if (typeInputVal === cvOption)
      {
        if (self.cvOutputPorts.length) {
          form.find('.cv-select').show()
        } else {
          form.find('.no-cv').show()
        }
      }

      // Disabled/Enable save button
      if (currentAddressing && currentAddressing.uri) {
        if (typeInputVal === ccOption && !self.hasControlChainDevice() ||
            (typeInputVal === cvOption && !self.cvOutputPorts.length)) {
          form.find('.js-save').addClass('disabled')
        } else {
          form.find('.js-save').removeClass('disabled')
        }
      } else {
        if ((!form.find('input[name=tempo]').prop("checked") && typeInputVal === kNullAddressURI) ||
            (typeInputVal === ccOption && !self.hasControlChainDevice()) ||
            (typeInputVal === cvOption && !self.cvOutputPorts.length)) {
          form.find('.js-save').addClass('disabled')
        } else {
          form.find('.js-save').removeClass('disabled')
        }
      }

      // Hide/show extended specific content
      if (typeInputVal === kNullAddressURI ||
          typeInputVal === kMidiLearnURI || typeInputVal.lastIndexOf(kMidiCustomPrefixURI, 0) === 0 ||
          (typeInputVal === ccOption && !self.hasControlChainDevice()) ||
          typeInputVal === cvOption ||
          ! this.portSupportsSensitivity(port))
      {
        form.find('.sensitivity').css({ display: "none" })
        self.disableMinMaxSteps(form, false)
      }
      else
      {
        form.find('.sensitivity').css({ display: "block" })
      }

      if (typeInputVal === kMidiLearnURI || typeInputVal.lastIndexOf(kMidiCustomPrefixURI, 0) === 0 || typeInputVal === ccOption || typeInputVal === cvOption)
      {
        form.find('.tempo').css({ display: "none" })
      }
      else if (hasTempoRelatedDynamicScalePoints(port))
      {
        form.find('.tempo').css({ display: "block" })
        if (form.find('input[name=tempo]').prop("checked")) {
          self.disableMinMaxSteps(form, true)
        }
      }

      // Hide/show cv operational mode for everything except CV plugin ports
      if (typeInputVal !== cvOption || isHwCvUri(cvUri)) {
        form.find('.cv-op-mode').css({ display: "none" })
      } else {
        form.find('.cv-op-mode').css({ display: "block" })
      }

      // Set unipolar mode based on default cv port ranges or current addressing
      if (typeInputVal === cvOption) {
        var cvPort = self.cvOutputPorts.find(function (port) { return port.uri === cvUri })
        if (cvPort) {
          var operationalMode = cvPort.defaultOperationalMode
          if (firstOpen && currentAddressing && currentAddressing.uri &&
              isCvUri(currentAddressing.uri) && currentAddressing.operationalMode)
          {
            operationalMode = currentAddressing.operationalMode
          }
          form.find('select[name=cv-op-mode]').val(operationalMode)
        }
      }
    }

    this.buildDeviceTable = function (deviceTable, currentAddressing, actuators,
                                      hmiPageInput, hmiSubPageInput, hmiUriInput,
                                      sensitivity, ledColourMode, momentarySwMode, port) {
      var table = $('<table/>').addClass('hmi-table')
      var row, cell, ctable, uri, uriAddressings, usedAddressings, addressing
      var actuator, actuatorName, actuatorSubPages, groupActuator, groupAddressings, lastGroupName, subpageTables = {}

      if (ADDRESSING_PAGES > 0)
      {
        // build header row
        var headerRow = $('<tr/>')
        for (var i = 1; i <= ADDRESSING_PAGES; i++) {
          headerRow.append($('<th>Page '+i+'</th>'))
        }
        table.append(headerRow)

        for (var actuatorUri in actuators) {
          if (!startsWith(actuatorUri, deviceOption)) {
            continue
          }
          actuator = actuators[actuatorUri]
          actuatorSubPages = actuator.subpages || [null]
          usedAddressings = self.addressingsByActuator[actuatorUri]

          // pre-create groups for subpages
          if (actuator.subpages) {
            for (var i in actuator.subpages) {
              lastGroupName = actuator.subpages[i]
              if (!subpageTables[lastGroupName]) {
                  deviceTable.append(table)
                  deviceTable.append($('<div class="group-strike">'+ lastGroupName +'</div>'))
                  table = subpageTables[lastGroupName] = $('<table/>').addClass('hmi-table')
              } else {
                  table = subpageTables[lastGroupName]
              }
            }
            ctable = null
            lastGroupName = null

          // actuator belongs to a new group (compared to last one)
          } else if (actuator.group && actuator.group != lastGroupName) {
              deviceTable.append(table)
              deviceTable.append($('<div class="group-strike">'+ actuator.group +'</div>'))
              ctable = table = $('<table/>').addClass('hmi-table')
              lastGroupName = actuator.group

          // there was a group before, but not anymore, so create a "no-group" group
          } else if (lastGroupName && !actuator.group) {
              deviceTable.append(table)
              deviceTable.append($('<div class="group-strike">No Group</div>'))
              ctable = table = $('<table/>').addClass('hmi-table')
              lastGroupName = null

          // no groups ever in use, just act normal
          } else {
              ctable = table
          }

          for (var actSubPage = 0; actSubPage < actuatorSubPages.length; actSubPage++) {
            row = $('<tr/>')
            if (actuator.subpages) {
                ctable = subpageTables[actuatorSubPages[actSubPage]]
            }
            for (var addrPage = 0; addrPage < ADDRESSING_PAGES; addrPage++) {
              actuatorName = lastGroupName ? (actuator.gname || actuator.name) : actuator.name
              cell = $('<td data-page="'+ addrPage +'" data-subpage="'+ actSubPage +'" data-uri="'+ actuatorUri +'">'+ actuatorName +'</td>')
              if (currentAddressing &&
                  currentAddressing.uri == actuatorUri &&
                  currentAddressing.page == addrPage &&
                  (currentAddressing.subpage == null || currentAddressing.subpage == actSubPage)) {
                hmiPageInput.val(currentAddressing.page)
                hmiSubPageInput.val(currentAddressing.subpage)
                hmiUriInput.val(currentAddressing.uri)
                cell.addClass('selected')
              } else {
                // Only allow actuator groups to be used when all their "child" actuators are not in use on current page
                if (actuator.actuator_group) {
                  for (var i = 0; i < actuator.actuator_group.length; i++) {
                    uri = actuator.actuator_group[i]
                    uriAddressings = self.addressingsByActuator[uri]
                    for (var j in uriAddressings) {
                      instance = uriAddressings[j]
                      addressing = self.addressingsData[instance]
                      if (addressing.page == addrPage) {
                        cell.addClass('disabled')
                      }
                    }
                  }
                }
                // Check if page+uri already assigned, then disable cell
                for (var i in usedAddressings) {
                  instance = usedAddressings[i]
                  addressing = self.addressingsData[instance]
                  if (addressing.page == addrPage &&
                      (addressing.subpage == null || addressing.subpage == actSubPage)) {
                    cell.addClass('disabled')
                  }
                }
              }
              row.append(cell)
            }
            ctable.append(row)
          }
        }
      }
      else
      {
        for (var actuatorUri in actuators) {
          if (!startsWith(actuatorUri, deviceOption)) {
            continue
          }
          actuator = actuators[actuatorUri]
          usedAddressings = self.addressingsByActuator[actuatorUri]
          if (actuator.actuator_group && actuator.group && actuator.group != lastGroupName) {
              deviceTable.append(table)
              deviceTable.append($('<div class="group-strike">'+ actuator.group +'</div>'))
              table = $('<table/>').addClass('hmi-table')
              lastGroupName = actuator.group
          }
          row = $('<tr/>')
          cell = $('<td data-uri="'+ actuatorUri +'">'+ actuator.name+'</td>')

          if (currentAddressing && currentAddressing.uri == actuatorUri) {
            hmiUriInput.val(currentAddressing.uri)
            cell.addClass('selected')
          } else {
            // Only allow actuator groups to be used when all their "child" actuators are not in use
            if (actuator.actuator_group) {
              for (i = 0; i < actuator.actuator_group.length; i++) {
                uri = actuator.actuator_group[i]
                uriAddressings = self.addressingsByActuator[uri]
                if (uriAddressings.length) {
                  cell.addClass('disabled')
                }
              }
            }
            if (usedAddressings.length >= actuator.max_assigns) {
              cell.addClass('disabled')
            }
          }

          row.append(cell)
          table.append(row)
        }
      }

      deviceTable.append(table)

      // when addressing an actuator group, all "child" actuators or intersecting actuator groups are no longer
      // available to be addressed to anything else except on different pages
      if (ADDRESSING_PAGES > 0)
      {
        for (var i in HARDWARE_PROFILE) {
          if (HARDWARE_PROFILE[i].actuator_group) {
            groupActuator = HARDWARE_PROFILE[i]
            for (var j in self.addressingsByActuator[groupActuator.uri]) {
              instance = self.addressingsByActuator[groupActuator.uri][j]
              groupAddressings = self.addressingsData[instance]
              for (var k in groupActuator.actuator_group) {
                deviceTable.find('[data-uri="' + groupActuator.actuator_group[k] + '"][data-page="' + groupAddressings.page + '"]').addClass('disabled')
                for (var l = 0 in actuators) {
                  if (l !== groupActuator.uri && actuators[l].actuator_group && actuators[l].actuator_group.includes(groupActuator.actuator_group[k])) {
                    deviceTable.find('[data-uri="' + l + '"][data-page="' + groupAddressings.page + '"]').addClass('disabled')
                  }
                }
              }

            }
          }
        }
      }
      else
      {
        for (var i in HARDWARE_PROFILE) {
          if (HARDWARE_PROFILE[i].actuator_group) {
            groupActuator = HARDWARE_PROFILE[i]
            if (self.addressingsByActuator[groupActuator.uri].length) {
              for (var j in groupActuator.actuator_group) {
                deviceTable.find('[data-uri="' + groupActuator.actuator_group[j] + '"]').addClass('disabled')
              }
            }
          }
        }
      }

      deviceTable.find('td').click(function () {
        if ($(this).hasClass('disabled')) {
          return
        }
        var actuatorUri = $(this).attr('data-uri')
        var page = $(this).attr('data-page')
        var subpage = $(this).attr('data-subpage')

        // Update hidden inputs value
        hmiPageInput.val(page)
        hmiSubPageInput.val(subpage)
        hmiUriInput.val(actuatorUri)

        // Remove 'selected' class to all cells then add it to the clicked one
        deviceTable.find('td').removeClass('selected')
        $(this).addClass('selected')

        self.toggleAdvancedItemsVisibility(port,
                                           sensitivity, ledColourMode, momentarySwMode,
                                           actuators[actuatorUri],
                                           currentAddressing.uri === actuatorUri ? currentAddressing.steps : null)
      })

      self.toggleAdvancedItemsVisibility(port,
                                         sensitivity, ledColourMode, momentarySwMode,
                                         actuators[currentAddressing.uri], currentAddressing.steps)
    }

    this.addOption = function (addressings, actuator, currentAddressing, select) {
      var addressedToMe = currentAddressing.uri && currentAddressing.uri === actuator.uri
      if ((addressings && addressings.length < actuator.max_assigns) || addressedToMe) {
        $('<option>').attr('value', actuator.uri).text(actuator.name).appendTo(select)
        if (addressedToMe) {
          select.val(currentAddressing.uri)
        }
      }
    }

    // Opens an addressing window to address this a port
    this.open = function (instance, port, pluginLabel) {
        var instanceAndSymbol = instance+"/"+port.symbol
        var currentAddressing = self.addressingsData[instanceAndSymbol] || {}

        // Renders the window
        var form = $(options.renderForm(instance, port))

        var typeSelect = form.find('select[name=type]')
        var typeInput = form.find('input[name=type]')
        var hmiPageInput = form.find('input[name=hmi-page]')
        var hmiSubPageInput = form.find('input[name=hmi-subpage]')
        var hmiUriInput = form.find('input[name=hmi-uri]')
        var deviceTable = form.find('.device-table')
        var sensitivity = form.find('select[name=steps]')
        var ledColourMode = form.find('select[name=led-color-mode]')
        var momentarySwMode = form.find('select[name=momentary-sw-mode]')
        var operationalMode = form.find('select[name=cv-op-mode]')

        // Create selectable buttons to choose addressings type and show relevant dynamic content
        var typeInputVal = kNullAddressURI
        if (currentAddressing && currentAddressing.uri)
        {
          if (currentAddressing.uri == kMidiLearnURI || currentAddressing.uri.lastIndexOf(kMidiCustomPrefixURI, 0) === 0) {
            typeInputVal = kMidiLearnURI
          } else if (startsWith(currentAddressing.uri, deviceOption)) {
            typeInputVal = deviceOption
          } else if (startsWith(currentAddressing.uri, cvOption)) {
            typeInputVal = cvOption
          } else if (currentAddressing.uri !== kBpmURI){
            typeInputVal = ccOption
          }

          // restore values
          ledColourMode.val(currentAddressing.coloured ? 1 : 0)
          momentarySwMode.val(currentAddressing.momentary || 0)
        }
        else
        {
          // If there is no addressing made yet, try to set some good defaults
          ledColourMode.val(port.properties.indexOf("preferColouredListByDefault") >= 0 ? 1 : 0)

          if (port.properties.indexOf("preferMomentaryOffByDefault") >= 0) {
              momentarySwMode.val(2)
          } else if (port.properties.indexOf("preferMomentaryOnByDefault") >= 0) {
              momentarySwMode.val(1)
          } else {
              momentarySwMode.val(0)
          }
        }

        typeInput.val(typeInputVal)

        var actuators = self.availableActuators(instance, port, currentAddressing.tempo)
        var typeOptions = [kNullAddressURI, deviceOption, kMidiLearnURI, ccOption, cvOption]
        var i = 0
        typeSelect.find('option').unwrap().each(function() {
            var btn = $('<div class="btn js-type" data-value="'+typeOptions[i]+'">'+$(this).text()+'</div>');
            var jbtn = $(btn);
            if(jbtn.attr('data-value') == typeInput.val()) {
              btn.addClass('selected')
            }
            // Hide Device tab under mod-app
            if (jbtn.attr('data-value') === deviceOption && options.isApp()) {
              jbtn.hide()
            }
            // Hide MIDI tab if not available
            else if (jbtn.attr('data-value') === kMidiLearnURI && !actuators[kMidiLearnURI]) {
              jbtn.hide()
            }
            // Hide CV tab if not available
            else if (jbtn.attr('data-value') === cvOption && !self.isCvAvailable(port)) {
              jbtn.hide()
            }
            $(this).replaceWith(btn)
            i++
        })

        // Add options to control chain and cv actuators select
        var actuator, addressings, ccUri, cvUri
        var ccActuatorSelect = form.find('select[name=cc-actuator]')
        var cvPortSelect = form.find('select[name=cv-port]')
        var cvActuators
        var ccActuators = []
        for (var uri in actuators) {
          ccUri = is_control_chain_uri(uri)
          cvUri = isCvUri(uri)
          if (!(cvUri || ccUri)) {
            continue
          }
          actuator = actuators[uri]
          addressings = self.addressingsByActuator[uri]

          if (ccUri) {
            ccActuators.push(actuator)
            self.addOption(addressings, actuator, currentAddressing, ccActuatorSelect)
          } else { // cvUri
            self.addOption(addressings, actuator, currentAddressing, cvPortSelect)
          }
        }

        if (ccActuators.length === 0) {
          ccActuatorSelect.hide()
        } else {
          ccActuatorSelect.change(function () {
            var actuatorUri = $(this).val()
            self.toggleAdvancedItemsVisibility(port,
                                               sensitivity, ledColourMode, momentarySwMode,
                                               actuators[actuatorUri],
                                               currentAddressing.uri === actuatorUri ? currentAddressing.steps : null)
          })
        }

        form.find('.js-type').click(function () {
          form.find('.js-type').removeClass('selected')
          $(this).addClass('selected')
          typeInput.val($(this).attr('data-value'))
          self.showDynamicField(form, typeInput.val(), currentAddressing, port, cvPortSelect.val(), false)
        })

        cvPortSelect.change(function () {
          self.showDynamicField(form, typeInput.val(), currentAddressing, port, $(this).val(), false)
        })

        self.showDynamicField(form, typeInputVal, currentAddressing, port, cvPortSelect.val(), true)

        var pname = (port.symbol == ":bypass" || port.symbol == ":presets") ? pluginLabel : port.shortName
        var minv  = currentAddressing.minimum != null ? currentAddressing.minimum : port.ranges.minimum
        var maxv  = currentAddressing.maximum != null ? currentAddressing.maximum : port.ranges.maximum
        var min   = form.find('input[name=min]').val(minv).attr("min", port.ranges.minimum).attr("max", port.ranges.maximum)
        var max   = form.find('input[name=max]').val(maxv).attr("min", port.ranges.minimum).attr("max", port.ranges.maximum)
        var label = form.find('input[name=label]').val(currentAddressing.label || pname)
        var tempo = form.find('input[name=tempo]').prop("checked", currentAddressing.tempo || false)
        var divider = form.find('select[name=divider]')

        var dividerOptions = [];

        // Hide Tempo section if the ControlPort does not have the property mod:tempoRelatedDynamicScalePoints
        if (!hasTempoRelatedDynamicScalePoints(port)) {
          form.find('.tempo').css({display:"none"})
        // Else, build filtered list of divider values based on bpm and ControlPort min/max values
        } else {
          if (tempo.prop("checked")) {
            self.disableMinMaxSteps(form, true)
          }
          form.find('input[name=tempo]').bind('change', function() {
            self.disableMinMaxSteps(form, this.checked)

            if (currentAddressing.uri == null) {
              if (this.checked) {
                form.find('.js-save').removeClass('disabled')
              } else if (typeInput.val() === kNullAddressURI) {
                form.find('.js-save').addClass('disabled')
              }
            }

            actuators = self.availableActuators(instance, port, this.checked)
            deviceTable.empty()
            self.buildDeviceTable(deviceTable, currentAddressing, actuators,
                                  hmiPageInput, hmiSubPageInput, hmiUriInput,
                                  sensitivity, ledColourMode, momentarySwMode, port)
          })
          dividerOptions = self.buildDividerOptions(divider, port, currentAddressing.dividers)
        }

        if (port.properties.indexOf("toggled") >= 0 || port.properties.indexOf("trigger") >= 0) {
            // boolean, always min or max value
            var step = maxv-minv
            min.attr("step", step)
            max.attr("step", step)
            // hide ranges
            form.find('.range').hide()

        } else if (port.properties.indexOf("enumeration") >= 0) {
            // enumeration, step is list size - 1
            var step = port.scalePoints.length - 1
            min.attr("step", step)
            max.attr("step", step)
            // hide ranges
            form.find('.range').hide()

        } else if (port.properties.indexOf("integer") < 0) {
            // float, allow non-integer stepping
            var step = (maxv-minv)/100
            min.attr("step", step)
            max.attr("step", step)

            // Hide sensitivity and tempo options for MIDI
            // FIXME this whole section below can likely be removed without side effects
            var act = typeInput.val()
            if (act === kMidiLearnURI || act.lastIndexOf(kMidiCustomPrefixURI, 0) === 0 || act === cvOption) {
                form.find('.sensitivity').css({ display: "none" })
                form.find('.tempo').css({ display: "none" })
            }
            // Hide tempo option for CC or CV
            if (act === ccOption || act === cvOption) {
              form.find('.tempo').css({ display: "none" })
            }

            // Hide cv operational mode for everything except CV
            if (act !== cvOption) {
              form.find('.cv-op-mode').css({ display: "none" })
            }
        }

        self.buildDeviceTable(deviceTable, currentAddressing, actuators,
                              hmiPageInput, hmiSubPageInput, hmiUriInput,
                              sensitivity, ledColourMode, momentarySwMode, port)

        form.find('.js-save').click(function () {
            if ($(this).hasClass('disabled')) {
              return
            }
            self.saveAddressing(
              instance,
              port,
              actuators,
              typeInput,
              hmiPageInput,
              hmiSubPageInput,
              hmiUriInput,
              ccActuatorSelect,
              cvPortSelect,
              min,
              max,
              label,
              pname,
              sensitivity,
              ledColourMode,
              momentarySwMode,
              tempo,
              divider,
              dividerOptions,
              operationalMode,
              form
            );
        })

        form.find('.js-close').click(function () {
            form.remove()
            form = null
        })

        form.find('.advanced-toggle').click(function() {
            if (!form.find('.advanced-container').is(':visible')) {
              $('.mod-pedal-settings-address').find('.mod-box').animate({
                width: '916px'
              }, 100, function() {
                form.find('.advanced-container').toggle()
              });
            } else {
              form.find('.advanced-container').toggle(0, function() {
                $('.mod-pedal-settings-address').find('.mod-box').animate({
                  width: '766px'
                }, 100)
              })
            }
        })

        $('body').keydown(function (e) {
            if (e.keyCode == 27 && form && form.is(':visible')) {
                form.remove()
                form = null
                return false
            }
        })
        form.keydown(function (e) {
            if (e.keyCode == 13) {
                self.saveAddressing(
                  instance,
                  port,
                  actuators,
                  typeInput,
                  hmiPageInput,
                  hmiSubPageInput,
                  hmiUriInput,
                  ccActuatorSelect,
                  cvPortSelect,
                  min,
                  max,
                  label,
                  pname,
                  sensitivity,
                  ledColourMode,
                  momentarySwMode,
                  tempo,
                  divider,
                  dividerOptions,
                  operationalMode,
                  form
                );
                return false
            }
        })

        form.appendTo($('body'))
        form.focus()
    }

    this.addressNow = function (
      instance,
      port,
      actuator,
      minv,
      maxv,
      labelValue,
      sensitivityValue,
      tempoValue,
      dividerValue,
      dividerOptions,
      page,
      subpage,
      colouredValue,
      momentarySwValue,
      operationalModeValue,
      form
      ) {
        var instanceAndSymbol = instance+"/"+port.symbol;
        var currentAddressing = self.addressingsData[instanceAndSymbol] || {}

        var portValuesWithDividerLabels = []
        // Sync port value to bpm
        if (tempoValue && dividerValue && port.units && port.units.symbol) {
          if (port.units.symbol === 'BPM') {
            port.value = getPortValue(self.beatsPerMinutePort.value, dividerValue, port.units.symbol) // no need for conversion
          } else {
            port.value = convertSecondsToPortValueEquivalent(
              getPortValue(self.beatsPerMinutePort.value, dividerValue, port.units.symbol),
              port.units.symbol
            );
          }
        }

        var addressing = {
            uri    : actuator.uri || kNullAddressURI,
            label  : labelValue,
            minimum: minv,
            maximum: maxv,
            value  : port.value,
            steps  : sensitivityValue,
            tempo  : tempoValue,
            dividers: dividerValue,
            feedback: actuator.feedback === false ? false : true, // backwards compatible, true by default
            page: page || null,
            subpage: subpage || null,
            coloured: colouredValue,
            momentary: momentarySwValue,
            operationalMode: operationalModeValue,
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
                if (startsWith(currentAddressing.uri, kMidiCustomPrefixURI)) {
                    currentAddressing.uri = kMidiLearnURI
                }
                remove_from_array(self.addressingsByActuator[currentAddressing.uri], instanceAndSymbol)
            }

            // We're addressing
            if (actuator.uri && actuator.uri != kNullAddressURI)
            {
                var actuator_uri = actuator.uri
                if (startsWith(actuator_uri, kMidiCustomPrefixURI)) {
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

                // convert some values to proper type
                addressing.coloured = !!addressing.coloured
                addressing.momentary = parseInt(addressing.momentary)

                // now save
                self.addressingsByPortSymbol[instanceAndSymbol] = actuator.uri
                self.addressingsData        [instanceAndSymbol] = addressing

                // disable this control
                var feedback = actuator.feedback === false ? false : true // backwards compat, true by default
                options.setEnabled(instance, port.symbol, false, feedback, true, addressing.momentary)
            }
            // We're unaddressing
            else if (unaddressing)
            {
                delete self.addressingsByPortSymbol[instanceAndSymbol]
                delete self.addressingsData        [instanceAndSymbol]

                // enable this control
                options.setEnabled(instance, port.symbol, true)
            }

            if (form !== undefined) {
              form.remove()
              form = null
            }
        })
    }

    this.saveAddressing = function (
      instance,
      port,
      actuators,
      typeInput,
      hmiPageInput,
      hmiSubPageInput,
      hmiUriInput,
      ccActuatorSelect,
      cvPortSelect,
      min,
      max,
      label,
      pname,
      sensitivity,
      ledColourMode,
      momentarySwMode,
      tempo,
      divider,
      dividerOptions,
      operationalMode,
      form
      ) {
        var instanceAndSymbol = instance+"/"+port.symbol
        var currentAddressing = self.addressingsData[instanceAndSymbol] || {}

        var page = hmiPageInput.val()
        var subpage = hmiSubPageInput.val()
        var typeInputVal = typeInput.val()
        var uri = kNullAddressURI
        if (typeInputVal === deviceOption && hmiUriInput.val()) {
          uri = hmiUriInput.val()
        } else if(typeInputVal === ccOption && ccActuatorSelect.val()) {
          uri = ccActuatorSelect.val()
        } else if(typeInputVal === cvOption && cvPortSelect.val()) {
          uri = cvPortSelect.val()
        } else if (typeInputVal === kMidiLearnURI) {
          uri = kMidiLearnURI
        }
        var actuator = actuators[uri] || {}

        var tempoValue = tempo.prop("checked")
        // Sync port value to bpm with virtual bpm actuator
        if (tempoValue && uri === kNullAddressURI) {
          actuator = {
            uri  : kBpmURI,
            modes: ":float:integer:",
            steps: [],
            max_assigns: 99
          }
        }

        // no actuator selected or old one exists, do nothing
        if (actuator.uri == null && currentAddressing.uri == null) {
            console.log("Nothing to do")
            if (form !== undefined) {
              form.remove()
              form = null
            }
            return
        }

        // Check values
        var minv = min.val()
        if (minv == undefined || minv == "")
            minv = port.ranges.minimum

        var maxv = max.val()
        if (maxv == undefined || maxv == "")
            maxv = port.ranges.maximum

        if (parseFloat(minv) >= parseFloat(maxv)) {
            alert("The minimum value is equal or higher than the maximum. We cannot address a control like this!")
            return
        }

        var labelValue = label.val() || pname
        var sensitivityValue = sensitivity.val()
        var dividerValue = divider.val() ? parseFloat(divider.val()): divider.val()
        var colouredValue = ledColourMode.hasClass('disabled') ? 0 : parseInt(ledColourMode.val())
        var momentarySwValue = momentarySwMode.hasClass('disabled') ? 0 : parseInt(momentarySwMode.val())
        var operationalModeValue = operationalMode.val()

        // if changing from midi-learn, unlearn first
        if (currentAddressing.uri == kMidiLearnURI) {
            var addressing = {
                uri    : kMidiUnlearnURI,
                label  : labelValue,
                minimum: minv,
                maximum: maxv,
                value  : port.value,
                steps  : sensitivityValue,
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
                  self.addressNow(
                    instance,
                    port,
                    actuator,
                    minv,
                    maxv,
                    labelValue,
                    sensitivityValue,
                    tempoValue,
                    dividerValue,
                    dividerOptions,
                    page,
                    subpage,
                    colouredValue,
                    momentarySwValue,
                    operationalModeValue,
                    form
                  );
                // if not, just close the form
                } else if (form !== undefined) {
                    form.remove()
                    form = null
                }
            })
        }
        // otherwise just address it now
        else {
          self.addressNow(
            instance,
            port,
            actuator,
            minv,
            maxv,
            labelValue,
            sensitivityValue,
            tempoValue,
            dividerValue,
            dividerOptions,
            page,
            subpage,
            colouredValue,
            momentarySwValue,
            operationalModeValue,
            form
          );
        }
    }

    this.addHardwareMapping = function (instance, portSymbol, actuator_uri,
                                        label, minimum, maximum, steps,
                                        tempo, dividers, page, subpage, group, feedback, coloured, momentary) {
        var instanceAndSymbol = instance+"/"+portSymbol
        self.addressingsByActuator  [actuator_uri].push(instanceAndSymbol)
        self.addressingsByPortSymbol[instanceAndSymbol] = actuator_uri
        self.addressingsData        [instanceAndSymbol] = {
            uri     : actuator_uri,
            label   : label,
            minimum : minimum,
            maximum : maximum,
            steps   : steps,
            tempo   : tempo,
            dividers: dividers,
            feedback: feedback,
            page    : page,
            subpage : subpage,
            group   : group,
            coloured: coloured,
            momentary: momentary
        }
        // disable this control if needed
        options.setEnabled(instance, portSymbol, false, feedback, true, momentary)
    }

    this.addCvMapping = function (instance, portSymbol, actuator_uri,
                                        label, minimum, maximum, operationalMode, feedback) {
        var instanceAndSymbol = instance+"/"+portSymbol

        self.addressingsByActuator  [actuator_uri].push(instanceAndSymbol)
        self.addressingsByPortSymbol[instanceAndSymbol] = actuator_uri
        self.addressingsData        [instanceAndSymbol] = {
            uri     : actuator_uri,
            label   : label,
            minimum : minimum,
            maximum : maximum,
            feedback: feedback,
            operationalMode: operationalMode,
        }
        // disable this control
        options.setEnabled(instance, portSymbol, false, feedback, true)
    }


    this.addMidiMapping = function (instance, portSymbol, channel, control, minimum, maximum) {
        var instanceAndSymbol = instance+"/"+portSymbol
        var actuator_uri = create_midi_cc_uri(channel, control)

        if (self.addressingsByPortSymbol[instanceAndSymbol] == kMidiLearnURI) {
            var controlstr = (control == MIDI_PITCHBEND_AS_CC) ? "Pitchbend" : ("Controller #" + control)
            new Notification('info', "Parameter mapped to MIDI " + controlstr + ", Channel " + (channel+1), 8000)
        }

        self.addressingsByActuator  [kMidiLearnURI].push(instanceAndSymbol)
        self.addressingsByPortSymbol[instanceAndSymbol] = actuator_uri
        self.addressingsData        [instanceAndSymbol] = {
            uri     : actuator_uri,
            label   : null,
            minimum : minimum,
            maximum : maximum,
            steps   : null,
            feedback: true,
        }

        // disable this control
        options.setEnabled(instance, portSymbol, false, true, true)
    }

    this.addActuator = function (actuator) {
        HARDWARE_PROFILE.push(actuator)
        self.addressingsByActuator[actuator.uri] = []
    }

    this.hasControlChainDevice = function (actuator) {
        for (var i in HARDWARE_PROFILE) {
            if (is_control_chain_uri(HARDWARE_PROFILE[i].uri)) {
                return true;
            }
        }
        return false;
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

        delete self.addressingsByPortSymbol[instanceAndSymbol]
        delete self.addressingsData        [instanceAndSymbol]

        if (actuator_uri && actuator_uri != kNullAddressURI) {
            remove_from_array(self.addressingsByActuator[actuator_uri], instanceAndSymbol)
            return true
        }

        return false
    }

    this.addCvOutputPort = function (uri, name, operationalMode) {
      var existingPort = self.cvOutputPorts.find(function (port) {
        return port.uri === uri;
      })
      if (existingPort) {
        existingPort.name = name
      } else {
        self.cvOutputPorts.push({
          uri: uri,
          name: name,
          modes: cvModes,
          steps: [],
          max_assigns: 99,
          feedback: false,
          defaultOperationalMode: operationalMode,
        })
        self.addressingsByActuator[uri] = []
      }
    }

    this.removeCvOutputPort = function (uri) {
      var isAddressable = false
      self.cvOutputPorts = self.cvOutputPorts.filter(function (port) {
        if (port.uri === uri) {
          isAddressable = true
        }
        return port.uri !== uri
      });

      if (!isAddressable) {
        return
      }

      for (var i in self.addressingsByActuator[uri]) {
        instanceAndSymbol = self.addressingsByActuator[uri][i]
        delete self.addressingsData[instanceAndSymbol]
        delete self.addressingsByPortSymbol[instanceAndSymbol]

        var separatedInstanceAndSymbol = getInstanceSymbol(instanceAndSymbol)
        options.setEnabled(separatedInstanceAndSymbol[0], separatedInstanceAndSymbol[1], true)
      }

      delete self.addressingsByActuator[uri]
    }
}
