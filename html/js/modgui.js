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

var loadedIcons = {}
var loadedSettings = {}
var loadedCSSs = {}
var loadedJSs = {}
var isSDK = false

function shouldSkipPort(port) {
    // skip notOnGUI controls
    if (port.properties.indexOf("notOnGUI") >= 0)
        return true
    // skip special designated controls
    if (port.designation == "http://lv2plug.in/ns/lv2core#enabled" ||
        port.designation == "http://lv2plug.in/ns/lv2core#freeWheeling" ||
        port.designation == "http://lv2plug.in/ns/ext/time#beatsPerBar" ||
        port.designation == "http://lv2plug.in/ns/ext/time#beatsPerMinute" ||
        port.designation == "http://lv2plug.in/ns/ext/time#speed") {
        return true
    }
    // what else?
    return false;
}

function loadDependencies(gui, effect, callback) { //source, effect, bundle, callback) {
    var iconLoaded = true
    var settingsLoaded = true
    var cssLoaded = true
    var jsLoaded = true
    var nonCachedInfoLoaded = true

    var cb = function () {
        if (iconLoaded && settingsLoaded && cssLoaded && jsLoaded && nonCachedInfoLoaded) {
            setTimeout(callback, 0)
        }
    }

    var baseUrl = ''
    if (effect.source) {
        baseUrl += effect.source
        baseUrl.replace(/\/?$/, '')
    }

    var version    = [effect.builder, effect.microVersion, effect.minorVersion, effect.release].join('_')
    var escapeduri = escape(effect.uri)
    var plughash   = escapeduri + version

    if (! isSDK) {
        nonCachedInfoLoaded = false
        $.ajax({
            url: '/effect/get_non_cached',
            data: {
                uri: effect.uri
            },
            success: function (data) {
                effect.licensed = data.licensed
                effect.presets = data.presets
                nonCachedInfoLoaded = true
                cb()
            },
            error: function () {
                nonCachedInfoLoaded = true
                cb()
            },
            cache: false,
            dataType: 'json'
        })
    }

    if (effect.gui.iconTemplate) {
        if (loadedIcons[plughash]) {
            effect.gui.iconTemplate = loadedIcons[plughash]
        } else {
            iconLoaded = false
            var iconUrl = baseUrl + '/effect/file/iconTemplate?uri='+escapeduri+'&v='+version+'&r='+VERSION
            $.get(iconUrl, function (data) {
                effect.gui.iconTemplate = loadedIcons[plughash] = data
                iconLoaded = true
                cb()
            })
        }
    }

    if (effect.gui.settingsTemplate) {
        if (loadedSettings[plughash]) {
            effect.gui.settingsTemplate = loadedSettings[plughash]
        } else {
            settingsLoaded = false
            var settingsUrl = baseUrl + '/effect/file/settingsTemplate?uri='+escapeduri+'&v='+version+'&r='+VERSION
            $.get(settingsUrl, function (data) {
                effect.gui.settingsTemplate = loadedSettings[plughash] = data
                settingsLoaded = true
                cb()
            })
        }
    }

    if (effect.gui.stylesheet && !loadedCSSs[plughash]) {
        cssLoaded = false
        var cssUrl = baseUrl + '/effect/file/stylesheet?uri='+escapeduri+'&v='+version+'&r='+VERSION
        $.get(cssUrl, function (data) {
              data = Mustache.render(data, {
                         ns : '?uri=' + escapeduri + '&v=' + version,
                         cns: '_' + escapeduri.split("/").join("_").split("%").join("_").split(".").join("_") + version
                     })
            $('<style type="text/css">').text(data).appendTo($('head'))
            loadedCSSs[plughash] = true
            cssLoaded = true
            cb()
        })
    }

    if (effect.gui.javascript) {
        if (loadedJSs[plughash]) {
            gui.jsCallback = loadedJSs[plughash]
        } else {
            jsLoaded = false
            var jsUrl = baseUrl+'/effect/file/javascript?uri='+escapeduri+'&v='+version+'&r='+VERSION
            $.ajax({
                url: jsUrl,
                success: function (code) {
                    var method;
                    try {
                        eval('method = ' + code)
                    } catch (err) {
                        method = null
                        console.log("Failed to evaluate javascript for '"+effect.uri+"' plugin")
                    }
                    loadedJSs[plughash] = method
                    gui.jsCallback = method
                    jsLoaded = true
                    cb()
                },
                error: function () {
                    jsLoaded = true
                    cb()
                },
            })
        }
    }

    cb()
}

