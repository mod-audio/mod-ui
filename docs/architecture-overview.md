# mod-ui architecture overview: the device / desktop boundary

Written 2026-07-31 against `24aff2e0` (branch `tone3000`, `v0.99.8-3554`).

Purpose: let you decide *where a UI change belongs* before you open a file.
It is a map, not a reference. Line numbers drift; grep the symbol and treat
`:NNN` as a hint, the same convention as `AGENTS.md`.

ASCII only, by request.


## 1. One codebase, three runtime shapes

mod-ui is a Tornado webserver that renders one page (`html/index.html`) and
bridges it to `mod-host` over a socket. The same `mod/` + `html/` tree ships in
three places:

    shape A: MOD DEVICE (Duo / Duo X / Dwarf)
      mod-ui runs on the pedal, binds 0.0.0.0:80, browser is on your laptop
      over the LAN. Real HMI serial, real actuators, real cloud identity.

    shape B: MOD DESKTOP, standalone app
      systray binary starts jackd + mod-host + mod-ui as child processes,
      binds 127.0.0.1:18181, then opens your SYSTEM DEFAULT BROWSER at it.

    shape C: MOD DESKTOP, audio plugin (VST3 / CLAP / LV2 / AU)
      same stack, but ports are derived per plugin instance, and the page is
      shown inside an EMBEDDED WEBVIEW owned by the plugin window
      (WebKitGTK on Linux, WebView2 on Windows, WKWebView on macOS).

    shape D: this workspace's local harness (scripts/run-mod)
      mod-ui only. Fake host, fake HMI, no jackd, mod-fs/ as the device disk.

B and C both set `MOD_DESKTOP=1`. mod-ui itself cannot tell B from C.

Topology of shape B/C:

    +---------------------------------------------------------------+
    |  mod-desktop (Qt systray)  or  DesktopPlugin (DPF)             |
    |  - sets the whole MOD_* environment (see 3)                    |
    |  - spawns children, owns lifetime                              |
    |                                                                |
    |    +-----------+   +------------+   +----------------------+   |
    |    |  jackd    |<->|  mod-host  |<->|  mod-ui (cxfreeze)   |   |
    |    +-----------+   +------------+   |  tornado :18181      |   |
    |                      ^socket        +----------+-----------+   |
    +---------------------------------------------|-----------------+
                                                  | http + websocket
                     shape B: system browser  <---+
                     shape C: embedded webview <--+

In shape A, everything to the left of mod-ui is the pedal's own init system,
and the HMI serial port is real.


## 2. Where the two products actually diverge

There is far less desktop-specific code than you would expect. The entire
divergence is four mechanisms:

    1. MOD_DESKTOP=1            -> mod/settings.py DESKTOP
    2. a different mod-hardware-descriptor.json (no actuators, platform=desktop)
    3. absence of DEVICE_KEY / a real cloud device identity
    4. one frontend file: html/js/desktop-app.js (the DesktopApp object)

Everything else that "looks desktop-specific" is a downstream consequence of
one of those four. Internalise this: **there is no desktop branch to add code
to.** If you need desktop-specific behaviour you are almost always extending
mechanism 4.

Beware the filenames. `html/js/desktop.js` is NOT mechanism 4 -- it is the
shared web GUI controller and runs on the pedals too. It dates from 2013, two
years before any MOD Desktop integration existed (`MOD_APP` 2015, renamed to
`MOD_DESKTOP` in 2024); "desktop" there means the pedalboard workspace
metaphor. Mechanism 4 is `desktop-app.js`, and `desktop-app` is the naming tag
for everything MOD Desktop-specific.

### 2.1 What DESKTOP actually does in the backend

Grep `DESKTOP` in `mod/`. It has exactly three effects:

    mod/webserver.py  prepare()
        application.listen(PORT, address = "127.0.0.1" if DESKTOP else "0.0.0.0")
        -> desktop is loopback-only; a device is LAN-reachable.

    mod/webserver.py  TemplateHandler.index()
        'using_desktop': 'true' if DESKTOP else 'false'
        -> becomes the JS global USING_MOD_DESKTOP. THIS IS THE HOOK.

    mod/screenshot.py generate_screenshot()
        picks the frozen `mod-pedalboard` binary instead of `python3 -m
        modtools.pedalboard`, because on desktop there is no python on PATH.

That is all. No route is added or removed, no handler behaves differently.

### 2.2 What the hardware descriptor does

