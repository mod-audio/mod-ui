const DISABLE_CONTEXT_MENU: &str = r#"
if (window.location.origin === "http://localhost:18181") {
    document.addEventListener("contextmenu", function (event) {
        event.preventDefault();
    });
}
"#;

fn desktop_behavior<R: tauri::Runtime>() -> tauri::plugin::TauriPlugin<R> {
    tauri::plugin::Builder::new("desktop-behavior")
        .js_init_script(DISABLE_CONTEXT_MENU)
        .build()
}

fn main() {
    tauri::Builder::default()
        .plugin(desktop_behavior())
        .run(tauri::generate_context!())
        .expect("failed to run the MOD UI desktop application");
}