function GUI(effect, options) {
    var self = this

    options = $.extend({
        change: function(symbol, value) {
            console.log("PARAM CHANGE =>", symbol, value)
        },
        click: function (event) {
        },
        dragStart: function () {
            return true
        },
        drag: function (e, ui) {
        },
        dragStop: function (e, ui) {
        },
        presetLoad: function (uri) {
        },
        presetSaveNew: function (name, callback) {
            callback({ok:false})
        },
        presetSaveReplace: function (uri, bundlepath, name, callback) {
            callback({ok:false})
        },
        presetDelete: function (uri, bundlepath, callback) {
            callback()
        },
        bypassed: true,
        defaultIconTemplate: 'Template missing',
        defaultSettingsTemplate: 'Template missing',
        loadDependencies: true,
    }, options)

    if (!effect.gui)
        effect.gui = {}

    self.dependenciesCallbacks = []

    if (options.loadDependencies) {
        self.dependenciesLoaded = false

        loadDependencies(this, effect, function () {
            self.dependenciesLoaded = true
            for (var i in self.dependenciesCallbacks) {
                self.dependenciesCallbacks[i]()
            }
            self.dependenciesCallbacks = []
        })
    } else {
        self.dependenciesLoaded = true
    }

    self.effect = effect
    self.instance = null

    self.bypassed = options.bypassed
    self.currentPreset = ""

    this.makePortIndexes = function (ports) {
        var i, port, porti, indexes = {}

        for (i in ports) {
            porti = ports[i]

            port = {
                enabled: true,
                widgets: [],
                format: null,
                scalePointsIndex: null,
                valueFields: [],
            }
            $.extend(port, porti)

            // just in case
            if (port.ranges.default === undefined)
                port.ranges.default = port.ranges.minimum

            // adjust for sample rate
            if (port.properties.indexOf("sampleRate") >= 0) {
                port.ranges.minimum *= SAMPLERATE
                port.ranges.maximum *= SAMPLERATE
            }

            // set initial value
            port.value = port.ranges.default

            // ready
            indexes[port.symbol] = port
        }

        return indexes
    }

    self.controls = self.makePortIndexes(effect.ports.control.input)

    // Bypass needs to be represented as a port since it shares the hardware addressing
    // structure with ports. We use the symbol ':bypass' that is an invalid lv2 symbol and
    // so will cause no conflict
    // Be aware that this is being acessed directly in pedalboard.js
    self.controls[':bypass'] = {
        name: 'Bypass',
        symbol: ':bypass',
        ranges: {
            minimum: 0,
            maximum: 1,
            default: 1,
        },
        comment: "",
        designation: "",
        properties: ["toggled", "integer"],
        widgets: [],
        enabled: true,
        value: self.bypassed ? 1 : 0,
        format: null,
        scalePoints: [],
        scalePointsIndex: null,
        valueFields: [],

        // FIXME: limits of mustache
        default: 1,
        maximum: 1,
        minimum: 0,
        enumeration: false,
        integer: true,
        logarithmic: false,
        toggled: true,
        trigger: false,
    }

    // The same with bypass applies to presets, as ':presets' symbol
    self.controls[':presets'] = {
        name: 'Presets',
        symbol: ':presets',
        ranges: {
            minimum: -1,
            maximum: 0,
            default: -1,
        },
        comment: "",
        designation: "",
        properties: ["enumeration", "integer"],
        widgets: [],
        enabled: true,
        value: -1,
        format: null,
        scalePoints: [],
        scalePointsIndex: null,
        valueFields: []
    }

    this.setPortValue = function (symbol, value, source) {
        if (isNaN(value)) {
            throw "Invalid NaN value for " + symbol
        }
        var port = self.controls[symbol]
        var mod_port = source ? source.attr("mod-port") : (self.instance ? self.instance+'/'+symbol : symbol)
        if (!port.enabled || port.value == value)
            return

        if (value < port.ranges.minimum) {
            value = port.ranges.minimum
            console.log("WARNING: setPortValue called with < min value, symbol:", symbol)
        } else if (value > port.ranges.maximum) {
            value = port.ranges.maximum
            console.log("WARNING: setPortValue called with > max value, symbol:", symbol)
        }

        // update our own widgets
        self.setPortWidgetsValue(symbol, value, source, false)

        // let the host know about this change
        options.change(mod_port, value)

        // let the HMI know about this change
        paramchange = (self.instance + '/' + symbol + '/' + value)
        desktop.ParameterSet(paramchange)
    }

    this.setPortWidgetsValue = function (symbol, value, source, only_gui) {
        var label, valueField, widget,
            port = self.controls[symbol]

        port.value = value

        for (var i in port.widgets) {
            widget = port.widgets[i]
            if (source == null || widget != source) {
                widget.controlWidget('setValue', value, only_gui)
            }
        }

        for (var i in port.valueFields) {
            label = sprintf(port.format, value)
            if (port.scalePointsIndex && port.scalePointsIndex[label]) {
                label = port.scalePointsIndex[label].label
            }

            valueField = port.valueFields[i]
            valueField.data('value', value)
            valueField.text(label)
        }

        self.triggerJS({ type: 'change', symbol: symbol, value: value })

        // If trigger, switch back to default value after a few miliseconds
        // Careful not to actually send the change to the host, it's not needed
        if (port.properties.indexOf("trigger") >= 0 && value != port.ranges.default) {
            setTimeout(function () {
                self.setPortWidgetsValue(symbol, port.ranges.default, null, false)

                // When running SDK there's no host, so simulate trigger here.
                if (isSDK) options.change(mod_port, port.ranges.default);
            }, 200)
        }
    }

    this.setOutputPortValue = function (symbol, value) {
        self.triggerJS({ type: 'change', symbol: symbol, value: value })
    }

    this.getPortValue = function (symbol) {
        return self.controls[symbol].value
    }

    this.selectPreset = function (value) {
        self.currentPreset = value

        var bundlepath,
            presetElem,
            presetElems = [
            self.icon.find('[mod-role=presets]'),
            self.settings.find('.mod-presets')
        ]
        for (var i in presetElems) {
            presetElem = presetElems[i]
            presetElem.find('[mod-role=enumeration-option]').removeClass("selected")
            if (value) {
                bundlepath = presetElem.find('[mod-role=enumeration-option][mod-uri="' + value + '"]').addClass("selected").attr('mod-path')
            }
        }

        if (value) {
            // TODO: implement addressing for single presets
            //presetElem.find('.preset-btn-assign-sel').removeClass("disabled")

            if (bundlepath) {
                presetElem.find('.preset-btn-save').removeClass("disabled")
            } else {
                presetElem.find('.preset-btn-save').addClass("disabled")
            }

            if (bundlepath && presetElem.data('enabled')) {
                presetElem.find('.preset-btn-rename').removeClass("disabled")
                presetElem.find('.preset-btn-delete').removeClass("disabled")
            } else {
                presetElem.find('.preset-btn-rename').addClass("disabled")
                presetElem.find('.preset-btn-delete').addClass("disabled")
            }
        } else {
            presetElem.find('.preset-btn-save').addClass("disabled")
            presetElem.find('.preset-btn-rename').addClass("disabled")
            presetElem.find('.preset-btn-delete').addClass("disabled")
            presetElem.find('.preset-btn-assign-sel').addClass("disabled")
        }
    }

    this.addressPort = function (symbol, feedback) {
      var port = self.controls[symbol]
      if (symbol !== ":presets") {
        // add "addressed" class to all related widgets
        if (symbol == ":bypass") {
          self.settings.find('.mod-address[mod-role="bypass-address"]').addClass('addressed')
        } else {
          self.settings.find('.mod-address[mod-port-symbol="'+symbol+'"]').addClass('addressed')
        }
        // allow feedback when interacting with widget
        if (feedback) {
          for (var i in port.widgets) {
              port.widgets[i].controlWidget('address')
          }
        }
      } else {
        self.settings.find('[mod-role=presets-address]').addClass('addressed')
      }
    }

    this.disable = function (symbol) {
        var port = self.controls[symbol]
        port.enabled = false

        if (symbol == ":presets") {
            self.icon.find('[mod-role=presets]').controlWidget('disable')
            var presetElem = self.settings.find('.mod-presets')
            presetElem.data('enabled', false)
            presetElem.find('.preset-btn-rename').addClass("disabled")
            presetElem.find('.preset-btn-delete').addClass("disabled")
        } else {
            // disable all related widgets
            for (var i in port.widgets) {
                port.widgets[i].controlWidget('disable')
            }

            // disable value fields if needed
            if (port.properties.indexOf("enumeration") < 0 &&
                port.properties.indexOf("toggled") < 0 &&
                port.properties.indexOf("trigger") < 0)
            {
                for (var i in port.valueFields) {
                    port.valueFields[i].attr('contenteditable', false)
                }
            }
        }
    }

    this.enable = function (symbol) {
        var port = self.controls[symbol]
        port.enabled = true

        if (symbol == ":presets") {
            self.icon.find('[mod-role=presets]').controlWidget('enable')
            self.settings.find('.mod-presets').data('enabled', true)
            self.settings.find('[mod-role=presets-address]').removeClass('addressed')
            self.selectPreset(self.currentPreset)
        } else {
            if (symbol == ":bypass") {
              self.settings.find('.mod-address[mod-role="bypass-address"]').removeClass('addressed')
            } else {
              self.settings.find('.mod-address[mod-port-symbol="'+symbol+'"]').removeClass('addressed')
            }
            // enable all related widgets
            for (var i in port.widgets) {
                port.widgets[i].controlWidget('enable')
            }

            // enable value fields if needed
            if (port.properties.indexOf("enumeration") < 0 &&
                port.properties.indexOf("toggled") < 0 &&
                port.properties.indexOf("trigger") < 0)
            {
                for (var i in port.valueFields) {
                    port.valueFields[i].attr('contenteditable', true)
                }
            }
        }
    }

    this.render = function (instance, callback, skipNamespace) {
        self.instance = instance

        var render = function () {
            if (instance) {
                self.icon = $('<div mod-instance="' + instance + '" class="mod-pedal">')
            } else {
                self.icon = $('<div class="mod-pedal">')
            }

            var templateData = self.getTemplateData(effect, skipNamespace)
            self.icon.html(Mustache.render(effect.gui.iconTemplate || options.defaultIconTemplate, templateData))

            // Check for old broken icons
            var children = self.icon.children()
            if (children.hasClass("mod-pedal-boxy")      ||
                children.hasClass("mod-pedal-british")   ||
                children.hasClass("mod-pedal-japanese")  ||
                children.hasClass("mod-pedal-lata")      ||
                children.hasClass("mod-combo-model-001") ||
                children.hasClass("mod-head-model-001")  ||
                children.hasClass("mod-rack-model-001"))
            {
                console.log("This icon uses old MOD reserved css classes, this is not allowed anymore")
                self.icon.html(Mustache.render(options.defaultIconTemplate, templateData))
            }

            self.assignIconFunctionality(self.icon)
            self.assignControlFunctionality(self.icon, false)

            self.icon.find('[mod-role=presets]').change(function () {
                var value = $(this).val()
                options.presetLoad(value)
            })

            if (instance) {
                self.settings = $('<div class="mod-settings" mod-instance="' + instance + '">')
            } else {
                self.settings = $('<div class="mod-settings">')
            }

            // split presets, factory vs user
            var preset, presets = {
                factory: [],
                user: []
            }
            for (var i in self.effect.presets) {
                preset = self.effect.presets[i]
                if (preset.path) {
                    presets.user.push(preset)
                } else {
                    presets.factory.push(preset)
                }
            }
            templateData.presets = presets
            var totalPresetCount = self.effect.presets.length

            self.settings.html(Mustache.render(effect.gui.settingsTemplate || options.defaultSettingsTemplate, templateData))

            self.assignControlFunctionality(self.settings, false)

            var presetElem = self.settings.find('.mod-presets')

            if (instance && (totalPresetCount > 0 || self.effect.ports.control.input.length > 0))
            {
                presetElem.data('enabled', true)

                var getCurrentPresetItem = function () {
                    if (! self.currentPreset) {
                        return null
                    }
                    var opt = presetElem.find('[mod-role=enumeration-option][mod-uri="' + self.currentPreset + '"]')
                    if (opt.length == 0) {
                        return null
                    }
                    return opt
                }

                var presetItemClicked = function (e) {
                    if (!presetElem.data('enabled'))
                        return presetElem.customSelect('prevent', e)

                    var value = $(this).attr('mod-uri')
                    options.presetLoad(value)
                }

                presetElem.find('.preset-btn-save').click(function () {
                    if ($(this).hasClass('disabled')) {
                        return
                    }
                    var item = getCurrentPresetItem()
                    if (! item) {
                        return
                    }
                    var name = item.text() || "Untitled",
                        path = item.attr('mod-path'),
                        uri  = item.attr('mod-uri')
                    if (! path || ! uri) {
                        return
                    }
                    options.presetSaveReplace(uri, path, name, function (resp) {
                    })
                })

                presetElem.find('.preset-btn-save-as').click(function () {
                    if (desktop == null) {
                        return
                    }
                    var name = "",
                        item = getCurrentPresetItem()
                    if (item) {
                        name = item.text()
                    }
                    desktop.openPresetSaveWindow(name, function (newName) {
                        options.presetSaveNew(newName, function (resp) {
                            var newItem = $('<div mod-role="enumeration-option" mod-uri="'+resp.uri+'" mod-path="'+resp.bundle+'">'+newName+'</div>')
                            newItem.appendTo(presetElem.find('.mod-preset-user')).click(presetItemClicked)

                            presetElem.find('.radio-preset-user').click()
                            presetElem.find('.preset-btn-assign-all').removeClass("disabled")

                            totalPresetCount += 1
                            self.selectPreset(resp.uri)
                        })
                    })
                })

                presetElem.find('.preset-btn-rename').click(function () {
                    if (desktop == null) {
                        return
                    }
                    if ($(this).hasClass('disabled') || ! presetElem.data('enabled')) {
                        return
                    }
                    var item = getCurrentPresetItem()
                    if (! item) {
                        return
                    }
                    var name = name = item.text(),
                        path = item.attr('mod-path'),
                        uri  = item.attr('mod-uri')
                    if (! path || ! uri) {
                        return
                    }
                    desktop.openPresetSaveWindow(name, function (newName) {
                        options.presetSaveReplace(uri, path, newName, function (resp) {
                            item.text(newName)
                        })
                    })
                })

                presetElem.find('.preset-btn-delete').click(function () {
                    if ($(this).hasClass('disabled') || ! presetElem.data('enabled')) {
                        return
                    }
                    var item = getCurrentPresetItem()
                    if (! item) {
                        return
                    }
                    var path = item.attr('mod-path')
                    if (! path) {
                        return
                    }
                    options.presetDelete(self.currentPreset, path, function () {
                        self.selectPreset("")
                        item.remove()

                        totalPresetCount -= 1

                        if (totalPresetCount == 1) {
                            presetElem.find('.preset-btn-assign-all').addClass("disabled")
                        }
                    })
                })

                presetElem.find('.radio-preset-factory').click(function () {
                    presetElem.find('.mod-preset-user').hide()
                    presetElem.find('.mod-preset-factory').show()
                })
                presetElem.find('.radio-preset-user').click(function () {
                    presetElem.find('.mod-preset-factory').hide()
                    presetElem.find('.mod-preset-user').show()
                })
                presetElem.find('[mod-role=enumeration-option]').each(function () {
                    $(this).click(presetItemClicked)
                })

                if (totalPresetCount == 1) {
                    presetElem.find('.preset-btn-assign-all').addClass("disabled")

                } else if (presets.factory.length == 0) {
                    presetElem.find('.mod-enumerated-title').find('span').hide()
                    presetElem.find('.mod-preset-factory').hide()
                    presetElem.find('.mod-preset-user').show()

                    if (presets.user.length == 0) {
                        presetElem.find('.preset-btn-assign-all').addClass("disabled")
                    }
                }
            }
            else
            {
                presetElem.hide()
            }

            if (! instance) {
                self.settings.find(".js-close").hide()
                self.settings.find(".mod-address").hide()
            }

            // adjust icon size after adding all basic elements
            setTimeout(function () {
                var width = children.width(),
                    height = children.height()

                if (width != 0 && height != 0) {
                    self.icon.width(width)
                    self.icon.height(height)
                    if (width < 150) {
                        self.icon.find('.mod-information').hide()
                    }
                }

                if (! instance) {
                    $('[mod-role="input-audio-port"]').addClass("mod-audio-input")
                    $('[mod-role="output-audio-port"]').addClass("mod-audio-output")
                    $('[mod-role="input-midi-port"]').addClass("mod-midi-input")
                    $('[mod-role="output-midi-port"]').addClass("mod-midi-output")
                    $('[mod-role="input-cv-port"]').addClass("mod-cv-input")
                    $('[mod-role="output-cv-port"]').addClass("mod-cv-output")
                }

                // listen for future resizes
                children.resize(function () {
                    width = children.width()
                    height = children.height()
                    if (width != 0 && height != 0) {
                        self.icon.width(width)
                        self.icon.height(height)
                        if (width < 150) {
                            self.icon.find('.mod-information').hide()
                        } else {
                            self.icon.find('.mod-information').show()
                        }
                    }
                })
            }, 1)

            // make list of ports to pass to javascript 'start' event
            var port, value, jsPorts = [{
                symbol: ":bypass",
                value : self.bypassed ? 1 : 0
            }]
            // inputs
            for (var i in self.effect.all_control_in_ports) {
                port = self.effect.all_control_in_ports[i]

                if (self.controls[port.symbol] != null) {
                    value = self.controls[port.symbol].value
                } else if (port.ranges.default !== undefined) {
                    value = port.ranges.default
                } else {
                    value = port.ranges.minimum
                }

                jsPorts.push({
                    symbol: port.symbol,
                    value : value
                })
            }
            // outputs
            for (var i in self.effect.ports.control.output) {
                port = self.effect.ports.control.output[i]

                if (port.ranges.default !== undefined) {
                    value = port.ranges.default
                } else {
                    value = port.ranges.minimum
                }

                jsPorts.push({
                    symbol: port.symbol,
                    value : value
                })
            }
            self.jsStarted = true
            self.triggerJS({ type: 'start', ports: jsPorts })

            callback(self.icon, self.settings)
        }

        if (self.dependenciesLoaded) {
            render()
        } else {
            self.dependenciesCallbacks.push(render)
        }
    }

    this.renderDummyIcon = function (callback) {
        var render = function () {
            var icon = $('<div class="mod-pedal dummy">')
            icon.html(Mustache.render(effect.gui.iconTemplate || options.defaultIconTemplate,
                      self.getTemplateData(effect, false)))
            self.assignControlFunctionality(icon, true)
            callback(icon)
        }
        if (self.dependenciesLoaded) {
            render()
        } else {
            self.dependenciesCallbacks.push(render)
        }
    }

    this.assignIconFunctionality = function (element) {
        var handle = element.find('[mod-role=drag-handle]')
        var drag_options = {
            handle: handle,
            start: options.dragStart,
            drag: options.drag,
            stop: options.dragStop
        }
        if (handle.length > 0) {
            element.draggable(drag_options)
            element.click(options.click)
        }
    }

    this.assignControlFunctionality = function (element, onlySetValues) {
        var instance = element.attr('mod-instance')

        element.find('[mod-role=input-control-port]').each(function () {
            var control = $(this)
            var symbol = $(this).attr('mod-port-symbol')
            var port = self.controls[symbol]

            if (port)
            {
                // Set the display formatting of this control
                if (port.units.render)
                    port.format = port.units.render.replace('%f', '%.2f')
                else
                    port.format = '%.2f'

                if (port.properties.indexOf("integer") >= 0) {
                    port.format = port.format.replace(/%\.\d+f/, '%d')
                }

                var valueField = element.find('[mod-role=input-control-value][mod-port-symbol=' + symbol + ']')
                port.valueFields.push(valueField)

                if (port.scalePoints && port.scalePoints.length > 0) {
                    port.scalePointsIndex = {}
                    for (var i in port.scalePoints) {
                        port.scalePointsIndex[sprintf(port.format, port.scalePoints[i].value)] = port.scalePoints[i]
                    }
                }

                if (port.properties.indexOf("expensive") >= 0) {
                    element.find('.mod-address[mod-port-symbol=' + symbol + ']').addClass('disabled').hide()
                }

                control.controlWidget({
                    dummy: onlySetValues,
                    port: port,
                    change: function (e, value) {
                        self.setPortValue(symbol, value, control)
                    }
                })

                if (valueField.length > 0 && port.properties.indexOf("enumeration") < 0 &&
                                             port.properties.indexOf("toggled") < 0 &&
                                             port.properties.indexOf("trigger") < 0)
                {
                    // For ports that are not enumerated, we allow
                    // editing the value directly
                    valueField.attr('contenteditable', true)
                    valueField.focus(function () {
                        valueField.text(sprintf(port.format, valueField.data('value')))
                    })
                    valueField.keydown(function (e) {
                        // enter
                        if (e.keyCode == 13) {
                            valueField.blur()
                            return false
                        }
                        // numbers
                        if (e.keyCode >= 48 && e.keyCode <= 57) {
                            return true;
                        }
                        if (e.keyCode >= 96 && e.keyCode <= 105) {
                            return true;
                        }
                        // backspace and delete
                        if (e.keyCode == 8 || e.keyCode == 46 || e.keyCode == 110) {
                            return true;
                        }
                        // left, right, dot
                        if (e.keyCode == 37 || e.keyCode == 39 || e.keyCode == 190) {
                            return true;
                        }
                        // minus
                        if (e.keyCode == 109 || e.keyCode == 189) {
                            return true;
                        }
                        // prevent key
                        e.preventDefault();
                        return false
                    })
                    valueField.blur(function () {
                        var value = parseFloat(valueField.text())
                        if (isNaN(value)) {
                            value = valueField.data('value')
                            valueField.text(sprintf(port.format, value))
                        }
                        else if (value < port.ranges.minimum)
                            value = port.ranges.minimum;
                        else if (value > port.ranges.maximum)
                            value = port.ranges.maximum;
                        self.setPortValue(symbol, value, control)
                        // setPortWidgetsValue() skips this control as it's the same as the 'source'
                        control.controlWidget('setValue', value, true)
                    })
                }

                port.widgets.push(control)

                control.attr("mod-port", (instance ? instance + "/" : "") + symbol)
                control.addClass("mod-port")

                self.setPortWidgetsValue(symbol, port.value, control, true)
            }
            else
            {
                control.text('No such symbol: ' + symbol)
            }
        })

        element.find('[mod-role=bypass]').each(function () {
            var control = $(this)
            var port = self.controls[':bypass']
            port.widgets.push(control)

            control.bypassWidget({
                dummy: onlySetValues,
                port: port,
                change: function (e, value) {
                    /*
                     TESTING - the following code is also on 'changeLights' so we don't need it here?
                    self.bypassed = value
                    element.find('[mod-role=bypass-light]').each(function () {
                        // NOTE
                        // the element itself will get inverse class ("on" when light is "off"),
                        // because of the switch widget.
                        if (value)
                            $(this).addClass('off').removeClass('on')
                        else
                            $(this).addClass('on').removeClass('off')
                    });
                    */
                    self.bypassed = !!value

                    self.setPortValue(':bypass', value ? 1 : 0, control)

                    /*
                    if (value)
                        control.addClass('on').removeClass('off')
                    else
                        control.addClass('off').removeClass('on')
                    */
                },
                changeLights: function (value) {
                    element.find('[mod-role=bypass-light]').each(function () {
                        // NOTE
                        // the element itself will get inverse class ("on" when light is "off"),
                        // because of the switch widget.
                        if (value)
                            $(this).addClass('off').removeClass('on')
                        else
                            $(this).addClass('on').removeClass('off')
                    });
                },
            })

            control.attr("mod-port", instance ? instance + "/:bypass" : ":bypass")
            control.attr("mod-widget", "bypass")
            control.addClass("mod-port")

            self.setPortWidgetsValue(':bypass', onlySetValues ? 0 : port.value, control, true)
        })

        element.find('[mod-role=bypass-light]').each(function () {
            self.setPortWidgetsValue(':bypass', onlySetValues ? 0 : (self.bypassed ? 1 : 0), $(this), true)
        })

        if (onlySetValues) {
            return
        }

        element.find('[mod-role=input-control-minimum]').each(function () {
            var symbol = $(this).attr('mod-port-symbol')
            if (!symbol) {
                $(this).html('missing mod-port-symbol attribute')
                return
            }
            var port = self.controls[symbol]
            if (! port) {
                return
            }

            var format, value
            if (port.units.render) {
                format = port.units.render
            } else {
                format = '%f'
            }

            if (port.properties.indexOf("integer") >= 0) {
                format = format.replace(/%\.\d+f/, '%d')
                value = sprintf(format, port.ranges.minimum)
            }
            else {
                value = sprintf(format, port.ranges.minimum)
                if (value.length > 8) {
                    format = format.replace('%f', '%.2f')
                    value  = sprintf(format, port.ranges.minimum)
                }
            }
            $(this).html(value)
        });

        element.find('[mod-role=input-control-maximum]').each(function () {
            var symbol = $(this).attr('mod-port-symbol')
            if (!symbol) {
                $(this).html('missing mod-port-symbol attribute')
                return
            }
            var port = self.controls[symbol]
            if (! port) {
                return
            }

            var format, value
            if (port.units.render) {
                format = port.units.render
            } else {
                format = '%f'
            }

            if (port.properties.indexOf("integer") >= 0) {
                format = format.replace(/%\.\d+f/, '%d')
                value  = sprintf(format, port.ranges.maximum)
            } else {
                value = sprintf(format, port.ranges.maximum)
                if (value.length > 8) {
                    format = format.replace('%f', '%.2f')
                    value  = sprintf(format, port.ranges.maximum)
                }
            }
            $(this).html(value)
        })

        // Gestures for tablet. When event starts, we check if it's centered in any widget and stores the widget if so.
        // Following events will be forwarded to proper widget
        element[0].addEventListener('gesturestart', function (ev) {
            ev.preventDefault()
            element.find('[mod-role=input-control-port]').each(function () {
                var widget = $(this)
                var top = widget.offset().top
                var left = widget.offset().left
                var right = left + widget.width()
                var bottom = top + widget.height()
                if (ev.pageX >= left && ev.pageX <= right && ev.pageY >= top && ev.pageY <= bottom) {
                    element.data('gestureWidget', widget)
                    widget.controlWidget('gestureStart')
                }
            });
            ev.handled = true
        })
        element[0].addEventListener('gestureend', function (ev) {
            ev.preventDefault()
            element.data('gestureWidget').controlWidget('gestureEnd', ev.scale)
            element.data('gestureWidget', null)
            ev.handled = true
        })
        element[0].addEventListener('gesturechange', function (ev) {
            ev.preventDefault()
            var widget = element.data('gestureWidget')
            if (!widget) {
                return
            }
            widget.controlWidget('gestureChange', ev.scale)
            ev.handled = true
        })
        element[0].addEventListener('dblclick', function (ev) {
            ev.preventDefault()
            ev.handled = true
        })
    }

    this.getTemplateData = function (options, skipNamespace) {
        var data = $.extend({}, options.gui.templateData)
        data.effect = options

        var version    = [options.builder, options.microVersion, options.minorVersion, options.release].join('_')
        var escapeduri = escape(options.uri)

        if (skipNamespace) {
            data.ns  = ''
            data.cns = '_sdk'
        } else {
            data.ns  = '?uri=' + escapeduri + '&v=' + version,
            data.cns = '_' + escapeduri.split("/").join("_").split("%").join("_").split(".").join("_") + version
        }

        // fill fields that might not be present on modgui data
        if (!data.brand) {
            data.brand = options.gui.brand || ""
        }
        if (!data.label) {
            data.label = options.gui.label || ""
        }
        if (!data.color) {
            data.color = options.gui.color
        }
        if (!data.knob) {
            data.knob = options.gui.knob
        }
        if (!data.model) {
            data.model = options.gui.model
        }
        if (!data.panel) {
            data.panel = options.gui.panel
        }
        if (!data.controls) {
            data.controls = options.gui.ports || {}
        }

        // insert comment and scalePoints into controls
        for (var i in data.controls)
        {
            var dcontrol = data.controls[i]
            var scontrol = self.controls[dcontrol.symbol]

            if (scontrol) {
                dcontrol.comment     = scontrol.comment
                dcontrol.scalePoints = scontrol.scalePoints
            } else {
                console.log("Control port symbol '" + dcontrol.symbol + "' is missing")
            }
        }

        if (data.effect.ports.control.input)
        {
            var inputs = []
            for (var i in data.effect.ports.control.input) {
                var port = data.effect.ports.control.input[i]

                // skip notOnGUI controls
                if (shouldSkipPort(port)) {
                    continue
                }

                port['enumeration'] = port.properties.indexOf("enumeration") >= 0
                port['integer'    ] = port.properties.indexOf("integer") >= 0
                port['logarithmic'] = port.properties.indexOf("logarithmic") >= 0
                port['toggled'    ] = port.properties.indexOf("toggled") >= 0
                port['trigger'    ] = port.properties.indexOf("trigger") >= 0

                inputs.push(port)
            }

            data.effect.all_control_in_ports = data.effect.ports.control.input
            data.effect.ports.control.input = inputs
        }
        else
        {
            data.effect.all_control_in_ports = []
        }

        if (isSDK) {
            // this is expensive and only useful for mod-sdk
            DEBUG = JSON.stringify(data, undefined, 4)
        }

        return data
    }

    this.jsData = {}
    this.jsStarted = false

    this.jsFuncs = {
        // added in v1: allow plugin js code to change plugin controls
        set_port_value: function (symbol, value) {
            self.setPortValue(symbol, value, null)
        }
    }

    this.triggerJS = function (event) {
        if (!self.jsCallback || !self.jsStarted)
            return

        // bump this everytime the data structure or funtions change
        event.api_version = 1

        // normal data
        event.data     = self.jsData
        event.icon     = self.icon
        event.settings = self.settings

        try {
            self.jsCallback(event, self.jsFuncs)
        } catch (err) {
            self.jsCallback = null
            console.log("A plugin javascript code is broken and has been disabled")
        }
    }
}

