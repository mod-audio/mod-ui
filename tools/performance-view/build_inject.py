#!/usr/bin/env python3
"""
Builds performance-inject.js: the performance view as one script you can paste
into the browser console of an unmodified MOD web UI, to try it on a real
device without installing anything. Reload the page to remove it.

    python3 tools/performance-view/build_inject.py > performance-inject.js
"""
import json, os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
css = open(os.path.join(ROOT, 'html/css/performance.css')).read()
js  = open(os.path.join(ROOT, 'html/js/performance.js')).read()

markup = '''<div id="performance-view" style="display:none">
    <div class="performance-stage">
        <div class="performance-track"></div>
        <div class="performance-empty" style="display:none">No plugins on this pedalboard</div>
    </div>
    <div class="performance-strip"></div>
</div>'''

out = '''/*
 * MOD UI performance view: test build.
 *
 * Paste this whole file into the browser console (or run it as a
 * bookmarklet) on your MOD's web UI, e.g. http://192.168.51.1/
 * A lightning bolt appears next to the puzzle icon, bottom left.
 * Nothing is installed on the device: reload the page and it's gone.
 */
(function () {
    if (document.getElementById('performance-view')) {
        console.log('Performance view is already loaded')
        return
    }

    $('<style id="performance-view-css">').text(%(css)s).appendTo('head')
    $('#main-menu #mod-plugins').after('<div id="mod-performance" class="icon" data-message="Performance view"></div>')
    $('#main-menu').before(%(markup)s)

    // Runtime version of the pedalboard.js changes on the branch: while the
    // view has borrowed the plugin icons, pause canvas layout, and deliver
    // value updates straight to the plugin's GUI (pedalboard.js only looks
    // for icons on the canvas).
    var original = $.fn.pedalboard
    $.fn.pedalboard = function (method) {
        var self = this
        if (self.data && self.data('performanceMode')) {
            if (method === 'fitToWindow') {
                self.data('performancePendingFit', true)
                return self
            }
            if (method === 'adapt' || method === 'focusPlugin' || method === 'drawPluginJacks') {
                return self
            }
            var a = arguments
            var icon = (self.data('plugins') || {})[a[1]]
            var gui = icon && icon.data && icon.data('gui')
            if (gui && icon.closest('#performance-view').length) {
                if (method === 'setPortWidgetsValue') {
                    gui.setPortWidgetsValue(a[2], a[3], null, true)
                    return
                }
                if (method === 'setPortEnabled') {
                    if (a[3] || a[4]) gui.enable(a[2]); else gui.disable(a[2])
                    if (a[5]) gui.addressPort(a[2], a[4], a[6])
                    return
                }
                if (method === 'setWritableParameterValue') {
                    gui.setWritableParameterValue(a[2], a[3], a[4], null, true)
                    return
                }
            }
        }
        return original.apply(this, arguments)
    }

%(js)s

    desktop.performanceView = new PerformanceView({
        pedalboard: desktop.pedalboard,
        view: $('#performance-view'),
        trigger: $('#main-menu #mod-performance'),
        exitTrigger: $('#main-menu #mod-plugins'),
    })
    $('#main-menu #mod-performance').statusTooltip()
    console.log('Performance view loaded: tap the lightning bolt, bottom left')
})();
''' % {'css': json.dumps(css), 'markup': json.dumps(markup), 'js': js}

sys.stdout.write(out)