`get_hardware_descriptor()` (`mod/__init__.py`) just reads
`MOD_HARDWARE_DESC_FILE`. On desktop that file is
`mod-desktop/utils/linux/mod-hardware-descriptor.json`:

    { "name": "MOD Desktop", "platform": "desktop",
      "architecture": "x64_64", "bin-compat": "linux-x64_64",
      "factory_pedalboards": true }

Note what is MISSING: `actuators`, `addressing_pages`, `codec_truebypass`.
Consequences, all automatic:

    no "actuators" -> get_hardware_actuators() == []
                   -> HARDWARE_PROFILE == [] in the page
                   -> hardware.js renders no device addressing targets
    no codec_truebypass -> index.html hides #mod-bypassLeft / #mod-bypassRight
    platform "desktop"  -> JS global PLATFORM, used for per-model quirks
                           (e.g. desktop.js gates #mod-cpu-stats on
                            PLATFORM != "duo")

HMI is not gated by DESKTOP at all. `mod/session.py` tries to open the real
serial port, fails on a desktop machine, and falls back to `FakeHMI`. Same
code path as a broken cable.

### 2.3 The three JS globals that carry the boundary

Rendered into `html/index.html` by `TemplateHandler.index()`:

    PLATFORM            = '{{platform}}'                  // "desktop", "duo", ...
    USING_MOD_DESKTOP   = {{using_desktop}}               // MOD_DESKTOP=1
    USING_MOD_DEVICE    = {{using_mod}} && !{{using_desktop}}
                          // using_mod = DEVICE_KEY set AND platform known

They are not mutually exhaustive. A plain `python3 server.py` dev run is
neither: both are false. Three states, so **do not write `if (!USING_MOD_DEVICE)`
when you mean "on desktop"** - that also catches the local harness.

Current consumers, complete:

    index.html   if (USING_MOD_DEVICE) -> cloud device auth, else hide
                 #mod-cloud-plugins, #mod-update, .js-cloud, bypass buttons,
                 and force-show #mod-xruns / #mod-status
    index.html   if ({{using_desktop}}) DesktopApp.setup(desktop)
                 else honour the dev-mode preference
    index.html   cloud terms gating (desktop must accept explicitly; the
                 /desktop-tou.html and /desktop-pp.html pages are linked
                 from there)

`USING_MOD_DESKTOP` is read in exactly one place, the `DesktopApp.setup()`
call. Nothing else in `html/js/` reads it -- everything downstream asks
`DesktopApp.isActive()` instead.

**There are TWO cutdown mechanisms, not one.** This trips people up. They run
in sequence in index.html:

    index.html:173-190   the `else` arm of if (USING_MOD_DEVICE), which hides
                         #mod-cloud-plugins, #mod-update, .js-cloud and the
                         bypass buttons. Fires for desktop AND for a plain
                         local harness run.
    index.html:~200      DesktopApp.setup(), which runs after it and can
                         therefore re-show anything the first one hid.

The Plugin Store is hidden by the first, not the second.

### 2.4 DesktopApp: the actual desktop UI surface

`html/js/desktop-app.js`. One object, `DesktopApp`, holding the store
constants, the widget renderers, the cloud-query override and `setup()`.

`setup()` sets `active = true`, puts a `desktop-app` class on `<body>` (so
CSS can do the persistent hiding that a one-off `.hide()` cannot), then:

    hide, genuinely unavailable and not a reason to buy hardware:
          #mod-file-manager #mod-settings #mod-status #mod-ram
          #mod-show-midi-port
          #pedalboards-library a        (every <a> in the library panel)
          #pedal-presets-window .js-assign-all

    show with an upsell widget, genuinely exclusive to MOD hardware:
          #mod-bank      -> panel injected into #bank-library
          #mod-devices   -> panel injected into #mod-devices-window
          #mod-cloud-plugins (re-shown; see the two-mechanisms note above)
          hardware.js addressing -> Device / Control Chain tabs shown locked

`DesktopApp.isActive()` is exposed to `hardware.js` through the `isApp`
callback in the HardwareManager options, and consumed in:

    desktop.js     installMissingPlugins() -> refuse, warn "plugins are missing"
    hardware.js    addressing dialog -> Device / Control Chain tabs get
                   .desktop-app-locked and show the inline widget on click
    cloudplugin.js storeQuery() on both cloud queries; the info window shows
                   "Installed" or the CTA instead of Install/Remove/Upgrade;
                   non-installed grid tiles get .desktop-app-locked

