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
            userSession: null, //must be passed
            getFeed: function (page, lastId, callback) {
                callback([])
            },
            loadPedalboard: function (pedalboard) {},
            trigger: $('<div>')
        }, options)

        self.data(options)
        self.window($.extend({
            open: function () {
                self.data('page', 0)
                self.socialWindow('showFeed', 0)
            }
        }, options))

        self.find('button').click(function () {
            self.socialWindow('nextPage')
        })

        /*
	self.find('#cloud-feed').click(function() {
	    self.socialWindow('renderFeed')
	})
	self.find('#cloud-pedalboards').click(function() {
	    self.socialWindow('showSearch')
	})
	*/
        return self
    },

    showFeed: function (page, lastId) {
        var self = $(this)
        self.data('getFeed')(page, lastId, function (data) {
            var canvas = self.find('#social-main')
            //if (page == 0)
            //    canvas.find('li.feed').remove()
            /*var content =*/ self.socialWindow('renderFeed', data, canvas)
            //canvas.find('li.more').appendTo(canvas) // always last item
            //self.find('button').show()
            self.window('open')
        })
    },

    nextPage: function () {
        var self = $(this)
        page   = self.data('page') + 1
        lastId = null // self.data('lastId')
        self.data('page', page)
        self.socialWindow('showFeed', page, lastId)
    },

    renderFeed: function (data, canvas) {
        if (data.length == 0)
            return

        var self = $(this)
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
                    if (! plug.name)
                        continue
                    context.pedalboard.plugins.push({
                        name     : plug.name,
                        thumbnail: plug.thumbnail_href,
                    })
                }
            }

            var content = $(Mustache.render(TEMPLATES.cloud_feed, context))

            if (sdata.pedalboard) {
                content.find('.js-pedalboard-' + sdata.pedalboard.id).click(pbLoad(sdata.pedalboard.file_href))
            }

            content.appendTo(canvas)

            renderNextPost(data)
        }

        renderNextPost(data.reverse())
    },

    showSearch: function () {},
})
