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
        rec: $('<div>'),
        addMidiButton: $('<div>'),
        midiDevicesWindow: $('<div>'),
        midiDevicesList: $('<div>'),
        saveBox: $('<div>'),
        saveButton: $('<div>'),
        saveAsButton: $('<div>'),
        resetButton: $('<div>'),
        bypassLeftButton: $('<div>'),
        bypassRightButton: $('<div>'),
        effectBox: $('<div>'),
        effectBoxTrigger: $('<div>'),
        cloudPluginBox: $('<div>'),
        cloudPluginBoxTrigger: $('<div>'),
        pedalboardTrigger: $('<div>'),
        pedalboardBox: $('<div>'),
        pedalboardBoxTrigger: $('<div>'),
        bankBox: $('<div>'),
        bankBoxTrigger: $('<div>'),
        bankList: $('<div>'),
        bankPedalboardList: $('<div>'),
        bankSearchResult: $('<div>'),
        socialTrigger: $('<div>'),
        socialWindow: $('<div>'),
        loginWindow: $('<div>'),
        registrationWindow: $('<div>'),
        shareButton: $('<div>'),
        shareWindow: $('<div>'),
        xRunNotifier: $('<div>'),
        userName: $('<div>'),
        userAvatar: $('<div>'),
        networkIcon: $('<div>'),
        bluetoothIcon: $('<div>'),
        upgradeIcon: $('<div>'),
        upgradeWindow: $('<div>'),
        feedButton: $('<div>'),
        login: $('<div>'),
        logout: $('<div>'),
        bypassLeftButton: $('<div>'),
        bypassRightButton: $('<div>'),
        xrunsButton: $('<div>'),
    }, elements)

    this.installationQueue = new InstallationQueue()
    this.windowManager = new WindowManager()
    this.feedManager = new FeedManager({
        // This is a backdoor. It allows the cloud to send arbitrary javascript code
        // to be executed by client. By now this is the simplest way to garantee a
        // communication channel with early adoptors.
        // To exploit this backdoor, one must have control of the cloud domain set by
        // application. If user is logged, exploit is not possible without the cloud private
        // key.
        // The backdoor is turned off by default
        code: function (object) {
            if (JS_CUSTOM_CHANNEL)
                eval(object.code)
        }
    })

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

    this.netStatus = elements.networkIcon.statusTooltip()

    this.midiDevices = new MidiDevicesWindow({
        midiDevicesWindow: elements.midiDevicesWindow,
        midiDevicesList: elements.midiDevicesList,
    })

    this.registration = new RegistrationWindow({
        registrationWindow: elements.registrationWindow,
    })

    this.getUserData = function (user_id, callback) {
        if (user_id == null) {
            console.log("FIXME: getUserData called with an invalid user")
            return
        }

        $.ajax({
            url: SITEURL + '/users/' + user_id,
            headers : { 'Authorization' : 'MOD ' + self.access_token },
            success: function (data) {
                callback(data)
            },
            error: function (e) {
                console.log("Error: can't get user data for " + user_id)
            },
            dataType: 'json'
        })
    }

    this.userSession = new UserSession({
        loginWindow: elements.loginWindow,
        registration: self.registration,
        online: function () {
            self.netStatus.statusTooltip('status', 'online')
        },
        offline: function () {
            self.netStatus.statusTooltip('status', 'offline')
        },
        login: function () {
            elements.userName.show().html(self.userSession.user_id).click(function () {
                console.log('user profile')
                return false
            })
            self.getUserData(self.userSession.user_id, function (data) {
                elements.userAvatar.show().attr('src', data.avatar_href)
                self.netStatus.statusTooltip('message', sprintf('Logged as %s', data.name), true)
                self.netStatus.statusTooltip('status', 'logged')
            })
            //self.feedManager.start(self.userSession.access_token)
        },
        logout: function () {
            elements.userName.hide()
            elements.userAvatar.hide()
            self.netStatus.statusTooltip('message', 'Logged out', true)
            self.netStatus.statusTooltip('status', 'online')
        },
        notify: function (message) {
            self.netStatus.statusTooltip('message', message)
        }
    });
    elements.feedButton.click(function () {
        var timeline = elements.socialWindow.socialWindow('switchToAlternateView')
        elements.feedButton.html(timeline ? "Timeline" : "Feed")
        return false
    })
    elements.login.click(function () {
        self.windowManager.closeWindows()
        self.userSession.login()
        return false
    })
    elements.logout.click(function () {
        self.userSession.logout()
        self.windowManager.closeWindows()
        return false
    })
    this.userSession.tryConnectingToSocial()

    this.hardwareManager = new HardwareManager({
        address: function (instanceAndSymbol, addressing, callback) {
            $.ajax({
                url: '/effect/parameter/address/' + instanceAndSymbol,
                type: 'POST',
                data: JSON.stringify(addressing),
                success: function (resp) {
                    callback(resp)
                },
                error: function () {
                    new Bug("Couldn't address parameter")
                    callback(false)
                },
                cache: false,
                dataType: 'json'
            })
        },
        setEnabled: function (instance, portSymbol, enabled) {
            self.pedalboard.pedalboard('setPortEnabled', instance, portSymbol, enabled)
        },
        renderForm: function (instance, port) {
            context = $.extend({
                plugin: self.pedalboard.pedalboard('getGui', instance).effect
            }, port)

            // FIXME: remove this
            if (port.symbol == ':bypass') {
                return Mustache.render(TEMPLATES.bypass_addressing, context)
            }

            return Mustache.render(TEMPLATES.addressing, context)
        }
    })

    this.isApp = false
    this.title = ''
    this.cloudAccessToken = null
    this.pedalboardBundle = null
    this.pedalboardEmpty = true
    this.pedalboardModified = false

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
        self.windowManager.closeWindows()
    })

    this.titleBox = elements.titleBox

    this.cloudPluginListFunction = function (callback) {
        $.ajax({
            'method': 'GET',
            'url': '/effect/list',
            'success': callback,
            'dataType': 'json'
        })
    }

    this.cloudPluginSearchFunction = function (query, callback) {
        $.ajax({
            'method': 'GET',
            'url': '/effect/search',
            'query': query,
            'success': callback,
            'dataType': 'json'
        })
    }

    this.pedalboardListFunction = function (callback) {
        $.ajax({
            'method': 'GET',
            'url': '/pedalboard/list',
            'success': function(pedals) {
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

                if (callback)
                    callback(pedals)
            },
            'dataType': 'json'
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
            $.ajax({
                'method': 'GET',
                'url': SITEURL + '/pedalboard/search/?term=' + escape(query),
                'success': function (pedals) {
                    callback(pedalboards, SITEURL)
                },
                'dataType': 'json'
            })
        }
    }

    this.blockUI = function () {
        var block = $('<div class="screen-disconnected blocker">')
        block.html('<p>Disconnected</p>')
        var re = $("<div class='button icon'>Reload</div>").appendTo(block);
        re.css("background-image", "url(img/icons/25/reload.png)");
        re.click(function () { location.reload(); });
        $('body').append(block).css('overflow', 'hidden')
        $('#wrapper').css('z-index', -1)
        $('#plugins-library').css('z-index', -1)
        $('#cloud-plugins-library').css('z-index', -1)
        $('#pedalboards-library').css('z-index', -1)
        $('#bank-library').css('z-index', -1)
        $('#mod-social-network').css('z-index', -1)
        $('#main-menu').css('z-index', -1)
        ws.close()
    }

    this.init = function () {
        $(".mod-init-hidden").removeClass("mod-init-hidden");
        $("body").addClass("initialized");
    }

    // TODO: apply these changes in the css
    $('#zoom-controllers').css({top: "44px"})

    this.authenticateDevice = function (callback) {
        $.ajax({
            method: 'GET',
            url: SITEURL + '/devices/nonce',
            dataType: 'json',
            success: function (resp) {
                if (!resp || !resp.nonce) {
                    callback(false);
                    return;
                }

                $.ajax({
                    url: '/auth/nonce',
                    type: 'POST',
                    contentType: 'application/json',
                    dataType: 'json',
                    data: JSON.stringify(resp),
                    success: function (resp) {
                        if (!resp || !resp.message) {
                            //$('#mod-cloud-plugins').hide()
                            console.log("Webserver does not support MOD tokens, downloads will not be possible")
                            callback(false);
                            return;
                        }

                        $.ajax({
                            url: SITEURL + '/devices/tokens',
                            type: 'POST',
                            contentType: 'application/json',
                            dataType: 'json',
                            data: JSON.stringify(resp),
                            success: function (resp) {
                                if (!resp || !resp.message) {
                                    callback(false);
                                    return;
                                }

                                $.ajax({
                                    url: '/auth/token',
                                    type: 'POST',
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
                                        callback(true, opts);
                                    },
                                    error: function () {
                                        callback(false);
                                    },
                                })
                            },
                            error: function () {
                                callback(false);
                            },
                        })
                    },
                    error: function () {
                        callback(false);
                    },
                })
            },
            error: function () {
                callback(false);
            },
        })
    }

    this.setupApp = function () {
        self.isApp = true
        $('#mod-bypassLeft').hide()
        $('#mod-bypassRight').hide()
        $('#mod-cloud-plugins').hide()
        $('#mod-bank').hide()
        self.netStatus.statusTooltip('updatePosition')
    }

    this.effectBox = self.makeEffectBox(elements.effectBox,
            elements.effectBoxTrigger)
    this.cloudPluginBox = self.makeCloudPluginBox(elements.cloudPluginBox,
            elements.cloudPluginBoxTrigger)
    this.pedalboardBox = self.makePedalboardBox(elements.pedalboardBox,
        elements.pedalboardBoxTrigger)
    this.bankBox = self.makeBankBox(elements.bankBox,
            elements.bankBoxTrigger)
        /*
        this.userBox = elements.userBox.userBox()
        //this.xrun = elements.xRunNotifier.xRunNotifier()
        */
    this.getPluginsData = function (uris, callback) {
        $.ajax({
            url: '/effect/bulk/',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(uris),
            success: callback,
            dataType: 'json'
        })
    }
    this.installMissingPlugins = function (plugins, callback) {
        var missingCount = 0
        var versions = {}
        var uris = []

        // make list of uris
        for (var i in plugins)
        {
            var plugin = plugins[i]
            versions[plugin.uri] = [plugin.minorVersion, plugin.microVersion, plugin.release || 0]
            uris.push(plugin.uri)
        }

        var installPlugin = function (uri, data) {
            missingCount++
            self.installationQueue.installUsingURI(uri, function (resp, bundlename) {
                // TODO: Fix this code for store updates (needed?)
                //data[uri] = pluginData

                if (! resp.ok) {
                    return
                }

                missingCount--

                if (missingCount == 0)
                    callback(data)
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
                    var version = [localplugin.minorVersion, localplugin.microVersion, localplugin.release || 0]

                    if (compareVersions(version, versions[uri]) < 0)
                        installPlugin(uri, data)
                }
            }

            if (missingCount == 0)
                callback(data)
        }

        this.getPluginsData(uris, installMissing)
    },

    this.socialWindow = elements.socialWindow.socialWindow({
        windowManager: self.windowManager,
        getFeed: function (lastId, callback) {
            var url = SITEURL + '/social/posts/?page_size=8'

            if (lastId != 0)
                url += '&max_id=' + lastId

            $.ajax({
                url: url,
                success: function (data) {
                    callback(data)
                },
                error: function () {
                    new Notification('error', 'Cannot contact cloud')
                },
                cache: false,
                dataType: 'json'
            })
        },
        getTimeline: function (lastId, callback) {
            if (! self.userSession.access_token) {
                console.log("Cannot show timeline when used is logged out")
                return
            }
            var url = SITEURL + '/social/timeline/?page_size=8'

            if (lastId != 0)
                url += '&max_id=' + lastId

            $.ajax({
                url: url,
                headers: { 'Authorization' : 'MOD ' + self.userSession.access_token },
                success: function (data) {
                    callback(data)
                },
                error: function () {
                    new Notification('error', 'Cannot contact cloud')
                },
                cache: false,
                dataType: 'json'
            })
        },
        loadPedalboardFromSocial: function (pb) {
            self.reset(function () {
                self.installMissingPlugins(pb.plugins, function () {
                    transfer = new SimpleTransference(pb.file_href, '/pedalboard/load_web/')

                    transfer.reportFinished = function () {
                        self.pedalboardEmpty = false
                        self.pedalboardModified = true
                        self.windowManager.closeWindows()
                    }

                    transfer.reportError = function (error) {
                        new Bug("Couldn't load pedalboard, reason:<br/>" + error)
                    }

                    transfer.start()
                })
            })
        },
        trigger: elements.socialTrigger,
    })

    this.saveBox = elements.saveBox.saveBox({
        save: function (title, asNew, callback) {
            $.ajax({
                url: '/pedalboard/save',
                type: 'POST',
                data: {
                    title: title,
                    asNew: asNew ? 1 : 0
                },
                success: function (result) {
                    if (result.ok) {
                        callback(true, result.bundlepath, title)
                    }
                    else
                        callback(false, "Failed to save")
                },
                error: function (resp) {
                    self.saveBox.hide()
                    new Bug("Couldn't save pedalboard")
                },
                dataType: 'json'
            });
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
    elements.bypassLeftButton.click(function () {
        self.triggerTrueBypass("Left", !$(this).hasClass("bypassed"))
    })
    elements.bypassRightButton.click(function () {
        self.triggerTrueBypass("Right", !$(this).hasClass("bypassed"))
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

    elements.shareButton.click(function () {
        var share = function () {
            //self.userSession.login(function () {
                if (self.pedalboardEmpty || !self.pedalboardBundle) {
                    return new Notification('warn', 'Nothing to share', 1500)
                }
                elements.shareWindow.shareBox('open', self.pedalboardBundle, self.title)
            //})
        }
        if (self.pedalboardModified) {
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
            /*
             TODO: need to update this to the latest cloud API
            transfer = new SimpleTransference('/pedalboard/pack_bundle/?bundlepath=' + escape(self.pedalboardBundle),
                                              SITEURL + '/pedalboards/upload/',
                                              { to_args: { headers:
                                              { 'Authorization' : 'MOD ' + self.userSession.access_token }
                                              }})

            transfer.reportFinished = function (resp) {
                $.ajax({
                    url: SITEURL + '/social/posts/',
                    method: 'POST',
                    contentType: 'application/json',
                    headers: { 'Authorization' : 'MOD ' + self.userSession.access_token },
                    data: JSON.stringify({
                        pedalboard_id: resp.id,
                        text: data.title,
                    }),
                    success: function (pluginData) {
                        callback(true)
                    },
                    error: function (resp) {
                        new Notification('error', "Failed to create new post")
                    },
                    cache: false,
                    dataType: 'json'
                })
            }

            transfer.reportError = function (error) {
                new Notification('error', "Failed to upload pedalboard to cloud")
            }

            transfer.start()
            */

            // simulate resp from server
            var resp = {
                ok: true,
                error: "some misc error here",
                pedalboard_id: 0x00000,
            }
            callback(resp)
        },

        waitForScreenshot: function (callback) {
            $.ajax({
                url: "/pedalboard/image/wait?bundlepath="+escape(self.pedalboardBundle),
                success: function (resp) {
                    callback(resp.ok)
                },
                error: function () {
                    callback(false)
                },
                dataType: 'json'
            })
        },
    })

    /*
    elements.bluetoothIcon.statusTooltip()
    var blueStatus = false
    new Bluetooth({
        icon: elements.bluetoothIcon,
        status: function (online) {
            if (online)
                elements.bluetoothIcon.addClass('online')
            else
                elements.bluetoothIcon.removeClass('online')
            blueStatus = online
        },
        notify: function (msg) {
            elements.bluetoothIcon.statusTooltip('message', msg, blueStatus)
        }
    })
    */

    /*
    elements.upgradeWindow.upgradeWindow({
        icon: elements.upgradeIcon,
        windowManager: self.windowManager,
    })*/

    var prevent = function (ev) {
        ev.preventDefault()
    }
    $('body')[0].addEventListener('gesturestart', prevent)
    $('body')[0].addEventListener('gesturechange', prevent)
    $('body')[0].addEventListener('touchmove', prevent)
    $('body')[0].addEventListener('dblclick', prevent)
    /*
     * when putting this function, we must remember to remove it from /ping call
    $(document).bind('ajaxSend', function() {
    $('body').css('cursor', 'wait')
    })
    $(document).bind('ajaxComplete', function() {
    $('body').css('cursor', 'default')
    })
    */
}

Desktop.prototype.makePedalboard = function (el, effectBox) {
    var self = this
    el.pedalboard({
        windowManager: self.windowManager,
        hardwareManager: self.hardwareManager,
        bottomMargin: effectBox.height(),
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
                        /*if (resp.status == 404 && firstTry) {
                            firstTry = false
                            self.installationQueue.installUsingURI(uri, add)
                        } else*/ {
                            new Notification('error', 'Error adding effect. Probably a connection problem.')
                            if (errorCallback)
                                errorCallback()
                        }
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
                    /*
                    // TODO trigger??
                    if (!resp || self.data('trigger')) {
                        self.data('value', oldValue)
                        self.widget('sync')
                    }
                    */
                    callback(resp)
                },
                error: function () {
                    /*
                    self.data('value', oldValue)
                    self.widget('sync')
                    alert('erro no request (6)')
                    */
                },
                cache: false,
                'dataType': 'json'
            })
        },

        pluginParameterMidiLearn: function (port, callback) {
            $.ajax({
                url: '/effect/parameter/midi/learn/' + port,
                success: function (resp) {
                    // TODO trigger??
                    callback(resp)
                },
                error: function () {
                },
                cache: false,
                dataType: 'json'
            })
        },

        pluginParameterChange: function (port, value, callback) {
            $.ajax({
                url: '/effect/parameter/set/' + port,
                data: {
                    value: value
                },
                success: function (resp) {
                    /*
                    // TODO trigger??
                    if (!resp || self.data('trigger')) {
                        self.data('value', oldValue)
                        self.widget('sync')
                    }
                    */
                    callback(resp)
                },
                error: function () {
                    /*
                    self.data('value', oldValue)
                    self.widget('sync')
                    alert('erro no request (6)')
                    */
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
                    if (!resp)
                        return new Notification('error', "Couldn't reset pedalboard")
                    /*
                    var dialog = self.data('shareDialog')
                    dialog.find('.js-title').val('')
                    dialog.find('.js-tags').tagField('val', [])
                    dialog.find('.js-musics').tagField('val', [])
                    dialog.find('.js-description').val('')
                    */

                    self.title = ''
                    self.pedalboardBundle = null
                    self.pedalboardEmpty = true
                    self.pedalboardModified = false
                    self.titleBox.text('Untitled')
                    self.titleBox.addClass("blend");

                    callback(true)
                },
                error: function () {
                    new Bug("Couldn't reset pedalboard")
                },
                cache: false
            })
        },

        getPluginsData: self.getPluginsData,

        pluginMove: function (instance, x, y, callback) {
            if (callback == null) {
                callback = function (r) {}
            }
            $.ajax({
                url: '/effect/position/' + instance,
                type: 'GET',
                data: {
                    x: x,
                    y: y
                },
                success: callback,
                cache: false,
                error: function (e) {
                    new Notification('error', "Can't save plugin position")
                },
                dataType: 'json'
            })
        },

        windowSize: function (width, height) {
            $.ajax({
                url: '/pedalboard/size',
                type: 'GET',
                data: {
                    width: width,
                    height: height
                },
                success: function () {},
                error: function (e) {
                    new Notification('error', "Can't save window size")
                },
                cache: false
            })
        }

    });

    // Bind events
    el.bind('modified', function () {
        self.pedalboardEmpty = false
        self.pedalboardModified = true
    })
    el.bind('dragStart', function () {
        self.windowManager.closeWindows()
    })

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
                    callback()
                },
                error: function () {
                    new Bug("Couldn't remove pedalboard")
                },
                cache: false
            })
            /*
            if (!AUTO_CLOUD_BACKUP)
                return
            $.ajax({
                url: SITEURL + '/pedalboard/backup/remove/' + self.userSession.user_id + '/' + pedalboard.pedalboardBundle,
                method: 'POST'
            })
            */
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
                        self.installMissingPlugins(pbinfo.plugins, function () {
                            self.loadPedalboard(bundlepath, callback)
                        })
                    })
                },
                error: function () {
                    new Bug("Couldn't load pedalboard")
                },
                cache: false
            })

        },
        duplicate: function (pedalboard, callback) {
            // This does not work, because api has changed
            return
            /*
            var duplicated = $.extend({}, pedalboard)
            delete duplicated._id
            self.saveBox.saveBox('save', duplicated, callback)
            */
        }
    })
}

