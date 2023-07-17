// SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
// SPDX-License-Identifier: AGPL-3.0-or-later

function WaitMessage(canvas) {
    var self = this

    this.plugins = {}

    self.block = $('<div class="screen-loading blocker">')
    self.block.hide()
    var anim = $("#loading").clone();
    anim.attr("id", null);
    self.block.append(anim);
    self.msg = $('<p class="block-message">');
    self.block.append(self.msg);
    $('body').append(self.block).css('overflow', 'hidden')

    this.start = function (message) {
        this.msg.text(message);
        $('#wrapper').css('z-index', -1)
        self.block.show(250)
    }

    this.stop = function () {
        self.block.hide(250)
        $('#wrapper').css('z-index', 'auto')
    }

    this.stopIfNeeded = function () {
        if (Object.keys(self.plugins).length == 0) {
            self.stop()
        }
    }

    this.startPlugin = function (instance, position) {
        var div = $('<div class="plugin-wait">')
        div.width(position.width).height(position.height)
        div.css({
            position: 'absolute',
            top: position.y,
            left: position.x
        })
        canvas.append(div)
        self.plugins[instance] = div
    }

    this.stopPlugin = function (instance, stopIfZero) {
        if (self.plugins[instance]) {
            self.plugins[instance].remove()
            delete self.plugins[instance]
        }

        if (stopIfZero && Object.keys(self.plugins).length == 0) {
            self.stop()
        }
    }
}
