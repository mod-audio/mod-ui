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

function FeedManager(options) {
    var self = this

    this.handlers = {}

    this.start = function (sid) {
        self.sid = sid
        self.update()
    }

    this.update = function () {
        $.ajax({
            url: SITEURL + '/feed/' + self.sid,
            success: function (events) {
                for (var i = 0; i < events.length; i++) {
                    var handlers = self.handlers[events[i].type]
                    if (handlers == null) {
                        console.log('Error: no handler for ' + events[i].type)
                    } else {
                        for (var j = 0; j < handlers.length; j++) {
                            handlers[j](events[i])
                        }
                    }
                    self.update()
                }
            },
            error: function (e) {
                console.log("Error: can't get feed from cloud: " + e)
                setTimeout(function () {
                    self.update()
                }, 10000)
            },
            dataType: 'json'
        })

    }

    this.bind = function (eventType, handler) {
        if (self.handlers[eventType] == null)
            self.handlers[eventType] = []
        self.handlers[eventType].push(handler)
    }

    for (var eventType in options) {
        self.bind(eventType, options[eventType])
    }
}