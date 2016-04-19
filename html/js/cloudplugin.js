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

// add this to plugin data when cloud fails
function getDummyPluginData() {
    return $.extend(true, {}, {
        bundles: [""],
        ports: {
            control: {
                input: []
            },
        },
    })
}

JqueryClass('cloudPluginBox', {
    init: function (options) {
        var self = $(this)

        options = $.extend({
            resultCanvas: self.find('.js-cloud-plugins'),
            removePluginBundles: function (bundles, callback) {
                callback(null)
            },
            installPluginURI: function (uri, callback) {
                callback(null)
            },
            upgradePluginURI: function (uri, callback) {
                callback(null)
            }
        }, options)

        self.data(options)

        var searchbox = self.find('input[type=search]')

        // make sure searchbox is empty on init
        searchbox.val("")

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

        self.find('input:checkbox[name=installed]').click(function (e) {
            self.cloudPluginBox('search')
        })

        self.find('input:checkbox[name=stable]').click(function (e) {
            self.cloudPluginBox('search')
        })
        $('#cloud_install_all').click(function (e) {
            self.cloudPluginBox('search', function (plugins) {
                var bundle_id, bundle_ids = []

                for (var i in plugins) {
                    bundle_id = plugins[i].bundle_id
                    if (! bundle_id) {
                        continue
                    }
                    if (plugins[i].installedVersion) {
                        continue
                    }
                    if (bundle_ids.indexOf(bundle_id) < 0) {
                        bundle_ids.push(bundle_id)
                    }
                }

                var count = 0
                var finished = function () {
                    count += 1
                    if (count != bundle_ids.length)
                        return;
                    self.cloudPluginBox('search')
                }

                for (var i in bundle_ids) {
                    desktop.installationQueue.installUsingBundle(bundle_ids[i], finished)
                }
            })
        })
        $('#cloud_update_all').click(function (e) {
            self.cloudPluginBox('search', function (plugins) {
                var plugin, bundle_id, bundle_ids = []

                for (var i in plugins) {
                    plugin    = plugins[i]
                    bundle_id = plugin.bundle_id
                    if (! bundle_id) {
                        continue
                    }
                    if (! plugin.installedVersion) {
                        continue
                    }
                    if (compareVersions(plugin.latestVersion, plugin.installedVersion) <= 0) {
                        continue
                    }
                    if (bundle_ids.indexOf(bundle_id) < 0) {
                        bundle_ids.push(bundle_id)
                    }
                }

                var count = 0
                var finished = function () {
                    count += 1
                    if (count != bundle_ids.length)
                        return;
                    self.cloudPluginBox('search')
                }

                for (var i in bundle_ids) {
                    desktop.installationQueue.installUsingBundle(bundle_ids[i], finished)
                }
            })
        })

        var results = {}
        self.data('results', results)

        self.data('category', null)
        self.find('ul.categories li').click(function () {
            var category = $(this).attr('id').replace(/^cloud-plugin-tab-/, '')
            self.cloudPluginBox('setCategory', category)
        })

        self.cloudPluginBox('setCategory', "All")

        options.open = function () {
            var stablecb = self.find('input:checkbox[name=stable]')
            if (stablecb.is(':checked')) {
                self.cloudPluginBox('search')
            } else {
                stablecb.click()
            }
            return false
        }

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
    search: function (customRenderCallback) {
        var self  = $(this)
        var query = {
            text: self.data('searchbox').val(),
            summary: "true",
        }
        if (self.find('input:checkbox[name=stable]:checked').length > 0) {
            query.stable = "true"
        }
        if (self.find('input:checkbox[name=installed]:checked').length)
            return self.cloudPluginBox('searchInstalled', query, customRenderCallback)
        return self.cloudPluginBox('searchAll', query, customRenderCallback)
    },

    // search cloud and local plugins, show all but prefer cloud
    searchAll: function (query, customRenderCallback) {
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

                    if (compareVersions(cplugin.installedVersion, cplugin.latestVersion) >= 0) {
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

            if (customRenderCallback) {
                customRenderCallback(plugins)
            } else {
                self.cloudPluginBox('showPlugins', plugins)
            }
        }

        // cloud search
        $.ajax({
            method: 'GET',
            url: SITEURL + "/lv2/plugins",
            data: query,
            success: function (plugins) {
                results.cloud = plugins
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
        if (query.text)
        {
            var allplugins = desktop.pluginIndexerData
            var lplugins   = {}

            var ret = desktop.pluginIndexer.search(query.text)
            for (var i in ret) {
                var uri = ret[i].ref
                if (! allplugins[uri]) {
                    console.log("ERROR: Plugin '" + uri + "' was not previously cached, cannot show it")
                    continue
                }
                lplugins[uri] = allplugins[uri]
            }

            results.local = $.extend(true, {}, lplugins) // deep copy instead of link/reference
            if (results.cloud != null)
                renderResults()
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
                        plugin.installedVersion = [plugin.minorVersion, plugin.microVersion, plugin.release]
                        allplugins[plugin.uri] = plugin
                    }
                    desktop.resetPluginIndexer(allplugins)

                    results.local = $.extend(true, {}, allplugins) // deep copy instead of link/reference
                    if (results.cloud != null)
                        renderResults()
                },
                dataType: 'json',
            })
        }
    },

    // search cloud and local plugins, show installed only
    searchInstalled: function (query, customRenderCallback) {
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

                    if (compareVersions(lplugin.installedVersion, lplugin.latestVersion) >= 0) {
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

            if (customRenderCallback) {
                customRenderCallback(plugins)
            } else {
                self.cloudPluginBox('showPlugins', plugins)
            }
        }

        // cloud search
        $.ajax({
            method: 'GET',
            url: SITEURL + "/lv2/plugins",
            data: query,
            success: function (plugins) {
                // index by uri, needed later to check its latest version
                var cplugins = {}
                for (var i in plugins) {
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
        if (query.text)
        {
            var allplugins = desktop.pluginIndexerData
            var lplugins   = []

            var ret = desktop.pluginIndexer.search(query.text)
            for (var i in ret) {
                var uri = ret[i].ref
                if (! allplugins[uri]) {
                    console.log("ERROR: Plugin '" + uri + "' was not previously cached, cannot show it")
                    continue
                }
                lplugins.push(allplugins[uri])
            }

            results.local = $.extend(true, {}, lplugins) // deep copy instead of link/reference
            if (results.cloud != null)
                renderResults()
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
                        plugin.installedVersion = [plugin.minorVersion, plugin.microVersion, plugin.release]
                        allplugins[plugin.uri] = plugin
                    }
                    desktop.resetPluginIndexer(allplugins)

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

        // sort plugins by label
        var alower, blower
        plugins.sort(function (a, b) {
            alower = a.label.toLowerCase()
            blower = b.label.toLowerCase()
            if (alower > blower)
                return 1
            if (alower < blower)
                return -1
            return 0
        })

        var category   = {}
        var categories = {
            'All': plugins.length
        }
        var cachedContentCanvas = {
            'All': self.find('#cloud-plugin-content-All')
        }
        var pluginsDict = {}

        var plugin, render
        for (var i in plugins) {
            plugin   = plugins[i]
            category = plugin.category[0]
            render   = self.cloudPluginBox('renderPlugin', plugin)

            pluginsDict[plugin.uri] = plugin

            if (category && category != 'All') {
                if (categories[category] == null) {
                    categories[category] = 1
                    cachedContentCanvas[category] = self.find('#cloud-plugin-content-' + category)
                } else {
                    categories[category] += 1
                }
                render.clone(true).appendTo(cachedContentCanvas[category])
            }

            render.appendTo(cachedContentCanvas['All'])
        }

        self.data('pluginsDict', pluginsDict)

        // display plugin count
        self.cloudPluginBox('setCategoryCount', categories)
    },

    setCategoryCount: function (categories) {
        var self = $(this)
        self.data('categoryCount', categories)

        var tab
        for (var category in categories) {
            tab = self.find('#cloud-plugin-tab-' + category)
            tab.html(tab.html().split(/\s/)[0] + ' <span class="plugin_count">(' + categories[category] + ')</span>')
        }
    },

    renderPlugin: function (plugin) {
        var self = $(this)
        var uri = escape(plugin.uri)
        var comment = plugin.comment
        var has_comment = ""
        if(!comment) {
            comment = "No description available";
            has_comment = "no_description";
        }
        var plugin_data = {
            uri: uri,
            screenshot_href: plugin.screenshot_href,
            has_comment: has_comment,
            comment: comment,
            status: plugin.status,
            brand : plugin.brand,
            label : plugin.label
        }

        var rendered = $(Mustache.render(TEMPLATES.cloudplugin, plugin_data))
        rendered.click(function () {
            self.cloudPluginBox('showPluginInfo', plugin)
        })

        return rendered
    },

    postInstallAction: function (installed, removed) {
        var category, categories = self.data('categoryCount')

        // ---------------------------------------------------------------
        // REMOVED

        for (var i in removed) {
            uri     = removed[i]
            lplugin = self.data('pluginsDict')[uri]
            oldElem = self.find('.cloud-plugin[mod-uri="'+escape(uri)+'"]')

            if (lplugin.latestVersion) {
                // removing a plugin available on cloud, keep its store item
                lplugin.status = 'blocked'
                lplugin.bundle_name = bundle_name
                delete lplugin.bundles
                delete lplugin.installedVersion

                newElem = self.cloudPluginBox('renderPlugin', lplugin)
                oldElem.replaceWith(newElem)

            } else {
                // removing local plugin means the number of possible plugins goes down
                category = lplugin.category[0]

                if (category && category != 'All') {
                    categories[category] -= 1
                }
                categories['All'] -= 1

                // remove it from store
                delete self.data('pluginsDict')[uri]
                oldElem.remove()
            }
        }

        // ---------------------------------------------------------------
        // INSTALLED

        for (var i in installed) {
            uri     = installed[i]
            cplugin = self.data('pluginsDict')[uri]

            cplugin.status = 'installed'
            cplugin.bundles = bundles
            cplugin.installedVersion = cplugin.latestVersion

            oldElem = self.find('.cloud-plugin[mod-uri="'+escape(uri)+'"]')
            newElem = self.cloudPluginBox('renderPlugin', cplugin)
            oldElem.replaceWith(newElem)
        }

        // ---------------------------------------------------------------
        // UPDATED

        // [re-]installed plugins
        for (var i in installed) {
            uri     = installed[i]
            cplugin = self.data('pluginsDict')[uri]

            cplugin.status = 'installed'
            cplugin.bundles = bundles
            cplugin.installedVersion = cplugin.latestVersion

            oldElem = self.find('.cloud-plugin[mod-uri="'+escape(uri)+'"]')
            newElem = self.cloudPluginBox('renderPlugin', cplugin)
            oldElem.replaceWith(newElem)
        }

        // removed plugins (assume removed from store)
        for (var i in removed) {
            uri = removed[i]

            if (installed.indexOf(uri) >= 0) {
                continue
            }

            lplugin = self.data('pluginsDict')[uri]
            oldElem = self.find('.cloud-plugin[mod-uri="'+escape(uri)+'"]')

            // removing local plugin means the number of possible plugins goes down
            category = lplugin.category[0]
            if (category && category != 'All') {
                categories[category] -= 1
            }
            categories['All'] -= 1

            // remove it from store
            delete self.data('pluginsDict')[uri]
            oldElem.remove()
        }

        // ---------------------------------------------------------------

        self.cloudPluginBox('setCategoryCount', categories)
        info.window('close')
    },

    showPluginInfo: function (plugin, autoAction) {
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

            for (var i = 0; i < plugin.ports.control.input.length; i++) {  // formating numbers and flooring ranges up to two decimal cases
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

            var canInstall = false,
                canUpgrade = false

            // The remove button will remove the plugin, close window and re-render the plugins
            // without the removed one
            if (plugin.installedVersion) {
                info.find('.js-install').hide()
                info.find('.js-remove').show().click(function () {
                    // Remove plugin
                    self.data('removePluginBundles')(plugin.bundles, function (resp) {
                        desktop.updatePluginList([], resp.removed)

                        var oldElem, newElem, uri, lplugin, category,
                            bundle_name = plugin.bundles[0].split('/').filter(function(el){return el.length!=0}).pop(0),
                            categories = self.data('categoryCount')

                        for (var i in resp.removed) {
                            uri     = resp.removed[i]
                            lplugin = self.data('pluginsDict')[uri]
                            oldElem = self.find('.cloud-plugin[mod-uri="'+escape(uri)+'"]')

                            if (lplugin.latestVersion) {
                                // removing a plugin available on cloud, keep its store item
                                lplugin.status = 'blocked'
                                lplugin.bundle_name = bundle_name
                                delete lplugin.bundles
                                delete lplugin.installedVersion

                                newElem = self.cloudPluginBox('renderPlugin', lplugin)
                                oldElem.replaceWith(newElem)

                            } else {
                                // removing local plugin means the number of possible plugins goes down
                                category = lplugin.category[0]

                                if (category && category != 'All') {
                                    categories[category] -= 1
                                }
                                categories['All'] -= 1

                                // remove it from store
                                delete self.data('pluginsDict')[uri]
                                oldElem.remove()
                            }
                        }

                        self.cloudPluginBox('setCategoryCount', categories)
                        info.window('close')
                    })
                })
            } else {
                canInstall = true
                info.find('.js-remove').hide()
                info.find('.js-installed-version').hide()
                info.find('.js-install').show().click(function () {
                    // Install plugin
                    self.data('installPluginURI')(plugin.uri, function (resp) {
                        var oldElem, newElem, uri, category, cplugin,
                            bundles = [LV2_PLUGIN_DIR + plugin.bundle_name]

                        for (var i in resp.installed) {
                            uri     = resp.installed[i]
                            cplugin = self.data('pluginsDict')[uri]

                            cplugin.status = 'installed'
                            cplugin.bundles = bundles
                            cplugin.installedVersion = cplugin.latestVersion

                            oldElem = self.find('.cloud-plugin[mod-uri="'+escape(uri)+'"]')
                            newElem = self.cloudPluginBox('renderPlugin', cplugin)
                            oldElem.replaceWith(newElem)
                        }

                        info.window('close')
                    })
                })
            }

            if (plugin.installedVersion && compareVersions(plugin.latestVersion, plugin.installedVersion) > 0) {
                canUpgrade = true
                info.find('.js-upgrade').show().click(function () {
                    // Upgrade plugin
                    self.data('upgradePluginURI')(plugin.uri, function (resp) {
                        var oldElem, newElem, uri, category, lplugin,
                            bundles = [LV2_PLUGIN_DIR + plugin.bundle_name],
                            categories = self.data('categoryCount')

                        // [re-]installed plugins
                        for (var i in resp.installed) {
                            uri     = resp.installed[i]
                            cplugin = self.data('pluginsDict')[uri]

                            cplugin.status = 'installed'
                            cplugin.bundles = bundles
                            cplugin.installedVersion = cplugin.latestVersion

                            oldElem = self.find('.cloud-plugin[mod-uri="'+escape(uri)+'"]')
                            newElem = self.cloudPluginBox('renderPlugin', cplugin)
                            oldElem.replaceWith(newElem)
                        }

                        // removed plugins (assume removed from store)
                        for (var i in resp.removed) {
                            uri = resp.removed[i]

                            if (resp.installed.indexOf(uri) >= 0) {
                                continue
                            }

                            lplugin = self.data('pluginsDict')[uri]
                            oldElem = self.find('.cloud-plugin[mod-uri="'+escape(uri)+'"]')

                            // removing local plugin means the number of possible plugins goes down
                            category = lplugin.category[0]
                            if (category && category != 'All') {
                                categories[category] -= 1
                            }
                            categories['All'] -= 1

                            // remove it from store
                            delete self.data('pluginsDict')[uri]
                            oldElem.remove()
                        }

                        self.cloudPluginBox('setCategoryCount', categories)
                        info.window('close')
                    })
                })
            } else {
                info.find('.js-upgrade').hide()
            }

            if (! plugin.latestVersion) {
                info.find('.js-latest-version').hide()
            }

            if (autoAction) {
                var elem
                if (autoAction == "install" && canInstall) {
                    elem = info.find('.js-install')
                } else if (autoAction == "upgrade" && canUpgrade) {
                    elem = info.find('.js-upgrade')
                }
                if (elem != null) {
                    console.log("Processing", plugin.uri)
                    elem.click()
                }
            } else {
                info.appendTo($('body'))
                info.window('open')
                self.data('info', info)
            }
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
                    // delete cloud specific fields just in case
                    delete pluginData.bundle_name
                    delete pluginData.latestVersion
                    // ready to merge
                    plugin = $.extend(pluginData, plugin)
                    localChecked = true
                    showInfo()
                },
                error: function () {
                    // assume not installed
                    localChecked = true
                    showInfo()
                },
                dataType: 'json'
            })
        }

        // always get cloud plugin info
        $.ajax({
            url: SITEURL + "/lv2/plugins",
            data: {
                uri: plugin.uri
            },
            success: function (pluginData) {
                if (pluginData && pluginData.length > 0) {
                    pluginData = pluginData[0]
                    // delete local specific fields just in case
                    delete pluginData.bundles
                    delete pluginData.installedVersion
                    // ready to merge
                    plugin = $.extend(pluginData, plugin)
                    plugin.latestVersion = [plugin.minorVersion, plugin.microVersion, plugin.release_number]
                } else {
                    plugin = $.extend(getDummyPluginData(), plugin)
                    plugin.latestVersion = null
                }
                cloudChecked = true
                showInfo()
            },
            error: function () {
                plugin = $.extend(getDummyPluginData(), plugin)
                plugin.latestVersion = null
                cloudChecked = true
                showInfo()
            },
            dataType: 'json'
        })
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
