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

function RegistrationWindow(options) {
    var self = this;

    var SITEURLNEW = "http://social.dev.portalmod.com"

    options = $.extend({
        registrationWindow: $('<div>'),
    }, options)

    options.registrationWindow.find('.js-close').click(function () {
        self.close()
    })

    this.registrationCallback = function () {};

    this.start = function (callback) {
        self.registrationCallback = callback
        options.registrationWindow.show()
    }

    this.close = function () {
        self.form[0].reset()
        options.registrationWindow.hide()
    }

    this.form = options.registrationWindow.find('form')
    this.form.submit(function (event) {
        event.preventDefault()
        options.registrationWindow.find('.error').hide()
        var user_id = $(this).find('input[name=user_id]').val()
        var name    = $(this).find('input[name=name]').val()
        var pass1 = $(this).find('input[name=password]').val()
        var pass2 = $(this).find('input[name=password2]').val()
        var email = $(this).find('input[name=email]').val()
        if (!self.validateRequiredFields())
            return
        if (!self.validateEmail(email))
            return
        if (!self.validatePassword(pass1, pass2))
            return
        $.ajax({
            url: SITEURLNEW + '/api/auth/users',
            method: 'POST',
            data: $(this).serialize(),
            headers : { 'Content-Type' : 'application/json' },
            success: function (result) {
                if (!result.ok) {
                    self.error(result.error)
                    return
                }
                self.close()
                self.registrationCallback(result)
            },
            error: function (error) {
                new Notification('error', 'Could not register user: ' + error.statusText)
            },
            dataType: 'json'
        })
    })

    this.validatePassword = function (pass1, pass2) {
        if (pass1.length < 6) {
            return self.error('Password must be at least 6 characters long')
        }
        if (pass1 != pass2) {
            return self.error('Passwords do not match')
        }
        return true
    }

    this.validateRequiredFields = function () {
        var required = {
            'email': 'E-mail',
            'name': 'Name',
            'user_id': 'User ID'
        }
        for (var field in required) {
            if (!self.form.find('input[name=' + field + ']').val())
                return self.error(required[field] + ' is required')
        }
        return true
    }

    this.validateEmail = function (email) {
        var re = /^(([^<>()[\]\\.,;:\s@\"]+(\.[^<>()[\]\\.,;:\s@\"]+)*)|(\".+\"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
        if (!re.test(email))
            return self.error('You must provide a valid e-mail address')
        return true
    }

    this.error = function (message) {
        options.registrationWindow.find('.error').show().html(message)
        return false
    }
}
