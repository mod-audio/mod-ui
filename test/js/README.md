# Frontend tests

Tests for the browser JavaScript in `html/js/`. The Python backend has its own suite in
`test/` (pytest); this is the JS side.

## Running

```bash
npm install      # once, pulls in jsdom (the only dependency)
npm test         # runs everything under test/js/
npm run test:watch
```

Node's built-in test runner (`node --test`, `node:assert`) — no Jest, no Vitest, no build
step. The only third-party dependency is `jsdom`.

## How it works

`html/js/*.js` is not modular. It defines globals and assumes `jQuery`, `Mustache` and a few
page variables already exist, so it cannot be `require`d. Instead `harness.js` stands up a
jsdom window, loads the real vendored libraries, then loads the **real source file under
test** with `window.eval` and drives its now-global functions. The tests exercise the
shipped code, not a copy of it.

`harness.js` exports:

- `makeWindow({url, body})` — a jsdom window with jQuery/Mustache loaded and the page globals
  (`VERSION`, `baseUrl`, `desktop`, `isSDK`) defined. Returns `{window, $, load}` where
  `load(rel)` evals a source file, `rel` being relative to `html/`.
- `captureWindowOptions(ctx)` — grabs the options a `JqueryClass` box hands to
  `self.window(...)`, without pulling in the real overlay machinery.
- `stubAjax(ctx, routes)` — an `$.ajax` that answers by URL substring.

## What this can and cannot test

jsdom has a DOM but no browser around it. So:

**In scope** — DOM manipulation and logic. Widget rendering and re-rendering, event wiring,
list ordering, preference storage, the shape of data handed between functions. This is where
the bugs these tests were written for actually lived.

**Out of scope, stays manual** — anything needing a real browser:

- **Layout.** `getBoundingClientRect` is all zeros in jsdom, so popup *placement* (the
  `mozInnerScreenY` / chrome-height math in `tone3000.js`) cannot be tested here.
- **Windowing.** `window.open` is a stub; there is no real popup, no cross-window focus, no
  cookie behaviour.
- **CSS.** No cascade, no computed styles.
- **The network and the Tornado backend.** Backend routes are tested in `test/` (pytest);
  the `POST /files/upload` guards and the `fullname` round-trip belong there, not here.

Keep this boundary honest — a green suite that quietly doesn't cover placement or the backend
is worse than no suite, because it reads as coverage.

## Files

- `harness.js` — the rig described above (not itself a test; `*.test.js` are the tests).
- `modgui.filelist.test.js` — `GUI.refreshFileTypesLists` / `swapFileWidgets`: refreshing a
  plugin's file dropdown in place, across two templates that nest options differently. Runs
  against `fixtures/icon-nested.html` and the shipped `html/resources/settings.html`.
- `fixtures/icon-nested.html` — a plugin-icon template whose file options nest inside a
  `.mod-enumerated-list`, the way NAM's icon does. Vendored so the suite needs only the
  `mod-ui` checkout, not the sibling `mod-fs/` dev tree.
- `tone3000.autoopen.test.js` — the Tone3000 tab's auto-open preference and the popup's
  lifetime relative to the tab.
