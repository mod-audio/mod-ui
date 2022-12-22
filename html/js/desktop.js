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

function Desktop(elements) {
    var self = this

    // The elements below are expected to be all defined in HTML and passed as parameter
    elements = $.extend({
        titleBox: $('<div>'),
        zoomIn: $('<div>'),
        zoomOut: $('<div>'),
        addMidiButton: $('<div>'),
        midiPortsWindow: $('<div>'),
        midiPortsList: $('<div>'),
        pedalPresetsWindow: $('<div>'),
        pedalPresetsList: $('<div>'),
        pedalPresetsOverlay: $('<div>'),
        updateDeviceWindow: $('<div>'),
        saveBox: $('<div>'),
        saveButton: $('<div>'),
        saveAsButton: $('<div>'),
        resetButton: $('<div>'),
        cvAddressingButton: $('<div>'),
        snapshotSaveButton: $('<div>'),
        snapshotSaveAsButton: $('<div>'),
        snapshotManageButton: $('<div>'),
        transportButton: $('<div>'),
        transportWindow: $('<div>'),
        transportPlay: $('<div>'),
        transportBPB: $('<div>'),
        transportBPM: $('<div>'),
        transportSyncMode: $('<div>'),
        effectBox: $('<div>'),
        effectBoxTrigger: $('<div>'),
        cloudPluginBox: $('<div>'),
        cloudPluginBoxTrigger: $('<div>'),
        pedalboardTrigger: $('<div>'),
        fileManagerBox: $('<div>'),
        fileManagerBoxTrigger: $('<div>'),
        pedalboardBox: $('<div>'),
        pedalboardBoxTrigger: $('<div>'),
        bankBox: $('<div>'),
        bankBoxTrigger: $('<div>'),
        bankList: $('<div>'),
        bankPedalboardList: $('<div>'),
        bankSearchResult: $('<div>'),
        shareButton: $('<div>'),
        shareWindow: $('<div>'),
        presetSaveBox: $('<div>'),
        devicesIcon: $('<div>'),
        devicesWindow: $('<div>'),
        statusIcon: $('<div>'),
        settingsIcon: $('<div>'),
        upgradeIcon: $('<div>'),
        upgradeWindow: $('<div>'),
        bypassLeftButton: $('<div>'),
        bypassRightButton: $('<div>'),
        bufferSizeButton: $('<div>'),
        xrunsButton: $('<div>'),
        cpuStatsButton: $('<div>'),
    }, elements)

    this.installationQueue = new InstallationQueue()
    this.windowManager = new WindowManager()

    this.pluginIndexer = lunr(function () {
        this.field('data')
        this.ref('id')
        this.requireAllTerms = true
    })

    this.pedalboardIndexer = lunr(function () {
        this.field('data')
        this.ref('id')
        this.requireAllTerms = true
    })

    this.pluginIndexerData = {}
    this.pedalboardIndexerData = {}
    this.previousPedalboardList = null
    this.cvAddressing = false

    this.resetPluginIndexer = function (plugins) {
        self.pluginIndexer = lunr(function () {
            this.field('data')
            this.ref('id')
            this.requireAllTerms = true
        })

        var i, plugin
        for (i in plugins) {
            plugin = plugins[i]
            self.pluginIndexer.add({
                id: plugin.uri,
                data: [plugin.uri, plugin.name, plugin.brand, plugin.comment, plugin.category.join(" ")].join(" "),
            })
        }
        self.pluginIndexerData = plugins
    }

    this.pedalboardStatsSuccess = false;
    this.pedalboardStats = {};
    this.resetPedalboardStats = function() {
        this.pedalboardStatsSuccess = false;
        $.ajax({
            url: SITEURL + '/pedalboards/stats',
            type: 'GET',
            success: function(stats) {
                self.pedalboardStatsSuccess = true;
                self.pedalboardStats = stats;
            },
            cache: false
        })
    };
    this.getPedalboardHref = function(uri) {
        if (!this.pedalboardStatsSuccess) {
            return null;
        }
        var base64Uri = btoa(uri);
        if (!this.pedalboardStats[base64Uri]) {
            return null;
        }
        var encodedUri = encodeURIComponent(uri);
        return PEDALBOARDS_URL + '/?plugin_uri=' + encodedUri;
    };

    this.midiDevices = new MidiPortsWindow({
        midiPortsWindow: elements.midiPortsWindow,
        midiPortsList: elements.midiPortsList,
    })

    this.hardwareManager = new HardwareManager({
        address: function (instanceAndSymbol, addressing, callback) {
            $.ajax({
                url: '/effect/parameter/address/' + instanceAndSymbol,
                type: 'POST',
                data: JSON.stringify(addressing),
                success: function (resp) {
                    if (resp) {
                        self.pedalboardModified = true
                        callback(true)
                    } else {
                        new Bug("Couldn't address parameter, not allowed")
                        callback(false)
                    }
                },
                error: function () {
                    new Bug("Couldn't address parameter, server error")
                    callback(false)
                },
                cache: false,
                dataType: 'json'
            })
        },
        setEnabled: function (instance, portSymbol, enabled, feedback, forceAddress, momentaryMode) {
            if (!enabled && feedback === undefined) {
                console.warn("ERROR setEnabled called as false, but with undefined feedback")
                feedback = true
            }
            if (instance == "/pedalboard") {
                self.transportControls.setControlEnabled(portSymbol, enabled, feedback, forceAddress, momentaryMode)
                return
            }
            self.pedalboard.pedalboard('setPortEnabled', instance, portSymbol, enabled, feedback, forceAddress, momentaryMode)
        },
        renderForm: function (instance, port) {
            var label

            if (instance == "/pedalboard") {
                label = "Pedalboard"
            } else {
                label = self.pedalboard.pedalboard('getLabel', instance)
            }

            if (port.symbol == ':bypass' || port.symbol == ':presets') {
                context = {
                    label: label,
                    name: port.symbol == ':bypass' ? "On/Off" : port.name
                }
                return Mustache.render(TEMPLATES.bypass_addressing, context)
            }

            context = {
                label: label,
                name: port.shortName
            }
            return Mustache.render(TEMPLATES.addressing, context)
        },
        isApp: function() {
            return self.isApp;
        },
    })

    this.pedalPresets = new SnapshotsManager({
        pedalPresetsWindow: elements.pedalPresetsWindow,
        pedalPresetsList: elements.pedalPresetsList,
        pedalPresetsOverlay: elements.pedalPresetsOverlay,
        hardwareManager: self.hardwareManager,
        renamedCallback: function (name) {
            self.titleBox.text((self.title || 'Untitled') + " - " + (name || 'Default'))
        }
    })

    this.isApp = false
    this.title = ''
    this.cloudAccessToken = null
    this.cloudHardwareDeviceVersions = null
    this.pedalboardBundle = null
    this.pedalboardEmpty  = true
    this.pedalboardModified = false
    this.pedalboardPresetId = 0
    this.pedalboardPresetName = ''
    this.pedalboardDemoPluginsNotified = false
    this.loadingPeldaboardForFirstTime = true
    this.licenseManager = null

    this.pedalboard = self.makePedalboard(elements.pedalboard, elements.effectBox)

    elements.zoomIn.click(function () {
        self.pedalboard.pedalboard('zoomIn')
    })
    elements.zoomOut.click(function () {
        self.pedalboard.pedalboard('zoomOut')
    })

    var ajaxFactory = function (url, errorMessage) {
        return function (callback) {
            $.ajax({
                url: url,
                success: callback,
                error: function () {
                    new Error(errorMessage)
                },
                cache: false,
                dataType: 'json'
            })
        }
    }

    elements.pedalboardTrigger.click(function () {
        self.windowManager.closeWindows(null, true)
    })

    this.titleBox = elements.titleBox

    this.ParameterSet = function (paramchange) {
        $.ajax({
            url: '/effect/parameter/set/' ,
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(paramchange),
            success: function (resp) {
                if (!resp) {
                    new Bug("Couldn't address parameter, not allowed")
                }
            },
            error: function () {
                new Bug ("Couldn't address parameter, server error")
            },
            cache: false,
            global: false,
            dataType: 'json'
        })
    }

    this.cloudPluginListFunction = function (callback) {
        $.ajax({
            method: 'GET',
            url: '/effect/list',
            success: callback,
            cache: false,
            dataType: 'json',
        })
    }

    this.cloudPluginSearchFunction = function (query, callback) {
        $.ajax({
            method: 'GET',
            url: '/effect/search',
            query: query,
            success: callback,
            cache: false,
            dataType: 'json'
        })
    }

    this.pedalboardListFunction = function (callback) {
        if (self.previousPedalboardList != null && callback) {
            callback(self.previousPedalboardList)
            return
        }

        $.ajax({
            method: 'GET',
            url: '/pedalboard/list',
            success: function(pedals) {
                var allpedals = {}
                for (var i=0; i<pedals.length; i++) {
                    var pedal = pedals[i]
                    allpedals[pedal.bundle] = pedal
                    self.pedalboardIndexer.add({
                        id: pedal.bundle,
                        data: [pedal.bundle, pedal.title].join(" ")
                    })
                }
                self.pedalboardIndexerData = allpedals
                self.previousPedalboardList = pedals

                if (callback) {
                    callback(pedals)
                }
            },
            cache: false,
            dataType: 'json'
        })
    }
    this.pedalboardSearchFunction = function (local, query, callback) {
        if (local)
        {
            var allpedals = self.pedalboardIndexerData
            var pedals    = []

            ret = self.pedalboardIndexer.search(query)
            for (var i in ret) {
                var uri = ret[i].ref
                pedals.push(allpedals[uri])
            }

            callback(pedals, '')
        }
        else
        {
            // NOTE: this part is never called. pedalboard search is always local
            $.ajax({
                method: 'GET',
                url: SITEURL + '/pedalboard/search/?term=' + escape(query),
                success: function (pedals) {
                    callback(pedalboards, SITEURL)
                },
                cache: false,
                dataType: 'json'
            })
        }
    }

    this.blockUI = function (isUpdating) {
        if ($('body').find('.screen-disconnected').length != 0) {
            return
        }
        var block = $('<div class="screen-disconnected blocker">')

        if (isUpdating) {
            block.html('<p>Auto-update in progress, please wait...</p>')
        } else {
            block.html('<p>Disconnected</p>')
            var re = $("<div class='button icon'>Reload</div>").appendTo(block);
            re.css("background-image", "url(img/icons/25/reload.png)");
            re.click(function () { location.reload(); });
        }

        $('body').append(block).css('overflow', 'hidden')
        $('#wrapper').css('z-index', -1)
        $('#plugins-library').css('z-index', -1)
        $('#cloud-plugins-library').css('z-index', -1)
        $('#pedalboards-library').css('z-index', -1)
        $('#bank-library').css('z-index', -1)
        $('#main-menu').css('z-index', -1)
        ws.close()
    }

    this.init = function () {
        $(".mod-init-hidden").removeClass("mod-init-hidden");
        $("body").addClass("initialized");
    }

    this.authenticateDevice = function (callback) {
        $.ajax({
            method: 'GET',
            url: SITEURL + '/devices/nonce',
            cache: false,
            success: function (resp) {
                if (!resp || !resp.nonce) {
                    callback(false)
                    return
                }
                $.ajax({
                    url: '/auth/nonce',
                    type: 'POST',
                    cache: false,
                    contentType: 'application/json',
                    dataType: 'json',
                    data: JSON.stringify(resp),
                    success: function (resp) {
                        if (!resp || !resp.message) {
                            //$('#mod-cloud-plugins').hide()
                            callback(false)
                            console.log("Webserver does not support MOD tokens, downloads will not be possible")
                            return;
                        }

                        $.ajax({
                            url: SITEURL + '/devices/tokens',
                            type: 'POST',
                            cache: false,
                            contentType: 'application/json',
                            dataType: 'json',
                            data: JSON.stringify(resp),
                            success: function (resp) {
                                if (!resp || !resp.message) {
                                    callback(false)
                                    return;
                                }

                                var license_info = resp.license_info;

                                if (resp['upgrade']) {
                                    $.ajax({
                                        method: 'GET',
                                        url: resp['image-href'],
                                        cache: false,
                                        contentType: 'application/json',
                                        success: function (data) {
                                            elements.upgradeWindow.upgradeWindow('setup', resp['upgrade-required'], data)
                                        },
                                        error: function () {
                                            elements.upgradeWindow.upgradeWindow('setErrored')
                                        },
                                    })
                                } else {
                                    elements.upgradeWindow.upgradeWindow('setUpdated')
                                }

                                $.ajax({
                                    url: '/auth/token',
                                    type: 'POST',
                                    cache: false,
                                    contentType: 'application/json',
                                    dataType: 'json',
                                    data: JSON.stringify(resp),
                                    success: function (resp) {
                                        self.cloudAccessToken = resp.access_token;
                                        var opts = {
                                            from_args: {
                                                headers: { 'Authorization' : 'MOD ' + resp.access_token }
                                            }
                                        }
                                        if (self.licenseManager === null) {
                                            self.licenseManager = new LicenseManager()
                                            self.licenseManager.addLicenses(license_info, function(installed) {
                                                if (installed > 0) {
                                                    var s = installed > 1 ? 's' : ''
                                                    new Notification('info', installed + ' plugin'+s+' licensed')
                                                }
                                            })
                                        }
                                        callback(true, opts);
                                    },
                                    error: function () {
                                        callback(false);
                                    },
                                })
                            },
                            error: function () {
                                callback(false)
                            },
                        })
                    },
                    error: function () {
                        callback(false)
                    },
                })
            },
            error: function () {
                callback(false)
            },
        })
    }

    elements.devicesIcon.statusTooltip()
    this.ccDeviceManager = new ControlChainDeviceManager({
        devicesIcon: elements.devicesIcon,
        devicesWindow: elements.devicesWindow,
        updateInfoWindow: elements.updateDeviceWindow,
        setIconTooltip: function (msg) {
            elements.devicesIcon.statusTooltip('message', msg, true)
        },
        showNotification: function (msg) {
            if (! self.loadingPeldaboardForFirstTime) {
                new Notification('info', msg, 5000)
            }
        },
        cancelDownload: function (callback) {
            $.ajax({
                url: '/controlchain/cancel/',
                type: 'POST',
                success: function () {
                    callback()
                },
                error: function () {
                    callback()
                },
                cache: false,
                dataType: 'json'
            })
        },
    })

    this.ccDeviceAdded = function (dev_uri, label, labelsuffix, version) {
        self.ccDeviceManager.deviceAdded(dev_uri, label+labelsuffix, version)
        self.checkHardwareDeviceVersion(dev_uri, label, version)
    }

    this.ccDeviceRemoved = function (dev_uri, label, version) {
        self.ccDeviceManager.deviceRemoved(dev_uri, label, version)
        elements.upgradeWindow.upgradeWindow('cancelDeviceSetup', dev_uri)
    }

    this.ccDeviceConnected = function (label, version) {
        self.ccDeviceManager.deviceConnected(label, version)
    }

    this.ccDeviceDisconnected = function (label, version) {
        self.ccDeviceManager.deviceDisconnected(label, version)
    }

    this.ccDeviceUpdateFinished = function () {
        elements.upgradeWindow.upgradeWindow('setUpdated')
        elements.upgradeWindow.hide()
        self.ccDeviceManager.hideUpdateWindow()
        new Notification("info", "Control Chain device firmware update complete!")
    }

    this.transportControls = new TransportControls({
        transportButton: elements.transportButton,
        transportWindow: elements.transportWindow,
        transportPlay: elements.transportPlay,
        transportBPB: elements.transportBPB,
        transportBPM: elements.transportBPM,
        transportSyncMode: elements.transportSyncMode,
        openAddressingDialog: function (port, label) {
            self.hardwareManager.open("/pedalboard", port, label)
        },
        setNewBeatsPerMinuteValue: function (bpm) {
          self.hardwareManager.setBeatsPerMinuteValue(bpm)
        },
        removeBPMHardwareMapping: function(syncMode) {
          var instanceAndSymbol = "/pedalboard/:bpm"
          if (self.hardwareManager.removeHardwareMappping(instanceAndSymbol)) {
              var source = syncMode === "link" ? "Ableton Link" : "MIDI"
              new Notification('info', 'BPM addressing removed, incompatible with ' + source + ' sync mode', 8000)
          }
          self.pedalboardModified = true
        },
        setSyncMode: function(syncMode, callback) {
          $.ajax({
              url: '/pedalboard/transport/set_sync_mode/' + syncMode,
              type: 'POST',
              success: function (resp) {
                  if (resp) {
                      callback(true)
                  } else {
                      new Bug("Couldn't set new sync mode")
                      callback(false)
                  }
              },
              error: function () {
                  new Bug("Couldn't set new sync mode, server error")
                  callback(false)
              },
              cache: false,
              dataType: 'json'
          })
        },
        unaddressPort: function (portSymbol, syncMode, callback) {
            var addressing = {
                uri    : kNullAddressURI,
                label  : "",
                minimum: 0,
                maximum: 0,
                value  : 0,
                steps  : 0,
            }
            var instanceAndSymbol = "/pedalboard/" + portSymbol

            $.ajax({
                url: '/effect/parameter/address/' + instanceAndSymbol,
                type: 'POST',
                data: JSON.stringify(addressing),
                success: function (resp) {
                    if (resp) {
                        if (self.hardwareManager.removeHardwareMappping(instanceAndSymbol)) {
                            var source = syncMode === "link" ? "Ableton Link" : "MIDI"
                            new Notification('info', 'BPM addressing removed, incompatible with ' + source + ' sync mode', 8000)
                        }
                        self.pedalboardModified = true
                        callback(true)
                    } else {
                        new Bug("Couldn't address parameter")
                        callback(false)
                    }
                },
                error: function () {
                    new Bug("Couldn't address parameter, server error")
                    callback(false)
                },
                cache: false,
                dataType: 'json'
            })
        },
    })

    this.checkHardwareDeviceVersion = function (dev_uri, label, version) {
        if (self.cloudAccessToken == null) {
            self.authenticateDevice(function (ok) {
                if (ok && self.cloudAccessToken != null) {
                    self.checkHardwareDeviceVersion(dev_uri, label, version)
                } else {
                    console.log("Notice: failed to check device version")
                }
            })
            return
        }

        if (self.cloudHardwareDeviceVersions == null) {
            $.ajax({
                method: 'GET',
                url: CONTROLCHAIN_URL + '/versions',
                success: function (resp) {
                    if (!resp) {
                        console.log("Notice: failed to get latest device version")
                        return
                    }
                    if (resp.api_version != 1) {
                        return
                    }

                    self.cloudHardwareDeviceVersions = resp
                    self.checkHardwareDeviceVersion(dev_uri, label, version)
                },
                error: function (resp) {
                    console.log("Notice: failed to get latest device version")
                },
                cache: false,
                dataType: 'json'
            })
            return
        }

        var devs = self.cloudHardwareDeviceVersions.devices
        if (! devs || Object.keys(devs).length == 0) {
            return
        }
        var dev = devs[dev_uri]
        if (! dev) {
            return
        }

        var majminor = VERSION.split(".").slice(0, 2).join(".")
        var cloudversion = dev[majminor]

        if (! cloudversion) {
            cloudversion = dev["latest"]
            if (! cloudversion) {
                return
            }
        }

        if (compareVersions(version.split("."), cloudversion.split("."), 3) < 0) {
            data = {
                'uri': dev_uri,
                'label': label,
                'download-url': CONTROLCHAIN_URL + "/file/" + label + cloudversion + ".bin",
                'release-url': "http://wiki.moddevices.com/wiki/Control_Chain_Releases#" + label + "," + cloudversion
            }
            elements.upgradeWindow.upgradeWindow('setupDevice', data)
        }
    }

    this.validatePlugins = function (uris, callback) {
        $.ajax({
            url: SITEURL + '/pedalboards/validate/',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                uris: uris,
            }),
            success: function (resp) {
                if (! resp.result) {
                    callback(false)
                    return
                }
                callback(true)
            },
            error: function (resp) {
                new Bug("Couldn't validate pedalboard, error:<br/>" + resp.statusText)
            },
            cache: false,
            dataType: 'json'
        })
    }

    this.saveConfigValue = function (key, value, callback) {
        $.ajax({
            url: '/config/set',
            type: 'POST',
            data: {
                key  : key,
                value: value,
            },
            success: function () {
              if (callback) {
                callback(true)
              }
            },
            error: function () {
              if (callback) {
                callback(false)
              }
            },
            cache: false,
            dataType: 'json'
        })
    }

    this.setupApp = function () {
        self.isApp = true
        $('#mod-bank').hide()
        $('#mod-file-manager').hide()
        $('#mod-settings').hide()
        $('#pedalboards-library').find('a').hide()
    }

    this.effectBox = self.makeEffectBox(elements.effectBox,
                                        elements.effectBoxTrigger)
    this.cloudPluginBox = self.makeCloudPluginBox(elements.cloudPluginBox,
                                                  elements.cloudPluginBoxTrigger)
    this.pedalboardBox = self.makePedalboardBox(elements.pedalboardBox,
                                                elements.pedalboardBoxTrigger)
    this.bankBox = self.makeBankBox(elements.bankBox,
                                    elements.bankBoxTrigger)
    this.fileManagerBox = self.makeFileManagerBox(elements.fileManagerBox,
                                                  elements.fileManagerBoxTrigger)

    this.getPluginsData = function (uris, callback) {
        $.ajax({
            url: '/effect/bulk/',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(uris),
            success: callback,
            cache: false,
            dataType: 'json'
        })
    }
    this.installMissingPlugins = function (plugins, callback) {
        if (self.isApp) {
            new Notification('warn', "Cannot load this pedalboard, some plugins are missing", 4000)
            callback(false)
            return
        }

        var missingCount = 0
        var versions = {}
        var uris = []
        var error = false

        // make list of uris
        for (var i in plugins) {
            var plugin = plugins[i]
            if (uris.indexOf(plugin.uri) < 0) {
                versions[plugin.uri] = [plugin.builder || 0, plugin.minorVersion, plugin.microVersion, plugin.release || 0]
                uris.push(plugin.uri)
            }
        }

        var finalCallback = function () {
            self.previousPedalboardList = null
            if (error && !confirm("Failed to install some required plugins, do you want to load the pedalboard anyway?")) {
                callback(false)
                return
            }
            callback(true)
        }

        var installPlugin = function (uri, data) {
            missingCount++

            self.installationQueue.installUsingURI(uri, 'auto', function (resp, bundlename) {
                if (! resp.ok) {
                    error = true
                }

                missingCount--

                if (missingCount == 0) {
                    finalCallback()
                }
            })
        }

        var installMissing = function (data) {
            for (var i in uris) {
                var uri         = uris[i]
                var localplugin = data[uri]

                if (localplugin == null)
                {
                    installPlugin(uri, data)
                }
                else
                {
                    var version = [localplugin.builder || 0, localplugin.minorVersion, localplugin.microVersion, localplugin.release || 0]

                    if (compareVersions(version, versions[uri]) < 0) {
                        installPlugin(uri, data)
                    }
                }
            }

            if (missingCount == 0) {
                finalCallback()
            }
        }

        this.getPluginsData(uris, installMissing)
    },

    this.loadRemotePedalboard = function (pedalboard_id) {
        self.windowManager.closeWindows(null, true)

        if (self.cloudAccessToken == null) {
            self.authenticateDevice(function (ok) {
                if (ok && self.cloudAccessToken != null) {
                    self.loadRemotePedalboard(pedalboard_id)
                } else {
                    new Notification('error', "Cannot load remote pedalboards, authentication failure")
                }
            })
            return
        }

        $.ajax({
            url: startsWith(pedalboard_id, 'https://') ? pedalboard_id : (SITEURL + '/pedalboards/' + pedalboard_id),
            contentType: 'application/json',
            success: function (resp) {
                if (!resp.data.stable && PREFERENCES['show-labs-plugins'] !== "true") {
                    new Notification('error', 'This pedalboard contains one or more community maintained MOD Labs plugins. To load it, you need to enable MOD Labs plugins in <a href="settings">Settings</a> -> Advanced');
                    return;
                }
                self.reset(function () {
                    self.installMissingPlugins(resp.data.plugins, function (ok) {
                        if (ok) {
                            var transfer = new SimpleTransference(resp.file_href, '/pedalboard/load_web/',
                                                                  { from_args: { headers:
                                                                  { 'Authorization' : 'MOD ' + self.cloudAccessToken }
                                                                  }})

                            transfer.reauthorizeDownload = self.authenticateDevice

                            transfer.reportFinished = function () {
                                self.pedalboardEmpty = false
                                self.pedalboardModified = true
                            }

                            transfer.reportError = function (error) {
                                new Bug("Couldn't load pedalboard, reason:<br/>" + error)
                            }

                            transfer.start()
                        } else {
                            self.pedalboard.data('wait').stop()
                        }
                    })
                })
            },
            error: function (resp) {
                  new Bug("Couldn't get pedalboard info, error:<br/>" + resp.statusText)
            },
            cache: false,
            dataType: 'json'
        })
    },

    this.waitForScreenshot = function (generate, callback) {
        var bundlepath = self.pedalboardBundle
        pending_pedalboard_screenshots.push(bundlepath)

        if (generate) {
            $.ajax({
                url: "/pedalboard/image/generate?bundlepath="+escape(bundlepath),
                success: function (resp) {
                    callback(resp.ok)
                },
                error: function () {
                    callback(false)
                },
                cache: false,
                dataType: 'json'
            })
        } else {
            $.ajax({
                url: "/pedalboard/image/wait?bundlepath="+escape(bundlepath),
                success: function (resp) {
                    callback(resp.ok)
                },
                error: function () {
                    callback(false)
                },
                cache: false,
                dataType: 'json'
            })
        }
    },

    this.saveBox = elements.saveBox.saveBox({
        save: function (windotTitle, name, asNew, callback) {
            $.ajax({
                url: '/pedalboard/save',
                type: 'POST',
                data: {
                    title: name,
                    asNew: asNew ? 1 : 0
                },
                success: function (result) {
                    if (result.ok) {
                        // dummy call to keep 1 ajax request active while screenshot is generated
                        self.waitForScreenshot(false, function(){})
                        // all set
                        callback(true, result.bundlepath, result.title)
                    } else {
                        callback(false, "Failed to save")
                    }
                },
                error: function (resp) {
                    self.saveBox.hide()
                    callback(false, "Couldn't save pedalboard")
                },
                cache: false,
                dataType: 'json'
            });
        }
    })

    this.presetSaveBox = elements.presetSaveBox.saveBox({
        save: function (windotTitle, name, asNew, callback) {
            callback(true, "", name)
        }
    })

    elements.addMidiButton.click(function () {
        self.showMidiDeviceList()
    })
    elements.saveButton.click(function () {
        self.saveCurrentPedalboard(false)
    })
    elements.saveAsButton.click(function () {
        self.saveCurrentPedalboard(true)
    })

    elements.cvAddressingButton.click(function () {
      // Show/hide CV checkboxes
      if ($(this).hasClass('selected')) {
        $('body').find('.output-cv-checkbox').hide()
      } else {
        $('body').find('.output-cv-checkbox').show()
      }
      // Toggle cvAddressing and button state
      self.cvAddressing = !self.cvAddressing
      self.pedalboard.pedalboard('setCvAddressing', self.cvAddressing)
      $(this).toggleClass('selected')
    })
    elements.resetButton.click(function () {
        self.reset(function () {
            $.ajax({
                url: '/pedalboard/load_bundle/',
                type: 'POST',
                data: {
                    bundlepath: DEFAULT_PEDALBOARD,
                    isDefault: '1',
                },
                cache: false,
                dataType: 'json'
            })
        })
    })
    elements.snapshotSaveButton.click(function () {
        if (self.pedalboardPresetId < 0) {
            return new Notification('warn', 'Nothing to save', 1500)
        }

        $.ajax({
            url: '/snapshot/save',
            method: 'POST',
            success: function () {
                self.pedalboardModified = true
                new Notification('info', 'Pedalboard snapshot saved', 2000)
            },
            error: function () {
                new Bug("Failed to save pedalboard snapshot")
            },
            cache: false,
            dataType: 'json',
        })
    })
    elements.snapshotSaveAsButton.click(function () {
        var addressed = !!self.hardwareManager.addressingsByPortSymbol['/pedalboard/:presets']
        if (addressed) {
            return new Notification("warn", "Cannot change snapshot while addressed to hardware", 3000)
        }

        desktop.openPresetSaveWindow("Saving Snapshot", "", function (newName) {
            $.ajax({
                url: '/snapshot/saveas',
                data: {
                    title: newName,
                },
                success: function (resp) {
                    if (! resp.ok) {
                        return
                    }
                    self.pedalboardPresetId = resp.id
                    self.pedalboardPresetName = resp.title
                    self.pedalboardModified = true
                    self.titleBox.text((self.title || 'Untitled') + " - " + resp.title)
                    new Notification('info', 'Pedalboard snapshot saved', 2000)
                },
                error: function () {
                    new Bug("Failed to save pedalboard snapshot")
                },
                cache: false,
                dataType: 'json',
            })
        })
    })
    elements.snapshotManageButton.click(function () {
        var addressed = !!self.hardwareManager.addressingsByPortSymbol['/pedalboard/:presets']
        var feedback = true

        if (addressed) {
            console.log(self.hardwareManager.addressingsData['/pedalboard/:presets'])
            feedback = self.hardwareManager.addressingsData['/pedalboard/:presets'].feedback
        }

        self.pedalPresets.start(self.pedalboardPresetId, addressed, feedback)
    })

    elements.bypassLeftButton.click(function () {
        self.triggerTrueBypass("Left", !$(this).hasClass("bypassed"))
    })
    elements.bypassRightButton.click(function () {
        self.triggerTrueBypass("Right", !$(this).hasClass("bypassed"))
    })
    elements.bufferSizeButton.click(function () {
        var newsize
        if ($(this).text() == "128 frames") {
            newsize = '256'
        } else {
            newsize = '128'
        }

        $.ajax({
            url: '/set_buffersize/' + newsize,
            method: 'POST',
            cache: false,
            success: function (resp) {
                if (! resp.ok) {
                    new Bug("Couldn't set new buffer size")
                }
            },
            error: function () {
                new Bug("Communication failure")
            },
        })
    })
    elements.xrunsButton.click(function () {
        if (cached_xruns == 0) {
            return
        }
        $.ajax({
            url: '/reset_xruns/',
            method: 'POST',
            cache: false,
            success: function (ok) {
                if (ok) {
                    cached_xruns = 0
                    $("#mod-xruns").text("0 Xruns")
                }
            }
        })
    })
    elements.cpuStatsButton.click(function () {
        $.ajax({
            url: '/switch_cpu_freq/',
            method: 'POST',
            cache: false,
            success: function (ok) {
                if (! ok) {
                    new Bug("Couldn't set new cpu frequency")
                }
            },
            error: function () {
                new Bug("Communication failure")
            },
        })
    })

    elements.shareButton.click(function () {
        var share = function () {
            if (self.pedalboardEmpty) {
                return new Notification('warn', 'Nothing to share', 1500)
            }

            var uris = self.pedalboard.pedalboard('getLoadedPluginURIs')

            if (uris.length == 0) {
                return new Notification('warn', 'No plugins loaded, cannot share', 1500)
            }

            self.validatePlugins(uris, function (stable) {
                elements.shareWindow.shareBox('open', self.pedalboardBundle, self.title, stable)
            })
        }

        if (self.pedalboardModified || ! (self.pedalboardEmpty || self.pedalboardBundle)) {
            if (confirm('There are unsaved modifications, pedalboard must first be saved. Save it?')) {
                self.saveCurrentPedalboard(false, share)
            }
        } else {
            share()
        }
    })

    elements.shareWindow.shareBox({
        recordStart: ajaxFactory('/recording/start', "Can't record. Probably a connection problem."),
        recordStop: ajaxFactory('/recording/stop', "Can't stop record. Probably a connection problem. Please try stopping again"),
        playStart: function (startCallback, stopCallback) {
            $.ajax({
                url: '/recording/play/start',
                success: function (resp) {
                    $.ajax({
                        url: '/recording/play/wait',
                        success: stopCallback,
                        error: function () {
                            new Error("Couln't check when sample playing has ended")
                        },
                        cache: false,
                        dataType: 'json'
                    })
                    startCallback(resp)
                },
                error: function () {
                    new Error("Can't play. Probably a connection problem.")
                },
                cache: false,
                dataType: 'json'
            })
        },
        playStop: ajaxFactory('/recording/play/stop', "Can't stop playing. Probably a connection problem. Please try stopping again"),
        recordDownload: ajaxFactory('/recording/download', "Can't download recording. Probably a connection problem."),
        recordReset: ajaxFactory('/recording/reset', "Can't reset your recording. Probably a connection problem."),

        share: function (data, callback) {
            if (! data.reauthorized) {
                // save user data
                $.ajax({
                    url: '/save_user_id/',
                    method: 'POST',
                    data: data,
                    success: function () {},
                    error: function () {},
                    cache: false,
                    global: false,
                    dataType: 'json',
                })
            }

            if (self.cloudAccessToken == null) {
                self.authenticateDevice(function (ok) {
                    if (ok && self.cloudAccessToken != null) {
                        elements.shareWindow.shareBox('share', data, callback)
                    } else {
                        callback({
                            ok: false,
                            error: "authentication failure"
                        })
                    }
                })
                return
            }

            // pack & upload to cloud
            $.ajax({
                url: SITEURL + '/pedalboards/',
                method: 'POST',
                contentType: 'application/json',
                headers: { 'Authorization' : 'MOD ' + self.cloudAccessToken },
                data: JSON.stringify({
                    author     : data.name,
                    email      : data.email,
                    description: data.description,
                    title      : data.title,
                }),
                success: function (resp) {
                    var transfer = new SimpleTransference('/pedalboard/pack_bundle/?bundlepath=' + escape(self.pedalboardBundle),
                                                          resp.upload_href,
                                                          { to_args: { headers:
                                                          { 'Authorization' : 'MOD ' + self.cloudAccessToken }
                                                          }})

                    transfer.reauthorizeUpload = self.authenticateDevice;

                    transfer.reportFinished = function (resp2) {
                        callback({
                            ok: true,
                            id: resp.id,
                        })
                    }

                    transfer.reportError = function (error) {
                        callback({
                            ok: false,
                            error: "Failed to upload pedalboard to cloud (missing screenshot?)",
                        })
                    }

                    transfer.start()
                },
                error: function (resp) {
                    if (resp.status == 401 && ! data.reauthorized) {
                        console.log("Pedalboard share unauthorized, retrying authentication...")
                        data.reauthorized = true
                        self.authenticateDevice(function (ok, options) {
                            if (ok) {
                                console.log("Authentication succeeded")
                                self.options = $.extend(self.options, options)
                                elements.shareWindow.shareBox('share', data, callback)
                            } else {
                                console.log("Authentication failed")
                                callback({
                                    ok: false,
                                    error: resp.statusText
                                })
                            }
                        })
                        return;
                    }

                    callback({
                        ok: false,
                        error: resp.statusText
                    })
                },
                cache: false,
                dataType: 'json'
            })
        },

        waitForScreenshot: self.waitForScreenshot,
    })

    elements.statusIcon.statusTooltip()
    this.networkStatus = new NetworkStatus({
        icon: elements.statusIcon,
        notify: function (msg) {
            elements.statusIcon.statusTooltip('message', msg, true)
        }
    })

    elements.settingsIcon.click(function() {
        document.location.href = '/settings';
    })

    elements.settingsIcon.statusTooltip()
    elements.pedalboardTrigger.statusTooltip()
    elements.pedalboardBoxTrigger.statusTooltip()
    elements.bankBoxTrigger.statusTooltip()
    elements.cloudPluginBoxTrigger.statusTooltip()
    elements.fileManagerBoxTrigger.statusTooltip()

    this.upgradeWindow = elements.upgradeWindow.upgradeWindow({
        icon: elements.upgradeIcon,
        windowManager: self.windowManager,
        startUpgrade: function (callback) {
            $.ajax({
                type: 'POST',
                url: '/update/begin',
                success: function (ok) {
                    callback(ok)
                },
                error: function () {
                    callback(false)
                },
                cache: false,
                dataType: 'json',
            })
        },
        startDeviceUpgrade: function () {
            self.ccDeviceManager.showUpdateWindow()
        },
    })

    var prevent = function (ev) {
        ev.preventDefault()
    }
    $('body')[0].addEventListener('gesturestart', prevent)
    $('body')[0].addEventListener('gesturechange', prevent)
    $('body')[0].addEventListener('touchmove', prevent)
    $('body')[0].addEventListener('dblclick', prevent)
}

