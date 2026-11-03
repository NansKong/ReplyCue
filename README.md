# Copilot — Windows app + Next.js website

The project now has a Next.js setup workspace in a packaged Windows app, plus a matching product website. The existing Python engine and floating reader are preserved.

## Open it

- **Windows app, no installation:** double-click `Launch-Windows.cmd`.
- **Windows installer:** `releases/windows/ReplyCue-Setup-0.1.6.exe`.
- **Website development:** double-click `Launch-Website.cmd`, then open http://127.0.0.1:3000.
- **Original native-only version:** the original `Launch.cmd` remains available.

For the packaged app, open Connections and enter your API keys once. Keys from the development .env are not distributed with the app. Do not share your personal .env.

## Folders

| Folder | Purpose |
| --- | --- |
| apps/website | Next.js website and desktop UI |
| apps/windows | Electron host, Python adapter, installer build |
| packages/engine | Unchanged Python engine and native overlay |
| docs | Design references, architecture, build instructions, checks |
| releases/windows | Installer, standalone folder, checksum |

Read [project structure](docs/PROJECT-STRUCTURE.md), [build and run](docs/BUILD-AND-RUN.md), [design references](docs/DESIGN-REFERENCES.md), and [validation](docs/VALIDATION.md).

This is an unsigned Windows x64 preview. The website is built locally and ready to host. Live meeting and fresh-machine installation checks remain to be done.
