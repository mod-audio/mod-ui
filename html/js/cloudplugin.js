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
    checkLocalScreenshot: function(plugin) {
        if(plugin.status == 'installed') {
            if (plugin.gui.thumbnail && plugin.gui.screenshot) {
                plugin.screenshot_href =  "/effect/image/screenshot.png?uri=" + encodeURIComponent(plugin.uri)
                plugin.thumbnail_href  = "/effect/image/thumbnail.png?uri=" + encodeURIComponent(plugin.uri)
            } else {
                plugin.screenshot_href = "/resources/pedals/default-screenshot.png"
                plugin.thumbnail_href  = "/resources/pedals/default-thumbnail.png"
            }
        }
        else {
            if (!plugin.screenshot_href && !plugin.thumbnail_href) {                        
                plugin.screenshot_href = "/resources/pedals/default-screenshot.png"
                plugin.thumbnail_href  = "/resources/pedals/default-thumbnail.png"
            }
        }
    },
    searchAll: function (query) {
        // TODO: implement new cloud API
        
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
                plugin.latestVersion = [plugin.minorVersion, plugin.microVersion]        
                console.log(plugin.label+' - '+plugin.installedVersion+' - '+plugin.latestVersion)
                if (plugin.installedVersion == null) {
                    plugin.status = 'blocked'
                } else if (compareVersions(plugin.installedVersion, plugin.latestVersion) == 0) {
                    plugin.status = 'installed'
                } else {
                    plugin.status = 'outdated'
                }
                if (results.local[plugin.uri]) {
                    self.cloudPluginBox('checkLocalScreenshot', plugin)
                    console.log(results.local[plugin.uri].release);
                    plugin.installedVersion = [results.local[plugin.uri].minorVersion,
                        results.local[plugin.uri].microVersion,
                        results.local[plugin.uri].release || 0
                    ]
                    delete results.local[plugin.uri] 
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
                self.cloudPluginBox('checkLocalScreenshot', plugin)
                plugins.push(plugin)
            }
            self.cloudPluginBox('showPlugins', plugins)
        }

        var url = query.term ? '/effect/search/' : '/effect/list'
        $.ajax({
            'method': 'GET',
            'url': url,
            'data': query,
            'success': function (plugins) {                
                self.data('allplugins', plugins)
                results.local = {}
                for (i in plugins) { // local thumbnails for installed plugins 
                    results.local[plugins[i].uri] = plugins[i]                    
                }
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
            'url':  SITEURL+url,
            'data': query,
            'success': function (plugins) {
                results.local = {}
                self.data('allplugins', plugins)
                for (i in plugins)
                    results.local[plugins[i].uri] = plugins[i]
                if (results.cloud != null)
                    renderResults()
            },
            'dataType': 'json'
        })

        $.ajax({
            'method': 'GET',
            'url': SITEURLNEW + "/lv2/plugins/",
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

        var url = (query.term ? '/effect/search/' : '/effect/list/')
        $.ajax({
            'method': 'GET',
            'url': url,
            'data': query,
            'success': function (plugins) {
                console.log(plugins);
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
            tab.html(tab.html() + ' <span class="plugin_count">(' + count[category] + ')</span>')
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