Desktop.prototype.makePedalboard = function (el, effectBox) {
    var self = this
    el.pedalboard({
        windowManager: self.windowManager,
        hardwareManager: self.hardwareManager,
        bottomMargin: effectBox.height(),
        cvAddressing: self.cvAddressing,
        pluginLoad: function (uri, instance, x, y, callback, errorCallback) {
            var firstTry = true
            var add = function () {
                $.ajax({
                    url: '/effect/add/' + instance + '?x=' + x + '&y=' + y + '&uri=' + escape(uri),
                    success: function (pluginData) {
                        if (pluginData) {
                            callback(pluginData)
                        } else {
                            new Notification('error', 'Error adding effect')
                            if (errorCallback)
                                errorCallback()
                        }
                    },
                    error: function (resp) {
                        new Notification('error', 'Error adding effect. Probably a connection problem.')
                        if (errorCallback)
                            errorCallback()
                    },
                    cache: false,
                    dataType: 'json'
                })
            }
            add()
        },

        pluginRemove: function (instance, callback) {
            $.ajax({
                url: '/effect/remove/' + instance,
                success: function (resp) {
                    if (resp)
                        callback()
                    else
                        new Notification("error", "Couldn't remove effect")
                },
                cache: false,
                dataType: 'json'
            })
        },

        pluginPresetLoad: function (instance, uri, callback) {
            $.ajax({
                url: '/effect/preset/load/' + instance,
                data: {
                    uri: uri
                },
                success: function (resp) {
                    callback(resp)
                },
                error: function () {
                },
                cache: false,
                dataType: 'json'
            })
        },

        pluginPresetSaveNew: function (instance, name, callback) {
            $.ajax({
                url: '/effect/preset/save_new/' + instance,
                data: {
                    name: name
                },
                success: function (resp) {
                    callback(resp)
                },
                error: function () {
                },
                cache: false,
                dataType: 'json'
            })
        },

        pluginPresetSaveReplace: function (instance, uri, bundlepath, name, callback) {
            $.ajax({
                url: '/effect/preset/save_replace/' + instance,
                data: {
                    uri   : uri,
                    bundle: bundlepath,
                    name  : name
                },
                success: function (resp) {
                    callback(resp)
                },
                error: function () {
                },
                cache: false,
                dataType: 'json'
            })
        },

        pluginPresetDelete: function (instance, uri, bundlepath, callback) {
            $.ajax({
                url: '/effect/preset/delete/' + instance,
                data: {
                    uri   : uri,
                    bundle: bundlepath
                },
                success: function (resp) {
                    callback(resp)
                },
                error: function () {
                },
                cache: false,
                dataType: 'json'
            })
        },

        portConnect: function (fromPort, toPort, callback) {
            var urlParam = fromPort + ',' + toPort
            $.ajax({
                url: '/effect/connect/' + urlParam,
                success: function (resp) {
                    callback(resp)
                    if (!resp) {
                        console.log('erro')
                    }
                },
                cache: false,
                dataType: 'json'
            })
        },

        portDisconnect: function (fromPort, toPort, callback) {
            var urlParam = fromPort + ',' + toPort
            $.ajax({
                url: '/effect/disconnect/' + urlParam,
                success: function () {
                    callback(true)
                },
                cache: false,
                dataType: 'json'
            })
        },

        reset: function (callback) {
            $.ajax({
                url: '/reset',
                success: function (resp) {
                    if (!resp) {
                        return new Notification('error', "Couldn't reset pedalboard")
                    }

                    self.title = ''
                    self.pedalboardBundle = null
                    self.pedalboardEmpty  = true
                    self.pedalboardModified = false
                    self.pedalboardPresetId = 0
                    self.pedalboardPresetName = ''
                    self.pedalboardDemoPluginsNotified = false
                    self.titleBox.text('Untitled')
                    self.titleBox.addClass("blend")
                    self.transportControls.resetControlsEnabled()

                    callback(true)
                },
                error: function () {
                    new Bug("Couldn't reset pedalboard")
                },
                cache: false
            })
        },

        getPluginsData: self.getPluginsData,

        showPluginInfo: function (pluginData) {
            pluginData.installedVersion = [pluginData.builder,
                                           pluginData.minorVersion,
                                           pluginData.microVersion,
                                           pluginData.release]
            self.effectBox.effectBox('showPluginInfo', pluginData)
        },

        pluginParameterChange: function (port, value) {
            self.pedalboardModified = true
            ws.send(sprintf("param_set %s %f", port, value))
        },

        pluginPatchGet: function (instance, uri) {
            ws.send(sprintf("patch_get %s %s", instance, uri))
        },

        pluginPatchSet: function (instance, uri, valuetype, value) {
            self.pedalboardModified = true
            ws.send(sprintf("patch_set %s %s %s %s", instance, uri, valuetype, value))
        },

        pluginMove: function (instance, x, y) {
            self.pedalboardModified = true
            ws.send(sprintf("plugin_pos %s %f %f", instance, x, y))
        },

        windowSize: function (width, height) {
            // FIXME
            if (ws && width > 0 && height > 0) {
                ws.send(sprintf("pb_size %f %f", width, height))
            }
        },

        pedalboardFinishedLoading: function (callback) {
            if (! self.loadingPeldaboardForFirstTime) {
                callback()
                return
            }

            self.loadingPeldaboardForFirstTime = false
            self.effectBox.effectBox('search', function () {
                setTimeout(function () {
                    callback()
                }, 500)
            })
        },

        addCVAddressingPluginPort: function (uri, name, callback) {
            $.ajax({
                url: '/pedalboard/cv_addressing_plugin_port/add',
                type: 'POST',
                data: {
                    uri: uri,
                    name: name,
                },
                success: function (resp) {
                    if (!resp) {
                        return new Notification('error', "Couldn't add CV port")
                    }
                    callback(resp)
                },
                error: function () {
                  new Bug("Couldn't add CV port")
                },
                cache: false,
                dataType: 'json'
            })
        },

        removeCVAddressingPluginPort: function (uri, callback) {
            $.ajax({
                url: '/pedalboard/cv_addressing_plugin_port/remove',
                type: 'POST',
                data: {
                    uri: uri,
                },
                success: function (resp) {
                    if (!resp) {
                        return new Notification('error', "Couldn't remove CV port")
                    }
                    callback(resp)
                },
                error: function () {
                  new Bug("Couldn't remove CV port")
                },
                cache: false,
                dataType: 'json'
            })
        },

        notifyDemoPluginLoaded: function () {
            if (self.pedalboardDemoPluginsNotified) {
                return
            }
            self.pedalboardDemoPluginsNotified = true
            new Notification('warn', 'This pedalboard contains a trial plugin.<br>Using trial plugins will intentionally mute the audio at regular intervals.')
        },
    });

    // Bind events
    el.bind('modified', function () {
        self.pedalboardEmpty = false
        self.pedalboardModified = true
    })
    /*
    el.bind('dragStart', function () {
        self.windowManager.closeWindows(null, true)
    })
    */

    el.bind('pluginDragStart', function () {
        self.effectBox.addClass('fade')
    })
    el.bind('pluginDragStop', function () {
        self.effectBox.removeClass('fade')
    })

    return el
}

