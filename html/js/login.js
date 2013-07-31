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

/*
 * The authentication has the following steps:
 * 
 * 1 - Get a session id (sid) from cloud
 * 
 * 2 - Send the sid to device, get the device serial number and signed sid
 * 
 * 3 - Send the signed sid to cloud. If device is already assigned to a user,
 *     user data is received and login is done.
 * 
 * 4 - Application calls method login() when authorization is needed. If user
 *     is not logged, an authentication window will open
 * 
 * 5 - Login and password is sent to server. The response will be a package containing
 *     user data signed by server
 *
 * 6 - The package is sent to device, that will confirm server signature
 *
 * Now the session id can be used to identify this user + device pair.
 */

 function UserSession(options) {
    var self = this

    var OFFLINE = 0
    var CONNECTING = 1
    var ONLINE = 2
    var LOGGED = 3

    this.status = OFFLINE

    options = $.extend({
        offline: function() {},
        connecting: function() {},
        online: function() {},
        login: function() {},
        logout: function() {},
	loginWindow: $('<div>')
    }, options)

    this.getSessionId = function() {
        self.setStatus(CONNECTING)
        $.ajax({
            url: SITEURL+'/login/start_session',
            type: 'GET',
            success: function(sid) {
                self.sid = sid
                self.signSession()
            },
            error: function(e) {
                self.setStatus(OFFLINE)
            },
            dataType: 'json'
        })
    }

    this.signSession = function() {
        $.ajax({ url: '/login/sign_session/'+self.sid,
           success: function(signature) {
               self.identifyDevice(signature)
           },
           error: function() {
               new Notification('error', 'Could not start authentication')
           },
           dataType: 'json'
       })
    }

    this.identifyDevice = function(signature) {
        $.ajax({
            url: SITEURL+'/login/identify_device',
            data: signature,
            type: 'GET',
            success: function(status) {
                if (!status.device_auth) {
                    self.setStatus(OFFLINE)
                    return new Notification('error', 'This device cannot be identified, please contact support')
                }
                if (status.user_auth)
                    self.identifyUser(status.user, status.signature, new Function())
                else
                    self.setStatus(ONLINE)
            },
            error: function() {
                self.setStatus(OFFLINE)
            },
            dataType: 'json'
        });
    }

    this.login = function(callback) {
        if (self.status === LOGGED) {
            return callback()
        } else if (self.status < ONLINE) {
            return new Notification('error', 'Device is offline')
        }
	options.loginWindow.window('open')
	self.loginCallback = callback
    };

     options.loginWindow.find('form').on('submit', function(event) {
	 event.preventDefault();
	 options.loginWindow.find('.error').hide()
	 data = $(this).serialize()
	 $(this).find('input[type=password]').val('')
	 $.ajax({ url: SITEURL+'/login/authenticate/' + self.sid,
		  method: 'POST',
		  data: data,
		  success: function(resp) {
		      if (!resp.ok) {
			  options.loginWindow.find('.error').text('Invalid password').show()
			  return
		      }
		      self.identifyUser(resp.user, resp.signature, function(ok) {
			  if (ok) {
			      if (self.loginCallback) {
				  self.loginCallback()
				  self.loginCallback = null
			      }
			  } else {
			      new Notification('error', 'Security error: server sent invalid data')
			  }
		      })
		  },
		  error: function(resp) {
		      return new Notification('error', "Error authenticating")
		  },
		  dataType: 'json'
		})
     });

     options.loginWindow.find('.js-close').on('click', function() {
	 options.loginWindow.find('.error').hide()
	 options.loginWindow.find('input[type=text]').val('')
	 options.loginWindow.find('input[type=password]').val('')
	 options.loginWindow.window('close')
     })
     
     this.identifyUser = function(user, signature, callback) {
	$.ajax({ url: '/login/authenticate',
		 method: 'POST',
		 data: { user: user, signature: signature },
		 success: function(resp) {
		     if (resp.ok) {
			 self.user = self.treatUserData(resp.user)
			 options.loginWindow.window('close')
			 callback(true)
			 self.setStatus(LOGGED)
		     } else {
			 callback(false)
		     }
		 },
		 error: function(resp) {
		     new Notification('error', "Could not verify authentication data received from server")
		 },
		 dataType: 'json'
	       })
     }

    this.logout = function() {
        $.ajax({ 'url': SITEURL + '/logout/' + self.sid,
            success: function() {
                self.sid = null
                options.logout()
		self.getSessionId()
            },
            error: function() {
                return new Notification('error', 'Could not logout')
            }
        })
    }

    this.setStatus = function(status) {
        if (status == self.status)
            return
        self.status = status
        switch(status) {
            case OFFLINE:
            options.offline(); break;
            case CONNECTING:
            options.connecting(); break;
            case ONLINE:
            options.online(); break;
            case LOGGED:
            options.login()
        }
    }

     this.treatUserData = function(user) {
	 if (user.first_name) {
	     user.name = user.first_name
	     if (user.last_name)
		 user.name += ' ' + user.last_name
	 } else
	     user.name = user.username
	 return user
     }

}