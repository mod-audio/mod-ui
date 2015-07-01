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
            getFeed: function (page, callback) {
                callback([])
            },
            loadPedalboard: function (pedalboard) {},
            trigger: $('<div>')
        }, options)

        self.data(options)
        self.window($.extend({
            preopen: function (callback) {
                options.userSession.login(callback)
            },
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

    showFeed: function (page) {
        var self = $(this)
        self.data('getFeed')(page, function (pedalboards) {
            var canvas = self.find('#social-main')
            if (page == 0)
                canvas.find('li.feed').remove()
            var content = self.socialWindow('renderFeed', pedalboards, canvas)
            //canvas.find('li.more').appendTo(canvas) // always last item
            //self.find('button').show()
            self.window('open')
        })
    },

    nextPage: function () {
        var self = $(this)
        page = self.data('page') + 1
        self.data('page', page)
        self.socialWindow('showFeed', page)
    },

    renderFeed: function (pedalboards, canvas) {
        var self = $(this)
        var pbLoad = function (pb_url) {
            return function () {
                self.data('loadPedalboard')(pb_url)
            }
        }

        function renderNextPedalboard(pedalboards) {
            if (pedalboards.length == 0)
                return

            var pb = pedalboards.pop()
            console.log(pb)

            // FIXME
            desktop.userSession.getUserData(pb.user_id, function (data) {
                var context = {
                    cloud:       SITEURLNEW,
                    avatar_href: data.avatar_href,
                    user_name:   data.name
                }
                console.log(i)
                // FIXME broken
                //pb.created = renderTime(new Date(pb.created * 1000))

                $.extend(context, pb)

                var content = $(Mustache.render(TEMPLATES.cloud_feed, context))
                content.find('.js-pedalboard-' + pb.id).click(pbLoad(pb.file_href))
                content.find('div.spec').each(function () {
                    var spec = $(this)
                    if (parseInt(spec.find('span').html()) == 0) {
                        spec.addClass('none')
                    }
                });
                content.appendTo(canvas)

                renderNextPedalboard(pedalboards)
            })
        }

        renderNextPedalboard(pedalboards.reverse())
    },

    showSearch: function () {},
})
