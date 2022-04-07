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

    this.installBundleId = function (bundleId, usingLabs, callback) {
        $.ajax({
            url: (usingLabs ? CLOUD_LABS_URL : SITEURL) + '/lv2/bundles/' + bundleId,
            success: function (data) {
                var bincompat, targetfiles = null
                for (var i in data.files) {
                    bin_compat = data.files[i].bin_compat
                    if (bin_compat !== undefined && bin_compat.toUpperCase() == BIN_COMPAT.toUpperCase()) {
                        targetfiles = data.files[i];
                        break;
                    }
                }
                if (targetfiles == null || targetfiles.file_href === undefined) {
                    new Notification('error', "Can't find bundle to install", 5000)
                    if (queue.length == 0) {
                        notification.closeAfter(3000)
                    }
                    callback({ok:false})
                    return
                }
                queue.push({
                    name: data.name,
                    count: data.plugins.length,
                    file: targetfiles.file_href,
                    md5: targetfiles.md5,
                    usingLabs: usingLabs,
                })
                callbacks.push(callback)
                if (queue.length == 1) {
                    self.installNext()
                }
            },
            error: function () {
                new Notification('error', "Download failed", 5000)
                if (queue.length == 0) {
                    notification.closeAfter(3000)
                }
                callback({ok:false})
            },
            cache: false,
            dataType: 'json',
        })
    }

    this.installUsingURI = function (uri, usingLabs, callback) {
        if (queue.length == 0) {
            self.openNotification()
        }

        var downloadFailed = function () {
            new Notification('error', 'Download failed', 5000)
            if (queue.length == 0) {
                notification.closeAfter(3000)
            }
            callback({ok:false})
        }


        if (usingLabs === 'auto') {
            // this condition is triggered when loading a pedalboard for which we are missing plugins.
            // is this case we cannot know where the plugin comes from (prod or labs), so try both.
            $.ajax({
                url: SITEURL + '/lv2/plugins',
                data: {
                    uri: uri,
                    image_version: VERSION,
                },
                success: function (effects) {
                    if (effects.length == 0) {
                        self.installUsingURI(uri, true, callback)
                        return
                    }
                    self.installBundleId(effects[0].bundle_id, false, callback)
                },
                error: downloadFailed,
                cache: false,
                dataType: 'json',
            })
        } else {
            $.ajax({
                url: (usingLabs ? CLOUD_LABS_URL : SITEURL) + '/lv2/plugins',
                data: {
                    uri: uri,
                    image_version: VERSION,
                },
                success: function (effects) {
                    if (effects.length == 0) {
                        new Notification('error', "Can't find plugin to install", 5000)
                        if (queue.length == 0) {
                            notification.closeAfter(3000)
                        }
                        callback({ok:false})
                        return
                    }
                    self.installBundleId(effects[0].bundle_id, usingLabs, callback)
                },
                error: function () {
                    new Notification('error', 'Download failed', 5000)
                    if (queue.length == 0) {
                        notification.closeAfter(3000)
                    }
                    callback({ok:false})
                },
                cache: false,
                dataType: 'json',
            })
        }
    }

    this.installUsingBundle = function (bundleId, usingLabs, callback) {
        if (queue.length == 0) {
            self.openNotification()
        }

        self.installBundleId(bundleId, usingLabs, callback)
    }

    this.installNext = function () {
        var bundle = queue[0]
        var callback = callbacks[0]

        if (desktop.cloudAccessToken == null) {
            desktop.authenticateDevice(function (ok) {
                if (ok && desktop.cloudAccessToken != null) {
                    self.installNext()
                } else {
                    for (var i in callbacks) {
                        callbacks[i]({ok:false})
                    }
                    queue = []
                    callbacks = []
                    notification.close()
                    new Notification('error', "Cannot install plugins, authentication failure", 8000)
                }
            })
            return
        }

        var installationMsg = 'Downloading package ' + bundle.name
        if (bundle.count > 1) {
            installationMsg += ' (contains ' + bundle.count + ' plugins)'
        }
        notification.open()
        notification.html(installationMsg)
        notification.type('warning')
        notification.bar(1)

        var trans = new SimpleTransference(bundle.file, '/effect/install',
                                           { from_args: { headers:
                                           { 'Authorization' : 'MOD ' + desktop.cloudAccessToken }
                                           }})

        trans.reauthorizeDownload = desktop.authenticateDevice;

        trans.reportPercentageStatus = function (percentage) {
            notification.bar(percentage*100)

            if (percentage == 1) {
                installationMsg = installationMsg.replace("Downloading", "Installing")
                notification.html(installationMsg)
            }
        }

        trans.reportError = function (reason) {
            queue = []
            callbacks = []
            notification.close()
            new Notification('error', "Could not install plugin: " + reason, 5000)

            desktop.updateAllPlugins()
        }

        trans.reportFinished = function (resp) {
            var localcallbacks = [callback],
                result = resp.result

            queue.shift()
            callbacks.shift()

            if (result.ok) {
                notification.html(installationMsg + ' - OK!')
                notification.bar(0)
                notification.type('success')
            } else {
                new Notification('error', "Could not install plugin: " + result.error, 5000)
            }

            // check for duplicates
            var duplicated = []
            for (var i in queue) {
                if (JSON.stringify(queue[i]) === JSON.stringify(bundle)) {
                    duplicated.push(i)
                }
            }
            // reverse order so we can pop from queue
            duplicated.reverse()
            for (var i in duplicated) {
                var j = duplicated[i]

                localcallbacks.push(callbacks[j])
                queue.splice(j, 1)
                callbacks.splice(j, 1)
            }

            if (queue.length > 0) {
                self.installNext()
            } else {
                notification.closeAfter(3000)
                desktop.updateAllPlugins()
            }

            // TODO
            //desktop.updatePluginList(result.installed, result.removed)

            for (var i in localcallbacks) {
                localcallbacks[i](result, bundle.name)
            }
        }

        trans.start()
    }
}
