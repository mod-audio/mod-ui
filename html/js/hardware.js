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

// use pitchbend as midi cc, with an invalid MIDI controller number
var MIDI_PITCHBEND_AS_CC = 131

function create_midi_cc_uri (channel, controller) {
    if (controller == MIDI_PITCHBEND_AS_CC) {
        return sprintf("%sCh.%d_Pbend", kMidiCustomPrefixURI, channel+1)
    }
    return sprintf("%sCh.%d_CC#%d", kMidiCustomPrefixURI, channel+1, controller)
}

function startsWith (value, pattern) {
    return value.lastIndexOf(pattern) === 0;
};

function is_control_chain_uri (uri) {
  if (startsWith(uri, deviceOption)) {
    return false;
  }
  if (uri == kMidiLearnURI || startsWith(uri, kMidiCustomPrefixURI)) {
    return false;
  }
  return true;
}

// Units supported for tap tempo (lowercase)
var kTapTempoUnits = ['ms','s','hz','bpm']

function HardwareManager(options) {
    var self = this

    options = $.extend({
        // This is the function that will actually make the addressing
        address: function (instanceAndSymbol, addressing, callback) { callback(true) },

        // Callback to enable or disable a control in GUI
        setEnabled: function (instance, portSymbol, enabled, feedback) {},

        // Renders the address html template
        renderForm: function (instance, port) {},

    }, options)

    this.beatsPerMinutePort = {
      ranges: { // XXX would be good to have a centralized place for this data, currently it's also in transport.js and others
          minimum: 20.0,
          maximum: 280.0
      },
      value: null
    }

    this.setBeatsPerMinuteValue = function (bpm) {
      if (self.beatsPerMinutePort.value === bpm) {
          return
      }
      self.beatsPerMinutePort.value = bpm
    }

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
        self.addressingsByActuator[kBpmURI] = []
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
            var actuator, modes
            for (var i in HARDWARE_PROFILE) {
                actuator = HARDWARE_PROFILE[i]
                modes    = actuator.modes

                // usedAddressings = self.addressingsByActuator[actuator.uri]
                // if (!PAGES_CB && usedAddressings.length >= actuator.max_assigns && usedAddressings.indexOf(key) < 0) {
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

    this.disableMinMaxSteps = function (form, disabled) {
      form.find('select[name=steps]').prop('disabled', disabled)
      form.find('input[name=min]').prop('disabled', disabled)
      form.find('input[name=max]').prop('disabled', disabled)
    }

    this.toggleSensibility = function (port, select, actuators, actuatorUri) {
      var currentActuator = actuators[actuatorUri]
      if (currentActuator && currentActuator.steps.length === 0) {
        select.parent().parent().hide()
      } else if (!((port.properties.indexOf("integer") >= 0 || port.properties.indexOf("toggled") >= 0 || port.properties.indexOf("trigger") >= 0)
        && port.symbol != ":bypass" && port.symbol != ":presets")) {
        select.parent().parent().show()
      }
    }

    // Show dynamic field content based on selected type of addressing
    this.showDynamicField = function (form, typeInputVal, currentAddressing, port) {
      // Hide all then show the relevant content
      form.find('.dynamic-field').hide()
      if (typeInputVal === kMidiLearnURI) {
        form.find('.midi-learn-hint').show()
        if (currentAddressing && currentAddressing.uri && currentAddressing.uri.lastIndexOf(kMidiCustomPrefixURI, 0) === 0) {
          form.find('.midi-learn-hint').hide()
          var midiCustomLabel = "MIDI " + currentAddressing.uri.replace(kMidiCustomPrefixURI,"").replace(/_/g," ")
          form.find('.midi-custom-uri').text(midiCustomLabel)
          form.find('.midi-learn-custom').show()
        }
      } else if (typeInputVal === deviceOption) {
        form.find('.device-table').show()
      } else if (typeInputVal === ccOption) {
        var ccActuatorSelect = form.find('select[name=cc-actuator]')
        if (ccActuatorSelect.children('option').length) {
          form.find('.cc-select').show()
        } else if (self.hasControlChainDevice()) {
          form.find('.cc-in-use').show()
        } else {
          form.find('.no-cc').show()
        }
      }

      // Hide/show extended specific content
      if (typeInputVal == kMidiLearnURI || typeInputVal.lastIndexOf(kMidiCustomPrefixURI, 0) === 0) {
        form.find('.sensibility').css({visibility:"hidden"})
        self.disableMinMaxSteps(form, false)
      } else {
        form.find('.sensibility').css({visibility:"visible"})
      }

      if (typeInputVal == kMidiLearnURI || typeInputVal.lastIndexOf(kMidiCustomPrefixURI, 0) === 0 || typeInputVal == ccOption) {
        form.find('.tempo').css({display:"none"})
      } else if (hasTempoRelatedDynamicScalePoints(port)) {
        form.find('.tempo').css({display:"block"})
        if (form.find('input[name=tempo]').prop("checked")) {
          self.disableMinMaxSteps(form, true)
        }
      }
    }

    this.buildDeviceTable = function (deviceTable, currentAddressing, actuators, hmiPageInput, hmiUriInput, sensibility, port) {
      var table = $('<table/>').addClass('hmi-table')
      var groupTable = $('<table/>').addClass('hmi-table')
      var row, cell, uri, uriAddressings, usedAddressings, addressing, groupActuator, groupAddressings
      if (PAGES_CB && PAGES_NB > 0) {
        // build header row
        var headerRow = $('<tr/>')
        for (var i = 1; i <= PAGES_NB; i++) {
          headerRow.append($('<th>Page '+i+'</th>'))
        }
        table.append(headerRow)

        for (var actuatorUri in actuators) {
          row = $('<tr/>')
          usedAddressings = self.addressingsByActuator[actuatorUri]
          for (var page = 0; page < PAGES_NB; page++) {
            if (startsWith(actuatorUri, deviceOption)) {
              cell = $('<td data-page="'+ page +'" data-uri="'+ actuatorUri +'">'+ actuators[actuatorUri].name+'</td>')
              if (currentAddressing && currentAddressing.uri == actuatorUri && currentAddressing.page == page) {
                hmiPageInput.val(currentAddressing.page)
                hmiUriInput.val(currentAddressing.uri)
                cell.addClass('selected')
              } else {
                // Only allow actuator groups to be used when all their “child” actuators are not in use on current page
                if (actuators[actuatorUri].group) {
                  for (var i = 0; i < actuators[actuatorUri].group.length; i++) {
                    uri = actuators[actuatorUri].group[i]
                    uriAddressings = self.addressingsByActuator[uri]
                    for (var j in uriAddressings) {
                      instance = uriAddressings[j]
                      addressing = self.addressingsData[instance]
                      if (addressing.page == page) {
                        cell.addClass('disabled')
                      }
                    }
                  }
                }
                // Check if page+uri already assigned, then disable cell
                for (var i in usedAddressings) {
                  instance = usedAddressings[i]
                  addressing = self.addressingsData[instance]
                  if (addressing.page == page) {
                    cell.addClass('disabled')
                  }
                }

              }
              row.append(cell)
            }
          }

          if (actuators[actuatorUri].group) {
            groupTable.append(row)
          } else {
            table.append(row)
          }
        }

        // when addressing an actuator group, all “child” actuators are no longer available to be addressed to anything else,
        // except on different pages
        // TODO remove
        for (var i in HARDWARE_PROFILE) {
          if (HARDWARE_PROFILE[i].group) {
            groupActuator = HARDWARE_PROFILE[i]
            for (var j in self.addressingsByActuator[groupActuator.uri]) {
              instance = self.addressingsByActuator[groupActuator.uri][j]
              groupAddressings = self.addressingsData[instance]
              for (var k in groupActuator.group) {
                table.find('[data-uri="' + groupActuator.group[k] + '"][data-page="' + groupAddressings.page + '"]').addClass('disabled')
              }
            }
          }
        }
      } else {
        for (var actuatorUri in actuators) {
          row = $('<tr/>')
          usedAddressings = self.addressingsByActuator[actuatorUri]
          if (startsWith(actuatorUri, deviceOption)) {
            cell = $('<td data-uri="'+ actuatorUri +'">'+ actuators[actuatorUri].name+'</td>')
            if (currentAddressing && currentAddressing.uri == actuatorUri) {
              hmiUriInput.val(currentAddressing.uri)
              cell.addClass('selected')
            } else {
              // Only allow actuator groups to be used when all their “child” actuators are not in use
              if (actuators[actuatorUri].group) {
                for (i = 0; i < actuators[actuatorUri].group.length; i++) {
                  uri = actuators[actuatorUri].group[i]
                  uriAddressings = self.addressingsByActuator[uri]
                  if (uriAddressings.length) {
                    cell.addClass('disabled')
                  }
                }
              }
              if (usedAddressings.length >= actuators[actuatorUri].max_assigns) {
                cell.addClass('disabled')
              }
            }

            row.append(cell)
          }
          if (actuators[actuatorUri].group) {
            groupTable.append(row)
          } else {
            table.append(row)
          }
        }

        // when addressing an actuator group, all “child” actuators are no longer available to be addressed to anything else
        // TODO remove
        for (var i in HARDWARE_PROFILE) {
          if (HARDWARE_PROFILE[i].group) {
            groupActuator = HARDWARE_PROFILE[i]
            if (self.addressingsByActuator[groupActuator.uri].length) {
              for (var j in groupActuator.group) {
                table.find('[data-uri="' + groupActuator.group[j] + '"]').addClass('disabled')
              }
            }
          }
        }
      }

      deviceTable.append(table)
      if (groupTable.children().length) {
        deviceTable.append($('<div class="group-strike">Group</div>'))
        deviceTable.append(groupTable)
      }

      deviceTable.find('td').click(function () {
        if ($(this).hasClass('disabled')) {
          return
        }
        var actuatorUri = $(this).attr('data-uri')
        var page = $(this).attr('data-page')

        // Update hidden inputs value
        hmiPageInput.val(page)
        hmiUriInput.val(actuatorUri)

        // Remove 'selected' class to all cells then add it to the clicked one
        deviceTable.find('td').removeClass('selected')
        $(this).addClass('selected')

        if (actuatorUri) {
         self.toggleSensibility(port, sensibility, actuators, actuatorUri)
       }
      })
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
        var hmiUriInput = form.find('input[name=hmi-uri]')

        // Create selectable buttons to choose addressings type and show relevant dynamic content
        var typeInputVal = kNullAddressURI
        if (currentAddressing && currentAddressing.uri) {
          if (currentAddressing.uri == kMidiLearnURI || currentAddressing.uri.lastIndexOf(kMidiCustomPrefixURI, 0) === 0) {
            typeInputVal = kMidiLearnURI
          } else if (startsWith(currentAddressing.uri, deviceOption)) {
            typeInputVal = deviceOption
          } else if (currentAddressing.uri !== kBpmURI){
            typeInputVal = ccOption
          }
        }
        typeInput.val(typeInputVal)

        var actuators = self.availableActuators(instance, port)
        var typeOptions = [kNullAddressURI, deviceOption, kMidiLearnURI, ccOption]
        var i = 0
        typeSelect.find('option').unwrap().each(function() {
            var btn = $('<div class="btn js-type" data-value="'+typeOptions[i]+'">'+$(this).text()+'</div>')
            if($(btn).attr('data-value') == typeInput.val()) {
              btn.addClass('selected')
            }
            if ($(btn).attr('data-value') === kMidiLearnURI && !actuators[kMidiLearnURI]) {
              $(btn).hide()
            }
            $(this).replaceWith(btn)
            i++
        })

        // Add options to control chain actuators select
        var actuator, addressings, addressedToMe
        var ccActuatorSelect = form.find('select[name=cc-actuator]')
        var ccActuators = []
        for (var uri in actuators) {
          if (! is_control_chain_uri(uri)) {
            continue
          }
          actuator = actuators[uri]
          addressings = self.addressingsByActuator[uri]
          addressedToMe = currentAddressing.uri && currentAddressing.uri === actuator.uri
          ccActuators.push(actuator)
          if (addressings.length < actuator.max_assigns || addressedToMe) {
            $('<option>').attr('value', actuator.uri).text(actuator.name).appendTo(ccActuatorSelect)
            if (addressedToMe) {
              ccActuatorSelect.val(currentAddressing.uri)
            }
          }
        }
        if (ccActuators.length === 0) {
          ccActuatorSelect.hide()
        }

        form.find('.js-type').click(function () {
          form.find('.js-type').removeClass('selected')
          $(this).addClass('selected')
          typeInput.val($(this).attr('data-value'))
          self.showDynamicField(form, typeInput.val(), currentAddressing, port)
        })

        self.showDynamicField(form, typeInputVal, currentAddressing, port)

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
            if(this.checked) {
              self.disableMinMaxSteps(form, true)
            } else {
              self.disableMinMaxSteps(form, false)
            }
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
            // hide ranges
            form.find('.range').hide()

        } else if (port.properties.indexOf("integer") < 0) {
            // float, allow non-integer stepping
            var step = (maxv-minv)/100
            min.attr("step", step)
            max.attr("step", step)

            // Hide sensibility and tempo options for MIDI
            var act = typeInput.val()
            if (act == kMidiLearnURI || act.lastIndexOf(kMidiCustomPrefixURI, 0) === 0) {
                form.find('.sensibility').css({visibility:"hidden"})
                form.find('.tempo').css({display:"none"})
            }
            // Hide tempo option for CC
            if (act === ccOption) {
              form.find('.tempo').css({display:"none"})
            }
        }

        var sensibility = form.find('select[name=steps]')
        self.buildSensibilityOptions(sensibility, port, currentAddressing.steps)

        var deviceTable = form.find('.device-table')
        self.buildDeviceTable(deviceTable, currentAddressing, actuators, hmiPageInput, hmiUriInput, sensibility, port)

        // Hide sensibility if current addressing actuator does not support it
        if (currentAddressing && currentAddressing['uri']) {
          self.toggleSensibility(port, sensibility, actuators, currentAddressing['uri'])
        }

        form.find('.js-save').click(function () {
            self.saveAddressing(instance, port, actuators, typeInput, hmiPageInput, hmiUriInput, ccActuatorSelect, min, max, label, pname, sensibility, tempo, divider, dividerOptions, form)
        })

        form.find('.js-close').click(function () {
            form.remove()
            form = null
        })

        form.find('.advanced-toggle').click(function() {
            if (!form.find('.advanced-container').is(':visible')) {
              $('.mod-pedal-settings-address').find('.mod-box').animate({
                width: '640px'
              }, 100, function() {
                form.find('.advanced-container').toggle()
              });
            } else {
              form.find('.advanced-container').toggle(0, function() {
                $('.mod-pedal-settings-address').find('.mod-box').animate({
                  width: '450px'
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
                self.saveAddressing(instance, port, actuators, typeInput, hmiPageInput, hmiUriInput, ccActuatorSelect, min, max, label, pname, sensibility, tempo, divider, dividerOptions, form)
                return false
            }
        })

        form.appendTo($('body'))
        form.focus()
    }

    this.addressNow = function (instance, port, actuator, minv, maxv, labelValue, sensibilityValue, tempoValue, dividerValue, dividerOptions, page, form) {
        var instanceAndSymbol = instance+"/"+port.symbol;
        var currentAddressing = self.addressingsData[instanceAndSymbol] || {}

        var portValuesWithDividerLabels = []
        // Sync port value to bpm
        if (tempoValue && dividerValue && port.units && port.units.symbol) {
          if (port.units.symbol === 'BPM') {
            port.value = getPortValue(self.beatsPerMinutePort.value, dividerValue, port.units.symbol) // no need for conversion
          } else {
            port.value = convertSecondsToPortValueEquivalent(getPortValue(self.beatsPerMinutePort.value, dividerValue, port.units.symbol), port.units.symbol);
          }
        }

        var addressing = {
            uri    : actuator.uri || kNullAddressURI,
            label  : labelValue,
            minimum: minv,
            maximum: maxv,
            value  : port.value,
            steps  : sensibilityValue,
            tempo  : tempoValue,
            dividers: dividerValue,
            feedback: actuator.feedback === false ? false : true, // backwards compatible, true by default
            page: page || null,
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

                // now save
                self.addressingsByPortSymbol[instanceAndSymbol] = actuator.uri
                self.addressingsData        [instanceAndSymbol] = addressing

                // disable this control
                var feedback = actuator.feedback === false ? false : true // backwards compat, true by default
                options.setEnabled(instance, port.symbol, false, feedback, true)
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

    this.saveAddressing = function (instance, port, actuators, typeInput, hmiPageInput, hmiUriInput, ccActuatorSelect, min, max, label, pname, sensibility, tempo, divider, dividerOptions, form) {
        var instanceAndSymbol = instance+"/"+port.symbol
        var currentAddressing = self.addressingsData[instanceAndSymbol] || {}

        var page = hmiPageInput.val()
        var typeInputVal = typeInput.val()
        var uri = kNullAddressURI
        if (typeInputVal === deviceOption && hmiUriInput.val()) {
          uri = hmiUriInput.val()
        } else if(typeInputVal === ccOption && ccActuatorSelect.val()) {
          uri = ccActuatorSelect.val()
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
        var sensibilityValue = sensibility.val()
        var dividerValue = divider.val() ? parseFloat(divider.val()): divider.val()

        // if changing from midi-learn, unlearn first
        if (currentAddressing.uri == kMidiLearnURI) {
            var addressing = {
                uri    : kMidiUnlearnURI,
                label  : labelValue,
                minimum: minv,
                maximum: maxv,
                value  : port.value,
                steps  : sensibilityValue,
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
                    self.addressNow(instance, port, actuator, minv, maxv, labelValue, sensibilityValue, tempoValue, dividerValue, dividerOptions, page, form)
                // if not, just close the form
                } else if (form !== undefined) {
                    form.remove()
                    form = null
                }
            })
        }
        // otherwise just address it now
        else {
            self.addressNow(instance, port, actuator, minv, maxv, labelValue, sensibilityValue, tempoValue, dividerValue, dividerOptions, page, form)
        }
    }

    this.addHardwareMapping = function (instance, portSymbol, actuator_uri,
                                        label, minimum, maximum, steps,
                                        tempo, dividers, page, group, feedback) {
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
            group   : group
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
        options.setEnabled(instance, portSymbol, false, true)
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
}
