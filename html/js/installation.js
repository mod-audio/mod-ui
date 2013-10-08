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

function InstallationQueue() {
    var self = this

    var queue = []
    var callbacks = []
    var results = {}

    var notification

    this.openNotification = function() {
	if (!notification)
	    notification = new Notification('warning')
	else
	    notification.open()
	notification.html('Installing effect...')
	notification.type('warning')
	notification.bar(0)
    }

    // TODO rename to installUrl
    this.install = function(effectUrl, callback) {
	if (queue.length == 0) {
	    self.openNotification()
	}
	
	$.ajax({ 'url': SITEURL+'/effect/get/?url='+escape(effectUrl),
		 'success': function(effect) {
		     if (!effect) {
			 new Notification('error', sprintf("Can't find effect %s to install", effectUrl))
			 if (queue.length == 0)
			     notification.close()
		     }
		     queue.push(effect)
		     callbacks.push(callback)
		     if (queue.length == 1)
			 self.installNext()
		     
		 },
		 'error': function() {
		     new Notification('error', 'Installation failed')
		     if (queue.length == 0)
			 notification.closeAfter(5000)
		 },
		 'dataType': 'json'
	       })
	
    }

    this.installEffect = function(effect, callback) {
	queue.push(effect)
	callbacks.push(callback)
	if (queue.length == 1)
	    self.installNext()
    }
    
    this.installNext =  function() {
	var effect = queue[0]
	var callback = callbacks[0]
	var finish = function() {
	    var status = $('[mod-role=available-plugin][mod-plugin-id='+effect._id+'] .status')
	    status.removeClass('installed')
	    status.removeClass('outdated')
	    status.removeClass('blocked')
	    status.addClass('installed')
	    queue.shift()
	    callbacks.shift()
	    if (queue.length > 0) {
		self.installNext()
	    } else {
		notification.closeAfter(3000)
	    }
	    callback(effect)
	}

	var abort = function(reason) {
	    queue.shift()
	    callbacks.shift()
	    notification.close()
	    new Notification('error', "Could not install effect: " + reason)
	}

	if (results[effect._id]) {
	    finish()
	    return
	}
	
	var installationMsg = 'Installing package '+effect['package']+' (contains '+effect.name+')'
	notification.html(installationMsg)
	notification.type('warning')
	notification.bar(1)

	var trans = new Transference(SITEURL+'/effect/install',
				     '/effect/install',
				     effect['package_id'])
	
	trans.reportStatus = function(status) {
	    notification.bar(status.percent)
	}
	
	trans.reportFinished = function(result) {
	    notification.html(installationMsg + ' - OK!')
	    notification.bar(100)
	    notification.type('success')
	    for (var i=0; i<result.length; i++) {
		results[result[i]] = true
	    }
	    finish()
	}

	trans.reportError = abort
	
	trans.start()
	
    }
}
