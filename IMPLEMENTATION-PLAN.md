# Interview Prompter implementation plan

## Product boundary
Windows-first assistant for practice and permitted live assistance. Capture exclusion is a compatibility feature, not universal invisibility or system-level concealment. No process hiding, capture-tool tampering or monitoring bypass is part of the architecture.

## Milestone 1 — Native reading prototype (started)
Deliver a movable, resizable, always-on-top window, note editor, text import, scrolling, font controls and hide control. Request Windows capture exclusion before adding sensitive text; reapply on handle creation. Show failure instead of silently falling back. The editor remains capture-visible. API readback verifies configuration only.

Acceptance: launch on Windows; import notes; update text; pause/restart; resize; hide and reopen; close cleanly. Verify receiver-side video on supported sharing applications before claiming compatibility.

## Milestone 2 — Native application foundation
Install .NET SDK and build a C#/WPF application with separate Audio, Transcription, Retrieval, Generation and Overlay interfaces. Port this disposable PowerShell prototype. Add cancellation tokens, session IDs and structured error states. Store credentials in Windows Credential Manager, not source files. Keep audio in bounded memory buffers by default.

## Milestone 3 — Resume and JD preparation
Accept TXT, PDF and DOCX. Extract text with page/section metadata; OCR only when necessary. Produce an editable candidate profile and separate role requirements. Require explicit selection of document versions for each session. Index chunks for keyword and vector retrieval. JD requirements must never become candidate experience. Treat uploaded text as evidence, never as executable instructions.

Acceptance: replacing a resume removes stale retrieval results; unsupported achievements are flagged; each candidate-specific assertion links to supporting material. Include scanned, multi-column and malformed files in evaluation.

## Milestone 4 — Live audio and transcription
Capture selected meeting playback using WASAPI. Keep optional microphone input separate. Stream transcription using a provider adapter; show interim and final text. Implement device-change detection, reconnect, bounded queues, explicit start/stop and visible capture status. Disclose cloud processing before starting.

Acceptance: headphone playback works; silence does not stall the session; device changes recover; transcription revisions do not duplicate questions. No provider secrets appear in logs.

## Milestone 5 — Questions and grounded answers
Use a turn state machine: listening, candidate question, finalized question, retrieving, generating, complete or interrupted. Combine voice activity, transcript stability and semantic question detection. Resolve follow-ups from actual spoken history, not generated suggestions. Cancel superseded requests. Retrieve and rerank resume/project evidence, then stream a short answer followed by optional details. Freeze text already being read. Provide manual correction and pause controls.

Acceptance: multi-part questions, interruptions, follow-ups, silence and acknowledgments behave correctly. No unsupported personal facts in the evaluation set. Target 2–4 seconds from question completion to first useful text; record p50 and p95 rather than promising this before measurement.

## Milestone 6 — Packaging and verification
Ship signed installer, retention/deletion controls and a compatibility report. Test at least 60-minute mock sessions, interrupted networks, high-DPI monitors and receiver-side recordings. Repeat capture verification after OS or meeting-app changes.

## Capture matrix
Record OS build, meeting-app version, capture mode, monitor scaling, GPU and recording result. Cover whole-display/window sharing, start/stop sharing, launch, resize, restore, monitor changes and reconnect. Mark results pass/fail/unverified with dated evidence. No API success can replace this test.

## Estimated sequence
Prototype and feasibility: 1 week. Native foundation and documents: 1–2 weeks. Audio and transcription: 1 week. Retrieval and live answers: 1–2 weeks. Reliability and release: 1–2 weeks. Re-estimate after the capture/audio prototypes.