Desktop.prototype.makePedalboardBox = function (el, trigger) {
    var self = this
    return el.pedalboardBox({
        trigger: trigger,
        windowManager: this.windowManager,
        list: self.pedalboardListFunction,
        search: self.pedalboardSearchFunction,
        saveConfigValue: self.saveConfigValue,
        remove: function (pedalboard, callback) {
            if (!confirm(sprintf('The pedalboard "%s" will be permanently removed! Confirm?', pedalboard.title)))
                return
            $.ajax({
                url: '/pedalboard/remove/',
                data: {
                    bundlepath: pedalboard.bundle
                },
                success: function () {
                    new Notification("info", sprintf('Pedalboard "%s" removed', pedalboard.title), 1000)
                    self.previousPedalboardList = null
                    callback()
                },
                error: function () {
                    new Bug("Couldn't remove pedalboard")
                },
                cache: false
            })
        },
        load: function (bundlepath, broken, callback) {
            if (!broken) {
                self.loadPedalboard(bundlepath, callback)
                return
            }
            $.ajax({
                url: '/pedalboard/info/',
                data: {
                    bundlepath: bundlepath
                },
                success: function (pbinfo) {
                    self.reset(function () {
                        self.installMissingPlugins(pbinfo.plugins, function (ok) {
                            if (ok) {
                                self.loadPedalboard(bundlepath, callback)
                            } else {
                                self.pedalboard.data('wait').stop()
                            }
                        })
                    })
                },
                error: function () {
                    new Bug("Couldn't load pedalboard")
                },
                cache: false
            })
        },
    })
}

