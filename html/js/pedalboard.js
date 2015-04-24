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

JqueryClass('pedalboard', {
    init: function (options) {
        var self = $(this)
        options = $.extend({
            // baseScale is the initial scale (zoom level) of the pedalboard
            // The scale is the webkit-transform scale() css property that the pedalboard has
            baseScale: 0.5,
            // maxScale is the maximum zoom.
            maxScale: 1,
            // WindowManager instance
            windowManager: new WindowManager(),
            // HardwareManager instance, must be specified
            hardwareManager: null,
            // InstallationQueue instance
            installationQueue: new InstallationQueue(),

            // Wait object, used to show waiting message to user
            wait: new WaitMessage(self),

            // current z index (last plugin added or moved around)
            z_index: 30,

            // This is a margin, in pixels, that will be disconsidered from pedalboard height when calculating
            // hardware ports positioning
            bottomMargin: 0,

            // Below are functions that application uses to integrate functionality to pedalboard.
            // They all receive a callback as last parameter, which must be called with a true value
            // to indicate that operation was successfully executed.
            // In case of error, application is expected to communicate error to user and then call the
            // callback with false value. The pedalboard will silently try to keep consistency, with
            // no garantees. (TODO: do something if consistency can't be achieved)

            // Loads a plugin with given plugin url and instance
            // Application MUST use this instance. Overriding this is mandatory.
            pluginLoad: function (url, instance, x, y, callback) {
                callback(true)
            },

            // Removes the plugin given by instance
            pluginRemove: function (instance, callback) {
                callback(true)
            },

            // Loads a preset
            pluginPresetLoad: function (instance, label, callback) {
                callback(true)
            },

            // Changes the parameter of a plugin's control port
            pluginParameterChange: function (port, value, callback) {
                callback(true)
            },

            // Bypasses or un-bypasses plugin
            pluginBypass: function (instance, bypassed, callback) {
                callback(true)
            },

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

            // Loads a pedalboard
            pedalboardLoad: function (uid, callback) {
                callback(true)
            },

            // Takes a list of plugin URLs and gets a dictionary containing all those plugins's data,
            // indexed by URL
            getPluginsData: function (plugins, callback) {
                callback({})
            },

            // Marks the position of a plugin
            pluginMove: function (instance, x, y, callback) {
                callback(true)
            },

            // Sets the size of the pedalboard
            windowSize: function (width, height) {}

        }, options)

        self.pedalboard('wrapApplicationFunctions', options, ['pluginLoad', 'pluginRemove', 'pluginParameterChange', 'pluginPresetLoad', 'pluginBypass',
            'portConnect', 'portDisconnect', 'reset', 'pedalboardLoad', 'pluginMove'
        ])

        self.data(options)

        // When bypassApplication is set to true, the applicationFunctions provided by options will be bypassed
        self.data('bypassApplication', false)

        // minScale holds the minimum scale of the pedalboard. It's initialized as being the base scale
        // and gets smaller as pedalboard size grows
        self.data('minScale', options.baseScale)

        self.data('instanceCounter', -1)

        // Holds all plugins loaded, indexed by instance
        self.data('plugins', {})

        // Hardware inputs and outputs, which have an instance of -1 and symbol as given by application
        self.data('hwInputs', [])
        self.data('hwOutputs', [])

        // connectionManager keeps track of all connections
        self.data('connectionManager', new ConnectionManager())

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

        $(window).resize(function () {
            self.pedalboard('fitToWindow')
        })

        // Create background element to catch dropped jacks
        // Must be much bigger than screen, so that nothing can be
        // dropped outside it even if mouse goes outside window
        var bg = $('<div>')
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

        // Dragging the pedalboard move the view area
        self.mousedown(function (e) {
                self.pedalboard('drag', e)
            })
            // The mouse wheel is used to zoom in and out
        self.bind('mousewheel', function (e) {
            // Zoom by mousewheel has been desactivated.
            // Let's keep the code here so that maybe later this can be a user option
            return

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

    serialize: function (callback) {
        var self = $(this)
        var scale = self.data('scale')
        var hw = self.data('hardwareManager')

        var data = {}
        data.width = self.width()
        data.height = self.height()

        data.instances = []
        var instance, plugin, pluginData, gui
        var plugins = self.data('plugins')
        for (instance in plugins) {
            plugin = plugins[instance]
            gui = plugin.data('gui')
            preset = gui.serializePreset()
                // TODO: hack tosco para tirar a porta virtual :bypass, rever arquitetura
            delete preset[':bypass']
            pluginData = {
                instance: instance,
                url: plugin.data('url'),
                x: (plugin.offset().left - self.offset().left) / scale,
                y: (plugin.offset().top - self.offset().top) / scale,
                preset: preset,
                addressing: hw ? hw.serializeInstance(instance) : null,
                bypassed: gui.bypassed
            }
            data.instances.push(pluginData)
        }

        data.connections = []
        self.data('connectionManager').iterate(function (jack) {
            var from = jack.data('origin')
            var to = jack.data('destination')
            data.connections.push([from.data('instance'),
                from.data('symbol'),
                to.data('instance'),
                to.data('symbol')
            ])
        })

        callback(data)
    },

    unserialize: function (data, callback, loadPedalboardAtOnce, bypassApplication) {
        var self = $(this)

        /*
         * Unserialization will first call all application callbacks and after everything is done,
         * build the pedalboard in screen.
         * To do that, it takes two queues to work on (instances and connections), and as it's working
         * on them, it queues actions to be done when everything is ready.
         * To work on the instances and connections queues, it uses two asynchronous recursive functions
         * that will process next element element and gives itself as callback for the application.
         */

        // Let's avoid modifying original data
        data = $.extend({}, data)

        if (bypassApplication == null)
            bypassApplication = !!loadPedalboardAtOnce

        // We might want to bypass application
        self.data('bypassApplication', bypassApplication)

        self.data('wait').start('Loading pedalboard...')
        var ourCallback = function () {
            self.data('wait').stop()
            if (callback)
                callback()
        }

        var addressingErrors = []
        var instanceNameIndex = {}

        // Queue closures to all actions needed after everything is loaded
        var finalActions = []
        var finish = function () {
            for (var i in finalActions)
                finalActions[i]()

            // Now check for addressing errors
            if (addressingErrors.length > 0) {
                verboseErrors = []
                var error
                for (var i = 0; i < addressingErrors.length; i++) {
                    error = addressingErrors[i]
                    verboseErrors.push(instanceNameIndex[error[0]] + "/" + error[1])
                }
                message = 'The following parameters could not be addressed: ' + verboseErrors.join(', ')
                new Notification('warn', message)
            }

            self.data('bypassApplication', false)
            setTimeout(function () {
                self.pedalboard('adapt')
            }, 1)
            if (loadPedalboardAtOnce)
                self.data('pedalboardLoad')(data._id, ourCallback)
            else
                ourCallback()
        }

        var loadPlugin, connect

        // Loads the next plugin in queue. Gets as parameter a data structure containing
        // information on all plugins
        loadPlugin = function (pluginsData) {
            var plugin = data.instances.pop()
            if (plugin == null)
            // Queue is empty, let's load connections now
                return connect()

            var pluginData = pluginsData[plugin.url]
            instanceNameIndex[plugin.instance] = pluginData.name

            self.data('pluginLoad')(plugin.url, plugin.instance, plugin.x, plugin.y,
                function (ok) {
                    if (!ok)
                        return
                    for (var symbol in plugin.preset) {
                        value = plugin.preset[symbol]
                        self.data('pluginParameterChange')(plugin.instance,
                            symbol,
                            value,
                            function (ok) {
                                if (!ok) {
                                    new Notification('error', sprintf("Can't set parameter for %s", symbol))
                                }
                            })
                    }

                    self.pedalboard('addPlugin', pluginData, plugin.instance, plugin.x, plugin.y, {
                            'preset': plugin.preset,
                            'bypassed': plugin.bypassed
                        }, plugin.addressing, addressingErrors,
                        function () {
                            loadPlugin(pluginsData)
                        }
                    )
                })
        }

        // Loads next connection in queue
        var connect = function () {
            var con = data.connections.pop()
            if (con == null)
            // Queue is empty, let's load everything
                return finish()

            var fromInstance = con[0]
            var fromSymbol = con[1]
            var toInstance = con[2]
            var toSymbol = con[3]

            self.data('portConnect')(fromInstance, fromSymbol, toInstance, toSymbol,
                function (ok) {
                    if (!ok)
                        return
                    finalActions.push(function () {
                        var plugins = $.extend({
                            'system': self
                        }, self.data('plugins'))
                        var orig = plugins[fromInstance]
                        var dest = plugins[toInstance]
                        if (!orig || !dest)
                            return
                        var output = orig.find('[mod-port-symbol=' + fromSymbol + ']')
                        var input = dest.find('[mod-port-symbol=' + toSymbol + ']')

                        var jack = output.find('[mod-role=output-jack]')
                        self.pedalboard('connect', jack, input)
                    })
                    connect()
                })
        }

        self.pedalboard('getPluginsData', data.instances, loadPlugin)
    },

    // Gets a list of instances, loads from application the data from all plugins available,
    // installs missing plugins and gives callback the whole result
    getPluginsData: function (instances, callback) {
        var self = $(this)
        var plugins = {}
        for (var i in instances) {
            plugins[instances[i].url] = 1
        }
        var urls = Object.keys(plugins)

        var missingCount = 0
        var installationQueue = self.data('installationQueue')

        var installPlugin = function (url, data) {
            missingCount++
            installationQueue.install(url, function (pluginData) {
                data[url] = pluginData
                missingCount--
                if (missingCount == 0)
                    callback(data)
            })
        }

        var installMissing = function (data) {
            for (var i in urls)
                if (data[urls[i]] == null)
                    installPlugin(urls[i], data)
            if (missingCount == 0)
                callback(data)
        }

        self.data('getPluginsData')(urls, installMissing)
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
     * 3 - Pedalboard calls a the application callback (pluginLoad option), with plugin url, instanceID and
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
            var instance = self.pedalboard('generateInstance', pluginData.url)
            waiter.startPlugin(instance, position)
            var pluginLoad = self.data('pluginLoad')
            pluginLoad(pluginData.url, instance, position.x, position.y, function () {})
/*                function () {
                    self.pedalboard('addPlugin', pluginData, instance, position.x, position.y)
                    setTimeout(function () {
                        self.pedalboard('adapt')
                    }, 1)
                    waiter.stopPlugin(instance)
                },
                function () {
                    waiter.stopPlugin(instance)
                })
*/
        })

        var options = {
            defaultIconTemplate: DEFAULT_ICON_TEMPLATE
        }

        element.draggable($.extend({
            helper: function () {
                var element = $('<div class="mod-pedal dummy">')
                new GUI(pluginData, options).renderDummyIcon(function (icon) {
                    element.attr('class', icon.attr('class'))
                    element.addClass('dragging')

                    var scale = self.data('scale')
                    var w = icon.width()
                    var h = icon.height()
                    var dx = w / (4 * scale) - w / 4
                    var dy = h / (2 * scale) - h / 2
                    element.css({
                        webkitTransform: 'scale(' + scale + ') translate(-' + dx + 'px, -' + dy + 'px)',
                    })
                    element.append(icon.children())
                })
                $('body').append(element)

                return element
            }
        }, draggableOptions))
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

        var scale = self.data('baseScale')

        self.parent().css({
            width: $(window).width() - self.data('hmargins'),
            height: $(window).height() - self.data('vmargins')
        })

        var scale = self.data('baseScale')
        self.css({
            width: self.parent().width() / scale,
            height: self.parent().height() / scale,
        })

        self.pedalboard('positionHardwarePorts')

        var zoom = self.data('currentZoom')
        if (!zoom)
            return

        zoom.screenX = zoom.screenX * self.width() / old.width
        zoom.screenY = zoom.screenY * self.height() / old.height

        self.pedalboard('zoom', zoom.scale, zoom.canvasX, zoom.canvasY, zoom.screenX, zoom.screenY, 0)

        self.data('windowSize')(self.width(), self.height())
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

        self.data('scale', scale)
        self.data('offsetX', offsetX)
        self.data('offsetY', offsetY)

        if (duration == null)
            duration == 400
        self.animate({
            scale: scale,
            top: offsetY,
            left: offsetX
        }, {
            duration: duration,
            step: function (value, prop) {
                if (prop.prop == 'scale')
                    self.css('webkitTransform', 'scale(' + value + ')')
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
    adapt: function () {
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


        if (wDif == 0 && hDif == 0)
        // nothing has changed
            return

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

        var time = 400

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
            x = parseInt(plugin.css('left')) + left
            y = parseInt(plugin.css('top')) + top
            plugin.animate({
                left: x,
                top: y
            }, {
                duration: time,
                step: drawFactory(plugin),
                complete: drawFactory(plugin)
            })
            self.data('pluginMove')(instance, x, y, function (r) {})
        }

        var viewWidth = self.parent().width()
        var viewHeight = self.parent().height()
        var newScale = viewWidth / w

        self.data('minScale', Math.min(self.data('minScale'), newScale))

        self.animate({
            scale: newScale,
        }, {
            duration: time,
            step: function (scale, prop) {
                if (prop.prop != 'scale')
                    return
                var width = viewWidth / scale
                var height = viewHeight / scale
                var offsetX = (viewWidth - width) / 2
                var offsetY = (viewHeight - height) / 2
                self.width(width)
                self.height(height)
                self.css({
                    webkitTransform: 'scale(' + scale + ')',
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


    // Position the hardware ports as to be evenly distributed vertically in pedalboard.
    // Output ports are positioned at left and input ports at right.
    positionHardwarePorts: function () {
        var self = $(this)

        var height = self.height() - self.data('bottomMargin')

        var adjust = function (elements, css) {
            var top = height / (elements.length + 1)
            var i, el
            elements.sort(function(e1, e2) {
                var e1_midi = e1.hasClass('mod-midi-output') || e1.hasClass('mod-midi-input')
                var e2_midi = e2.hasClass('mod-midi-output') || e2.hasClass('mod-midi-input')
                if (e1_midi == e2_midi) {
                    if (e1.attr('mod-port-index') > e2.attr('mod-port-index')) {
                        return 1
                    } else {
                        return -1
                    }
                } else {
                    if (e1_midi) {
                        return 1
                    } else {
                        return -1
                    }
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
        self.data('connectionManager').iterateInstance(':system:', function (jack) {
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
    },

    /*********
     * Plugins
     */

    // Generate an instance for a new plugin.
    // TODO: check with ingen if instance does not exist
    generateInstance: function (url) {
        var self = $(this)
        url = url.split("/")
        var instance = url[url.length-1]
        instance = instance.split("#")[instance.split("#").length-1]
        var i = 1;
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
    addPlugin: function (pluginData, instance, x, y, guiOptions, addressing, addressingErrors, renderCallback) {
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
                self.data('pluginMove')(instance, ui.position.left, ui.position.top, function (r) {})
                self.pedalboard('adapt')
            },
            click: function (event) {
                obj.icon.css({'z-index': self.data('z_index')+1})
                self.pedalboard('drawPluginJacks', obj.icon)
                self.data('z_index', self.data('z_index')+1)

                // check if mouse is not over a control button
                if (self.pedalboard('mouseIsOver', event, obj.icon.find('[mod-role=input-control-port]')))
                    return
                    // check if mouse is not over the footswitch
                if (self.pedalboard('mouseIsOver', event, obj.icon.find('[mod-role=bypass]')))
                    return
                    // clicking in input means expand
                if (self.pedalboard('mouseIsOver', event, obj.icon.find('[mod-role=input-audio-port]')))
                    return
                    // clicking in output or output jack means connecting
                if (self.pedalboard('mouseIsOver', event, obj.icon.find('[mod-role=output-audio-port]')))
                    return
                if (self.pedalboard('mouseIsOver', event, obj.icon.find('[mod-role=output-midi-port]')))
                    return
                if (self.pedalboard('mouseIsOver', event, obj.icon.find('[mod-role=output-jack]')))
                    return


                // setTimeout avoids cable drawing bug
                setTimeout(function () {
                    self.pedalboard('focusPlugin', obj.icon)
                }, 0)
            },
            presetLoad: function (uri) {
                self.data('pluginPresetLoad')(instance, uri,
                    function (ok) {
                        // TODO Handle error
                    })
            },
            change: function (port, value) {
                self.data('pluginParameterChange')(port, value,
                    function (ok) {
                            // TODO Handle this error
                    })
            },
            bypass: function (bypassed) {
                self.data('pluginBypass')(instance, bypassed,
                    function (ok) {
                        // TODO Handle this error
                    })
            },
            defaultIconTemplate: DEFAULT_ICON_TEMPLATE,
            defaultSettingsTemplate: DEFAULT_SETTINGS_TEMPLATE
        }, guiOptions)

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
        var pluginGui = new GUI(pluginData, options)
        pluginGui.render(instance, function (icon, settings) {
            obj.icon = icon

            self.data('plugins')[instance] = icon

            self.trigger('modified')

            icon.data('url', pluginData.url)
            icon.data('gui', pluginGui)
            icon.data('settings', settings)
            icon.data('instance', instance)

            var hardware = self.data('hardwareManager')
            if (addressing && hardware)
                hardware.unserializeInstance(instance, addressing, self.data('bypassApplication'), addressingErrors)

            var i, symbol, port
            if (hardware) {
                var addressFactory = function (port) {
                    return function () {
                        hardware.open(instance, port, pluginGui.getPortValue(port.symbol))
                    }
                }

                for (i = 0; i < pluginData.ports.control.input.length; i++) {
                    port = pluginData.ports.control.input[i]
                    var address = settings.find('[mod-role=input-control-address][mod-port-symbol=' + port.symbol + ']')
                    if (address.length == 0)
                        continue
                    address.click(addressFactory(port))
                }

                // Let's define bypass like other ports.
                settings.find('[mod-role=bypass-address]').click(function () {
                    hardware.open(instance, pluginGui.controls[':bypass'], pluginGui.bypassed)
                })
            } else {
                settings.find('[mod-role=input-control-address]').hide()
            }

            // Find elements with mod-role of audio/midi input/output ports and assign functionality to them
            var types = ['audio', 'midi']
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

            var actions = $('<div>').addClass('mod-actions').appendTo(icon)
            $('<div>').addClass('mod-settings').click(function () {
                settings.window('open')
                return false
            }).appendTo(actions)
            $('<div>').addClass('mod-remove').click(function () {
                self.pedalboard('removePlugin', instance)
                return false
            }).appendTo(actions)

            settings.window({
                windowManager: self.data('windowManager')
            }).appendTo($('body'))
            icon.css({
                'z-index': self.data('z_index'),
                position: 'absolute',
                left: x,
                top: y
            }).appendTo(self)
            self.data('z_index', self.data('z_index')+1)
            if (renderCallback)
                renderCallback()
        })
    },

    getGui: function (instance) {
        var self = $(this)
        var plugin = self.data('plugins')[instance]
        return plugin.data('gui')
    },

    // Redraw all connections from or to a plugin
    drawPluginJacks: function (plugin) {
        var self = $(this)
        var myjacks = []

        self.data('connectionManager').iterateInstance(plugin.data('instance'), function (jack) {
            myjacks.push($(jack.data('svg')._container))
        })

        $('.hasSVG.cable-connected').filter(function(e) {!(e in myjacks)}).css({'z-index': 0})

        self.data('connectionManager').iterateInstance(plugin.data('instance'), function (jack) {
            self.pedalboard('drawJack', jack)
            $(jack.data('svg')._container).css({ 'z-index': self.data("z_index")-1, 'pointer-events': 'none'})
        })
    },

    // Removes a plugin from pedalboard.
    // Calls application removal function with proper removal callback
    removePlugin: function (instance) {
        var self = $(this)
        var pluginRemove = self.data('pluginRemove')
        pluginRemove(instance, function () {
        })
    },

    removePluginFromCanvas: function (instance) {
        var self = $(this)
        var plugins = self.data('plugins')
        var plugin = plugins[instance]

        var connections = self.data('connectionManager')
        connections.iterateInstance(instance, function (jack) {
            var input = jack.data('destination')
            jack.data('canvas').remove()
            jack.remove()
            self.pedalboard('packJacks', input)
        })
        connections.removeInstance(instance)

        var hw = self.data('hardwareManager')
        if (hw)
            hw.removeInstance(instance)

        delete plugins[instance]

        plugin.remove()
    },

    // Highlight all inputs to which a jack can be connected (any inputs that are not from same
    // instance and are not already connected). Highlight parameter indicates if we want highlighting
    // on or off. If highlight parameter is false, no jack is needed.
    highlightInputs: function (highlight, jack) {
        var self = $(this)
        var connections = self.data('connectionManager')
        if (!highlight) {
            self.find('[mod-role=input-audio-port]').removeClass('input-connecting')
            self.find('[mod-role=input-midi-port]').removeClass('input-connecting')
            self.find('[mod-role=input-audio-port]').removeClass('input-connecting-highlight')
            self.find('[mod-role=input-midi-port]').removeClass('input-connecting-highlight')
            return
        }

        var output = jack.data('origin')
        var fromInstance = output.data('instance')
        var fromSymbol = output.data('symbol')
        var portType = output.data('portType')

        self.find('[mod-role=input-' + portType + '-port]').each(function () {
            var input = $(this)
            var toInstance = input.data('instance')
            var toSymbol = input.data('symbol')
            var ok

            // Do not highlight if this output and input are already connected
            ok = !connections.connected(fromInstance, fromSymbol, toInstance, toSymbol)
                // Neither if output and input belong to same instance
            if (toInstance >= 0) // do not check this on hardware ports
                ok = ok && (fromInstance != toInstance)

            if (ok) {
                input.addClass('input-connecting')
            }
        });
    },

    // Removes all plugins and restore pedalboard initial state, so that a new pedalboard
    // can be created
    reset: function (callback) {
        var self = $(this)

        self.data('bypassApplication', false)

        self.data('reset')(function (ok) {
            if (!ok) {
                return
            }
            self.data('connectionManager').iterateInstance(":system:", function (jack) {
                self.pedalboard('disconnect', jack)
            })
            if (callback)
                callback()
        })
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
            drop: function (event, ui) {
                var jack = ui.draggable

                self.pedalboard('do_connect', jack, element)
                element.removeClass('input-connecting-highlight')
            },
            over: function (event, ui) {
                var outputType = ui.draggable.parent().attr('mod-role').split(/-/)[1]
                var inputType = element.attr('mod-role').split(/-/)[1]
                if (outputType != inputType)
                    return
                self.data('background').droppable('disable');
                element.addClass('input-connecting-highlight')
            },
            out: function (event, ui) {
                self.data('background').droppable('enable');
                element.removeClass('input-connecting-highlight')
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

        element.click(function () {
            self.pedalboard('startConnection', element)
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
        var canvas = $('<div>')
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
                p = ui.position
                p.top /= scale
                p.left /= scale
                self.pedalboard('drawJack', jack, true)
            },
            stop: function () {
                self.pedalboard('preventDrag', false)

                self.pedalboard('highlightInputs', false)

                jack.removeClass('jack-connecting')
                output.removeClass('output-connecting')
                canvas.removeClass('cable-connecting')
                if (!jack.hasClass('jack-connected'))
                    jack.addClass('jack-disconnected')

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
            var xi = source.offset().left / scale - self.offset().left / scale // + source.width()
            var yi = source.offset().top / scale - self.offset().top / scale + source.height() / 2
            var xo = jack.offset().left / scale - self.offset().left / scale
            var yo = jack.offset().top / scale - self.offset().top / scale + jack.height() / 2
            if (source.hasClass("mod-audio-output"))
                self.pedalboard('drawBezier', jack.data('canvas'), xi+12, yi, xo, yo, '')
            else
                self.pedalboard('drawBezier', jack.data('canvas'), xi+9, yi, xo, yo, '')
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
            deltaX = 8.5 * (deltaX / 6) ^ 0.8
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

    do_connect: function (jack, input) {
        var self = $(this)
        var output = jack.data('origin')

        var previousInput = jack.data('destination')

        // If this jack is already connected to this output, keep connection
        // This means user just took a connected jack, dragged around and dropped
        // in the same input
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
            return
        }
        // This jack was connected to some other input, let's disconnect it
        if (previousInput) {
            self.pedalboard('disconnect', jack)
            self.pedalboard('packJacks', previousInput)
        }

        self.data('portConnect')(output.attr('mod-port'), input.attr('mod-port'),
            function (ok) {
                if (!ok)
                    self.pedalboard('disconnect', jack)
            })
    },

    // Connects an output port to an input port.
    // The output is obtained from jack
    connect: function (jack, input) {
        var self = $(this)
        var output = jack.data('origin')

       // If output is already connected to this input through another jack, abort connection
        if (self.pedalboard('connected', output, input))
            return self.pedalboard('disconnect', jack)

        // Can only connect midi to midi and audio to audio
        if (input.data('portType') != output.data('portType'))
            return self.pedalboard('disconnect', jack)

        // Everything ok, let's do the connection
        self.pedalboard('finishConnection')

        // Register the connection in desktop structure
        self.data('connectionManager').connect(output.attr("mod-port"), input.attr("mod-port"),
            jack)

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
        // Pedalboard has been modified
        self.trigger('modified')

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
        } else {
            // UGLY WORKAROUND :(
            if (output.hasClass("mod-audio-output") && !output.hasClass("hardware-output"))
                jack.css({
                    top: 12,
                    left: 0
                })
            else if (output.hasClass("mod-midi-output") && output.hasClass("hardware-output"))
                jack.css({
                    top: -15,
                    left: 0
                })
            else
                jack.css({
                    top: 0,
                    left: 0
                })
        }
        if (Object.keys(self.data('connectionManager').origIndex[output.attr('mod-port')]).length == 1) {
            output.addClass('output-disconnected')
            output.removeClass('output-connected')
        }

        jack.data('connected', false)
    },

    // Connect two ports using instance and symbol information.
    // Used for unserializing. We have to find the spare jack in output,
    // put it
    connectPorts: function (fromInstance, fromSymbol, toInstance, toSymbol) {},

    connected: function (output, input) {
        var self = $(this)
        var manager = self.data('connectionManager')
        return manager.connected(output.attr("mod-port"), input.attr("mod-port"))
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
        var wrapper = $('<div class="mod-pedal-input-wrapper">')
        var arrow = $('<div class="mod-pedal-input-arrow">').appendTo(wrapper)
        wrapper.height(jacks.length * 40 + 10)
        var jack
        wrapper.appendTo(input)
        wrapper.css('top', (input.height() - wrapper.height()) / 2)
        arrow.css('top', wrapper.height() / 2 - 12)
        var jack
        for (var i = 0; i < jacks.length; i++) {
            jack = $(jacks[i])
            jack.css({
                position: 'absolute',
                height: 30,
                marginTop: -wrapper.height() / 2 + jack.height() / 2 + 40 * i + 10,
                width: wrapper.width(),
            })
            self.pedalboard('drawJack', jack)
            jack.draggable('enable')
        }
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
        var from = fromPort.split("/")
        if (from.length == 1)
            var instance = ':system:'
        else
            var instance = from[0]
        if (self.origByInstanceIndex[instance] == null)
            self.origByInstanceIndex[instance] = {}
        self._addToIndex(self.origByInstanceIndex[instance], fromPort, toPort, jack)

        var to = toPort.split("/")
        if (to.length == 1)
            var instance = ':system:'
        else
            var instance = to[0]

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
        var from = fromPort.split("/")
        if (from.length == 1)
            var instance = ':system:'
        else
            var instance = from[0]
        if (self.origByInstanceIndex[instance] != null)
            self._removeFromIndex(self.origByInstanceIndex[instance], fromPort, toPort)

        var to = toPort.split("/")
        if (to.length == 1)
            var instance = ':system:'
        else
            var instance = to[0]
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
