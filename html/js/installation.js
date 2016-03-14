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
        notification.html('Installing effect...')
        notification.type('warning')
        notification.bar(0)
    }

    // TODO rename to installURI
    this.install = function (effectURI, callback) {
        if (queue.length == 0) {
            self.openNotification()
        }

        $.ajax({
            url: SITEURL + '/lv2/plugins?uri=' + escape(effectURI),
            success: function (effects) {
                if (effects.length == 0) {
                    new Notification('error', "Can't find effect to install: " + effectURI, 5000)
                    if (queue.length == 0)
                        notification.closeAfter(3000)
                    return
                }
                var effect = effects[0]
                queue.push(effect)
                callbacks.push(callback)
                if (queue.length == 1)
                    self.installNext()
            },
            error: function () {
                new Notification('error', 'Download failed', 5000)
                if (queue.length == 0)
                    notification.closeAfter(3000)
            },
            dataType: 'json',
        })

    }

    this.installEffect = function (effect, callback) {
        queue.push(effect)
        callbacks.push(callback)
        if (queue.length == 1)
            self.installNext()
    }

    this.installNext = function () {
        var effect = queue[0]
        var callback = callbacks[0]
        var finish = function () {
            var status = $('[mod-role=cloud-plugin][mod-plugin-id=' + effect.id + '] .status')
            status.removeClass('installed')
            status.removeClass('outdated')
            status.removeClass('blocked')
            status.addClass('installed')
            queue.shift()
            callbacks.shift()
            if (queue.length > 0) {
                self.installNext()
            } else {
                notification.closeAfter(3000)
                desktop.rescanPlugins()
            }

            $.ajax({
                url: '/effect/get',
                data: {
                    uri: effect.uri
                },
                success: function (plugin) {
                    callback(plugin)
                },
                error: function () {
                    callback(null)
                },
                dataType: 'json'
            })
        }

        var installationMsg = 'Installing package ' + effect.bundle_name + ' (contains ' + effect.name + ')'
        notification.html(installationMsg)
        notification.type('warning')
        notification.bar(1)

        var trans = new SimpleTransference(effect['bundle_file_href']+"duo/", '/effect/install')

        trans.reportStatus = function (status) {
            notification.bar(status.percent)
        }

        trans.reportError = function (reason) {
            queue.shift()
            callbacks.shift()
            notification.close()
            new Notification('error', "Could not install effect: " + reason, 5000)
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
                new Notification('error', "Could not install effect: " + result.error, 5000)
            }
        }

        trans.start()
    }
}