function JqueryClass() {
    var name = arguments[0]
    var methods = {}
    for (var i = 1; i < arguments.length; i++) {
        $.extend(methods, arguments[i])
    }
    (function ($) {
        $.fn[name] = function (method) {
            if (methods[method]) {
                return methods[method].apply(this, Array.prototype.slice.call(arguments, 1));
            } else if (typeof method === 'object' || !method) {
                return methods.init.apply(this, arguments);
            } else {
                $.error('Method ' + method + ' does not exist on jQuery.' + name);
            }
        }
    })(jQuery);
}

(function ($) {
    $.fn['controlWidget'] = function () {
        var self = $(this)
        var widgets = {
            'film': 'film',
            'switch': 'switchWidget',
            'bypass': 'bypassWidget',
            'select': 'selectWidget',
            'custom-select': 'customSelect'
        }
        var name = self.attr('mod-widget') || 'film'
        name = widgets[name]
        $.fn[name].apply(this, arguments)
    }
})(jQuery);

var baseWidget = {
    config: function (options) {
        var self = $(this)
            // Very quick bugfix. When pedalboard is unserialized, the disable() of addressed knobs
            // are called before config. Right thing would probably be to change this behaviour, but
            // while that is not done, this check will avoid the bug. TODO
        if (!(self.data('enabled') === false))
            self.data('enabled', true)
        self.bind('valuechange', options.change)

        var port = options.port

        var portSteps
        if (port.properties.indexOf("toggled") >= 0) {
            portSteps = 2
        } else if (port.properties.indexOf("enumeration") >= 0 && port.scalePoints.length >= 2) {
            portSteps = port.scalePoints.length
            //port.scalePoints.sort(function (a, b) { return a.value - b.value })
        } else {
            portSteps = self.data('filmSteps')
        }

        if (port.rangeSteps) {
            portSteps = Math.min(port.rangeSteps, portSteps)
        }

        // This is a bit verbose and could be optmized, but it's better that
        // each port property used is documented here
        self.data('symbol',       port.symbol)
        self.data('default',      port.ranges.default)
        self.data('maximum',      port.ranges.maximum)
        self.data('minimum',      port.ranges.minimum)
        self.data('enumeration',  port.properties.indexOf("enumeration") >= 0)
        self.data('integer',      port.properties.indexOf("integer") >= 0)
        self.data('logarithmic',  port.properties.indexOf("logarithmic") >= 0)
        self.data('toggled',      port.properties.indexOf("toggled") >= 0)
        self.data('trigger',      port.properties.indexOf("trigger") >= 0)
        self.data('scalePoints',  port.scalePoints)

        if (port.properties.indexOf("logarithmic") >= 0) {
            self.data('scaleMinimum', (port.ranges.minimum != 0) ? Math.log(port.ranges.minimum) / Math.log(2) : 0)
            self.data('scaleMaximum', (port.ranges.maximum != 0) ? Math.log(port.ranges.maximum) / Math.log(2) : 0)
        } else {
            self.data('scaleMinimum', port.ranges.minimum)
            self.data('scaleMaximum', port.ranges.maximum)
        }

        var wheelStep = 30
        var stepDivider = portSteps / Math.max(portSteps, wheelStep)

        self.data('portSteps', portSteps)
        self.data('wheelStep', wheelStep)
        self.data('stepDivider', stepDivider)

        self.data('dragPrecisionVertical', Math.ceil(100 / portSteps))
        self.data('dragPrecisionHorizontal', Math.ceil(portSteps / 10))
    },

    setValue: function (value, only_gui) {
        alert('not implemented')
    },

    // For tablets: these methods can be used to implement gestures.
    // It will receive gesture events a scale from a gesture centered on this widget
    gestureStart: function () {},
    gestureChange: function (scale) {},
    gestureEnd: function (scale) {},

    disable: function () {
        $(this).addClass('disabled').data('enabled', false)
    },
    enable: function () {
        $(this).removeClass('addressed').removeClass('disabled').data('enabled', true)
    },
    address: function () {
        $(this).data('enabled', true)
    },

    valueFromSteps: function (steps) {
        var self = $(this)
        var min = self.data('scaleMinimum')
        var max = self.data('scaleMaximum')
        var portSteps = self.data('portSteps')

        steps = Math.min(portSteps-1, Math.max(0, steps))

        var portSteps = self.data('portSteps')

        var value = min + steps * (max - min) / (portSteps - 1)
        if (self.data('logarithmic')) {
            value = Math.pow(2, value)
        }

        if (self.data('integer')) {
            value = Math.round(value)
        }

        if (self.data('enumeration')) {
            steps = Math.round(steps)
            value = self.data('scalePoints')[steps].value
        }

        if (value < self.data('minimum')) {
            value = self.data('minimum')
        } else if (value > self.data('maximum')) {
            value = self.data('maximum')
        }

        return value
    },

    stepsFromValue: function (value) {
        var self = $(this)

        if (self.data('enumeration')) {
            // search for the nearest scalePoint
            var points = self.data('scalePoints')
            if (value <= points[0].value)
                return 0
            for (var step = 0; step < points.length; step++) {
                if (points[step + 1] == null) {
                    return step
                }
                if (value < points[step].value + (points[step + 1].value - points[step].value) / 2) {
                    return step
                }
            }
        }

        var portSteps = self.data('portSteps')
        var min = self.data('scaleMinimum')
        var max = self.data('scaleMaximum')

        if (self.data('logarithmic')) {
            value = Math.log(value) / Math.log(2)
        }

        if (self.data('integer')) {
            value = Math.round(value)
        }

        return Math.round((value - min) * (portSteps - 1) / (max - min))
    },

    prevent: function (e) {
        var self = $(this)
        if (self.data('prevent')) {
            return
        }
        self.data('prevent', true)
        var img = $('<img>').attr('src', 'img/icn-blocked.png')
        $('body').append(img)
        img.css({
            position: 'absolute',
            top: e.pageY - img.height() / 2,
            left: e.pageX - img.width() / 2,
            zIndex: 99999
        })
        setTimeout(function () {
            img.remove()
            self.data('prevent', false)
        }, 500)
        new Notification("warn", "Cannot change a parameter addressed to hardware", 3000)
    }
}