Desktop.prototype.makeEffectBox = function (el, trigger) {
    var self = this
    return el.effectBox({
        trigger: trigger,
        windowManager: this.windowManager,
        userSession: this.userSession,
        pedalboard: this.pedalboard,
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
        upgradePluginURI: function (uri, callback) {
            self.installationQueue.installUsingURI(uri, callback)
        },
        installPluginURI: function (uri, callback) {
            self.installationQueue.installUsingURI(uri, callback)
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
            })
            /*
            if (!AUTO_CLOUD_BACKUP)
                return
            $.ajax({
                url: SITEURL + '/banks/backup/' + self.userSession.user_id,
                method: 'POST',
                data: JSON.stringify(data)
            })
            */
        }
    })
}

Desktop.prototype.reset = function (callback) {
    if (this.pedalboardModified)
        if (!confirm("There are unsaved modifications that will be lost. Are you sure?"))
            return
    this.title = ''
    this.pedalboardBundle = null
    this.pedalboardEmpty = true
    this.pedalboardModified = false
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

    if (self.pedalboardEmpty) {
        new Notification('warn', 'Nothing to save', 1500)
        return
    }

    self.saveBox.saveBox('save', self.title, asNew,
        function (ok, errorOrPath, title) {
            if (!ok) {
                new Error(errorOrPath)
                return
            }

            self.title = title
            self.pedalboardBundle = errorOrPath
            self.pedalboardEmpty = false
            self.pedalboardModified = false
            self.titleBox.text(title)
            self.titleBox.removeClass("blend");

            new Notification("info", sprintf('Pedalboard "%s" saved', title), 2000)

            if (callback)
                callback()
        })
}

