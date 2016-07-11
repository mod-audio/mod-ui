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

var STOPPED = 0
var RECORDING = 1
var PLAYING = 2

var RECORD_COUNTDOWN = 3
var RECORD_LENGTH = 60

JqueryClass('shareBox', {
    init: function (options) {
        var self = $(this)

        options = $.extend({
            recordStart: function (callback) {
                callback()
            },
            recordStop: function (callback) {
                callback()
            },
            playStart: function (startCallback, stopCallback) {
                startCallback();
                setTimeout(stopCallback, 3000)
            },
            playStop: function (callback) {
                callback()
            },
            recordDownload: function (callback) {
                callback({})
            },
            recordReset: function (callback) {
                callback()
            },
            share: function (data, callback) {
                callback({ok:true})
            },
            waitForScreenshot: function (generate, callback) {
                callback(true)
            },
        }, options)

        self.data(options)
        self.data('bundlepath', '')
        self.data('recordedData', null)
        self.data('status', STOPPED)
        self.data('step', 0)
        self.data('screenshotDone', false)

        self.find('#record-rec').click(function () {
            if (! $(this).hasClass("disabled")) {
                self.shareBox('recordStartCountdown');
            }
            return false
        })
        self.find('#record-stop').click(function () {
            self.shareBox('recordStop');
            return false
        })
        self.find('#record-play').click(function () {
            self.shareBox('recordPlay');
            return false
        })
        self.find('#record-play-stop').click(function () {
            self.shareBox('recordStop');
            return false
        })
        self.find('#record-again').click(function () {
            self.shareBox('recordStartCountdown');
            return false
        })
        self.find('#record-delete').click(function () {
            self.shareBox('recordDelete');
            return false
        })
        self.find('#record-cancel').click(function () {
            self.shareBox('close');
            return false
        })
        self.find('#record-share').click(function () {
            self.shareBox('share');
            return false
        })

        self.find('#share-window-url-btn').click(function () {
            self.find('#share-window-url').select()

            var ok
            try {
                ok = document.execCommand('copy')
            } catch (err) {
                ok = false
            }

            if (ok) {
                $('#share-tooltip').css('opacity',1).find('.tooltip-inner').html('Copied to clipboard')
            } else {
                console.log('Unable to copy to clipboard.')
                $('#share-tooltip').css('opacity',1).find('.tooltip-inner').html('Press Ctrl/Cmd + C to copy')
            }

            setTimeout(function() {
                $('#share-tooltip').css('opacity',0)
            }, 2000)
        })

        $('body').keydown(function (e) {
            if (e.keyCode == 27)
                self.shareBox('close')
        })
    },

    showStep: function (step) {
        var self = $(this)
        self.data('step', step)
        for (var i = 1; i < 5; i++) {
            if (i == step)
                $('#record-step-' + i).show()
            else
                $('#record-step-' + i).hide()
        }
        var button = $('#record-share')
        if (step == 1) {
            button.text('Just share').attr('disabled', !self.data('screenshotDone'))
        } else {
            button.text('Share')
            if (step == 4)
                button.attr('disabled', !self.data('screenshotDone'))
            else
                button.attr('disabled', true)
        }
    },

    recordStartCountdown: function () {
        var self = $(this)
        var status = self.data('status')
        var start = function () {
            self.data('recordedData', null)
            self.shareBox('recordCountdown', RECORD_COUNTDOWN)
        }
        if (status == STOPPED) {
            start()
        } else if (status == PLAYING) {
            self.shareBox('recordStop', start)
        }
    },
    recordCountdown: function (secs) {
        var self = $(this)
        self.shareBox('showStep', 2)
        if (secs == 0) {
            self.data('status', RECORDING)
            self.data('recordStart')(function () {
                self.shareBox('recordStopCountdown', RECORD_LENGTH)
            })
            return
        }
        $('#record-countdown').text(secs)
        setTimeout(function () {
            self.shareBox('recordCountdown', secs - 1)
        }, 1000)
    },
    recordStopCountdown: function (secs) {
        var self = $(this)
        self.data('stopTimeout', null)
        if (secs == 0)
            return self.shareBox('recordStop')
        self.shareBox('showStep', 3)
        $('#record-stop').text(secs)
        var timeout = setTimeout(function () {
            self.shareBox('recordStopCountdown', secs - 1)
        }, 1000)
        self.data('stopTimeout', timeout)
    },
    recordStop: function (callback) {
        var self = $(this)
        var status = self.data('status')
        var _callback = callback || function () {}
        if (status == STOPPED) {
            return _callback()
        } else if (status == RECORDING) {
            var timeout = self.data('stopTimeout')
            if (timeout)
                clearTimeout(timeout)
            self.data('recordStop')(function () {
                self.data('status', STOPPED)
                self.shareBox('showStep', 4)
                $('#record-play').show()
                $('#record-play-stop').hide()
                _callback()
            })
        } else { // PLAYING
            self.data('playStop')(function () {
                self.find('#record-play').removeClass('playing')
                self.data('status', STOPPED)
                _callback()
            })
        }
    },
    recordPlay: function () {
        var self = $(this)
        var play = function () {
            self.data('playStart')(function () {
                $('#record-play').hide()
                $('#record-play-stop').show()
                self.data('status', PLAYING)
            }, function () {
                $('#record-play').show()
                $('#record-play-stop').hide()
                self.data('status', STOPPED)
            })
        }
        var status = self.data('status')
        if (status == STOPPED)
            play()
        else
            self.shareBox('recordStop', play)
    },

    recordDelete: function () {
        var self = $(this)
        self.data('recordReset')(function () {
            self.shareBox('showStep', 1)
        })
    },

    share: function () {
        var self = $(this)
        var step = self.data('step')
        var data = {
            bundlepath : self.data('bundlepath'),
            name       : self.find('#pedalboard-share-name').val(),
            email      : self.find('#pedalboard-share-email').val(),
            description: self.find('#pedalboard-share-comment').val(),
            title      : self.find('#pedalboard-share-title').val()
        }
        $('#record-share').attr('disabled', true)

        var hasAudio = (step == 4)
        var shareNow = function (data) {
            self.find('#record-rec').addClass("disabled").attr('disabled', true)
            self.find('#record-stop').addClass("disabled").attr('disabled', true)
            self.find('#record-play').addClass("disabled").attr('disabled', true)
            self.find('#record-play-stop').addClass("disabled").attr('disabled', true)
            self.find('#record-again').addClass("disabled").attr('disabled', true)
            self.find('#record-delete').addClass("disabled").attr('disabled', true)

            self.shareBox('recordStop', function () {
                self.data('share')(data, function (resp) {
                    self.find('#record-rec').removeClass("disabled").attr('disabled', false)
                    self.find('#record-stop').removeClass("disabled").attr('disabled', false)
                    self.find('#record-play').removeClass("disabled").attr('disabled', false)
                    self.find('#record-play-stop').removeClass("disabled").attr('disabled', false)
                    self.find('#record-again').removeClass("disabled").attr('disabled', false)
                    self.find('#record-delete').removeClass("disabled").attr('disabled', false)

                    if (resp.ok) {
                        $('#record-step-' + step).hide()
                        $('#record-share').attr('disabled', resp.ok).hide()

                        var pb_url = PEDALBOARDS_URL + "/pedalboards/" + resp.id
                        $('#share-window-url').attr('value', pb_url)
                        $('#share-window-fb').attr('href', "https://www.facebook.com/sharer/sharer.php?u="+pb_url)
                        $('#share-window-tw').attr('href', "https://twitter.com/intent/tweet?source="+pb_url)

                        if (hasAudio) {
                            self.data('recordReset')(function () {
                                $('#share-window-form').hide()
                                $('#share-window-links').show()
                            })
                        } else {
                            $('#share-window-form').hide()
                            $('#share-window-links').show()
                        }
                    } else {
                        new Notification('error', "Couldn't share pedalboard: " + resp.error)
                        $('#record-share').attr('disabled', false)
                    }
                })
            })
        }

        if (hasAudio) {
            // User has recorded some sound
            self.data('recordDownload')(function (audioData) {
                data.audio = audioData.audio
                shareNow(data)
            })
        } else {
            // Just share without audio
            shareNow(data)
        }
    },

    open: function (bundlepath, title, uris) {
        var self = $(this)

        $('#record-share').show()
        $('#share-window-form').show()
        $('#share-window-links').hide()
        self.shareBox('showStep', 1)
        self.data('bundlepath', bundlepath)
        self.data('screenshotDone', false)
        self.find('#pedalboard-share-title').val(title)
        self.find('#record-share').attr('disabled', true)
        self.find('#share-wait-screenshot').show().text("Waiting for screenshot...")
        self.find('.js-share').addClass('disabled')
        self.find('textarea').val('').focus()
        self.show()

        var done = function () {
            self.data('screenshotDone', true)
            self.find('#share-wait-screenshot').hide()
            self.shareBox('showStep', self.data('step'))
        }

        self.data('waitForScreenshot')(false, function (ok) {
            if (ok) {
                done()
                return
            }
            // 2nd try
            self.find('#share-wait-screenshot').text("Generating screenshot...")
            self.data('waitForScreenshot')(true, function (ok) {
                if (ok) {
                    done()
                    return
                }
                // 3rd and final try
                self.find('#share-wait-screenshot').text("Generating for screenshot... (final attempt)")
                self.data('waitForScreenshot')(true, function (ok) {
                    // shit! just upload without screenshot then.. :(
                    self.find('#share-wait-screenshot').text("Generating for screenshot... failed!")
                    done()
                })
            })
        })
    },

    close: function () {
        var self = $(this)
        self.shareBox('recordStop', function () {
            self.data('recordReset')(function () {
                self.hide()
            })
        })
    }

})
