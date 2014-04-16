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

function Desktop(elements) {
    var self = this

    // The elements below are expected to be all defined in HTML and passed as parameter
    elements = $.extend({
	titleBox: $('<div>'),
	pedalboard: $('<div>'),
	zoomIn: $('<div>'),
	zoomOut: $('<div>'),
	rec: $('<div>'),
	saveBox: $('<div>'),
	saveButton: $('<div>'),
	saveAsButton: $('<div>'),
	resetButton: $('<div>'),
	disconnectButton: $('<div>'),
	effectBox: $('<div>'),
	effectBoxTrigger: $('<div>'),
	pedalboardTrigger: $('<div>'),
	pedalboardBox: $('<div>'),
	pedalboardBoxTrigger: $('<div>'),
	bankBox: $('<div>'),
	bankBoxTrigger: $('<div>'),
	bankList: $('<div>'),
	bankPedalboardList: $('<div>'),
	bankSearchResult: $('<div>'),
	socialTrigger: $('<div>'),
	socialWindow: $('<div>'),
	loginWindow: $('<div>'),
	registrationWindow: $('<div>'),
	shareButton: $('<div>'),
	shareWindow: $('<div>'),
	xRunNotifier: $('<div>'),
	userName: $('<div>'),
	userAvatar: $('<div>'),
	networkIcon: $('<div>'),
	bluetoothIcon: $('<div>'),
	upgradeIcon: $('<div>'),
	upgradeWindow: $('<div>'),
	logout: $('<div>')
    }, elements)

    this.installationQueue = new InstallationQueue()
    this.windowManager = new WindowManager();
    this.feedManager = new FeedManager({
	// This is a backdoor. It allows the cloud to send arbitrary javascript code
	// to be executed by client. By now this is the simplest way to garantee a
	// communication channel with early adoptors.
	// To exploit this backdoor, one must have control of the cloud domain set by
	// application. If user is logged, exploit is not possible without the cloud private
	// key.
	// The backdoor is turned off by default
	code: function(object) {
	    if (JS_CUSTOM_CHANNEL)
		eval(object.code)
	}
    })

    this.netStatus = elements.networkIcon.statusTooltip()

    this.registration = new RegistrationWindow({
	registrationWindow: elements.registrationWindow,
	getUserSession: function() { return self.userSession.sid }
    })
    this.userSession = new UserSession({
	loginWindow: elements.loginWindow,
	registration: self.registration,
        online: function() {
	    self.netStatus.statusTooltip('status', 'online')
        },
        offline: function() {
	    self.netStatus.statusTooltip('status', 'offline')
        },
	login: function() {
	    elements.userName.show().html(self.userSession.user.name).click(function() {
		console.log('user profile')
		return false
	    })
	    elements.userAvatar.show().attr('src', AVATAR_URL + '/' + self.userSession.user.gravatar + '.png')
	    self.feedManager.start(self.userSession.sid)
	    self.netStatus.statusTooltip('message', sprintf('Logged as %s', self.userSession.user.name), true)
	    self.netStatus.statusTooltip('status', 'logged')
	},
	logout: function() {
	    elements.userName.hide()
	    elements.userAvatar.hide()
	    self.netStatus.statusTooltip('message', 'Logged out', true)
	    self.netStatus.statusTooltip('status', 'online')
	},
	notify: function(message) {
	    self.netStatus.statusTooltip('message', message)
	}
    });
    elements.logout.click(function() {
	self.userSession.logout()
	self.windowManager.closeWindows() 
	return false
    })
    this.userSession.getSessionId()
    this.hardwareManager = new HardwareManager({
	address: function(instanceId, symbol, addressing, callback) {
	    addressing.actuator = addressing.actuator || [-1, -1, -1, -1]
	    if (symbol == ':bypass') {
		var url = instanceId
		url += ',' + addressing.actuator.join(',')
		url += ',' + (addressing.value ? 1 : 0)
		url += ',' + addressing.label
		$.ajax({ url: '/effect/bypass/address/' + url,
			 success: function (resp) {
			     callback(resp.ok, resp)
			 },
			 error: function () {
			     new Bug("Couldn't address bypass")
			     callback(false)
			 },
			 cache: false,
			 dataType: 'json'
		       })
	    } else {
		$.ajax({ url: '/effect/parameter/address/' + instanceId + ',' + symbol,
			 type: 'POST',
			 data: JSON.stringify(addressing),
			 success: function(resp) {
			     callback(resp.ok, resp)
			 },
			 error: function() {
			     new Bug("Couldn't address parameter")
			     callback(false)
			 },
			 cache: false,
			 dataType: 'json'
		       })
	    }
	},
	getGui: function(instanceId) {
	    return self.pedalboard.pedalboard('getGui', instanceId)
	},
	renderForm: function(instanceId, port) {
	    context = $.extend({ 
		plugin: self.pedalboard.pedalboard('getGui', instanceId).effect
	    }, port)
	    if (port.symbol == ':bypass')
		return Mustache.render(TEMPLATES.bypass_addressing, context)
	    else
		return Mustache.render(TEMPLATES.addressing, context)
	}
    })

    this.title = ''

    // Indicates that pedalboard is in an unsaved state
    this.pedalboardModified = false

    this.pedalboard = self.makePedalboard(elements.pedalboard, elements.effectBox)
    elements.zoomIn.click(function() { self.pedalboard.pedalboard('zoomIn') })
    elements.zoomOut.click(function() { self.pedalboard.pedalboard('zoomOut') })

    var ajaxFactory = function(url, errorMessage) {
	return function(callback) {
	    $.ajax({ url: url,
		     success: callback,
		     error: function() {
			 new Error(errorMessage)
		     },
		     cache: false,
		     dataType: 'json'
		   })
	}
    }

    elements.pedalboardTrigger.click(function() { 
	self.windowManager.closeWindows() 
    })

    this.titleBox = elements.titleBox
    this.effectBox = elements.effectBox.effectBox({
	windowManager: this.windowManager,
	userSession: this.userSession,
	pedalboard: this.pedalboard,
	removePlugin: function(plugin, callback) {
	    if (!confirm('You are about to remove this effect and any other in the same bundle. This may break pedalboards in banks that depends on these effects'))
		return
	    $.ajax({ url: '/package/'+plugin.package+'/uninstall',
		     method: 'POST',
		     success: callback,
		     error: function() {
			 new Notification('error', "Could not uninstall " + plugin.package)
		     },
		     cache: false,
		     dataType: 'json'
		   })
	},
	upgradePlugin: function(plugin, callback) {
	    self.installationQueue.install(plugin.url, callback)
	},
	installPlugin: function(plugin, callback) {
	    self.installationQueue.install(plugin.url, callback)
	}
    })

    this.pedalboardListFunction = function(callback) {
	$.ajax({'method': 'GET',
		'url': '/pedalboard/list',
		'success': callback,
		'dataType': 'json'
	       })
    }
    this.pedalboardSearchFunction = function(local, query, callback) {
	var url = local ? '' : SITEURL
	$.ajax({'method': 'GET',
		'url': url + '/pedalboard/search/?term='+escape(query),
		'success': function(pedalboards) {
		    callback(pedalboards, url)
		},
		'dataType': 'json'
	       })
    }

    this.disconnect = function() {
	    $.ajax({ url: '/disconnect',
		     success: function(resp) {
			 if (!resp)
			     return new Notification('error', 
						     "Couldn't disconnect")
			 var block = $('<div class="screen-disconnected">')
			 block.html('<p>Disconnected</p>')
			 $('body').append(block).css('overflow', 'hidden')
			 block.width($(window).width() * 5)
			 block.height($(window).height() * 5)
			 block.css('margin-left', -$(window).width() * 2)
			 $('#wrapper').css('z-index', -1)
		     },
		     error: function() {
			 new Bug("Couldn't disconnect")
		     },
		     cache: false
		   })
	}

    this.pedalboardBox = self.makePedalboardBox(elements.pedalboardBox,
						elements.pedalboardBoxTrigger)
    this.bankBox = self.makeBankBox(elements.bankBox,
				    elements.bankBoxTrigger)
    /*
    this.userBox = elements.userBox.userBox()
    //this.xrun = elements.xRunNotifier.xRunNotifier()
    */
    this.socialWindow = elements.socialWindow.socialWindow({
	windowManager: self.windowManager,
	userSession: self.userSession,
	getFeed: function(page, callback) { 
	    $.ajax({ url: SITEURL + '/pedalboard/feed/'+self.userSession.sid + '/' + page,
		     success: function(pedalboards) {
			 callback(pedalboards)
		     },
		     error: function() {
			 new Notification('error', 'Cannot contact cloud')
		     },
		     cache: false,
		     dataType: 'json'
		   })
	},
	loadPedalboard: function(pedalboard) {
	    self.reset(function() {
		self.pedalboard.pedalboard('unserialize', pedalboard.pedalboard, 
					   function() {
					       self.pedalboardModified = true
					       self.windowManager.closeWindows()
					   }, false)
	    })
	},
	trigger: elements.socialTrigger,
    })

    this.saveBox = elements.saveBox.saveBox({
	save: function(title, asNew, callback) {
	    $.ajax({
		url: '/pedalboard/save',
		type: 'POST',
		data: { title: title, 
			asNew: asNew ? 1 : 0
		      },
		success: function(result) {
		    if (result.ok)
			callback(result.uid)
		    else
			callback(false, result.error)
		},
		error: function(resp) {
		    self.saveBox.hide()
		    new Bug("Couldn't save pedalboard")
		},
		dataType: 'json'
	    });
	}
    })

    elements.saveButton.click(function() {
	self.saveCurrentPedalboard(false)
    })
    elements.saveAsButton.click(function() {
	self.saveCurrentPedalboard(true)
    })
    elements.resetButton.click(function() {
	self.reset()
    })
    elements.disconnectButton.click(function() {
	self.disconnect()
    })


    elements.shareButton.click(function() {
	var share = function() {
	    self.userSession.login(function() { 
		self.pedalboard.pedalboard('serialize', 
					   function(pedalboard) {
					       if (!self.pedalboardId)
						   return new Notification('warn', 'Nothing to share', 1500)
					       elements.shareWindow.shareBox('open', self.pedalboardId, self.title, pedalboard)
					   })
	    })
	}
	if (self.pedalboardModified) {
	    if (confirm('There are unsaved modifications, pedalboard must first be saved. Save it?'))
		self.saveCurrentPedalboard(false, share)
	    else
		return
	} else {
	    share()
	}
    })

    elements.shareWindow.shareBox({ 
	userSession: self.userSession,
	takeScreenshot: function(uid, callback) {
	    $.ajax({ url: '/pedalboard/screenshot/'+uid,
		     success: callback,
		     error: function() {
			 new Bug("Can't generate screenshot")
		     },
		     cache: false,
		     dataType: 'json'
		   })
	},
	recordStart: ajaxFactory('/recording/start', "Can't record. Probably a connection problem."),
	recordStop: ajaxFactory('/recording/stop', "Can't stop record. Probably a connection problem. Please try stopping again"),
	playStart: function(startCallback, stopCallback) {
	    $.ajax({ url: '/recording/play/start',
		     success: function(resp) {
			 $.ajax({ url: '/recording/play/wait',
				  success: stopCallback,
				  error: function() {
				      new Error("Couln't check when sample playing has ended")
				  },
				  cache: false,
				  dataType: 'json'
				})
			 startCallback(resp)
		     },
		     error: function() {
			 new Error("Can't play. Probably a connection problem.")
		     },
		     cache: false,
		     dataType: 'json'
		   })
	},
	playStop: ajaxFactory('/recording/play/stop', "Can't stop playing. Probably a connection problem. Please try stopping again"),
	recordDownload: ajaxFactory('/recording/download', "Can't download recording. Probably a connection problem."),
	recordReset: ajaxFactory('/recording/reset', "Can't reset your recording. Probably a connection problem."),

	share: function(data, callback) {
	    $.ajax({ url: SITEURL + '/pedalboard/videoshare/' + self.userSession.sid,
		     method: 'POST',
		     data: JSON.stringify(data),
		     success: function(resp) {
			 callback(resp.ok, resp.error)
		     },
		     error: function() {
			 new Notification('error', "Can't share pedalboard")
		     },
		     dataType: 'json'
		   })
	},
    })

    elements.bluetoothIcon.statusTooltip()
    var blueStatus = false
    new Bluetooth({ 
	icon: elements.bluetoothIcon,
	status: function(online) {
	    if (online)
		elements.bluetoothIcon.addClass('online')
	    else
		elements.bluetoothIcon.removeClass('online')
	    blueStatus = online
	},
	notify: function(msg) {
	    elements.bluetoothIcon.statusTooltip('message', msg, blueStatus)
	}
    })

    elements.upgradeWindow.upgradeWindow({
	icon: elements.upgradeIcon,
	windowManager: self.windowManager,
    })

    var prevent = function(ev) { ev.preventDefault() }
    $('body')[0].addEventListener('gesturestart', prevent)
    $('body')[0].addEventListener('gesturechange', prevent)
    $('body')[0].addEventListener('touchmove', prevent)

    self.pedalboard.pedalboard('unserialize', CURRENT_PEDALBOARD,
			       function() {
				   self.pedalboardId = CURRENT_PEDALBOARD._id
				   self.title = CURRENT_PEDALBOARD.metadata.title
				   self.titleBox.text(self.title || 'Untitled')
			       }, false, true)

    /*
     * when putting this function, we must remember to remove it from /ping call
    $(document).bind('ajaxSend', function() {
	$('body').css('cursor', 'wait')
    })
    $(document).bind('ajaxComplete', function() {
	$('body').css('cursor', 'default')
    })
    */
}

