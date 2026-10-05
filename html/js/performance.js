// SPDX-FileCopyrightText: 2026 Niels
// SPDX-License-Identifier: AGPL-3.0-or-later

/*
 * Performance view
 *
 * Shows the pedals of the current pedalboard one at a time, as large as the
 * screen allows (capped at 2x native size), in a swipeable carousel. The
 * active (centred) pedal's settings sit in a strip underneath.
 *
 * The pedal faces and settings shown here are the *same* DOM elements the
 * editor uses: they are moved in on enter and moved back on exit. So every
 * control stays bound to the same modgui instance, and parameter, bypass,
 * preset and addressing changes stay in sync with the editor, the device and
 * other browsers without any extra plumbing.
 *
 * While the view is open the pedalboard is flagged 'performanceMode', which
 * pauses its layout code (fitToWindow, adapt, focusPlugin, drawPluginJacks),
 * because the moved icons no longer sit on the canvas.
 */

function PerformanceView(options) {
    var self = this

    options = $.extend({
        pedalboard: null,   // #pedalboard-dashboard
        view: null,         // #performance-view
        trigger: null,      // footer bolt icon
        exitTrigger: null,  // footer puzzle (Constructor) icon
    }, options)

    var MAX_SCALE   = 2.0
    var GAP         = 48  // px between pedals
    var PAD_Y       = 28  // px above and below the pedal
    var POLL_MS     = 400
    var SETTLE_MS   = 140
    var STORAGE_KEY = 'mod-performance-view'
    var HIDDEN_KEY  = 'mod-performance-hidden'
    var TILE        = ':hidden'  // pseudo instance of the "N hidden" tile

    var pb       = options.pedalboard
    var view     = options.view
    var stage    = view.find('.performance-stage')
    var track    = view.find('.performance-track')
    var strip    = view.find('.performance-strip')
    var empty    = view.find('.performance-empty')
    var trigger  = options.trigger

    var isOpen       = false
    var slides       = []     // [{instance, slide, scaler, icon, settings, w, h}]
    var active       = -1
    var shownSettings = null  // settings element currently in the strip
    var signature    = ''
    var builtFor     = null   // pedalboard bundle the carousel was last built for
    var pollTimer    = null
    var settleTimer  = null
    var wheelLock    = false
    var scrollRaf    = null
    var spacerL      = $('<div class="performance-spacer">')
    var spacerR      = $('<div class="performance-spacer">')

    // strip furniture of our own: a hide button next to the borrowed settings
    // panel, and the shelf of hidden pedals shown when the tile is centred
    var EYE_OFF = '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" d="M3 3l18 18M10.6 5.1A10.4 10.4 0 0 1 12 5c5.5 0 9 5.5 9.5 7-.3.8-1.3 2.6-3 4.2M6.6 6.6C4.4 8 3 10.2 2.5 12c.6 1.7 4 7 9.5 7 1.6 0 3-.4 4.3-1.1M9.9 9.9a3 3 0 0 0 4.2 4.2"/></svg>'
    var tools = $('<div class="performance-tools">').prependTo(strip)
    var hideButton = $('<button type="button" class="performance-hide" title="Hide this pedal from the performance view">' + EYE_OFF + '<span>Hide</span></button>').appendTo(tools)
    var shelf = $('<div class="performance-shelf">').appendTo(strip).hide()
    var tile = null  // the "N hidden" slide, created on demand

    this.isOpen = function () {
        return isOpen
    }

    // ------------------------------------------------------------------
    // state (AC: re-enter on last pedal, reset when the pedalboard changes)

    var boardKey = function () {
        return (desktop && desktop.pedalboardBundle) || ''
    }
    var saveState = function () {
        if (active < 0 || !slides[active]) {
            return
        }
        var state = { bundle: boardKey(), instance: slides[active].instance }
        self._state = state
        try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)) } catch (e) {}
    }
    var loadState = function () {
        if (self._state) {
            return self._state
        }
        try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) } catch (e) { return null }
    }

    // Hidden pedals, per pedalboard, in this browser only:
    // { "<bundle path>": ["/graph/instance", ...] }
    var hiddenMap = null
    var loadHidden = function () {
        try { hiddenMap = JSON.parse(localStorage.getItem(HIDDEN_KEY)) || {} } catch (e) { hiddenMap = hiddenMap || {} }
    }
    var hiddenList = function () {
        if (!hiddenMap) loadHidden()
        return (hiddenMap[boardKey()] || []).slice()
    }
    var saveHidden = function (list) {
        if (!hiddenMap) loadHidden()
        if (list.length) hiddenMap[boardKey()] = list
        else delete hiddenMap[boardKey()]
        try { localStorage.setItem(HIDDEN_KEY, JSON.stringify(hiddenMap)) } catch (e) {}
    }
    // other tabs of this browser
    window.addEventListener('storage', function (e) {
        if (e.key !== HIDDEN_KEY) return
        loadHidden()
        if (isOpen) rebuild()
    })

    // ------------------------------------------------------------------
    // plugin order: follow the signal, left to right

    var instanceOf = function (port) {
        return port.substring(0, port.lastIndexOf('/'))
    }

    var canvasPos = function (icon) {
        // inline left/top are the canvas coordinates; computed values are
        // overridden by our CSS while the icon is on stage
        var el = icon[0]
        return { x: parseFloat(el.style.left) || 0, y: parseFloat(el.style.top) || 0 }
    }

    this.signalOrder = function () {
        var plugins = pb.data('plugins') || {}
        var connMgr = pb.data('connectionManager')
        var ids = Object.keys(plugins).filter(function (k) {
            return plugins[k] && plugins[k].data && plugins[k].data('gui')
        })
        var known = {}, edges = {}, indeg = {}, depth = {}
        ids.forEach(function (i) { known[i] = true; edges[i] = {}; indeg[i] = 0 })

        var from, to, a, b
        for (from in (connMgr ? connMgr.origIndex : {})) {
            a = instanceOf(from)
            if (!known[a]) continue
            for (to in connMgr.origIndex[from]) {
                b = instanceOf(to)
                if (!known[b] || a === b || edges[a][b]) continue
                edges[a][b] = true
                indeg[b]++
            }
        }

        // longest path from a source = signal-flow depth (Kahn's algorithm)
        var queue = ids.filter(function (i) { return indeg[i] === 0 })
        queue.forEach(function (i) { depth[i] = 0 })
        while (queue.length) {
            a = queue.shift()
            for (b in edges[a]) {
                depth[b] = Math.max(depth[b] || 0, depth[a] + 1)
                if (--indeg[b] === 0) queue.push(b)
            }
        }
        // anything left is part of a feedback loop: put it after the rest
        var maxDepth = 0
        ids.forEach(function (i) { if (depth[i] != null) maxDepth = Math.max(maxDepth, depth[i]) })
        ids.forEach(function (i) { if (depth[i] == null) depth[i] = maxDepth + 1 })

        var pos = {}
        ids.forEach(function (i) { pos[i] = canvasPos(plugins[i]) })
        ids.sort(function (p, q) {
            return (depth[p] - depth[q]) || (pos[p].x - pos[q].x) || (pos[p].y - pos[q].y)
        })
        return ids
    }

    var currentSignature = function () {
        var plugins = pb.data('plugins') || {}
        var connMgr = pb.data('connectionManager')
        var keys = Object.keys(plugins).sort().join('|')
        var conns = connMgr ? Object.keys(connMgr.origIndex).map(function (f) {
            return f + '>' + Object.keys(connMgr.origIndex[f]).sort().join(',')
        }).sort().join('|') : ''
        return boardKey() + '#' + keys + '#' + conns
    }

    // ------------------------------------------------------------------
    // moving the editor's elements in and out

    var takeIcon = function (icon) {
        icon.addClass('performance-icon')
        if (icon.data('ui-draggable') || icon.data('draggable')) icon.draggable('disable')
        if (icon.data('ui-droppable') || icon.data('droppable')) icon.droppable('disable')
    }

    var returnIcon = function (icon) {
        icon.removeClass('performance-icon')
        if (icon.data('ui-draggable') || icon.data('draggable')) icon.draggable('enable')
        if (icon.data('ui-droppable') || icon.data('droppable')) icon.droppable('enable')
        icon.appendTo(pb)
    }

    var showSettings = function (settings) {
        if (shownSettings && shownSettings[0] === (settings && settings[0])) {
            return
        }
        hideSettings()
        if (!settings || !settings.length) {
            return
        }
        shownSettings = settings
        settings.addClass('performance-settings').appendTo(strip)
        // centre the controls when they fit, scroll from the start when they don't
        settings.find('.mod-controls').scrollLeft(0)
    }

    // what the strip shows for a slide: its settings, or the hidden shelf
    var showStrip = function (s) {
        if (s && s.tile) {
            hideSettings()
            tools.hide()
            renderShelf()
            shelf.show()
        } else {
            shelf.hide()
            tools.toggle(!!s)
            showSettings(s && s.settings)
        }
    }

    var thumbnailUrl = function (icon) {
        var gui = icon.data('gui')
        var v = gui && gui.effect && gui.effect.renderedVersion
        return '/effect/image/thumbnail.png?uri=' + escape(icon.data('uri')) + (v ? '&v=' + v : '')
    }

    var renderShelf = function () {
        var plugins = pb.data('plugins') || {}
        var hidden = {}
        hiddenList().forEach(function (i) { hidden[i] = true })
        var ids = self.signalOrder().filter(function (i) { return hidden[i] })

        shelf.empty()
        var head = $('<div class="performance-shelf-head">').appendTo(shelf)
        $('<span>').text('Hidden from this view').appendTo(head)
        if (ids.length > 1) {
            $('<button type="button" class="performance-show-all">Show all</button>').appendTo(head).click(function () {
                saveHidden([])
                rebuild({ focus: ids[0] })
            })
        }
        var row = $('<div class="performance-shelf-row">').appendTo(shelf)
        ids.forEach(function (instance) {
            var icon = plugins[instance]
            var item = $('<button type="button" class="performance-shelf-item">').attr('title', 'Show in the performance view')
            $('<span class="performance-shelf-thumb">').append($('<img alt="">').attr('src', thumbnailUrl(icon))).appendTo(item)
            $('<span class="performance-shelf-label">').text(icon.data('label') || instance.split('/').pop()).appendTo(item)
            item.click(function () {
                saveHidden(hiddenList().filter(function (i) { return i !== instance }))
                rebuild({ focus: instance })
            })
            row.append(item)
        })
    }

    var hideSettings = function () {
        if (!shownSettings) {
            return
        }
        shownSettings.removeClass('performance-settings').hide().appendTo($('body'))
        shownSettings = null
    }

    hideButton.click(function () {
        var s = slides[active]
        if (!s || s.tile) return
        var pedals = slides.filter(function (x) { return !x.tile })
        var i = pedals.indexOf(s)
        // the next pedal slides into the middle; at the end, the previous one
        var next = pedals[i + 1] || pedals[i - 1]
        saveHidden(hiddenList().concat([s.instance]))
        rebuild({ focus: next ? next.instance : TILE })
    })

    // ------------------------------------------------------------------
    // building and laying out the carousel

    var rebuild = function (opts) {
        opts = opts || {}
        var all = self.signalOrder()
        var hidden = {}
        hiddenList().forEach(function (i) { hidden[i] = true })
        var order = all.filter(function (i) { return !hidden[i] })
        var hiddenCount = all.length - order.length
        var key = boardKey()
        var boardChanged = key !== builtFor
        builtFor = key
        // a different pedalboard starts again at its first pedal, even if it
        // happens to use the same instance names
        var prevInstance = !boardChanged && active >= 0 && slides[active] ? slides[active].instance : null
        var prevIndex = boardChanged ? -1 : active
        var plugins = pb.data('plugins') || {}
        var byInstance = {}
        slides.forEach(function (s) { if (!s.tile) byInstance[s.instance] = s })

        var next = []
        order.forEach(function (instance) {
            var icon = plugins[instance]
            var s = byInstance[instance]
            if (!s) {
                s = { instance: instance }
                s.slide  = $('<div class="performance-slide">').attr('data-instance', instance)
                s.scaler = $('<div class="performance-scaler">').appendTo(s.slide)
            }
            delete byInstance[instance]
            if (s.icon && s.icon[0] !== icon[0] && s.icon.data('gui')) {
                // instance was replaced by another plugin (a removed icon has
                // already lost its data and stays gone)
                returnIcon(s.icon)
            }
            if (!icon.parent().is(s.scaler)) {
                takeIcon(icon)
                icon.appendTo(s.scaler)
            }
            if (!s.icon || s.icon[0] !== icon[0]) {
                s.icon = icon
                measure(s)
            }
            s.settings = icon.data('settings')
            next.push(s)
        })

        // slides whose plugin is gone (removed, or the pedalboard changed)
        for (var gone in byInstance) {
            var g = byInstance[gone]
            if (g.icon && g.icon.parent().is(g.scaler) && g.icon.data('gui')) {
                returnIcon(g.icon)
            }
            if (shownSettings && g.settings && shownSettings[0] === g.settings[0]) {
                hideSettings()
            }
            g.slide.remove()
        }

        if (hiddenCount) {
            if (!tile) {
                tile = { instance: TILE, tile: true, nw: 180, nh: 250, maxScale: 1.3 }
                tile.slide  = $('<div class="performance-slide performance-tile">').attr('data-instance', TILE)
                tile.scaler = $('<div class="performance-scaler">').appendTo(tile.slide)
                tile.box    = $('<div class="performance-tile-box">').html(EYE_OFF + '<b></b><small>Tap to show</small>').appendTo(tile.scaler)
            }
            tile.box.find('b').text(hiddenCount + ' hidden')
            next.push(tile)
        }

        slides = next
        active = -1  // indexes may have shifted; setActive() below re-applies classes
        track.children().detach()
        track.append(spacerL)
        slides.forEach(function (s) { track.append(s.slide) })
        track.append(spacerR)

        empty.toggle(slides.length === 0)
        if (slides.length === 0) {
            active = -1
            showStrip(null)
            return
        }

        layout(true)

        // which pedal should be active?
        var idx = -1
        if (opts.focus) {
            idx = slides.findIndex(function (s) { return s.instance === opts.focus })
        }
        if (idx < 0 && prevInstance) {
            idx = slides.findIndex(function (s) { return s.instance === prevInstance })
            if (idx < 0 && prevIndex >= 0) {
                // same board, pedal removed: stay close to where we were
                idx = Math.min(prevIndex, slides.length - 1)
            }
        }
        if (idx < 0) {
            var state = loadState()
            if (state && state.bundle === boardKey()) {
                idx = slides.findIndex(function (s) { return s.instance === state.instance })
            }
        }
        if (idx < 0) idx = 0
        if (slides[idx].tile && slides.length > 1 && !opts.focus && prevInstance !== TILE) idx = 0  // don't open on the tile
        setActive(idx, true)
        scrollToIndex(idx, false)
    }

    // Native pedal size. offsetWidth/Height ignore transforms, so this works
    // while the pedal is scaled; it only changes if the face itself changes.
    var measure = function (s) {
        if (s.tile) return true
        s.nw = s.icon.outerWidth()
        s.nh = s.icon.outerHeight()
        return s.nw > 0 && s.nh > 0
    }

    var lastStage = ''
    var layout = function (force) {
        if (!slides.length) {
            return false
        }
        var stageW = stage[0].clientWidth
        var stageH = stage[0].clientHeight
        var key = stageW + 'x' + stageH
        var remeasured = false
        slides.forEach(function (s) {
            if (!s.nw || !s.nh) remeasured = measure(s) || remeasured
        })
        if (!force && !remeasured && key === lastStage) {
            return false  // nothing to do: never touch styles needlessly, it repaints every pedal
        }
        lastStage = key

        var availH = Math.max(40, stageH - PAD_Y * 2)
        var availW = Math.max(40, stageW * 0.86)
        slides.forEach(function (s, i) {
            var w = s.nw || 200, h = s.nh || 300
            var scale = Math.min(s.maxScale || MAX_SCALE, availH / h, availW / w)
            var gap = i === slides.length - 1 ? 0 : GAP
            if (scale === s.scale && w === s.lw && h === s.lh && gap === s.gap) return
            s.scale = scale
            s.lw = w
            s.lh = h
            s.gap = gap
            s.w = w * scale
            s.h = h * scale
            s.scaler.css({ width: w, height: h, transform: 'scale(' + scale + ')' })
            s.slide.css({ width: s.w, height: s.h, marginRight: gap })
        })
        spacerL.css('width', Math.max(0, (stageW - slides[0].w) / 2))
        spacerR.css('width', Math.max(0, (stageW - slides[slides.length - 1].w) / 2))
        return true
    }

    // Programmatic moves are animated by hand with snapping switched off:
    // browsers cancel or re-snap native smooth scrolls inside a snap container.
    var animating = null
    var scrollToIndex = function (idx, smooth) {
        var s = slides[idx]
        if (!s) return
        var el = stage[0]
        var target = Math.round(s.slide[0].offsetLeft + s.w / 2 - el.clientWidth / 2)
        target = Math.max(0, Math.min(el.scrollWidth - el.clientWidth, target))
        if (animating) {
            cancelAnimationFrame(animating.raf)
            animating = null
        }
        if (!smooth) {
            el.scrollLeft = target
            return
        }
        var from = el.scrollLeft
        var start = null
        var duration = Math.min(450, 180 + Math.abs(target - from) * 0.25)
        stage.addClass('performance-animating')
        var step = function (ts) {
            if (start === null) start = ts
            var t = Math.min(1, (ts - start) / duration)
            var e = 1 - Math.pow(1 - t, 3)  // ease-out cubic
            el.scrollLeft = from + (target - from) * e
            if (t < 1) {
                animating.raf = requestAnimationFrame(step)
            } else {
                animating = null
                stage.removeClass('performance-animating')
                setActive(idx, false)
            }
        }
        animating = { raf: requestAnimationFrame(step), idx: idx }
    }

    var nearestIndex = function () {
        var el = stage[0]
        var centre = el.scrollLeft + el.clientWidth / 2
        var best = -1, bestDist = Infinity
        slides.forEach(function (s, i) {
            var c = s.slide[0].offsetLeft + s.w / 2
            var d = Math.abs(c - centre)
            if (d < bestDist) { bestDist = d; best = i }
        })
        return best
    }

    var setActive = function (idx, immediateSettings) {
        if (idx < 0 || idx >= slides.length) return
        if (idx !== active) {
            slides.forEach(function (s, i) { s.slide.toggleClass('active', i === idx) })
            active = idx
            saveState()
        }
        clearTimeout(settleTimer)
        if (immediateSettings) {
            showStrip(slides[idx])
        } else {
            settleTimer = setTimeout(function () {
                if (slides[active]) showStrip(slides[active])
            }, SETTLE_MS)
        }
    }

    this.goTo = function (idx) {
        idx = Math.max(0, Math.min(slides.length - 1, idx))
        setActive(idx, false)
        scrollToIndex(idx, true)
    }

    // ------------------------------------------------------------------
    // input

    stage.on('scroll', function () {
        if (scrollRaf) return
        scrollRaf = requestAnimationFrame(function () {
            scrollRaf = null
            if (animating) return  // the animation knows where it is going
            var idx = nearestIndex()
            if (idx >= 0) setActive(idx, false)
        })
    })

    // vertical mouse wheel moves one pedal per notch; horizontal trackpad
    // scrolling is left to the browser (scroll-snap does the centring)
    stage[0].addEventListener('wheel', function (e) {
        if (Math.abs(e.deltaY) <= Math.abs(e.deltaX)) return
        e.preventDefault()
        if (wheelLock || Math.abs(e.deltaY) < 4) return
        wheelLock = true
        setTimeout(function () { wheelLock = false }, 320)
        self.goTo(active + (e.deltaY > 0 ? 1 : -1))
    }, { passive: false })

    // a pointer that lands on a neighbouring pedal selects it instead of
    // touching its controls
    var slideIndexOf = function (target) {
        var slide = $(target).closest('.performance-slide')
        if (!slide.length) return -1
        return slides.findIndex(function (s) { return s.slide[0] === slide[0] })
    }
    var touchStart = null
    stage[0].addEventListener('touchstart', function (e) {
        var idx = slideIndexOf(e.target)
        if (idx < 0 || idx === active) { touchStart = null; return }
        e.stopPropagation()  // keep it away from the pedal's widgets, but allow swiping
        var t = e.touches[0]
        touchStart = { idx: idx, x: t.clientX, y: t.clientY }
    }, true)
    stage[0].addEventListener('touchmove', function (e) {
        if (!touchStart) return
        e.stopPropagation()
        var t = e.touches[0]
        if (Math.abs(t.clientX - touchStart.x) > 10 || Math.abs(t.clientY - touchStart.y) > 10) touchStart.moved = true
    }, true)
    stage[0].addEventListener('touchend', function (e) {
        if (!touchStart) return
        e.stopPropagation()
        if (!touchStart.moved) {
            e.preventDefault()  // no synthetic mouse events
            self.goTo(touchStart.idx)
        }
        touchStart = null
    }, true)
    var blockNeighbour = function (e) {
        var idx = slideIndexOf(e.target)
        if (idx < 0 || idx === active) return
        e.stopPropagation()
        e.preventDefault()
        if (e.type === 'click') self.goTo(idx)
    }
    ;['mousedown', 'mouseup', 'click', 'dblclick'].forEach(function (type) {
        stage[0].addEventListener(type, blockNeighbour, true)
    })

    // desktop.js cancels every touchmove that reaches <body> (no page
    // scrolling or rubber-banding). Our carousel and strip need native
    // scrolling, so stop those events here. Knobs still cancel their own
    // touches, so dragging a knob turns it instead of scrolling.
    view[0].addEventListener('touchmove', function (e) {
        e.stopPropagation()
    }, { passive: true })

    $(document).on('keydown', function (e) {
        if (!isOpen || !view.is(':visible')) return
        if ($(e.target).is('input, textarea, select, [contenteditable]')) return
        if (e.keyCode === 37) { self.goTo(active - 1); e.preventDefault() }
        if (e.keyCode === 39) { self.goTo(active + 1); e.preventDefault() }
    })

    // Only real window resizes / rotations. (jquery.ba-resize, used elsewhere
    // in the UI, triggers 'resize' on elements and those bubble up to window;
    // reacting to them re-laid-out and re-centred the carousel mid-swipe.)
    var resizeTimer = null
    $(window).on('resize orientationchange', function (e) {
        if (!isOpen || e.target !== window) return
        clearTimeout(resizeTimer)
        resizeTimer = setTimeout(function () {
            var keep = active
            if (layout(false) && keep >= 0) {
                scrollToIndex(keep, false)
                setActive(keep, true)
            }
        }, 120)
    })

    // ------------------------------------------------------------------
    // footer icon state while other windows open on top of us

    // Other main windows (pedalboards, banks, files, store) open on top of
    // the view and leave it running underneath; show the bolt as selected
    // only while nothing covers it.
    var coveringWindow = function () {
        var wins = (typeof WINDOWMANAGER !== 'undefined' && WINDOWMANAGER) ? WINDOWMANAGER.windows : []
        return wins.some(function (w) {
            return w[0] !== view[0] && w.data('isMainWindow') && w.is(':visible')
        })
    }
    var syncFooter = function () {
        if (!isOpen) return
        var covered = coveringWindow()
        trigger.toggleClass('selected', !covered)
        if (!covered) options.exitTrigger.removeClass('selected')
    }
    $(document).on('windowopen windowclose', function () {
        // window.js updates the footer icons after triggering these
        setTimeout(syncFooter, 0)
    })

    // ------------------------------------------------------------------
    // enter / exit

    this.open = function () {
        if (isOpen) return
        isOpen = true
        pb.data('performanceMode', true)
        $('body').addClass('performance-mode')
        trigger.addClass('selected')
        options.exitTrigger.removeClass('selected')
        view.show()

        slides = []
        active = -1
        builtFor = null
        signature = currentSignature()
        rebuild()

        pollTimer = setInterval(function () {
            syncFooter()
            // plugins and connections can change under us (another browser,
            // the device, a pedalboard load); follow along
            if (slides.some(function (sl) { return !sl.nw || !sl.nh })) layout(false)
            var sig = currentSignature()
            if (sig !== signature) {
                signature = sig
                rebuild()
            }
        }, POLL_MS)
    }

    this.close = function () {
        if (!isOpen) return
        isOpen = false
        clearInterval(pollTimer)
        clearTimeout(settleTimer)
        saveState()

        showStrip(null)
        slides.forEach(function (s) {
            if (s.icon && s.icon.parent().is(s.scaler) && s.icon.data('gui')) returnIcon(s.icon)
        })
        slides = []
        active = -1
        track.children().detach()
        view.hide()
        trigger.removeClass('selected')
        options.exitTrigger.addClass('selected')
        $('body').removeClass('performance-mode')

        pb.data('performanceMode', false)
        if (pb.data('performancePendingFit')) {
            pb.data('performancePendingFit', false)
            pb.pedalboard('fitToWindow')
        }
        // redraw cables in case anything moved or connected while we were away
        var plugins = pb.data('plugins') || {}
        for (var instance in plugins) {
            if (plugins[instance] && plugins[instance].data) pb.pedalboard('drawPluginJacks', plugins[instance])
        }
    }

    trigger.click(function () {
        self.open()
        return false
    })
    options.exitTrigger.click(function () {
        self.close()
    })
}