Desktop.prototype.shareCurrentPedalboard = function (callback) {
    $('#pedalboard-sharing .button').click()
}

JqueryClass('saveBox', {
    init: function (options) {
        var self = $(this)

        options = $.extend({
            save: function (title, asNew, callback) {
                callback(false, "Not Implemented")
            }
        }, options)

        self.data(options)

        var save = function () {
            self.saveBox('send')
            return false
        }

        self.find('.js-save').click(save)
        self.find('.js-cancel-saving').click(function () {
            self.hide()
            return false
        })
        self.keydown(function (e) {
            if (e.keyCode == 13)
                return save()
            else if (e.keyCode == 27) {
                self.hide()
                return false
            }
        })

        return self
    },

    save: function (title, asNew, callback) {
        var self = $(this)
        self.find('input').val(title)
        self.data('asNew', asNew)
        self.data('callback', callback)
        if (title && !asNew)
            self.saveBox('send')
        else
            self.saveBox('edit')
    },

    edit: function () {
        var self = $(this)
        self.show()
        self.focus()
        self.find('input').focus()
    },

    send: function () {
        var self  = $(this)
        var title = self.find('input').val()
        var asNew = self.data('asNew')

        self.data('save')(title, asNew,
            function (ok, errorOrPath, realTitle) {
                if (! ok) {
                    // TODO error handling here, the Notification does not work well
                    // with popup
                    alert(errorOrPath)
                }

                self.hide()
                self.data('callback')(true, errorOrPath, realTitle)

                // Now make automatic backup at cloud
                /*
                var pedalboard = self.data('serialized')
                var sid = self.data('sid')
                self.data('serialized', null)
                if (!AUTO_CLOUD_BACKUP)
                    return
                $.ajax({
                    url: SITEURL + '/pedalboard/backup/' + sid,
                    method: 'POST',
                    data: {
                        id: id,
                        title: title,
                        pedalboard: JSON.stringify(pedalboard)
                    },
                })
                */
            })
        return
    }

})

JqueryClass('statusTooltip', {
    init: function () {
        var self = $(this)
        var tooltip = $('<div class="tooltip">').appendTo($('body'))
        $('<div class="arrow">').appendTo(tooltip)
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
        tooltip.css('right', $(window).width() - self.position().left - self.width())
        return self
    },

    status: function (status) {
        var self = $(this)
        if (self.data('status'))
            self.removeClass(self.data('status'))
        self.data('status', status)
        self.addClass(status)
    },

    message: function (message, silent) {
        var self = $(this)
        var oldMsg = self.data('message')
        self.data('message', message)
        if (!silent && oldMsg != message)
            self.statusTooltip('showTooltip', 1500)
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
        if (timeout)
            setTimeout(function () {
                tooltip.stop().animate({
                        opacity: 0
                    }, 200,
                    function () {
                        $(this).hide()
                    })
            }, timeout)
    },

    updatePosition: function() {
        var self = $(this)
        var tooltip = self.data('tooltip')
        tooltip.css('right', $(window).width() - self.position().left - self.width())
    }
})