JqueryClass('film', baseWidget, {
    init: function (options) {
        var self = $(this)
        self.data('dragged', false)
        self.data('initialized', false)
        self.data('initvalue', options.port.ranges.default)
        self.film('getAndSetSize', options.dummy, function () {
            self.film('config', options)
            self.data('initialized', true)
            self.film('setValue', self.data('initvalue'), true)
        })

        self.on('dragstart', function (event) {
            event.preventDefault()
        })

        var moveHandler = function (e) {
            if (!self.data('enabled')) {
                return
            }
            self.film('mouseMove', e)
        }

        var upHandler = function (e) {
            self.film('mouseUp', e)
            $(document).unbind('mouseup', upHandler)
            $(document).unbind('mousemove', moveHandler)
        }

        self.mousedown(function (e) {
            e.preventDefault();
            if (!self.data('enabled')) {
                return self.film('prevent', e)
            }
            if (e.which == 1) { // left button
                self.film('mouseDown', e)
                $(document).bind('mouseup', upHandler)
                $(document).bind('mousemove', moveHandler)
                self.trigger('filmstart')
            }
         })

        self.data('wheelBuffer', 0)
        self.bind('mousewheel', function (e) {
            if (!self.data('enabled')) {
                return self.film('prevent', e)
            }
            self.film('mouseWheel', e)
        })

        self.bind('touchstart', function (e) {
            e.preventDefault();
            if (!self.data('enabled')) {
                return self.film('prevent', e)
            }
            self.film('mouseDown', e.originalEvent.changedTouches[0])
        })
        self.bind('touchmove', function (e) {
            if (!self.data('enabled')) {
                return
            }
            self.film('mouseMove', e.originalEvent.changedTouches[0])
        })
        self.bind('touchend', function (e) {
            self.film('mouseUp', e.originalEvent.changedTouches[0])
        })

        self.click(function (e) {
            if (!self.data('enabled')) {
                return self.film('prevent', e)
            }
            if (self.data('dragged')) {
                /* If we get a click after dragging the knob, ignore the click.
                   This happens when the user releases the mouse while hovering the knob.
                   We DO NOT want this click event, as it will bump the current value again. */
                return
            }
            self.film('mouseClick', e)
        })

        return self
    },

    setValue: function (value, only_gui) {
        var self = $(this)
        if (self.data('initialized')) {
            var position = self.film('stepsFromValue', value)
            self.data('position', position)
            self.film('setRotation', position)
        } else {
            self.data('initvalue', value)
        }
        if (!only_gui) {
            self.trigger('valuechange', value)
        }
    },

    getAndSetSize: function (dummy, callback) {
        var self = $(this)
        var binded = false
        var handled = false

        function tryGetAndSetSizeNow() {
            if (dummy && ! self.is(":visible")) {
                return
            }
            if (self.data('initialized') || handled) {
                desktop.pedalboard.pedalboard('scheduleAdapt', false)
                return
            }

            var url = self.css('background-image') || "none";
            url = url.match(/^url\(['"]?([^\)'"]*)['"]?\)/i);
            if (!url) {
                if (! binded) {
                    binded = true
                    self.bind('resize', tryGetAndSetSizeNow)
                }
                return
            }

            handled = true
            url = url[1];
            if (binded) {
                self.unbind('resize')
            }

            var height = parseInt(self.css('background-size').split(" ")[1] || 0);
            var bgImg = new Image;
            bgImg.onload = function () {
                var w = this.naturalWidth;
                var h = this.naturalHeight;
                var computedStyle = window.getComputedStyle(self.get(0));
                var computedStyleWidth = computedStyle.getPropertyValue('width')
                var sw = computedStyleWidth ? Math.round(parseFloat(computedStyleWidth)) : self.outerWidth();
                if (w == 0) {
                    new Notification('error', 'Apparently your browser does not support all features you need. Install latest Chromium, Google Chrome or Safari')
                }
                height = height || h;
                self.data('filmSteps', Math.round(height * w / (sw * h)));
                self.data('size', sw)
                callback()
                if (! isSDK && desktop != null) {
                    desktop.pedalboard.pedalboard('scheduleAdapt', false)
                }
            }
            bgImg.setAttribute('src', url);
        }

        setTimeout(tryGetAndSetSizeNow, 5)
    },

    mouseDown: function (e) {
        var self = $(this)
        self.data('dragged', false)
        self.data('lastY', e.pageY)
        self.data('lastX', e.pageX)
    },

    mouseUp: function (e) {
        var self = $(this)
    },

    mouseMove: function (e) {
        var self = $(this)
        self.data('dragged', true)

        var vdiff = (self.data('lastY') - e.pageY) / self.data('dragPrecisionVertical')
        var hdiff = (e.pageX - self.data('lastX')) / self.data('dragPrecisionHorizontal')
        var portSteps = self.data("portSteps")

        if (Math.abs(vdiff) > 0) {
            self.data('lastY', e.pageY)
        }
        if (Math.abs(hdiff) > 0) {
            self.data('lastX', e.pageX)
        }

        var position = self.data('position')
        var diff = (vdiff + hdiff) * self.data('stepDivider')

        position += diff
        position = Math.min(portSteps-1, Math.max(0, position));

        self.data('position', position)
        self.film('setRotation', position)
        var value = self.film('valueFromSteps', position)
        self.trigger('valuechange', value)
    },

    mouseClick: function (e) {
        // Advance one step, to go beginning if at end.
        // Useful for fine tunning and toggle
        var self = $(this)
        var portSteps = self.data('portSteps')
        var position = self.data('position')

        if (e.shiftKey) {
            // going down
            position -= 1
            if (position < 0) {
                if (self.data('enumeration') || self.data('toggled')) {
                    position = portSteps-1
                } else {
                    position = 0
                }
            }
        } else {
            // going up
            position += 1
            if (position >= portSteps) {
                if (self.data('enumeration') || self.data('toggled')) {
                    position = 0
                } else {
                    position = portSteps-1
                }
            }
        }

        self.data('position', position)
        self.film('setRotation', position)
        var value = self.film('valueFromSteps', position)
        self.trigger('valuechange', value)
    },

    mouseWheel: function (e) {
        var self = $(this)
        var portSteps = self.data("portSteps")
        var wheelStep = self.data("wheelStep")
        var delta = ('wheelDelta' in e.originalEvent) ? e.originalEvent.wheelDelta : -wheelStep * e.originalEvent.detail;
        delta += self.data('wheelBuffer')
        self.data('wheelBuffer', delta % wheelStep)
        var diff = (delta / wheelStep) * self.data("stepDivider")
        if (diff == 0.0) {
            return
        }
        if (diff >= -1.0 && diff <= 1.0) {
            diff = diff > 0 ? 1 : -1
        } else {
            diff = Math.round(diff)
        }
        var position = self.data('position')
        position += diff
        position = Math.min(portSteps-1, Math.max(0, position))
        self.data('position', position)
        if (Math.abs(diff) > 0) {
            self.data('lastY', e.pageY)
        }
        self.film('setRotation', position)
        var value = self.film('valueFromSteps', position)
        self.trigger('valuechange', value)
    },

    gestureStart: function () {},
    gestureChange: function (scale) {
        var self = $(this)
        var diff = Math.round(Math.log(scale) * 30)
        var position = self.data('position')
        position += diff
        self.film('setRotation', position)
        self.data('lastPosition', position)
        var value = self.film('valueFromSteps', position)
        self.trigger('valuechange', value)
    },
    gestureEnd: function () {
        var self = $(this)
        self.data('position', self.data('lastPosition'))
    },

    setRotation: function (steps) {
        var self = $(this)

        var filmSteps = self.data('filmSteps')
        var portSteps = self.data('portSteps')
        var rotation

        if (portSteps == 1) {
        // this is very dummy, a control with only one possible. let's just avoid zero division
        // in this theoric case.
            rotation = Math.round(filmSteps / 2)
        } else if (portSteps != null) {
            rotation = Math.round(steps) * Math.round(filmSteps / portSteps)
        }

        rotation = Math.min(filmSteps-1, Math.max(0, rotation))

        var bgShift = rotation * -self.data('size')
        bgShift += 'px 0px'
        self.css('background-position', bgShift)
    }

})

