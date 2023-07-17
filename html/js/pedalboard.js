// SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
// SPDX-License-Identifier: AGPL-3.0-or-later

$.ui.intersect = function(draggable, droppable, toleranceMode) {
    if (!droppable.offset) {
        return false;
    }

    var draggableLeft, draggableTop,
        x1 = (draggable.positionAbs || draggable.position.absolute).left,
        y1 = (draggable.positionAbs || draggable.position.absolute).top,
        x2 = x1 + draggable.helperProportions.width,
        y2 = y1 + draggable.helperProportions.height,
        l = droppable.offset.left,
        t = droppable.offset.top,
        r = l + droppable.proportions.width,
        b = t + droppable.proportions.height;

    switch (toleranceMode) {
    case "custom":
        return (l < x1 + (draggable.helperProportions.width / 2) && // Right Half
                x2 - (draggable.helperProportions.width / 2) < r && // Left Half
                t < y1 + (draggable.helperProportions.height / 2.5) && // Bottom Half
                y2 - (draggable.helperProportions.height / 2.5) < b ); // Top Half
    case "custom-replace":
        {
            var scale = draggable.helper.data('scale');
            if (!scale) {
                return false;
            }

            x1 = draggable.helper.offset().left;
            y1 = draggable.helper.offset().top;
            x2 = x1 + draggable.helper.children().width() * scale;
            y2 = y1 + draggable.helper.children().height() * scale;
            r = l + droppable.proportions.width * scale;
            b = t + droppable.proportions.height * scale;

            /* helper code for display drag and drop areas
            $('#dropable-area').css({ left: l, width: r - l, top: t, height: b - t, })
            $('#draggable-area').css({ left: x1, top: y1, width: x2 - x1, height: y2 - y1, })
            */

            // touch
            return (
                (y1 >= t && y1 <= b) ||	// Top edge touching
                (y2 >= t && y2 <= b) ||	// Bottom edge touching
                (y1 < t && y2 > b)		// Surrounded vertically
            ) && (
                (x1 >= l && x1 <= r) ||	// Left edge touching
                (x2 >= l && x2 <= r) ||	// Right edge touching
                (x1 < l && x2 > r)		// Surrounded horizontally
            );
        }
    case "fit":
        return (l <= x1 && x2 <= r && t <= y1 && y2 <= b);
    case "intersect":
        return (l < x1 + (draggable.helperProportions.width / 2) && // Right Half
            x2 - (draggable.helperProportions.width / 2) < r && // Left Half
            t < y1 + (draggable.helperProportions.height / 2) && // Bottom Half
            y2 - (draggable.helperProportions.height / 2) < b ); // Top Half
    case "pointer":
        draggableLeft = ((draggable.positionAbs || draggable.position.absolute).left + (draggable.clickOffset || draggable.offset.click).left);
        draggableTop = ((draggable.positionAbs || draggable.position.absolute).top + (draggable.clickOffset || draggable.offset.click).top);
        return isOverAxis( draggableTop, t, droppable.proportions().height ) && isOverAxis( draggableLeft, l, droppable.proportions().width );
    case "touch":
        return (
            (y1 >= t && y1 <= b) ||	// Top edge touching
            (y2 >= t && y2 <= b) ||	// Bottom edge touching
            (y1 < t && y2 > b)		// Surrounded vertically
        ) && (
            (x1 >= l && x1 <= r) ||	// Left edge touching
            (x2 >= l && x2 <= r) ||	// Right edge touching
            (x1 < l && x2 > r)		// Surrounded horizontally
        );
    default:
        return false;
    }
};

