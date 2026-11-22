// SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
// SPDX-License-Identifier: AGPL-3.0-or-later



/*
 * performance view behaviour
 *
 * The interface for managing your pedal board parameters on a touch device
 *
 * Properties:
 */

// Where it is remembered the full screen hint has been seen, see showHint
var FULLSCREEN_HINT_SEEN = 'performance-fullscreen-hint-seen'

JqueryClass('performanceBox', {
    init: function (options) {
        var self = $(this)

        options = $.extend({
            pedalboard: undefined,
            pedalPresets: undefined,
            resultCanvasPlugins: self.find('.js-performance-plugins'),
            resultCanvasPluginSettings: self.find('.js-performance-plugin-settings'),
            visibleFilter: true,
            selectedElement: undefined,
            selectedIndex: -1,
            plugins: [], // filtered plugins
            nodes: [], // rendered plugins
            inDesign: false,
            isMainWindow: true,
            windowName: "Performance",
            selectElement: function (element, callback) {
                const pedalboard = self.data("pedalboard")

                if (pedalboard) {
                    let selectedIndex = -1
                    const displaySelectedElementSettings = self.data("displaySelectedElementSettings")
                    const currSelectedIndex = self.data("selectedIndex")

                    // remove selected from the current selected element
                    if (currSelectedIndex >= 0) {
                        $("#mod-performance-plugin-" + currSelectedIndex.toString())?.removeClass("selected");
                    }

                    if (element === ":presets") {
                        const pedalPresets = self.data("pedalPresets")
                        let div = document.createElement("div")
                        
                        pedalPresets.getPedalPresetList(function(presets) {
                            let data = []
                            
                            Object.keys(presets).forEach(key => data.push({index: data.length + 1, label: presets[key]}) )
                            div.innerHTML = Mustache.render(TEMPLATES.performance_snapshots, {presets: data})
                            let rendered = $(Array.prototype.slice.call(div.childNodes, 0))
                            const settings = rendered[0];

                            // add the selected class
                            selectedIndex = 0;

                            displaySelectedElementSettings(element, selectedIndex, settings, function() {
                                self.data('scrollAndSelectElement')("#mod-performance-plugin-0")

                                // attach events
                                $(".performance .snapshot").each(function(index, snapshotDiv) {
                                    snapshotDiv.onclick = function (e) {
                                        pedalPresets.loadPreset(index, e.target.innerText)
                                    }
                                });
                            })
                        });
                    } else {
                        //TODO: if element is plugin, show plugin settings
                        const plugin = element
                        const plugins = self.data("plugins")
                        // its own face, if that is what is shown, see flip below
                        const settings = self.data("face") ? self.data("faceOf")(plugin)[0]
                                                           : plugin.settingsPerformance[0];

                        selectedIndex = plugins.indexOf(plugin) + 1 // +1 'cause 0 is the snapshot page

                        displaySelectedElementSettings(element, selectedIndex, settings)
                        self.data('scrollAndSelectElement')("#mod-performance-plugin-" + selectedIndex.toString())
                    }
                }
            },

            // The one chosen marked and brought to the middle of the list, along the
            // bottom or down the side, see main.css. By the list's own scroll, which a
            // finger still on the page does not stop, as it does scrollIntoView's
            scrollAndSelectElement: function(elementSelector) {
                let element = $(elementSelector)

                if (element && element[0]) {
                    element.addClass("selected")

                    const list = self.data("resultCanvasPlugins")
                    const el = element[0]
                    if (list[0].scrollWidth > list[0].clientWidth) {
                        list.stop(true).animate({
                            scrollLeft: el.offsetLeft - (list[0].clientWidth - el.offsetWidth) / 2
                        }, 250)
                    } else {
                        list.stop(true).animate({
                            scrollTop: el.offsetTop - (list[0].clientHeight - el.offsetHeight) / 2
                        }, 250)
                    }
                }
            },

            // show the settings for the selected plugin or snapshots
            displaySelectedElementSettings: function(selectedElement, selectedIndex, settings, callback) {
                const settingsContainer = self.data('resultCanvasPluginSettings')
                const settingsDiv = settingsContainer[0];

                self.data('showCurrent')(selectedIndex)
                if (settingsDiv) {
                    $(settingsDiv).fadeOut(200, function() {
                        settingsDiv.innerHTML = ""

                        if (settings) {
                            settingsDiv.appendChild(settings);
                            $(settingsDiv).fadeIn(200);
                        }

                        self.data("selectedElement", selectedElement)
                        self.data("selectedIndex", selectedIndex)
                        if (callback)
                            callback([])
                    })
                }
            },

            /*
             * Update the plugin effect list after a change made by another client,
             * keeping the selected plugin when it is still listed
             */
            refreshPlugins: function() {
                if (!self.is(':visible'))
                    return

                const selectedElement = self.data("selectedElement")

                self.data('updatePlugins')()

                const selectedIndex = self.data("plugins").indexOf(selectedElement) + 1 // +1 'cause 0 is the snapshot page

                if (selectedElement === ":presets") {
                    $("#mod-performance-plugin-0").addClass("selected")
                } else if (selectedIndex > 0) {
                    self.data("selectedIndex", selectedIndex)
                    $("#mod-performance-plugin-" + selectedIndex.toString()).addClass("selected")
                } else {
                    self.data('selectElement')(":presets")
                }
            },

            // What is shown, for full screen, the list that says so being gone, see below:
            // its picture, its name, and where it is among them all, the snapshots first
            showCurrent: function(index) {
                const element = $("#mod-performance-plugin-" + index.toString())
                const current = self.find('.current-plugin')

                current.find('img').attr('src', element.find('img').attr('src'))
                current.find('.name').text(element.find('.title').text())
                current.find('.position').text((index + 1) + '/' + (self.data('plugins').length + 1))
                current.find('.previous').toggleClass('disabled', index == 0)
                current.find('.next').toggleClass('disabled', index == self.data('plugins').length)
            },

            /*
             * Update the plugin effect list
             */
            updatePlugins: function() {
                const pedalboard = self.data("pedalboard")

                if (!pedalboard)
                    return

                const plugins = pedalboard.data("plugins")
                const canvas = self.data("resultCanvasPlugins")

                canvas[0].innerHTML = ""

                // append snapshot view
                var div = document.createElement("div");
        
                div.innerHTML = Mustache.render(TEMPLATES.performance_plugin, {
                    uri   : ":presets",
                    brand : "&nbsp;",
                    label : "Snapshots",
                    thumbnail_href: "/img/presets.png"
                });
                var rendered = $(Array.prototype.slice.call(div.childNodes, 0))

                rendered[0].id = "mod-performance-plugin-0"

                rendered.click(function () {
                    self.data("selectElement")(":presets")
                })
                canvas.append(rendered);

                // TODO: controls assigned to phisical mod

                // append effects controls one by one
                const visibleFilter = self.data("visibleFilter")
                var guis = []

                for (pluginKey in plugins) {
                    guis.push(plugins[pluginKey].data("gui"))
                }
                guis = guis
                        .filter(item => !visibleFilter || item.getPerformanceOptions()?.visible === visibleFilter)
                        .sort(function(a,b) {
                            const pa = a.getPerformanceOptions()
                            const pb = b.getPerformanceOptions()
                            const labela = a.label || a.effect.name
                            const labelb = b.label || b.effect.name

                            //console.log(`${labela}-${pa.index} vs ${labelb}-${pb.index}`)
                            if (pa.index < pb.index)
                                return -1
                            else if (pa.index > pb.index)
                                return 1
                            else {
                                if (labela < labelb)
                                    return -1
                                else if (labela > labelb)
                                    return 1
                                else
                                    return 0
                            }
                        })

                let index = 1
                self.data('plugins', guis)
                let nodes = []
                for (key in guis) { 
                    const gui = guis[key];
                    
                    const node = self.performanceBox("renderPlugin", index, gui, canvas)
                    nodes.push(node)
                    index += 1
                }

                self.data('nodes', nodes)

                const saveButton = $('#performance-save-button')
                if (saveButton) {
                    if (self.data("inDesign")) {
                        saveButton.removeClass('mod-hidden')
                    } else {
                        saveButton.addClass('mod-hidden')
                    }
                }
            },

            savePedalboard: function() {
                desktop.saveCurrentPedalboard(false)
            }
        }, options)

        self.data(options)

        options.open = function () {
            // check the default for the visibleFilter: if any plugin is favorite the filter will be true on oper
            const pedalboard = self.data("pedalboard")

            if (pedalboard) {
                let defaultvisibleFilter = false;
                const plugins = pedalboard.data("plugins")
                for (pluginKey in plugins) {
                    const gui = plugins[pluginKey].data("gui")

                    if (gui.getPerformanceOptions().visible) {
                        defaultvisibleFilter = true;
                        break;
                    }
                }

                self.data('visibleFilter', defaultvisibleFilter)
                self.data('showVisibleFilter')()
            }

            // it starts on the plugins' own faces
            self.data('face', true)

            self.data('updatePlugins')()
            self.data("selectElement")(":presets")

            return false
        }

        // The plugins listed down the side rather than along the bottom, see main.css
        const sideways = window.matchMedia('screen and (max-width: 1022px) and (orientation: landscape)')

        // Goes to the next plugin, or the one before, the snapshots first of all: whether
        // there is one that way
        const step = function (dir) {
            const index = Math.max(0, self.data("selectedIndex") + dir)
            const pluginDiv = $("#mod-performance-plugin-" + index.toString())

            if (index == self.data("selectedIndex") || ! pluginDiv[0]) {
                return false
            }
            const selectedElement = index == 0 ? ":presets" : pluginDiv.data("plugin")
            if (! selectedElement) {
                return false
            }
            self.data('selectElement')(selectedElement)
            return true
        }

        const canvas = self.data("resultCanvasPlugins")
        canvas.bind("mousewheel", function(event, delta, deltaX, deltaY) {
            let index = self.data("selectedIndex")
            
            index -= deltaY;
            if (index < 0)
                index = 0;

            const pluginDiv = $("#mod-performance-plugin-" + index.toString())

            if (pluginDiv && pluginDiv[0]) {
                let selectedElement;

                if (index == 0) { // snapshots
                    selectedElement = ":presets";
                } else {
                    const plugin = pluginDiv.data("plugin")

                    if (plugin) {
                        selectedElement = plugin
                    }
                }
                self.data('selectElement')(selectedElement)
            }
            event.preventDefault();
        });

        // A finger along the list of plugins, the way it runs, goes to the next one or
        // the one before, one a swipe, as on what is shown, see below: it is not scrolled
        // by hand, the one chosen is brought into it. Not while arranging them, when a
        // finger drags them
        let listSwipe = null
        canvas.on('pointerdown', function (e) {
            const ev = e.originalEvent
            listSwipe = ev.pointerType == 'mouse' || ! ev.isPrimary || self.data("inDesign") ? null :
                        { id: ev.pointerId, x: ev.clientX, y: ev.clientY, down: sideways.matches }
        }).on('pointermove', function (e) {
            const ev = e.originalEvent
            if (! listSwipe || ev.pointerId != listSwipe.id) {
                return
            }
            const along = listSwipe.down ? ev.clientY - listSwipe.y : ev.clientX - listSwipe.x
            if (Math.abs(along) < 30) {
                return
            }
            listSwipe = null
            step(along < 0 ? 1 : -1)
        }).on('pointerup pointercancel', function () {
            listSwipe = null
        })

        // What is shown, and where on it a finger is taken by a control rather than by the
        // gestures below
        const settingsCanvas = self.data('resultCanvasPluginSettings')
        const controls = '.mod-knob-image, .mod-switch-image, .mod-enumerated-list, .mod-presets-menu, ' +
                         '.mod-ab-toggle, .mod-address, .mod-knob-snapshot-status, input, select, textarea, button, a, ' +
                         '[mod-role=input-control-port], [mod-role=bypass], [mod-role=presets]'

        // A plugin's own face, which a double tap on its settings, off their controls,
        // flips to, and one on the face back: its controls work there too. As big as fits
        // where the settings were, up to twice its size. It stays the face shown going to
        // another plugin, the snapshots having no other
        const faceOf = function (plugin) {
            const face = $('<div class="mod-performance-face">').append(plugin.performanceIcon())
            fitFace(face, 20)
            return face
        }
        // once it is shown, which may be after the settings before it have faded out
        const fitFace = function (face, tries) {
            // as big as what it holds, placed inside it, as the board makes its plugins
            const icon = face.children('.mod-pedal')
            const inner = icon.children().first()
            const width = inner[0] && inner[0].offsetWidth, height = inner[0] && inner[0].offsetHeight
            if (! width || ! height || ! face.width()) {
                if (tries) {
                    setTimeout(function () {
                        fitFace(face, tries - 1)
                    }, 50)
                }
                return
            }
            const scale = Math.min(2, (face.width() - 32) / width, (face.height() - 32) / height)
            icon.css({ width: width, height: height, transform: 'scale(' + scale + ')' })
        }
        self.data('faceOf', faceOf)
        const fitFaces = function () {
            settingsCanvas.find('.mod-performance-face').each(function () {
                fitFace($(this))
            })
        }
        $(window).on('resize', fitFaces)
        const FLIP = 350
        const flip = function () {
            const element = self.data("selectedElement")
            if (! element || element === ":presets" || settingsCanvas.hasClass('mod-flip-away')) {
                return
            }
            const toFace = ! self.data("face")
            settingsCanvas.removeClass('mod-flip-back').addClass('mod-flip-away')
            setTimeout(function () {
                self.data("face", toFace)
                // the settings and the face are kept, with what they do, for next time
                settingsCanvas.children().detach()
                settingsCanvas.append(toFace ? faceOf(element) : element.settingsPerformance)
                settingsCanvas.removeClass('mod-flip-away').addClass('mod-flip-back')
                setTimeout(function () {
                    settingsCanvas.removeClass('mod-flip-back')
                }, FLIP)
            }, FLIP)
        }
        // A tap on the plugin in the list already shown flips it too, rather than
        // choosing it again. Not while arranging them
        let listDown = null, listFlipped = false
        canvas.on('pointerdown', function (e) {
            const item = $(e.originalEvent.target).closest('.plugin')
            listDown = item.hasClass('selected') ? e.originalEvent : null
        }).on('pointerup', function (e) {
            const ev = e.originalEvent
            const down = listDown
            listDown = null
            if (! down || down.pointerId != ev.pointerId || self.data("inDesign") ||
                Math.abs(ev.clientX - down.clientX) > 10 || Math.abs(ev.clientY - down.clientY) > 10) {
                return
            }
            listFlipped = true
            flip()
        })
        // the tap's click, which would choose it again, kept from it
        canvas[0].addEventListener('click', function (e) {
            if (listFlipped) {
                listFlipped = false
                e.stopPropagation()
            }
        }, true)

        let tapped = 0, tapDown = null
        settingsCanvas.on('pointerdown', function (e) {
            tapDown = e.originalEvent
        }).on('pointerup', function (e) {
            const ev = e.originalEvent
            const down = tapDown
            tapDown = null
            if (! down || down.pointerId != ev.pointerId ||
                Math.abs(ev.clientX - down.clientX) > 10 || Math.abs(ev.clientY - down.clientY) > 10 ||
                $(ev.target).closest(controls).length) {
                return
            }
            if (Date.now() - tapped < 350) {
                tapped = 0
                flip()
            } else {
                tapped = Date.now()
            }
        })

        // A finger on what is shown, the way the list runs, across with it along the
        // bottom, up and down with it down the side (see main.css): a carousel. What is
        // shown follows the finger, and let go a quarter of the way on, or flicked, the
        // next plugin comes, or the one before, and it goes back otherwise. Not starting
        // on the controls, which take the finger themselves, nor the other way, which
        // scrolls. A plugin's face, which does not scroll, goes across whichever way the
        // list runs, and also the way it runs
        let swipe = null
        const slide = function (el, along, down, animated) {
            el.style.transition = animated ? 'transform 0.2s ease, opacity 0.2s ease' : ''
            el.style.transform = along ? (down ? 'translateY(' : 'translateX(') + along + 'px)' : ''
        }
        settingsCanvas.on('pointerdown', function (e) {
            const ev = e.originalEvent
            if (ev.pointerType == 'mouse' || ! ev.isPrimary || $(ev.target).closest(controls).length) {
                swipe = null
                return
            }
            swipe = { id: ev.pointerId, x: ev.clientX, y: ev.clientY, t: Date.now(),
                      down: sideways.matches && ! self.data("face"), free: sideways.matches && !! self.data("face"),
                      along: 0, going: false }
        }).on('pointermove', function (e) {
            const ev = e.originalEvent
            if (! swipe || ev.pointerId != swipe.id) {
                return
            }
            if (swipe.free && ! swipe.going) {
                swipe.down = Math.abs(ev.clientY - swipe.y) > Math.abs(ev.clientX - swipe.x)
            }
            const along = swipe.down ? ev.clientY - swipe.y : ev.clientX - swipe.x
            const across = swipe.down ? ev.clientX - swipe.x : ev.clientY - swipe.y
            if (! swipe.going) {
                if (Math.abs(along) < 12 && Math.abs(across) < 12) {
                    return
                }
                // the other way, a scroll
                if (Math.abs(across) >= Math.abs(along)) {
                    swipe = null
                    return
                }
                swipe.going = true
                try {
                    this.setPointerCapture(ev.pointerId)
                } catch (err) {}
            }
            swipe.along = along
            slide(this, along, swipe.down, false)
        }).on('pointerup pointercancel', function (e) {
            const ev = e.originalEvent
            if (! swipe || ev.pointerId != swipe.id) {
                return
            }
            const s = swipe
            swipe = null
            if (! s.going) {
                return
            }
            const el = this
            const rect = el.getBoundingClientRect()
            const size = s.down ? rect.height : rect.width
            const fast = Math.abs(s.along) / Math.max(1, Date.now() - s.t) > 0.5
            const dir = s.along < 0 ? 1 : -1
            if (e.type == 'pointerup' && (Math.abs(s.along) > size / 4 || fast) && step(dir)) {
                // out the way it went, then in place for the next, which fades in
                slide(el, -dir * size, s.down, true)
                setTimeout(function () {
                    slide(el, 0, s.down, false)
                }, 200)
            } else {
                slide(el, 0, s.down, true)
            }
        })

        // Full screen, from the button by the title, which stays: no list, what
        // is shown has it all, going from one to the next by the swipes above, and it says
        // which it is by itself, see showCurrent. It ends with the view
        const fullscreenButton = self.find('#performance-fullscreen')
        const current = self.find('.current-plugin')
        const hint = self.find('.fullscreen-hint')
        let hintOver = null
        // The first time only, in this browser: the arrows nudge and it says what they
        // and a swipe do. Where nothing can be remembered, the first time each time
        const showHint = function () {
            try {
                if (localStorage.getItem(FULLSCREEN_HINT_SEEN)) {
                    return
                }
                localStorage.setItem(FULLSCREEN_HINT_SEEN, '1')
            } catch (err) {}
            current.add(hint).addClass('hinting')
            hintOver = setTimeout(hideHint, 4000)
        }
        const hideHint = function () {
            clearTimeout(hintOver)
            current.add(hint).removeClass('hinting')
        }
        const setFullscreen = function (on) {
            $('body').toggleClass('performance-fullscreen', on)
            fullscreenButton.attr('title', on ? 'Back to the list' : 'Controls full screen')
            fitFaces()
            if (on) {
                showHint()
            } else {
                hideHint()
            }
        }
        fullscreenButton.click(function () {
            setFullscreen(! $('body').hasClass('performance-fullscreen'))
        })
        self.on('windowclose', function () {
            setFullscreen(false)
        })

        // There, a swipe across the plugin's name or the title, a mouse's too, or lying
        // low anywhere along the strip they are on, goes to the next plugin or the one
        // before, whichever way what is shown goes, one a swipe. A double tap there flips
        // it, as on what is shown
        let stripSwipe = null, swiped = false, stripTapped = 0
        self.find('header, .current-plugin, .fullscreen-strip').on('pointerdown', function (e) {
            const ev = e.originalEvent
            stripSwipe = null
            swiped = false
            if (! $('body').hasClass('performance-fullscreen') || ! ev.isPrimary || $(ev.target).closest('.fullscreen-toggle').length) {
                return
            }
            const arrow = $(ev.target).closest('.go').length > 0
            stripSwipe = { id: ev.pointerId, x: ev.clientX, y: ev.clientY, arrow: arrow }
            // captured, an arrow would not get its click
            if (arrow) {
                return
            }
            try {
                this.setPointerCapture(ev.pointerId)
            } catch (err) {}
        }).on('pointermove', function (e) {
            const ev = e.originalEvent
            if (! stripSwipe || ev.pointerId != stripSwipe.id) {
                return
            }
            const along = ev.clientX - stripSwipe.x
            if (Math.abs(along) < 30 || Math.abs(along) < Math.abs(ev.clientY - stripSwipe.y)) {
                return
            }
            stripSwipe = null
            swiped = true
            hideHint()
            step(along < 0 ? 1 : -1)
        }).on('pointerup pointercancel', function (e) {
            const ev = e.originalEvent
            const tap = e.type == 'pointerup' && stripSwipe && ! stripSwipe.arrow &&
                        Math.abs(ev.clientX - stripSwipe.x) < 12 && Math.abs(ev.clientY - stripSwipe.y) < 12
            stripSwipe = null
            if (! tap) {
                return
            }
            if (Date.now() - stripTapped < 350) {
                stripTapped = 0
                flip()
            } else {
                stripTapped = Date.now()
            }
        })
        current.find('.go').click(function () {
            if (! swiped) {
                hideHint()
                step($(this).hasClass('next') ? 1 : -1)
            }
        })

        // The crossed eye: plain while the plugins not made visible are left out, lit while
        // they are shown too
        const visibleFilterButton = self.find('#performance-filter-visibility')
        self.data('showVisibleFilter', function () {
            const all = !self.data('visibleFilter')
            visibleFilterButton.toggleClass('active', all)
                .attr('title', all ? 'Showing the hidden plugins too: hide them' : 'Hidden plugins left out: show them')
        })
        visibleFilterButton.click(function() {
            const newValue = !self.data('visibleFilter')

            self.data('visibleFilter', newValue)
            self.data('showVisibleFilter')()
            self.data('updatePlugins')()
            self.data("selectElement")(":presets")
        });

        // enable drag & drop on mobile
        const settingsButton = self.find("#performance-design-button")
        settingsButton.click(function() {
            const newInDesign = !self.data("inDesign")

            if (newInDesign) {
                visibleFilterButton.removeClass("mod-hidden")
            } else {
                visibleFilterButton.addClass("mod-hidden")
            }

            self.data("inDesign", newInDesign)
            self.data('updatePlugins')()
            self.data("selectElement")(":presets")
        });

        // display save pedalboard button
        const saveButton = $('#performance-save-button')
        saveButton?.click(function() {
            self.data('savePedalboard')()
        })

        self.window(options)
        return self
    },

    renderPlugin: function (index, plugin, container) {
        var self = $(this)
        if (container.length == 0)
            return
        var uri = escape(plugin.effect.uri)
        var ver = [plugin.effect.builder, plugin.effect.microVersion, plugin.effect.minorVersion, plugin.effect.release].join('_')

        var plugin_data = {
            uri   : uri,
            brand : !plugin.effect.brand ? "&nbsp;": plugin.effect.brand,
            label : plugin.label || plugin.effect.label,
            thumbnail_href: (plugin.effect.gui && plugin.effect.gui.thumbnail)
                          ? ("/effect/image/thumbnail.png?uri=" + uri + "&v=" + ver)
                          :  "/resources/pedals/default-thumbnail.png",
        }

        if (window.devicePixelRatio && window.devicePixelRatio >= 2) {
            plugin_data.thumbnail_href = plugin_data.thumbnail_href.replace("thumbnail","screenshot")
        }

        const visibleFilter = self.data('visibleFilter')
        var div = document.createElement("div");

        div.innerHTML = Mustache.render(TEMPLATES.performance_plugin, plugin_data);
        var rendered = $(Array.prototype.slice.call(div.childNodes, 0));

        rendered[0].id = "mod-performance-plugin-" + index.toString()
        $(rendered).data('plugin', plugin)
        rendered[0].setAttribute('mod-instance', plugin.instance)

        if (self.data("inDesign")) {
            // enable drag & drop in design mode
            rendered.draggable({
                axis: desktop.isMobile ? "y" : "x",
                scroll: true,
                revert: true,
                handle: desktop.isMobile ? "img" : null,
                start: function() {
                    rendered.zIndex(1)
                    rendered.css('opacity', '0.8')
                },
                stop: function() {
                    rendered.zIndex(0)
                    rendered.css('opacity', '1')

                }
            })

            rendered.droppable({
                drop: function( event, ui ) {
                    // swap position rendered with ui using jquery
                    var target = plugin.getPerformanceOptions()
                    var draggedPlugin = ui.draggable.data('plugin') 
                    var source = draggedPlugin.getPerformanceOptions();

                    const tmp = target.index
                    target.index = source.index
                    source.index = tmp

                    self.data('updatePlugins')()
                    self.data("selectElement")(draggedPlugin)

                    // let the host know about this change
                    desktop.pedalboard.data('performancePluginIndexSet')(plugin.instance, target.index)
                    desktop.pedalboard.data('performancePluginIndexSet')(draggedPlugin.instance, source.index)
                }
            })

            const iconFavorite = rendered.find('.icon-visible')

            if (iconFavorite) {
                if (visibleFilter === false) {
                    iconFavorite.removeClass('hidden')
                    if (plugin.getPerformanceOptions()?.visible ?? false) {
                        iconFavorite.addClass("icon-eye")
                        iconFavorite.addClass("is-visible")
                    } else {
                        iconFavorite.addClass("icon-eye-off")
                    }
                    iconFavorite.click(function(e) {
                        const performanceOptions = plugin.getPerformanceOptions()
                        const visible = !(performanceOptions.visible ?? false);

                        if (visible) {
                            iconFavorite.removeClass('icon-eye-off')
                            iconFavorite.addClass("icon-eye")
                            iconFavorite.addClass("is-visible")
                        } else {
                            iconFavorite.addClass('icon-eye-off')
                            iconFavorite.removeClass("icon-eye")
                            iconFavorite.removeClass("is-visible")
                        }
                        //console.log(`plugin ${plugin.instance} toggle visible: ${visible}`)

                        performanceOptions.visible = visible
                        // let the host know about this change
                        desktop.pedalboard.data('performancePluginVisibilitySet')(plugin.instance, visible)

                        e.stopPropagation()
                    })
                } else {
                    iconFavorite.addClass('hidden')
                }
            }

            const renameBox = rendered.find('.label-container')

            renameBox?.click(function() {
                desktop.openInputBoxWindow('Rename', plugin.label || plugin.effect.name, function(newName, cancelled) {
                    if (cancelled)
                        return

                    plugin.setLabel(newName)
                    // update the UI label & settings label
                    rendered?.find('.title')?.text(plugin.label || plugin.effect.label)
                },
                'Rename',
                function(value) {
                    return true; // always valid
                })
            })
            renameBox?.find('.icon')?.removeClass('mod-hidden')
        } else if (visibleFilter === false && ! (plugin.getPerformanceOptions()?.visible ?? false)) {
            // showing them all, those not made visible say so, only as a state: they are
            // made visible arranging the view
            rendered.find('.icon-visible').addClass('icon-eye-off visibility-state')
        }

        rendered.click(function () {
            self.data('selectElement')(plugin)
        })

        container.append(rendered)

        return rendered
    }
})
