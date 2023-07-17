// SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
// SPDX-License-Identifier: AGPL-3.0-or-later

JqueryClass('upgradeWindow', {
    init: function (options) {
        var self = $(this)

        options = $.extend({
            icon: $('<div>'),
            windowManager: $('<div>'),
            startUpgrade: function (callback) {
                callback(true)
            },
            startDeviceUpgrade: function () {},
        }, options)

        self.data(options)
        self.data('updatedata', null)
        self.data('updaterequired', false)
        self.data('updatesystem', false)
        self.data('eggshown', false)

        options.icon.statusTooltip()
        options.icon.statusTooltip('message', 'Checking for updates...', true)

        options.icon.click(function () {
            self.upgradeWindow('open')
        })

        $('body').keydown(function (e) {
            if (e.keyCode == 27)
                self.upgradeWindow('close')
        })

        self.find('.js-close').click(function () {
            self.upgradeWindow('close')
        })

        self.find('button.js-upgrade').click(function () {
            if ($(this).hasClass('disabled')) {
                return
            }
            if ($(this).text() == "Upgrade Now") {
                if (self.data('updatesystem')) {
                    self.upgradeWindow('startUpgrade')
                } else {
                    self.upgradeWindow('startDeviceUpgrade')
                }
            } else {
                self.upgradeWindow('downloadStart')
            }
        })

        self.hide()

        return self
    },

    open: function () {
        var self = $(this)
        var data = self.data('updatedata')

        if (! data) {
            return
        }

        var html

        if (self.data('updatesystem')) {
            html = "Update version <b>" + data['version'].replace("v","") + "</b>.<br/>" +
                   "Released on " + data['release-date'].split('T')[0] + ".";

            if (window.location.host == "192.168.50.1") {
                html += "<br/><br/>" +
                        "Sorry, cannot update via bluetooth.<br/>" +
                        "Please connect the MOD via USB and try again.";
                self.find('button.js-upgrade').addClass('disabled')

            } else if (self.data('updaterequired')) {
                html += "<br/><br/>" +
                        "<b>This update is required!</b>";
            }
        } else {
            html = "One of your connected Control Chain devices is using outdated firmware, please update.<br/>"
                   "Just follow the instructions on <a href='#' target='_blank'>this link</a>.";
        }

        var p = self.find('.mod-upgrade-details').find('p')
        $(p[0]).html(html)

        self.find('a').attr('href', data['release-url'])
        self.find('button.js-upgrade').text("Download")

        self.show()
    },

    close: function () {
        var self = $(this)

        self.hide()

        if (self.data('updatesystem')) {
            setCookie("auto-updated-canceled_" + VERSION, "true", 15)
        } else {
            setCookie("device-update-canceled_" + VERSION, "true", 15)
        }
    },

    setup: function (required, data) {
        var self = $(this)
        var icon = self.data('icon')

        var ignoreUpdate = (getCookie("auto-updated-canceled_" + VERSION, "false") == "true")

        self.data('updatedata', data)
        self.data('updaterequired', false)
        self.data('updatesystem', true)
        icon.statusTooltip('message', "An update is available, click to learn more", ignoreUpdate || required, 8000)
        icon.statusTooltip('status', 'update-available')

        if (required && ! ignoreUpdate) {
            self.upgradeWindow('open')
            new Notification('warn', 'A required update is available.<br/>Please update.', 8000)
        }
    },

    setupDevice: function (data) {
        var self = $(this)

        if (self.data('updatesystem')) {
            return
        }

        var icon = self.data('icon')
        var ignoreUpdate = (getCookie("device-update-canceled_" + VERSION, "false") == "true")

        self.data('updatedata', data)
        self.data('updaterequired', false)
        self.data('updatesystem', false)
        icon.statusTooltip('message', "A device update is available, click to learn more", ignoreUpdate, 8000)
        icon.statusTooltip('status', 'update-available')
    },

    cancelDeviceSetup: function (dev_uri) {
        var self = $(this)

        if (self.data('updatesystem')) {
            return
        }

        var data = self.data('updatedata')
        if (! data) {
            return
        }

        var uri = data['uri']
        if (! uri || uri != dev_uri) {
            return
        }

        self.hide()
        self.upgradeWindow('setUpdated')
    },

    setErrored: function () {
        var self = $(this)
        var icon = self.data('icon')

        icon.statusTooltip('message', "Failed to connect to MOD Cloud", true)
        icon.statusTooltip('status', 'error')
    },

    setUpdated: function () {
        var self = $(this)
        self.data('updatedata', null)

        var icon = self.data('icon')
        icon.statusTooltip('message', "System is up-to-date", true)
        icon.statusTooltip('status', 'uptodate')

        var date = new Date()
        var d = date.getDay(),
            m = date.getMonth();

        if (m == 12 && (d == 24 || d == 25) && ! self.data('eggshown')) {
            self.data('eggshown', true)
            setTimeout(function() {
                new Notification('warn', 'The MOD Team wishes you happy holidays!', 8000)
            }, 5000)
        }
    },

    downloadStart: function () {
        var self = $(this)
        self.find('.mod-upgrade-details').hide()
        self.find('.download-progress').show()
        self.find('.progressbar').width(0)

        self.find('.download-start').show().text("Downloading...")
        self.find('.download-complete').hide()

        var transfer = new SimpleTransference(self.data('updatedata')['download-url'],
                                              self.data('updatesystem') ? '/update/download' : '/controlchain/download')

        transfer.reportPercentageStatus = function (percentage) {
            self.find('.progressbar').width(self.find('.progressbar-wrapper').width() * percentage)

            if (percentage == 1) {
                self.find('.download-start').text("Preparing update... (may take a few minutes)")
            }
        }

        transfer.reportFinished = function (resp) {
            self.find('.mod-upgrade-details').show().find('p:lt(2)').show()
            self.find('.download-progress').hide()
            self.find('button.js-upgrade').text("Upgrade Now")

            self.find('.download-start').hide()
            self.find('.download-complete').show()

            if (self.data('updatesystem')) {
                if (confirm("The MOD will now be updated. Any unsaved work will be lost. "+
                            "The upgrade can take several minutes, "+
                            "in which you may not be able to play or do anything else. Continue?")) {
                    self.upgradeWindow('startUpgrade')
                }
            } else {
                self.upgradeWindow('startDeviceUpgrade')
            }
        }

        transfer.reportError = function (error) {
            self.find('.mod-upgrade-details').show().find('p:lt(2)').hide()
            self.find('button.js-upgrade').text("Retry")

            self.find('.download-start').show().text("Download failed!")
            self.find('.download-complete').hide()
        }

        transfer.start()
    },

    startUpgrade: function () {
        var self = $(this)

        self.data('startUpgrade')(function (ok) {
            if (ok) {
                desktop.blockUI(true)
            } else {
                new Bug("Failed to start upgrade")
            }
        })
    },

    startDeviceUpgrade: function () {
        var self = $(this)
        self.data('startDeviceUpgrade')()
    },
})
