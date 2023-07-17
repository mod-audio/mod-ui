// SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
// SPDX-License-Identifier: AGPL-3.0-or-later

/* The method below is already implemented in modgui.js.
 * The reason it's there and not here is because  modgui.js is a standalone implementation
 * of modgui LV2 standards and should not depend of anything from this package (it's also used in modsdk)
 * We kept it commented here because this is where it used to belong, and it's weird to have this so core
 * function being declared only in modgui.js.
 */
/*
function JqueryClass(name, methods) {
    (function($) {
	$.fn[name] = function(method) {
	    if (methods[method]) {
		return methods[method].apply(this, Array.prototype.slice.call(arguments, 1));
	    } else if (typeof method === 'object' || !method) {
		return methods.init.apply(this, arguments);
	    } else {
		$.error( 'Method ' +  method + ' does not exist on jQuery.' + name );
	    }
	}
    })(jQuery);
}
*/

(function ($) {
    $.fn.cleanableInput = function (options) {
        var self = $(this)
        var remove = $('<span class="input-clean"></span>')
        remove.insertAfter(self)

        var position = function () {
            remove.show()
/*            remove.css('left', self.position().left + self.width() - 3)
            remove.css('top', self.position().top + self.height() - 22)
*/        }

        remove.click(function () {
            self.val('')
            remove.hide()
            self.trigger('keypress')
        })

        if (self.val().length == 0)
            remove.hide()
        else
            position()

        self.keyup(function () {
            if (self.val().length > 0)
                position()
            else
                remove.hide()
        })

    }
})(jQuery);

(function ($) {
    $.extend($.expr[":"], {
        scrollable: function (element) {
            var vertically_scrollable, horizontally_scrollable;
            if ($(element).css('overflow') == 'scroll' || $(element).css('overflowX') == 'scroll' || $(element).css('overflowY') == 'scroll') return true;

            vertically_scrollable = (element.clientHeight < element.scrollHeight) && (
                $.inArray($(element).css('overflowY'), ['scroll', 'auto']) != -1 || $.inArray($(element).css('overflow'), ['scroll', 'auto']) != -1);

            if (vertically_scrollable) return true;

            horizontally_scrollable = (element.clientWidth < element.scrollWidth) && (
                $.inArray($(element).css('overflowX'), ['scroll', 'auto']) != -1 || $.inArray($(element).css('overflow'), ['scroll', 'auto']) != -1);
            return horizontally_scrollable;
        }
    });
})(jQuery)

function setCookie(name, value, days) {
    if (days) {
        var date = new Date();
        date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
        var expires = "; expires=" + date.toGMTString();
    } else var expires = "";
    document.cookie = name + "=" + value + expires + "; path=/";
}

function getCookie(c_name, defaultValue) {
    if (document.cookie.length > 0) {
        c_start = document.cookie.indexOf(c_name + "=");
        if (c_start != -1) {
            c_start = c_start + c_name.length + 1;
            c_end = document.cookie.indexOf(";", c_start);
            if (c_end == -1) {
                c_end = document.cookie.length;
            }
            return unescape(document.cookie.substring(c_start, c_end));
        }
    }
    if (defaultValue)
        return defaultValue
    return "";
}

function compareVersions(a, b, len) {
    if (!a && !b) {
        return 0
    }
    if (!b) {
        return 1
    }
    if (!a) {
        return -1
    }
    if (! len) {
        len = 4
    }
    for (var i = 0; i < len; i++) {
        if (a[i] > b[i]) {
            return 1
        }
        if (a[i] < b[i]) {
            return -1
        }
    }
    return 0
}

function renderTime(time) {
    var months = ['Jan',
        'Feb',
        'Mar',
        'Apr',
        'May',
        'Jun',
        'Jul',
        'Aug',
        'Sep',
        'Oct',
        'Nov',
        'Dec'
    ]
    return sprintf('%s %02d %02d:%02d',
        months[time.getMonth()],
        time.getDate(),
        time.getHours(),
        time.getMinutes())
}

function remove_from_array(array, element) {
    var index = array.indexOf(element)
    if (index > -1)
        array.splice(index, 1)
}

var pending_pedalboard_screenshots = []

function wait_for_pedalboard_screenshot(bundlepath, version, callback) {
    // allow to cache request if no screenshot is being currently generated
    var cache = pending_pedalboard_screenshots.indexOf(bundlepath) < 0;

    $.ajax({
        url: "/pedalboard/image/check?bundlepath="+escape(bundlepath)+'&v='+version.toString(),
        success: function (resp) {
            if (resp.status == 1) {
                // success
                remove_from_array(pending_pedalboard_screenshots, bundlepath)
                callback({'ok':true,'ctime':resp.ctime})
                return
            }

            if (resp.status == 0) {
                // pending
                setTimeout(function() {
                    wait_for_pedalboard_screenshot(bundlepath, version, callback)
                }, 1000)
                return
            }

            // error
            callback({'ok':false})

        },
        error: function () {
            callback({'ok':false})
        },
        cache: cache,
        global: false,
        dataType: 'json'
    })
}
