// SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
// SPDX-License-Identifier: AGPL-3.0-or-later

var WINDOWMANAGER = null;

function WindowManager() {
    var self = this

    WINDOWMANAGER = self

    this.windows = []

    this.register = function (window) {
        self.windows.push(window)

        window.bind('windowopen', function () {
            self.closeWindows(window, true)
        })
    }

    this.closeWindows = function (window, forced) {
        for (var i = 0; i < self.windows.length; i++) {
            var win = self.windows[i]
            // Close window if not current and forced or not main and current window is not plugin info modal opened from cloud-plugins-library tab
            if (win != window && (forced || ! win.data('isMainWindow')) && !(win.selector === '#cloud-plugins-library' && window && window.hasClass('plugin-info'))) {
                win.window('close')
            }
        }
    }

    $(document).bind('keydown', function (e) {
        if (e.keyCode == 27) {
            self.closeWindows()
        }
    })
}

(function ($) {
    /*
     * window
     */

    var methods = {
        init: function (options) {
            var self = $(this)

            options = $.extend({
                isMainWindow: false,
                windowName: "Unknown",
                windowManager: WINDOWMANAGER
            }, options)

            var trigger = options.trigger
            self.data('trigger', trigger)
            self.data('isMainWindow', options.isMainWindow)
            self.data('windowName', options.windowName)

            if (options.open) {
                self.bind('windowopen', options.open)
            }
            if (options.close) {
                self.bind('windowclose', options.close)
            }
            if (options.preopen) {
                self.data('preopen', options.preopen)
            }

            self.hide()

            self.data('initialized', true)
            options.windowManager.register(self)

            self.find('.js-close').click(function () {
                self.window('close')
                return false
            })

            if (trigger) {
                trigger.removeClass('selected')

                trigger.click(function () {
                    self.window('toggle')
                })
            }

            //self.click(function() { return false })

            // TODO this shouldn't be too hardcoded
            self.data('defaultIcon', $('#mod-plugins'))

            return self
        },

        open: function (closure, force) {
            var self = $(this)

            if (!force && self.data('preopen')) {
                self.data('preopen')(function () {
                    self.window('open', closure, true)
                })
                return
            }

            if (!self.data('initialized'))
                self.window()

            if (closure) {
                self.bind('windowopen', closure)
                return
            }

            self.window('unfade')

            if (self.is(':visible'))
                return

            self.css('z-index', 1000)
            self.show()
            self.trigger('windowopen')

            var trigger = self.data('trigger')
            if (trigger) {
                trigger.addClass('selected')
                self.data('defaultIcon').removeClass('selected')
            }
        },

        close: function (closure) {
            var self = $(this)
            if (closure) {
                self.bind('windowclose', closure)
                return
            }
            if (!self.is(':visible'))
                return

            self.hide()

            var trigger = self.data('trigger')
            if (trigger) {
                trigger.removeClass('selected')
                self.data('defaultIcon').addClass('selected')
            }

            self.trigger('windowclose')
        },

        toggle: function () {
            var self = $(this)
            if (self.is(':visible')) {
                if (self == self.data('defaultIcon'))
                    self.window('close')
            }
            else
                self.window('open')
        },

        fade: function () {
            var self = $(this)
            if (self.is(':visible'))
                self.animate({
                    opacity: 0.1
                }, 400)
        },

        unfade: function () {
            var self = $(this)
            if (self.is(':visible'))
                self.animate({
                    opacity: 1
                }, 400)
            else
                self.css('opacity', 1)
        }
    }

    $.fn.window = function (method) {
        if (methods[method]) {
            return methods[method].apply(this, Array.prototype.slice.call(arguments, 1));
        } else if (typeof method === 'object' || !method) {
            return methods.init.apply(this, arguments);
        } else {
            $.error('Method ' + method + ' does not exist on jQuery.window');
        }
    }
})(jQuery);

//to open link in a new window

jQuery('a[target^="_new"]').click(function() {
    return openWindow(this.href);
})


function openWindow(url) {

    if (window.innerWidth <= 640) {
        // if width is smaller then 640px, create a temporary a elm that will open the link in new tab
        var a = document.createElement('a');
        a.setAttribute("href", url);
        a.setAttribute("target", "_blank");

        var dispatch = document.createEvent("HTMLEvents");
        dispatch.initEvent("click", true, true);

        a.dispatchEvent(dispatch);
    }
    else {
        var width = window.innerWidth * 0.66 ;
        // define the height in
        var height = width * window.innerHeight / window.innerWidth ;
        // Ratio the hight to the width as the user screen ratio
        window.open(url , 'newwindow', 'width=' + width + ', height=' + height + ', top=' + ((window.innerHeight - height) / 2) + ', left=' + ((window.innerWidth - width) / 2));
    }
    return false;
}
