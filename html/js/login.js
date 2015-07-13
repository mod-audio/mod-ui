/*
 * Copyright 2012-2013 AGR Audio, Industria e Comercio LTDA. <contato@moddevices.com>
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
 * The authentication has the following steps: (NOTE: work in progress, this has changed now)
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

    var OFFLINE      = 0 // Cloud haven't been reached yet, maybe no network
    var CONNECTING   = 1 // Trying to reach cloud and get a session id
    var ONLINE       = 2 // Device has been identified
    var LOGGED       = 3 // User has been identified and is logged at this device
    var DISCONNECTED = 4 // Device was not recognized by Cloud, communication suspended

    this.status        = OFFLINE
    this.user_id       = null
    this.access_token  = null
    this.refresh_token = null

    options = $.extend({
        offline: function () {},
        connecting: function () {},
        online: function () {},
        login: function () {},
        logout: function () {},
        disconnected: function () {},
        notify: function (message) {
            new Notification('error', message)
        },
        loginWindow: $('<div>'),
        loginButton: $("#mod-social-network-header .menu ul li.login"),
        logoutButton: $("#mod-social-network-header .menu ul li.logout")
    }, options)

    this.tryConnectingToSocial = function () {
        self.setStatus(CONNECTING)

        // get data from mod-ui
        $.ajax({
            url: '/tokens/get',
            type: 'GET',
            success: function (resp) {
                if (!resp.ok) {
                    self.setStatus(OFFLINE)
                    return
                }

                // see if the cloud is working
                $.ajax({
                    url: SITEURLNEW + '/auth/tokens',
                    method: 'PUT',
                    headers: { /*'Authorization': 'MOD ' + resp.access_token,*/
                               'Content-Type' : 'application/json'
                    },
                    data: JSON.stringify({
                        refresh_token: resp.refresh_token
                    }),
                    success: function (resp2) {
                        self.user_id       = resp2.user_id
                        self.access_token  = resp2.access_token
                        self.refresh_token = resp2.refresh_token
                        self.setStatus(LOGGED)

                        // update the refresh token in mod-ui
                        $.ajax({
                            url: '/tokens/save/',
                            type: 'POST',
                            headers: { 'Content-Type' : 'application/json' },
                            data: JSON.stringify(resp2),
                            dataType: 'json'
                        })

                    },
                    error: function (e) {
                        self.setStatus(OFFLINE)
                        self.notify("Could not contact cloud")
                    },
                    dataType: 'json'
                })

            },
            error: function () {
                self.setStatus(OFFLINE)
                self.notify("Communication with mod-ui failed")
            },
            dataType: 'json'
        })
    }

    this.login = function (callback) {
        if (self.status === LOGGED) {
            return callback()
        }
        options.loginWindow.window('open')
        self.loginCallback = callback
    };

    options.loginWindow.find('form').on('submit', function (event) {
        event.preventDefault();
        options.loginWindow.find('.error').hide()

        // get values
        var user_id  = $(this).find('input[name=user_id]').val()
        var password = $(this).find('input[name=password]').val()

        // clear password entry
        $(this).find('input[type=password]').val('')

        // log in
        self.tryLogin(user_id, password)
    });

    options.loginWindow.find('.js-close').on('click', function () {
        options.loginWindow.find('.error').hide()
        options.loginWindow.find('input[type=text]').val('')
        options.loginWindow.find('input[type=password]').val('')
        options.loginWindow.window('close')
    })

    options.loginWindow.find('#register').click(function () {
        options.loginWindow.hide()
        options.registration.start(function (data) {
            self.tryLogin(data.user_id, data.password)
        })
    })

    this.getUserData = function (user_id, callback) {
        if (user_id == null)
            user_id = self.user_id
        //if (user_id == null)
        //    return

        $.ajax({
            url: SITEURLNEW + '/users/' + user_id,
            headers : { 'Authorization' : 'MOD ' + self.access_token },
            success: function (data) {
                callback(data)
            },
            error: function (e) {
                console.log("Error: can't get user data for " + user_id)
            },
            dataType: 'json'
        })
    }

    this.tryLogin = function (user_id, password) {
        self.setStatus(CONNECTING)

        $.ajax({
            url: SITEURLNEW + '/auth/tokens',
            method: 'POST',
            headers : { 'Content-Type' : 'application/json' },
            data: JSON.stringify({
                user_id: user_id,
                password: password
            }),
            success: function (resp) {
                // make sure the cloud server sent us the correct user data
                if (resp.user_id != user_id) {
                    self.setStatus(OFFLINE)
                    self.notify("User ID mismatch")
                    return
                }

                // send data to mod-ui, saving for next time
                $.ajax({
                    url: '/tokens/save/',
                    type: 'POST',
                    headers : { 'Content-Type' : 'application/json' },
                    data: JSON.stringify(resp),
                    success: function (uiresp) {
                        self.user_id       = resp.user_id
                        self.access_token  = resp.access_token
                        self.refresh_token = resp.refresh_token
                        options.loginWindow.window('close')
                        self.setStatus(LOGGED)
                        if (self.loginCallback) {
                            self.loginCallback()
                            self.loginCallback = null
                        }
                    },
                    error: function () {
                        self.setStatus(OFFLINE)
                        self.notify("Communication with mod-ui failed")
                    },
                    dataType: 'json'
                })

            },
            error: function (resp) {
                self.setStatus(OFFLINE)
                self.notify("Could not get token from server")
            },
            dataType: 'json'
        })
    }

    this.logout = function () {
        // tell mod-ui to delete tokens
        $.ajax({ url: '/tokens/delete' })

        self.user_id       = null
        self.access_token  = null
        self.refresh_token = null
        options.logoutButton.hide()
        options.loginButton.show()
        options.logout()
        self.setStatus(OFFLINE)
    }

    this.setStatus = function (status) {
        if (status == self.status)
            return
        self.status = status
        switch (status) {
        case OFFLINE:
            options.offline();
            break;
        case CONNECTING:
            options.connecting();
            break;
        case ONLINE:
            options.online();
            break;
        case LOGGED:
            options.loginButton.hide()
            options.logoutButton.show()
            options.login();
            break;
        case DISCONNECTED:
            options.disconnected();
            break;
        }
    }

    this.notify = options.notify
}
