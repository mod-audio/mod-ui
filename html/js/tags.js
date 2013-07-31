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

(function($) {
    /*
     * tagField
     */

    var methods = {
	init: function(options) {
	    var self = $(this)

	    self.data('tags', [])
	    self.data('index', {})

	    var template = self.find('.js-item-template')
	    template.remove()
	    // very hacky outterHtml 
	    var template = template.clone().wrap('<div>').parent().html()
	    self.data('template', template.replace(/TAG/, '{{tag}}'))

	    var input = self.find('input[type=text]')
	    self.data('input', input)

	    input.keydown(function(e) { 
		if (e.keyCode == 13) { 
		    self.tagField('add')
		}
	    })
	},

	val: function(tags) {
	    var self = $(this)
	    self.tagField('add')
	    if (tags != undefined) {
 		var index = self.data('index')
		for (var tag in index) 
		    index[tag].remove()
		self.data('tags', [])
		self.data('index', {})
		if (tags)
		    for (var i=0; i<tags.length; i++) {
			self.tagField('add', tag)
		    }
	    }
	    return self.data('tags')
	},

	add: function() {
	    var self = $(this)

	    var tag = self.data('input').val()
	    self.data('input').val('')

	    var tags = self.data('tags')
	    var index = self.data('index')

	    if (!tag || index[tag])
		return

	    var item = $(Mustache.render(self.data('template'), { tag: tag }))
	    self.find('.js-item-list').append(item)
	    item.find('.js-remove').click(function() {
		self.tagField('remove', tag)
	    })

	    tags.push(tag)
	    index[tag] = item
	},

	remove: function(tag) {
	    var self = $(this)

	    var tags = self.data('tags')
	    var index = self.data('index')

	    var item = index[tag]

	    if (!tag || !item)
		return
	    
	    delete(index[tag])
	    tags.splice(tags.indexOf(tag), 1)

	    item.remove()	    
	},

	

    }
    $.fn.tagField = function(method) {
	if (methods[method]) {
	    return methods[method].apply(this, Array.prototype.slice.call(arguments, 1));
	} else if (typeof method === 'object' || !method) {
	    return methods.init.apply(this, arguments);
	} else {
	    $.error( 'Method ' +  method + ' does not exist on jQuery.tagField' );
	}
    }
})(jQuery);