**The plugin store is a mock on desktop.** The cloud catalogue has no x86_64
builds at all -- everything in it is arm-a7 (Duo), aarch64-a53 (Duo X),
aarch64-a35 (Dwarf) or aarch64-a76. Querying with MOD Desktop's own
`bin_compat` (`linux-x64_64`) returns nothing, which is why the store used to
be hidden here. `DesktopApp.storeQuery()` therefore rewrites the query to
browse as a Dwarf, and **deletes `image_version`** -- MOD Desktop's `VERSION`
is its own release number and matches no device image, which would zero the
result set again. Plugin URIs are shared between device and store, so the
existing local/cloud merge still marks installed plugins correctly.

Mustache partials for the widgets live in `html/include/desktop-app/` and are
exposed as `TEMPLATES['desktop_app_<name>']`. That subdirectory only works
because `BulkTemplateLoader` (`mod/webserver.py`) has a second pass for it --
its main loop is a flat listdir filtered on `^[a-z_]+\.html$`, which skips
subdirectories and rejects hyphens.

**`desktop-app.js` is the seam.** Any behaviour you want to differ on MOD
Desktop goes there or is gated on `DesktopApp.isActive()` / `USING_MOD_DESKTOP`,
unless it is genuinely a server-side concern.


## 3. The environment contract

mod-ui has no config file. `mod/settings.py` is a flat read of `MOD_*` env
vars, and whoever launches mod-ui owns them. This is the single most useful
table for understanding why the desktop app behaves differently.

Values marked (default) are not set by that launcher at all; they are the
`mod/settings.py` fallback.

    variable                    device (MBS mod-ui.run)  desktop (cxfreeze/systray)
    --------------------------  -----------------------  -------------------------
    MOD_DESKTOP                 unset                    1
    MOD_DEVICE_WEBSERVER_PORT   80 (default)             18181 (B) / derived (C)
    MOD_DEVICE_HOST_PORT        5555 (default)           18182 (B) / derived (C)
    MOD_DATA_DIR                /root/data               ~/Documents/MOD Desktop
    MOD_USER_FILES_DIR          /data/user-files (def.)  <DATA_DIR>/user-files
    MOD_USER_PLUGINS_DIR        ~/.lv2 (default)         <DATA_DIR>/lv2
    MOD_USER_PEDALBOARDS_DIR    ~/.pedalboards (def.)    <DATA_DIR>/pedalboards
    MOD_FACTORY_PEDALBOARDS_DIR /usr/share/mod/... (d.)  <appdir>/pedalboards
    MOD_KEYS_PATH               /root/keys/              <DATA_DIR>/keys
    MOD_HARDWARE_DESC_FILE      /etc/mod-hardware-       <appdir>/mod-hardware-
                                descriptor.json          descriptor.json
    MOD_IMAGE_VERSION_PATH      /etc/mod-release/release <appdir>/VERSION
    MOD_HTML_DIR                <prefix>/share/mod/html  <appdir>/html
    MOD_MODEL_TYPE              per product              "MOD Desktop"
    MOD_DEVICE_KEY              /var/cache/mod/key       generated once, fake
    MOD_DEVICE_TAG              /var/cache/mod/tag       generated "MDS-..." tag

Sources to read when this drifts:

    mod-build-system/builds/rootfs/package/mod-ui/mod-ui.run
                                                 the device-side env
    mod-desktop/utils/cxfreeze/mod-ui-setup.py   the python-side env, the
                                                 authoritative desktop contract
    mod-desktop/src/systray/utils.cpp            initEvironment(), the process
                                                 -side env (paths, UID, JACK)
    mod-desktop/src/plugin/utils.cpp             the plugin variant of the same;
                                                 the comment in systray says
                                                 the two MUST stay in sync

Two traps in that table:

  - `MOD_LV2_PATH` is set by systray but is **not** a mod-ui variable. mod-ui
    reads `MOD_USER_PLUGINS_DIR`; `MOD_LV2_PATH` is consumed by systray itself
    when launching jackd/mod-host. Do not add it to `mod/settings.py`.
  - The desktop generates a *fake but persistent* device key and tag. So
    `using_mod` can be true-ish on desktop; that is precisely why
    `USING_MOD_DEVICE` subtracts `using_desktop` rather than just testing the
    key.


