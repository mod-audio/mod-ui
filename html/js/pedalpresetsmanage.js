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
        pedalPresetsOverlay: $('<div>'),
        renamedCallback: function (name) {},
        hardwareManager: null,
        currentlyAddressed: false,
        editingElem: null,
        presetCount: 0,
    }, options)

    options.pedalPresetsOverlay.hide().blur(self.pedalPresetRenamed).keydown(function (e) {
        if (e.keyCode == 13) { // enter
            return self.pedalPresetRenamed()
        }
    })

    options.pedalPresetsWindow.keydown(function (e) {
        if (e.keyCode == 27) { // esc
            self.hideRenameOverlay()
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
        self.hideRenameOverlay()
        options.pedalPresetsWindow.hide()
        return false
    })

    options.pedalPresetsWindow.find('.js-rename').click(function (e) {
        if (options.currentlyAddressed) {
            return self.prevent(e)
        }
        if (options.editingElem != null) {
            console.log("Note: rename click ignored")
            return false
        }

        var selected = options.editingElem = options.pedalPresetsList.find('option:selected')

        options.pedalPresetsOverlay.css({
            position: "absolute",
            width: selected.width()+2,
            height: selected.height()+2,
            top: selected.position().top,
            left: selected.position().left
        }).prop("value", selected.html()).show().focus()

        return false
    })

    options.pedalPresetsWindow.find('.js-delete').click(function (e) {
        self.hideRenameOverlay()

        var selected = options.pedalPresetsList.find('option:selected')
        var selectId = selected.val()

        if (selectId == 0) {
            return self.prevent(e, "Cannot delete initial preset")
        } else if (options.currentlyAddressed) {
            return self.prevent(e)
        }

        $.ajax({
            url: '/pedalpreset/remove',
            type: 'GET',
            data: {
                id: selectId,
            },
            success: function () {
                selected.remove()
                options.pedalPresetsList.find('option:first').prop('selected','selected').click()

                options.presetCount -= 1
                if (options.presetCount <= 1) {
                    options.pedalPresetsWindow.find('.js-assign-all').addClass('disabled')
                }
            },
            error: function () {},
            cache: false,
        })

        return false
    })

    options.pedalPresetsWindow.find('.js-assign').click(function () {
        self.hideRenameOverlay()

        // TODO
        console.log(this)
        return false
    })

    options.pedalPresetsWindow.find('.js-assign-all').click(function (e) {
        self.hideRenameOverlay()

        if ($(this).hasClass("disabled")) {
            return self.prevent(e, "Cannot assign list with only 1 preset")
        }

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

    this.start = function (currentId, currentlyAddressed) {
        // clear old entries
        options.pedalPresetsList.find('option').remove()

        // save state
        options.currentlyAddressed = currentlyAddressed

        self.getPedalPresetList(function (presets) {
            options.presetCount = Object.keys(presets).length

            if (options.presetCount == 0) {
                return new Notification("error", "No pedalboard presets available")
            }

            if (options.presetCount == 1) {
                options.pedalPresetsWindow.find('.js-assign-all').addClass('disabled')
            } else {
                options.pedalPresetsWindow.find('.js-assign-all').removeClass('disabled')
            }

            if (options.currentlyAddressed) {
                options.pedalPresetsWindow.find('.js-delete').addClass('disabled')
                options.pedalPresetsWindow.find('.js-rename').addClass('disabled')
            } else {
                options.pedalPresetsWindow.find('.js-delete').removeClass('disabled')
                options.pedalPresetsWindow.find('.js-rename').removeClass('disabled')
            }

            // add new ones
            for (var i in presets) {
                var elem = $('<option value="'+i+'">'+presets[i]+'</option>')

                if (currentId == i && ! options.currentlyAddressed) {
                    elem.prop('selected', 'selected')
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

    this.prevent = function (e, customMessage) {
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
        new Notification("warn", customMessage || "Cannot change presets while addressed to hardware", 3000)
        return false
    }

    this.optionClicked = function (e) {
        self.hideRenameOverlay()

        var selectId = $(this).val()
        var prtitle  = $(this).html()

        if (options.currentlyAddressed) {
            options.pedalPresetsList.find('option:selected').removeProp('selected')
            return self.prevent(e)
        }

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
                new Notification("info", "Preset " + prtitle + " loaded", 2000)
            },
            error: function () {},
            cache: false,
        })
    }

    this.hideRenameOverlay = function () {
        options.editingElem = null
        options.pedalPresetsOverlay.prop("value","").hide()
    }

    this.pedalPresetRenamed = function () {
        if (options.editingElem == null) {
            console.log("FIXME: bad state reached")
            return false
        }

        var text = options.pedalPresetsOverlay.hide().val()
        var elem = options.editingElem
        var prId = elem.val()

        options.editingElem = null

        if (text == "") {
            return false
        }

        $.ajax({
            url: '/pedalpreset/rename',
            type: 'GET',
            data: {
                id   : prId,
                title: text,
            },
            success: function () {
                elem.html(text)
                options.renamedCallback(text)
            },
            error: function () {},
            cache: false,
        })

        return false
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
