// SPDX-FileCopyrightText: 2012-2026 MOD Audio UG
// SPDX-License-Identifier: AGPL-3.0-or-later

// Per-plugin CPU panel, opened by clicking the CPU bar.
//
// mod-host measures each plugin's worst cycle and pushes "cpu_load <instance> <pct>"
// on the websocket whenever a plugin beats its own record. Peaks, not averages: a
// plugin that averages 5% and spikes to 60% is the one that drops audio, and an
// average hides exactly that. Nothing is polled, here or in mod-host -- reporting is
// switched on while the panel is open and off again when it closes.
//
// Two columns, because "expensive" means two things. The percentage is the plugin's
// share of one audio cycle. What it costs the cycle is different: plugins run on
// parallel jack threads, so one on a branch that finishes early can be costly and
// still free in xrun terms. The biggest consumer is regularly not the one to remove.

function CpuLoadPanel(options) {
    var self = this

    options = $.extend({
        window: $('<div>'),
        list: $('<div>'),
        summary: $('<div>'),
        pedalboard: $('<div>'),
    }, options)

    var CRITICAL_TIP = 'On the longest chain of plugins that wait on each other. ' +
                       'Whatever you save here comes straight off the audio cycle.'

    // instance -> worst share of a cycle seen since monitoring was last reset
    this.peaks = {}
    this.order = []
    this.open_ = false
    this.repaint = null

    // The explanation is long and only wanted once, so it hides behind the (i).
    var help = options.window.find('.cpu-load-help')
    var info = options.window.find('.cpu-load-info')
    info.click(function (e) {
        e.stopPropagation()
        help.toggleClass('mod-hidden')
        info.attr('aria-expanded', help.hasClass('mod-hidden') ? 'false' : 'true')
             .toggleClass('open', !help.hasClass('mod-hidden'))
    })

    this.open = function () {
        if (self.open_) {
            return
        }
        self.open_ = true
        self.peaks = {}
        self.order = []
        options.list.html('<div class="cpu-load-empty">Waiting for the first cycle...</div>')
        options.summary.text('')
        help.addClass('mod-hidden')
        info.attr('aria-expanded', 'false').removeClass('open')
        options.window.removeClass('mod-hidden')
        self.subscribe(1)
    }

    this.close = function () {
        if (! self.open_) {
            return
        }
        self.open_ = false
        self.subscribe(0)
        options.window.addClass('mod-hidden')
    }

    this.toggle = function () {
        if (self.open_) { self.close() } else { self.open() }
    }

    this.subscribe = function (enable) {
        $.ajax({
            url: '/cpu_monitor/' + enable,
            type: 'POST',
            cache: false,
            error: function () {
                if (self.open_) {
                    self.close()
                    new Bug("Could not start plugin CPU monitoring")
                }
            },
        })
    }

    // Enabling again is what clears mod-host's recorded peaks
    this.reset = function () {
        self.peaks = {}
        self.order = []
        options.list.html('<div class="cpu-load-empty">Waiting for the first cycle...</div>')
        self.subscribe(1)
    }

    // One pushed reading. They arrive per plugin as records are beaten, so repaint on a
    // timer rather than per message -- a burst would otherwise redraw the list per row.
    this.setLoad = function (instance, percent) {
        if (! self.open_) {
            return
        }
        self.peaks[instance] = percent
        if (self.repaint === null) {
            self.repaint = setTimeout(function () {
                self.repaint = null
                if (self.open_) { self.render() }
            }, 200)
        }
    }

    // Signal-flow edges between instances, audio only. MIDI connections order the jack
    // graph too, but they do not carry the DSP work, and treating them as dependencies
    // makes the graph look far more serial than it runs.
    //
    // Hardware ports keep their own port path as the node name. Reducing them to their
    // instance would fold capture and playback into one node and invent a loop through
    // the whole pedalboard.
    this.edges = function () {
        var connMgr = options.pedalboard.data('connectionManager')
        var edges = []

        if (!connMgr) {
            return edges
        }

        function node(port) {
            var instance = port.substring(0, port.lastIndexOf("/"))
            return instance === "/graph" ? port : instance
        }

        connMgr.iterate(function (jack) {
            var destination = jack.data('destination')
            if (!destination || !destination.hasClass('mod-audio-input')) {
                return
            }
            var from = node(jack.data('origin').attr('mod-port'))
            var to = node(destination.attr('mod-port'))
            if (from !== to) {
                edges.push([from, to])
            }
        })

        return edges
    }

    // Row order is settled once, while the first readings come in, and then left
    // alone. Peaks creep upward forever, so re-sorting on every update makes
    // near-equal plugins trade places continuously -- motion that carries no
    // information. Values and bars keep updating in place; "Reset peaks" re-ranks.
    this.render = function () {
        var instances = Object.keys(self.peaks)

        if (instances.length === 0) {
            options.list.html('<div class="cpu-load-empty">No plugins loaded</div>')
            options.summary.text('')
            self.order = []
            return
        }

        // a plugin reporting for the first time is still the list filling up
        if (instances.length !== self.order.length) {
            self.order = instances.sort(function (a, b) { return self.peaks[b] - self.peaks[a] })
            self.build()
        }

        var graph = graphSlack(self.peaks, self.edges())
        var total = 0
        var i

        for (i = 0; i < self.order.length; i++) {
            var instance = self.order[i]
            var load = self.peaks[instance]
            var slack = graph.slack[instance]
            var critical = slack !== undefined && slack < 0.01
            var row = options.list.find('.cpu-load-row[mod-instance="' + instance + '"]')

            total += load

            // Scaled against a whole cycle, not against the busiest plugin. Scaling to
            // the busiest means its every new record resizes every other bar, so the
            // whole list twitches when one plugin moves. This way a bar only changes
            // when its own plugin does, and its width means something on its own.
            row.find('.cpu-load-meter').css('width', Math.min(100, load).toFixed(1) + '%')
            row.find('.cpu-load-value').text(load.toFixed(1) + '%')
            row.find('.cpu-load-slack').text(critical ? 'critical path'
                                                      : (slack === undefined ? '' : slack.toFixed(1) + '% spare'))
            row.toggleClass('critical', critical)
            row.attr('title', row.data('name') + ' - ' + load.toFixed(1) + '% of a cycle at worst. ' +
                     (critical ? CRITICAL_TIP
                               : 'Runs in parallel with something slower, and finishes early. It could use ' +
                                 (slack === undefined ? '0' : slack.toFixed(1)) +
                                 '% more CPU before it started making the cycle longer, ' +
                                 'so making it cheaper buys no headroom.'))
        }

        options.summary.html(
            escapeHtml(self.order.length + ' plugins. Worst cycle seen so far for each. ' +
                       'Adding up the longest chain gives ' + graph.critical.toFixed(0) + '% of a cycle, ' +
                       'a worst case that has to stay under 100%.'))
    }

    // Rebuild the rows. Only called when the set of plugins changes, so the list does
    // not flicker while values update.
    this.build = function () {
        var html = '<div class="cpu-load-head">' +
                       '<span class="cpu-load-name">plugin</span>' +
                       '<span class="cpu-load-value">cpu</span>' +
                       '<span class="cpu-load-slack">effect on the audio cycle</span>' +
                   '</div>'
        var names = {}

        for (var i = 0; i < self.order.length; i++) {
            var instance = self.order[i]
            var gui = options.pedalboard.pedalboard('getGui', instance)
            var name = (gui && gui.effect && (gui.effect.label || gui.effect.name)) ||
                       instance.replace('/graph/', '')
            names[instance] = name

            html += '<div class="cpu-load-row" mod-instance="' + escapeHtml(instance) + '">' +
                        '<div class="cpu-load-meter"></div>' +
                        '<span class="cpu-load-name">' + escapeHtml(name) + '</span>' +
                        '<span class="cpu-load-value"></span>' +
                        '<span class="cpu-load-slack"></span>' +
                    '</div>'
        }

        options.list.html(html)
        options.list.find('.cpu-load-row').each(function () {
            var row = $(this)
            row.data('name', names[row.attr('mod-instance')])
        })

        // clicking a row jumps to that plugin on the board
        options.list.find('.cpu-load-row').click(function () {
            var instance = $(this).attr('mod-instance')
            var pedal = $('.mod-pedal[mod-instance="' + instance + '"]')
            if (pedal.length === 0) {
                return
            }
            self.close()
            options.pedalboard.pedalboard('focusPlugin', pedal)
        })
    }

    function escapeHtml(text) {
        return $('<div>').text(text).html()
    }
}
