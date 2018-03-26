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

		var carousel = new Carousel(plugins[0]);
		var left = carousel;
		var right = carousel;
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

		self.data('carousel', carousel)
		self.data('plugins', plugins)

		self.featuredCarousel('highlight')
	},

	highlight: function() {
		var self = $(this)
		var carousel = self.data('carousel')
		self.data('plugins').removeClass('left').removeClass('right').removeClass('main')
		carousel.element.addClass('main')
		carousel.leftNode.element.addClass('left')
		carousel.rightNode.element.addClass('right')

	},

	rotateLeft: function() {
		var self = $(this);
		var carousel = self.data('carousel');
		self.data('carousel', carousel.leftNode);
		self.featuredCarousel('highlight');
	},

	rotateRight: function() {
		var self = $(this);
		var carousel = self.data('carousel');
		self.data('carousel', carousel.rightNode);
		self.featuredCarousel('highlight');
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
