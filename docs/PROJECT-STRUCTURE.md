# Copilot application and website

```
teleprompter/
  apps/
    website/              Next.js App Router, TypeScript, shared visual system
      app/page.tsx        Public product website
      app/desktop/        Windows setup UI (also viewable without a backend)
      components/         Reader demo, workspace, brand
      public/downloads/   Built installer copied here after packaging
      out/                Static production website
    windows/
      electron/           Sandboxed desktop host and narrow preload API
      backend/            Python transport and PyInstaller configuration
      Build.ps1           Build website, engine, checks, and NSIS installer
      Launch.cmd          Run the development Windows application
  packages/
    engine/               Existing Python engine and native overlay, unchanged
      tests/              Existing engine regression tests
  docs/                   Architecture, design references, release instructions
  releases/windows/       Installer and standalone application directory
```

The original root Python files and Launch.cmd remain available as the previous native-only version. New app work uses packages/engine as its engine source. Avoid changing the two copies independently; future engine fixes should target packages/engine. No .env file is copied into that package or the release.

## Architecture

Next.js exports static HTML, JS, local fonts, and CSS. Electron loads only those bundled files on the `copilot://app` protocol. Context isolation, sandboxing, navigation restrictions, denied browser permissions, sender checks, and a restricted preload API separate the UI from the OS.

Electron starts the Python engine as a hidden child process. JSON messages travel over inherited stdin/stdout pipes; no HTTP API or network listener is opened by the app. A small adapter calls the original Studio methods. It replaces only native setup-window visibility with Electron show/hide events. Transcription, answer generation, session memory, provider calls, reading pace, and the native overlay remain unchanged.

Setup UI is visible to ordinary screen capture. The native reader retains the existing Windows capture setting. Receiver-side meeting compatibility remains unverified; no universal invisibility guarantee is made.

## Local configuration

Development reads the existing root `.env`. The installed app reads `%APPDATA%\copilot-windows\.env` (the Connections screen displays the exact location). Add keys in Connections once; blank fields preserve existing values. They stay in a plaintext backend configuration file protected by the user's normal filesystem permissions. Keys are never returned in state snapshots and are not included in the website or installer. API calls still go directly from Python to Groq and Replicate.

Documents and conversation text remain in memory. There are no new accounts, analytics, external fonts, or telemetry. Model selections continue to come from the backend .env. Closing the app requests cancellation and waits for existing workers to finish, as in the original engine.