JqueryClass('selectWidget', baseWidget, {
    init: function (options) {
        var self = $(this)
        self.selectWidget('config', options)
        self.selectWidget('setValue', options.port.ranges.default, true)
        self.change(function () {
            // nothing special here, no need to call 'setValue'
            self.trigger('valuechange', parseFloat(self.val()))
        })
        return self
    },

    setValue: function (value, only_gui) {
        var self = $(this)
        self.val(value)
        if (!only_gui) {
            self.trigger('valuechange', value)
        }
    }
})

JqueryClass('switchWidget', baseWidget, {
    init: function (options) {
        var self = $(this)
        self.switchWidget('config', options)
        self.switchWidget('setValue', options.port.ranges.default, true)
        self.click(function (e) {
            if (!self.data('enabled')) {
                return self.switchWidget('prevent', e)
            }
            var nextValue = (self.data('value') == self.data('minimum')) ? self.data('maximum') : self.data('minimum')
            self.switchWidget('setValue', nextValue, false)
        })
        return self
    },
    setValue: function (value, only_gui) {
        var self = $(this)
        self.data('value', value)

        if (value == self.data('minimum')) {
            self.addClass('off').removeClass('on')
        } else {
            self.addClass('on').removeClass('off')
        }

        if (!only_gui) {
            self.trigger('valuechange', value)
        }
    }
})

