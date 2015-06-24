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

JqueryClass('upgradeWindow', {
    init: function (options) {
        var self = $(this)

        var icon = options.icon
        var windowManager = options.windowManager
        self.data('icon', icon)
        self.data('windowManager', options.windowManager)
        self.data('uptodate', true)
        self.data('warn', $('<p>'))

        icon.statusTooltip()

        icon.click(function () {
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
            if (!confirm("The MOD software will be upgraded. Any unsaved work will be lost. The upgrade can take several minutes, in which you may not be able to play or do anything else. Continue?"))
                return
            var installer = new Installer({
                repository: PACKAGE_REPOSITORY,
                localServer: PACKAGE_SERVER_ADDRESS,
                reportStatus: function (status) {
                    self.upgradeWindow('reportInstallationStatus', status)
                },
                reportError: function (error) {}
            })
            self.upgradeWindow('downloadStart')
            installer.upgrade(function () {
                self.upgradeWindow('downloadEnd')
            })
        })

        self.upgradeWindow('check')
        self.hide()
    },

    open: function () {
        var self = $(this)
        if (!self.data('uptodate'))
            self.show()
    },

    close: function () {
        $(this).hide()
    },

    check: function (count) {
        var self = $(this)
        var icon = self.data('icon')
        if (count == null)
            count = 0
        if (typeof (Installer) == "undefined" && count < 10) {
            count++;
            setTimeout(function () {
                self.upgradeWindow('check', count)
            }, 1000)
            return
        }
        try {
            var installer = new Installer({
                repository: PACKAGE_REPOSITORY,
                localServer: PACKAGE_SERVER_ADDRESS
            })
        } catch (err) {
            icon.statusTooltip('message', 'Local upgrade server is offline')
            return
        }
        icon.statusTooltip('message', 'Checking for updates...', true)
        installer.checkUpgrade(function (packages) {
            if (packages.length == 0) {
                icon.statusTooltip('message', 'System is up-to-date', true)
                icon.statusTooltip('status', 'uptodate')
                self.data('uptodate', true)
                self.hide()
                return
            }
            icon.statusTooltip('status', 'update-available')
            if (packages.length == 1)
                icon.statusTooltip('message', '1 software update available')
            else
                icon.statusTooltip('message', sprintf('%d software updates available', packages.length))
            var ul = self.find('ul')
            ul.html('')
            var i, pack
            for (i = 0; i < packages.length; i++) {
                pack = packages[i].replace(/^(.+)-([0-9.]+)-(\d+)-[^-]+.tar.xz$/,
                    function (m, pack, version, release) {
                        return pack + ' v' + version + ' rel. ' + release
                    })
                $('<li>').html(pack).appendTo(ul)
            }
            self.data('uptodate', false)
        })
    },

    reportInstallationStatus: function (status) {
        var self = $(this)
        if (status.complete && status.numFile == status.totalFiles) {
            self.find('.download-info').hide()
            self.find('.download-start').hide()
            self.find('.download-installing').show()
            self.upgradeWindow('block')
        } else {
            self.find('.download-info').show()
            self.find('.download-start').hide()
            self.find('.download-installing').hide()
        }
        self.find('.progressbar').width(self.find('.progressbar-wrapper').width() * status.percent / 100)
        self.find('.filename').html(status.currentFile)
        self.find('.file-number').html(status.numFile)
        self.find('.total-files').html(status.totalFiles)
    },

    downloadStart: function () {
        var self = $(this)
        self.find('.mod-upgrade-packages-list').hide()
        self.find('.download-progress').show()
        self.find('.download-info').hide()
        self.find('.download-installing').hide()
        self.find('.installation-checking').hide()
        self.find('.download-start').show()
        self.find('.progressbar').width(0)
    },

    downloadEnd: function () {
        var self = $(this)
        self.find('.download-installing').hide()
        self.find('.installation-checking').show()
        self.data('warn').remove()
        var ping = function () {
            $.ajax({
                url: '/ping',
                success: function (result) {
                    // we must remove the v=CHECKSUM parameter from url, so page can get
                    // a new parameter according to new software checksum.
                    var url = document.location.href.replace(/v=[^&]+&?/, '').replace(/[?&]$/, '')
                    document.location.href = url
                },
                error: function () {
                    setTimeout(ping, 1000)
                },
                dataType: 'json'
            })
        }
        setTimeout(ping, 1000)
    },

    block: function () {
        var self = $(this)
        self.data('windowManager').closeWindows()
        var block = $('<div class="screen-disconnected">')
        var warn = $('<p>').html('Do not turn off<br/>(might brick your MOD)').appendTo(block)
        $('body').append(block).css('overflow', 'hidden')
        block.width($(window).width() * 5)
        block.height($(window).height() * 5)
        block.css('margin-left', -$(window).width() * 2)
        $('#wrapper').css('z-index', -1)
        self.data('warn', warn)
    }
})