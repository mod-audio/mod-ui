function WaitMessage() {
    var self = this
    self.block = $('<div class="screen-disconnected">')
    self.block.hide()
    $('body').append(self.block).css('overflow', 'hidden')
    
    this.start = function(message) {
	self.block.html('')
	$('<p>').text(message).appendTo(self.block)
	self.block.width($(window).width() * 5)
	self.block.height($(window).height() * 5)
	self.block.css('margin-left', -$(window).width() * 2)
	$('#wrapper').css('z-index', -1)
	self.block.show()
    }

    this.stop = function() {
	self.block.hide()
	$('#wrapper').css('z-index', 'auto')
    }
}