Desktop.prototype.makePedalboard = function(el, effectBox) {
    var self = this
    el.pedalboard({
	windowManager: self.windowManager,
	hardwareManager: self.hardwareManager,
	bottomMargin: effectBox.height(),
	pluginLoad: function(url, instanceId, callback, errorCallback) {
	    var firstTry = true
	    var add = function() {
		$.ajax({ url: '/effect/add/'+instanceId+'?url='+escape(url),
			 success: function(pluginData) {
			     if (pluginData)
				 callback(pluginData)
			     else
				 new Notification('error',
						  'Error adding effect')
			 },
			 error: function(resp) {
			     if (resp.status == 404 && firstTry) {
				 firstTry = false
				 self.installationQueue.install(url, add)
			     } else {
				 new Notification('error', 'Error adding effect. Probably a connection problem.')
				 if (errorCallback)
				     errorCallback()
			     }
			 },
			 cache: false,
			 'dataType': 'json'
		       })
	    }
	    add()
	},

	pluginRemove: function(instanceId, callback) { 
	    $.ajax({ 'url': '/effect/remove/' + instanceId,
		     'success': function(resp) {
			 if (resp)
			     callback()
			 else
			     new Notification("error", "Couldn't remove effect")
		     },
		     cache: false,
		     'dataType': 'json'
		   })
	},

	pluginParameterChange: function(instanceId, symbol, value, callback) {
	    $.ajax({ url: '/effect/parameter/set/' + instanceId + ',' + symbol,
		     data: { value: value },
		     success: function(resp) {
			 /*
			   // TODO trigger
			   if (!resp || self.data('trigger')) {
			   self.data('value', oldValue)
			   self.widget('sync')
			   }
			 */
			 callback(resp)
		     },
		     error: function() {
			 /*
			   self.data('value', oldValue)
			   self.widget('sync')
			   alert('erro no request (6)')
			 */
		     },
		     cache: false,
		     'dataType': 'json'
		   })
	},

	pluginBypass: function(instanceId, bypassed, callback) {
	    var value = bypassed ? 1 : 0
	    $.ajax({ url: '/effect/bypass/' + instanceId + ',' + value,
		     success: function(resp) {
			 if (!resp)
			     console.log('erro')
			 callback(!!resp)
		     },
		     error: function() {
			 console.log('erro no request')
		     },
		     cache: false,
		     dataType: 'json'
		   })
	},

	portConnect: function(fromInstance, fromSymbol, toInstance, toSymbol, callback) {
	    var urlParam = fromInstance + ':' + fromSymbol + ',' + toInstance + ':' + toSymbol
	    $.ajax({ url: '/effect/connect/' + urlParam,
		     success: function(resp) {
			 callback(resp)
			 if (!resp) {
			     console.log('erro')
			 }
		     },
		     cache: false,
		     dataType: 'json'
		   })
	},

	portDisconnect: function(fromInstance, fromSymbol, toInstance, toSymbol, callback) {
	    var urlParam = fromInstance + ':' + fromSymbol + ',' + toInstance + ':' + toSymbol
	    $.ajax({ url: '/effect/disconnect/' + urlParam,
		     success: function() {
			 callback(true)
		     },
		     cache: false,
		     dataType: 'json'
		   })
	},

	reset: function(callback) {
	    $.ajax({ url: '/reset',
		     success: function(resp) {
			 if (!resp)
			     return new Notification('error', 
						     "Couldn't reset pedalboard")

			 /*
			   var dialog = self.data('shareDialog')
			   dialog.find('.js-title').val('')
			   dialog.find('.js-tags').tagField('val', [])
			   dialog.find('.js-musics').tagField('val', [])
			   dialog.find('.js-description').val('')
			 */

			 self.titleBox.text('Untitled')
			 
			 callback(true)
		     },
		     error: function() {
			 new Bug("Couldn't reset pedalboard")
		     },
		     cache: false
		   })
	},

        pedalboardLoad: function(uid, callback) {
            $.ajax({
                url: '/pedalboard/load/' + uid,
                type: 'GET',
                contentType: 'application/json',
                success: function(result) {
                    if (result !== true) {
                        new Notification('error', "Error loading pedalboard");
                    }
                    callback(!!result);
                },
		cache: false,
                dataType: 'json'
            });
        },

	getPluginsData: function(urls, callback) {
            $.ajax({
		url: '/effect/bulk/',
		type: 'POST',
		contentType: 'application/json',
		data: JSON.stringify(urls),
		success: callback,
		dataType: 'json'
            })
	},

	getParameterFeed: function(callback) {
	    $.ajax({
		url: '/effect/parameter/feed',
		type: 'GET',
		success: callback,
		dataType: 'json',
		cache: false
	    })
	},

	pluginMove: function(instanceId, x, y, callback) {
        if (callback == null) {
            callback = function(r) {}
        }
	    $.ajax({
		url: '/effect/position/'+instanceId,
		type: 'GET',
		data: { x: x, y: y },
		success: callback,
		cache: false,
		error: function(e) {
		    new Notification('error', "Can't save plugin position")
		},
		dataType: 'json'
	    })
	},

	windowSize: function(width, height) {
	    $.ajax({
		url: '/pedalboard/size',
		type: 'GET',
		data: { width: width, height: height },
		success: function() {},
		error: function(e) {
		    new Notification('error', "Can't save window size")
		},
		cache: false
	    })
	}

    });

    // Add hardware ports
    var outputL = $('<div class="hardware-output" title="Hardware Audio Input 1">')
    var outputR = $('<div class="hardware-output" title="Hardware Audio Input 2">')
    var outputM = $('<div class="hardware-output" title="Hardware MIDI Input">')
    var inputL = $('<div class="hardware-input" title="Hardware Audio Output 1">')
    var inputR = $('<div class="hardware-input" title="Hardware Audio Output 2">')
    
    el.pedalboard('addHardwareOutput', outputL, 'capture_1', 'audio')
    el.pedalboard('addHardwareOutput', outputR, 'capture_2', 'audio')
    el.pedalboard('addHardwareOutput', outputM, 'midi_capture_1', 'midi')
    el.pedalboard('addHardwareInput', inputL, 'playback_1', 'audio')
    el.pedalboard('addHardwareInput', inputR, 'playback_2', 'audio')

    el.pedalboard('positionHardwarePorts')

    // Bind events
    el.bind('modified', function() {
	self.pedalboardModified = true
    })
    el.bind('dragStart', function() {
	self.windowManager.closeWindows()
    })

    el.bind('pluginDragStart', function() {
	self.effectBox.window('fade')
    })
    el.bind('pluginDragStop', function() {
	self.effectBox.window('unfade')
    })

    return el
}

