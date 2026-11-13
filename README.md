# ReplyCue

ReplyCue is a Windows app for interview practice. Its floating reader keeps suggested answers close while you speak, and its workspace lets you add a résumé and job description for context.

## Try the Windows trial

[Download ReplyCue for Windows](https://reply-cue.vercel.app/#download) or get the installer directly from the [v0.1.19 GitHub release](https://github.com/NansKong/ReplyCue/releases/tag/v0.1.19).

1. Download and run the installer on Windows 10 or 11 (x64).
2. Open ReplyCue and go to **Connections**.
3. Sign in with a verified email and password, or choose Google or GitHub to sign in through your browser and return to ReplyCue.
4. Reopen **Connections** to check your remaining trial time. Enable cloud processing and start a session to try live transcription and suggested answers.

Each verified account receives a one-hour trial for live transcription and suggested answers. Active time accumulates across sessions. Pause or End stops the timer, and closing the app or losing its connection stops counting within 30 seconds of the last check-in. After one hour, that account’s trial stops. Paid subscriptions are coming later.

### Automatic mock assessments (Windows 0.1.22)

Open **Mock assessment**, choose a question type and coding language, allow cloud processing, and choose **Start mock session**. Drag around the question area once. ReplyCue then watches that area, waits for changed content to settle, and generates coding solutions or MCQ explanations automatically. No repeated capture or confirmation is required. Use **Change question area** to select another region.

Answers appear in the overlay, the mock workspace, and session history. Unchanged questions are suppressed locally, and only one answer request runs at a time. Pause and End stop screen reading and the trial timer. Screen images stay in memory and only the selected region is sent for analysis. Mock mode does not capture audio. Include all options, diagrams, constraints, and function signatures in the region. Generated code is not executed. This feature is for mock assessments and permitted assistance; it does not promise to be undetectable by monitoring software.

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
