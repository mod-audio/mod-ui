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
        self.data('searchbox', searchbox)
        searchbox.cleanableInput()
        searchbox.keydown(function (e) {
            if (e.keyCode == 13) {
                self.cloudPluginBox('search')
                return false
            }
        })
        var lastKeyUp = null
        searchbox.keyup(function (e) {
            if (e.keyCode == 13)
                return
            if (lastKeyUp != null) {
                clearTimeout(lastKeyUp)
                lastKeyUp = null
            }
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
    checkLocalScreenshot: function(plugin) {
        if (plugin.status == 'installed') {
            if (plugin.gui) {
                plugin.screenshot_href = "/effect/image/screenshot.png?uri=" + escape(plugin.uri)
                plugin.thumbnail_href  = "/effect/image/thumbnail.png?uri=" + escape(plugin.uri)
            } else {
                plugin.screenshot_href = "/resources/pedals/default-screenshot.png"
                plugin.thumbnail_href  = "/resources/pedals/default-thumbnail.png"
            }
        }
        else {
            //if (!plugin.screenshot_available && !plugin.thumbnail_available) {
            if (!plugin.screenshot_href && !plugin.thumbnail_href) {
                plugin.screenshot_href = "/resources/pedals/default-screenshot.png"
                plugin.thumbnail_href  = "/resources/pedals/default-thumbnail.png"
            }
        }
    },

    // search cloud and local plugins, show all but prefer cloud
    searchAll: function (query) {
       /* Get an array of plugins from cloud, organize local plugins in a dictionary indexed by uri.
          Then show all plugins as ordered in cloud, but with aggregated metadata from local plugin.
          All plugins installed but not in cloud (may be installed via sdk) will be unordered at end of list.
        */
        var self = $(this)
        var results = {}
        var cplugin, lplugin;

        renderResults = function () {
            var plugins = []

            for (var i in results.cloud) {
                cplugin = results.cloud[i]
                lplugin = results.local[cplugin.uri]

                cplugin.latestVersion = [cplugin.minorVersion, cplugin.microVersion, cplugin.release || 0]

                if (lplugin) {
                    cplugin.installedVersion = [lplugin.minorVersion, lplugin.microVersion, lplugin.release || 0]
                    delete results.local[cplugin.uri]

                    if (compareVersions(cplugin.installedVersion, cplugin.latestVersion) == 0) {
                        cplugin.status = 'installed'
                    } else {
                        cplugin.status = 'outdated'
                    }

                    self.cloudPluginBox('checkLocalScreenshot', cplugin)

                } else {
                    cplugin.installedVersion = [0, 0, 0]
                    cplugin.status = 'blocked'
                }

                if (!cplugin.screenshot_available && !cplugin.thumbnail_available) {
                    if (!cplugin.screenshot_href && !cplugin.thumbnail_href) {
                        cplugin.screenshot_href = "/resources/pedals/default-screenshot.png"
                        cplugin.thumbnail_href  = "/resources/pedals/default-thumbnail.png"
                    }
                }

                plugins.push(cplugin)
            }

            for (var uri in results.local) {
                lplugin = results.local[uri]
                lplugin.latestVersion = [0, 0, 0]
                lplugin.status = 'installed'
                self.cloudPluginBox('checkLocalScreenshot', lplugin)
                plugins.push(lplugin)
            }

            self.cloudPluginBox('showPlugins', plugins)
        }

        // cloud search
        $.ajax({
            'method': 'GET',
            'url': SITEURLNEW + "/lv2/plugins/",
            'data': {
                'search': query.term
            },
            'success': function (plugins) {
                results.cloud = plugins
                if (results.local != null) {
                    renderResults()
                }
            },
            'dataType': 'json'
        })

        // local search
        if (query.term)
        {
            var allplugins = desktop.pluginIndexerData
            var lplugins   = {}

            var ret = desktop.pluginIndexer.search(query.term)
            for (var i in ret) {
                var uri = ret[i].ref
                if (! allplugins[uri]) {
                    console.log("ERROR: Plugin '" + uri + "' was not previously cached, cannot show it")
                    continue
                }
                lplugins[uri] = allplugins[uri]
            }

            results.local = lplugins
            if (results.cloud != null)
                renderResults()
        }
        else
        {
            $.ajax({
                'method': 'GET',
                'url': '/effect/list',
                'success': function (plugins) {
                    var allplugins = {}
                    for (var i in plugins) {
                        lplugin = plugins[i]
                        lplugin.installedVersion = [lplugin.minorVersion, lplugin.microVersion, lplugin.release || 0]

                        allplugins[lplugin.uri] = lplugin
                        desktop.pluginIndexer.add({
                            id: lplugin.uri,
                            data: [lplugin.uri, lplugin.brand, lplugin.name, lplugin.category.join(" ")].join(" ")
                        })
                    }
                    desktop.pluginIndexerData = allplugins

                    results.local = $.extend({}, allplugins)
                    if (results.cloud != null)
                        renderResults()
                },
                'dataType': 'json'
            })
        }
    },

    // search cloud and local plugins, show installed only
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

        var results = {}
        var cplugin, lplugin

        renderResults = function () {
            var plugins = []

            for (var i in results.local) {
                lplugin = results.local[i]
                cplugin = results.cloud[lplugin.uri]

                if (cplugin) {
                    lplugin.latestVersion = [cplugin.minorVersion, cplugin.microVersion, cplugin.release || 0]

                    if (compareVersions(lplugin.installedVersion, lplugin.latestVersion) == 0) {
                        lplugin.status = 'installed'
                    } else {
                        lplugin.status = 'outdated'
                    }
                } else {
                    lplugin.latestVersion = [0, 0, 0]
                    lplugin.status = 'installed'
                }

                // we're showing installed only, so prefer to show installed modgui screenshot
                if (lplugin.gui) {
                    lplugin.screenshot_href = "/effect/image/screenshot.png?uri=" + escape(lplugin.uri)
                    lplugin.thumbnail_href  = "/effect/image/thumbnail.png?uri=" + escape(lplugin.uri)
                } else {
                    lplugin.screenshot_href = "/resources/pedals/default-screenshot.png"
                    lplugin.thumbnail_href  = "/resources/pedals/default-thumbnail.png"
                }

                plugins.push(lplugin)
            }

            self.cloudPluginBox('showPlugins', plugins)
        }

        // cloud search
        $.ajax({
            'method': 'GET',
            'url': SITEURLNEW + "/lv2/plugins/",
            'data': {
                'search': query.term
            },
            'success': function (plugins) {
                // index by uri, needed later to check its latest version
                var cplugins = {}
                for (var i in plugins)
                    cplugins[plugins[i].uri] = plugins[i]
                results.cloud = cplugins
                if (results.local != null)
                    renderResults()
            },
            'dataType': 'json'
        })

        // local search
        if (term)
        {
            var allplugins = desktop.pluginIndexerData
            var lplugins   = []

            var ret = desktop.pluginIndexer.search(term)
            for (var i in ret) {
                var uri = ret[i].ref
                if (! allplugins[uri]) {
                    console.log("ERROR: Plugin '" + uri + "' was not previously cached, cannot show it")
                    continue
                }
                lplugins.push(allplugins[uri])
            }

            results.local = lplugins
            if (results.cloud != null)
                renderResults()
        }
        else
        {
            $.ajax({
                'method': 'GET',
                'url': '/effect/list',
                'success': function (plugins) {
                    var allplugins = {}
                    for (var i in plugins) {
                        lplugin = plugins[i]
                        lplugin.installedVersion = [lplugin.minorVersion, lplugin.microVersion, lplugin.release || 0]

                        allplugins[lplugin.uri] = lplugin
                        desktop.pluginIndexer.add({
                            id: lplugin.uri,
                            data: [lplugin.uri, lplugin.name, lplugin.brand, lplugin.comment, lplugin.category.join(" ")].join(" "),
                        })
                    }
                    desktop.pluginIndexerData = allplugins

                    results.local = plugins
                    if (results.cloud != null)
                        renderResults()
                },
                'dataType': 'json'
            })
        }
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
        self.data('plugins', plugins)

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

        // render plugins
        var plugin
        for (i in plugins) {
            plugin   = plugins[i]
            category = plugin.category[0]

            self.cloudPluginBox('renderPlugin', plugin, i, self.find('#cloud-plugin-content-All'))

            if (category && category != 'All') {
                self.cloudPluginBox('renderPlugin', plugin, i, self.find('#cloud-plugin-content-' + category))
            }
        }

        // display plugin count
        for (category in categories) {
            var tab = self.find('#cloud-plugin-tab-' + category)
            tab.html(tab.html() + ' <span class="plugin_count">(' + categories[category] + ')</span>')
        }
    },

    renderPlugin: function (plugin, index, canvas) {
        var self = $(this)
        var template = TEMPLATES.cloudplugin
        var uri = escape(plugin.uri)
        if(!plugin.comment) {
            plugin.comment = 'No description available';
            plugin.has_description = 'no_description';
        }
        var plugin_data = {
            id: plugin.id || plugin._id,
            thumbnail_href: plugin.thumbnail_href,
            screenshot_href: plugin.screenshot_href,
            has_description: plugin.has_description,
            description: plugin.comment,
            uri: uri,
            status: plugin.status,
            brand : plugin.brand,
            label : plugin.label
        }

        var rendered = $(Mustache.render(template, plugin_data))
        rendered.click(function () {
            self.cloudPluginBox('showPluginInfo', plugin, index)
        })

        canvas.append(rendered)
        return rendered
    },

    showPluginInfo: function (plugin, index) {
        var self = $(this)
        var uri  = escape(plugin.uri)
        var bundle
        if(plugin.bundles) { // FIXME
            if(plugin.bundles.length > 0) {
                bundle = plugin.bundles[0].replace(/\.lv2$/, '')
            }
            else {
                bundle = plugin.bundles[0]
            }
        }
        else {
            bundle = plugin.brand
        }


        var plugin_data = {
            thumbnail_href: plugin.thumbnail_href,
            screenshot_href: plugin.screenshot_href,
            category: plugin.category[0] || "",
            installed_version: version(plugin.installedVersion),
            latest_version: version(plugin.latestVersion),
            package_name: bundle,
            description: plugin.comment,
            uri: uri,
            status: plugin.status,
            brand : plugin.brand,
            label : plugin.label
        }
        console.log(plugin_data)

        var info = $(Mustache.render(TEMPLATES.cloudplugin_info, plugin_data))

        // The remove button will remove the plugin, close window and re-render the plugins
        // without the removed one
        if (plugin.installedVersion) {
            info.find('.js-install').hide()
            info.find('.js-remove').show().click(function () {
                self.data('removePlugin')(plugin, function (ok) {
                    if (ok) {
                        info.window('close')

                        var plugins = self.data('plugins')
                        delete plugins[index].installedVersion
                        plugins[index].status = 'blocked'

                        self.cloudPluginBox('showPlugins', plugins)
                        desktop.rescanPlugins()
                    }
                })
            })
        } else {
            info.find('.js-remove').hide()
            info.find('.js-installed-version').hide()
            info.find('.js-install').show().click(function () {
                // Install plugin
                self.data('installPlugin')(plugin, function (plugin) {
                    if (plugin) {
                        plugin.status = 'installed'
                        plugin.latestVersion = [plugin.minorVersion, plugin.microVersion, plugin.release || 0]
                        plugin.installedVersion = plugin.latestVersion
                        if (info.is(':visible')) {
                            info.remove()
                            self.cloudPluginBox('showPluginInfo', plugin, index)
                        }
                        desktop.rescanPlugins()
                    }
                })
            })
        }

        var checkVersion = function () {
            if (plugin.installedVersion && compareVersions(plugin.latestVersion, plugin.installedVersion) > 0) {
                info.find('.js-upgrade').show().click(function () {
                    // Do the upgrade
                    self.data('upgradePlugin')(plugin, function (plugin) {
                        if (plugin) {
                            var plugins = self.data('plugins')
                            plugin.latestVersion = [plugin.minorVersion, plugin.microVersion, plugin.release || 0]
                            plugin.installedVersion = plugin.latestVersion
                            plugins[index] = plugin
                            if (info.is(':visible')) {
                                info.remove()
                                self.effectBox('showPluginInfo', plugin, index)
                            }
                            desktop.rescanPlugins()
                        }
                    })
                })
            } else {
                info.find('.js-upgrade').hide()
            }
        }

        if (plugin.latestVersion) {
            checkVersion()
        } else {
            // wait for cloud info
            info.find('.js-upgrade').hide()

            $.ajax({
                url: SITEURLNEW + "/lv2/plugins",
                data: {
                    uri: plugin.uri
                },
                success: function (pluginData) {
                    plugin.latestVersion = [pluginData.minorVersion, pluginData.microVersion, pluginData.release || 0]
                    info.find('.js-latest-version span').html(version(plugin.latestVersion))
                    checkVersion()
                },
                dataType: 'json'
            })
        }

        /*info.window({
            windowManager: self.data('windowManager'),
            close: function () {
                info.remove()
                self.data('info', null)
            }
        }) keep plugin info open in plugin store*/
        info.appendTo($('body'))
        info.window('open')
        self.data('info', info)
    },

})
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
