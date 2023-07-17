// SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
// SPDX-License-Identifier: AGPL-3.0-or-later

function NetworkStatus(options) {
    var self = this

    options = $.extend({
        icon: $('<div>'),
        frequency: 5000,
        notify: function (msg) {
            console.log(msg)
        },
    }, options)

    var icon = options.icon
    var frequency = options.frequency

    this.timedOutPhase = 0

    this.ping = function () {
        if (pb_loading) {
            setTimeout(self.ping, frequency)
            return
        }
        var start = Date.now()
        $.ajax({
            url: '/ping',
            cache: false,
            global: false,
            success: function (resp) {
                if (self.timedOutPhase >= 2) {
                    location.reload()
                    return
                } else {
                    self.timedOutPhase = 0
                }

                if (icon.is(':visible')) {
                    var time = Date.now() - start - resp.ihm_time
                    self.status(true, time, resp.ihm_time)
                }

                setTimeout(self.ping, frequency)
            },
            error: function (resp, error) {
                if (resp.status == 0)
                {
                    var loading = $('.screen-loading').is(':visible')

                    if (document.readyState != "complete" || $.active != 0 || loading || isInstallingPackage)
                    {
                        self.timedOutPhase = 0
                    }
                    else
                    {
                        if (error == "timeout") {
                            switch (self.timedOutPhase) {
                            case 1:
                                desktop.blockUI()
                                // fall-through
                            case 0:
                                console.log("Connection timed out")
                                self.timedOutPhase++;
                                break;
                            }
                        } else if (error == "error") {
                            self.timedOutPhase = 3
                        }
                    }
                }
                self.status(false)
                setTimeout(self.ping, frequency)
            },
            dataType: 'json',
            timeout: frequency,
        })
    }

    this.status = function (online, network_time, ihm_time) {
        var msg
        if (online) {
            if (ihm_time == 0) {
                msg = sprintf('Network: %dms', network_time)
            } else {
                msg = sprintf('Network: %dms | Controller: %dms', network_time, ihm_time)
            }
        } else {
            msg = 'OFFLINE'
        }

        options.notify(msg)
    }

    this.ping()
}
