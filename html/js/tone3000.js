// SPDX-FileCopyrightText: 2012-2023 MOD Audio UG
// SPDX-License-Identifier: AGPL-3.0-or-later

/*
 * Tone3000 Select flow.
 *
 * This runs in a popup, not an iframe, and that is not cosmetic. TONE3000's sign-in
 * cookie is SameSite=Lax, so it is never sent on a cross-site iframe subrequest: the
 * OTP verifies, the cookie comes back, the next request drops it, and the user lands
 * on the login screen again -- silently, with no console error, in every browser.
 * Only TONE3000 can change that (SameSite=None; Secure; Partitioned, or calling
 * requestStorageAccess() from their own page). A popup is a top-level browsing
 * context, so its cookies are first-party and none of this applies.
 *
 * This file only opens that popup and mints the PKCE pair it will need. Everything
 * that happens after the user picks a tone -- the token exchange, the API reads, the
 * download itself -- belongs to tone3000-callback.html, which TONE3000 redirects the
 * popup to. That page is served from our origin, so it reads the pair straight out of
 * the sessionStorage written below.
 */

var TONE3000_STATE_KEY = 't3k_state'
var TONE3000_VERIFIER_KEY = 't3k_code_verifier'
var TONE3000_REDIRECT_PATH = '/tone3000-callback.html'
var TONE3000_POPUP_NAME = 't3k_select'

var tone3000Popup = null

function tone3000Base64Url (bytes) {
    var str = String.fromCharCode.apply(null, new Uint8Array(bytes))
    return btoa(str).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '')
}

function tone3000RandomBase64Url (nbytes) {
    return tone3000Base64Url(crypto.getRandomValues(new Uint8Array(nbytes)))
}

// S256 PKCE challenge. crypto.subtle only exists in a secure context. localhost is
// one; the real device, on plain http:// over a LAN IP, is not. A pure-JS sha256
// will be needed before this ships to hardware.
function tone3000Sha256Base64Url (input) {
    return crypto.subtle.digest('SHA-256', new TextEncoder().encode(input))
                 .then(tone3000Base64Url)
}

/* Build the authorize URL, stashing the PKCE verifier and CSRF state in OUR
   sessionStorage. The popup gets only a snapshot of it, taken at window.open() time,
   which is before these are written -- but the callback page is same-origin with us
   and reads them back live through window.opener. */
function tone3000BuildAuthorizeUrl () {
    var verifier = tone3000RandomBase64Url(32)
    var state = tone3000RandomBase64Url(16)

    return tone3000Sha256Base64Url(verifier).then(function (challenge) {
        sessionStorage.setItem(TONE3000_VERIFIER_KEY, verifier)
        sessionStorage.setItem(TONE3000_STATE_KEY, state)

        var params = {
            client_id: TONE3000_CLIENT_ID,
            redirect_uri: window.location.origin + TONE3000_REDIRECT_PATH,
            response_type: 'code',
            code_challenge: challenge,
            code_challenge_method: 'S256',
            state: state,
            prompt: 'select_tone',
            // The NAM plugin is what consumes these files; don't offer the user
            // formats this device cannot load.
            format: 'nam',
        }

        var qs = []
        for (var key in params) {
            qs.push(encodeURIComponent(key) + '=' + encodeURIComponent(params[key]))
        }
        return TONE3000_API + '/api/v1/oauth/authorize?' + qs.join('&')
    })
}

// Headroom for the popup's own title bar, plus whatever the desktop reserves at the
// bottom of the screen. Tuned by eye; nothing can measure it before the popup exists.
var TONE3000_POPUP_CHROME = 165

// What `outerHeight - innerHeight` misses. Chrome under-reports the height of its own
// toolbars by about this much; the true value cannot be recovered from anything a page
// can read. Unused where mozInnerScreenY exists, which needs no estimate at all.
var TONE3000_CHROME_UNDERREPORT = 35

/* Screen y of the top of our viewport.
 *
 * Firefox says so exactly. Everyone else gets `screenY` (the window frame) plus a guess
 * at the chrome above the viewport, and the guess runs short -- see the constant. */
function tone3000ViewportTop () {
    if (window.mozInnerScreenY !== undefined) {
        return window.mozInnerScreenY
    }
    return window.screenY + (window.outerHeight - window.innerHeight) + TONE3000_CHROME_UNDERREPORT
}

/* Cover the panel's content area, starting below our own title bar rather than on top
 * of it. #tone3000-wrapper *is* that area, so measure it instead of guessing -- move
 * the bar in CSS and the popup follows. */
function tone3000PopupBounds () {
    var wrapper = $('#tone3000-wrapper')[0]

    return {
        left: Math.round(window.screenX),
        top: Math.round(tone3000ViewportTop() + wrapper.getBoundingClientRect().top),
        width: window.innerWidth,
        height: window.innerHeight - TONE3000_POPUP_CHROME,
    }
}

function tone3000PopupFeatures (bounds) {
    return 'width=' + bounds.width +
           ',height=' + bounds.height +
           ',left=' + bounds.left + ',top=' + bounds.top +
           ',toolbar=no,menubar=no,location=no,status=no,resizable=yes,scrollbars=yes'
}

// How long to keep nudging the popup into place, and how often. It is shown within a
// frame or two; the rest is slack.
var TONE3000_PLACE_TRIES = 6
var TONE3000_PLACE_INTERVAL = 40