Desktop.prototype.makeEffectBox = function (el, trigger) {
    var self = this
    return el.effectBox({
        trigger: trigger,
        windowManager: this.windowManager,
        pedalboard: this.pedalboard,
        saveConfigValue: this.saveConfigValue,
    })
}

Desktop.prototype.makeCloudPluginBox = function (el, trigger) {
    var self = this
    return el.cloudPluginBox({
        trigger: trigger,
        windowManager: this.windowManager,
        list: self.cloudPluginListFunction,
        removePluginBundles: function (bundles, callback) {
            if (!confirm('You are about to remove this plugin and any other in the same bundle. This may break pedalboards that depend on them.'))
                return
            self.previousPedalboardList = null
            $.ajax({
                url: '/package/uninstall',
                data: JSON.stringify(bundles),
                method: 'POST',
                success: function(resp) {
                    if (resp.ok) {
                        callback(resp)
                    } else {
                        new Notification('error', "Could not uninstall bundle: " + resp.error)
                    }
                },
                error: function () {
                    new Notification('error', "Failed to uninstall plugin")
                },
                cache: false,
                dataType: 'json'
            })
        },
        upgradePluginURI: function (uri, usingLabs, callback) {
            self.previousPedalboardList = null
            self.installationQueue.installUsingURI(uri, usingLabs, callback)
        },
        installPluginURI: function (uri, usingLabs, callback) {
            self.previousPedalboardList = null
            self.installationQueue.installUsingURI(uri, usingLabs, callback)
        }
    })
}