## 4. Request path: where a page actually comes from

    GET /  ->  302  ->  GET /?v=<cachebuster>
                          |
                          v
      TemplateHandler (mod/webserver.py) .index()
        reads: hardware descriptor, prefs, favorites, session/host state,
               settings.py constants (cloud URLs, TONE3000_*, DESKTOP)
        renders html/index.html as a TORNADO template ({{ }} / {% %})
                          |
                          v
      html/index.html: a wall of `var X = {{x}}` globals, then
      $(document).ready -> new Desktop({ ...element refs... })
                          |
                          v
      html/js/desktop.js: the central controller, on EVERY platform. Builds
      every "box" (overlay panel), wires every #main-menu icon, owns
      websocket setup via host.js. Not MOD Desktop-specific -- see 2.4.

Static assets under `html/` are served straight off disk by
`TimelessStaticFileHandler` (the catch-all `(r"/(.*)")` route). Mustache
partials in `html/include/` are bundled into the `TEMPLATES` object by
`BulkTemplateLoader`.

Practical consequence, and it is a big one:

    editing html/ needs NO restart (index.html is re-rendered per request,
    js/css are served from disk). Only mod/ and utils/ changes need one.

The other direction is the WebSocket: `/websocket` -> `ServerWebSocket`,
fanned out from `mod/session.py` `msg_callback`, consumed in `html/js/host.js`.
There is no "rescan"-style client-to-server command in the dispatcher; adding
one means touching `on_message` in `ServerWebSocket`.


