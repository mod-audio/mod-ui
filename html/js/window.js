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

function WindowManager() {
    var self = this

    this.windows = []

    this.register = function(window) {
	self.windows.push(window)

	window.window('open', function(f) {
	    self.closeWindows(window)
	})

    }
    
    this.closeWindows = function(window) {
	for (var i=0; i<self.windows.length; i++) {
	    var win = self.windows[i]
	    if (win != window)
		win.window('close')
	}
    }

    $(document).bind('keydown', function(e) {
	if (e.keyCode == 27) {
	    self.closeWindows()
	}
    })
}

(function($) {
    /*
     * window
     */

    var methods = {
	init: function(options) {
	    var self = $(this)
	    if (!options)
		options = {}
	    var trigger = options.trigger
	    self.data('trigger', trigger)

	    if (options.open) self.bind('windowopen', options.open)
	    if (options.close) self.bind('windowclose', options.close)

	    self.hide()

	    options.windowManager.register(self)

	    self.find('.js-close').click(function() {
		self.window('close')
		return false
	    })

	    if (trigger) {
		trigger.removeClass('selected')

		trigger.click(function() {
		    self.window('toggle')
		})
	    }

	    //self.click(function() { return false })

	    // TODO this shouldn't be too hardcoded
	    self.data('defaultIcon', $('#mod-plugins'))

	    return self
	},

	open: function(closure) {
	    var self = $(this)
	    if (closure) {
		self.bind('windowopen', closure)
		return
	    }

	    self.window('unfade')

	    if (self.is(':visible'))
		return

	    var trigger = self.data('trigger')
	    if (trigger)
		trigger.addClass('selected')
	    self.css('z-index', 100)
	    self.show()
	    self.trigger('windowopen')

	    self.data('defaultIcon').removeClass('selected')
	},
	    
	close: function(closure) {
	    var self = $(this)
	    if (closure) {
		self.bind('windowclose', closure)
		return
	    }
	    if (!self.is(':visible'))
		return

	    var trigger = self.data('trigger')
	    if (trigger)
		trigger.removeClass('selected')
	    self.hide()
	    self.trigger('windowclose')
	    self.data('defaultIcon').addClass('selected')
	},

	toggle: function() {
	    var self = $(this)
	    if (self.is(':visible'))
		self.window('close')
	    else
		self.window('open')
	},

	fade: function() {
	    var self = $(this)
	    if (self.is(':visible'))
		self.animate({ opacity: 0.1 }, 400)
	},

	unfade: function() {
	    var self = $(this)
	    if (self.is(':visible'))
		self.animate({ opacity: 1 }, 400)
	    else
		self.css('opacity', 1)
	}
    }

    $.fn.window = function(method) {
	if (methods[method]) {
	    return methods[method].apply(this, Array.prototype.slice.call(arguments, 1));
	} else if (typeof method === 'object' || !method) {
	    return methods.init.apply(this, arguments);
	} else {
	    $.error( 'Method ' +  method + ' does not exist on jQuery.window' );
	}
    }
})(jQuery);