Desktop.prototype.makeBankBox = function (el, trigger) {
    var self = this
    el.bankBox({
        trigger: trigger,
        windowManager: this.windowManager,
        list: self.pedalboardListFunction,
        search: self.pedalboardSearchFunction,
        load: function (callback) {
            $.ajax({
                url: '/banks',
                success: callback,
                error: function () {
                    new Bug("Couldn't load banks")
                },
                cache: false,
                dataType: 'json',
            })
        },
        save: function (data, callback) {
            $.ajax({
                type: 'POST',
                url: '/banks/save',
                data: JSON.stringify(data),
                success: callback,
                error: function () {
                    new Bug("Couldn't save banks")
                },
                cache: false,
            })
        },
        copyFactoryPedalboard: function (bundlepath, title, callback) {
            $.ajax({
                url: '/pedalboard/factorycopy/',
                data: {
                    bundlepath: bundlepath,
                    title: title,
                },
                success: function (resp) {
                    if (resp) {
                        self.previousPedalboardList = null
                        new Notification('warning', 'Factory pedalboard was copied to user pedalboards')
                        callback(resp)
                    } else {
                        new Bug("Could not copy factory pedalboard")
                    }
                },
                error: function () {
                    new Bug("Failed to copy factory pedalboard")
                },
                cache: false
            })
        },
    })
}

