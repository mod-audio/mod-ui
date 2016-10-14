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
        }, options)

        self.data(options)
        self.data('showPluginsRenderId', 0)

        var searchbox = self.find('input[type=search]')

        // make sure searchbox is empty on init
        searchbox.val("")

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

        // CATEGORY WRAPPERS
        self.find(".plugins-wrapper").each(function () {
            $(this).data("pos", 0);
            $(this).data("plug", 0);
        })

        // CATEGORY SCROLL
        self.on('DOMMouseScroll mousewheel', function ( event ) {
            if( event.originalEvent.detail > 0 || event.originalEvent.wheelDelta < 0 )
                self.effectBox('shiftNext');
            else
                self.effectBox('shiftPrev');
            self.effectBox('scrolling');
            return false;
        });
        self.data("scrollTO", false);

        //self.effectBox('fold')
        self.effectBox('setCategory', 'Favorites')

        // don't search just yet.
        // it's a little expensive, let init time go for loading the pedalboard first
        self.effectBox('showPlugins', [])

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
        self.find('.plugins-wrapper').removeClass("selected");
        self.find('#effect-tab-' + category).addClass('selected')
        self.find('#effect-content-' + category).addClass("selected");
        self.data('category', category)
        self.effectBox('unfold')
        self.effectBox('calculateNavigation')
    },

    search: function (callback) {
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
                    var i, plugin, allplugins = {}
                    for (i in plugins) {
                        plugin = plugins[i]
                        plugin.installedVersion = [plugin.builder, plugin.minorVersion, plugin.microVersion, plugin.release]
                        allplugins[plugin.uri] = plugin
                    }
                    desktop.resetPluginIndexer(allplugins)
                    self.effectBox('showPlugins', plugins, callback)
                },
                cache: false,
                dataType: 'json'
            });
        }
    },

    showPlugins: function (plugins, callback) {
        var self = $(this)
        self.effectBox('cleanResults')
        plugins.sort(function (a, b) {
            a = a.label.toLowerCase()
            b = b.label.toLowerCase()
            if (a > b) {
                return 1
            }
            if (a < b) {
                return -1
            }
            return 0
        })

        // count plugins first
        var pluginCount = plugins.length
        var categories = {
            'Favorites': FAVORITES.length,
            'All': 0,
            'Delay': 0,
            'Distortion': 0,
            'Dynamics': 0,
            'Filter': 0,
            'Generator': 0,
            'Modulator': 0,
            'Reverb': 0,
            'Simulator': 0,
            'Spatial': 0,
            'Spectral': 0,
            'Utility': 0,
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
        function renderNextPlugin(c) {
            if (self.data('showPluginsRenderId') != currentRenderId) {
                // another render is in place, stop this one
                if (callback) { callback() }
                return
            }

            if (renderedIndex >= pluginCount) {
                // if we get here it means we finished rendering
                self.effectBox('calculateNavigation')

                if (self.data('showPluginsRenderId') == currentRenderId) {
                    // no other renders in queue, take the chance and reset the id
                    self.data('showPluginsRenderId', 0)
                }
                if (callback) { callback() }
                return
            }

            plugin   = plugins[renderedIndex]
            category = plugin.category[0]

            self.effectBox('renderPlugin', plugin, self.find('#effect-content-All'))

            if (FAVORITES.indexOf(plugin.uri) >= 0) {
                self.effectBox('renderPlugin', plugin, self.find('#effect-content-Favorites'))
            }

            if (category && category != 'All') {
                self.effectBox('renderPlugin', plugin, self.find('#effect-content-' + category))
            }

            renderedIndex += 1

            c = c || 0;
            if (c < 20) renderNextPlugin(c+1);
            else setTimeout(renderNextPlugin, 1);
        }

        renderNextPlugin(0)
    },

    renderPlugin: function (plugin, container) {
        var self = $(this)
        if (container.length == 0)
            return
        var uri = escape(plugin.uri)
        var ver = [plugin.builder, plugin.microVersion, plugin.minorVersion, plugin.release].join('_')

        var plugin_data = {
            uri   : uri,
            brand : plugin.brand,
            label : plugin.label,
            thumbnail_href: (plugin.gui && plugin.gui.thumbnail)
                          ? ("/effect/image/thumbnail.png?uri=" + uri + "&v=" + ver)
                          :  "/resources/pedals/default-thumbnail.png",
            demo: plugin.demo
        }

        var div = document.createElement("div");
        div.innerHTML = Mustache.render(TEMPLATES.plugin, plugin_data);
        var rendered = $(Array.prototype.slice.call(div.childNodes, 0));

        self.data('pedalboard').pedalboard('registerAvailablePlugin', rendered, plugin, {
            distance: 2,
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

            // formating numbers and flooring ranges up to two decimal cases
            for (var i = 0; i < plugin.ports.control.input.length; i++) {
                plugin.ports.control.input[i].formatted = {
                    "default": formatNum(Math.floor(plugin.ports.control.input[i].ranges.default * 100) / 100),
                    "maximum": formatNum(Math.floor(plugin.ports.control.input[i].ranges.maximum * 100) / 100),
                    "minimum": formatNum(Math.floor(plugin.ports.control.input[i].ranges.minimum * 100) / 100)
                }
            }

            var ver = [plugin.builder, plugin.microVersion, plugin.minorVersion, plugin.release].join('_')

            var metadata = {
                author: plugin.author,
                uri: plugin.uri,
                thumbnail_href: (plugin.gui && plugin.gui.thumbnail)
                              ? "/effect/image/thumbnail.png?uri=" + uri + "&v=" + ver
                              : "/resources/pedals/default-thumbnail.png",
                screenshot_href: (plugin.gui && plugin.gui.screenshot)
                              ? "/effect/image/screenshot.png?uri=" + uri + "&v=" + ver
                              : "/resources/pedals/default-screenshot.png",
                category: plugin.category[0] || "None",
                installed_version: version(plugin.installedVersion),
                latest_version: "DO NOT SHOW THIS!!", // not shown on local plugin bar
                package_name: plugin.bundles[0].replace(/\.lv2$/, ''),
                comment: plugin.comment.trim() || "No description available",
                brand : plugin.brand,
                name  : plugin.name,
                label : plugin.label,
                ports : plugin.ports,
                demo  : !!plugin.demo,
                installed: true,
                favorite_class: FAVORITES.indexOf(plugin.uri) >= 0 ? "favorite" : "",
                pedalboard_href: desktop.getPedalboardHref(plugin.uri),
            };

            var info = $(Mustache.render(TEMPLATES.cloudplugin_info, metadata))

            // hide install etc buttons
            info.find('.js-remove').hide()
            info.find('.js-install').hide()
            info.find('.js-upgrade').hide()
            info.find('.js-latest-version').hide()

            // hide control ports table if none available
            if (plugin.ports.control.input.length == 0) {
                info.find('.plugin-controlports').hide()
            }

            info.find('.favorite-button').on('click', function () {
                var isFavorite = $(this).hasClass('favorite'),
                    widget = $(this)

                $.ajax({
                    url: '/favorites/' + (isFavorite ? 'remove' : 'add'),
                    type: 'POST',
                    data: {
                        uri: plugin.uri,
                    },
                    success: function (ok) {
                        if (! ok) {
                            console.log("favorite action failed")
                            return
                        }

                        if (isFavorite) {
                            // was favorite, not anymore
                            widget.removeClass('favorite');
                            remove_from_array(FAVORITES, plugin.uri)
                            self.find('#effect-content-Favorites').find('[mod-uri="'+escape(plugin.uri)+'"]').remove()

                        } else {
                            // was not favorite, now is
                            widget.addClass('favorite');
                            FAVORITES.push(plugin.uri)
                            self.effectBox('renderPlugin', plugin, self.find('#effect-content-Favorites'))
                        }

                        self.find('#effect-tab-Favorites').html('Favorites (' + FAVORITES.length + ')')
                    },
                    cache: false,
                    dataType: 'json'
                })
            });

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
                    // FIXME: needed?
                    desktop.pluginIndexerData[plugin.uri] = plugin
                    showInfo()
                },
                cache: false,
                dataType: 'json'
            })
        }
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
        var wrapper = self.find('.plugins-wrapper.selected')
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
        $(this).effectBox('shiftDir', -1);
    },

    shiftRight: function () {
        $(this).effectBox('shiftDir', 1);
    },


    // This whole scrolling and shifting thing is very expensive due
    // to lots of relayouts and redraws. This is because we want to
    // snap to plugins on the left border of the container. We should
    // switch to a less greedy concept. Maybe next century.

    shiftDir: function (dir) {
        var self = $(this);
        var wrapper = self.find('.plugins-wrapper.selected');
        var parent = wrapper.parent().parent();
        var plugins = wrapper.children();
        var pos = wrapper.data("pos");
        var pw = parent.width();
        var ww = wrapper.width();
        var pos = Math.min(0,
                  Math.max(-(ww - pw), pos - pw * dir + 64));
        var shift = 0;
        if (pos != -(ww - pw)) {
            for (var i = 0; i < plugins.length; i++) {
                var plugw = $(plugins[i]).outerWidth();
                if (shift + plugw >= -pos) {
                    pos = -shift;
                    wrapper.data("plug", i);
                    break;
                }
                shift += plugw;
            }
        }
        wrapper.data("pos", pos);
        wrapper[0].style.left = pos + "px";
    },

    shiftPrev: function () {
        $(this).effectBox('shiftAlter', -1);
    },

    shiftNext: function () {
        $(this).effectBox('shiftAlter', 1);
    },

    shiftAlter: function (dir) {
        var self = $(this);
        var wrapper = self.find('.plugins-wrapper.selected');
        var parent = wrapper.parent().parent();
        var children = wrapper.children();
        var plug = wrapper.data("plug");
        var pw = parent.width();
        var ww = wrapper.width();
        if (ww < pw) return;
        plug = Math.min(children.length-1, Math.max(0, plug + dir));
        var pos = Math.max(-(ww - pw),
                           -$(children[plug]).position().left);
        while (-$(children[plug]).position().left < pos)
            plug--;
        wrapper[0].style.left = pos + "px";
        wrapper.data("pos", pos);
        wrapper.data("plug", plug);
    },
    scrolling: function () {
        var self = $(this);
        var scrollTO = self.data("scrollTO");
        if (scrollTO) {
            clearTimeout(scrollTO);
        } else {
            self.addClass("scrolling");
        }
        self.data("scrollTO", setTimeout(function () {
            self.data("scrollTO", false);
            self.removeClass("scrolling");
        }, 200));
    }
})

function version(v) {
    if (!v || !v.length)
        return '0:0.0-0'
    return ""+v[0]+":"+v[1]+"."+v[2]+"-"+v[3]
}
