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
            if (e.keyCode == 13) { //detect enter
                self.cloudPluginBox('search')
                return false
            }
            else if (e.keyCode == 8 || e.keyCode == 46) { //detect delete and backspace
                setTimeout(function () {
                    self.cloudPluginBox('search')
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
                self.cloudPluginBox('search')
            }, 400);
        })

        var filters = self.find('input:checkbox[name=installed]')
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

    // search all or installed, depending on selected option
    search: function () {
        var self  = $(this)
        var query = {
            term: self.data('searchbox').val()
        }
        if (self.find('input:checkbox[name=installed]:checked').length)
            return self.cloudPluginBox('searchInstalled', query)
        return self.cloudPluginBox('searchAll', query)
    },

    // search cloud and local plugins, show all but prefer cloud
    searchAll: function (query) {
        var self = $(this)
        var results = {}
        var cplugin, lplugin;

        renderResults = function () {
            var plugins = []

            for (var i in results.cloud) {
                cplugin = results.cloud[i]
                lplugin = results.local[cplugin.uri]

                cplugin.latestVersion = [cplugin.minorVersion, cplugin.microVersion, cplugin.release_number]

                if (lplugin) {
                    if (!lplugin.installedVersion) {
                        console.log("local plugin is missing version info:", lplugin.uri)
                        lplugin.installedVersion = [0, 0, 0]
                    }

                    cplugin.installedVersion = lplugin.installedVersion
                    delete results.local[cplugin.uri]

                    if (compareVersions(cplugin.installedVersion, cplugin.latestVersion) == 0) {
                        cplugin.status = 'installed'
                    } else {
                        cplugin.status = 'outdated'
                    }

                    self.cloudPluginBox('checkLocalScreenshot', cplugin)

                } else {
                    cplugin.installedVersion = null // if set to [0, 0, 0], it appears as intalled on cloudplugininfo
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
                lplugin.status = 'installed'
                lplugin.latestVersion = null
                self.cloudPluginBox('checkLocalScreenshot', lplugin)
                plugins.push(lplugin)
            }

            self.cloudPluginBox('showPlugins', plugins)
        }

        // cloud search
        $.ajax({
            method: 'GET',
            url: SITEURLNEW + "/lv2/plugins/",
            data: {
                search: query.term
            },
            success: function (plugins) {
                var cplugins = []
                for (var i in plugins) {
                    if (plugins[i].stable)
                        cplugins.push(plugins[i])
                }
                results.cloud = cplugins
                if (results.local != null) {
                    renderResults()
                }
            },
            error: function () {
                results.cloud = []
                if (results.local != null) {
                    renderResults()
                }
            },
            dataType: 'json',
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
                method: 'GET',
                url: '/effect/list',
                success: function (plugins) {
                    var allplugins = {}
                    for (var i in plugins) {
                        lplugin = plugins[i]
                        lplugin.installedVersion = [lplugin.minorVersion, lplugin.microVersion, lplugin.release]

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
                dataType: 'json',
            })
        }
    },

    // search cloud and local plugins, show installed only
    searchInstalled: function (query) {
        var self = $(this)
        var results = {}
        var cplugin, lplugin

        renderResults = function () {
            var plugins = []

            for (var i in results.local) {
                lplugin = results.local[i]
                cplugin = results.cloud[lplugin.uri]

                if (cplugin) {
                    lplugin.latestVersion = [cplugin.minorVersion, cplugin.microVersion, cplugin.release_number]

                    if (compareVersions(lplugin.installedVersion, lplugin.latestVersion) == 0) {
                        lplugin.status = 'installed'
                    } else {
                        lplugin.status = 'outdated'
                    }
                } else {
                    lplugin.latestVersion = null
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
            method: 'GET',
            url: SITEURLNEW + "/lv2/plugins/",
            data: {
                search: query.term
            },
            success: function (plugins) {
                // index by uri, needed later to check its latest version
                var cplugins = {}
                for (var i in plugins) {
                    if (plugins[i].stable)
                        cplugins[plugins[i].uri] = plugins[i]
                }
                results.cloud = cplugins
                if (results.local != null)
                    renderResults()
            },
            error: function () {
                results.cloud = {}
                if (results.local != null)
                    renderResults()
            },
            dataType: 'json',
        })

        // local search
        if (query.term)
        {
            var allplugins = desktop.pluginIndexerData
            var lplugins   = []

            var ret = desktop.pluginIndexer.search(query.term)
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
                method: 'GET',
                url: '/effect/list',
                success: function (plugins) {
                    var allplugins = {}
                    for (var i in plugins) {
                        lplugin = plugins[i]
                        lplugin.installedVersion = [lplugin.minorVersion, lplugin.microVersion, lplugin.release]

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
                dataType: 'json',
            })
        }
    },

    showPlugins: function (plugins) {
        var self = $(this)
        self.cloudPluginBox('cleanResults')
        // FIXME: this sort stuff doesn't seem to work properly
        // sort by label
        plugins.sort(function (a, b) {
            if (a.label > b.label)
                return 1
            if (a.label < b.label)
                return -1
            return 0
        })
        // now sort by status
        plugins.sort(function (a, b) {
            if (a.status == 'installed')
                return 1
            if (a.status == 'blocked')
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

        // render plugins
        var plugin
        for (i in plugins) {
            plugin   = plugins[i]
            category = plugin.category[0]

            self.cloudPluginBox('renderPlugin', plugin, self.find('#cloud-plugin-content-All'))

            if (category && category != 'All') {
                self.cloudPluginBox('renderPlugin', plugin, self.find('#cloud-plugin-content-' + category))
            }
        }

        // display plugin count
        for (category in categories) {
            var tab = self.find('#cloud-plugin-tab-' + category)
            tab.html(tab.html() + ' <span class="plugin_count">(' + categories[category] + ')</span>')
        }
    },

    renderPlugin: function (plugin, canvas) {
        var self = $(this)
        var uri = escape(plugin.uri)
        var comment = plugin.comment
        var has_comment = ""
        if(!comment) {
            comment = "No description available";
            has_comment = "no_description";
        }
        var plugin_data = {
            id: plugin.id || plugin._id, // FIXME: id or _id??
            thumbnail_href: plugin.thumbnail_href,
            screenshot_href: plugin.screenshot_href,
            has_comment: has_comment,
            comment: comment,
            uri: uri,
            status: plugin.status,
            brand : plugin.brand,
            label : plugin.label
        }

        var rendered = $(Mustache.render(TEMPLATES.cloudplugin, plugin_data))
        rendered.click(function () {
            self.cloudPluginBox('showPluginInfo', plugin)
        })

        canvas.append(rendered)
        return rendered
    },

    showPluginInfo: function (plugin) {
        var self = $(this)
        var uri  = escape(plugin.uri)

        var cloudChecked = false
        var localChecked = false

        var showInfo = function() {
            if (!cloudChecked || !localChecked)
                return

            function formatNum(x) {
                var parts = x.toString().split(".");
                parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
                return parts.join(".");
            }

            for(var i = 0; i< plugin.ports.control.input.length; i++) {  // formating numbers and flooring ranges up to two decimal cases
                plugin.ports.control.input[i].formatted = {}

                plugin.ports.control.input[i].formatted.default = formatNum(Math.floor(plugin.ports.control.input[i].ranges.default * 100) / 100);
                plugin.ports.control.input[i].formatted.maximum = formatNum(Math.floor(plugin.ports.control.input[i].ranges.maximum * 100) / 100);
                plugin.ports.control.input[i].formatted.minimum = formatNum(Math.floor(plugin.ports.control.input[i].ranges.minimum * 100) / 100);
            }

            var metadata = {
                uri: uri,
                thumbnail_href: plugin.thumbnail_href,
                screenshot_href: plugin.screenshot_href,
                category: plugin.category[0] || "",
                installed_version: version(plugin.installedVersion),
                latest_version: version(plugin.latestVersion),
                package_name: (plugin.bundle_name || plugin.bundles[0]).replace(/\.lv2$/, ''),
                comment: plugin.comment || "No description available",
                brand : plugin.brand,
                name  : plugin.name,
                label : plugin.label,
                ports : plugin.ports,
            }

            var info = $(Mustache.render(TEMPLATES.cloudplugin_info, metadata))

            // The remove button will remove the plugin, close window and re-render the plugins
            // without the removed one
            if (plugin.installedVersion) {
                info.find('.js-install').hide()
                info.find('.js-remove').show().click(function () {
                    // Remove plugin
                    self.data('removePlugin')(plugin, function (ok) {
                        if (ok) {
                            info.window('close')

                            delete desktop.pluginIndexerData[plugin.uri].installedVersion
                            desktop.pluginIndexerData[plugin.uri].status = 'blocked'

                            desktop.rescanPlugins()
                            self.cloudPluginBox('search')
                        }
                    })
                })
            } else {
                info.find('.js-remove').hide()
                info.find('.js-installed-version').hide()
                info.find('.js-install').show().click(function () {
                    // Install plugin
                    self.data('installPlugin')(plugin, function (pluginData) {
                        if (pluginData) {
                            pluginData.status = 'installed'
                            pluginData.latestVersion = [pluginData.minorVersion, pluginData.microVersion, pluginData.release]
                            pluginData.installedVersion = pluginData.latestVersion

                            desktop.pluginIndexerData[plugin.uri] = $.extend(plugin, pluginData)

                            if (info.is(':visible')) {
                                info.remove()
                                self.cloudPluginBox('checkLocalScreenshot', pluginData)
                                self.cloudPluginBox('showPluginInfo', pluginData)
                            }
                            desktop.rescanPlugins()
                            self.cloudPluginBox('search')
                        }
                    })
                })
            }

            if (plugin.installedVersion && compareVersions(plugin.latestVersion, plugin.installedVersion) > 0) {
                info.find('.js-upgrade').show().click(function () {
                    // Upgrade plugin
                    self.data('upgradePlugin')(plugin, function (pluginData) {
                        if (pluginData) {
                            pluginData.status = 'installed'
                            pluginData.latestVersion = [pluginData.minorVersion, pluginData.microVersion, pluginData.release]
                            pluginData.installedVersion = pluginData.latestVersion

                            desktop.pluginIndexerData[plugin.uri] = $.extend(plugin, pluginData)

                            if (info.is(':visible')) {
                                info.remove()
                                self.cloudPluginBox('checkLocalScreenshot', pluginData)
                                self.cloudPluginBox('showPluginInfo', pluginData)
                            }
                            desktop.rescanPlugins()
                            self.cloudPluginBox('search')
                        }
                    })
                })
            } else {
                info.find('.js-upgrade').hide()
            }

            if (! plugin.latestVersion) {
                info.find('.js-latest-version').hide()
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
        }

        // get full plugin info if plugin has a local version
        if ((plugin.bundles && plugin.bundles.length > 0) || ! plugin.installedVersion) {
            localChecked = true
        } else {
            $.ajax({
                url: "/effect/get",
                data: {
                    uri: plugin.uri
                },
                success: function (pluginData) {
                    plugin = $.extend(plugin, pluginData)
                    localChecked = true
                    showInfo()
                },
                dataType: 'json'
            })
        }

        if (plugin.latestVersion) {
            cloudChecked = true
        } else {
            $.ajax({
                url: SITEURLNEW + "/lv2/plugins",
                data: {
                    uri: plugin.uri
                },
                success: function (pluginData) {
                    if (pluginData && Object.keys(pluginData).length > 0) {
                        plugin.latestVersion = [pluginData.minorVersion, pluginData.microVersion, pluginData.release_number]
                    } else {
                        plugin.latestVersion = null
                    }
                    cloudChecked = true
                    showInfo()
                },
                error: function () {
                    plugin.latestVersion = null
                    cloudChecked = true
                    showInfo()
                },
                dataType: 'json'
            })
        }

        showInfo()
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