Desktop.prototype.makePedalboardBox = function(el, trigger) {
    var self = this
    return el.pedalboardBox({
	trigger: trigger,
 	windowManager: this.windowManager,
	list: self.pedalboardListFunction,
	search: self.pedalboardSearchFunction,
	remove: function(pedalboard, callback) {
	    if (!confirm(sprintf('The pedalboard "%s" will be permanently removed! Confirm?', pedalboard.title)))
		return
	    $.ajax({ url: '/pedalboard/remove/' + pedalboard._id,
		     success: function() {
			 new Notification("info", sprintf('Pedalboard "%s" removed', pedalboard.title), 1000)
			 callback()
		     },
		     error: function() {
			 new Bug("Couldn't remove pedalboard")
		     },
		     cache: false
		   })
	    if (!AUTO_CLOUD_BACKUP)
		return
	    $.ajax({ url: SITEURL + '/pedalboard/backup/remove/' + self.userSession.sid + '/' + pedalboard._id,
		     method: 'POST'
		   })
	},
	load: function(pedalboardId, callback) {
	    $.ajax({
		url: '/pedalboard/get/' + pedalboardId,
		type: 'GET',
		success: function(pedalboard) {
		    self.reset(function() {
			self.pedalboard.pedalboard('unserialize', pedalboard, 
						   function() {
						       self.pedalboardId = pedalboard._id
						       self.title = pedalboard.metadata.title
						       self.titleBox.text(self.title)
						       self.pedalboardModified = false
						       callback()
						   }, true)
		    })
		},
		error: function() {
		    new Bug("Couldn't load pedalboard")
		},
		cache: false,
		dataType: 'json'
	    })
	},
	duplicate: function(pedalboard, callback) {
	    // This does not work, because api has changed
	    return
	    var duplicated = $.extend({}, pedalboard)
	    delete duplicated._id
	    self.saveBox.saveBox('save', duplicated, callback)
	}
    })
}