## 5. Frontend layout, and the overlay-box pattern

    html/
      index.html            server-rendered shell. Globals, #main-menu markup,
                            every overlay panel, the Desktop({...}) element map.
      settings.html         the separate settings screen (#mod-settings).
                            HIDDEN on desktop by DesktopApp.setup().
      pedalboard.html       standalone pedalboard render (screenshots).
      tone3000-callback.html  our OAuth landing page, served from our origin.
      desktop-tou.html
      desktop-pp.html       Terms / privacy, linked from the cloud-terms block
                            in index.html. NOTE the naming trap: the text of
                            both is written about MOD Desktop specifically,
                            but the DEVICE arm of that dialog links to them
                            too (index.html:404,406). Pre-existing mismatch;
                            new device-flavoured copy is a call for Gian.
      include/*.html        Mustache partials -> js/templates.js TEMPLATES
      include/desktop-app/  MOD Desktop widgets -> TEMPLATES['desktop_app_*']
      css/main.css          the sprite sheet lives here; icons are
                            background-position offsets
      css/desktop-app.css   MOD Desktop styles, all scoped under .desktop-app
      js/
        desktop.js          THE controller, all platforms. elements map,
                            makeXBox factories, dev-mode toggles.
        desktop-app.js      the MOD Desktop seam. See section 2.4.
        window.js           WindowManager: makes the full-screen #*-library
                            panels mutually exclusive.
        pedalboard.js       the constructor canvas (drag/drop, cables).
        modgui.js           per-plugin GUI build, incl. file dropdowns.
        hardware.js         addressing / actuators. Reads HARDWARE_PROFILE.
        host.js             websocket + backend command plumbing.
        file_manager.js     iframe box -> port 8081 (browsepy).
        tone3000.js         our popup + PKCE box.

Every bottom-left icon follows the same five-point pattern. To add one:

    1. index.html   add <div id="mod-foo" class="icon" data-message="Foo">
                    inside #main-menu
    2. index.html   add the overlay <div id="foo-library" class="mod-hidden
                    mod-init-hidden"> inside #wrapper
    3. index.html   register fooBox / fooBoxTrigger in the Desktop({...}) map
    4. js/foo.js    JqueryClass('fooBox', {...}) with an options.open, then
                    self.window(options); add the <script> tag in index.html
    5. desktop.js   add to the `elements` map, add makeFooBox(), call it in the
                    constructor; add the statusTooltip() line
    plus css/main.css for the sprite background-position.

`#mod-file-manager` and `#mod-tone3000` are the two worked examples.


## 6. Decision table: where does my change go?

    I want to change...                        edit
    -----------------------------------------  ----------------------------------
    anything visual, any platform              html/ only. No restart needed.
    a new top-level panel/tab                  the five-point pattern in 5
    behaviour that differs on MOD Desktop      desktop-app.js (or gate on
                                               DesktopApp.isActive())
    behaviour that differs on a MOD pedal      index.html USING_MOD_DEVICE block
    behaviour per pedal model                  PLATFORM global (from hwdesc)
    which actuators/addressings exist          the hardware descriptor json,
                                               not mod-ui
    a new server value the page needs          add a key in TemplateHandler
                                               .index() AND a `var X = {{x}}`
                                               line in index.html
    a new HTTP endpoint                        mod/webserver.py: handler class
                                               + a tuple in web.Application
    a new server->browser push                 session.py msg_callback, handled
                                               in js/host.js
    a new browser->server ws command           ServerWebSocket.on_message
    anything about ports/paths/env             NOT mod-ui. mod-desktop's
                                               cxfreeze/mod-ui-setup.py and
                                               systray/utils.cpp, or the MBS
                                               image for a device.


## 7. Repository boundary (important before you commit)

`mod-desktop` does not fork the UI. Its Makefile symlinks:

    build/html          -> src/mod-ui/html
    build/mod           -> src/mod-ui/mod
    build/modtools      -> src/mod-ui/modtools

`src/mod-ui` is a git submodule of the same upstream repo this checkout comes
from, pinned at `3265d63b` (`v0.99.8-3535`). This workspace checkout is
`24aff2e0` (`v0.99.8-3554`), i.e. the pin plus 19 commits: the characterization
test suite and the whole Tone3000 feature.

So:

    - all UI work happens HERE, in mod-ui. There is nothing to edit on the
      mod-desktop side for a UI change.
    - to see a change in an actual MOD Desktop build, the submodule pin has to
      be bumped and mod-desktop rebuilt. Follow mod-desktop/AGENTS.md; that
      build has its own worktree and attempt-record discipline.
    - the desktop build has never seen the Tone3000 work. Anything in this doc
      about Tone3000 + desktop is untested by construction.


## 8. Known traps at the boundary

  - **`#mod-tone3000` is not touched by `DesktopApp.setup()`.** The Tone3000
    icon will therefore appear in MOD Desktop. Whether that is right is a
    product decision; it is currently unconsidered, not decided.

  - **The Tone3000 flow uses `window.open`, not an iframe** (see the header
    comment in `js/tone3000.js` - SameSite=Lax cookies force a top-level
    context). Shape B (system browser) is fine. Shape C (embedded WebView) is
    an open question: popup handling differs per platform WebView and may need
    an explicit "open in browser" fallback. Untested.

  - **`#mod-buffersize` is hidden on desktop.** It is `mod-hidden` in markup and
    only revealed by `enable_dev_mode()`, which `index.html` calls only in the
    `else` branch of the `using_desktop` test. JACK buffer size is arguably more
    relevant on desktop than on a pedal. Probably a bug; deliberate change to
    `DesktopApp.setup()` if you want it.

  - **Settings screen unreachable on desktop.** `DesktopApp.setup()` hides
    `#mod-settings`, so nothing in `settings.html` can be reached from the
    desktop UI. Some of it (audio prefs) would apply.

  - **The store's "installed" marking depends on URI equality.** The mock
    catalogue is the Dwarf's, and a desktop plugin is only shown as installed
    if its LV2 URI matches the cloud one exactly. That holds for the bundled
    set today (verified: 8 of 9 local plugins match), but a desktop-only
    plugin with its own URI will look un-installed in the store.

  - **Loopback-only binding.** With `MOD_DESKTOP=1` the server binds
    `127.0.0.1`. Fine locally; it means the LAN origin does not exist, so any
    LAN-origin concern (the Duo's plain-HTTP secure-context problem, phone
    access) is silently untestable in desktop mode.

  - **Three-state platform detection.** See 2.3. `!USING_MOD_DEVICE` is not
    "desktop".

  - **Decompiled artifacts at the repo root.** `webserver.py`, `webserver.pyc`,
    `webserver.py~` are uncompyle6 output, not source. The real file is
    `mod/webserver.py`.


## 9. What the local harness can and cannot prove

`scripts/run-mod` (shape D) runs mod-ui alone against `mod-fs/`. As of this
writing it also accepts `MOD_DESKTOP=1`:

    MOD_DESKTOP=1 ./scripts/run-mod restart     # renders using_desktop=true
    ./scripts/run-mod restart                   # back to neither-device-nor-desktop

That gives you a real `DesktopApp.setup()` run and a real desktop-shaped page, which is
enough for essentially all layout, panel, and control-visibility work.

It does NOT give you: jackd, mod-host, real audio, the real desktop hardware
descriptor (`PLATFORM` stays "Unknown" unless you point
`MOD_HARDWARE_DESC_FILE` at mod-desktop's json), the embedded WebView of shape
C, or the systray's native menus. Anything that depends on those has to be
checked against an actual MOD Desktop build.
