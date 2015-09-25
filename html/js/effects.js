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
            removePlugin: function (plugin, callback) {
                callback(true)
            },
            installPlugin: function (plugin, callback) {
                callback(plugin)
            },
            upgradePlugin: function (plugin, callback) {
                callback(plugin)
            }
        }, options)

        self.data(options)

        var mode = getCookie('searchMode', 'installed')
        self.find('input[name=mode][value=' + mode + ']').prop('checked', true)

        self.find('input[type=radio]').change(function () {
            self.effectBox('search')
        })

        var settingsBox = self.find('#plugins-library-settings-window')
        var searchbox = self.find('input[type=search]')

        searchbox.cleanableInput()
        self.data('searchbox', searchbox)

        //var categoryBrowse = self.find('div.categories')

        var results = {}

        settingsBox.window({
            windowManager: options.windowManager,
            trigger: self.find('.js-settings-trigger')
        })

            //self.data('categoryBrowse', categoryBrowse)

        /*
	self.data('mode', 'installed')
	self.find('#js-mode-installed').addClass('current')
	self.find('.js-mode').click(function() {
	    var mode = $(this).attr('id').replace(/^.+-/, '')
	    self.effectBox('mode', mode)
	    return false
	})
	*/

        searchbox.keydown(function (e) {
            if (e.keyCode == 13) {
                self.effectBox('search')
                return false
            }
        })
        var lastKeyUp;
        searchbox.keyup(function (e) {
            if (e.keyCode == 13)
                return
            clearTimeout(lastKeyUp)
            if (e.keyCode == 13)
                return
            lastKeyUp = setTimeout(function () {
                self.effectBox('search')
            }, 400);
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
            allplugins = self.data('allplugins')
            plugins    = []

            ret = desktop.pluginIndexer.search(term)
            for (var i in ret) {
                var uri = ret[i].ref
                plugins.push(allplugins[uri])
            }

            self.effectBox('showPlugins', plugins)
        }
        else
        {
            $.ajax({
                'method': 'GET',
                'url': '/effect/list',
                'success': function (plugins) {
                    var allplugins = {}
                    for (var i=0; i<plugins.length; i++) {
                        var plugin = plugins[i]
                        plugin.installedVersion = [plugin.minorVersion, plugin.microVersion, plugin.release || 0]
                        plugin.status = 'installed'

                        allplugins[plugin.uri] = plugin
                        desktop.pluginIndexer.add({
                            id: plugin.uri,
                            data: [plugin.uri, plugin.brand, plugin.name, plugin.author.name, plugin.category.join(" ")].join(" ")
                        })
                    }
                    self.data('allplugins', allplugins)
                    self.effectBox('showPlugins', plugins)
                },
                'dataType': 'json'
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
        self.data('plugins', plugins)

        var currentCategory = self.data('category')
        var pluginCount     = plugins.length
        var showingAll      = currentCategory == 'All'

        // count plugins first
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

        // render plugins
        function renderNextPlugin() {
            if (self.renderedIndex >= pluginCount) {
                self.effectBox('calculateNavigation')
                return
            }

            category = plugins[self.renderedIndex].category[0]

            self.effectBox('renderPlugin', self.renderedIndex, self.find('#effect-content-All'))

            if (category && category != 'All') {
                self.effectBox('renderPlugin', self.renderedIndex, self.find('#effect-content-' + category))
            }

            self.renderedIndex += 1
            setTimeout(renderNextPlugin, 1);
        }

        self.renderedIndex = 0
        renderNextPlugin(0)
    },

    renderPlugin: function (index, container) {
        var self = $(this)
        if (container.length == 0)
            return
        var plugin = self.data('plugins')[index]
        var uri = escape(plugin.uri)

        var plugin_data = {
            uri   : uri,
            status: plugin.status,
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
            self.effectBox('showPluginInfo', index)
        })

        container.append(rendered)

        // this 200px extra is a good margin to make sure the container's parent will
        // always be big enough. it's impossible at this moment to know the necessary width,
        // as this will be given by images not yet loaded.
        container.parent().width(container.parent().width() + rendered.width() + 200)
    },

    showPluginInfo: function (index) {
        var self = $(this)
        var plugins = self.data('plugins')
        var plugin = plugins[index]

        plugin.title = plugin.name.split(/\s*-\s*/)[0]
        plugin.subtitle = plugin.name.split(/\s*-\s*/)[1]
        plugin.installed_version = version(plugin.installedVersion)
        plugin.latest_version = version(plugin.latestVersion)
        plugin.package_name = "TODO" //plugin.package.replace(/\.lv2$/, '')
        plugin.description = (plugin.description || '').replace(/\n/g, '<br\>\n')

        var info = $(Mustache.render(TEMPLATES.plugin_info, plugin))

        if (plugin.rating)
            $(info.find('.rating')[0]).addClass(['', 'one', 'two', 'three', 'four', 'five'][Math.round(plugin.rating)])

        // The remove button will remove the plugin, close window and re-render the plugins
        // without the removed one
        if (plugin.installedVersion) {
            info.find('.js-remove').click(function () {
                self.data('removePlugin')(plugin, function (ok) {
                    if (ok) {
                        info.window('close')
                        delete plugins[index].installedVersion
                        plugins[index].status = 'blocked'
                        self.effectBox('showPlugins', plugins)
                    }
                })
            }).show()
        } else {
            info.find('.js-installed-version').hide()
            info.find('.js-install').show().click(function () {
                // Install plugin
                self.data('installPlugin')(plugin, function (plugin) {
                    if (plugin) {
                        plugins[index].installedVersion = plugins[index].latestVersion
                        if (info.is(':visible')) {
                            info.remove()
                            self.effectBox('showPluginInfo', index)
                        }
                    }
                })
            })
        }

        var checkVersion = function () {
            if (plugin.installedVersion && compareVersions(plugin.latestVersion, plugin.installedVersion) > 0) {
                info.find('.js-upgrade').click(function () {
                    // Do the upgrade
                    self.data('upgradePlugin')(plugin, function (plugin) {
                        if (plugin) {
                            plugin.installedVersion = plugins[index].latestVersion
                            plugin.latestVersion = plugins[index].latestVersion
                            plugins[index] = plugin
                            if (info.is(':visible')) {
                                info.remove()
                                self.effectBox('showPluginInfo', index)
                            }
                        }
                    })
                }).show()
            }

            if (compareVersions(plugin.latestVersion, plugin.installedVersion) == 0)
                self.effectBox('getRating', plugin, info.find('.js-rate'))

            self.effectBox('getReviews', plugin.uri, info, function () {

                var title = info.find('input[name=title]')
                var comment = info.find('textarea[name=comment]')

                if (compareVersions(plugin.latestVersion, plugin.installedVersion) == 0) {
                    info.find('.js-comment').click(function () {
                        var userSession = self.data('userSession')
                        userSession.login(function () {
                            $.ajax({
                                url: SITEURL + '/effect/comment/' + userSession.sid,
                                method: 'POST',
                                data: JSON.stringify({
                                    'title': title.val(),
                                    'comment': comment.val(),
                                    'uri': plugin.uri,
                                    'version': version(plugin.latestVersion)
                                }),
                                success: function (res) {
                                    if (res.ok) {
                                        title.val('')
                                        comment.val('')
                                        self.effectBox('getReviews', plugin.uri, info)
                                    } else {
                                        alert(res.error)
                                    }
                                },
                                error: function () {
                                    new Notification('error', "Couldn't post comment")
                                },
                                dataType: 'json'
                            })
                        })
                        return false
                    })
                } else {
                    title.attr('placeholder', 'Please install and test latest version before commenting')
                    title.attr('disabled', true)
                    comment.attr('disabled', true)
                    info.find('.js-comment').attr('disabled', true)
                }
            })
        }

        if (plugin.latestVersion)
            checkVersion()
        else {
            $.ajax({
                url: SITEURL + '/effect/get/',
                data: {
                    uri: plugin.uri
                },
                success: function (pluginData) {
                    plugin.latestVersion = [pluginData.minorVersion,
                        pluginData.microVersion,
                        pluginData.release
                    ]
                    info.find('.js-latest-version span').html(version(plugin.latestVersion))
                    checkVersion()
                },
                dataType: 'json'
            })
        }

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
    },

    getReviews: function (uri, info, callback) {
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

JqueryClass('cloudPluginBox', {
    init: function (options) {
        var self = $(this)

        options = $.extend({
            resultCanvas: self.find('.js-cloud-plugins'),
            removePlugin: function (plugin, callback) {
                callback(true)
            },
            installPlugin: function (plugin, callback) {
                callback(plugin)
            },
            upgradePlugin: function (plugin, callback) {
                callback(plugin)
            }
        }, options)

        self.data(options)
        var searchbox = self.find('input[type=search]')

        searchbox.cleanableInput()
        self.data('searchbox', searchbox)

        searchbox.keydown(function (e) {
            if (e.keyCode == 13) {
                self.cloudPluginBox('search')
                return false
            }
        })
        var lastKeyUp;
        searchbox.keyup(function (e) {
            if (e.keyCode == 13)
                return
            clearTimeout(lastKeyUp)
            if (e.keyCode == 13)
                return
            lastKeyUp = setTimeout(function () {
                self.cloudPluginBox('search')
            }, 400);
        })

        var filters = self.find('input:radio[name=installed]')
        self.data('filters', filters)

        filters.click(function (e) {
            self.cloudPluginBox('search')
        })

        var results = {}
        self.data('results', results)

        self.data('category', null)
        self.find('ul.categories li').click(function () {
            var category = $(this).attr('id').replace(/^cloud-plugin-tab-/, '')
            self.cloudPluginBox('setCategory', category)
        })

        self.cloudPluginBox('search')
        self.cloudPluginBox('setCategory', "All")
        self.window(options)
    },

    setCategory: function (category) {
        var self = $(this)
        self.find('ul.categories li').removeClass('selected')
        self.find('.plugins-wrapper').hide()
        self.find('#cloud-plugin-tab-' + category).addClass('selected')
        self.find('#cloud-plugin-content-' + category).show().css('display', 'inline-block')
        self.data('category', category)
    },
    cleanResults: function () {
        var self = $(this)
        self.find('.plugins-wrapper').html('')
        self.find('ul.categories li').each(function () {
            $(this).html($(this).html().split(/\s/)[0])
        });
    },
    searchAll: function (query) {
        // TODO: implement new cloud API
        return
        /* Get an array of plugins from cloud, organize local plugins in a dictionary indexed by uri.
	   Then show all plugins as ordered in cloud, but with aggregated metadata from local plugin.
	   All plugins installed but not in cloud (may be installed via sdk) will be unordered at end of list.
	 */
        var self = $(this)
        var results = {}
        var plugins = []
        var plugin, i;

        renderResults = function () {
            for (i in results.cloud) {
                plugin = results.cloud[i]
                plugin.latestVersion = [plugin.minorVersion, plugin.microVersion, plugin.release]
                if (results.local[plugin.uri]) {
                    if (plugin.gui && plugin.gui.screenshot) {
                        plugin.screenshot_href =  "/effect/image/screenshot.png?uri=" + uri
                        plugin.thumbnail_href  = "/effect/image/thumbnail.png?uri=" + uri
                    } else {
                        plugin.screenshot_href = "/resources/pedals/default-screenshot.png"
                        plugin.thumbnail_href  = "/resources/pedals/default-thumbnail.png"
                    }
                    plugin.installedVersion = [results.local[plugin.uri].minorVersion,
                        results.local[plugin.uri].microVersion,
                        results.local[plugin.uri].release || 0
                    ]
                    delete results.local[plugin.uri]
                }
                if (plugin.installedVersion == null) {
                    plugin.status = 'blocked'
                } else if (compareVersions(plugin.installedVersion, plugin.latestVersion) == 0) {
                    plugin.status = 'installed'
                } else {
                    plugin.status = 'outdated'
                }
                plugins.push(plugin)
            }
            for (uri in results.local) {
                plugin = results.local[uri]
                plugin.installedVersion = [
                    plugin.minorVersion,
                    plugin.microVersion,
                    plugin.release || 0
                ]
                plugin.status = 'installed'
                plugins.push(plugin)
            }
            self.cloudPluginBox('showPlugins', plugins)
        }

        var url = query.term ? '/effect/search/' : '/effect/list/'

        $.ajax({
            'method': 'GET',
            'url': url,
            'data': query,
            'success': function (plugins) {
                results.local = {}
                for (i in plugins)
                    results.local[plugins[i].uri] = plugins[i]
                if (results.cloud != null)
                    renderResults()
            },
            'dataType': 'json'
        })

        $.ajax({
            'method': 'GET',
            'url': SITEURLNEW + "/lv2/plugins",
            'data': {'search': query.term},
            'success': function (plugins) {
                results.cloud = plugins
                if (results.local != null)
                    renderResults()
            },
            'dataType': 'json'
        })
    },

    searchNotInstalled: function (query) {
        /* Get an array of plugins from cloud and a dict of installed plugins by uri.
	   Show only those plugins not installed
	 */
        var self = $(this)
        var results = {}
        var plugin, i;

        renderResults = function () {
            var plugins = []
            for (i in results.cloud) {
                plugin = results.cloud[i]
                plugin.latestVersion = [plugin.minorVersion, plugin.microVersion, plugin.release]
                plugin.status = 'blocked'
                plugin.source = SITEURL.replace(/api\/?$/, '')
                if (!results.local[plugin.uri]) {
                    plugins.push(plugin)
                }
            }
            self.cloudPluginBox('showPlugins', plugins)
        }

        var url = query.term ? '/effect/search/' : '/effect/list/'

        $.ajax({
            'method': 'GET',
            'url': url,
            'data': query,
            'success': function (plugins) {
                results.local = {}
                for (i in plugins)
                    results.local[plugins[i].uri] = plugins[i]
                if (results.cloud != null)
                    renderResults()
            },
            'dataType': 'json'
        })

        $.ajax({
            'method': 'GET',
            'url': SITEURLNEW + "/lv2/plugins",
            'data': {'search': query.term},
            'success': function (plugins) {
                results.cloud = plugins
                if (results.local != null)
                    renderResults()
            },
            'dataType': 'json'
        })
    },

    search: function () {
        var self = $(this)
        var searchbox = self.data('searchbox')
        var checked_filter = self.find('input:radio[name=installed]:checked').val()
        var term = searchbox.val()
        var query = {
            'term': term
        }

        if (checked_filter == "all")
            return self.cloudPluginBox('searchAll', query)
        else if (checked_filter == "not-installed")
            return self.cloudPluginBox('searchNotInstalled', query)

        var url = query.term ? '/effect/search/' : '/effect/list/'
        $.ajax({
            'method': 'GET',
            'url': url,
            'data': query,
            'success': function (plugins) {
                for (var i = 0; i < plugins.length; i++) {
                    plugins[i].installedVersion = [plugins[i].minorVersion,
                        plugins[i].microVersion,
                        plugins[i].release || 0
                    ]
                    plugins[i].status = 'installed'
                }
                self.cloudPluginBox('showPlugins', plugins)
            },
            'dataType': 'json'
        })
    },

    showPlugins: function (plugins) {
        var self = $(this)
        self.cloudPluginBox('cleanResults')
        plugins.sort(function (a, b) {
            if (a.label > b.label)
                return 1
            if (a.label < b.label)
                return -1
            return 0
        })
        var count = {
            'All': 0
        }
        var category

        for (var i in plugins) {
            self.cloudPluginBox('showPlugin', plugins[i])
            category = plugins[i].category[0]
            if (count[category] == null)
                count[category] = 1
            else
                count[category] += 1
            count.All += 1
        }
       self.data('plugins', plugins)

        var currentCategory = self.data('category')
        var empty = true
        for (category in count) {
            var tab = self.find('#cloud-plugin-tab-' + category)
            tab.html(tab.html() + ' (' + count[category] + ')')
            if (category == currentCategory && count[category] > 0)
                empty = false;
        }
    },

    showPlugin: function (plugin) {
        var self = $(this)
        var results = self.data('results')
        var canvas = self.data('resultCanvas')
        self.cloudPluginBox('render', plugin, self.find('#cloud-plugin-content-All'))
        self.cloudPluginBox('render', plugin, self.find('#cloud-plugin-content-' + plugin.category[0]))
    },

    showPluginInfo: function (plugin) {
        var self = $(this)
        var uri = escape(plugin.uri)

        var plugin_data = {
            thumbnail_href: plugin.thumbnail_href,
            screenshot_href: plugin.screenshot_href,
            category: plugin.category[0] || "",
            installed_version: version(plugin.installedVersion),
            latest_version: version(plugin.latestVersion),
            package_name: "TODO",//plugin.package.replace(/\.lv2$/, ''),
            uri: uri,
            status: plugin.status,
            brand : plugin.brand,
            label : plugin.label
        }

        var info = $(Mustache.render(TEMPLATES.cloudplugin_info, plugin_data))

        // The remove button will remove the plugin, close window and re-render the plugins
        // without the removed one
        if (plugin.installedVersion) {
            info.find('.js-remove').click(function () {
                self.data('removePlugin')(plugin, function (ok) {
                    if (ok) {
                        info.window('close')
                        delete plugins[index].installedVersion
                        plugins[index].status = 'blocked'
                        self.cloudPluginBox('showPlugins', plugins)
                    }
                })
            }).show()
        } else {
            info.find('.js-installed-version').hide()
            info.find('.js-install').show().click(function () {
                // Install plugin
                self.data('installPlugin')(plugin, function (plugin) {
                    if (plugin) {
                        plugin.installedVersion = plugin.latestVersion
                        if (info.is(':visible')) {
                            info.remove()
                            self.cloudPluginBox('showPluginInfo', plugin)
                        }
                    }
                })
            })
        }

        var checkVersion = function () {
            if (plugin.installedVersion && compareVersions(plugin.latestVersion, plugin.installedVersion) > 0) {
                info.find('.js-upgrade').click(function () {
                    // Do the upgrade
                    self.data('upgradePlugin')(plugin, function (plugin) {
                        if (plugin) {
                            plugin.installedVersion = plugins[index].latestVersion
                            plugin.latestVersion = plugins[index].latestVersion
                            plugins[index] = plugin
                            if (info.is(':visible')) {
                                info.remove()
                                self.effectBox('showPluginInfo', plugin)
                            }
                        }
                    })
                }).show()
            }
        }

        if (plugin.latestVersion)
            checkVersion()
        else {
            $.ajax({
                url: SITEURLNEW + "/lv2/plugins",
                data: {
                    uri: plugin.uri
                },
                success: function (pluginData) {
                    plugin.latestVersion = [pluginData.minorVersion,
                        pluginData.microVersion,
                        pluginData.release
                    ]
                    info.find('.js-latest-version span').html(version(plugin.latestVersion))
                    checkVersion()
                },
                dataType: 'json'
            })
        }

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
    },

    render: function (plugin, canvas) {
        var self = $(this)
        var template = TEMPLATES.cloudplugin
        var uri = escape(plugin.uri)
        var plugin_data = {
            id: plugin.id || plugin._id,
            thumbnail_href: plugin.thumbnail_href,
            uri: uri,
            status: plugin.status,
            brand : plugin.brand,
            label : plugin.label
        }

        var rendered = $(Mustache.render(template, plugin_data))
        rendered.click(function () {
            self.cloudPluginBox('showPluginInfo', plugin)
        })


        /*
        var load = function () {
            self.data('load')(pedalboard._id, function () {
                self.window('close')
            })
            return false
        }
        rendered.find('.js-load').click(load)
        rendered.find('img').click(load)
        rendered.find('.js-duplicate').click(function () {
            self.data('duplicate')(pedalboard, function (duplicated) {
                var dupRendered = self.pedalboardBox('render', duplicated, canvas)
                dupRendered.insertAfter(rendered)
                dupRendered.css('opacity', 0)
                dupRendered.animate({
                    opacity: 1
                }, 200)
            })
            return false
        })
        */
        canvas.append(rendered)
        return rendered
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
