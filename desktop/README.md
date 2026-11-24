# MOD UI desktop

Just a tiny [Tauri](https://tauri.app/) wrapper around the HTML frontend, so
that it behaves more like an application than a web page. Personally I prefer
this behaviour but maybe that's just me.

There's not really any significant code or logic here, it just connects to the
backend and renders the result.

## Development

Start the backend, eg. using
[mod-desktop](https://github.com/mod-audio/mod-desktop). That should serve the
UI on `http://localhost:18181`.

You need
[Cargo and Rust installed](https://doc.rust-lang.org/cargo/getting-started/installation.html).

Install the Tauri CLI once, then run the desktop application:

```sh
cargo install tauri-cli --version '^2.0.0' --locked
cd desktop
cargo tauri dev
```

The platform-specific prerequisites listed in the
[Tauri documentation](https://v2.tauri.app/start/prerequisites/) are required.

## Packaging

Build an installer or application bundle on each target operating system:

```sh
cd desktop
cargo tauri build
```

Tauri uses the operating system's native WebView, so Windows, macOS, and Linux
packages should be built on their respective platforms. The packaged app still
expects MOD UI to be available at `http://localhost:18181`; no backend files are
embedded in the application.

You can also specify the package format:

```sh
cargo tauri build --bundles deb
# or
cargo tauri build --bundles rpm
# or
cargo tauri build --bundles appimage
```

## Backend address

The backend address is intentionally defined only in `tauri.conf.json`, in both
`build.devUrl` and `build.frontendDist`. If the local server address changes,
update both values together.

## AI declaration

Code largely written by Codex (and reviewed by me).
