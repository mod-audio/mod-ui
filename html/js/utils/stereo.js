// SPDX-FileCopyrightText: 2012-2026 MOD Audio UG
// SPDX-License-Identifier: AGPL-3.0-or-later

// Which side of a stereo pair a port symbol names, and what the other side is called.
//
// ponytail: naming heuristic. LV2 declares real pairs through the port-groups extension
// and this repo's backend already reads them (utils_lilv.cpp -> PluginPort.group), but
// that field does not reach the plugin JSON, no released mod-desktop ships a libmod_utils
// that has it, and most plugins declare no groups anyway. Swap the body of this function
// for a port.group comparison once the field is in the browser.

var STEREO_OTHER_SIDE = {
    'l': 'r',
    'r': 'l',
    'left': 'right',
    'right': 'left',
}

// A trailing "l" only means "left" when it stands as a token of its own: the whole
// symbol ("l"), after a separator ("in_l"), or after a case change ("outL"). Without
// that rule "signal" and "pedal" read as left channels and pair with whatever port
// happens to be called "signar" - or, far more likely, with nothing, which is merely
// wasted work. The case-change rule is what keeps "SIGNAL" out.
function stereoSideIsOwnToken(prefix, separator, side) {
    if (prefix === '' || separator !== '') {
        return true
    }
    var last = prefix.slice(-1)
    return side === side.toUpperCase() && last !== last.toUpperCase()
}

// Recase `word` the way `like` is cased: "R" for "L", "Right" for "Left", else lower
function stereoRecase(word, like) {
    if (like === like.toUpperCase()) {
        return word.toUpperCase()
    }
    if (like[0] === like[0].toUpperCase()) {
        return word[0].toUpperCase() + word.slice(1)
    }
    return word
}

// Given one port symbol, returns the symbol its stereo partner would have, and whether
// this symbol is the left/odd half of the pair (the half that draws the merged cable).
// Returns null for symbols that name no side at all, such as a mono "in".
//
// The returned symbol is a guess: the caller decides it is a real pair by checking that
// a port of the same type and direction actually goes by that name.
function stereoCounterpart(symbol) {
    var m = /^(.*?)([_-]?)(left|right|l|r)$/i.exec(symbol)
    if (m !== null && stereoSideIsOwnToken(m[1], m[2], m[3])) {
        var side = m[3].toLowerCase()
        return {
            symbol: m[1] + m[2] + stereoRecase(STEREO_OTHER_SIDE[side], m[3]),
            first: side[0] === 'l',
        }
    }

    // Numbered channels pair up as (1,2), (3,4), ... so a four-out plugin gets two
    // pairs rather than one pair and two strays
    m = /^(.*?)([_-]?)(\d+)$/.exec(symbol)
    if (m !== null) {
        var n = parseInt(m[3], 10)
        if (n < 1) {
            return null
        }
        var partner = String(n % 2 === 1 ? n + 1 : n - 1)
        while (partner.length < m[3].length) {
            partner = '0' + partner  // keep any zero padding: out_01 -> out_02
        }
        return {
            symbol: m[1] + m[2] + partner,
            first: n % 2 === 1,
        }
    }

    return null
}
