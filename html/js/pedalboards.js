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
    this.lastKeyTimeout = null
    this.search = function () {
        if (self.lastKeyTimeout != null) {
            clearTimeout(self.lastKeyTimeout)
            self.lastKeyTimeout = null
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
        if (e.keyCode == 13) { // detect enter
            self.search()
            return false
        } else if (e.keyCode == 8 || e.keyCode == 46) { // detect delete and backspace
            if (self.lastKeyTimeout != null) {
                clearTimeout(self.lastKeyTimeout)
            }
            self.lastKeyTimeout = setTimeout(function () {
                self.search()
            }, 400)
        }
    })
    this.searchbox.keypress(function (e) { // keypress won't detect delete and backspace but will only allow inputable keys
        if (e.which == 13) {
            return
        }
        if (self.lastKeyTimeout != null) {
            clearTimeout(self.lastKeyTimeout)
        }
        self.lastKeyTimeout = setTimeout(function () {
            self.search()
        }, 400)
    })
    this.searchbox.on('paste', function(e) {
        if (self.lastKeyTimeout != null) {
            clearTimeout(self.lastKeyTimeout)
        }
        self.lastKeyTimeout = setTimeout(function () {
            self.search()
        }, 400);
    })

    if (this.searchbutton) {
        this.searchbutton.click(function () {
            self.search()
            return false
        })
    }
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
            resultCanvasUser: self.find('.js-user-pedalboards'),
            resultCanvasFactory: self.find('.js-factory-pedalboards'),
            viewModes: self.find('.view-modes'),
            viewModeList: self.find('#view-mode-list'),
            viewModeGrid: self.find('#view-mode-grid'),
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
            saveConfigValue: function (key, value, callback) {
                callback([])
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
                self.data('resultCanvasUser').html('')
                self.data('resultCanvasFactory').html('')
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

        options.viewModes.pedalboardsModeSelector(options.resultCanvasUser,
                                                  options.resultCanvasFactory,
                                                  options.saveConfigValue)

        return self
    },

    initViewMode: function (viewMode) {
        var self = $(this)
        if (viewMode === 'list') {
            self.data('resultCanvasUser').addClass('list-selected')
            self.data('resultCanvasFactory').addClass('list-selected')
            self.data('viewModeList').addClass('selected')
            self.data('viewModeGrid').removeClass('selected')
        } else { // grid or no value yet (grid is default)
            self.data('viewModeGrid').addClass('selected')
        }
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
        var canvas = pedalboard.factory ? self.data('resultCanvasFactory') : self.data('resultCanvasUser')
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

        if (pedalboard.factory || pedalboard.bundle == DEFAULT_PEDALBOARD) {
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

        wait_for_pedalboard_screenshot(pedalboard.bundle, pedalboard.version, function (resp) {
            var img = rendered.find('.img');

            if (resp.ok)
            {
                img.css({backgroundImage: "url(/pedalboard/image/thumbnail.png?bundlepath="+
                                            escape(pedalboard.bundle)+"&tstamp="+resp.ctime+"&v="+pedalboard.version+")"});
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
    init: function (canvasUser, canvasFactory, saveConfigValue) {
        var self = $(this)
        self.click(function () {
            // self.toggleClass('icon-th-1')
            // self.toggleClass('icon-th-list')
            // save view mode in user preferences
            var viewModeList = self.find('#view-mode-list')
            var viewModeGrid = self.find('#view-mode-grid')
            var newViewMode = viewModeList.hasClass('selected') ? 'grid' : 'list'
            saveConfigValue('pb-view-mode', newViewMode, function () {
              canvasUser.toggleClass('list-selected')
              canvasFactory.toggleClass('list-selected')
              viewModeList.toggleClass('selected')
              viewModeGrid.toggleClass('selected')
            })
        })

    }
})