JqueryClass('pedalboard', {
    init: function (options) {
        var self = $(this)
        options = $.extend({
            // baseScale is the initial scale (zoom level) of the pedalboard
            // The scale is the transform scale() css property that the pedalboard has
            baseScale: 0.5,
            // maxScale is the maximum zoom.
            maxScale: 1,
            // wherever to skip zoom animations
            skipAnimations: false,

            // WindowManager instance
            windowManager: new WindowManager(),
            // HardwareManager instance, must be specified
            hardwareManager: null,

            // Wait object, used to show waiting message to user
            wait: new WaitMessage(self),

            // current z index (last plugin added or moved around)
            z_index: 30,

            // This is a margin, in pixels, that will be disconsidered from pedalboard height when calculating
            // hardware ports positioning
            bottomMargin: 0,

            cvAddressing: false,

            // Below are functions that application uses to integrate functionality to pedalboard.
            // They all receive a callback as last parameter, which must be called with a true value
            // to indicate that operation was successfully executed.
            // In case of error, application is expected to communicate error to user and then call the
            // callback with false value. The pedalboard will silently try to keep consistency, with
            // no garantees. (TODO: do something if consistency can't be achieved)

            // Loads a plugin with given plugin uri and instance
            // Application MUST use this instance. Overriding this is mandatory.
            pluginLoad: function (uri, instance, x, y, callback, errorCallback) {
                callback(true)
            },

            // Removes the plugin given by instance
            pluginRemove: function (instance, callback) {
                callback(true)
            },

            // Loads a preset
            pluginPresetLoad: function (instance, uri, callback) {
                callback(true)
            },

            // Save a new preset
            pluginPresetSaveNew: function (instance, name, callback) {
                callback({ok:false})
            },

            // Save a preset, replacing an existing one
            pluginPresetSaveReplace: function (instance, uri, bundlepath, name, callback) {
                callback({ok:false})
            },

            // Delete a preset
            pluginPresetDelete: function (instance, uri, bundlepath, callback) {
                callback(true)
            },

            // Changes the parameter of a plugin's control port
            pluginParameterChange: function (port, value) {},

            // Get value of a plugin parameter
            pluginPatchGet: function (instance, uri) {},

            // Set value of a plugin parameter
            pluginPatchSet: function (instance, uri, valuetype, value) {},

            // Connects two ports
            portConnect: function (fromPort, toPort, callback) {
                callback(true)
            },

            // Disconnect two ports
            portDisconnect: function (fromPort, toPort, callback) {
                callback(true)
            },

            // Removes all plugins
            reset: function (callback) {
                callback(true)
            },

            // Marks the position of a plugin
            pluginMove: function (instance, x, y) {},

            // Takes a list of plugin URIs and gets a dictionary containing all those plugins's data,
            // indexed by URI
            getPluginsData: function (uris, callback) {
                callback({})
            },

            // Show dialog with plugin info, same as clicking on the bottom plugin bar
            showPluginInfo: function (pluginData) {
            },

            // Show the plugin's native UI, in an external desktop window
            showExternalUI: function (instance) {
            },

            // Sets the size of the pedalboard
            windowSize: function (width, height) {},

            // inform dekstop instance that pedalboard has finished loading
            pedalboardFinishedLoading: function (callback) {
                callback()
            },

            // Add new plugin cv output port to available addressable cv ports
            // or update existing cv port's name
            addCVAddressingPluginPort: function (uri, label, callback) {
              callback(true)
            },

            // Remove plugin cv output port from available addressable cv ports
            removeCVAddressingPluginPort: function (uri, callback) {
              callback(true)
            },

            // Show notification that we are using a demo plugin
            notifyDemoPluginLoaded: function () {
            },
        }, options)

        self.pedalboard('wrapApplicationFunctions', options, [
            'pluginLoad', 'pluginRemove',
            'pluginPresetLoad', 'pluginPresetSaveNew', 'pluginPresetSaveReplace', 'pluginPresetDelete',
            'pluginParameterChange', 'pluginPatchGet', 'pluginPatchSet', 'pluginMove',
            'portConnect', 'portDisconnect', 'reset', 'getPluginsData'
        ])

        self.data(options)

        // When bypassApplication is set to true, the applicationFunctions provided by options will be bypassed
        self.data('bypassApplication', false)

        // minScale holds the minimum scale of the pedalboard. It's initialized as being the base scale
        // and gets smaller as pedalboard size grows
        self.data('minScale', options.baseScale)

        self.data('instanceCounter', -1)
        self.data('overCount', 0)

        // Holds all plugins loaded, indexed by instance
        self.data('plugins', {})

        // Hardware inputs and outputs, which have an instance of -1 and symbol as given by application
        self.data('hwInputs', [])
        self.data('hwOutputs', [])

        // connectionManager keeps track of all connections
        self.data('connectionManager', new ConnectionManager())

        // last adapt schedule time
        self.data('adaptTime', 0)

        // if first time to adapt
        self.data('adaptFirstTime', true)

        // widgets on the arrive list
        self.data('callbacksToArrive', {})

        // replacement plugin, used for recreating connections
        self.data('replacementPlugin', null)

        // Pedalboard itself will get big dimensions and will have it's scale and position changed dinamically
        // often. So, let's wrap it inside an element with same original dimensions and positioning, with overflow
        // hidden, so that the visible part of the pedalboard is always occupying the area that was initially determined
        // by the css.
        var parent = $('<div>')
        parent.css({
            width: self.width(),
            height: self.height(),
            position: self.css('position'),
            top: self.css('top'),
            left: self.css('left'),
            overflow: 'hidden'
        })
        parent.insertAfter(self)
        self.appendTo(parent)

        self.pedalboard('resetSize')

        // Pedalboard is expected to be the main element in screen. So, the original margins relative to window will be
        // stored, so that when window is resized, pedalboard is resized too, keeping that margins
        self.data('offset', self.offset())
        self.data('hmargins', $(window).width() - self.parent().width())
        self.data('vmargins', $(window).height() - self.parent().height())
        self.data('topmargin', self.offset().top)

        if (! options.skipAnimations) {
            var resizeTimeout;

            function resizeThrottler() {
                if (resizeTimeout) {
                    clearTimeout(resizeTimeout);
                }
                resizeTimeout = setTimeout(function() {
                    resizeTimeout = null;
                    self.pedalboard('fitToWindow');
                }, 250);
            }

            window.addEventListener("resize", resizeThrottler, false);
            //$(window).resize(resizeThrottler)
        }

        // Create background element to catch dropped jacks
        // Must be much bigger than screen, so that nothing can be
        // dropped outside it even if mouse goes outside window
        var bg = $('<div>')
        bg.addClass('ignore-arrive')
        bg.css({
            width: '300%',
            height: '300%',
            position: 'absolute',
            top: '-100%',
            left: '-100%'
        })
        self.append(bg)
        bg.droppable({
            accept: '[mod-role=output-jack]',
            greedy: true,
            drop: function (event, ui) {
                var jack = ui.draggable
                self.pedalboard('disconnect', jack)
            },
        })
        self.data('background', bg)

        // Create a blank SVG containing some fancy f/x for later use
        self.svg({ onLoad: function (svg) {
            var _svg = svg._svg;
            _svg.setAttribute("id", "styleSVG");
            var defs = svg.defs();
            for (var i = 1; i <= 20; i+=1) {
                var filter = document.createElementNS("http://www.w3.org/2000/svg", 'filter');
                filter.setAttribute("id", "blur_" + i);
                filter.setAttribute("x", "0");
                filter.setAttribute("y", "0");
                var blur = document.createElementNS("http://www.w3.org/2000/svg", 'feGaussianBlur');
                blur.setAttribute("stdDeviation", i / 10);
                filter.appendChild(blur);
                defs.appendChild(filter);
            }
        }});

        // Dragging the pedalboard move the view area
        self.mousedown(function (e) {
            self.pedalboard('drag', e)
        })

        // The mouse wheel is used to zoom in and out
        self.bind('mousewheel', function (e) {
            // Zoom by mousewheel has been desactivated.
            // Let's keep the code here so that maybe later this can be a user option
            if (true) return;

            var ev = e.originalEvent

            // check if mouse is not over a control button
            if (self.pedalboard('mouseIsOver', ev, self.find('[mod-role=input-control-port]')))
                return

            var maxS = self.data('maxScale')
            var minS = self.data('minScale')
            var step = (maxS - minS) / 5
            var steps = ev.wheelDelta / 120
            var scale = self.data('scale')
            var newScale = scale + steps * step
            newScale = Math.min(maxS, newScale)
            newScale = Math.max(minS, newScale)

            if (newScale == scale)
                return

            var canvasX = (ev.pageX - self.offset().left) / scale
            var canvasY = (ev.pageY - self.offset().top) / scale
            var screenX = ev.pageX - self.parent().offset().left
            var screenY = ev.pageY - self.parent().offset().top

            self.pedalboard('zoom', newScale, canvasX, canvasY, screenX, screenY, 0)
        })

        self.pedalboard('initGestures')

        // To add plugins to pedalboard, user drags and drops a plugin element,
        // one that has been registered with registerAvailablePlugin
        self.droppable({
            accept: '[mod-role=available-plugin]',
            drop: function (event, ui) {
                if (ui.helper.consumed)
                    return // TODO Check if this really necessary
                var scale = self.data('scale')
                ui.draggable.trigger('pluginAdded', {
                    x: (ui.helper.offset().left - self.offset().left) / scale,
                    y: (ui.helper.offset().top - self.offset().top) / scale,
                    width: ui.helper.children().width(),
                    height: ui.helper.children().height()
                })
            }
        })

        self.disableSelection()

        return self
    },

    setCvAddressing: function (cvAddressing) {
      var self = $(this);
      self.data('cvAddressing', cvAddressing);
    },

    initGestures: function () {
        var self = $(this)
            // Gestures for tablets
        var startScale, canvasX, canvasY
        self[0].addEventListener('gesturestart', function (ev) {
            if (ev.handled) return
            startScale = self.data('scale')
            canvasX = (ev.pageX - self.offset().left) / startScale
            canvasY = (ev.pageY - self.offset().top) / startScale
            ev.preventDefault()
        })
        self[0].addEventListener('gesturechange', function (ev) {
            if (ev.handled) return
            var maxS = self.data('maxScale')
            var minS = self.data('minScale')
            var scale = self.data('scale')
            var newScale = startScale * ev.scale
            newScale = Math.min(maxS, newScale)
            newScale = Math.max(minS, newScale)

            var screenX = ev.pageX - self.parent().offset().left
            var screenY = ev.pageY - self.parent().offset().top

            self.pedalboard('zoom', newScale, canvasX, canvasY, screenX, screenY, 0)
            ev.preventDefault()
        })
        self[0].addEventListener('dblclick', function (ev) {
            if (ev.handled) return
            self.pedalboard('zoomOut')
            ev.preventDefault()
        })
    },

    // Check if mouse event has happened over any element of a jquery set in pedalboard
    mouseIsOver: function (ev, elements) {
        var scale = $(this).data('scale')
        var top, left, right, bottom, element
        for (var i = 0; i < elements.length; i++) {
            element = $(elements[i])
            top = element.offset().top
            left = element.offset().left
            right = left + element.width() * scale
            bottom = top + element.height() * scale
            if (ev.pageX >= left && ev.pageX <= right && ev.pageY >= top && ev.pageY <= bottom)
                return true
        }
        return false
    },

    // This wrap all application functions to provide a way to bypass all of them when desired
    wrapApplicationFunctions: function (options, functions) {
        var self = $(this)
        var factory = function (key, closure) {
                return function () {
                    var callback = arguments[arguments.length - 1]
                    if (self.data('bypassApplication')) {
                        callback(true)
                    } else {
                        closure.apply(this, arguments)
                    }
                }
            }
        // First, let's wrap all application functions to provide a way to bypass all of them when desired
        for (var i in functions)
            options[functions[i]] = factory(functions[i], options[functions[i]])
    },

    fakeLoadFromServerData: function (data, callback, bypassApplication) {
        var self = $(this)
        console.log("PEDALBOARD_DATA")
        console.log(data)
        /*
         * Unserialization will first call all application callbacks and after everything is done,
         * build the pedalboard in screen.
         * To do that, it takes 3 queues to work on (plugins, hw-ports, and connections), and as it's working
         * on them, it queues actions to be done when everything is ready.
         * To work on the instances and connections queues, it uses two asynchronous recursive functions
         * that will process next element element and gives itself as callback for the application.
         */

        // Let's avoid modifying original data
        data = $.extend({}, data)

        // We might want to bypass application
        self.data('bypassApplication', false)

        var ourCallback = function () {
            if (callback)
                callback()
        }

        // Queue closures to all actions needed after everything is loaded
        var finalActions = []
        var finish = function () {
            for (var i in finalActions)
                finalActions[i]()

            self.data('bypassApplication', false)
            setTimeout(function () {
                if (! self.pedalboard('fitToWindow')) {
                    self.pedalboard('adapt', true)
                }
                ourCallback()
            }, 1)
        }

        var loadPlugin, createHardwarePorts, connect

        // Loads the next plugin in queue. Gets as parameter a data structure containing
        // information on all plugins
        loadPlugin = function (pluginsData) {
            var plugin = data.plugins.pop()
            if (plugin == null) {
                // Queue is empty, let's create the hardware ports now
                return createHardwarePorts()
            }

            var pluginData = pluginsData[plugin.uri]

            if (pluginData == null) {
                console.log("Missing plugin:", plugin.uri)
                loadPlugin(pluginsData)
                return
            }

            var instance
            if (plugin.instance) {
                instance = '/graph/' + plugin.instance
            } else {
                instance = self.pedalboard('generateInstance', pluginData.uri)
            }

            self.data('pluginLoad')(plugin.uri, instance, plugin.x, plugin.y,
                function (ok) {
                    if (!ok) {
                        return
                    }
                    var symbol, value
                    for (var i in plugin.ports) {
                        symbol = plugin.ports[i].symbol
                        value  = plugin.ports[i].value
                        self.pedalboard('setPortWidgetsValue', instance, symbol, value)
                    }

                    self.pedalboard('addPlugin', pluginData, instance, plugin.bypassed, plugin.x, plugin.y, {}, function () {
                            loadPlugin(pluginsData)
                        }
                    )
                })
        }

        // Create needed hardware ports
        createHardwarePorts = function () {
            if (data.hardware) {
                var symbol
                for (var i=1, count=data.hardware.audio_ins; i<=count; i++) {
                    symbol = (i < 3) ? ('/graph/capture_' + i) : ('/graph/audio_from_slave_' + (i-2))
                    var hw = $('<div class="ignore-arrive hardware-output" mod-port-index="' + i + '" title="Hardware Capture ' + i + '">')
                    self.pedalboard('addHardwareOutput', hw, symbol, 'audio')
                }
                for (var i=1, count=data.hardware.audio_outs; i<=count; i++) {
                    symbol = (i < 3) ? ('/graph/playback_' + i) : ('/graph/audio_to_slave_' + (i-2))
                    var hw = $('<div class="ignore-arrive hardware-input" mod-port-index="' + i + '" title="Hardware Playback ' + i + '">')
                    self.pedalboard('addHardwareInput', hw, '/graph/playback_' + i, 'audio')
                }
                for (var i=1, count=data.hardware.cv_ins; i<=count; i++) {
                    var hw = $('<div class="ignore-arrive hardware-output" mod-port-index="' + i + '" title="Hardware CV Capture ' + i + '">')
                    self.pedalboard('addHardwareOutput', hw, '/graph/cv_capture_' + i + '_in', 'cv')
                }
                for (var i=1, count=data.hardware.cv_outs; i<=count; i++) {
                    var hw = $('<div class="ignore-arrive hardware-input" mod-port-index="' + i + '" title="Hardware CV Playback ' + i + '">')
                    self.pedalboard('addHardwareInput', hw, '/graph/cv_playback_' + i + '_out', 'cv')
                }
                if (data.hardware.serial_midi_in) {
                    var hw = $('<div class="ignore-arrive hardware-output" mod-port-index="1" title="Hardware DIN MIDI In">')
                    self.pedalboard('addHardwareOutput', hw, '/graph/serial_midi_in', 'midi')
                }
                if (data.hardware.serial_midi_out) {
                    var hw = $('<div class="ignore-arrive hardware-input" mod-port-index="1" title="Hardware DIN MIDI Out">')
                    self.pedalboard('addHardwareInput', hw, '/graph/serial_midi_out', 'midi')
                }
                if (data.hardware.midi_merger_in) {
                    var hw = $('<div class="ignore-arrive hardware-output" mod-port-index="2" title="All MIDI In">')
                    self.pedalboard('addHardwareOutput', hw, '/graph/midi_merger_in', 'midi')
                }
                if (data.hardware.midi_merger_out) {
                    var hw = $('<div class="ignore-arrive hardware-input" mod-port-index="2" title="All MIDI Out">')
                    self.pedalboard('addHardwareInput', hw, '/graph/midi_merger_out', 'midi')
                }
                var portdata, pindex, prefix
                for (var i in data.hardware.midi_ins) {
                    portdata = data.hardware.midi_ins[i]
                    pindex   = parseInt(portdata.symbol.replace("midi_capture_",""))+1
                    var hw = $('<div class="ignore-arrive hardware-output" mod-port-index=' + pindex + ' title="Hardware ' + portdata.name + '">')
                    self.pedalboard('addHardwareOutput', hw, '/graph/' + portdata.symbol, 'midi')
                }
                for (var i in data.hardware.midi_outs) {
                    portdata = data.hardware.midi_outs[i]
                    pindex   = parseInt(portdata.symbol.replace("midi_playback_",""))+1
                    prefix   = portdata.name === 'MIDI Loopback' ? 'Virtual' : 'Hardware'
                    var hw = $('<div class="ignore-arrive hardware-input" mod-port-index=' + pindex + ' title="' + prefix + ' ' + portdata.name + '">')
                    self.pedalboard('addHardwareInput', hw, '/graph/' + portdata.symbol, 'midi')
                }
            }
            self.pedalboard('positionHardwarePorts')
            return connect()
        }

        // Loads next connection in queue
        var connect = function () {
            var conn = data.connections.pop()
            if (conn == null)
                // Queue is empty, let's load everything
                return finish()

            var source = conn.source
            var target = conn.target

            self.data('portConnect')(source, target,
                function (ok) {
                    if (!ok) {
                        return
                    }
                    finalActions.push(function () {
                        var plugins = $.extend({
                            'system': self
                        }, self.data('plugins'))

                        var output = $('[mod-port="/graph/' + source + '"]')
                        var  input = $('[mod-port="/graph/' + target + '"]')

                        self.pedalboard('connect', output.find('[mod-role=output-jack]'), input)
                    })
                    connect()
                })
        }

        var uris = []
        for (var i in data.plugins)
            uris.push(data.plugins[i].uri)

        if (data.width > 0 && data.height > 0) {
            // FIXME: finish this
            self.css({
                width: data.width,
                height: data.height,
                position: 'absolute'
            })
        }

        self.data('getPluginsData')(uris, loadPlugin)
    },

    // Register hardware inputs and outputs, elements that will be used to represent the audio inputs and outputs
    // that interface with the hardware.
    // Note that these are considered inputs and outputs from the pedalboard point of view: the outputs are
    // expected to be a source of sound, and so it's an input from the user perspective; the input is the
    // sound destination, so will be an output to user.
    addHardwareInput: function (element, symbol, portType) {
        var self = $(this)
        element.attr('mod-role', 'input-' + portType + '-port')
        element.attr('mod-port-symbol', symbol)
        element.attr('mod-port', symbol)
        self.pedalboard('makeInput', element, '')
        self.data('hwInputs').push(element)
        self.append(element)
    },

    addHardwareOutput: function (element, symbol, portType) {
        var self = $(this)
        element.attr('mod-role', 'output-' + portType + '-port')
        element.attr('mod-port-symbol', symbol)
        element.attr('mod-port', symbol)
        self.pedalboard('makeOutput', element, '')
        self.data('hwOutputs').push(element)
        self.append(element)
    },

    /* Make this element a draggable item that can be used to add effects to this pedalboard.
     * Plugin adding has the following workflow:
     * 1 - Application registers an HTML element as being an available plugin
     * 2 - User drags this element and drops in Pedalboard
     * 3 - Pedalboard calls a the application callback (pluginLoad option), with plugin uri, instanceID and
     *     another callback.
     * 4 - Application loads the plugin with given instance and calls the pedalboard callback,
     *     or communicate error to user
     * 5 - Pedalboard renders the plugin
     * Parameters are:
     *   - Plugin is a data structure as parsed by mod-python's modcommon.lv2.Plugin class.
     *   - draggableOptions will be passed as parameter to the draggable jquery ui plugin
     */
    registerAvailablePlugin: function (element, pluginData, draggableOptions) {
        var self = $(this)

        element.bind('pluginAdded', function (e, position) {
            var waiter = self.data('wait')
            var instance = self.pedalboard('generateInstance', pluginData.uri)
            waiter.startPlugin(instance, position)
            var pluginLoad = self.data('pluginLoad')
            pluginLoad(pluginData.uri, instance, position.x, position.y,
                function () {
                    /*
                    self.pedalboard('addPlugin', pluginData, instance, false, position.x, position.y)
                    setTimeout(function () {
                        self.pedalboard('adapt', true)
                    }, 1)
                    */
                    waiter.stopPlugin(instance, false)
                },
                function () {
                    self.data('replacementPlugin', null)
                    waiter.stopPlugin(instance, false)
                })
        })

        element.attr('mod-io-type', pluginData.iotype)

        var options = {
            defaultIconTemplate: DEFAULT_ICON_TEMPLATE,
            dummy: true,
        }
        var thumb = element.children(".thumb");
        var img = thumb.children("img");
        element.draggable($.extend(draggableOptions, {
            helper: function (event) {
                var dummy = $('<div class="mod-pedal ignore-arrive dummy">');
                var imgrect = img.position();
                imgrect.width = img.width();
                imgrect.height = img.height();
                var clickpos  = { x: event.offsetX,
                                  y: event.offsetY };
                var clickperc = { x: Math.min(imgrect.width, Math.max(0, (event.offsetX - imgrect.left))) / imgrect.width,
                                  y: Math.min(imgrect.height, Math.max(0, (event.offsetY - imgrect.top))) / imgrect.height };
                var pad = { left: parseInt(element.css("padding-left")),
                            top: parseInt(element.css("padding-top")) };
                var renderedVersion = [pluginData.builder,
                                       pluginData.microVersion,
                                       pluginData.minorVersion,
                                       pluginData.release].join('_');
                console.log(pluginData.buildEnvironment)

                dummy.data('overIcons', [])
                dummy.data('scale', self.data('scale'))

                $.ajax({
                    url: '/effect/get',
                    data: {
                        uri: pluginData.uri,
                        version: VERSION,
                        plugin_version: renderedVersion,
                    },
                    success: function (plugin) {
                        new GUI(plugin, options).renderDummyIcon(function (icon) {
                            dummy.attr('class', icon.attr('class'))
                            dummy.addClass('dragging')
                            dummy.css("transformOrigin", "0 0");
                            dummy.css("visibility", "hidden");
                            var children = icon.children();

                            var settle = function () {
                                var scale = self.data('scale');
                                var trans = 'scale(' + scale + ') ';
                                var w = icon.width();
                                var h = icon.height();
                                var tx = (pad.left + clickpos.x) / scale - clickperc.x * w;
                                var ty = (pad.top + clickpos.y) / scale - clickperc.y * h;
                                trans += 'translate(' + tx + 'px, ' + ty + 'px) ';
                                dummy.css({
                                    webkitTransform: trans,
                                    MozTransform: trans,
                                    msTransform: trans,
                                    transform: trans,
                                })
                                dummy.data('scale', scale);
                            }
                            children.resize(function () {
                                icon.width(children.width());
                                icon.height(children.height());
                                settle();
                                dummy.css("visibility", "visible");
                            })
                            dummy.append(children);
                        })
                    },
                    cache: !!pluginData.buildEnvironment,
                    dataType: 'json'
                })
                $('body').append(dummy)
                return dummy
            },
            handle: thumb
        }))
    },

    // Resize pedalboard size to fit whole window
    // This is a bit buggy, because if window size is reduced, a plugin may get out of the pedalboard
    // area and become unreacheble. To correct this, scaling must also be considered when calculating
    // dimensions
    fitToWindow: function () {
        var self = $(this)

        var old = {
            width: self.width(),
            height: self.height()
        }

        self.parent().css({
            width: $(window).width() - self.data('hmargins'),
            height: $(window).height() - self.data('vmargins')
        })

        var scale = self.data('baseScale')
        self.css({
            width: self.parent().width() / scale,
            height: self.parent().height() / scale,
        })

        var zoom = self.data('currentZoom')
        if (!zoom) {
            return false
        }

        zoom.screenX = zoom.screenX * self.width() / old.width
        zoom.screenY = zoom.screenY * self.height() / old.height

        self.data('windowSize')(self.width(), self.height())
        self.pedalboard('zoom', Math.min(self.data('scale'), scale), zoom.canvasX, zoom.canvasY, zoom.screenX, zoom.screenY, 0)
        self.pedalboard('adapt', true)

        return true
    },

    // Prevents dragging of whole dashboard when dragging of effect or jack starts
    preventDrag: function (prevent) {
        $(this).data('preventDrag', prevent)
    },

    // Moves the viewable area of the pedalboard
    drag: function (start) {
        var self = $(this)

        self.trigger('dragStart')

        var scale = self.data('scale')

        var canvasX = (start.pageX - self.offset().left) / scale
        var canvasY = (start.pageY - self.offset().top) / scale
        var screenX = start.pageX - self.parent().offset().left
        var screenY = start.pageY - self.parent().offset().top

        var moveHandler = function (e) {
            if (self.data('preventDrag'))
                return

            self.pedalboard('zoom', scale, canvasX, canvasY,
                screenX + e.pageX - start.pageX,
                screenY + e.pageY - start.pageY,
                0)
        }

        var upHandler = function (e) {
            $(document).unbind('mouseup', upHandler)
            $(document).unbind('mousemove', moveHandler)
        }

        $(document).bind('mousemove', moveHandler)
        $(document).bind('mouseup', upHandler)
    },

    // Changes the viewing scale of the pedalboard and position it in a way that
    // the (canvasX, canvasY) point of pedalboard will match the (screenX, screenY)
    // position of the screen. This way, when user uses the mousewheel to zoom, the
    // mouse will remain in the same point of the pedalboard while scale is changed.
    // Duration is the time in miliseconds used to animate the zoom, default is 400.
    zoom: function (scale, canvasX, canvasY, screenX, screenY, duration) {
        var self = $(this)
        self.data('currentZoom', {
            scale: scale,
            canvasX: canvasX,
            canvasY: canvasY,
            screenX: screenX,
            screenY: screenY
        })

        // This is the offset put by browser, must be compensated
        var autoOffsetX = -self.width() * (scale - 1) / 2
        var autoOffsetY = -self.height() * (scale - 1) / 2

        // This is the position of this point in pixels
        var absoluteX = canvasX * scale
        var absoluteY = canvasY * scale

        var offsetX = -autoOffsetX - absoluteX + screenX
        var offsetY = -autoOffsetY - absoluteY + screenY

        var maxOffsetX = -autoOffsetX
        var minOffsetX = -autoOffsetX - self.width() * scale + self.parent().width()
        var maxOffsetY = -autoOffsetY
        var minOffsetY = -autoOffsetY - self.height() * scale + self.parent().height()

        offsetX = Math.max(minOffsetX, offsetX)
        offsetX = Math.min(maxOffsetX, offsetX)
        offsetY = Math.max(minOffsetY, offsetY)
        offsetY = Math.min(maxOffsetY, offsetY)

        self.data('offsetX', offsetX)
        self.data('offsetY', offsetY)

        if (self.data('skipAnimations')) {
            duration = 0
        } else if (duration == null) {
            duration == 400
        }

        // workaround some browsers that send a zero value at step start, which is an invalid scale
        var usingInitialZero = false
        var oldScale = self.data('scale')
        var newScale = scale

        self.animate({
            scale: scale,
            top: offsetY,
            left: offsetX
        }, {
            duration: duration,
            step: function (value, prop) {
                if (prop.prop != 'scale') {
                    return
                }
                // if we receive a value of 0, which is impossible for the scale variable, trigger workaround
                if (value == 0) {
                    usingInitialZero = true
                }
                if (usingInitialZero) {
                    var per = value / newScale
                    value = (oldScale * (1.0 - per)) + (newScale * per)
                }

                self.css({
                    webkitTransform: 'scale(' + value + ')',
                    MozTransform: 'scale(' + value + ')',
                    msTransform: 'scale(' + value + ')',
                    transform: 'scale(' + value + ')',
                })
                self.data('scale', value)
            },
        })
    },

    // Changes the scale of the pedalboard and centers view on (x, y)
    zoomAt: function (scale, x, y, duration) {
        var self = $(this)

        var screenX = self.parent().width() / 2
        var screenY = self.parent().height() / 2
        self.pedalboard('zoom', scale, x, y, screenX, screenY, duration)
    },

    // Zoom to desired plugin
    focusPlugin: function (plugin) {
        var self = $(this)
        var scale = self.data('scale')
        var x = plugin.position().left / scale + plugin.width() / 2
        var y = plugin.position().top / scale + plugin.height() / 2
        self.pedalboard('zoomAt', 1, x, y)
    },

    // Increase zoom level
    zoomIn: function () {
        var self = $(this)
        var scale = self.data('scale')
        var newScale
        if (scale == 1)
            return

        if (scale >= 0.5)
            newScale = 1
        else
            newScale = 0.5
        if (newScale > scale) {
            var x = $(window).width() / 2
            var y = $(window).height() / 2
            var canvasX = (x - self.offset().left) / scale
            var canvasY = (y - self.offset().top) / scale
            var screenX = x - self.parent().offset().left
            var screenY = y - self.parent().offset().top

            self.pedalboard('zoom', newScale, canvasX, canvasY, screenX, screenY, 500)
        }
    },

    // Decrease zoom level
    zoomOut: function () {
        var self = $(this)
        var scale = self.data('scale')
        var newScale
        if (scale == self.data('minScale'))
            return
        if (scale <= 0.5)
            newScale = self.data('minScale')
        else
            newScale = 0.5
        if (newScale < scale) {
            var x = $(window).width() / 2
            var y = $(window).height() / 2
            var canvasX = (x - self.offset().left) / scale
            var canvasY = (y - self.offset().top) / scale
            var screenX = x - self.parent().offset().left
            var screenY = y - self.parent().offset().top

            self.pedalboard('zoom', newScale, canvasX, canvasY, screenX, screenY, 500)
        }
    },

    // Enlarge the pedalboard to a minimum size capable of accommodating all plugins.
    adapt: function (forcedUpdate) {
        var self = $(this)
        // First, get the minmum bounding rectangle,
        // given by minX, maxX, minY and maxY
        var minX, maxX, minY, maxY, rightMargin, w, h, x, y, plugin, pos
        //var pedals = self.find('.js-effect')
        var plugins = self.data('plugins')
        var scale = self.data('scale')
        minX = 0
        maxX = self.width()
        minY = 0
        maxY = self.height()
        rightMargin = 150
        var instance
        for (instance in plugins) {
            plugin = plugins[instance]
            if (!plugin.position) continue
            pos = plugin.position()
            w = plugin.width()
            h = plugin.height()
            x = pos.left / scale
            y = pos.top / scale

            minX = Math.min(minX, x)
            maxX = Math.max(maxX, x + w + rightMargin)
            minY = Math.min(minY, y)
            maxY = Math.max(maxY, y + h)
        }

        // Now calculate how much to increase in width and height,
        // and how much to move in left and top
        var wDif = 0
        var hDif = 0
        var left = 0
        var top = 0
        w = self.width()
        h = self.height()
        if (minX < 0) {
            wDif -= minX
            left -= minX
        }
        if (maxX > w)
            wDif += maxX - w
        if (minY < 0) {
            hDif -= minY
            top -= minY
        }
        if (maxY > h)
            hDif += maxY - h

        if (wDif == 0 && hDif == 0 && ! forcedUpdate) {
            // nothing has changed
            return
        }

        var scale = self.data('scale')

        // now let's modify desired width and height to keep
        // screen ratio
        var ratio = w / h
        w += wDif
        h += hDif
        if (ratio > w / h) // we have to increase width to keep ratio
            w = ratio * h
        else if (ratio < w / h) // increse height to keep ratio
            h = w / ratio

        var time = (self.data('skipAnimations') || forcedUpdate) ? 0 : 400

        // Move animate everything: move plugins, scale and position
        // canvas

        var drawFactory = function (plugin) {
            return function () {
                self.pedalboard('drawPluginJacks', plugin)
            }
        }

        // move plugins
        for (instance in plugins) {
            plugin = plugins[instance]
            if (!plugin.position) continue
            pos = plugin.position()
            old_x = Math.round(pos.left / scale)
            old_y = Math.round(pos.top / scale)
            x = parseInt(plugin.css('left')) + left
            y = parseInt(plugin.css('top')) + top
            if (old_x == x && old_y == y) {
                continue
            }
            plugin.animate({
                left: x,
                top: y
            }, {
                duration: time,
                step: drawFactory(plugin),
                complete: drawFactory(plugin)
            })
            self.data('pluginMove')(instance, x, y)
        }

        var viewWidth = self.parent().width()
        var viewHeight = self.parent().height()
        var newScale = viewWidth / w

        self.data('minScale', newScale)

        // if we are at scale 1, it is very much likely that we do not want to zoom out now
        // keep current scale if that is the case
        if (scale == 1 && ! forcedUpdate) {
            var width = viewWidth / newScale
            var height = viewHeight / newScale
            self.width(width)
            self.height(height)
            self.pedalboard('positionHardwarePorts')
            return
        }

        // workaround some browsers that send a zero value at step start, which is an invalid scale
        var usingInitialZero = false
        var oldScale = scale

        self.animate({
            scale: newScale,
        }, {
            duration: time,
            step: function (scale, prop) {
                if (prop.prop != 'scale') {
                    return
                }
                // if we receive a scale of 0, which is impossible for the scale variable, trigger workaround
                if (scale == 0) {
                    usingInitialZero = true
                }
                if (usingInitialZero) {
                    var per = scale / newScale
                    scale = (oldScale * (1.0 - per)) + (newScale * per)
                }

                var width = viewWidth / scale
                var height = viewHeight / scale
                var offsetX = (viewWidth - width) / 2
                var offsetY = (viewHeight - height) / 2
                self.width(width)
                self.height(height)
                self.css({
                    webkitTransform: 'scale(' + scale + ')',
                    MozTransform: 'scale(' + scale + ')',
                    msTransform: 'scale(' + scale + ')',
                    transform: 'scale(' + scale + ')',
                    top: offsetY,
                    left: offsetX,
                })
                self.pedalboard('positionHardwarePorts')
                self.data('scale', scale)
                self.data('offsetX', offsetX)
                self.data('offsetY', offsetY)
            },
        })

    },

    scheduleAdapt: function (forcedUpdate) {
        var self = $(this)

        if (self.data('skipAnimations')) {
            return
        }

        if (forcedUpdate) {
            self.data('adaptForcedUpdate', true)
        }

        var firstTime = self.data('adaptFirstTime')

        var callAdaptLater = function () {
            var curTime2 = self.data('adaptTime')

            if (curTime2 <= 0) {
                if (firstTime) {
                    if (document.readyState == "complete") {
                        // ready to roll
                        firstTime = false
                        self.data('adaptFirstTime', false)
                    } else {
                        // still not ready
                        setTimeout(callAdaptLater, 250)
                        return
                    }
                }

                // proceed
                var forcedUpdate = self.data('adaptForcedUpdate')
                self.data('adaptForcedUpdate', false)
                self.data('adaptTime', 0)
                self.pedalboard('positionHardwarePorts')
                self.data('pedalboardFinishedLoading')(function () {
                    self.pedalboard('adapt', forcedUpdate)
                    self.data('wait').stopIfNeeded()
                })

                //console.log("done!")

            } else {
                // decrease timer
                self.data('adaptTime', curTime2-20)
                setTimeout(callAdaptLater, 200)
                //console.log("pending...", curTime2)
            }
        }

        var curTime = self.data('adaptTime')

        if (curTime == 0) {
            // first time, setup everything
            self.data('adaptTime', firstTime ? 201 : 101)
            setTimeout(callAdaptLater, 1)
        } else if (curTime < 500) {
            // not first time, increase timer
            self.data('adaptTime', curTime + (firstTime ? 4 : 1))
        }
    },

    // Position the hardware ports as to be evenly distributed vertically in pedalboard.
    // Output ports are positioned at left and input ports at right.
    positionHardwarePorts: function () {
        var self = $(this)

        var height = self.height() - self.data('bottomMargin')

        var adjust = function (elements, css) {
            var top = height / (elements.length + 1)
            var i, el
            elements.sort(function(e1, e2) {
                var e1_audio = e1.hasClass('mod-audio-output') || e1.hasClass('mod-audio-input')
                var e2_audio = e2.hasClass('mod-audio-output') || e2.hasClass('mod-audio-input')
                var e1_midi  = e1.hasClass('mod-midi-output')  || e1.hasClass('mod-midi-input')
                var e2_midi  = e2.hasClass('mod-midi-output')  || e2.hasClass('mod-midi-input')
                var e1_cv    = e1.hasClass('mod-cv-output')    || e1.hasClass('mod-cv-input')
                var e2_cv    = e2.hasClass('mod-cv-output')    || e2.hasClass('mod-cv-input')
                // FIXME - there's got to be a better way..
                if ((e1_audio && e2_audio) || (e1_midi && e2_midi) || (e1_cv && e2_cv)) {
                    return (parseInt(e1.attr('mod-port-index')) > parseInt(e2.attr('mod-port-index'))) ? 1 : -1;
                } else if (e1_cv || e2_cv) {
                    return e1_cv ? 1 : -1;
                } else {
                    return e1_midi ? 1 : -1;
                }
            })
            for (i = 0; i < elements.length; i++) {
                el = elements[i]
                el.css($.extend(css, {
                    top: top * (i + 1) - el.height() / 2
                }))
            }
        }

        adjust(self.data('hwInputs'), {
            right: 0
        })
        adjust(self.data('hwOutputs'), {
            left: 0
        })

        // Redraw all cables that connect to or from hardware ports
        //self.data('connectionManager').iterateInstance(':system:', function (jack) {
        self.data('connectionManager').iterate(function (jack) {
            self.pedalboard('drawJack', jack)
        })
    },

    // Resets the pedalboard size and zoom to initial configuration
    resetSize: function () {
        var self = $(this)
        var scale = self.data('baseScale')
        var w = self.parent().width() / scale
        var h = self.parent().height() / scale
        self.css({
            width: w,
            height: h,
            position: 'absolute'
        })

        self.data('minScale', scale)

        self.pedalboard('zoomAt', scale, w / 2, h / 2, 0)
        self.data('windowSize')(self.width(), self.height())

        self.pedalboard('positionHardwarePorts')
    },

    /*********
     * Plugins
     */

    // Generate an instance for a new plugin.
    // TODO: check with ingen if instance does not exist
    generateInstance: function (uri) {
        var self = $(this)
        // copied from ingen's algorithm to get a valid instance symbol
        var last_uri_delim = function (s) {
            for (var i = s.length-1; i > 0; --i) {
                switch(s[i]) {
                    case '/': case '?': case '#': case ':':
                        return i
                }
            }
            return -1
        }
        var re = /[^_a-zA-Z0-9]+/g
        var instance = uri
        var last_delim = last_uri_delim(instance)
        while (last_delim != -1 &&
                !instance.substr(last_delim, instance.length-1).match(/[a-zA-Z0-9]/)) {
            instance = instance.substr(0, last_delim)
            last_delim = last_uri_delim(instance)
        }
        instance = instance.substr(last_delim+1, instance.length-1).replace(re, "_")
        if (instance[0].match(/[0-9]/)) // instance names cant start with numbers
            instance = "_" + instance
        var i = 1;
        instance = '/graph/' + instance
        // the prefix "/graph/cv_" is reserved, make sure we dont use it
        if (instance === '/graph/cv') {
            instance = instance + 'x'
        }
        if (instance in self.data('plugins')) {
            instance = instance + "_1"
            while (instance in self.data('plugins')) {
                i = i + 1
                instance = instance.slice(0, -1) + i
            }
        }
        return instance
    },

    // Adds a plugin to pedalboard. This is called after the application loads the plugin with the
    // instance, now we need to put it in screen.
    addPlugin: function (pluginData, instance, bypassed, x, y, guiOptions, renderCallback, skipModified) {
        var self = $(this)
        var scale = self.data('scale')

        var obj = {}
        var options = $.extend({
            dragStart: function () {
                self.trigger('pluginDragStart', instance)
                obj.icon.addClass('dragging')
                obj.icon.css({'z-index': self.data('z_index')+1})
                self.data('z_index', self.data('z_index')+1)
                return true
            },
            drag: function (e, ui) {
                self.trigger('pluginDrag', instance)
                var scale = self.data('scale')
                ui.position.left /= scale
                ui.position.top /= scale
                self.trigger('modified')
                self.pedalboard('drawPluginJacks', obj.icon)
            },
            dragStop: function (e, ui) {
                self.trigger('pluginDragStop')
                self.trigger('modified')
                self.pedalboard('drawPluginJacks', obj.icon)
                obj.icon.removeClass('dragging')
                self.data('pluginMove')(instance, ui.position.left, ui.position.top)
                self.pedalboard('adapt', false)
            },
            click: function (event) {
                obj.icon.css({'z-index': self.data('z_index')+1})
                self.pedalboard('drawPluginJacks', obj.icon)
                self.data('z_index', self.data('z_index')+1)

                // only zoom-in if event was triggered by a click on the drag-handle
                // this prevents zoom-in when dragging a control and releasing the mouse over an empty area of the plugin
                if (! $(event.target).hasClass("mod-drag-handle"))
                    return;

                // setTimeout avoids cable drawing bug
                setTimeout(function () {
                    self.pedalboard('focusPlugin', obj.icon)
                }, 0)
            },
            change: function (port, value) {
                self.data('pluginParameterChange')(port, value)
            },
            patchGet: function (uri) {
                self.data('pluginPatchGet')(instance, uri)
            },
            patchSet: function (uri, valuetype, value) {
                self.data('pluginPatchSet')(instance, uri, valuetype, value)
            },
            presetLoad: function (uri) {
                self.data('pluginPresetLoad')(instance, uri, function (ok) {
                        if (ok) {
                            // TODO Handle this error
                        }
                    })
            },
            presetSaveNew: function (name, callback) {
                self.data('pluginPresetSaveNew')(instance, name, function (resp) {
                        if (resp.ok) {
                            callback(resp)
                        }
                    })
            },
            presetSaveReplace: function (uri, bundlepath, name, callback) {
                self.data('pluginPresetSaveReplace')(instance, uri, bundlepath, name, function (resp) {
                        if (resp.ok) {
                            callback(resp)
                        }
                    })
            },
            presetDelete: function (uri, bundlepath, callback) {
                self.data('pluginPresetDelete')(instance, uri, bundlepath, function (ok) {
                        if (ok) {
                            callback()
                        }
                    })
            },
            bypassed: bypassed ? 1 : 0,
            defaultIconTemplate: DEFAULT_ICON_TEMPLATE,
            defaultSettingsTemplate: DEFAULT_SETTINGS_TEMPLATE
        }, guiOptions)

        /* FIXME this is not used anywhere. remove?
        var preset_list = []
        for (var key in pluginData['presets']) {
            preset_list.push({
                label: pluginData['presets'][key]['label'],
                uri: pluginData['presets'][key]['uri']
            })
        }
        pluginData = $.extend({
            preset_list: preset_list
        }, pluginData)
        */
        var pluginGui = new GUI(pluginData, options)

        pluginGui.render(instance, function (icon, settings) {
            obj.icon = icon
            icon.attr('mod-uri', escape(pluginData.uri));

            if (pluginData.licensed < 0) {
                // This is a TRIAL plugin
                icon.find('[mod-role="drag-handle"]').addClass('demo-plugin').addClass('demo-plugin-light');
                self.data('notifyDemoPluginLoaded')()
            }

            self.data('plugins')[instance] = icon

            if (! skipModified) {
                self.trigger('modified')
            }

            icon.data('label', pluginData.label)
            icon.data('uri', pluginData.uri)
            icon.data('gui', pluginGui)
            icon.data('settings', settings)
            icon.data('instance', instance)

            var address, symbol, port
            /*
            var hardware = self.data('hardwareManager')
            hardware.instanceAdded(instance)
            */

            var addressFactory = function (port) {
                return function () {
                    if ($(this).hasClass("disabled")) {
                        return
                    }
                    var hardware = self.data('hardwareManager')
                    hardware.open(instance, port, pluginData.label)
                }
            }

            for (symbol in pluginGui.controls) {
                port = pluginGui.controls[symbol]
                if (symbol == ':bypass') {
                    address = settings.find('[mod-role=bypass-address]')
                } else if (symbol == ':presets') {
                    address = settings.find('[mod-role=presets-address]')
                } else {
                    address = settings.find('[mod-role=input-control-address][mod-port-symbol=' + symbol + ']')
                }
                if (address.length == 0) {
                    continue
                }
                address.click(addressFactory(port))
            }

            // Find elements with mod-role of audio/midi input/output ports and assign functionality to them
            var types = ['audio', 'midi', 'cv']
            var directions = ['input', 'output']
            var j, k, type, direction, method
            for (i = 0; i < types.length; i++) {
                type = types[i]
                for (j = 0; j < directions.length; j++) {
                    direction = directions[j]
                    if (!pluginData.ports[type] || !pluginData.ports[type][direction])
                        continue
                    for (k = 0; k < pluginData.ports[type][direction].length; k++) {
                        symbol = pluginData.ports[type][direction][k].symbol
                        element = icon.find('[mod-role=' + direction + '-' + type + '-port][mod-port-symbol=' + symbol + ']')
                        if (element.length == 0)
                            continue
                        // call either makeInput or makeOutput
                        var method = 'make' + direction.charAt(0).toUpperCase() + direction.slice(1)
                        self.pedalboard(method, element, instance)
                    }
                }
            }

            icon.mousedown(function () {
                self.pedalboard('preventDrag', true)
                var upHandler = function () {
                    self.pedalboard('preventDrag', false)
                    $('body').unbind('mouseup', upHandler)
                }
                $('body').bind('mouseup', upHandler)
            })

            icon.attr('mod-io-type', pluginData.iotype)

            icon.droppable({
                accept: '[mod-role=available-plugin][mod-io-type="'+pluginData.iotype+'"]',
                tolerance: 'custom-replace',
                activeClass: 'possible-replaceable-drop',
                drop: function (event, ui) {
                    // icon.removeClass('replaceable-drop')
                    var overIcons = ui.helper.data('overIcons');
                    if (overIcons.length === 0 || overIcons[overIcons.length-1] != icon) {
                        return;
                    }
                    ui.helper.data('overIcons', []);

                    var instance = event.target.getAttribute('mod-instance')
                    var connMgr = self.data('connectionManager')
                    var replacement = {
                        'instance': instance,
                        'audio': [],
                        'midi': [],
                    }

                    connMgr.iterateInstance(instance, function (jack) {
                        var input   = jack.data('destination')
                        var inport  = input.attr('mod-port')
                        var output  = jack.data('origin')
                        var outport = output.attr('mod-port')
                        var type
                        if (input.hasClass('mod-audio-input')) {
                            type = 'audio'
                        } else if (input.hasClass('mod-midi-input')) {
                            type = 'midi'
                        } else {
                            return
                        }
                        if (startsWith(inport, instance+'/')) {
                            var symbol = inport.slice(instance.length+1)
                            console.log(symbol, pluginData.ports[type]['input'])
                            for (var i = 0; i < pluginData.ports[type]['input'].length; i++) {
                                if (pluginData.ports[type]['input'][i].symbol == symbol) {
                                    inport = i
                                    break;
                                }
                            }
                        }
                        if (startsWith(outport, instance+'/')) {
                            var symbol = outport.slice(instance.length+1)
                            console.log(symbol, pluginData.ports[type]['output'])
                            for (var i = 0; i < pluginData.ports[type]['output'].length; i++) {
                                if (pluginData.ports[type]['output'][i].symbol == symbol) {
                                    outport = i
                                    break;
                                }
                            }
                        }
                        replacement[type].push([inport, outport])
                    })

                    console.log(replacement)

                    self.data('replacementPlugin', replacement)
                    self.pedalboard('removePlugin', instance, pluginData.ports)
                },
                over: function (event, ui) {
                    var overIcons = ui.helper.data('overIcons');
                    if (overIcons.length !== 0) {
                        var oldIcon = overIcons[overIcons.length-1]
                        oldIcon.removeClass('replaceable-drop')
                        oldIcon.find('[mod-role="drag-handle"]').removeClass('replaceable-drop')
                    }
                    icon.addClass('replaceable-drop')
                    icon.find('[mod-role="drag-handle"]').addClass('replaceable-drop')
                    overIcons.push(icon)
                },
                out: function (event, ui) {
                    var overIcons = ui.helper.data('overIcons');
                    remove_from_array(overIcons, icon)
                    if (icon.hasClass('replaceable-drop')) {
                        icon.removeClass('replaceable-drop')
                        icon.find('[mod-role="drag-handle"]').removeClass('replaceable-drop')
                        if (overIcons.length !== 0) {
                            var oldIcon = overIcons[overIcons.length-1]
                            oldIcon.addClass('replaceable-drop')
                            oldIcon.find('[mod-role="drag-handle"]').removeClass('replaceable-drop')
                        }
                    }
                },
            })

            var actions = $('<div>').addClass('ignore-arrive').addClass('mod-actions').appendTo(icon)
            if (pluginData.hasExternalUI) {
                $('<div>').addClass('mod-external-ui').click(function () {
                    self.pedalboard('finishConnection')
                    self.data('showExternalUI')(instance)
                    return false
                }).appendTo(actions)
            }
            $('<div>').addClass('mod-information').click(function () {
                self.pedalboard('finishConnection')
                self.data('showPluginInfo')(pluginData)
                return false
            }).appendTo(actions)
            $('<div>').addClass('mod-settings').click(function () {
                self.pedalboard('finishConnection')
                settings.window('open')
                return false
            }).appendTo(actions)
            $('<div>').addClass('mod-remove').click(function () {
                self.pedalboard('finishConnection')
                self.pedalboard('removePlugin', instance, pluginData.ports)
                return false
            }).appendTo(actions)

            settings.window({
                windowName: "Plugin Settings",
                windowManager: self.data('windowManager')
            }).appendTo($('body'))
            icon.css({
                'z-index': self.data('z_index'),
                position: 'absolute',
                left: x,
                top: y
            }).appendTo(self)

            // adjust position of cv out checkboxes if needed
            var lastCvPosY = -1, lastCvElem
            for (k = 0; k < pluginData.ports['cv']['output'].length; k++) {
                symbol = pluginData.ports['cv']['output'][k].symbol
                element = icon.find('[mod-role=' + direction + '-' + type + '-port][mod-port-symbol=' + symbol + ']')
                if (element.length == 0)
                    continue
                var curCvPosY = element.position().top
                if (lastCvPosY != -1 && Math.abs(curCvPosY - lastCvPosY) < 50) {
                    element.find('.output-cv-checkbox').css({left:'50px',top:'10px'})
                    lastCvElem.find('.output-cv-checkbox').css({left:'50px',top:'10px'})
                }
                lastCvElem = element
                lastCvPosY = curCvPosY
            }

            self.data('z_index', self.data('z_index')+1)
            if (renderCallback)
                renderCallback()
        })

        var replacementPlugin = self.data('replacementPlugin')
        self.data('replacementPlugin', null)

        if (replacementPlugin) {
            var hasConnectionsErrors = 0,
                connectionsDone = 0,
                connectionsToDo = replacementPlugin.audio.length + replacementPlugin.midi.length;

            function finalizeConnection(ok) {
                hasConnectionsErrors |= !ok;

                if (++connectionsDone == connectionsToDo && hasConnectionsErrors) {
                    new Notification('error', "Failed to automatically reconnect all ports", 5000)
                }
            }

            for (var i in replacementPlugin.audio) {
                var ports = replacementPlugin.audio[i]
                var inport, outport
                if (typeof(ports[0]) === 'number') {
                    inport = pluginData.ports['audio']['input'][ports[0]]
                    if (inport === undefined) {
                        continue
                    }
                    inport = instance+'/'+inport.symbol
                } else {
                    inport = replacementPlugin.audio[i][0]
                }
                if (typeof(ports[1]) === 'number') {
                    outport = pluginData.ports['audio']['output'][ports[1]]
                    if (outport === undefined) {
                        continue
                    }
                    outport = instance+'/'+outport.symbol
                } else {
                    outport = replacementPlugin.audio[i][1]
                }

                self.data('portConnect')(outport, inport, finalizeConnection)
            }

            for (var i in replacementPlugin.midi) {
                var ports = replacementPlugin.midi[i]
                var inport, outport
                if (typeof(ports[0]) === 'number') {
                    inport = pluginData.ports['midi']['input'][ports[0]]
                    if (inport === undefined) {
                        continue
                    }
                    inport = instance+'/'+inport.symbol
                } else {
                    inport = replacementPlugin.midi[i][0]
                }
                if (typeof(ports[1]) === 'number') {
                    outport = pluginData.ports['midi']['output'][ports[1]]
                    if (outport === undefined) {
                        continue
                    }
                    outport = instance+'/'+outport.symbol
                } else {
                    outport = replacementPlugin.midi[i][1]
                }

                self.data('portConnect')(outport, inport, finalizeConnection)
            }
        }
    },

    // Remove "Trial" watermark from all instances of a plugin
    license: function(uri) {
        var self = $(this);
        var plugins = self.data('plugins');

        var icon;
        for (var instance in plugins) {
            icon = plugins[instance]
            if (icon && icon.data && icon.data('uri') == uri) {
                icon.find('[mod-role="drag-handle"]').removeClass('demo-plugin').removeClass('demo-plugin-light');
            }
        }
    },

    getLabel: function (instance) {
        var plugin = $(this).data('plugins')[instance]
        if (plugin && plugin.data) {
            return plugin.data('label')
        }
        return "effect"
    },

    getGui: function (instance) {
        var plugin = $(this).data('plugins')[instance]
        if (plugin && plugin.data) {
            return plugin.data('gui')
        }
        return null
    },

    getLoadedPluginURIs: function () {
        var plugin, plugins = $(this).data('plugins')
        var uri, uris = {}

        for (var i in plugins) {
            plugin = plugins[i]
            if (plugin != null && plugin.data != null) {
                uri = plugin.data('uri')
                if (uri != null) {
                    uris[uri] = true
                }
            }
        }

        return Object.keys(uris)
    },

    setPortEnabled: function (instance, symbol, enabled, feedback, forceAddress, momentaryMode) {
        var self = $(this)
        var targetname = '.mod-pedal[mod-instance="'+instance+'"]'
        var callbackId = instance+'/'+symbol+":enabled"
        var gui = self.pedalboard('getGui', instance)

        if (gui && self.find(targetname).length) {
            if (enabled || feedback) {
                gui.enable(symbol)
            } else {
                gui.disable(symbol)
            }
            if (forceAddress) {
              gui.addressPort(symbol, feedback, momentaryMode)
            }

        } else {
            var cb = function () {
                delete self.data('callbacksToArrive')[callbackId]
                self.unbindArrive(targetname, cb)

                var gui = self.pedalboard('getGui', instance)
                if (enabled || feedback) {
                    gui.enable(symbol)
                } else {
                    gui.disable(symbol)
                }

                if (forceAddress) {
                  gui.addressPort(symbol, feedback, momentaryMode)
                }
            }

            self.pedalboard('addUniqueCallbackToArrive', cb, targetname, callbackId)
        }
    },

    setPortWidgetsValue: function (instance, symbol, value) {
        var self = $(this)
        var targetname = '.mod-pedal[mod-instance="'+instance+'"]'
        var callbackId = instance+'/'+symbol+":value"
        var gui = self.pedalboard('getGui', instance)

        if (gui && self.find(targetname).length) {
            gui.setPortWidgetsValue(symbol, value, null, true)

        } else {
            var cb = function () {
                delete self.data('callbacksToArrive')[callbackId]
                self.unbindArrive(targetname, cb)

                var gui = self.pedalboard('getGui', instance)
                gui.setPortWidgetsValue(symbol, value, null, true)
            }

            self.pedalboard('addUniqueCallbackToArrive', cb, targetname, callbackId)
        }
    },

    setOutputPortValue: function (instance, symbol, value) {
        var self = $(this)
        var gui = self.pedalboard('getGui', instance)

        if (gui) {
            gui.setOutputPortValue(symbol, value)

        } else {
            var targetname = '.mod-pedal[mod-instance="'+instance+'"]'
            var callbackId = instance+'/'+symbol+":value"

            var cb = function () {
                delete self.data('callbacksToArrive')[callbackId]
                self.unbindArrive(targetname, cb)

                var gui = self.pedalboard('getGui', instance)
                gui.setOutputPortValue(symbol, value)
            }

            self.pedalboard('addUniqueCallbackToArrive', cb, targetname, callbackId)
        }
    },

    setReadableParameterValue: function (instance, uri, valuetype, valuedata) {
        var self = $(this)
        var gui = self.pedalboard('getGui', instance)

        if (gui) {
            gui.setReadableParameterValue(uri, valuetype, valuedata)

        } else {
            var targetname = '.mod-pedal[mod-instance="'+instance+'"]'
            var callbackId = instance+'@'+uri+'@value'

            var cb = function () {
                delete self.data('callbacksToArrive')[callbackId]
                self.unbindArrive(targetname, cb)

                var gui = self.pedalboard('getGui', instance)
                gui.setReadableParameterValue(uri, valuetype, valuedata)
            }

            self.pedalboard('addUniqueCallbackToArrive', cb, targetname, callbackId)
        }
    },

    setWritableParameterValue: function (instance, uri, valuetype, valuedata) {
        var self = $(this)
        var targetname = '.mod-pedal[mod-instance="'+instance+'"]'
        var callbackId = instance+'@'+uri+'@value'
        var gui = self.pedalboard('getGui', instance)

        if (gui && self.find(targetname).length) {
            gui.setWritableParameterValue(uri, valuetype, valuedata, null, true)

        } else {
            var cb = function () {
                delete self.data('callbacksToArrive')[callbackId]
                self.unbindArrive(targetname, cb)

                var gui = self.pedalboard('getGui', instance)
                gui.setWritableParameterValue(uri, valuetype, valuedata, null, true)
            }

            self.pedalboard('addUniqueCallbackToArrive', cb, targetname, callbackId)
        }
    },

    selectPreset: function (instance, value) {
        var self = $(this)
        var gui = self.pedalboard('getGui', instance)

        if (gui) {
            gui.selectPreset(value)

        } else {
            var targetname = '.mod-pedal[mod-instance="'+instance+'"]'
            var callbackId = instance+'/'+":presets"

            var cb = function () {
                delete self.data('callbacksToArrive')[callbackId]
                self.unbindArrive(targetname, cb)

                var gui = self.pedalboard('getGui', instance)
                gui.selectPreset(value)
            }

            self.pedalboard('addUniqueCallbackToArrive', cb, targetname, callbackId)
        }
    },

    addUniqueCallbackToArrive: function (cb, targetname, callbackId) {
        var self = $(this);
        var callbacks = self.data('callbacksToArrive'),
            currentCallback = callbacks[callbackId];

        if (currentCallback) {
            self.unbindArrive(targetname, currentCallback)
        }

        callbacks[callbackId] = cb
        self.arrive(targetname, cb)
    },

    // Redraw all connections from or to a plugin
    drawPluginJacks: function (plugin) {
        var self = $(this)
        var myjacks = []
        var connMgr = self.data('connectionManager')
        connMgr.iterateInstance(plugin.data('instance'), function (jack) {
            myjacks.push($(jack.data('svg')._container))
        })
        $('.hasSVG.cable-connected').filter(function(e) {!(e in myjacks)}).css({'z-index': 0})

        connMgr.iterateInstance(plugin.data('instance'), function (jack) {
            self.pedalboard('drawJack', jack)
            $(jack.data('svg')._container).css({ 'z-index': self.data("z_index")-1, 'pointer-events': 'none'})
        })
    },

    // Removes a plugin from pedalboard. (from the system?)
    // Calls application removal function with proper removal callback
    removePlugin: function (instance, ports) {
        var self = $(this)
        var pluginRemove = self.data('pluginRemove')
        pluginRemove(instance, function () {
          // Remove plugin's cv output ports from harware manager
          if (ports && ports.cv && ports.cv.output) {
            for (var i = 0; i < ports.cv.output.length; i++) {
              self.data('hardwareManager').removeCvOutputPort('/cv' + instance + '/' + ports.cv.output[i].symbol)
            }
          }
        })
    },

    removeItemFromCanvas: function (instance) {
        var self = $(this)
        var plugins = self.data('plugins')
        var connMgr = self.data('connectionManager')

        if (instance in plugins) {
            connMgr.iterateInstance(instance, function (jack) {
                var input = jack.data('destination')
                jack.data('canvas').remove()
                jack.remove()
                self.pedalboard('packJacks', input)
            })
            connMgr.removeInstance(instance)

            self.data('hardwareManager').removeInstance(instance)

            var plugin = plugins[instance]
            // plugin might have failed to register
            if (plugin && plugin.data) {
                var pluginGui = plugin.data('gui')
                pluginGui && pluginGui.triggerJS({ type: 'end' })
            }
            if (plugin && plugin.length) {
                plugin.remove()
            }

            delete plugins[instance]
        } else {
            connMgr.iterate(function (jack) {
                var input   = jack.data('destination')
                var inport  = input.attr('mod-port')
                var output  = jack.data('origin')
                var outport = output.attr('mod-port')

                if (inport != instance && outport != instance)
                    return

                connMgr.disconnect(outport, inport)
                jack.data('canvas').remove()
                jack.remove()
                self.pedalboard('packJacks', input)

                if (!connMgr.origIndex[outport] || Object.keys(connMgr.origIndex[outport]).length == 0) {
                    output.addClass('output-disconnected')
                    output.removeClass('output-connected')
                }
            })

            var inputs  = self.data('hwInputs')
            var outputs = self.data('hwOutputs')

            var hwsToRemove = []
            inputs.forEach(function (hw) {
                if (hw.attr("mod-port-symbol") == instance) {
                    hwsToRemove.push(hw)
                }
            })
            for (var i in hwsToRemove) {
                hwsToRemove[i].remove()
                remove_from_array(inputs, hwsToRemove[i])
            }

            hwsToRemove = []
            outputs.forEach(function (hw) {
                if (hw.attr("mod-port-symbol") == instance) {
                    hwsToRemove.push(hw)
                }
            })
            for (var i in hwsToRemove) {
                hwsToRemove[i].remove()
                remove_from_array(outputs, hwsToRemove[i])
            }

            self.pedalboard('positionHardwarePorts')
        }
    },

    // Highlight all inputs to which a jack can be connected (any inputs that are not from same
    // instance and are not already connected). Highlight parameter indicates if we want highlighting
    // on or off. If highlight parameter is false, no jack is needed.
    highlightInputs: function (highlight, jack) {
        var self = $(this)
        var connMgr = self.data('connectionManager')
        if (!highlight) {
            self.find('[mod-role=input-audio-port]').removeClass('input-connecting')
            self.find('[mod-role=input-midi-port]').removeClass('input-connecting')
            self.find('[mod-role=input-cv-port]').removeClass('input-connecting')
            self.find('[mod-role=input-audio-port]').removeClass('input-connecting-highlight')
            self.find('[mod-role=input-midi-port]').removeClass('input-connecting-highlight')
            self.find('[mod-role=input-cv-port]').removeClass('input-connecting-highlight')
            return
        }

        var output = jack.data('origin')
        var fromPort = output.attr('mod-port')
        var portType = output.data('portType')

        self.find('[mod-role=input-' + portType + '-port]').each(function () {
            $(this).addClass('input-connecting')
        });
    },

    // Removes all plugins and restore pedalboard initial state, so that a new pedalboard
    // can be created
    reset: function (callback) {
        var self = $(this)

        self.data('bypassApplication', false)
        self.data('callbacksToArrive', {})

        var connMgr = self.data('connectionManager')
        connMgr.iterate(function (jack) {
            self.pedalboard('disconnect', jack)
        })

        self.data('reset')(function (ok) {
            if (!ok) {
                return
            }
            self.pedalboard('resetData')
            if (callback) {
                callback()
            }
        })
    },

    // Removes all pedalboard data
    resetData: function () {
        var self = $(this)

        self.data('hardwareManager').reset()

        var connMgr = self.data('connectionManager')

        connMgr.iterate(function(jack) {
            self.pedalboard('destroyJack', jack);
        })

        connMgr.reset()

        var plugins = self.data('plugins')
        for (var instance in plugins) {
            var plugin = plugins[instance]

            // plugin might have failed to register
            if (plugin && plugin.data) {
                var pluginGui = plugin.data('gui')
                pluginGui && pluginGui.triggerJS({ type: 'end' })
            }
            if (plugin && plugin.length) {
                plugin.remove()
            }
        }
        self.data('plugins', {})

        self.pedalboard('resetSize')
    },

    // Make element an audio/midi inputs, to which jacks can be dragged to make connections
    makeInput: function (element, instance) {
        var self = $(this)
        var symbol = element.attr('mod-port-symbol')
        var portType = element.attr('mod-role').split(/-/)[1]

        element.addClass('mod-input')
        element.addClass('mod-' + portType + '-input')
        element.addClass('input-disconnected')

        element.data('instance', instance)
        element.data('symbol', symbol)
        element.data('portType', portType)

        if (instance != "")
            element.attr('mod-port', instance + "/" + symbol)
        else
            element.attr('mod-port', symbol)

        element.droppable({
            accept: '[mod-role=output-jack]',
            tolerance: 'custom',
            drop: function (event, ui) {
                var overCount = self.data('overCount');
                self.data('overCount', 0);

                var jack = ui.draggable
                var outputType = jack.parent().attr('mod-role').split(/-/)[1]
                var inputType = element.attr('mod-role').split(/-/)[1]
                if (outputType != inputType) {
                    return
                }

                self.pedalboard('do_connect', jack, element, overCount)
                element.removeClass('input-connecting-highlight')
            },
            over: function (event, ui) {
                var outputType = ui.draggable.parent().attr('mod-role').split(/-/)[1]
                var inputType = element.attr('mod-role').split(/-/)[1]
                if (outputType != inputType)
                    return

                element.addClass('input-connecting-highlight')

                var overCount = self.data('overCount')+1;
                self.data('overCount', overCount);
                if (overCount == 1) {
                    self.data('background').droppable('disable')
                }
            },
            out: function (event, ui) {
                element.removeClass('input-connecting-highlight')

                var overCount = self.data('overCount')-1;
                if (overCount < 0) {
                    overCount = 0
                }
                self.data('overCount', overCount);
                if (overCount == 0) {
                    self.data('background').droppable('enable')
                }
            },
            greedy: true,
        })

        element.click(function () {
            var connection = self.data('ongoingConnection')
            if (connection) {
                self.pedalboard('do_connect', connection.jack, element)
            } else {
                self.pedalboard('expandInput', element)
            }
        })
    },

    // Make element an audio output, which contain jacks that can be dragged to
    // inputs to make connections
    makeOutput: function (element, instance) {
        var self = $(this)
        var symbol = element.attr('mod-port-symbol')
        var portType = element.attr('mod-role').split(/-/)[1]

        element.addClass('mod-output')
        element.addClass('mod-' + portType + '-output')
        element.addClass('output-disconnected')

        element.data('instance', instance)
        element.data('symbol', symbol)
        element.data('portType', portType)
        if (instance != "")
            element.attr('mod-port', instance + "/" + symbol)
        else
            element.attr('mod-port', symbol)


        self.pedalboard('spawnJack', element)

        element.click(function (e) {
            // Do not start connection if cv addressing checkbox or text input clicked
            if (!$(e.target).is('input') && !$(e.target).hasClass('checkmark') && !$(e.target).hasClass('checkbox-container')) {
              self.pedalboard('startConnection', element)
            }
        })
    },

    // Creates a jack element inside an output. This jack can then be dragged and dropped
    // inside an input to connect them.
    // Each jack knows it's origin's instance and symbol, and also tracks several elements
    // that are created with it to draw fancy cables.
    spawnJack: function (output) {
        var self = $(this)
        var jack = $('<div>').appendTo(output)

        jack.attr('mod-role', 'output-jack')
        jack.addClass('mod-output-jack')
        jack.addClass('jack-disconnected')

        // Track the origin of the jack
        jack.data('origin', output)

        // Indicates if this jack is connected to an input or not, and to which input
        jack.data('connected', false)
        jack.data('destination', null)

        // Create a canvas occupying the whole screen, which will be used to draw this
        // jack's cable.
        // The cable is composed by three lines with different style: one for the cable,
        // one for the background shadow and one for the reflecting light.
        var canvas = $('<div>');
        canvas.addClass('ignore-arrive');

        if (output.attr("class").search("mod-audio-") >= 0)
            canvas.addClass("mod-audio");
        else if (output.attr("class").search("mod-midi-") >= 0)
            canvas.addClass("mod-midi");
        else if (output.attr("class").search("mod-cv-") >= 0)
            canvas.addClass("mod-cv");

        // Add checkbox + text inputs next to output cv ports for addressings
        if (output.attr('mod-role') === 'output-cv-port' && output.find('.output-cv-checkbox').length === 0) {
          var port = output.attr("mod-port");
          var portSymbol = output.attr("mod-port-symbol");
          var cvPort = '/cv' + port;
          var addedPort = self.data('hardwareManager').cvOutputPorts.find(function (port) {
            return port.uri === cvPort;
          });

          var cvCheckboxInput = $('<div>');
          cvCheckboxInput.addClass('ignore-arrive');

          // Append checkbox
          var checkbox = $('<input type="checkbox">');
          var checkboxContainer = $('<span class="checkbox-container"></span>');
          checkbox.appendTo(checkboxContainer);
          $('<span class="checkmark" />').appendTo(checkboxContainer);
          checkboxContainer.appendTo(cvCheckboxInput);

          // Append text input
          var textInput = $('<input type="text" />');
          textInput.appendTo(cvCheckboxInput);

          cvCheckboxInput.addClass('output-cv-checkbox');
          cvCheckboxInput.appendTo(output);
          if (!self.data('cvAddressing')) {
            cvCheckboxInput.hide()
          }

          // Disable inputs for hardware cv ports
          var defaultText = output.attr("title")
          if (
            portSymbol === "/graph/cv_exp_pedal" ||
            portSymbol === "/graph/cv_capture_1" ||
            portSymbol === "/graph/cv_capture_2"
          ) {
            checkbox.prop('disabled', true);
            checkbox.prop('checked', true);
            textInput.prop('disabled', true);
          } else {
            // Add default displayed name to plugins CV ports
            var instance = port
              .split("/graph/")[1]
              .split("/")[0]
              .replace(/^\w/, function(chr) {
                return chr.toUpperCase();
              });
            defaultText = instance + " " + defaultText
            if (addedPort) {
              defaultText = addedPort.name;
              checkbox.prop('checked', true);
            } else {
              textInput.hide();
            }
          }
          textInput.val(defaultText);

          checkbox.change(function () {
            var name = textInput.val();
            if ($(this).prop('checked')) {
              // Register new addressable cv port
              self.data('addCVAddressingPluginPort')(cvPort, name, function (resp) {
                if (resp && resp.ok) {
                  self.data('hardwareManager').addCvOutputPort(cvPort, name, resp.operational_mode);
                  // Show and highlight text input
                  textInput.show();
                  textInput.select();
                }
              });
            } else {
              // Unregister cv port
              self.data('removeCVAddressingPluginPort')(cvPort, function (resp) {
                if (resp) {
                  self.data('hardwareManager').removeCvOutputPort(cvPort);
                  // Hide text input again
                  textInput.hide();
                }
              });
            }
          })

          textInput.change(function () {
            var name = $(this).val();
            self.data('addCVAddressingPluginPort')(cvPort, name, function (resp) {
              if (resp && resp.ok) {
                self.data('hardwareManager').addCvOutputPort(cvPort, name, resp.operational_mode);
              }
            });
          });

          textInput.keydown(function (e) {
            if (e.keyCode === 13) {
              $(this).blur();
            }
          });
        }

        canvas.css({
            width: '100%',
            height: '100%',
            position: 'absolute',
            top: 0,
            left: 0
        })
        self.append(canvas)
        canvas.svg()
        var svg = canvas.find('svg')
        svg.css({
            width: '100%',
            height: '100%',
            position: 'absolute',
            top: 0,
            left: 0
        })

        jack.data('canvas', canvas)
        svg = canvas.svg('get')
        jack.data('svg', svg)
        canvas.data('pathShadow', svg.createPath())
        canvas.data('pathCable', svg.createPath())
        canvas.data('pathLight', svg.createPath())

        jack.draggable({
            revert: 'invalid',
            revertDuration: 0,
            start: function () {
                // Prevents dragging of whole pedalboard while jack is being dragged
                self.pedalboard('preventDrag', true)

                // If user has started a connection by clicking a jack, this drag will
                // end it
                self.pedalboard('finishConnection')

                // Highlight all inputs in which this jack can be dropped
                self.pedalboard('highlightInputs', true, jack)

                // While jack is being dragged, all related elements receive
                // the "*-connecting" class
                jack.removeClass('jack-disconnected')
                jack.removeClass('jack-connected')
                jack.addClass('jack-connecting')
                output.addClass('output-connecting')
                canvas.removeClass('cable-connected')
                canvas.addClass('cable-connecting')

                var cur = jack.data('destination')
                if (cur)
                    cur.removeClass('input-connected')

            },
            drag: function (e, ui) {
                var scale = self.data('scale')
                ui.position.top /= scale
                ui.position.left /= scale
                jack.css({ marginTop: 0 })
                self.pedalboard('drawJack', jack, true)
            },
            stop: function () {
                self.pedalboard('preventDrag', false)

                self.pedalboard('highlightInputs', false)
                jack.removeClass('jack-connecting')
                output.removeClass('output-connecting')
                canvas.removeClass('cable-connecting')
                if (!jack.hasClass('jack-connected')) {
                    jack.addClass('jack-disconnected')
                    jack.css({
                        top: 'auto',
                        left: 'auto',
                        marginTop: 'auto',
                    })

                    // if jack output previous sibling has a margin-bottom,
                    // adjust jack top position in accordance
                    if (jack.data('origin') && jack.data('origin').prev() && jack.data('origin').prev().css('margin-bottom')) {
                      jack.css('top', parseInt(jack.css('top')) - parseInt(jack.data('origin').prev().css('margin-bottom')))
                    }
                }
                self.pedalboard('drawJack', jack)
            }
        })

        // draggable puts position relative in jack. this messes with layout and is not necessary
        // in this case, because we'll recalculate the position during drag anyway because of scaling
        jack.css('position', 'absolute')

        canvas.click(function () {
            self.pedalboard('colapseInput')
            self.pedalboard('finishConnection')
        })

        return jack
    },

    destroyJack: function (jack) {
        var self = $(this)
        var output = jack.data('origin')
        var input = jack.data('destination')
        self.data('connectionManager').disconnect(output.attr('mod-port'), input.attr('mod-port'))
        jack.data('canvas').remove()
        jack.remove()
        self.pedalboard('packJacks', input)
    },

    // Draws a cable from jack's source (the output) to it's current position
    // Force parameter will force drawing when jack is disconnected
    drawJack: function (jack, force) {
        var self = $(this)
        // We used settimeout so that drawing will occur after all events are processed. This avoids some bad
        // user experience
        setTimeout(function () {
            var svg = jack.data('svg')
            if (!svg)
            // maybe jack has just been disconnected and so no drawing is necessary
                return

            svg.clear()

            // If this jack is not connected and
            if (!jack.data('connected') && !force)
                return

            var source = jack.data('origin')
            var scale = self.data('scale')

            // Cable will follow a cubic bezier curve, which is defined by 4 points. They are:
            // P0 (xi, yi) - starting point
            // P3 (xo, yo) - the destination point
            // P1 (xo - deltaX, yi) and P2 (xi + deltaX, yo): define the curve
            // Gets origin and destination coordinates
            var xi = source.offset().left / scale - self.offset().left / scale + source.width()
            var yi = source.offset().top / scale - self.offset().top / scale + source.height() / 2
            var xo = jack.offset().left / scale - self.offset().left / scale
            var jackOffsetTop = jack.offset().top

            // Adjust jack offset top position
            // that is sometimes biased by jack destination previous sibling margin bottom
            if (!force && parseInt(jack.css('top')) === 0 && parseInt(jack.css('bottom')) === 0) {
              jackOffsetTop = jack.offset().top - jack.position().top
            }
            var yo = jackOffsetTop / scale - self.offset().top / scale + jack.height() / 2

            //if (source.hasClass("mod-audio-output"))
                //self.pedalboard('drawBezier', jack.data('canvas'), xi+12, yi, xo, yo, '')
            //else
            self.pedalboard('drawBezier', jack.data('canvas'), xi, yi, xo, yo, '')
        }, 0)
    },

    drawBezier: function (canvas, xi, yi, xo, yo, stylePrefix) {
        var svg = canvas.svg('get')
        if (!svg)
            return
        svg.clear()

        var pathS = canvas.data('pathShadow')
        var pathC = canvas.data('pathCable')
        var pathL = canvas.data('pathLight')

        pathS.reset()
        pathC.reset()
        pathL.reset()

        // The calculations below were empirically obtained by trying several things.
        // It gives us a pretty good result
        var deltaX = xo - xi - 50
        if (deltaX < 0) {
            deltaX = 8.5 * (deltaX / 6) // ^ 0.8
        } else {
            deltaX /= 1.5
        }

        // Draw three lines following same path, one for shadow, one for cable and one for light
        // The recipe for a good cable is that shadow is wide and darke, cable is not so wide and not so dark,
        // and light is very thin and light.
        // Each has a different class, so it will be defined by CSS.
        svg.path(null,
            pathS.move(xi, yi).curveC(xo - deltaX, yi, xi + deltaX, yo, xo, yo), {
                class_: stylePrefix + 'shadow'
            }
        )
        svg.path(null,
            pathC.move(xi, yi).curveC(xo - deltaX, yi, xi + deltaX, yo, xo, yo), {
                class_: stylePrefix + 'cable'
            }
        )
        svg.path(null,
            pathL.move(xi, yi).curveC(xo - deltaX, yi, xi + deltaX, yo, xo, yo), {
                class_: stylePrefix + 'light'
            }
        )
    },

    startConnection: function (output) {
        var self = $(this)
        if (self.data('ongoingConnection'))
            return
        var jack = output.find('[mod-role=output-jack]')
        var canvas = $('<div>')
        canvas.addClass('ignore-arrive')
        canvas.css({
            width: '100%',
            height: '100%',
            position: 'absolute',
            top: 0,
            left: 0
        })
        self.append(canvas)
        canvas.svg()
        var svg = canvas.find('svg')
        svg.css({
            width: '100%',
            height: '100%',
            position: 'absolute',
            top: 0,
            left: 0
        })

        svg = canvas.svg('get')
        canvas.data('pathShadow', svg.createPath())
        canvas.data('pathCable', svg.createPath())
        canvas.data('pathLight', svg.createPath())

        canvas.click(function () {
            self.pedalboard('finishConnection')
        })
        var moveHandler = function (e) {
            if ($(e.target).is('input')) { // cv addressing input
              return
            }
            var scale = self.data('scale')
                // In iPad a tap will first trigger a mousemove event and, if no modifications are made, a click
                // event will be triggered. So, to capture a click we must schedule all actions in mousemove handler
            if (!self.data('ongoingConnection'))
            // a tap in ipad will cause this
                return
            setTimeout(function () {
                var xi = output.offset().left / scale - self.offset().left / scale
                var yi = output.offset().top / scale - self.offset().top / scale + output.height() / 2
                var xo = (e.pageX - self.offset().left) / scale
                var yo = (e.pageY - self.offset().top) / scale

                self.pedalboard('drawBezier', canvas, xi, yi, xo, yo, 'connecting-')
            }, 0)
        }
        var connection = {
            jack: jack,
            canvas: canvas,
            moveHandler: moveHandler,
        }
        self.bind('mousemove', moveHandler)
        self.data('ongoingConnection', connection)
        self.pedalboard('highlightInputs', true, jack)
    },

    finishConnection: function () {
        var self = $(this)
        var connection = self.data('ongoingConnection')
        if (!connection)
            return
        self.data('ongoingConnection', null)
        connection.canvas.remove()
        self.unbind('mousemove', connection.moveHandler)
        self.pedalboard('highlightInputs', false)
    },

    do_connect: function (jack, input, overCount) {
        var self = $(this)
        var output = jack.data('origin')
        var previousInput = jack.data('destination')

        if (self.pedalboard('connected', output, input)) {
            // If this jack is already connected to this output, keep connection
            // This means user just took a connected jack, dragged around and dropped in the same input
            if (previousInput && input && previousInput[0] == input[0]) {
                jack.addClass('jack-connected')
                output.addClass('output-connected')
                output.removeClass('output-disconnected')
                output.removeClass('output-connecting')
                jack.data('canvas').addClass('cable-connected')
                jack.data('connected', true)
                input.addClass('input-connected')

                jack.css({
                    top: 'auto',
                    left: 'auto',
                    marginTop: 'auto',
                })

                // if jack input previous sibling has a margin-bottom,
                // adjust jack top position in accordance
                if (jack.data('destination') && jack.data('destination').prev() && jack.data('destination').prev().css('margin-bottom')) {
                  jack.css('top', parseInt(jack.css('top')) - parseInt(jack.data('destination').prev().css('margin-bottom')))
                }
            // If output is already connected to this input through another jack, abort connection
            } else {
                self.pedalboard('disconnect', jack)
                output.addClass('output-connected')
                output.removeClass('output-disconnected')
                output.removeClass('output-connecting')
            }
            return
        }

        // This jack was connected to some other input, let's disconnect it
        if (previousInput && overCount < 2) {
            self.pedalboard('disconnect', jack)
            self.pedalboard('packJacks', previousInput)
        }

        self.data('portConnect')(output.attr('mod-port'), input.attr('mod-port'),
            function (ok) {
                if (!ok) {
                    self.pedalboard('disconnect', jack)
                }
            })
    },

    // Connects an output port to an input port.
    // The output is obtained from jack
    connect: function (jack, input, skipModified) {
        var self = $(this)
        var output = jack.data('origin')
        if (output == null) {
            console.log("ERROR: The origin for '" + jack.selector + "' is missing")
            return
        }

        // If output is already connected to this input through another jack, abort connection
        if (self.pedalboard('connected', output, input)) {
            self.pedalboard('disconnect', jack)
            output.addClass('output-connected')
            output.removeClass('output-disconnected')
            output.removeClass('output-connecting')
            return
        }

        // Can only ports if they are the same type
        if (input.data('portType') != output.data('portType')) {
            return self.pedalboard('disconnect', jack)
        }

        // Everything ok, let's do the connection
        self.pedalboard('finishConnection')

        // Register the connection in desktop structure
        self.data('connectionManager').connect(output.attr("mod-port"), input.attr("mod-port"), jack)

        // Register the connection in jack
        jack.data('destination', input)
        jack.data('connected', true)
        input.append(jack)

        // Add status classes
        output.addClass('output-connected')
        output.removeClass('output-disconnected')
        output.removeClass('output-connecting')
        jack.addClass('jack-connected')
        jack.removeClass('jack-connecting')
        jack.removeClass('jack-disconnected')
        jack.data('canvas').addClass('cable-connected')

        // Redraw jack arrangement in both new and previous input, if any
        self.pedalboard('packJacks', input)
        self.pedalboard('spawnJack', output)

        if (! skipModified) {
            // Pedalboard has been modified
            self.trigger('modified')
        }

        // Do the connection in host. If there's a problem, undo the connection
        // It might be better to check first and then connect instead
        return
    },

    // Disconnect this jack
    // This will undo the connection made by this jack, if any,
    // destroy the jack and spawn a new one if necessary
    disconnect: function (jack) {
        var self = $(this)
        var connected = jack.data('connected')
        var input = jack.data('destination')
        var output = jack.data('origin')

        if (connected) {
            self.data('portDisconnect')(output.attr('mod-port'), input.attr('mod-port'), function (ok) {})
            self.trigger('modified')

            var connMgr = self.data('connectionManager')
            var outport = output.attr('mod-port')
            if (connMgr.origIndex[outport] && Object.keys(connMgr.origIndex[outport]).length == 1) {
                output.addClass('output-disconnected')
                output.removeClass('output-connected')
            }

        } else {
            jack.css({
                top: 'auto',
                left: 'auto',
                marginTop: 'auto',
            })

            // if jack output previous sibling has a margin-bottom,
            // adjust jack top position in accordance
            if (jack.data('origin') && jack.data('origin').prev() && jack.data('origin').prev().css('margin-bottom')) {
              jack.css('top', parseInt(jack.css('top')) - parseInt(jack.data('origin').prev().css('margin-bottom')))
            }
        }

        jack.data('connected', false)
    },

    // Connect two ports using instance and symbol information.
    // Used for unserializing. We have to find the spare jack in output,
    // put it
    connectPorts: function (fromInstance, fromSymbol, toInstance, toSymbol) {},

    connected: function (output, input) {
        var self = $(this)
        return self.data('connectionManager').connected(output.attr("mod-port"), input.attr("mod-port"))
    },

    // Adjust layout of all jacks connected to this input to fit inside it
    packJacks: function (input) {
        var self = $(this)
        var jacks = input.find('[mod-role=output-jack]')
        var count = jacks.length
        var height = input.height() //(input.height() - 6 - count) / count
        jacks.height(height)
        jacks.width(input.width())

        if (count > 0) {
            input.addClass('input-connected')
            input.removeClass('input-disconnected')
        } else {
            input.removeClass('input-connected')
            input.addClass('input-disconnected')
        }

        jacks.each(function () {
            var jack = $(this)
            jack.css({
                top: 'auto',
                left: 'auto',
                marginTop: 'auto',
            })

            // if jack input previous sibling has a margin-bottom,
            // adjust jack top position in accordance
            if (jack.position().top !== 0 && jack.data('destination') && jack.data('destination').prev() && jack.data('destination').prev().css('margin-bottom')) {
              jack.css('top', parseInt(jack.css('top')) - parseInt(jack.data('destination').prev().css('margin-bottom')))
            }

            jack.draggable(count <= 1 ? 'enable' : 'disable')
            self.pedalboard('drawJack', jack)
        });

        if (input.data('expanded'))
            self.pedalboard('colapseInput', input)
    },

    // This expands/collapses an input that has sevel connected jacks
    expandInput: function (input) {
        var self = $(this)
        var jacks = input.find('[mod-role=output-jack]')
        if (jacks.length < 2 || input.data('expanded'))
            return
        var wrapper = $('<div class="mod-pedal-input-wrapper ignore-arrive">')
        //var arrow = $('<div class="mod-pedal-input-arrow ignore-arrive">').appendTo(wrapper)
        wrapper.appendTo(input)

        //arrow.css('top', wrapper.height() / 2 - 12)
        var jack
        var h = 0;
        for (var i = 0; i < jacks.length; i++) {
            jack = $(jacks[i]);
            h = jack.height();
            w = jack.width();
            jack.css({
                position: 'absolute',
                marginTop: (-jacks.length * h) / 2 + h / 2 + h * i,
            })
            h = jack.height();
            self.pedalboard('drawJack', jack)
            jack.draggable('enable')
        }

        wrapper.innerHeight(jacks.length * h);
        wrapper.css('top', (input.height() - wrapper.height()) / 2)
        wrapper.css("width", w);
        wrapper.click(function () {
            self.pedalboard('colapseInput', input)
            return false
        })
        input.addClass('expanded')
        input.data('expanded', true)
        input.data('wrapper', wrapper)
        self.pedalboard('colapseInput')
        self.data('expandedInput', input)
    },
    colapseInput: function (input) {
        var self = $(this)
        if (input == null)
            input = self.data('expandedInput')
        if (!input)
            return
        var jacks = input.find('[mod-role=output-jack]')
        var wrapper = input.data('wrapper')
        if (wrapper) {
            wrapper.remove()
            input.data('wrapper', null)
        }
        input.data('expanded', false)
        self.data('expandedInput', null)
        input.removeClass('expanded')
        self.pedalboard('packJacks', input)
    },

    setPluginPosition: function(instance, x, y) {
        var self = $(this)
        var plugins = self.data('plugins');
        var plugin = plugins[instance];
        plugin.css({ top: y, left: x })
        self.pedalboard('fitToWindow')
        self.pedalboard('drawPluginJacks', plugin)
    }
})

