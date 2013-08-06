function Bluetooth(options) {

    options = $.extend({
	icon: null, // jquery dom element
	frequency: 5000,
	status: function(status) {},
	notify: function(msg) { alert(msg) },
    }, options)

    var icon = options.icon 
    var frequency = options.frequency

    var self = this

    this.ping = function() {
	var start = Date.now()
	$.ajax({ url: '/ping', 
		 success: function(result) {
		     var time = Date.now() - start - result.ihm_time
		     self.status(true, time, result.ihm_time)
		     setTimeout(self.ping, frequency)
		 },
		 error: function() {
		     self.status(false)
		     setTimeout(self.ping, frequency)
		 },
		 dataType: 'json'
	       })
    }

    this.status = function(online, bluetooth, ihm) {
	var msg
	if (online) {
	    msg = sprintf('Bluetooth: %dms Controls: %dms', bluetooth, ihm)
	    options.status(true)
	} else {
	    msg = 'OFFLINE'
	    options.status(false)
	}

	options.notify(msg)
    }

    this.ping()
}