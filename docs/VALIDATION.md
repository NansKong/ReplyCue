# Preview validation — 3 November 2026

Passed:
- Next.js 16.4.4 production static export and TypeScript compilation for `/`, `/desktop`, and the icon route.
- Source and frozen Python transport integration tests: initial state, synthetic credential saving, text document import, no-start without cloud consent, secrets omitted from outgoing messages, clean process shutdown.
- Development and packaged Electron `--check`: local page loaded, preload initialized, zero failed local assets, Python state response received, exit code 0.
- All 22 existing engine test assertions report OK. The pre-existing unittest process still exits 1 during Qt interpreter teardown; this is not counted as a clean suite process exit.
- Browser visual checks at desktop and mobile sizes, functioning website example selection, workspace navigation, responsive page width with no horizontal overflow at the tested mobile size.
- Byte-for-byte comparisons of all seven copied engine Python files against the original root files.
- NSIS installer built successfully from official runtime/tool archives. Electron and manually downloaded NSIS resources were verified against upstream hashes.

Limits:
- The native computer-use inspector failed to attach reliably to the Electron window, so native mouse/keyboard end-to-end verification is incomplete. The same Next.js layout was visually inspected in the browser, and the packaged shell/bridge was verified programmatically.
- No real interview audio or paid model calls were used. Live provider behavior and receiving-side screen-sharing compatibility remain unverified.
- The installer has not been tested on a fresh Windows machine. It is unsigned; no signing certificate was supplied.
- Runtime npm audit: zero advisories. Build toolchain: 15 moderate development-only findings in the current electron-builder dependency graph.

The website is a local static export, not a public deployment. The final installer is available in its `/downloads` directory. No personal .env is part of the release.