Desktop.prototype.makeBankBox = function(el, trigger) {
    var self = this
    el.bankBox({
	trigger: trigger,
 	windowManager: this.windowManager,
	list: self.pedalboardListFunction,
	search: self.pedalboardSearchFunction,
	load: function(callback) {
	    $.ajax({ url: '/banks',
		     success: callback,
		     error: function() {
			 new Bug("Couldn't load banks")
		     },
		     cache: false,
		     dataType: 'json',
		   })
	},
	save: function(data, callback) {
	    $.ajax({ type: 'POST',
		     url: '/banks/save',
		     data: JSON.stringify(data),
		     success: callback,
		     error: function() {
			 new Bug("Couldn't save banks")
		     },
		   })
	    if (!AUTO_CLOUD_BACKUP)
		return
	    $.ajax({ url: SITEURL + '/banks/backup/' + self.userSession.sid,
		     method: 'POST',
		     data: JSON.stringify(data)
		   })
	}
    })
}

Desktop.prototype.reset = function(callback) {
    if (this.pedalboardModified)
	if (!confirm("There are unsaved modifications that will be lost. Are you sure?"))
	    return
    this.pedalboardId = null
    this.title = ''
    this.pedalboardModified = false
    this.pedalboard.pedalboard('reset', callback)
}

