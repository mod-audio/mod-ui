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

/*
 * effectBox
 *
 * The interface for searching, selecting and installing plugins
 *
 * Properties:
 * - mode: The search mode, indicated by top buttons
 * - searchbox: dom of search's input
 * - resultCanvas: dom div in which results will be shown
 * - categoryBrowse: dom div with category menu
 * - results: dictionary containing detailed data of all plugins
 *            displayed
 */

JqueryClass('effectBox', {
    init: function (options) {
        var self = $(this)

        options = $.extend({
            pedalboard: $('<div>'),
            windowManager: null,
            userSession: null,
        }, options)

        self.data(options)
        self.data('showPluginsRenderId', 0)

        var searchbox = self.find('input[type=search]')
        self.data('searchbox', searchbox)
        searchbox.cleanableInput()
        searchbox.keydown(function (e) {
            if (e.keyCode == 13) { //detect enter
                self.effectBox('search')
                return false
            }
            else if (e.keyCode == 8 || e.keyCode == 46) { //detect delete and backspace
                setTimeout(function () {
                    self.effectBox('search')
                }, 400);
            }
        })
        var lastKeyUp = null
        searchbox.keypress(function (e) { // keypress won't detect delete and backspace but will only allow inputable keys
            if (e.which == 13)
                return
            if (lastKeyUp != null) {
                clearTimeout(lastKeyUp)
                lastKeyUp = null
            }
            if (e.which == 13)
                return
            lastKeyUp = setTimeout(function () {
                self.effectBox('search')
            }, 400);
        })

        var settingsBox = self.find('#plugins-library-settings-window')
        settingsBox.window({
            windowManager: options.windowManager,
            trigger: self.find('.js-settings-trigger')
        })
        self.find('.js-settings-trigger').click(function(){
            $('#effectSearch').focus() // will focus the input when clicking the search icon
        })

        self.droppable({
            accept: '.js-available-effect',
            drop: function (event, ui) {
                //ui.helper.consumed = true
            }
        })

        self.data('category', null)
        // CATEGORY TABS
        self.find('ul.js-category-tabs li').click(function () {
            var category = $(this).attr('id').replace(/^effect-tab-/, '')
            self.effectBox('setCategory', category)
        })

        self.find('.js-effects-fold').click(function () {
            self.effectBox('toggle')
        })

        self.find('.nav-left').click(function () {
            self.effectBox('shiftLeft')
        })
        self.find('.nav-right').click(function () {
            self.effectBox('shiftRight')
        })

        //self.effectBox('fold')
        self.effectBox('setCategory', 'All')
        self.effectBox('search')

        self.mouseenter(function () { self.effectBox('mouseEnter'); });
        $("#main-menu").mouseenter(function () { self.trigger("mouseenter") });
        return self
    },

    fold: function () {
        var self = $(this)
        //self.find('.js-effects-list').hide()
        self.addClass('folded')
        //self.find('.js-effects-fold').hide()
    },

    unfold: function () {
        var self = $(this)
        //self.find('.js-effects-list').show()
        self.removeClass('folded')
        //self.find('.js-effects-fold').show()
    },

    toggle: function () {
        var self = $(this);
        if (self.hasClass('auto')) {
            self.trigger("mouseleave");
            self.effectBox('unfold')
        } else
            self.effectBox('fold')
        self.toggleClass("auto");
    },

    mouseEnter: function (e) {
        var self = $(this);
        if (self.hasClass('auto')) {
            self.one("mouseleave", function () { self.effectBox('fold'); });
            self.effectBox('unfold');
        }
    },

    setCategory: function (category) {
        var self = $(this)
        self.find('ul.js-category-tabs li').removeClass('selected')
        self.find('.plugins-wrapper').hide()
        self.find('#effect-tab-' + category).addClass('selected')
        self.find('#effect-content-' + category).show().css('display', 'inline-block')
        self.data('category', category)
        self.effectBox('unfold')
        self.effectBox('calculateNavigation')
    },

    search: function () {
        var self = $(this)
        var searchbox = self.data('searchbox')
        var term = searchbox.val()

        if (term)
        {
            var allplugins = desktop.pluginIndexerData
            var plugins    = []

            var ret = desktop.pluginIndexer.search(term)
            for (var i in ret) {
                var uri = ret[i].ref
                plugins.push(allplugins[uri])
            }

            self.effectBox('showPlugins', plugins)
        }
        else
        {
            $.ajax({
                method: 'GET',
                url: '/effect/list',
                success: function (plugins) {
                    var allplugins = {}
                    for (var i in plugins) {
                        var plugin = plugins[i]
                        plugin.installedVersion = [plugin.minorVersion, plugin.microVersion, plugin.release || 0]

                        allplugins[plugin.uri] = plugin
                        desktop.pluginIndexer.add({
                            id: plugin.uri,
                            data: [plugin.uri, plugin.name, plugin.brand, plugin.comment, plugin.category.join(" ")].join(" "),
                        })
                    }
                    desktop.pluginIndexerData = allplugins
                    self.effectBox('showPlugins', plugins)
                },
                dataType: 'json'
            })
        }
    },

    showPlugins: function (plugins) {
        var self = $(this)
        self.effectBox('cleanResults')
        plugins.sort(function (a, b) {
            if (a.label > b.label)
                return 1
            if (a.label < b.label)
                return -1
            return 0
        })

        // count plugins first
        var pluginCount = plugins.length
        var categories = {
            'All': 0
        }
        var category
        for (i in plugins) {
            category = plugins[i].category[0]
            if (category) {
                if (categories[category] == null)
                    categories[category] = 1
                else
                    categories[category] += 1
            }
            categories.All += 1
        }

        // display plugin count
        for (category in categories) {
            var tab = self.find('#effect-tab-' + category)
            tab.html(tab.html() + ' (' + categories[category] + ')')
        }

        // disable navigation while we render plugins
        self.find('.nav-left').addClass('disabled')
        self.find('.nav-right').addClass('disabled')

        var renderedIndex = 0

        // current render id, to check if another render has been called
        var currentRenderId = self.data('showPluginsRenderId')+1
        self.data('showPluginsRenderId', currentRenderId)

        // render plugins
        var plugin
        function renderNextPlugin() {
            if (self.data('showPluginsRenderId') != currentRenderId) {
                // another render is in place, stop this one
                return
            }

            if (renderedIndex >= pluginCount) {
                // if we get here it means we finished rendering
                self.effectBox('calculateNavigation')

                if (self.data('showPluginsRenderId') == currentRenderId) {
                    // no other renders in queue, take the chance and reset the id
                    self.data('showPluginsRenderId', 0)
                }
                return
            }

            plugin   = plugins[renderedIndex]
            category = plugin.category[0]

            self.effectBox('renderPlugin', plugin, self.find('#effect-content-All'))

            if (category && category != 'All') {
                self.effectBox('renderPlugin', plugin, self.find('#effect-content-' + category))
            }

            renderedIndex += 1
            setTimeout(renderNextPlugin, 1);
        }

        renderNextPlugin(0)
    },

    renderPlugin: function (plugin, container) {
        var self = $(this)
        if (container.length == 0)
            return
        var uri = escape(plugin.uri)

        var plugin_data = {
            uri   : uri,
            brand : plugin.brand,
            label : plugin.label,
            thumbnail_href: (plugin.gui && plugin.gui.thumbnail)
                          ? ("/effect/image/thumbnail.png?uri=" + uri)
                          :  "/resources/pedals/default-thumbnail.png",
        }

        var rendered = $(Mustache.render(TEMPLATES.plugin, plugin_data))

        self.data('pedalboard').pedalboard('registerAvailablePlugin', rendered, plugin, {
            distance: 5,
            delay: 100,
            start: function () {
                if (self.data('info'))
                    self.data('info').remove()
                self.data('windowManager').closeWindows()
                self.window('fade')
            },
            stop: function () {
                self.window('unfade')
            }
        })

        rendered.click(function () {
            self.effectBox('showPluginInfo', plugin)
        })

        container.append(rendered)

        // this 200px extra is a good margin to make sure the container's parent will
        // always be big enough. it's impossible at this moment to know the necessary width,
        // as this will be given by images not yet loaded.
        container.parent().width(container.parent().width() + rendered.width() + 200)
    },

    showPluginInfo: function (plugin) {
        
        function formatNum(x) {
            var parts = x.toString().split(".");
            parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
            return parts.join(".");
        }

        var self = $(this)
        var uri  = escape(plugin.uri)
        
        var showInfo = function() {

            for(var i = 0; i< plugin.ports.control.input.length; i++) {  // formating numbers and flooring ranges up to two decimal cases

                plugin.ports.control.input[i].formatted = {}

                plugin.ports.control.input[i].formatted.default = formatNum(Math.floor(plugin.ports.control.input[i].ranges.default * 100) / 100);
                plugin.ports.control.input[i].formatted.maximum = formatNum(Math.floor(plugin.ports.control.input[i].ranges.maximum * 100) / 100);
                plugin.ports.control.input[i].formatted.minimum = formatNum(Math.floor(plugin.ports.control.input[i].ranges.minimum * 100) / 100);
                
            }

            var comment = plugin.comment
            var has_description = ""
            if(!comment) {
                comment = "No description available";
                has_description = "no_description";
            }

            var metadata = {
                author: plugin.author,
                comment: comment,
                has_description: has_description,
                thumbnail_href: (plugin.gui && plugin.gui.thumbnail)
                              ? "/effect/image/thumbnail.png?uri=" + uri
                              : "/resources/pedals/default-thumbnail.png",
                screenshot_href: (plugin.gui && plugin.gui.screenshot)
                              ? "/effect/image/screenshot.png?uri=" + uri
                              : "/resources/pedals/default-screenshot.png",
                category: plugin.category[0] || "",
                installed_version: version(plugin.installedVersion),
                latest_version: "DO NOT SHOW THIS!!", // not shown on local plugin bar
                package_name: plugin.bundles[0].replace(/\.lv2$/, ''),
                comment: plugin.comment || "No description available",
                brand : plugin.brand,
                name  : plugin.name,
                label : plugin.label,
                ports : plugin.ports,
            }

            var info = $(Mustache.render(TEMPLATES.cloudplugin_info, metadata))

            //hide install etc buttons
            info.find('.js-remove').hide()
            info.find('.js-install').hide()
            info.find('.js-upgrade').hide()
            info.find('.js-latest-version').hide()

            info.window({
                windowManager: self.data('windowManager'),
                close: function () {
                    info.remove()
                    self.data('info', null)
                }
            })

            info.appendTo($('body'))
            info.window('open')
            self.data('info', info)
        }

        if (plugin.bundles) {
            showInfo()
        } else {
            $.ajax({
                url: "/effect/get",
                data: {
                    uri: plugin.uri
                },
                success: function (pluginData) {
                    plugin = $.extend(plugin, pluginData)
                    desktop.pluginIndexerData[plugin.uri] = plugin
                    showInfo()
                },
                dataType: 'json'
            })
        }
    },

    getReviews: function (uri, info, callback) {
        // not implemented on cloud yet
        if (callback) callback()
        return

        var self = $(this)
        $.ajax({
            url: SITEURL + '/effect/reviews/',
            data: {
                uri: uri
            },
            success: function (comments) {
                var classes = ['', 'one', 'two', 'three', 'four', 'five']
                for (var i in comments) {
                    comments[i].created = renderTime(new Date(comments[i].created * 1000))
                    if (comments[i].rating)
                        comments[i].rating = classes[comments[i].rating]
                }
                var reviews = $(Mustache.render(TEMPLATES.plugin_reviews, {
                    comments: comments
                }))
                info.find('section.comments').html('').append(reviews)
                if (callback)
                    callback()
            },
            dataType: 'json'
        })
    },

    getRating: function (plugin, widget, callback) {
        var self = $(this)
        var userSession = self.data('userSession')
        var classes = ['---', 'one', 'two', 'three', 'four', 'five']
        var setRate = function (rating) {
            for (var i in classes)
                widget.removeClass(classes[i])
            if (rating)
                widget.addClass(classes[rating])
        }
        var rate = function (element) {
            var rating
            for (var i in classes) {
                if (element.hasClass(classes[i]))
                    rating = i
            }
            setRate(rating)
            $.ajax({
                url: SITEURL + '/effect/rate/' + userSession.sid,
                data: JSON.stringify({
                    uri: plugin.uri,
                    version: plugin.latestVersion,
                    rating: rating
                }),
                method: 'POST',
                success: function (result) {
                    if (result.ok)
                        setRate(result.rating)
                    else
                        alert(result.error)
                },
                dataType: 'json'
            })
        }
        if (!userSession.sid) {
            widget.children().click(function () {
                var element = $(this)
                userSession.login(function () {
                    rate(element)
                })
            })
            if (callback)
                callback()
            return
        }
        $.ajax({
            url: SITEURL + '/effect/rate/' + userSession.sid + '/mine',
            data: {
                uri: plugin.uri
            },
            success: function (rating) {
                setRate(rating)
                widget.children().click(function () {
                    rate($(this))
                })
                if (callback)
                    callback()
            },
            dataType: 'json'
        })
    },

    cleanResults: function () {
        var self = $(this)
        self.find('.plugins-wrapper').html('')
        self.find('ul.js-category-tabs li').each(function () {
            $(this).html($(this).html().split(/\s/)[0])
        });
        self.effectBox('resetShift')
            //$('#js-effect-info').hide()
    },

    calculateNavigation: function () {
        var self = $(this)
        var wrapper = self.find('.plugins-wrapper:visible')
        if (wrapper.length == 0)
            return
        var shift = wrapper.position().left
        var maxShift = Math.max(0, wrapper.width() - wrapper.parent().width())
        if (shift == 0)
            self.find('.nav-left').addClass('disabled')
        else
            self.find('.nav-left').removeClass('disabled')
        if (shift == maxShift)
            self.find('.nav-right').addClass('disabled')
        else
            self.find('.nav-right').removeClass('disabled')
    },

    resetShift: function () {
        $(this).find('.plugins-wrapper').css('left', 0)
    },

    shiftLeft: function () {
        var self = $(this)
        var wrapper = self.find('.plugins-wrapper:visible')
        var parent = wrapper.parent().parent()
        var shift = -wrapper.position().left
        var newShift = Math.max(0, shift - parent.width())
        self.effectBox('shiftTo', newShift)
    },

    shiftRight: function () {
        var self = $(this)
        var wrapper = self.find('.plugins-wrapper:visible')
        var parent = wrapper.parent().parent()
        var shift = -wrapper.position().left
        var maxShift = Math.max(0, wrapper.width())
        var newShift = Math.min(maxShift, shift + parent.width())
        if (newShift < maxShift)
            self.effectBox('shiftTo', newShift)
    },

    shiftTo: function (newShift) {
        var self = $(this)
        var wrapper = self.find('.plugins-wrapper:visible')
        var plugins = wrapper.children()
        var shift = 0
        var step
        for (var i = 0; i < plugins.length; i++) {
            step = $(plugins[i]).outerWidth()
            if (shift + step > newShift)
                return wrapper.animate({
                    left: -shift
                }, 500)
            shift += step
        }
        wrapper.animate({
            left: -newShift
        }, 500)
    }
})



// Compares two version arrays. They are both known to have two non-negative integers.
function compareVersions(a, b) {
    if (!a && !b)
        return 0
    if (!b)
        return 1
    if (!a)
        return -1
    for (var i = 0; i < 3; i++) {
        if (a[i] > b[i])
            return 1
        if (a[i] < b[i])
            return -1
    }
    return 0
}

function version(v) {
    if (!v || !v.length)
        return '0'
    var version = v[0]
    if (v.length < 2)
        return version
    version += '.' + v[1]
    if (v.length < 3)
        return version
    return version + '-' + v[2]
}
