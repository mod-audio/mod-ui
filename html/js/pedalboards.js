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

function PedalboardSearcher(opt) {
    var self = this

    this.mode = opt.mode
    this.searchbox = opt.searchbox
    this.searchbutton = opt.searchbutton
    this.cleanResults = opt.cleanResults
    this.render = opt.render
    this.skipBroken = opt.skipBroken

    this.searchbox.cleanableInput()

    this.list = function () {
        self.cleanResults()
        opt.list(function (pedalboards) {
            for (var i in pedalboards) {
                if (opt.skipBroken && pedalboards[i].broken)
                    continue;
                self.render(pedalboards[i], '')
            }
        })

    }
    this.lastKeyUp = null
    this.search = function () {
        if (self.lastKeyUp != null) {
            clearTimeout(self.lastKeyUp)
            self.lastKeyUp = null
        }
        var query = self.searchbox.val()
        var local = self.mode == 'installed'

        if (query.length == 0)
            return self.list()

        self.cleanResults()

        opt.search(local, query,
            function (pedalboards, url) {
                self.cleanResults()
                for (var i in pedalboards) {
                    if (opt.skipBroken && pedalboards[i].broken)
                        continue;
                    self.render(pedalboards[i], url)
                }
            }
        )
    }

    this.searchbox.keydown(function (e) {
        if (e.keyCode == 13) { //detect enter
            self.search()
            return false
        } else if (e.keyCode == 8 || e.keyCode == 46) { //detect delete and backspace
            if (self.lastKeyUp != null) {
                clearTimeout(self.lastKeyUp)
            }
            self.lastKeyUp = setTimeout(function () {
                self.search()
            }, 400)
        }
    })
    this.searchbox.keypress(function (e) { // keypress won't detect delete and backspace but will only allow inputable keys
        if (e.which == 13) {
            return
        }
        if (self.lastKeyUp != null) {
            clearTimeout(self.lastKeyUp)
        }
        self.lastKeyUp = setTimeout(function () {
            self.search()
        }, 400)
    })

    if (this.searchbutton)
        this.searchbutton.click(function () {
            self.search()
            return false
        })
}


/*
 * pedalboardBox
 *
 * The interface for managing your pedal boards
 *
 * Properties:
 * - searchbox: dom of search's input
 * - searchbutton: dom
 * - resultCanvas: dom div in which results will be shown
 * - results: dictionary containing detailed data of all plugins
 *            displayed
 */

JqueryClass('pedalboardBox', {
    init: function (options) {
        var self = $(this)

        options = $.extend({
            resultCanvas: self.find('.js-pedalboards'),
            list: function (callback) {
                callback([])
            },
            search: function (local, query, callback) {
                callback([])
            },
            remove: function (pedalboard, callback) {
                callback()
            },
            load: function (bundlepath, broken, callback) {
                callback()
            },
            isMainWindow: true,
            windowName: "Pedalboards",
        }, options)

        self.data(options)

        var results = {}
        self.data('results', results)

        var searcher = new PedalboardSearcher($.extend({
            searchbox: self.find('input[type=search]'),
            searchbutton: self.find('button.search'),
            mode: 'installed',
            skipBroken: false,
            render: function (pedalboard, url) {
                self.pedalboardBox('showPedalboard', pedalboard)
            },
            cleanResults: function () {
                self.data('resultCanvas').html('')
                self.data('results', {})
            }
        }, options))

        self.data('searcher', searcher)

        options.open = function () {
            searcher.search()
            return false
        }

        self.window(options)

        self.find('.js-close').click(function () {
            self.window('close')
        })

        return self
    },

    mode: function (mode) {
        var self = $(this)
        self.find('.js-mode').removeClass('current')
        self.find('#js-mode-' + mode).addClass('current')
        var searcher = self.data('searcher')
        searcher.mode = mode
        searcher.search()
    },

    showPedalboard: function (pedalboard) {
        var self = $(this)
        var results = self.data('results')
        var canvas = self.data('resultCanvas')
        self.pedalboardBox('render', pedalboard, canvas)
        results[pedalboard.bundle] = pedalboard
    },

    render: function (pedalboard, canvas) {
        var self = $(this)

        var metadata = {
            title: pedalboard.title,
            broken: pedalboard.broken ? "broken" : ""
        };

        var rendered = $(Mustache.render(TEMPLATES.pedalboard, metadata))

        rendered.click(function () {
            self.data('load')(pedalboard.bundle, pedalboard.broken, function () {
                self.window('close')
            })
            return false
        })

        if (pedalboard.bundle == DEFAULT_PEDALBOARD) {
            rendered.find('.js-remove').hide()
        } else {
            rendered.find('.js-remove').click(function (e) {
                self.data('remove')(pedalboard, function () {
                    rendered.remove()
                })
                e.stopPropagation();
                return false
            })
        }

        canvas.append(rendered)

        wait_for_pedalboard_screenshot(pedalboard.bundle, function (resp) {
            var img = rendered.find('.img');

            if (resp.ok)
            {
                img.css({backgroundImage: "url(/pedalboard/image/thumbnail.png?bundlepath="+
                                            escape(pedalboard.bundle)+"&tstamp="+resp.ctime+")"});
                img.addClass("loaded");
            }
            else
            {
                img.addClass("broken");
            }
        })

        return rendered
    }
})



/*
 * pedalboardsModeSelector
 *
 * Takes a pedalboard canvas and select between grid and list mode
 */
JqueryClass('pedalboardsModeSelector', {
    init: function (canvas) {
        var self = $(this)
        self.find('.grid').click(function () {
            self.children().removeClass('selected')
            $(this).addClass('selected')
            canvas.removeClass('list-selected')
            canvas.addClass('grid-selected')
        })
        self.find('.list').click(function () {
            self.children().removeClass('selected')
            $(this).addClass('selected')
            canvas.removeClass('grid-selected')
            canvas.addClass('list-selected')
        })
    }
})