Desktop.prototype.saveCurrentPedalboard = function(asNew, callback) {
    var self = this
    self.pedalboard.pedalboard('serialize', 
			       function(pedalboard) {
				   self.saveBox.saveBox('save', self.title, asNew, pedalboard, self.userSession.sid,
							function(uid, title) {
							    self.pedalboardId = uid
							    self.title = title
							    self.titleBox.text(title)
							    self.pedalboardModified = false
							    new Notification("info", 
									     sprintf('Pedalboard "%s" saved', title),
									     2000)
							    if (callback)
								callback()
							})
			       })
}

JqueryClass('saveBox', {
    init: function(options) {
	var self = $(this)

	options = $.extend({
	    save: function(title, asNew, callback) { callback(true) }
	}, options)

	self.data(options)

	var save = function() {
	    self.saveBox('send')
	    return false
	}

	self.find('.js-save').click(save)
	self.find('.js-cancel-saving').click(function() {
	    self.hide()
	    return false
	})
	self.keydown(function(e) {
	    if (e.keyCode == 13)
		return save()
	    else if (e.keyCode == 27) {
		self.hide()
		return false
	    }
	})

	return self
    },

    save: function(title, asNew, serialized, sessionId, callback) {
	var self = $(this)
	self.find('input').val(title)
	self.data('asNew', asNew)
	self.data('serialized', serialized)
	self.data('sid', sessionId)
	self.data('callback', callback)
	if (title && !asNew)
	    self.saveBox('send')
	else
	    self.saveBox('edit')
    },

    edit: function() {
	var self = $(this)
	self.find('input').focus()
	self.show()
    },

    send: function() {
	var self = $(this)
	var title = self.find('input').val()
	var asNew = self.data('asNew')

	self.data('save')(title, asNew,
			  function(id, error) {
			      if (id) {
				  self.hide()
				  self.data('callback')(id, title)
				  // Now make automatic backup at cloud
				  var pedalboard = self.data('serialized')
				  var sid = self.data('sid')
				  self.data('serialized', null)
				  if (!AUTO_CLOUD_BACKUP)
				      return
				  $.ajax({ url: SITEURL + '/pedalboard/backup/' + sid,
					   method: 'POST',
					   data: { id: id,
						   title: title,
						   pedalboard: JSON.stringify(pedalboard)
						 },
					 })
			      }
			      else {
				  // TODO error handling here, the Notification does not work well
				  // with popup
				  alert(error)
			      }
			  })
	return
    }

})

