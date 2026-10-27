# Shared External App slots (site customization)

This is a narrowly scoped server-persistence customization for `external-app-tab`
`external-app-tab-2`, and `external-app-tab-3`, not a change to the generic browser-local extension
settings contract.

- Authority: `STATE_DIR/external-apps.json`, installation-wide for this WebUI's
  authenticated owner. It is not scoped to a chat or browser origin. This is not
  a multi-user per-account settings implementation.
- Defaults: App 1 = NAS Recovery (`/apps/nas-recovery/`), App 2 = OpenCVE
  (`/apps/opencve/`); App 3 is blank with label `App 3`. Origin-free built-in paths work on LAN and public hosts.
- `GET /api/external-apps` reads both slots; `POST` updates exactly one allowlisted
  slot with `{id,url,label}`. Both run after authentication; writes use the core
  CSRF/origin gate, bounded JSON, validation, a process lock and atomic mode-0600
  replacement. Configured URLs are iframe destinations, never server proxy targets.
- Custom Configure handlers pass the runtime context into the editor and invoke
  `restoreFocus()` exactly once on Save, Cancel, backdrop dismissal, Escape or
  replacement. Otherwise Settings retains its disabled `Opening…` state forever.
  Editors use z-index 1150 above the core dialog layer (1100), and focus the label
  input so Escape is received. Both slots have real-runtime lifecycle regressions.
- A successful dialog save means the server acknowledged persistence. Errors
  retain the dialog and prior config. No localStorage migration can overwrite
  shared state. Clearing browser data cannot delete server configuration.
- Both manifest formats have empty `settings_schema`; the custom Configure
  registration opens the shared editor from Settings → Extensions as well as
  the app overlay. The former scalar editor intentionally no longer exists.
- This directory contains portable extension bundles (original attribution
  retained). Install them into the two existing extension directories; preserve
  the installation manifest and unrelated extensions. Do not reinstall from
  the gallery without reapplying this customization, since that replaces files.
- Backend changes require a WebUI restart. Wait for active runs to drain; do not
  restart the process hosting an unfinished agent response. Refresh browser pages
  after deployment. Already open pages do not live-sync changes from other devices.
- Runtime settings, signing keys and cookies must never enter source control.

## Verification

Run `HERMES_WEBUI_TEST_STATE_ROOT=<isolated-owned-path> ./scripts/test.sh -q
 tests/test_external_apps.py tests/test_extension_settings_runtime.py
 tests/test_extensions_settings_panel.py tests/test_opencve_app_bridge.py
 tests/test_issue1909_csrf_token.py tests/test_server_repo_root_bootstrap.py`.

Real-browser isolated fixture verification covered two independent browser
contexts with empty localStorage, saving via Configure, readback on the second
context, independent iframe URLs, rejected save retaining prior config, and
390px mobile dialog bounds. Embedded test pages were synthetic; the actual
NAS/OpenCVE endpoints need separate deployed HTTP verification. App login
sessions remain independent of persistent slot configuration.
