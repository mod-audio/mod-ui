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

function Notification(type, message, timeout) {
    var self = this
    if (type == 'error')
        type = 'danger' //fix for bootstrap
    else if (type == 'warn')
        type = 'warning'

    var delay = 200

    var container = $('#notifications')
    if (container.length == 0)
        container = $('body')


    this.open = function () {
        if (!NOTIFICATIONS_ENABLED)
            return
        if (self.rendered)
            self.rendered.remove()
        self.rendered = $(Mustache.render(TEMPLATES['notification'], {
            type: type,
            message: message
        }))

        container.click(function () {
            self.close()
        })

        self.barValue = $('<div class="progressbar-value">')
        self.rendered.find('.js-progressbar').html('').hide().append(self.barValue)

        container.append(self.rendered).show()

        if (timeout)
            self.closeAfter(timeout)
    }

    this.closeAfter = function (timeout, callback) {
        self.closeTimeout = setTimeout(function () {
            self.close()
            self.closeTimeout = false
        }, timeout)
    }

    this.close = function () {
        if (!self.rendered)
            return
        self.rendered.animate({
                opacity: 0
            }, delay,
            function () {
                self.rendered.remove()
            })
    }

    this.type = function (type) {
        self.rendered.removeClass('info')
        self.rendered.removeClass('warning')
        self.rendered.removeClass('danger')
        self.rendered.removeClass('success')
        self.rendered.addClass(type)
    }

    this.html = function (msg) {
        var container = self.rendered.find('.js-message')
        container.html('')
        self.rendered.find('.js-message').append(msg)
    }

    this.bar = function (value) {
        var bar = self.rendered.find('.js-progressbar')
        bar.show()
        var width = bar.width() * value / 100
        self.barValue.width(width)
    }

    self.open()
}

function Bug(msg) {
    new Notification('error', 'Bug! ' + msg)
        // TODO interface de notificação de bug
}
