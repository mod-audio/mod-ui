// SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
// SPDX-License-Identifier: AGPL-3.0-or-later

JqueryClass('tone3000Box', {
    init: function (options) {
        var self = $(this)

        options = $.extend({
            isMainWindow: true,
            windowName: "Tone3000",
        }, options)

        self.data(options)
        self.window(options)
    },
})
