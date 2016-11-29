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

function PedalboardPresetsManager(options) {
    var self = this;

    options = $.extend({
        pedalPresetsWindow: $('<div>'),
        pedalPresetsList: $('<div>'),
        hardwareManager: null,
    }, options)

    options.pedalPresetsWindow.keydown(function (e) {
        if (e.keyCode == 27) { // esc
            options.pedalPresetsWindow.hide()
            return false
        }
    })

    options.pedalPresetsWindow.keyup(function (e) {
        if (e.keyCode == 38 || e.keyCode == 40) { // up and down the list
            options.pedalPresetsList.find('option:selected').click()
            return false
        }
    })

    options.pedalPresetsWindow.find('.js-cancel').click(function () {
        options.pedalPresetsWindow.hide()
        return false
    })

    options.pedalPresetsWindow.find('.js-rename').click(function () {
        // TODO
        var selected = options.pedalPresetsList.find('option:selected')
        console.log(selected.text())
        alert("Not implemented yet")
        return false
    })

    options.pedalPresetsWindow.find('.js-delete').click(function (e) {
        var selected = options.pedalPresetsList.find('option:selected')
        var selectId = selected.val()

        if (selectId == 0) {
            var img = $('<img>').attr('src', 'img/icn-blocked.png')
            $('body').append(img)
            img.css({
                position: 'absolute',
                top: e.pageY - img.height() / 2,
                left: e.pageX - img.width() / 2,
                zIndex: 99999
            })
            setTimeout(function () {
                img.remove()
            }, 500)
            return false
        }

        // TODO - show prevent icon for index 0

        $.ajax({
            url: '/pedalpreset/remove',
            type: 'GET',
            data: {
                id: selected.val(),
            },
            success: function () {
                console.log("deleted preset")
                selected.remove()
                options.pedalPresetsList.find('option')[0].click()
            },
            error: function () {},
            cache: false,
        })
        console.log(this)
        // TODO
        return false
    })

    options.pedalPresetsWindow.find('.js-assign').click(function () {
        // TODO
        console.log(this)
        return false
    })

    options.pedalPresetsWindow.find('.js-assign-all').click(function () {
        var port = {
            name: 'Presets',
            symbol: ':presets',
            ranges: {
                minimum: -1,
                maximum: 0,
                default: -1,
            },
            comment: "",
            designation: "",
            properties: ["enumeration", "integer"],
            value: -1,
            format: null,
            scalePoints: [],
        }
        options.hardwareManager.open("/pedalboard", port, "Pedalboard")
        options.pedalPresetsWindow.hide()
        return false
    })

    this.start = function (current) {
        // clear old entries
        options.pedalPresetsList.find('option').remove()

        self.getPedalPresetList(function (presets) {
            if (presets.length == 0) {
                return new Notification("info", "No pedalboard presets available")
            }

            // add new ones
            for (var i in presets) {
                var elem = $('<option value="'+i+'">'+presets[i]+'</option>')

                if (current == i) {
                    elem.prop('selected','selected')
                    if (i == 0) {
                        options.pedalPresetsWindow.find('.js-delete').addClass('disabled')
                    }
                }

                elem.click(self.optionClicked)
                elem.appendTo(options.pedalPresetsList)
            }

            options.pedalPresetsWindow.show()

            options.pedalPresetsWindow.focus()
            options.pedalPresetsWindow.find('.preset-list').focus()
        })
    }

    this.optionClicked = function () {
        var selectId = $(this).val()

        if (selectId == 0) {
            options.pedalPresetsWindow.find('.js-delete').addClass('disabled')
        } else {
            options.pedalPresetsWindow.find('.js-delete').removeClass('disabled')
        }

        $.ajax({
            url: '/pedalpreset/load',
            type: 'GET',
            data: {
                id: selectId,
            },
            success: function () {
                console.log("loaded preset")
            },
            error: function () {},
            cache: false,
        })
    }

    this.getPedalPresetList = function (callback) {
        $.ajax({
            url: '/pedalpreset/list',
            type: 'GET',
            success: function (resp) {
                callback(resp)
            },
            error: function () {
                new Bug("Failed to get pedalboard preset list")
            },
            cache: false,
            dataType: 'json'
        })
    }
}