JqueryClass('statusTooltip', {
    init: function() {
	var self = $(this)
	var tooltip = $('<div class="tooltip">').appendTo($('body'))
	$('<div class="arrow">').appendTo(tooltip)
	$('<div class="text">').appendTo(tooltip)
	tooltip.hide()
	self.data('tooltip', tooltip)
	self.bind('mouseover', function() { self.statusTooltip('showTooltip') })
	self.bind('mouseout', function() { 
	    tooltip.stop().animate({ opacity: 0 }, 200,
				   function() { 
				       $(this).hide() 
				   }) 
	})
	tooltip.css('right', $(window).width() - self.position().left - self.width())
	return self
    },

    status: function(status) {
	var self = $(this)
	if (self.data('status'))
	    self.removeClass(self.data('status'))
	self.data('status', status)
	self.addClass(status)
    },

    message: function(message, silent) {
	var self = $(this)
	var oldMsg = self.data('message')
	self.data('message', message)
	if (!silent && oldMsg != message)
	    self.statusTooltip('showTooltip', 1500)
    },

    showTooltip: function(timeout) {
	var self = $(this)
	if (!self.data('message'))
	    return
	var tooltip = self.data('tooltip')
	tooltip.find('.text').html(self.data('message'))
	tooltip.show().stop().animate({ opacity: 1 }, 200)
	if (timeout)
	    setTimeout(function() { 
		tooltip.stop().animate({ opacity: 0 }, 200,
				       function() { $(this).hide() })
	    }, timeout)
    }
})
