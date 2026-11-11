// SPDX-FileCopyrightText: 2012-2026 MOD Audio UG
// SPDX-License-Identifier: AGPL-3.0-or-later

// Slack of every node in the pedalboard graph.
//
// Plugins run on parallel jack threads, so a plugin's cpu cost and its contribution
// to jack's DSP load are different numbers: only the longest chain through the graph
// bounds how long a cycle takes. A plugin with slack has headroom -- it finishes while
// something slower is still running, so making it cheaper buys nothing. A plugin with
// zero slack is on the critical path, and every microsecond off it is a microsecond
// off the cycle.
//
// weights: {node: cost}, missing nodes count as 0 (hardware ports, unmeasured clients)
// edges:   [[from, to], ...], signal flow direction
//
// returns {critical: <cost of longest chain>, slack: {node: cost}}
function graphSlack(weights, edges) {
    var nodes = {}
    var succ = {}
    var pred = {}
    var adj = {}
    var i, n, m, e

    function touch(node) {
        if (nodes[node] === undefined) {
            nodes[node] = weights[node] || 0
            succ[node] = []
            pred[node] = []
            adj[node] = []
        }
    }

    for (n in weights) { touch(n) }
    for (i = 0; i < edges.length; i++) {
        touch(edges[i][0])
        touch(edges[i][1])
        adj[edges[i][0]].push(edges[i][1])
    }

    // Drop back edges so what is left is a DAG. A pedalboard can contain a feedback
    // loop; jack breaks those the same way, by ordering on the edges it kept.
    //
    // Which edge gets dropped depends on where the walk starts, so start from the
    // sources -- the capture ports signal actually enters through -- and only then
    // pick up anything left inside a cycle. Sorted throughout: without it the answer
    // would change with object key order.
    var color = {}
    var seen = {}
    var incoming = {}
    for (n in nodes) { color[n] = 0; incoming[n] = 0 }
    for (i = 0; i < edges.length; i++) { incoming[edges[i][1]]++ }

    var roots = Object.keys(nodes).sort()
    var sources = []
    var rest = []
    for (i = 0; i < roots.length; i++) {
        if (incoming[roots[i]] === 0) { sources.push(roots[i]) } else { rest.push(roots[i]) }
    }
    roots = sources.concat(rest)

    for (n in adj) { adj[n].sort() }

    function visit(root) {
        var stack = [[root, 0]]
        color[root] = 1

        while (stack.length) {
            var top = stack[stack.length - 1]
            var out = adj[top[0]]

            if (top[1] >= out.length) {
                color[top[0]] = 2
                stack.pop()
                continue
            }

            m = out[top[1]++]
            if (color[m] === 1) { continue }        // back edge, drop it

            var key = top[0] + " " + m
            if (!seen[key]) {
                seen[key] = true
                succ[top[0]].push(m)
                pred[m].push(top[0])
            }
            if (color[m] === 0) {
                color[m] = 1
                stack.push([m, 0])
            }
        }
    }
    for (i = 0; i < roots.length; i++) { if (color[roots[i]] === 0) { visit(roots[i]) } }

    // Kahn topological order
    var indeg = {}
    var queue = []
    var topo = []
    for (n in nodes) { indeg[n] = pred[n].length }
    var ordered = Object.keys(nodes).sort()
    for (i = 0; i < ordered.length; i++) { if (indeg[ordered[i]] === 0) { queue.push(ordered[i]) } }
    while (queue.length) {
        n = queue.pop()
        topo.push(n)
        for (i = 0; i < succ[n].length; i++) {
            m = succ[n][i]
            if (--indeg[m] === 0) { queue.push(m) }
        }
    }

    // earliest finish, walking forwards
    var ef = {}
    var critical = 0
    for (i = 0; i < topo.length; i++) {
        n = topo[i]
        var start = 0
        for (e = 0; e < pred[n].length; e++) { start = Math.max(start, ef[pred[n][e]]) }
        ef[n] = start + nodes[n]
        critical = Math.max(critical, ef[n])
    }

    // latest finish that still fits inside the critical path, walking backwards
    var lf = {}
    var slack = {}
    for (i = topo.length - 1; i >= 0; i--) {
        n = topo[i]
        var latest = critical
        for (e = 0; e < succ[n].length; e++) {
            latest = Math.min(latest, lf[succ[n][e]] - nodes[succ[n][e]])
        }
        lf[n] = latest
        slack[n] = latest - ef[n]
    }

    return { critical: critical, slack: slack }
}
