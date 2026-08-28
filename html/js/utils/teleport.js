// SPDX-FileCopyrightText: 2012-2026 MOD Audio UG
// SPDX-License-Identifier: AGPL-3.0-or-later

// Rules for cable teleports, kept apart from the drawing so they are testable without a
// DOM. A name belongs to an output port, being teleported belongs to a cable, and neither
// is derived from the other.  names: { outputPort: name }  cables: [ {from, to} ]

// The separator used in the saved form. No port name can contain it.
var TELEPORT_ARROW = ' -> '

// Every name currently spoken for, as a lookup. `exceptPort` leaves one port out, so
// that renaming a port to what it is already called does not collide with itself.
function teleportNamesInUse(names, exceptPort) {
    var used = {}
    for (var port in names) {
        if (port !== exceptPort) {
            used[names[port]] = true
        }
    }
    return used
}

// A name for a port that nothing else is using: the plugin's name and the port's, and a
// number if even that is taken. Generated rather than typed, so disambiguating silently
// is help rather than surprise.
function teleportDefaultName(pluginName, portName, names) {
    var base = ((pluginName ? pluginName + ' ' : '') + portName).trim()
    var used = teleportNamesInUse(names, null)
    if (! used[base]) {
        return base
    }
    for (var n = 2; ; n++) {
        var candidate = base + ' ' + n
        if (! used[candidate]) {
            return candidate
        }
    }
}

// Whether a name the user typed can be accepted for this port. Empty is not a name --
// clearing the box is how you ask for the teleport to go away, handled by the caller.
function teleportNameAvailable(name, port, names) {
    name = (name || '').trim()
    if (! name) {
        return false
    }
    return ! teleportNamesInUse(names, port)[name]
}

// The saved form. Enforces the lifetime rule in both directions: a name with no
// teleported cable is not written, and a cable whose output has no name is not either,
// since it could not be drawn as a teleport anyway.
function teleportSerialise(names, cables) {
    var out = { names: {}, cables: [] }
    var i
    var used = {}
    for (i = 0; i < cables.length; i++) {
        if (names[cables[i].from]) {
            used[cables[i].from] = true
        }
    }
    for (var port in names) {
        if (used[port]) {
            out.names[port] = names[port]
        }
    }
    for (i = 0; i < cables.length; i++) {
        if (used[cables[i].from]) {
            out.cables.push(cables[i].from + TELEPORT_ARROW + cables[i].to)
        }
    }
    return out
}

// The saved form back into the working one. Anything unreadable is treated as no
// teleports at all -- a broken file must not stop a pedalboard loading.
function teleportDeserialise(data) {
    var out = { names: {}, cables: [] }
    if (! data || typeof data !== 'object') {
        return out
    }
    if (data.names && typeof data.names === 'object') {
        for (var port in data.names) {
            if (typeof data.names[port] === 'string' && data.names[port]) {
                out.names[port] = data.names[port]
            }
        }
    }
    if (Object.prototype.toString.call(data.cables) === '[object Array]') {
        for (var i = 0; i < data.cables.length; i++) {
            var parts = String(data.cables[i]).split(TELEPORT_ARROW)
            if (parts.length === 2 && parts[0] && parts[1]) {
                out.cables.push({ from: parts[0], to: parts[1] })
            }
        }
    }
    return out
}
