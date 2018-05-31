/*
 * In-memory database of all local, cloud and featured plugins.
 * Guidelines:
 * - We load the whole list of plugins only once and keep a full local database
 * - Any kind of filter is done by client
 * - Merge between local and remote versions is done on-demand, we do not keep cache on that
 * - If a new plugin arrives in cloud or is installed by hand in MOD, it won't be available
 *   until whole interface is reloaded
 * - If loading local plugin database fails, that's an unrecoverable error
 * - If loading remote plugin database fails, we mark database as offline and will make a new
 *   attempt every time loading is requested
 * - Once data is loaded, any loading attempt will be ignored
 * - Reloading can be explicitly requested
 * - Everytime new data is loaded, local index is completely rebuilt
 * 
 * These guidelines will keep information consistent through all interface
 */
function PluginDB() {
    var self = this;

    // List of all installed plugins
    this.localPlugins = [];

    // List of all remote plugins, including unstable ones
    this.cloudPlugins = [];

    // List of featured plugins
    this.featuredPlugins = [];

    // List of plugins available for buying
    this.shopifyPlugins = {};

    // Index to find all data related to a plugin (local, cloud, featured)
    this.index = {};

    // License manager will be available once device is online
    this.licenseManager = null;
    
    // Tells what have already been loaded.
    this.localLoaded = false;
    this.cloudLoaded = false;
    this.featuredLoaded = false;
}

PluginDB.prototype.setLicenseManager = function(licenseManager) {
    this.licenseManager = licenseManager;
}

// Private, load local plugins and do not rebuild indexes
PluginDB.prototype._loadLocal = function() {
    var self = this;
    if (self.localLoaded) {
        return new Promise(function(resolve, reject) {
            resolve();
        });
    }
    return new Promise(function(resolve, reject) {
        $.ajax({
            method: 'GET',
            url: '/effect/list',
            success: function (plugins) {
                self.localPlugins = [];
                var i, plugin;
                for (i in plugins) {
                    plugin = plugins[i];
                    plugin.installedVersion = [plugin.builder, plugin.minorVersion, plugin.microVersion, plugin.release];
                    self.localPlugins.push(plugin);
                }
                self.localLoaded = true;
                resolve();
            },
            error: function() {
                new Notification('error', "Can't get list of installed plugins");
                reject();
            },
            cache: false,
            dataType: 'json'
        });
    });
}

// Private, load all remote plugins and do not rebuild index
PluginDB.prototype._loadCloud = function() {
    var self = this;
    if (self.cloudLoaded) {
        return new Promise(function(resolve, reject) {
            resolve();
        });
    }
    return new Promise(function(resolve, reject) {
        $.ajax({
            method: 'GET',
            url: SITEURL + "/lv2/plugins",
            data: {
                summary: "true",
                image_version: VERSION,
            },
            success: function (plugins) {
                self.cloudPlugins = plugins;
                self.cloudLoaded = true;
            },
            error: function () {
                // Let's not do anything, thus preserving any previously
                // loaded data
            },
            complete: resolve,
            cache: false,
            dataType: 'json'
        });
    });
}

PluginDB.prototype._loadShopify = function() {
    var self = this
    return new Promise(function(resolve, reject) {
        var shopClient = ShopifyBuy.buildClient(SHOPIFY_CLIENT_OPTIONS);
        shopClient.fetchAllProducts().then(function(products) {
            self.shopifyPlugins = {};
            for (var i in products) {
                var uri = products[i].selectedVariant.attrs.variant.sku;
                self.shopifyPlugins[uri] = {
                    id: products[i].id,
                    price: products[i].selectedVariant.price
                }
            }
            resolve()
        }, function() {
            if (self.online) {
                new Notification('error', "Our commercial plugin store is offline now, sorry for the inconvenience");
            }
            // We never reject, because this is an acceptable failure in loadAll
            resolve();
        })
    });
}

PluginDB.prototype._loadFeatured = function() {
    var self = this;
    if (self.featuredLoaded) {
        return new Promise(function(resolve, reject) {
            resolve();
        });
    }
    return new Promise(function(resolve, reject) {
        $.ajax({
            method: 'GET',
            url: SITEURL + "/lv2/plugins/featured",
            success: function (featured) {
                self.featuredPlugins = featured;
                self.featuredLoaded = true;
            },
            error: function () {
                // Let's not do anything, thus preserving any previously
                // loaded data
            },
            complete: resolve,
            cache: false,
            dataType: 'json'
        });
    });
}

// Load local plugins and rebuild index
PluginDB.prototype.loadLocal = function() {
    var self = this;
    return new Promise(function(resolve, reject) {
        self._loadLocal().then(function() {
            self._rebuildIndex();
            resolve();
        }, reject);
    });
}

// Load all local and remote plugins and rebuild index
PluginDB.prototype.loadAll = function(callback) {
    var self = this;
    return new Promise(function(resolve, reject) {
        Promise.all([
            self._loadLocal(),
            self._loadCloud(),
            self._loadFeatured(),
            self._loadShopify(),
        ]).then(function() {
            self._rebuildIndex();
            resolve();
        }, reject);
    });
}

PluginDB.prototype._rebuildIndex = function() {
    var self = this;
    this.index = {};
    var i;
    for (i in self.localPlugins) {
        self._index('local', self.localPlugins[i]);
    }
    for (i in self.cloudPlugins) {
        self._index('cloud', self.cloudPlugins[i]);
    }
}

PluginDB.prototype._index = function(location, plugin) {
    if (!this.index[plugin.uri]) {
        this.index[plugin.uri] = {}
    }
    this.index[plugin.uri][location] = plugin;
}