Desktop.prototype.makeFileManagerBox = function (el, trigger) {
    var self = this
    el.fileManagerBox({
        trigger: trigger,
        windowManager: this.windowManager,
    })
}

Desktop.prototype.reset = function (callback) {
    if (this.pedalboardModified && !confirm("There are unsaved modifications that will be lost. Are you sure?")) {
        return
    }

    this.pedalboard.data('wait').start('Loading pedalboard...')
    this.pedalboard.pedalboard('reset', callback)
}

Desktop.prototype.updateAllPlugins = function () {
    this.effectBox.effectBox('search')
}

Desktop.prototype.updatePluginList = function (added, removed) {
    // TODO
    console.log("ADDED:", added)
    console.log("REMOVED:", removed)
    for (var i in added) {
        var uri = added[i]
    }
    for (var i in removed) {
        var uri = removed[i]
    }
    this.effectBox.effectBox('search')
}

Desktop.prototype.showMidiDeviceList = function () {
    this.midiDevices.start()
}

Desktop.prototype.triggerTrueBypass = function (channelName, bypassed) {
    var self = this;
    $.ajax({
        url: '/truebypass/' + channelName + '/' + (bypassed ? "true" : "false"),
        cache: false,
        dataType: 'json',
        success: function (ok) {
            if (ok) {
                self.setTrueBypassButton(channelName, bypassed);
            }
        }
    })
}