/* The feature string's left/top are a hint, and a browser drops them when the opener is
 * maximized -- width and height survive, position does not. moveTo is the lever left,
 * and only here: the popup is still the about:blank we opened, so it is same-origin.
 * One navigation later it is tone3000.com and moveTo throws.
 *
 * A single move does not take: window.open() returns before the browser has shown the
 * window, and the bounds it was created with are applied at show time, over the top of
 * anything we set first. So keep moving it for a beat. Where the feature string was
 * honoured this is all no-ops. */
function tone3000PlacePopup (popup, bounds) {
    return new Promise(function (resolve) {
        var attempts = 0
        function attempt () {
            attempts += 1
            try {
                popup.moveTo(bounds.left, bounds.top)
            } catch (e) {
                // Blocked (Firefox's dom.disable_window_move_resize) or already navigated.
                resolve()
                return
            }
            if (attempts >= TONE3000_PLACE_TRIES || popup.closed) {
                resolve()
                return
            }
            window.setTimeout(attempt, TONE3000_PLACE_INTERVAL)
        }
        attempt()
    })
}

function tone3000OpenSelectPopup () {
    if (!TONE3000_CLIENT_ID) {
        alert('TONE3000 is not configured on this device: MOD_TONE3000_CLIENT_ID is not set.')
        return
    }

    if (tone3000Popup && !tone3000Popup.closed) {
        tone3000Popup.focus()
        return
    }

    // Open synchronously, while we still hold the user activation from the click.
    // Deferring window.open until after the PKCE promise resolves gets it blocked
    // as an unsolicited popup.
    var bounds = tone3000PopupBounds()
    tone3000Popup = window.open('', TONE3000_POPUP_NAME, tone3000PopupFeatures(bounds))
    if (!tone3000Popup) {
        alert('Popup blocked -- allow popups for this site and try again.')
        return
    }

    // Both have to finish before the popup leaves about:blank: the URL is what we
    // navigate to, and after navigating we can no longer move it.
    var popup = tone3000Popup
    Promise.all([
        tone3000BuildAuthorizeUrl(),
        tone3000PlacePopup(popup, bounds),
    ]).then(function (results) {
        popup.location = results[0]
    }).catch(function (err) {
        popup.close()
        alert('Failed to build the TONE3000 authorize URL: ' + err)
    })
}

/* Called from the popup once a download lands -- it is same-origin with us, so it reaches
   this directly. Every plugin already on the board is holding a file list from before the
   download, so hand each one a fresh copy, with the files just written at the top of it.
   `downloaded` holds the paths the upload route reported writing. */
function tone3000RefreshFileLists (downloaded) {
    if (typeof desktop === 'undefined' || !desktop || !desktop.pedalboard) {
        return
    }
    var plugins = desktop.pedalboard.data('plugins')
    for (var instance in plugins) {
        var plugin = plugins[instance]
        var gui = (plugin && plugin.data) ? plugin.data('gui') : null
        if (gui && gui.refreshFileTypesLists) {
            gui.refreshFileTypesLists('nammodel', downloaded)
        }
    }
}

function tone3000ClosePopup () {
    if (tone3000Popup && !tone3000Popup.closed) {
        tone3000Popup.close()
    }
    tone3000Popup = null

    sessionStorage.removeItem(TONE3000_STATE_KEY)
    sessionStorage.removeItem(TONE3000_VERIFIER_KEY)
}

/* A popup outlives the page that opened it, and the callback page reads the PKCE pair
   out of this window -- so a reload or a navigation would strand it on screen with no
   opener left to read. pagehide (not unload) is the event that still fires when the
   page goes into the bfcache. */
window.addEventListener('pagehide', tone3000ClosePopup)

/* Browser-side for now: this is a preference about this browser's popup, not device state,
   and there is no user-settings route to put it behind. localStorage throws outright when
   storage is disabled, rather than degrading, so every access is guarded. */
var TONE3000_AUTO_OPEN_KEY = 't3k_auto_open'

function tone3000AutoOpen () {
    try {
        return localStorage.getItem(TONE3000_AUTO_OPEN_KEY) === '1'
    } catch (e) {
        return false
    }
}

function tone3000SetAutoOpen (enabled) {
    try {
        localStorage.setItem(TONE3000_AUTO_OPEN_KEY, enabled ? '1' : '0')
    } catch (e) {
        // Nothing to do -- the checkbox still works for this session.
    }
}

JqueryClass('tone3000Box', {
    init: function (options) {
        var self = $(this)

        options = $.extend({
            isMainWindow: true,
            windowName: "Tone3000",
        }, options)

        self.data(options)

        self.find('#tone3000-browse').click(function () {
            tone3000OpenSelectPopup()
            return false
        })

        var autoOpen = self.find('#tone3000-autoopen')
        autoOpen.prop('checked', tone3000AutoOpen())
        autoOpen.change(function () {
            tone3000SetAutoOpen(this.checked)
        })

        /* windowopen fires inside the click that selected the tab, so we still hold the user
           activation window.open needs. Opening the popup any later gets it blocked.

           There is deliberately no windowclose handler. It fires whenever the panel hides --
           including when the window manager hides it to raise another panel -- and closing
           the popup there meant every trip through another tab threw away the user's place
           in the catalog. The popup outlives the panel; only leaving the page closes it. */
        options.open = function () {
            if (tone3000AutoOpen()) {
                tone3000OpenSelectPopup()
            }
            return false
        }

        self.window(options)
    },
})