function ConnectionManager() {
    /*
     * Manages all connections in pedalboard.
     * Each connection is represented by 2 values:
     * origin port and destination port
     * Keeps two indexes, origIndex and destIndex, with jack objects in both.
     * The indexes are dicts that store each jack in path [port][port]
     */
    var self = this

    this.reset = function () {
        self.origIndex = {}
        self.destIndex = {}
        self.origByInstanceIndex = {}
        self.destByInstanceIndex = {}
    }

    this.reset()

    this._addToIndex = function (index, key1, key2, jack) {
        if(index[key1] == null)
            index[key1] = {}
        index[key1][key2] = jack
    }

    this._removeFromIndex = function (index, key1, key2) {
        if(index[key1] != null)
            delete index[key1][key2]
    }

    // Connects two ports
    this.connect = function (fromPort, toPort, jack) {
        self._addToIndex(self.origIndex, fromPort, toPort, jack)
        self._addToIndex(self.destIndex, toPort, fromPort, jack)

        // TODO: change the architecture so we don't need to keep this other index
        // and this 'system' HACK
        var instance = fromPort.substring(0, fromPort.lastIndexOf("/"))
        if (self.origByInstanceIndex[instance] == null)
            self.origByInstanceIndex[instance] = {}
        self._addToIndex(self.origByInstanceIndex[instance], fromPort, toPort, jack)

        instance = toPort.substring(0, toPort.lastIndexOf("/"))
        if (self.destByInstanceIndex[instance] == null)
            self.destByInstanceIndex[instance] = {}
        self._addToIndex(self.destByInstanceIndex[instance], toPort, fromPort, jack)
    }

    // Disconnects two ports
    this.disconnect = function (fromPort, toPort) {
        self._removeFromIndex(self.origIndex, fromPort, toPort)
        self._removeFromIndex(self.destIndex, toPort, fromPort)

        // TODO: change the architecture so we don't need to keep this other index
        // and this 'system' HACK
        var instance = fromPort.substring(0, fromPort.lastIndexOf("/"))
        if (self.origByInstanceIndex[instance] != null)
            self._removeFromIndex(self.origByInstanceIndex[instance], fromPort, toPort)

        instance = toPort.substring(0, toPort.lastIndexOf("/"))
        if (self.destByInstanceIndex[instance] != null)
            self._removeFromIndex(self.destByInstanceIndex[instance], toPort, fromPort)
    }

    // Checks if two ports are connected
    this.connected = function (fromPort, toPort) {
        try {
            return self.origIndex[fromPort][toPort] != null
        } catch (TypeError) {
            return false
        }
    }

    // Execute callback for all connections, passing jack as parameter
    this.iterate = function (callback) {
        for (var key1 in self.origIndex)
            for (var key2 in self.origIndex[key1])
                callback(self.origIndex[key1][key2])
    }

    // Execute callback for each connection of a given instance, passing jack as parameter
    this.iterateInstance = function (instance, callback) {
        if (self.origByInstanceIndex[instance] != null)
            for (var key1 in self.origByInstanceIndex[instance])
                for (var key2 in self.origByInstanceIndex[instance][key1])
                    callback(self.origByInstanceIndex[instance][key1][key2])
        if (self.destByInstanceIndex[instance] != null)
            for (var key1 in self.destByInstanceIndex[instance])
                for (var key2 in self.destByInstanceIndex[instance][key1])
                    callback(self.destByInstanceIndex[instance][key1][key2])
    }

    this.removeInstance = function (instance) {
        for (var port in self.origByInstanceIndex[instance]) {
            delete self.origIndex[port]
            for (var ins in self.destByInstanceIndex)
                for (var obiport in self.destByInstanceIndex[ins])
                    delete self.destByInstanceIndex[ins][obiport][port]
            for (var oport in self.destIndex)
                delete self.destIndex[oport][port]
        }

        for (var port in self.destByInstanceIndex[instance]) {
            delete self.destIndex[port]
            for (var ins in self.origByInstanceIndex)
                for (var dbiport in self.origByInstanceIndex[ins])
                    delete self.origByInstanceIndex[ins][dbiport][port]
            for (var dport in self.origIndex)
                delete self.origIndex[dport][port]
        }

        delete self.origByInstanceIndex[instance]
        delete self.destByInstanceIndex[instance]
    }
}