PluginDB.prototype.loadLocalDetail = function(uri) {
    var self = this;
    return new Promise(function(resolve, reject) {
        if (!self.index[uri].local) {
            resolve({});
            return;
        }
        $.ajax({
            url: "/effect/get",
            data: {
                uri: uri
            },
            success: function (pluginData) {
                // delete cloud specific fields just in case
                delete pluginData.bundle_name
                delete pluginData.latestVersion
                resolve(pluginData)
            },
            // We're not handling rejection for now,
            // should never happen
            error: function () {
                resolve({})
            },
            cache: false,
            dataType: 'json'
        })
    });
}

PluginDB.prototype.loadCloudDetail = function(uri) {
    var self = this;
    return new Promise(function(resolve, reject) {
        if (!self.index[uri].cloud) {
            resolve({});
            return;
        }
        $.ajax({
            url: SITEURL + "/lv2/plugins",
            data: {
                uri: uri,
                image_version: VERSION,
            },
            success: function (pluginData) {
                if (pluginData && pluginData.length > 0) {
                    pluginData = pluginData[0]
                    // delete local specific fields just in case
                    delete pluginData.bundles
                    delete pluginData.installedVersion
                    resolve(pluginData);
                } else {
                    resolve({})
                }
            },
            error: function () {
                resolve({});
            },
            cache: false,
            dataType: 'json'
        })
    });    
}

// Merge all information available to be displayed to user
PluginDB.prototype.getPlugin = function(uri, details) {
    var self = this;
    if (!this.index[uri]) {
        // Should never happen
        return {};
    }
    var lplugin = this.index[uri].local;
    var cplugin = this.index[uri].cloud;
    var plugin = cplugin || lplugin;

    var escaped = escape(uri);
    
    // Basic data
    var data = {
        author: plugin.author,
        uri: uri,
        escaped_uri: escaped,
        category: plugin.category[0] || 'None',
        comment: plugin.comment.trim() || "No description available",
        brand : plugin.brand,
        name  : plugin.name,
        label : plugin.label,
        plugin_href: PLUGINS_URL + '/' + btoa(uri),
        pedalboard_href: desktop.getPedalboardHref(uri),
    }

    var installedVersion, latestVersion;

    // Screenshot and installed version
    if (lplugin) {
        data.installedVersion = [lplugin.builder, lplugin.minorVersion, lplugin.microVersion, lplugin.release]
        if (lplugin.gui) {
            var ver = data.installedVersion.join('_')
            data.screenshot_href = '/effect/image/screenshot.png?uri=' + uri + '&v=' + ver;
            data.thumbnail_href  = '/effect/image/thumbnail.png?uri=' + uri + '&v=' + ver;
        } else {
            data.screenshot_href = '/resources/pedals/default-screenshot.png';
            data.thumbnail_href  = '/resources/pedals/default-thumbnail.png';
        }
        data.installed_version = this._version(data.installedVersion);
    }
    else {
        data.screenshot_href = cplugin.screenshot_href || '/resources/pedals/default-screenshot.png';
        data.thumbnail_href = cplugin.thumbnail_href || '/resources/pedals/default-thumbnail.png';
        data.installed_version = null;
    }

    // Latest version
    if (cplugin) {
        data.latestVersion = [parseInt(cplugin.builder_version) || 0, cplugin.minorVersion, cplugin.microVersion, cplugin.release_number]
        data.latest_version = this._version(data.latestVersion)
    } else {
        data.latest_version = null;
    }

    var shopify = this.shopifyPlugins[uri];
    var commercial = false;

    data.licensed = (lplugin && lplugin.licensed) || (this.licenseManager && this.licenseManager.licensed(uri));
    
    if (lplugin && data.licensed && !lplugin.licensed) {
        // Should not happen
        new Notification('warn', 'License for '+cplugin.label+' not downloaded, please reload interface', 4000);
    }

    if (cplugin.mod_license === 'paid_perpetual') {
        if (shopify) {
            data.shopify_id = shopify.id;
            if (!data.licensed) {
                data.price = shopify.price;
            }
        } else {
            // Plugin is commercial but it's not at shopify.
            // Display "trial only" unless there's a local license
            // (a trial only will appear for all plugins not purchased if
            //  shopify is offline)
            data.coming = !lplugin || !lplugin.licensed;
        }
        data.demo = lplugin && !data.licensed;
    }

    data.stable = (cplugin && cplugin.stable) || this.cloudPlugins.length == 0 || !lplugin;

    data.trial = commercial && lplugin && !lplugin.licensed;

    return data;
}

PluginDB.prototype.getPluginDetail = function(uri) {
    var self = this;
    return new Promise(function(resolve, reject) {
        if (!self.index[uri]) {
            // Should never happen
            reject();
            return;
        }
        var cplugin = {}, lplugin = {};
        var localPromise = self.loadLocalDetail(uri).then(function(plugin) {
            $.extend(lplugin, plugin);
        });
        var cloudPromise = self.loadCloudDetail(uri).then(function(plugin) {
            $.extend(cplugin, plugin);
        });
        Promise.all([localPromise, cloudPromise]).then(function() {
            var plugin = self.getPlugin(uri);
            $.extend(cplugin, lplugin);
            $.extend(cplugin, plugin);
            resolve(cplugin);
        });
    });        
}


PluginDB.prototype._version = function(v) {
    if (!v || !v.length)
        return '0.0-0'
    return ""+v[1]+"."+v[2]+"-"+v[3]
}

