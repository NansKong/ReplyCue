# 0.1.2 — Clean shutdown and Windows branding

Closing the workspace with the title-bar X previously destroyed its native window before `before-quit` called `hide()`. That reproduced the reported `TypeError: Object has been destroyed` at main.cjs:98. The main process now releases closed window references, checks window lifetime before using them, ignores late ready/state/show events during shutdown, and sends the engine one graceful shutdown request. Second launches cannot reopen a closing workspace.

The desktop shortcut used the Electron logo because `signAndEditExecutable: false` disabled executable resource editing as well as signing. The build now uses `signExecutable: false`, which preserves icon/metadata embedding for this unsigned preview. The canonical website favicon generates eight ICO sizes from 16 through 256 pixels. The desktop executable, installer, uninstaller, native backend executable, and native window icon use that artwork. The stable Windows application ID matches the installer.

Install `releases/windows/Copilot-Setup-0.1.2.exe` into the same folder as the existing installation (`E:\copilot` on the development machine). Existing per-user API settings are retained. The website download now points to 0.1.2. Audio capture and answer generation behavior are unchanged.

## Reproducible checks

- `node --test tests/lifecycle.test.cjs`: title-bar close, repeated quit, late events/second launch, and an already-stopped engine. Before the fix the test reproduced the exact reported stack trace.
- `node scripts/check-packaged.cjs`: boots the actual packaged desktop with an isolated profile, checks the UI/preload/backend connection, then verifies title-bar close and application quit both exit cleanly. It makes no cloud calls and captures no audio.
- `node scripts/check-icons.cjs`: inspects executable PE resources and compares every embedded icon size with the favicon-derived ICO in the desktop executable, backend, and installer.
- `backend/test_bridge.py -v`: source and frozen backend transport checks, including the synthetic audio buffer check.

`Build.ps1` regenerates icons and runs these checks before copying the installer to the website download directories.

## Validation results

On November 3, 2026, all four lifecycle regression tests and all three bridge tests passed. The Next.js production build and TypeScript checks passed. The actual packaged app passed both close modes with exit code 0, including the preload, local assets, and engine connection checks. All eight icon sizes matched the canonical ICO byte-for-byte in each of the three checked executables. Both website installer copies matched the release SHA-256. No real meeting audio or paid API requests were used.

References: [Electron window lifecycle](https://www.electronjs.org/docs/latest/api/browser-window), [electron-builder v26 Windows configuration](https://www.electron.build/v26/docs/win/).
