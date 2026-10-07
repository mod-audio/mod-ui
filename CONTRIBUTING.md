# Contributing to mod-ui

mod-ui is the web interface and Python backend of **MOD OS** (MOD Duo, Duo X, Dwarf) and of
**MOD Desktop** (Linux, Windows, macOS). One code base serves both products. This file explains
how the branches work, how a change reaches each product, and the rules that keep the two from
drifting apart. Read it before opening a pull request.

## Branches

| Branch | Role |
| --- | --- |
| `master` | The trunk. Every change starts here, as a pull request. |
| `plugin-store` | Receives `master` periodically. Release lines are cut from it. |
| `hotfix-<version>` (for example `hotfix-1.14`) | The release line of one MOD OS version. Only fixes that the release needs, each cherry-picked from `master`. Tagged `v<version>.<build>` per published build. |

Rules that follow from this:

- **Never commit directly to `plugin-store` or a `hotfix-*` branch.** A fix lands on `master`
  first and is cherry-picked by the maintainers. If a fix only makes sense on the release line,
  say so in the pull request and it will be handled as an exception.
- **Do not keep long-lived feature branches** that diverge from `master`. Rebase onto `master`
  before asking for review. A branch that lives for months becomes a second code base; mod-ui
  has paid for that once already with MOD Desktop.
- Releases are cut from `plugin-store` and the `hotfix-*` line, never from `master` directly.

## Two products, one code base

MOD Desktop runs the very same mod-ui as the devices, from the same commit. The differences are
handled at **run time**, behind one flag, and at **packaging time**, by what each product ships:

- **Behaviour**: anything Desktop-only lives behind `MOD_DESKTOP=1` (`settings.DESKTOP` in
  Python, `DesktopApp.isActive()` in JavaScript, the `desktop_app` template variable). The
  Desktop launcher sets that variable; a MOD device never does. The rendered device page must not
  contain a single Desktop token; a test checks this. Desktop-only assets (`html/js/desktop-app.js`,
  `html/css/desktop-app.css`, `html/include/desktop-app/`, `html/img/desktop-app/`) are served
  only when the flag is on.
- **Packaging**: what ends up in a Desktop package is decided in the
  [mod-desktop](https://github.com/mod-audio/mod-desktop) repository, not here. What ends up on a
  device is decided in the OS build system. Neither keeps a modified copy of any mod-ui file.
- **Pins**: the OS build pins a `hotfix-<version>` commit. **MOD Desktop pins the same commit as
  the OS release line it ships with.** Desktop never pins `master` and never carries its own
  branch of mod-ui. Desktop-only code therefore has to be on the release line too; it is inert
  there, by construction.

What this means for a contributor:

1. If your change is for the devices, it reaches the Desktop automatically at the next pin bump.
   Do not try to exclude the Desktop; if the feature cannot work there (hardware addressing,
   Control Chain, Banks, the Plugin Store, the File Manager), the Desktop seam hides or replaces
   it. Look at `html/js/desktop-app.js` for the pattern.
2. If your change is Desktop-only, it still goes to `master` as a normal pull request, behind the
   flag, with the device-output test passing. It will be cherry-picked to the current release line
   like any other change.
3. Never add a Desktop-specific copy of a file, template or script. One file, one flag.

## How a change travels

```
pull request → master → cherry-pick → hotfix-<version> → tag v<version>.<build>
                                                   ├─ MOD OS image (build system pins the tag)
                                                   └─ MOD Desktop (mod-desktop pins the same commit)
```

A fix shipped to the devices and to the Desktop is therefore always the same commit. When you
report a bug, give the version shown in the address bar (`?v=…`): on a device it is the OS build,
on the Desktop it is the Desktop build, and both identify the mod-ui commit.

## Pull requests

- One feature or fix per pull request, rebased onto `master` (or onto the branch it stacks on,
  stated in the description).
- The contributor keeps authorship. Maintainers may hand-rebase when it saves time, always with
  the original author on the commit.
- Web-UI-only changes merge on review. Anything that writes pedalboard files or reads new
  properties from plugin TTLs touches the shared LV2 vocabulary and needs that discussed first
  (open an issue before the code).
- Every merged change ships on the Testing channel first, then Stable.
- No CLA. Your sign-off on the pull request is enough.
- Do not add generated files, personal editor configuration or credentials. The Tone3000 client
  id and any API key are provided by the environment of the build, never committed.

## Tests

Frontend tests live in `test/js/` and run under Node's built-in test runner against the real
files in `html/`:

```
npm install      # once, pulls in jsdom
npm test
```

Python-side tests are plain `unittest` modules in `test/`:

```
python3 -m unittest discover -s test -p 'test_*.py'
```

A pull request that touches the Desktop seam must keep `test/test_desktop_app.py` and
`test/js/desktop-app*.test.js` green: they assert what the Desktop shows and hides and that the
device output is unchanged with the flag off.

## Questions

Open an issue in this repository, or ask on the [MOD forum](https://forum.mod.audio). Release
and channel decisions are taken by MOD; the rules above are the contract that lets everyone else
work without surprises.
