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

JqueryClass('socialWindow', {
    init: function (options) {
        var self = $(this)

        options = $.extend({
            feed: true,
            getFeed: function (lastId, callback) {
                callback([])
            },
            getTimeline: function (lastId, callback) {
                callback([])
            },
            loadPedalboard: function (pedalboard) {},
            trigger: $('<div>')
        }, options)

        self.data(options)
        self.window($.extend({
            open: function () {
                self.data('lastId', 0)
                self.socialWindow('showFeed', 0)
            },
        }, options))

        self.find('button').click(function () {
            self.socialWindow('nextFeedPage')
        })

        return self
    },

    switchToFeed: function () {
        seld.data('feed', true)
        self.data('lastId', 0)
        self.socialWindow('showFeed', 0)
    },

    switchToTimeline: function () {
        seld.data('feed', false)
        self.data('lastId', 0)
        self.socialWindow('showFeed', 0)
    },

    showFeed: function (lastId) {
        var self = $(this)
        self.data(self.data('feed') ? 'getFeed' : 'getTimeline')(lastId, function (data) {
            var canvas = self.find('#social-main')

            // remove existing contents
            if (lastId == 0)
            {
                canvas.find('li.feed').remove()
                self.find('li.more').show()
            }

            self.socialWindow('renderFeed', data, canvas)

            canvas.find('li.more').appendTo(canvas) // always last item
            self.find('button').show()
        })
    },

    nextFeedPage: function () {
        var self   = $(this)
        var lastId = self.data('lastId')
        self.socialWindow('showFeed', lastId)
    },

    renderFeed: function (data, canvas) {
        var self = $(this)

        if (data.length < 8) // page size used in desktop.js
            self.find('li.more').hide()

        var pbLoad = function (pb_url) {
            return function () {
                self.data('loadPedalboard')(pb_url)
            }
        }

        function renderNextPost(data) {
            if (data.length == 0)
                return

            var sdata = data.pop()
            //sdata.created = renderTime(new Date(sdata.created))
            //console.log(sdata)

            var context = {
                avatar_href: sdata.user.avatar_href,
                user_name  : sdata.user.name,
                text       : sdata.text,
            }

            if (sdata.pedalboard) {
                context.pedalboard = {
                    id       : sdata.pedalboard.id,
                    name     : sdata.pedalboard.name,
                    thumbnail: sdata.pedalboard.thumbnail_href,
                    plugins  : [],
                }

                for (var i in sdata.pedalboard.plugins) {
                    var plug = sdata.pedalboard.plugins[i]
                    context.pedalboard.plugins.push({
                        name     : plug.name || "Unknown",
                        thumbnail: plug.thumbnail_href || "/resources/pedals/default-thumbnail.png",
                    })
                }
            }

            var content = $(Mustache.render(TEMPLATES.cloud_feed, context))

            if (sdata.pedalboard) {
                content.find('.js-pedalboard-' + sdata.pedalboard.id).click(pbLoad(sdata.pedalboard.file_href))
            }

            content.appendTo(canvas)

            if (data.length == 0)
            {
                self.data('lastId', sdata.id)
                return
            }

            renderNextPost(data)
        }

        renderNextPost(data.reverse())
    },

    showSearch: function () {},
})
