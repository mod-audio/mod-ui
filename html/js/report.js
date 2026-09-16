// SPDX-FileCopyrightText: 2026 MOD Audio UG
// SPDX-License-Identifier: AGPL-3.0-or-later

/*
 * "Report a problem"
 *
 * Collects what the Web UI knows about this device and the current session
 * into a block of text, and points the user at the forum topic for the
 * running release so they can paste it there as a reply.
 *
 * Nothing is sent anywhere by itself: the user copies the text and posts it.
 * The device serial and logs are deliberately not included; QA can ask for
 * them in the thread.
 *
 * Used by index.html (with pedalboard and DSP stats) and settings.html
 * (system details only).
 */

function ProblemReport(options) {
    var self = this

    options = $.extend({
        version: '',          // OS version string as shown in Settings
        feedbackUrl: '',      // forum topic (or category) for this release
        getPedalboard: null,  // function () -> { title: '', plugins: [uri, ...] } or null
        getStats: null,       // function () -> { xruns: n, cpuLoad: n } or null
    }, options)

    this.window = null
    this.textarea = null

    var TEMPLATE = [
        '**What happened**',
        '',
        '',
        '**Steps to reproduce**',
        '1. ',
        '',
        '**Expected**',
        '',
        '',
    ].join('\n')

    this.build = function () {
        if (self.window) {
            return
        }
        var win = $('<div id="report-window" class="save-popup mod-hidden"></div>')
        var box = $('<div class="box"></div>').appendTo(win)
        box.append('<h1 class="pull-left">Report a problem</h1><span class="js-cancel close">&times;</span>')
        box.append('<div class="clearfix"></div>')
        box.append('<p>Describe the problem in the text below, then copy it and paste it as a reply in the forum topic for this release. ' +
                   'The system details are filled in for you.</p>')
        self.textarea = $('<textarea id="report-text" rows="18" spellcheck="false"></textarea>').appendTo(box)
        var actions = $('<div class="actions"></div>').appendTo(box)
        actions.append('<span id="report-copied" class="mod-hidden">Copied to clipboard</span> ')
        actions.append('<input type="button" id="report-copy" value="Copy to clipboard"> ')
        actions.append('<a id="report-open-forum" target="_blank" rel="noopener">Open the forum topic</a> ')
        actions.append('<input type="button" class="js-cancel" value="Close">')

        win.find('#report-open-forum').attr('href', options.feedbackUrl)

        win.find('.js-cancel').click(function () {
            self.close()
            return false
        })
        win.find('#report-copy').click(function () {
            self.copy()
            return false
        })
        $('body').keydown(function (e) {
            if (e.keyCode == 27) {
                self.close()
            }
        })

        $('body').append(win)
        self.window = win
    }

    this.open = function () {
        self.build()
        self.textarea.val(TEMPLATE + '\n\nCollecting system details...')
        self.window.show()

        $.ajax({
            url: '/system/info',
            method: 'GET',
            cache: false,
            global: false,
            dataType: 'json',
            success: function (info) {
                self.textarea.val(TEMPLATE + '\n' + self.render(info))
            },
            error: function () {
                self.textarea.val(TEMPLATE + '\n' + self.render(null))
            },
        })
    }

    this.close = function () {
        if (self.window) {
            self.window.hide()
        }
    }

    this.copy = function () {
        self.textarea.select()
        var ok
        try {
            ok = document.execCommand('copy')
        } catch (err) {
            ok = false
        }
        var note = self.window.find('#report-copied')
        note.text(ok ? 'Copied to clipboard' : 'Press Ctrl/Cmd + C to copy').show()
        setTimeout(function () { note.hide() }, 2500)
    }

    function formatUptime(seconds) {
        if (seconds === null || seconds === undefined) {
            return 'unknown'
        }
        var h = Math.floor(seconds / 3600)
        var m = Math.floor((seconds % 3600) / 60)
        return h + 'h ' + m + 'm'
    }

    this.render = function (info) {
        info = info || {}
        var lines = []
        lines.push('```')
        lines.push('OS release:    ' + (info.release || options.version || 'unknown') +
                   (info.sysdate ? '  (built ' + info.sysdate + ')' : ''))
        lines.push('Device:        ' + (info.hwname || 'unknown') +
                   ' / ' + (info.platform || '?') + ' / ' + (info.bin_compat || '?') +
                   (info.model ? ' / ' + info.model : ''))
        lines.push('Controller fw: ' + (info.controller || 'unknown'))
        if (info.uname) {
            lines.push('Kernel:        ' + info.uname.release)
        }
        lines.push('Uptime:        ' + formatUptime(info.uptime))

        var stats = options.getStats ? options.getStats() : null
        if (stats) {
            lines.push('Xruns:         ' + (stats.xruns === null ? 'unknown' : stats.xruns) +
                       '   DSP load: ' + (stats.cpuLoad === null ? 'unknown' : stats.cpuLoad + '%'))
        }

        var pb = options.getPedalboard ? options.getPedalboard() : null
        if (pb) {
            lines.push('Pedalboard:    "' + pb.title + '" (' + pb.plugins.length + ' plugins)')
            for (var i = 0; i < pb.plugins.length; i++) {
                lines.push('  - ' + pb.plugins[i])
            }
        }

        lines.push('Web UI at:     ' + window.location.host)
        lines.push('Browser:       ' + navigator.userAgent)
        lines.push('```')
        return lines.join('\n')
    }
}
