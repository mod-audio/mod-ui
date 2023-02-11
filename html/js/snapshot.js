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

function SnapshotsManager(options) {
    var self = this;

    options = $.extend({
        pedalPresetsWindow: $('<div>'),
        pedalPresetsList: $('<div>'),
        pedalPresetsOverlay: $('<div>'),
        renamedCallback: function (name) {},
        hardwareManager: null,
        canFeedback: true,
        currentlyAddressed: false,
        editingElem: null,
        presetCount: 0,
    }, options)

    $('body').keydown(function (e) {
        if (e.keyCode == 27) { // esc
            self.hideRenameOverlay()
            options.pedalPresetsWindow.hide()
        }
    })

    options.pedalPresetsOverlay
    .hide()
    .blur(self.pedalPresetRenamed)
    .keydown(function (e) {
        if (e.keyCode == 27) { // esc
            return self.hideRenameOverlay()
        }
        if (e.keyCode == 13) { // enter
            return self.pedalPresetRenamed()
        }
        return true
    })

    options.pedalPresetsWindow.keyup(function (e) {
        if (e.keyCode == 38 || e.keyCode == 40) { // up and down the list
            options.pedalPresetsList.find('option:selected').click()
            return false
        }
        return true
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
        var selectedHtml = selected.html()
        var name = selectedHtml.substring(selectedHtml.indexOf(".") + 1);

        options.pedalPresetsOverlay.css({
            position: "absolute",
            width: selected.width()+2,
            height: selected.height()+2,
            top: selected.position().top,
            left: selected.position().left
        }).prop("value", name).show().focus()

        return false
    })

    options.pedalPresetsWindow.find('.js-delete').click(function (e) {
        self.hideRenameOverlay()

        var selected = options.pedalPresetsList.find('option:selected')
        var selectId = selected.val()

        if (options.presetCount <= 1) {
            return self.prevent(e, "Cannot delete last remaining snapshot")
        } else if (options.currentlyAddressed) {
            return self.prevent(e)
        }

        $.ajax({
            url: '/snapshot/remove',
            type: 'GET',
            data: {
                id: selectId,
            },
            success: function () {
                selected.remove()
                options.renamedCallback()
                options.pedalPresetsWindow.find('.js-delete').addClass('disabled')

                options.presetCount -= 1
                if (options.presetCount <= 1) {
                    options.pedalPresetsWindow.find('.js-assign-all').addClass('disabled')
                }

                // Replace options value and text so we can a sequential list 0, 1, 2, etc.
                var i = 0
                options.pedalPresetsList.children().each(function(option) {
                  var optionHtml = $(this).html()
                  var prtitle = optionHtml.substring(optionHtml.indexOf(".") + 1)
                  $(this).html((i+1) + "." + prtitle)
                  $(this).val(i)
                  i++
                })
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
            return self.prevent(e, "Cannot assign list with only 1 snapshot")
        }

        var port = {
            name: 'Snapshots',
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

    this.start = function (currentId, currentlyAddressed, canFeedback) {
        // clear old entries
        options.pedalPresetsList.find('option').remove()

        // save state
        options.canFeedback = canFeedback
        options.currentlyAddressed = currentlyAddressed

        self.getPedalPresetList(function (presets) {
            options.presetCount = Object.keys(presets).length

            if (options.presetCount == 0) {
                return new Notification("error", "No pedalboard snapshots available")
            }

            if (options.presetCount <= 1) {
                options.pedalPresetsWindow.find('.js-assign-all').addClass('disabled')
            } else {
                options.pedalPresetsWindow.find('.js-assign-all').removeClass('disabled')
            }

            if (options.currentlyAddressed) {
                options.pedalPresetsWindow.find('.js-delete').addClass('disabled')
                options.pedalPresetsWindow.find('.js-rename').addClass('disabled')
            } else {
                if (options.presetCount <= 1) {
                    options.pedalPresetsWindow.find('.js-delete').addClass('disabled')
                } else {
                    options.pedalPresetsWindow.find('.js-delete').removeClass('disabled')
                }
                options.pedalPresetsWindow.find('.js-rename').removeClass('disabled')
            }

            // add new ones
            for (var i in presets) {
                var elem = $('<option value="'+i+'">'+(parseInt(i)+1)+"."+presets[i]+'</option>')

                if (currentId == i && ! options.currentlyAddressed) {
                    elem.prop('selected', 'selected')
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
        new Notification("warn", customMessage || "Cannot change snapshots while addressed to hardware", 3000)
        return false
    }

    this.optionClicked = function (e) {
        self.hideRenameOverlay()

        var selectId = $(this).val()

        var selectedHtml = $(this).html()
        var prtitle = selectedHtml.substring(selectedHtml.indexOf(".") + 1)

        if (options.currentlyAddressed) {
            if (!options.canFeedback) {
                options.pedalPresetsList.find('option:selected').removeProp('selected')
                return self.prevent(e)
            }
        } else if (options.presetCount > 1) {
            options.pedalPresetsWindow.find('.js-delete').removeClass('disabled')
        }

        $.ajax({
            url: '/snapshot/load',
            type: 'GET',
            data: {
                id: selectId,
            },
            success: function () {
                new Notification("info", "Snapshot " + prtitle + " loaded", 2000)
            },
            error: function () {},
            cache: false,
        })
    }

    this.hideRenameOverlay = function () {
        options.editingElem = null
        options.pedalPresetsOverlay.prop("value","").hide()
        return false
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
            url: '/snapshot/rename',
            type: 'GET',
            data: {
                id   : prId,
                title: text,
            },
            success: function (resp) {
                if (!resp.ok) {
                    return
                }
                elem.html((parseInt(prId)+1) + "." + resp.title)
                options.renamedCallback(resp.title)
            },
            error: function () {},
            cache: false,
        })

        return false
    }

    this.getPedalPresetList = function (callback) {
        $.ajax({
            url: '/snapshot/list',
            type: 'GET',
            success: function (resp) {
                callback(resp)
            },
            error: function () {
                new Bug("Failed to get pedalboard snapshot list")
            },
            cache: false,
            dataType: 'json'
        })
    }
}
