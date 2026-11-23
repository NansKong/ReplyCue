# ReplyCue

ReplyCue is a Windows app for interview practice. Its floating reader keeps suggested answers close while you speak, and its workspace lets you add a résumé and job description for context.

## Try the Windows trial

[Download ReplyCue for Windows](https://reply-cue.vercel.app/#download) or get the installer directly from the [v0.1.27 GitHub release](https://github.com/NansKong/ReplyCue/releases/tag/v0.1.27).

1. Download and run the installer on Windows 10 or 11 (x64).
2. Open ReplyCue and go to **Connections**.
3. Sign in with a verified email and password, or choose Google or GitHub to sign in through your browser and return to ReplyCue.
4. Reopen **Connections** to check your remaining trial time. Enable cloud processing and start a session to try live transcription and suggested answers.

Each verified account receives a one-hour trial for live transcription and suggested answers. Active time accumulates across sessions. Pause or End stops the timer, and closing the app or losing its connection stops counting within 30 seconds of the last check-in. After one hour, that account’s trial stops. Paid subscriptions are coming later.

### GitHub project context (Windows 0.1.27, based on 0.1.19)

Mock-assessment work is preserved separately on `archive/mock-assessments-v0.1.23`. This release starts from the 0.1.19 interview engine and floating reader, retaining managed sign-in and installer checks.

Open **GitHub projects** and choose **Connect GitHub**. Authorize in your browser, then return to ReplyCue. The app automatically discovers public repositories owned by the connected account (up to 500) and prepares metadata, README, dependency files and selected source, architecture, training/evaluation and test-file excerpts from the ten most recently pushed original projects, using forks if fewer original projects are available. No username, repository URL, private repository access, or repository write permission is needed. Checkboxes let you change the ten projects included in interview context; **Sync projects** refreshes the list and selected snapshots. Changes apply to the next session.

The GitHub OAuth token is verified against GitHub's `/user` endpoint, stored using Windows user-scoped DPAPI encryption, and sent only to `api.github.com`. It is never returned to the setup UI or included in AI prompts. The connection survives app restarts; **Disconnect GitHub** or signing out of ReplyCue clears it and local project context. Expired or revoked authorization prompts reconnection. GitHub's authenticated API limits still apply. The browser callback uses a single-use nonce and loopback POST; project authorization uses a separate in-memory Firebase instance so it does not replace your website sign-in.


Résumé and JD context are source-separated, with coverage across the document and question-specific evidence. The model is instructed to consider all supported projects, use a different project when asked for another, and avoid treating JD requirements or repository code as verified personal achievements. Prior suggestions remain explicitly unverified. Selected repository excerpts may be sent to AI when cloud processing is enabled.

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

### Managed Windows release builds

Install `apps/windows/backend/requirements-build.txt` in the root Python environment. For a distributable account-based installer, set `REPLYCUE_DESKTOP_FIREBASE_API_KEY` to the public desktop Firebase Auth key and `REPLYCUE_GATEWAY_URL` to `https://replycue-gateway.vercel.app/api/ai`, then run `apps/windows/Build.ps1 -ManagedRelease`.

The website's default `managed-config.json` deliberately has empty fields. The managed release script injects the desktop configuration into the exported UI before packaging. `npm run dist` rejects missing production configuration, and packaged startup tests require `managed: true`. Do not package a fresh website export directly as a managed release.

Deep project questions use file-labelled repository excerpts and focus retrieval on a named repository when available. Sync samples up to eight extra files within a bounded local snapshot; it does not index every source file or execute repository content. Exact experimental numbers are used only when present in the supplied evidence. Refresh previously synced projects to obtain the deeper context.