Desktop.prototype.setTrueBypassButton = function (channelName, state) {
    if (typeof state === "string") state = eval(state);
    var b = $("#mod-bypass" + channelName);
    b[(state ? "add" : "remove") + "Class"]("bypassed");
}

Desktop.prototype.loadPedalboard = function (bundlepath, callback) {
    var self = this

    self.reset(function () {
        $.ajax({
            url: '/pedalboard/load_bundle/',
            type: 'POST',
            data: {
                bundlepath: bundlepath
            },
            success: function (resp) {
                if (! resp.ok) {
                    callback(false)
                    return
                }
                self.title = resp.name
                self.pedalboardBundle = bundlepath
                self.pedalboardEmpty = false
                self.pedalboardModified = false
                self.pedalboardDemoPluginsNotified = false
                self.titleBox.text(resp.name);
                self.titleBox.removeClass("blend");

                callback(true)
            },
            error: function () {
                new Bug("Couldn't load pedalboard")
            },
            cache: false,
            dataType: 'json'
        })
    })
}

Desktop.prototype.saveCurrentPedalboard = function (asNew, callback) {
    var self = this

    if (self.pedalboardEmpty && ! self.pedalboardModified) {
        new Notification('warn', 'Nothing to save', 1500)
        return
    }

    self.saveBox.saveBox('save', "", self.title, asNew,
        function (ok, errorOrPath, title) {
            if (!ok) {
                new Error(errorOrPath)
                return
            }

            if (asNew || ! self.title) {
                self.titleBox.removeClass("blend");
                self.previousPedalboardList = null
            }

            self.title = title
            self.pedalboardBundle = errorOrPath
            self.pedalboardEmpty = false
            self.pedalboardModified = false
            self.titleBox.text(title + " - " + self.pedalboardPresetName)

            if (self.previousPedalboardList != null) {
                for (var i=0; i<self.previousPedalboardList.length; i++) {
                    var pedal = self.previousPedalboardList[i]
                    if (pedal.bundle == self.pedalboardBundle) {
                        pedal.version += 1
                        break
                    }
                }
            }

            new Notification("info", sprintf('Pedalboard "%s" saved', title), 2000)

            if (callback)
                callback()
        })
}

Desktop.prototype.shareCurrentPedalboard = function (callback) {
    $('#pedalboard-sharing .button').click()
}

Desktop.prototype.openPresetSaveWindow = function (windowTitle, name, callback) {
    this.presetSaveBox.saveBox('save', windowTitle, name, true,
        function (ok, ignored, newName) {
            callback(newName)
        })
}

Desktop.prototype.getDeviceShopToken = function(callback) {
    var self = this;

    var getToken = function() {
        $.ajax({
            url: SITEURL + '/licenses/requests/',
            cache: false,
            method: 'GET',
            headers: {
                'Authorization' : 'MOD ' + self.cloudAccessToken
            },
            success: function(result) {
                callback(result.id);
            },
            error: function(result) {
                new Notification('error', "Cannot get transaction authorization from Cloud, please contact support", 10000);
            }
        });
    }

    if (self.cloudAccessToken == null) {
        desktop.authenticateDevice(function (ok) {
            if (ok && self.cloudAccessToken != null) {
                getToken()
            } else {
                new Notification('error', "Can't authenticate with Cloud to access plugin store", 5000)
            }
        })
    } else {
        getToken();
    }
}
// TODO cache
Desktop.prototype.fetchShopProducts = function() {
    var self = this
    return new Promise(function(resolve, reject) {
        var shopClient = ShopifyBuy.buildClient(SHOPIFY_CLIENT_OPTIONS);
        shopClient.fetchAllProducts().then(function(products) {
            if (products.length > 0) {
                self.createCart(shopClient)
            }
            resolve(products)
        }, reject)
    })
}

Desktop.prototype.fetchShopProduct = function(uri) {
    var self = this
    var shopClient = ShopifyBuy.buildClient(SHOPIFY_CLIENT_OPTIONS);
    // TODO would be more efficient to query one single product,
    // but don't know how to query by variant's SKU
    return shopClient.fetchAllProducts().then(function(products) {
        for (var i in products) {
            if (uri == products[i].selectedVariant.attrs.variant.sku) {
                self.createCart(shopClient)
                return products[i]
            }
        }
    })
}

Desktop.prototype.createCart = function(shopClient) {
    var self = this
    ShopifyBuy.UI.onReady(shopClient).then(function (ui) {
        ui.createComponent('cart', {
            moneyFormat: '%E2%82%AC%7B%7Bamount%7D%7D',
            options: SHOPIFY_PRODUCT_OPTIONS
        }).then(function(cart) {
            self.cart = cart;
        })
        self.windowManager.registerShopify(ui);
    })
}

