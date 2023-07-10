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
                callback({})
            },
            installPluginURI: function (uri, callback) {
                callback({}, "")
            },
            upgradePluginURI: function (uri, callback) {
                callback({}, "")
            },
            info: null,
            fake: false,
            isMainWindow: true,
            windowName: "Plugin Store",
            pluginsData: {},
        }, options)

        self.data(options)

        var searchbox = self.find('input[type=search]')

        // make sure searchbox is empty on init
        searchbox.val("")

        self.data('searchbox', searchbox)
        searchbox.cleanableInput()

        self.data('category', null)
        self.cloudPluginBox('setCategory', "All")

        var lastKeyTimeout = null
        searchbox.keydown(function (e) {
            if (e.keyCode == 13) { // detect enter
                if (lastKeyTimeout != null) {
                    clearTimeout(lastKeyTimeout)
                    lastKeyTimeout = null
                }
                self.cloudPluginBox('search')
                return false
            }
            else if (e.keyCode == 8 || e.keyCode == 46) { // detect delete and backspace
                if (lastKeyTimeout != null) {
                    clearTimeout(lastKeyTimeout)
                }
                lastKeyTimeout = setTimeout(function () {
                    self.cloudPluginBox('search')
                }, 400);
            }
        })
        searchbox.keypress(function (e) { // keypress won't detect delete and backspace but will only allow inputable keys
            if (e.which == 13)
                return
            if (lastKeyTimeout != null) {
                clearTimeout(lastKeyTimeout)
            }
            lastKeyTimeout = setTimeout(function () {
                self.cloudPluginBox('search')
            }, 400);
        })
        searchbox.on('cut', function(e) {
            if (lastKeyTimeout != null) {
                clearTimeout(lastKeyTimeout)
            }
            lastKeyTimeout = setTimeout(function () {
                self.cloudPluginBox('search')
            }, 400);
        })
        searchbox.on('paste', function(e) {
            if (lastKeyTimeout != null) {
                clearTimeout(lastKeyTimeout)
            }
            lastKeyTimeout = setTimeout(function () {
                self.cloudPluginBox('search')
            }, 400);
        })

        self.find('input:checkbox[name=installed]').click(function (e) {
            self.find('input:checkbox[name=non-installed]').prop('checked', false)
            self.cloudPluginBox('search')
        })
        self.find('input:checkbox[name=non-installed]').click(function (e) {
            self.find('input:checkbox[name=installed]').prop('checked', false)
            self.cloudPluginBox('search')
        })
        self.find('input:checkbox[name=unstable]').click(function (e) {
            self.cloudPluginBox('search')
        })

        self.find('input:radio[name=plugins-source]').click(function (e) {
            self.cloudPluginBox('toggleFeaturedPlugins')
            self.cloudPluginBox('search')
        })

        $('#cloud_install_all').click(function (e) {
            if (! $(this).hasClass("disabled")) {
                $(this).addClass("disabled").css({color:'#444'})
                self.cloudPluginBox('installAllPlugins', false)
            }
        })
        $('#cloud_update_all').click(function (e) {
            if (! $(this).hasClass("disabled")) {
                $(this).addClass("disabled").css({color:'#444'})
                self.cloudPluginBox('installAllPlugins', true)
            }
        })

        var results = {}
        self.data('results', results)

        self.data('firstLoad', true)
        self.find('ul.categories li').click(function () {
            var category = $(this).attr('id').replace(/^cloud-plugin-tab-/, '')
            self.cloudPluginBox('setCategory', category)
        })

        options.open = function () {
            self.data('firstLoad', true)
            $('#cloud_install_all').addClass("disabled").css({color:'#444'})
            $('#cloud_update_all').addClass("disabled").css({color:'#444'})

            var unstablecb = self.find('input:checkbox[name=unstable]')
            if (!unstablecb.is(':checked')) {
                self.cloudPluginBox('search')
            } else {
                unstablecb.click()
            }

            return false
        }

        self.window(options)

        return self
    },

    setCategory: function (category) {
        var self = $(this)

        self.find('ul.categories li').removeClass('selected')
        self.find('.plugins-wrapper').hide()
        self.find('#cloud-plugin-tab-' + category).addClass('selected')
        self.find('#cloud-plugin-content-' + category).show().css('display', 'inline-block')
        self.data('category', category)

        // hide/show featured plugins if specific category/All
        self.cloudPluginBox('toggleFeaturedPlugins')
    },
    cleanResults: function () {
        var self = $(this)
        self.find('.plugins-wrapper').html('')
        self.find('ul.categories li').each(function () {
            var content = $(this).html().split(/\s/)
            if (content.length >= 2 && content[1] == "Utility") {
                $(this).html(content[0] + " Utility")
            } else {
                $(this).html(content[0])
            }
        });
    },
    checkLocalScreenshot: function (plugin) {
        if (plugin.status == 'installed') {
            if (plugin.gui) {
                var uri = escape(plugin.uri)
                var ver = plugin.installedVersion.join('_')
                plugin.screenshot_href = "/effect/image/screenshot.png?uri=" + uri + "&v=" + ver
                plugin.thumbnail_href  = "/effect/image/thumbnail.png?uri=" + uri + "&v=" + ver
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

    toggleFeaturedPlugins: function () {
      var self  = $(this)
      var featuredPlugins = self.find('.featured-plugins')
      var queryText = self.data('searchbox').val()
      var category = self.data('category')

      if (queryText === '' && category === 'All') {
        if (featuredPlugins.is(':hidden')) {
          featuredPlugins.show()
        }
      } else if (featuredPlugins.is(':visible')) {
        featuredPlugins.hide()
      }
    },

    // search all or installed, depending on selected option
    search: function (customRenderCallback) {
        var self  = $(this)
        var query = {
            text: self.data('searchbox').val(),
            summary: "true",
            image_version: VERSION,
            bin_compat: BIN_COMPAT,
        }

        if (self.find('input:checkbox[name=unstable]:checked').length == 0 || self.data('fake')) {
            query.stable = true
        }

        // hide/show featured plugins if searching/not searching
        self.cloudPluginBox('toggleFeaturedPlugins')

        if (self.find('input:checkbox[name=installed]:checked').length)
            return self.cloudPluginBox('searchInstalled', query, customRenderCallback)

        if (self.find('input:checkbox[name=non-installed]:checked').length)
            return self.cloudPluginBox('searchAll', false, query, customRenderCallback)

        return self.cloudPluginBox('searchAll', true, query, customRenderCallback)
    },

    synchronizePluginData: function (plugin) {
        var index = $(this).data('pluginsData')
        indexed = index[plugin.uri]
        if (indexed == null) {
            indexed = {}
            index[plugin.uri] = indexed
        }
        // Let's store all data safely, while modifying the given object
        // to have all available data
        $.extend(indexed, plugin)
        $.extend(plugin, indexed)

        if (window.devicePixelRatio && window.devicePixelRatio >= 2) {
            plugin.thumbnail_href = plugin.thumbnail_href.replace("thumbnail","screenshot")
        }
    },

    rebuildSearchIndex: function () {
        var plugins = Object.values($(this).data('pluginsData'))
        desktop.resetPluginIndexer(plugins.filter(function(plugin) { return !!plugin.installedVersion }))
    },

    // search cloud and local plugins, prefer cloud
    searchAll: function (showInstalled, query, customRenderCallback) {
        var self = $(this)
        var results = {}
        var cplugin, lplugin,
            cloudReached = false

        renderResults = function () {
            if (results.local == null || results.cloud == null || results.shopify == null)
                return

            var plugins = []

            for (var i in results.cloud) {
                cplugin = results.cloud[i]
                lplugin = results.local[cplugin.uri]

                if (!showInstalled && lplugin) {
                    continue
                }


                if (results.featured) {
                    cplugin.featured = results.featured.filter(function (ft) { return ft.uri === cplugin.uri })[0]
                }

                cplugin.latestVersion = [cplugin.builder_version || 0, cplugin.minorVersion, cplugin.microVersion, cplugin.release_number]
                if (desktop.licenseManager && cplugin.mod_license === 'paid_perpetual') {
                    cplugin.commercial = true
                    if (results.shopify[cplugin.uri]) {
                        cplugin.shopify_id = results.shopify[cplugin.uri].id
                        cplugin.licensed = desktop.licenseManager.licensed(cplugin.uri)

                        if (!cplugin.licensed)
                            cplugin.price = results.shopify[cplugin.uri].price
                    } else {
                        // Plugin is commercial but it's not at shopify.
                        // Trial available, commercial version coming soon
                        cplugin.licensed = desktop.licenseManager.licensed(cplugin.uri)
                    }
                }

                cplugin.demo = lplugin && cplugin.commercial && !cplugin.licensed

                if (cplugin.shopify_id) {
                    if (!cplugin.licensed)
                        cplugin.price = results.shopify[cplugin.uri].price;
                    if (lplugin && cplugin.licensed && !lplugin.licensed) {
                        // Should not happen
                        new Notification('warn', 'License for '+cplugin.label+' not downloaded, please reload interface', 4000);
                    }
                } else if (cplugin.commercial) {
                    cplugin.coming = true;
                }

                if (lplugin) {
                    if (!lplugin.installedVersion) {
                        console.log("local plugin is missing version info:", lplugin.uri)
                        lplugin.installedVersion = [0, 0, 0, 0]
                    }

                    cplugin.installedVersion = lplugin.installedVersion
                    delete results.local[cplugin.uri]

                    if (compareVersions(cplugin.installedVersion, cplugin.latestVersion) >= 0) {
                        cplugin.status = 'installed'
                    } else {
                        cplugin.status = 'outdated'
                    }

                    // overwrite build environment if local plugin
                    cplugin.buildEnvironment = lplugin.buildEnvironment

                    self.cloudPluginBox('checkLocalScreenshot', cplugin)

                } else {
                    cplugin.installedVersion = null // if set to [0, 0, 0, 0], it appears as intalled on cloudplugininfo
                    cplugin.status = 'blocked'
                }

                if (self.data('fake') && cplugin.mod_license === 'paid_perpetual') {
                    cplugin.licensed = true;
                }

                if (!cplugin.screenshot_available && !cplugin.thumbnail_available) {
                    if (!cplugin.screenshot_href && !cplugin.thumbnail_href) {
                        cplugin.screenshot_href = "/resources/pedals/default-screenshot.png"
                        cplugin.thumbnail_href  = "/resources/pedals/default-thumbnail.png"
                    }
                }
                self.cloudPluginBox('synchronizePluginData', cplugin)
                plugins.push(cplugin)
            }

            // for all the other plugins that are not in the cloud
            if (showInstalled) {
                for (var uri in results.local) {
                    lplugin = results.local[uri]
                    lplugin.status = 'installed'
                    lplugin.latestVersion = null
                    self.cloudPluginBox('checkLocalScreenshot', lplugin)
                    if (lplugin.licensed) {
                        if (lplugin.licensed > 0) {
                            lplugin.licensed = true;
                        } else {
                            lplugin.licensed = false;
                            lplugin.demo = true;
                        }
                    }
                    self.cloudPluginBox('synchronizePluginData', lplugin)
                    plugins.push(lplugin)
                }
            }

            if (customRenderCallback) {
                customRenderCallback(plugins)
            } else {
                self.cloudPluginBox('showPlugins', plugins, cloudReached)
            }

            if (self.data('firstLoad')) {
                self.data('firstLoad', false)
                $('#cloud_install_all').removeClass("disabled").css({color:'white'})
                $('#cloud_update_all').removeClass("disabled").css({color:'white'})
            }
            self.cloudPluginBox('rebuildSearchIndex')
        }

        // get list of shopify commercial plugins
        desktop.fetchShopProducts().then(function(products) {
            results.shopify = {};
            for (var i in products) {
                var uri = products[i].selectedVariant.attrs.variant.sku;
                results.shopify[uri] = {
                    id: products[i].id,
                    price: products[i].selectedVariant.price
                }
            }
            renderResults();
        }, function() {
            if (desktop.cloudAccessToken)
                new Notification('error', "Our commercial plugin store is offline now, sorry for the inconvenience")
            results.shopify = {}
            renderResults();
        });

        // cloud search
        var cloudResults
        $.ajax({
            method: 'GET',
            url: SITEURL + "/lv2/plugins",
            data: query,
            success: function (plugins) {
                cloudReached = true
                cloudResults = plugins
            },
            error: function () {
                cloudResults = []
            },
            complete: function () {
                $.ajax({
                    method: 'GET',
                    url: SITEURL + "/lv2/plugins/featured",
                    success: function (featured) {
                        results.featured = featured
                    },
                    error: function () {
                        results.featured = []
                        $('.featured-plugins').hide()
                    },
                    complete: function () {
                        results.cloud = cloudResults;
                        renderResults()
                    },
                    cache: false,
                    dataType: 'json'
                })
            },
            cache: false,
            dataType: 'json'
        })

        if (self.data('fake')) {
            results.local = {}
            renderResults()
            return;
        }

        // local search
        if (query.text)
        {
            var lplugins = {}

            var ret = desktop.pluginIndexer.search(query.text)
            for (var i in ret) {
                var uri = ret[i].ref
                var pluginData = self.data('pluginsData')[uri]
                if (! pluginData) {
                    console.log("ERROR: Plugin '" + uri + "' was not previously cached, cannot show it")
                    continue
                }
                lplugins[uri] = pluginData
            }

            results.local = $.extend(true, {}, lplugins) // deep copy instead of link/reference
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

                        plugin.installedVersion = [plugin.builder, plugin.minorVersion, plugin.microVersion, plugin.release]
                        allplugins[plugin.uri] = plugin
                    }

                    results.local = $.extend(true, {}, allplugins) // deep copy instead of link/reference
                    renderResults()
                },
                error: function () {
                    results.local = {}
                    renderResults()
                },
                cache: false,
                dataType: 'json'
            })
        }
    },

    // search cloud and local plugins, show installed only
    searchInstalled: function (query, customRenderCallback) {
        var self = $(this)
        var results = {}
        var cplugin, lplugin,
            cloudReached = false

        renderResults = function () {
            var plugins = []

            for (var i in results.local) {
                lplugin = results.local[i]
                cplugin = results.cloud[lplugin.uri]

                if (!lplugin.installedVersion) {
                    console.log("local plugin is missing version info:", lplugin.uri)
                    lplugin.installedVersion = [0, 0, 0, 0]
                }

                if (cplugin) {
                    lplugin.stable        = cplugin.stable
                    lplugin.latestVersion = [cplugin.builder_version || 0, cplugin.minorVersion, cplugin.microVersion, cplugin.release_number]

                    if (compareVersions(lplugin.installedVersion, lplugin.latestVersion) >= 0) {
                        lplugin.status = 'installed'
                    } else {
                        lplugin.status = 'outdated'
                    }
                    if (cplugin.shopify_id && !lplugin.licensed) {
                        lplugin.demo = true
                    }
                } else {
                    lplugin.latestVersion = null
                    lplugin.status = 'installed'
                }

                if (lplugin.licensed) {
                    if (lplugin.licensed > 0) {
                        lplugin.licensed = true;
                    } else {
                        lplugin.licensed = false;
                        lplugin.demo = true;
                    }
                }

                // we're showing installed only, so prefer to show installed modgui screenshot
                if (lplugin.gui) {
                    var uri = escape(lplugin.uri)
                    var ver = [lplugin.builder, lplugin.microVersion, lplugin.minorVersion, lplugin.release].join('_')

                    lplugin.screenshot_href = "/effect/image/screenshot.png?uri=" + uri + "&v=" + ver
                    lplugin.thumbnail_href  = "/effect/image/thumbnail.png?uri=" + uri + "&v=" + ver
                } else {
                    lplugin.screenshot_href = "/resources/pedals/default-screenshot.png"
                    lplugin.thumbnail_href  = "/resources/pedals/default-thumbnail.png"
                }
                self.cloudPluginBox('synchronizePluginData', lplugin)
                plugins.push(lplugin)
            }

            if (customRenderCallback) {
                customRenderCallback(plugins)
            } else {
                self.cloudPluginBox('showPlugins', plugins, cloudReached)
            }

            if (self.data('firstLoad')) {
                self.data('firstLoad', false)
                $('#cloud_install_all').removeClass("disabled").css({color:'white'})
                $('#cloud_update_all').removeClass("disabled").css({color:'white'})
            }
            self.cloudPluginBox('rebuildSearchIndex')
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
                    delete plugins[i].installedVersion
                    delete plugins[i].bundles
                    cplugins[plugins[i].uri] = plugins[i]
                }
                cloudReached = true
                results.cloud = cplugins
                if (results.local != null)
                    renderResults()
            },
            error: function () {
                results.cloud = {}
                if (results.local != null)
                    renderResults()
            },
            cache: false,
            dataType: 'json'
        })

        // local search
        if (query.text)
        {
            var lplugins = []

            var ret = desktop.pluginIndexer.search(query.text)
            for (var i in ret) {
                var uri = ret[i].ref
                var pluginData = self.data('pluginsData')[uri]
                if (! pluginData) {
                    console.log("ERROR: Plugin '" + uri + "' was not previously cached, cannot show it")
                    continue
                }
                lplugins.push(pluginData)
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
                    var i, plugin
                    for (i in plugins) {
                        plugin = plugins[i]
                        plugin.installedVersion = [plugin.builder || 0, plugin.minorVersion, plugin.microVersion, plugin.release]
                    }

                    results.local = plugins
                    if (results.cloud != null)
                        renderResults()
                },
                cache: false,
                dataType: 'json'
            })
        }
    },

    showPlugins: function (plugins, cloudReached) {
        var self = $(this)
        self.cloudPluginBox('cleanResults')
        var featured = plugins.filter(function(p) {
            return p.featured;
        })

        // sort plugins by label
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

        // sort featured plugins by priority
        featured.sort(function (a, b) {
            a = a.featured.priority
            b = b.featured.priority
            if (a > b) {
                return 1
            }
            if (a < b) {
                return -1
            }
            return 0
        })

        var category   = {}
        var categories = {
            'All': plugins.length,
            'ControlVoltage': 0,
            'Delay': 0,
            'Distortion': 0,
            'Dynamics': 0,
            'Filter': 0,
            'Generator': 0,
            'MIDI': 0,
            'Modulator': 0,
            'Reverb': 0,
            'Simulator': 0,
            'Spatial': 0,
            'Spectral': 0,
            'Utility': 0,
        }
        var cachedContentCanvas = {
            'All': self.find('#cloud-plugin-content-All')
        }
        var pluginsDict = {}

        var getCategory = function(plugin) {
            category = plugin.category[0]
            if (category == 'Utility' && plugin.category.length == 2 && plugin.category[1] == 'MIDI') {
                return 'MIDI';
            }
            return category
        }

        var plugin, render
		var factory = function(img) {
			return function() {
			    img.css('opacity', 1)
                            var top = (parseInt((img.parent().height()-img.height())/2))+'px'
                            // We need to put a padding in image, but slick creates clones of the
                            // element to use on carousel, so we need padding in all clones
                            var uri = img.parent().parent().parent().parent().attr('mod-uri')
                            var clones = $('div.slick-slide[mod-uri="'+uri+'"][mod-role="cloud-plugin"]')
                            clones.find('img').css('padding-top', top);
			};
		}

		if (!self.data('featuredInitialized')) {
			var featuredCanvas = $('.carousel')
			for (var i in featured) {
				plugin = featured[i]
				render   = self.cloudPluginBox('renderPlugin', plugin, cloudReached, true)
				render.appendTo(featuredCanvas)
				render.find('img').on('load', factory(render.find('img')));
			}
			var columns = $(window).width() >= 1650 ? 5 : 3;
			featuredCanvas.slick({
				slidesToShow: Math.min(columns, plugins.length),
				centerPadding: '60px',
				centerMode: true,
			});
			self.data('featuredInitialized', true)
		}

        for (var i in plugins) {
            plugin   = plugins[i]
            category = getCategory(plugin)
            render   = self.cloudPluginBox('renderPlugin', plugin, cloudReached)

            pluginsDict[plugin.uri] = plugin

            if (category && category != 'All' && categories[category] != null) {
                categories[category] += 1
                if (cachedContentCanvas[category] == null) {
                    cachedContentCanvas[category] = self.find('#cloud-plugin-content-' + category)
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

        for (var category in categories) {
            var tab = self.find('#cloud-plugin-tab-' + category)
            if (tab.length == 0) {
                continue
            }
            var content = tab.html().split(/\s/)

            if (content.length >= 2 && content[1] == "Utility") {
                content = content[0] + " Utility"
            } else {
                content = content[0]
            }
            tab.html(content + ' <span class="plugin_count">(' + categories[category] + ')</span>')
        }
    },

    renderPlugin: function (plugin, cloudReached, featured) {
        var self = $(this)
        var uri = escape(plugin.uri)
        var comment = plugin.comment.trim()
        var has_comment = ""
        if(!comment) {
            comment = "No description available";
            has_comment = "no_description";
        }
        var plugin_data = {
            uri: uri,
            screenshot_href: plugin.screenshot_href,
            thumbnail_href: plugin.thumbnail_href,
            has_comment: has_comment,
            comment: comment,
            status: plugin.status,
            brand : plugin.brand,
            label : plugin.label,
            demo: !!plugin.demo,
            price: plugin.price,
            licensed: plugin.licensed,
            featured: plugin.featured,
            coming: plugin.coming,
            unstable: plugin.stable === false,
            build_env: plugin.buildEnvironment,
        }

        var template = featured ? TEMPLATES.featuredplugin : TEMPLATES.cloudplugin
        var rendered = $(Mustache.render(template, plugin_data))
        rendered.click(function () {
            self.cloudPluginBox('showPluginInfo', plugin.uri)
        })

        return rendered
    },

    installAllPlugins: function (updateOnly) {
        var self = $(this)

        self.cloudPluginBox('search', function (plugins) {
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

            var bundle_id, bundle_ids = []
            var currentCategory = $("#cloud-plugins-library .categories .selected").attr('id').replace(/^cloud-plugin-tab-/, '') || "All"

            var plugin
            for (var i in plugins) {
                plugin = plugins[i]
                if (! plugin.bundle_id || ! plugin.latestVersion) {
                    continue
                }
                if (plugin.installedVersion) {
                    if (compareVersions(plugin.latestVersion, plugin.installedVersion) <= 0) {
                        continue
                    }
                } else if (updateOnly) {
                    continue
                }

                var category = plugin.category[0]
                if (category == 'Utility' && plugin.category.length == 2 && plugin.category[1] == 'MIDI') {
                    category = 'MIDI'
                }

                // FIXME for midi
                if (bundle_ids.indexOf(plugin.bundle_id) < 0 && (currentCategory == "All" || currentCategory == category)) {
                    bundle_ids.push(plugin.bundle_id)
                }
            }

            if (bundle_ids.length == 0) {
                $('#cloud_install_all').removeClass("disabled").css({color:'white'})
                $('#cloud_update_all').removeClass("disabled").css({color:'white'})
                new Notification('warn', 'All plugins are '+(updateOnly?'updated':'installed')+', nothing to do', 8000)
                return
            }

            var count = 0
            var finished = function (resp, bundlename) {
                self.cloudPluginBox('postInstallAction', resp.installed, resp.removed, bundlename)
                count += 1
                if (count == bundle_ids.length) {
                    $('#cloud_install_all').removeClass("disabled").css({color:'white'})
                    $('#cloud_update_all').removeClass("disabled").css({color:'white'})
                    new Notification('warn', 'All plugins are now '+(updateOnly?'updated':'installed'), 8000)
                }
                if (resp.ok) {
                    self.cloudPluginBox('search')
                }
            }

            for (var i in bundle_ids) {
                desktop.installationQueue.installUsingBundle(bundle_ids[i], finished)
            }
        })
    },

    postInstallAction: function (installed, removed, bundlename) {
        var self = $(this)
        var bundle = LV2_PLUGIN_DIR + bundlename
        var category, categories = self.data('categoryCount')
        var uri, plugin, oldElem, newElem

        for (var i in installed) {
            uri    = installed[i]
            plugin = self.data('pluginsData')[uri]

            if (! plugin) {
                continue
            }

            plugin.status  = 'installed'
            if (plugin.commercial && !plugin.licensed)
                plugin.demo = true;
            plugin.bundles = [bundle]
            plugin.installedVersion = plugin.latestVersion

            oldElem = self.find('.cloud-plugin[mod-uri="'+escape(uri)+'"]')
            newElem = self.cloudPluginBox('renderPlugin', plugin, true)
            oldElem.replaceWith(newElem)
        }

        for (var i in removed) {
            uri = removed[i]

            if (installed.indexOf(uri) >= 0) {
                continue
            }

            var favoriteIndex = FAVORITES.indexOf(uri)
            if (favoriteIndex >= 0) {
                FAVORITES.splice(favoriteIndex, 1)
                $('#effect-content-Favorites').find('[mod-uri="'+escape(uri)+'"]').remove()
                $('#effect-tab-Favorites').html('Favorites (' + FAVORITES.length + ')')
            }

            plugin  = self.data('pluginsData')[uri]
            oldElem = self.find('.cloud-plugin[mod-uri="'+escape(uri)+'"]')

            if (plugin.latestVersion) {
                // removing a plugin available on cloud, keep its store item
                plugin.status = 'blocked'
                plugin.demo = false
                plugin.bundle_name = bundle
                delete plugin.bundles
                plugin.installedVersion = null

                newElem = self.cloudPluginBox('renderPlugin', plugin, true)
                oldElem.replaceWith(newElem)

            } else {
                // removing local plugin means the number of possible plugins goes down
                category = plugin.category[0]

                if (category && category != 'All') {
                    if (category == 'Utility' && plugin.category.length == 2 && plugin.category[1] == 'MIDI') {
                        category = 'MIDI'
                    }
                    categories[category] -= 1
                }
                categories['All'] -= 1

                // remove it from store
                delete self.data('pluginsData')[uri]
                oldElem.remove()
            }
        }

        self.cloudPluginBox('setCategoryCount', categories)
    },

    showPluginInfo: function (uri) {
        var self = $(this)

        var plugin = self.data('pluginsData')[uri]
        if (!plugin) {
            if (self.data('fake'))
                new Notification('error', "Requested plugin is not available")
            return
        }

        var cloudChecked = false
        var localChecked = false

        var showInfo = function() {
            if (!cloudChecked || !localChecked)
                return

            // formating numbers and flooring ranges up to two decimal cases
            for (var i = 0; i < plugin.ports.control.input.length; i++) {
                plugin.ports.control.input[i].formatted = format(plugin.ports.control.input[i])
            }

            if (plugin.ports.cv && plugin.ports.cv.input) {
              for (var i = 0; i < plugin.ports.cv.input.length; i++) {
                plugin.ports.cv.input[i].formatted = format(plugin.ports.cv.input[i])
              }
            }

            if (plugin.ports.cv && plugin.ports.cv.output) {
              for (var i = 0; i < plugin.ports.cv.output.length; i++) {
                plugin.ports.cv.output[i].formatted = format(plugin.ports.cv.output[i])
              }
            }

            var category = plugin.category[0]
            if (category == 'Utility' && plugin.category.length == 2 && plugin.category[1] == 'MIDI') {
                category = 'MIDI'
            }

            // Plugin might have been licensed after plugin data was bound to event,
            // so let's check
            if (desktop.licenseManager && desktop.licenseManager.licensed(plugin.uri)) {
                plugin.licensed = true;
                plugin.demo = false;
                plugin.coming = false;
                plugin.price = null;
            }

            var metadata = {
                author: plugin.author,
                uri: plugin.uri,
                escaped_uri: escape(plugin.uri),
                thumbnail_href: plugin.thumbnail_href,
                screenshot_href: plugin.screenshot_href,
                category: category || "None",
                installed_version: version(plugin.installedVersion),
                latest_version: version(plugin.latestVersion),
                package_name: (plugin.bundle_name || plugin.bundles[0]).replace(/\.lv2$/, ''),
                comment: plugin.comment.trim() || "No description available",
                brand : plugin.brand,
                name  : plugin.name,
                label : plugin.label,
                ports : plugin.ports,
                plugin_href: PLUGINS_URL + '/' + btoa(plugin.uri),
                pedalboard_href: desktop.getPedalboardHref(plugin.uri, plugin.stable === false),
                shopify_id: plugin.shopify_id,
                price: plugin.price,
                trial: plugin.commercial && !plugin.licensed && status != 'blocked',
                demo  : !!plugin.demo,
                licensed: plugin.licensed,
                coming: plugin.coming,
                build_env_uppercase: plugin.buildEnvironment ? plugin.buildEnvironment.toUpperCase()
                                                             : (plugin.stable === false ? "BETA" : "LOCAL"),
                show_build_env: plugin.buildEnvironment !== "prod",
            };

            var info = self.data('info')

            if (info) {
                info.remove()
                self.data('info', null)
            }
            info = $(Mustache.render(TEMPLATES.cloudplugin_info, metadata))

            // hide control ports table if none available
            if (plugin.ports.control.input.length == 0) {
                info.find('.plugin-controlports').hide()
            }

            // hide cv inputs table if none available
            if (!plugin.ports.cv || (plugin.ports.cv && plugin.ports.cv.input && plugin.ports.cv.input.length == 0)) {
                info.find('.plugin-cvinputs').hide()
            }

            // hide cv ouputs ports table if none available
            if (!plugin.ports.cv || (plugin.ports.cv && plugin.ports.cv.output && plugin.ports.cv.output.length == 0)) {
                info.find('.plugin-cvoutputs').hide()
            }

            var canInstall = false,
                canUpgrade = false

            // The remove button will remove the plugin, close window and re-render the plugins
            // without the removed one
            if (plugin.installedVersion) {
                info.find('.js-install').hide()
                info.find('.js-remove').show().click(function () {
                    // Remove plugin
                    self.data('removePluginBundles')(plugin.bundles, function (resp) {
                        var bundlename = plugin.bundles[0].split('/').filter(function(el){return el.length!=0}).pop(0)
                        self.cloudPluginBox('postInstallAction', [], resp.removed, bundlename)
                        info.window('close')

                        // remove-only action, need to manually update plugins
                        desktop.updatePluginList([], resp.removed)
                    })
                })
            } else {
                canInstall = true
                info.find('.js-remove').hide()
                info.find('.js-installed-version').hide()
                info.find('.js-install').show().click(function () {
                    // Install plugin
                    self.data('installPluginURI')(plugin.uri, function (resp, bundlename) {
                        self.cloudPluginBox('postInstallAction', resp.installed, resp.removed, bundlename)
                        info.window('close')
                    })
                })
            }

            if (plugin.installedVersion && plugin.latestVersion && compareVersions(plugin.latestVersion, plugin.installedVersion) > 0) {
                canUpgrade = true
                info.find('.js-upgrade').show().click(function () {
                    // Upgrade plugin
                    self.data('upgradePluginURI')(plugin.uri, function (resp, bundlename) {
                        self.cloudPluginBox('postInstallAction', resp.installed, resp.removed, bundlename)
                        info.window('close')
                    })
                })
            } else {
                info.find('.js-upgrade').hide()
            }

            if (! plugin.latestVersion) {
                info.find('.js-latest-version').hide()
            }

            info.appendTo($('body'))
            info.window({
                windowName: "Cloud Plugin Info"
            })

            if (metadata.shopify_id && !metadata.licensed) {
                desktop.createBuyButton(metadata.shopify_id)
            }

            info.window('open')
            self.data('info', info)
        }

        // get full plugin info if plugin has a local version
        if ((plugin.bundles && plugin.bundles.length > 0) || ! plugin.installedVersion) {
            localChecked = true
        } else {
            var renderedVersion = [plugin.builder,
                                   plugin.microVersion,
                                   plugin.minorVersion,
                                   plugin.release].join('_');
            $.ajax({
                url: "/effect/get",
                data: {
                    uri: plugin.uri,
                    version: VERSION,
                    plugin_version: renderedVersion,
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
                    plugin.installedVersion = null
                    plugin.installed_version = null
                    localChecked = true
                    showInfo()
                },
                cache: !!plugin.buildEnvironment,
                dataType: 'json'
            })
        }

        // always get cloud plugin info
        $.ajax({
            url: SITEURL + "/lv2/plugins",
            data: {
                uri: plugin.uri,
                image_version: VERSION,
                bin_compat: BIN_COMPAT,
            },
            success: function (pluginData) {
                if (pluginData && pluginData.length > 0) {
                    pluginData = pluginData[0]
                    // delete local specific fields just in case
                    delete pluginData.bundles
                    delete pluginData.installedVersion
                    // ready to merge
                    plugin = $.extend(pluginData, plugin)
                    plugin.latestVersion = [plugin.builder_version || 0, plugin.minorVersion, plugin.microVersion, plugin.release_number]
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
            cache: false,
            dataType: 'json'
        })
    },
})
