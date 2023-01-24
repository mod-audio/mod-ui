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
            waitForScreenshot: function (generate, bundlepath, callback) {
                callback(true)
            },
        }, options)

        self.data(options)
        self.data('bundlepath', '')
        self.data('recordedData', null)
        self.data('recordTimeout', null)
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
        self.find('.js-cancel').click(function () {
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
                self.find('#share-tooltip').css('opacity',1).find('.tooltip-inner').html('Copied to clipboard')
            } else {
                console.log('Unable to copy to clipboard.')
                self.find('#share-tooltip').css('opacity',1).find('.tooltip-inner').html('Press Ctrl/Cmd + C to copy')
            }

            setTimeout(function() {
                self.find('#share-tooltip').css('opacity',0)
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
                self.find('#record-step-' + i).show()
            else
                self.find('#record-step-' + i).hide()
        }
        var button = self.find('#record-share')
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
        self.find('#record-countdown').text(secs)

        var recordTimeout = setTimeout(function () {
            self.shareBox('recordCountdown', secs - 1)
        }, 1000)
        self.data('recordTimeout', recordTimeout)
    },
    recordStopCountdown: function (secs) {
        var self = $(this)
        self.data('stopTimeout', null)
        if (secs == 0)
            return self.shareBox('recordStop')
        self.shareBox('showStep', 3)
        self.find('#record-stop').text(secs)
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
            return _callback(false)
        } else if (status == RECORDING) {
            var timeout = self.data('stopTimeout')
            if (timeout)
                clearTimeout(timeout)
            self.data('recordStop')(function () {
                self.data('status', STOPPED)
                self.shareBox('showStep', 4)
                self.find('#record-play').show()
                self.find('#record-play-stop').hide()
                _callback(true)
            })
        } else { // PLAYING
            self.data('playStop')(function () {
                self.find('#record-play').removeClass('playing')
                self.data('status', STOPPED)
                _callback(true)
            })
        }
    },
    recordPlay: function () {
        var self = $(this)
        var play = function () {
            self.data('playStart')(function () {
                self.find('#record-play').hide()
                self.find('#record-play-stop').show()
                self.data('status', PLAYING)
            }, function () {
                self.find('#record-play').show()
                self.find('#record-play-stop').hide()
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
        self.find('#record-share').attr('disabled', true)

        var hasAudio = (step == 4)
        var shareNow = function (data) {
            self.find('#record-rec').addClass("disabled").attr('disabled', true)
            self.find('#record-stop').addClass("disabled").attr('disabled', true)
            self.find('#record-play').addClass("disabled").attr('disabled', true)
            self.find('#record-play-stop').addClass("disabled").attr('disabled', true)
            self.find('#record-again').addClass("disabled").attr('disabled', true)
            self.find('#record-delete').addClass("disabled").attr('disabled', true)

            self.find('#share-wait-message').show().text("Uploading. Please wait...")

            self.shareBox('recordStop', function () {
                self.data('share')(data, function (resp) {
                    self.find('#record-rec').removeClass("disabled").attr('disabled', false)
                    self.find('#record-stop').removeClass("disabled").attr('disabled', false)
                    self.find('#record-play').removeClass("disabled").attr('disabled', false)
                    self.find('#record-play-stop').removeClass("disabled").attr('disabled', false)
                    self.find('#record-again').removeClass("disabled").attr('disabled', false)
                    self.find('#record-delete').removeClass("disabled").attr('disabled', false)

                    if (resp.ok) {
                        self.find('#record-step-' + step).hide()
                        self.find('#record-share').attr('disabled', resp.ok).hide()
                        self.find('#share-wait-message').hide()

                        var pb_url = PEDALBOARDS_URL + "/pedalboards/" + resp.id
                        self.find('#share-window-url').attr('value', pb_url)
                        self.find('#share-window-fb').attr('href', "https://www.facebook.com/sharer/sharer.php?u="+pb_url)
                        self.find('#share-window-tw').attr('href', "https://twitter.com/intent/tweet?source="+pb_url)

                        if (hasAudio) {
                            self.data('recordReset')(function () {
                                self.find('#share-window-form').hide()
                                self.find('#share-window-links').show()
                            })
                        } else {
                            self.find('#share-window-form').hide()
                            self.find('#share-window-links').show()
                        }
                    } else {
                        new Notification('error', "Couldn't share pedalboard: " + resp.error)
                        self.find('#record-share').attr('disabled', false)
                        self.find('#share-wait-message').show().text("Upload failed!")
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

    open: function (bundlepath, title, stable) {
        var self = $(this)

        self.find('#record-share').show()
        self.find('#share-window-form').show()
        self.find('#share-window-links').hide()
        self.shareBox('showStep', 1)
        self.data('bundlepath', bundlepath)
        self.data('screenshotDone', false)
        self.find('#pedalboard-share-title').val(title)
        self.find('#record-share').attr('disabled', true)
        self.find('#share-wait-message').show().text("Waiting for screenshot...")
        self.find('.js-share').addClass('disabled')
        self.find('textarea').val('').focus()
        if (stable) {
            self.find('.unstable-warning').hide();
        } else {
            self.find('.unstable-warning').show();
        }
        self.show()

        var done = function () {
            self.data('screenshotDone', true)
            self.find('#share-wait-message').hide()
            self.shareBox('showStep', self.data('step'))
        }

        self.data('waitForScreenshot')(false, bundlepath, function (ok) {
            if (ok) {
                done()
                return
            }
            // 2nd try
            self.find('#share-wait-message').show().text("Generating screenshot...")
            self.data('waitForScreenshot')(true, bundlepath, function (ok) {
                if (ok) {
                    done()
                    return
                }
                // 3rd and final try
                self.find('#share-wait-message').show().text("Generating for screenshot... (final attempt)")
                self.data('waitForScreenshot')(true, bundlepath, function (ok) {
                    // shit! just upload without screenshot then.. :(
                    self.find('#share-wait-message').show().text("Generating for screenshot... failed!")
                    done()
                })
            })
        })
    },

    close: function () {
        var self = $(this)

        var recordTimeout = self.data('recordTimeout')
        if (recordTimeout) {
            clearTimeout(recordTimeout)
            self.data('recordTimeout', null)
        }

        self.shareBox('recordStop', function (resetNeeded) {
            if (! resetNeeded) {
                self.hide()
                return
            }
            self.data('recordReset')(function () {
                self.hide()
            })
        })
    }

})
