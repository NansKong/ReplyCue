# ReplyCue

ReplyCue is a Windows app for interview practice. Its floating reader keeps suggested answers close while you speak, and its workspace lets you add a résumé and job description for context.

## Try the Windows trial

[Download ReplyCue for Windows](https://reply-cue.vercel.app/#download) or get the installer directly from the [v0.1.17 GitHub release](https://github.com/NansKong/ReplyCue/releases/tag/v0.1.17).

1. Download and run the installer on Windows 10 or 11 (x64).
2. Open ReplyCue and go to **Connections**.
3. Sign in with a verified email and password, or choose Google or GitHub to sign in through your browser and return to ReplyCue.
4. Reopen **Connections** to check your remaining trial time. Enable cloud processing and start a session to try live transcription and suggested answers.

Each verified account receives a one-hour trial for live transcription and suggested answers. Active time accumulates across sessions. Pause or End stops the timer, and closing the app or losing its connection stops counting within 30 seconds of the last check-in. After one hour, that account’s trial stops. Paid subscriptions are coming later.

### Floating reader controls

- **Shift+M** expands the reader; **Shift+N** collapses it. The shortcuts work while the session overlay is open and another app, such as Meet, has focus. They are released while you type in the ReplyCue workspace.
- Click the pill or press **Shift+M** to expand. Use the arrow or **Shift+N** to collapse.
- Drag the pill or the grip in the expanded header to move the overlay. Its position is remembered across launches and kept on screen.

The installer is **unsigned**, so Windows may show an **Unknown publisher** or SmartScreen warning. The GitHub release notes include the installer’s SHA-256 checksum.

## Develop locally

| Folder | Purpose |
| --- | --- |
| `apps/website` | Public website, web account pages, and Windows workspace UI |
| `apps/windows` | Electron host, Python bridge, and Windows installer build |
| `apps/gateway` | Firebase authentication, trial allowance, and server-side AI request controls |
| `packages/engine` | Python audio capture, answer processing, and floating reader |
| `docs` | Setup, architecture, and validation notes |

From `apps/website`, run `npm ci` and `npm run dev` to preview the website locally. See [build and run](docs/BUILD-AND-RUN.md) for the desktop build and [managed beta setup](docs/MANAGED-BETA.md) for gateway configuration. Keep service-account credentials and provider keys in server configuration.
