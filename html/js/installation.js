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

var kTargetArchitecture = "duo"

function InstallationQueue() {
    var self = this

    var queue = []
    var callbacks = []
    var results = {}

    var notification

    this.openNotification = function () {
        if (!notification)
            notification = new Notification('warning')
        else
            notification.open()
        notification.html('Downloading bundle...')
        notification.type('warning')
        notification.bar(0)
    }

    this.installBundleId = function (bundleId, callback) {
        $.ajax({
            url: SITEURL + '/lv2/bundles/' + bundleId,
            success: function (data) {
                var targetfiles = null
                for (var i in data.files) {
                    if (data.files[i].arch == kTargetArchitecture) {
                        targetfiles = data.files[i];
                        break;
                    }
                }
                if (targetfiles == null) {
                    new Notification('error', "Can't find bundle to install", 5000)
                    if (queue.length == 0)
                        notification.closeAfter(3000)
                    return
                }
                queue.push({
                    name:  data.name,
                    count: data.plugins.length,
                    file:  targetfiles.file_href,
                    md5:   targetfiles.md5,
                })
                callbacks.push(callback)
                if (queue.length == 1)
                    self.installNext()
            },
            error: function () {
                new Notification('error', "Download failed", 5000)
                if (queue.length == 0)
                    notification.closeAfter(3000)
            },
            dataType: 'json',
        })
    }

    this.installUsingURI = function (uri, callback) {
        if (queue.length == 0) {
            self.openNotification()
        }

        $.ajax({
            url: SITEURL + '/lv2/plugins?uri=' + escape(uri),
            success: function (effects) {
                if (effects.length == 0) {
                    new Notification('error', "Can't find plugin to install", 5000)
                    if (queue.length == 0)
                        notification.closeAfter(3000)
                    return
                }
                self.installBundleId(effects[0].bundle_id, callback)
            },
            error: function () {
                new Notification('error', 'Download failed', 5000)
                if (queue.length == 0)
                    notification.closeAfter(3000)
            },
            dataType: 'json',
        })
    }

    this.installUsingBundle = function (bundleId, callback) {
        if (queue.length == 0) {
            self.openNotification()
        }

        self.installBundleId(bundleId, callback)
    }

    this.installNext = function () {
        var bundle = queue[0]
        var callback = callbacks[0]
        var finish = function () {
            queue.shift()
            callbacks.shift()
            if (queue.length > 0) {
                self.installNext()
            } else {
                notification.closeAfter(3000)
                desktop.rescanPlugins()
                callback()
            }
        }

        var installationMsg = 'Installing package ' + bundle.name
                            + ' (contains ' + bundle.count + ' plugin' + (bundle.count > 1 ? 's)' : ')')
        notification.html(installationMsg)
        notification.type('warning')
        notification.bar(1)

        var trans = new SimpleTransference(bundle.file, '/effect/install',
                                           { from_args: { headers:
                                           { 'Authorization' : 'MOD ' + desktop.cloudAccessToken }
                                           }})

        trans.reportStatus = function (status) {
            notification.bar(status.percent)
        }

        trans.reportError = function (reason) {
            queue.shift()
            callbacks.shift()
            notification.close()
            new Notification('error', "Could not install plugin: " + reason, 5000)
        }

        trans.reportFinished = function (resp) {
            var result = resp.result
            if (result.ok) {
                notification.html(installationMsg + ' - OK!')
                notification.bar(100)
                notification.type('success')
                finish()
            } else {
                queue.shift()
                callbacks.shift()
                notification.close()
                new Notification('error', "Could not install plugin: " + result.error, 5000)
            }
        }

        trans.start()
    }
}
