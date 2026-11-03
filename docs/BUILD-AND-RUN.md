# Run and distribute

## Windows users

Run `releases/windows/ReplyCue-Setup-0.1.6.exe`. It installs per-user and can create a desktop shortcut. This preview is unsigned; it does not claim a verified publisher. No Python or Node installation is needed by the installed application.

On first launch, open Connections and add your own Groq and Replicate keys. The development .env is deliberately excluded from distributable files. Add your résumé and role, enable cloud processing, and start the session. The setup window yields to the native reader. Setup on the reader opens the Next.js workspace. Pausing, resuming, ending, and session history retain their existing behavior.

## Development

- Website: in `apps/website`, run `npm ci`, then `npm run dev` (http://127.0.0.1:3000).
- Static website: `npm run build` creates `apps/website/out`. Serve that directory with any static web server.
- Desktop: build the website first, then in `apps/windows`, run `npm ci`, then `npm start`. Uses the root Python .venv and root .env.
- Engine: Python 3.11; install `packages/engine/requirements.txt`. PyInstaller build dependency is pinned to 6.22.3 in `backend/requirements-build.txt`.
- Installer: run `apps/windows/Build.ps1` in PowerShell after installing JS and Python build dependencies.
- Transport checks: `.venv/Scripts/python.exe apps/windows/backend/test_bridge.py -v`.
- Desktop close regression checks: in `apps/windows`, run `npm test`.
- Packaged startup/close checks: in `apps/windows`, run `node scripts/check-packaged.cjs`.
- Embedded Windows icon checks: in `apps/windows`, run `node scripts/check-icons.cjs`.
- Engine checks: `.venv/Scripts/python.exe -m unittest discover -s packages/engine/tests -v`.

The engine spec excludes unrelated ICU libraries discovered on PATH because Qt uses Windows' ICU API. Preserve this rule when updating the packaging configuration.

`Build.ps1` copies the finished installer into the website download directory. The Electron build excludes that download directory to avoid recursively bundling the installer. The website is local and ready to host; no domain, public hosting, or release upload is configured.

## Release notes

This is an unsigned Windows x64 preview. Code signing, automatic updates, and a fresh-machine install test remain release tasks. Installer signing requires the publisher's certificate or signing service; none is supplied.

The website and runtime production npm dependency audits report no vulnerabilities at build time. The latest electron-builder toolchain currently reports 15 moderate development-only advisories through its minimatch dependency graph. They are not shipped as runtime dependencies; no unsupported major-version override or downgrade was forced.

No paid provider calls are made by the packaging checks. Live meeting latency, provider behavior, and screen-sharing compatibility require a real session separately.
