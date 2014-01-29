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

var STOPPED = 0
var RECORDING = 1
var PLAYING = 2

JqueryClass('shareBox', {
    init: function(options) {
	var self = $(this)

	options = $.extend({
	    // Generates a screenshot of pedalboard with given uid and calls callback with b64encoded data
	    takeScreenshot: function(uid, callback) { callback('') },

	    recordStart: function(callback) { callback() },
	    recordStop: function(callback) { callback() },
	    playStart: function(startCallback, stopCallback) { startCallback(); setTimeout(stopCallback, 3000) },
	    playStop: function(callback) { callback() },
	    recordDownload: function(callback) { callback({}) },
	    recordReset: function(callback) { callback() },

	    // Do the sharing in cloud
	    share: function(data, callback) { callback(true) }
	}, options)

	self.data(options)
	self.data('pedalboard', {})
	self.data('recordedData', null)

	self.find('.js-share').click(function() {
	    self.shareBox('share')
	})
	self.find('.js-close').click(function() { self.hide() })

	self.find('#record-rec').click(function() { self.shareBox('recordStart') })
	self.find('#record-stop').click(function() { self.shareBox('recordStop') })
	self.find('#record-play').click(function() { self.shareBox('recordPlay') })

	self.data('status', STOPPED)

	$('body').keydown(function(e) {
	    if (e.keyCode == 27)
		self.hide()
	})
    },

    recordStart: function() {
	var self = $(this)
	var status = self.data('status')
	var start = function() {
	    self.data('recordedData', null)
	    self.shareBox('recordCountdown', 1)
	}
	if (status == STOPPED) {
	    start()
	} else if (status == PLAYING) {
	    self.shareBox('recordStop', start)
	}
    },
    recordCountdown: function(secs) {
	var self = $(this)
	if (secs == 0) {
	    self.shareBox('announce', 'Recording!')
	    self.data('status', RECORDING)
	    self.data('recordStart')(function() {
		self.find('#record-rec').addClass('recording')
	    })
	    return
	}
	self.shareBox('announce', 'Recording starts in ' + secs, 1000)
	setTimeout(function() {
	    self.shareBox('recordCountdown', secs-1)
	}, 1000)
    },
    recordStop: function(callback) {
	var self = $(this)
	var status = self.data('status')
	if (status == STOPPED) {
	    return
	} else if (status == RECORDING) {
	    self.find('.js-share').removeClass('disabled')
	    self.data('recordStop')(function() {
		self.find('#record-rec').removeClass('recording')
		self.shareBox('announce')
		if (callback)
		    callback()
	    })
	} else { // PLAYING
	    self.data('playStop')(function() {
		self.find('#record-play').removeClass('playing')
		self.shareBox('announce')
		if (callback)
		    callback()
	    })
	}
    },
    recordPlay: function() {
	var self = $(this)
	var play = function() {
	    self.data('playStart')(function() {
		self.find('#record-play').addClass('playing')
		self.data('status', PLAYING)
	    }, function () {
		self.find('#record-play').removeClass('playing')
		self.data('status', STOPPED)
	    })
	    self.shareBox('announce', 'Playing')
	}
	var status = self.data('status')
	if (status == STOPPED)
	    play()
	else
	    self.shareBox('recordStop', play)
    },

    announce: function(message, timeout) {
	var self = $(this)
	if (message == null)
	    message = ''
	if (timeout == null)
	    timeout = 500
	var statusBox = self.find('#record-status')
	statusBox.text(message)
	if (self.data('announceTimeout'))
	    clearTimeout(self.data('announceTimeout'))
	self.data('announceTimeout', setTimeout(function() {
	    statusBox.text('')
	}, timeout))
    },

    share: function() {
	var self = $(this)
	var data = { 
	    pedalboard: self.data('pedalboard'),
	    title: self.find('input[type=text]').val(),
	    description: self.find('textarea').val()
	}
	self.data('recordDownload')(function(audioData) {
	    data = $.extend(data, audioData)
	    self.data('share')(data, function(ok) {
		if (ok) {
		    self.data('recordReset')(function(){
			self.hide()
		    })
		} else {
		    new Notification('error', "Couldn't share pedalboard")
		}
	    })
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
	self.show()
	text.autoResize({
	    maxHeight: $(window).height() - text.offset().top - 100
	})
    },

})

