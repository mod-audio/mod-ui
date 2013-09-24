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

JqueryClass('shareBox', {
    init: function(options) {
	var self = $(this)

	options = $.extend({
	    // Generates a screenshot of pedalboard with given uid and calls callback with b64encoded data
	    takeScreenshot: function(uid, callback) { callback('') },

	    // Do the sharing in cloud
	    share: function(data, callback) { callback(true) }
	}, options)

	self.data(options)
	self.data('pedalboard', {})
	self.data('screenshotGenerated', false)

	self.find('.js-share').click(function() {
	    if (self.data('screenshotGenerated'))
		self.shareBox('share')
	})
	self.find('.js-close').click(function() { self.hide() })
	$('body').keydown(function(e) {
	    if (e.keyCode == 27)
		self.hide()
	})
    },

    share: function() {
	var self = $(this)
	var data = { 
	    pedalboard: self.data('pedalboard'),
	    screenshot: self.data('screenshot'),
	    thumbnail: self.data('thumbnail'),
	    title: self.find('input[type=text]').val(),
	    description: self.find('textarea').val()
	}
	self.data('share')(data, function(ok) {
	    if (ok) {
		self.hide()
	    } else {
		new Notification('error', "Couldn't share pedalboard")
	    }
	})
    },

    open: function(uid, title, pedalboard) {
	var self = $(this)
	self.data('pedalboard', pedalboard)
	self.find('input[type=text]').val(title)
	var text = self.find('textarea')
	text.val('').focus()
	self.data('screenshotGenerated', false)
	self.find('.js-share').addClass('disabled')
	self.data('takeScreenshot')(uid, function(result) {
	    self.data('screenshot', result.screenshot)
	    self.data('thumbnail', result.thumbnail)
	    var img = self.find('img.screenshot').attr('src', 'data:image/png;base64,'+result.screenshot).show()
	    setTimeout(function() {
		self.find('.image').width(img.width()).height(img.height())
	    }, 0)
	    self.find('img.loading').hide()
	    self.find('.js-share').removeClass('disabled')
	    self.data('screenshotGenerated', true)
	})
	self.shareBox('calculateDimensions')
	self.find('img.loading').show()
	self.find('img.screenshot').hide()
	self.show()
	text.autoResize({
	    maxHeight: $(window).height() - text.offset().top - 100
	})

    },

    // Based on current pedalboard size and maximum screenshot dimensions, calculate the
    // resize img container to the final image size
    // This is not perfect, as the pedalboard might have just been loaded in a different screen size,
    // so that saved size is different from computed size here. Let's just ignore this case.
    calculateDimensions: function() {
	var self = $(this)
	width = self.data('pedalboard').width
	height = self.data('pedalboard').height
        if (width > MAX_SCREENSHOT_WIDTH) {
            height = height * MAX_SCREENSHOT_WIDTH / width
            width = MAX_SCREENSHOT_WIDTH
	}
        if (height > MAX_SCREENSHOT_HEIGHT) {
            width = width * MAX_SCREENSHOT_HEIGHT / height
            height = MAX_SCREENSHOT_HEIGHT
	}

	self.find('.image').width(width).height(height)
    }
})

