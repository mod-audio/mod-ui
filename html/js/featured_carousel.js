JqueryClass('featuredCarousel', {
	init: function(options) {
		var self = $(this);

		var plugins = self.find('div.featured');

		var plugins = plugins.sort(function(a, b) {
			a = $(a).data('priority');
			b = $(b).data('priority');
			if (a > b) return -1;
			if (b > a) return 1;
			return 0;
		})

		var main = new Carousel(plugins[0]);
		var left = main;
		var right = main;
		for (var i=1; i<plugins.length; i++) {
			if (i % 2 == 0) {
				left = left.addLeft(plugins[i])
			} else {
				right = right.addRight(plugins[i])
			}
		}

		left.leftNode = right
		right.rightNode = left

		if (plugins.length > 2) {
			var leftArrow = $('<div>').addClass('left-arrow').insertBefore($(plugins[0]))
			var rightArrow = $('<div>').addClass('right-arrow').insertAfter($(plugins[plugins.length-1]))

			leftArrow.click(function() { self.featuredCarousel('rotateLeft') });
			rightArrow.click(function() { self.featuredCarousel('rotateRight') });
		}

		main.element.addClass('main')
		main.leftNode.element.addClass('left')
		main.rightNode.element.addClass('right')

		self.data('main', main)
		self.data('plugins', plugins)
	},

	rotateLeft: function() {
		var self = $(this);
		var main = self.data('main')
		main.leftNode.leftNode.element.addClass('left')
		main.leftNode.element.removeClass('left').addClass('main')
		main.element.removeClass('main').addClass('right')
		main.rightNode.element.removeClass('right')
		self.data('main', main.leftNode);
	},

	rotateRight: function() {
		var self = $(this);
		var main = self.data('main');
		main.rightNode.rightNode.element.addClass('right')
		main.rightNode.element.removeClass('right').addClass('main')
		main.element.removeClass('main').addClass('left')
		main.leftNode.element.removeClass('left')
		self.data('main', main.rightNode);
	}
})

function Carousel(element, leftNode, rightNode) {
	// Double circular linked list

	this.element = $(element);
	this.rightNode = rightNode;
	this.leftNode = leftNode;
}

Carousel.prototype.addLeft = function(element) {
	this.leftNode = new Carousel(element, null, this)
	return this.leftNode
}

Carousel.prototype.addRight = function(element) {
	this.rightNode = new Carousel(element, this, null)
	return this.rightNode
}