Desktop.prototype.createBuyButton = function(shopifyId) {
    var shopClient = ShopifyBuy.buildClient(SHOPIFY_CLIENT_OPTIONS);
    ShopifyBuy.UI.onReady(shopClient).then(function (ui) {
        var node = document.getElementById('product-component-'+shopifyId);
        var button = $('<div class="shopify-fake-button">ADD TO CART</div>').appendTo(node);
        ui.createComponent('product', {
            id: [shopifyId],
            node: node,
            moneyFormat: '%E2%82%AC%7B%7Bamount%7D%7D',
            options: SHOPIFY_PRODUCT_OPTIONS
        });
    });
}

Desktop.prototype.waitForLicenses = function(deviceToken) {
    var self = this;
    var poll = function() {
        $.ajax({
            url: SITEURL + '/licenses/requests/'+deviceToken,
            method: 'GET',
            headers: {
                'Authorization' : 'MOD ' + self.cloudAccessToken
            },
            success: function(result) {
                if (self.licenseManager === null || !result.fulfilled) {
                    setTimeout(poll, 5000);
                    return;
                }
                self.licenseManager.addLicenses(result.license_info, function() {
                    var s = result.license_info.length > 1 ? 's' : ''
                    var msg = result.license_info.length + ' new plugin'+s+' purchased'
                    new Notification('info', msg);
                    var uris = result.license_info.map(function(l) { return l.plugin_uri });
                    if (self.cart) {
                        self.cart.empty()
                        self.cart.close()
                    }
                })
            },
            error: function() {
                new Notification('error', "Can't get licenses from Cloud, please reload interface after finishing your purchase");
            }
        });
    }
    setTimeout(poll, 5000);
}

Desktop.prototype.license = function(uri) {
    var container = $('[mod-uri="'+escape(uri)+'"]')
    container.find('.price').removeClass('price').addClass('licensed').html('')
    container.find('.description-price').removeClass('description-price').addClass('description-licensed').html('')
    container.find('.demo-mask').remove()
    container.find('.buy-button').remove()
    container.find('button').each(function(index, button) {
        $(button).html($(button).html().replace(/\s+Trial/, ''))
    });

    this.pedalboard.pedalboard('license', uri)
}

JqueryClass('saveBox', {
    init: function (options) {
        var self = $(this)

        options = $.extend({
            save: function (windowTitle, name, asNew, callback) {
                callback(false, "Not Implemented")
            }
        }, options)

        self.data(options)
        self.data('disabled', false)

        var save = function () {
            self.saveBox('send')
            return false
        }

        self.find('.js-save').click(save).prop('disabled',true)
        self.find('.js-cancel-saving').click(function () {
            if (self.data('disabled')) {
                return false
            }
            self.hide()
            return false
        })
        self.find('input').keyup(function () {
            self.find('.js-save').prop('disabled', this.value.length == 0 ? true : false);
        })
        self.keydown(function (e) {
            if (self.data('disabled')) {
                return false
            }
            if (e.keyCode == 13) {
                return save()
            }
            if (e.keyCode == 27) {
                self.hide()
                return false
            }
        })

        return self
    },

    save: function (windowTitle, name, asNew, callback) {
        var self = $(this)
        self.find('input').val(name)
        self.data('asNew', asNew)
        self.data('callback', callback)
        if (windowTitle) {
            self.find('h1').text(windowTitle)
        }
        if (name && !asNew) {
            self.saveBox('send')
        } else {
            self.saveBox('edit')
        }
    },

    edit: function () {
        var self = $(this)
        self.find('.js-save').prop('disabled', self.find('input').val().length == 0 ? true : false);
        self.show()
        self.focus()
        self.find('input').focus()
    },

    send: function () {
        var self  = $(this)
        var title = self.find('input').val()
        var asNew = self.data('asNew')

        if (title.length == 0) {
            new Bug("Cannot save with an empty name!")
            return
        }

        self.data('disabled', true)
        self.find('.js-cancel-saving').prop('disabled', true)
        self.find('.js-save').prop('disabled', true)
        self.data('save')("", title, asNew,
            function (ok, errorOrPath, realTitle) {
                if (! ok) {
                    new Bug(errorOrPath)
                }

                self.hide()
                self.data('disabled', false)
                self.find('.js-cancel-saving').prop('disabled', false)
                self.find('.js-save').prop('disabled', false)
                self.data('callback')(true, errorOrPath, realTitle)
            })
        return
    }

})

JqueryClass('statusTooltip', {
    init: function () {
        var self = $(this)
        var tooltip = $('<div class="tooltip">').appendTo($('body'))
        tooltip.data('arrow', $('<div class="arrow">').appendTo(tooltip))
        $('<div class="text">').appendTo(tooltip)
        tooltip.hide()
        self.data('tooltip', tooltip)
        self.bind('mouseover', function () {
            self.statusTooltip('showTooltip')
        })
        self.bind('mouseout', function () {
            tooltip.stop().animate({
                    opacity: 0
                }, 200,
                function () {
                    $(this).hide()
                })
        })

        // Special case for bottom left mod-plugins icon
        // arrow should be on the left, not on the right
        if (self.attr('id') === "mod-plugins") {
          var arrow = tooltip.data('arrow');
          arrow.css('left', 14);
        }

        return self
    },

    status: function (status) {
        var self = $(this)
        if (self.data('status'))
            self.removeClass(self.data('status'))
        self.data('status', status)
        self.addClass(status)
    },

    message: function (message, silent, timeout) {
        var self = $(this)
        var oldMsg = self.data('message')
        self.data('message', message)
        if (!silent && oldMsg != message)
            self.statusTooltip('showTooltip', timeout || 1500)
    },

    showTooltip: function (timeout) {
        var self = $(this)
        var msg = self.data('message')
        if (!msg)
            return
        var tooltip = self.data('tooltip')
        tooltip.find('.text').html(self.data('message'))
        tooltip.show().stop().animate({
            opacity: 1
        }, 200)

        // Adjust tooltip position in case window has been resized
        self.statusTooltip('updatePosition')

        if (timeout) {
            setTimeout(function () {
                tooltip.stop().animate({
                        opacity: 0
                    }, 200,
                    function () {
                        $(this).hide()
                    })
            }, timeout)
        }
    },

    updatePosition: function() {
        var self = $(this)
        var tooltip = self.data('tooltip')
        tooltip.css('right', $(window).width() - self.position().left - self.width())

        // Special case for bottom left mod-plugins icon
        if (self.attr('id') === "mod-plugins") {
            tooltip.css('right', $(window).width() - self.position().left - self.width() + tooltip.position().left);
        }
    }
})

function enable_dev_mode(skipSaveConfig) {
    // install/update all plugins
    $('#cloud_install_all').show()
    $('#cloud_update_all').show()

    // network and controller ping times
    $('#mod-status').show().statusTooltip('updatePosition')

    // adjust position
    $('#mod-devices').statusTooltip('updatePosition')
    $('#mod-settings').statusTooltip('updatePosition')

    // xrun counter
    $('#mod-xruns').show()

    // buffer size button
    $('#mod-buffersize').show()

    // CPU speed and temperature, not available on the Duo
    if (PLATFORM != "duo") {
        $('#mod-cpu-stats').show()
    }

    // transport parameters
    $('#mod-transport-window').css({
        right: '592px'
    })

    if (!skipSaveConfig) {
        // save settings
        desktop.saveConfigValue("dev-mode", "on")
    }

    // echo to you
    return "Dev mode enabled!"
}

function disable_dev_mode() {
    // install/update all plugins
    $('#cloud_install_all').hide()
    $('#cloud_update_all').hide()

    // network and controller ping times
    $('#mod-status').hide()

    // adjust position
    $('#mod-devices').statusTooltip('updatePosition')
    $('#mod-settings').statusTooltip('updatePosition')

    // xrun counter
    $('#mod-xruns').hide()

    // buffer size button
    $('#mod-buffersize').hide()

    // CPU speed and temperature
    $('#mod-cpu-stats').hide()

    // transport parameters
    $('#mod-transport-window').css({
        right: '310px'
    })

    // save settings
    desktop.saveConfigValue("dev-mode", "off")

    // echo to you
    return "Dev mode disabled!"
}