// this is the same as switchWidget with extra bypass-specific stuff
JqueryClass('bypassWidget', baseWidget, {
    init: function (options) {
        var self = $(this)
        self.data('changeLights', options.changeLights)
        self.bypassWidget('config', options)
        self.bypassWidget('setValue', options.port.ranges.default, true)
        self.click(function (e) {
            if (!self.data('enabled')) {
                return self.bypassWidget('prevent', e)
            }
            var nextValue = (self.data('value') == self.data('minimum')) ? self.data('maximum') : self.data('minimum')
            self.bypassWidget('setValue', nextValue, false)
        })
        return self
    },
    setValue: function (value, only_gui) {
        var self = $(this)
        self.data('value', value)
        self.data('changeLights')(value)

        if (value) {
            self.addClass('on').removeClass('off')
        } else {
            self.addClass('off').removeClass('on')
        }

        if (!only_gui) {
            self.trigger('valuechange', value)
        }
    },
})

JqueryClass('customSelect', baseWidget, {
    init: function (options) {
        var self = $(this)
        self.customSelect('config', options)
        self.customSelect('setValue', options.port.ranges.default, true)
        self.find('[mod-role=enumeration-option]').each(function () {
            var opt = $(this)
            opt.click(function (e) {
                if (!self.data('enabled')) {
                    return self.customSelect('prevent', e)
                }
                var value = opt.attr('mod-port-value')
                self.customSelect('setValue', value, false)
            })
        })
        self.click(function () {
            self.find('.mod-enumerated-list').toggle()
        })

        return self
    },

    setValue: function (value, only_gui) {
        var self = $(this)
        self.find('[mod-role=enumeration-option]').removeClass('selected')

        value = parseFloat(value)

        var selected = self.customSelect('getSelectedByValue', value)
        selected.addClass('selected')

        var valueField = self.find('[mod-role=input-control-value]')
        if (valueField) {
            valueField.data('value', value)
            valueField.text(selected.text())
        }

        if (!only_gui) {
            self.trigger('valuechange', value)
        }
    },

    // NOTE: this code matches the one in server-side `get_nearest_valid_scalepoint_value`
    getSelectedByValue: function (value) {
        var self = $(this)

        var selected = self.find('[mod-role=enumeration-option][mod-port-value="' + value + '"]')
        if (selected.length !== 0) {
            return selected
        }

        var options = self.find('[mod-role=enumeration-option]')
        var ovalue, nvalue
        for (var i=0; i<options.length; ++i) {
            ovalue = options[i].getAttribute("mod-port-value")
            if (Math.abs(parseFloat(ovalue)-value) < 0.0001) {
                return self.find('[mod-role=enumeration-option][mod-port-value="' + ovalue + '"]')
            }
        }

        for (var i=0; i<options.length-1; ++i) {
            ovalue = options[i].getAttribute("mod-port-value")
            nvalue = options[i+1].getAttribute("mod-port-value")

            if (Math.abs(parseFloat(ovalue)-value) < Math.abs(parseFloat(nvalue)-value)) {
                return self.find('[mod-role=enumeration-option][mod-port-value="' + ovalue + '"]')
            }
        }

        return self.find('[mod-role=enumeration-option][mod-port-value="' + nvalue + '"]')
    },
})
