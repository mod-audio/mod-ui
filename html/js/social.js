/*
 * Copyright 2012-2013 AGR Audio, Industria e Comercio LTDA. <contato@portalmod.com>
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
    init: function(options) {
	var self = $(this)
	options = $.extend({
	    userSession: null, //must be passed
	    getFeed: function(callback) { callback([]) },
	    loadPedalboard: function(pedalboard) {},
	    trigger: $('<div>')
	}, options)

	self.data(options)
	self.window($.extend({
	    preopen: function(callback) {
		options.userSession.login(callback)
	    },
	    open: function() {
		self.socialWindow('showFeed')
	    }
	}, options))

	self.find('#cloud-feed').click(function() {
	    self.socialWindow('renderFeed')
	})
	self.find('#cloud-pedalboards').click(function() {
	    self.socialWindow('showSearch')
	})
	return self
    },

    showFeed: function() {
	var self = $(this)
	self.data('getFeed')(function(pedalboards) {
	    var content = self.socialWindow('renderFeed', pedalboards)
	    self.find('#social-main').html('').append(content)
	    self.window('open')
	})
    },

    renderFeed: function(pedalboards) {
	var self = $(this)
	var pb, i;
	for (i=0; i<pedalboards.length; i++) {
	    pb = pedalboards[i]
	    if (pb.author.first_name) {
		pb.author.name = pb.author.first_name
		if (pb.author.last_name)
		    pb.author.name += ' ' + pb.author.last_name
	    } else {
		pb.author.name = pb.author.username
	    }
	    pb.created = renderTime(new Date(pb.created * 1000))
	}
	
	var context = { 
	    pedalboards: pedalboards,
	    cloud: SITEURL,
	}
	var content = $(Mustache.render(TEMPLATES.cloud_feed, context))
	content.find('div.spec').each(function() {
	    var spec = $(this)
	    if (parseInt(spec.find('span').html()) == 0) {
		spec.addClass('none')
	    }
	})
	for (i=0; i<pedalboards.length; i++) {
	    var pbFactory = function(pedalboard) {
		return function() {
		    self.data('loadPedalboard')(pedalboard)
		}
	    }
	    content.find('#pedalboard-'+pedalboards[i]['_id']).click(pbFactory(pedalboards[i]))
	}
	return content
    },

    showSearch: function() {
    },
})
