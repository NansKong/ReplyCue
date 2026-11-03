# Interview Copilot — Windows development build

Run Launch.cmd. Installer packaging is deferred.

## Setup and use
1. Set REPLICATE_API_TOKEN and GROQ_API_KEY in .env; configuration is reread when starting a session; save edits before clicking Start session. Keys remain in backend configuration, never in the UI. Keep .env private. Environment variables take precedence.
2. Import or paste your resume and job description, then review the extracted text. Background changes apply on the next session.
3. Allow cloud processing and select Start session. Setup hides; a compact listening indicator appears near the camera at the top of the screen.
4. Return to Google Meet or another meeting. Playback audio is captured from the default Windows output device, including other apps. The assistant transcribes speech, combines nearby fragments, retrieves background context and automatically suggests answers.
5. The overlay expands when an answer arrives. Use Pause/Resume, Setup, End, Glass and font controls. Click the compact tab to expand; the top chevron or Escape collapses. Setup pauses the session and opens settings; resume from the overlay. End restores setup.

## Conversation handling
Groq transcription and Gemini answer generation run independently. A bounded audio queue keeps incoming turns while answers are generated. If transcription falls behind by eight queued turns, the session stops with an explanation instead of silently discarding questions. Finalized fragments use a 200 ms debounce after transcription. New heard turns do not cancel the current answer. Follow-up text waits until that answer finishes; an unfinished answer is not erased by incoming speech. Question/acknowledgment recognition remains model-based. Actual spoken candidate microphone history is not captured, so follow-up context is limited to heard playback turns. Generated suggestions are never recorded as spoken answers.

The Session transcript tab holds heard turns in memory. No local recording or automatic transcript/document saving. Incremental answer text preserves the reader position instead of resetting it. Replicate SSE is requested when available, with a short stream timeout and fallback polling of the same prediction. Schema metadata is cached for five minutes. Unsupported or slow streaming does not create duplicate predictions.

## Providers
GROQ_STT_MODEL=whisper-large-v3-turbo
REPLICATE_ANSWER_MODEL=google/gemini-2.5-flash

Groq audio is uploaded as an in-memory multipart WAV request. Gemini receives the transcript and selected resume/JD context via Replicate. Provider data handling and charges apply. Use a Groq free-plan project and check account limits: the app cannot enforce the provider billing plan. Rate-limit/authentication errors stop listening; no automatic paid transcription fallback. Already submitted requests may still finish and incur charges. Prediction cancellation is best effort.

## Current limitations
Pause-based segmentation (0.65 seconds silence, 20-second turn cap) plus 200 ms grouping delay; lexical retrieval rather than embeddings; no automatic device switching, diarization, microphone history or OCR. Scanned PDFs require OCR. Real API execution, latency and accuracy still require a trial with your configured keys. No universal invisibility claim: native capture-setting readback is checked, while Google Meet receiving-side verification is explicitly deferred. Setup remains capture-visible when opened.

## Validation
Run .venv\Scripts\python.exe -m unittest discover -s tests -v
Six tests cover Groq multipart upload, interruption, quota handling without fallback, Groq-to-Gemini routing, incremental answer display and transcription while generation is busy. Startup smoke check: .venv\Scripts\python.exe app.py --check. Development tests use mocks and do not upload actual audio or spend credits.

Never distribute .env or a personal key. Any shared service key must eventually live on a server; packaging it inside an EXE does not protect it.

Startup fix: configuration is reread on demand and missing cloud consent is reported separately from missing credentials. Provider requests include an application User-Agent. Nine tests cover the session and configuration flow. Read-only provider authentication checks succeeded; paid model execution is still unverified.


## Answer continuity and current-session memory
Incoming speech no longer interrupts an answer. The current answer remains visible until a new answer starts, and overflow text has a visible scrollbar. Pause/End still cancels requests intentionally. Heard turns and generated suggestions are retained separately in memory for this session. Recent context is included directly and relevant older turns/suggestions are retrieved by keyword. This does not guarantee perfect recall of every fact, and suggestions are not treated as statements you actually spoke. Starting a new session clears memory; nothing is persisted automatically.

Fifteen tests cover provider routing, quota handling, streaming events, answer continuity, session-memory retrieval/reset and configuration. Live synthetic answer checks succeeded, but latency varied roughly 5–14 seconds; lower local overhead does not guarantee consistently low provider latency.

## Spoken answers and automatic reading
Answer instructions favor a natural spoken explanation: direct response, one example, and a useful distinction/trade-off. Behavioral answers use only supported resume facts. The assistant does not invent credentials or claim to know an interviewer's private preferences.

Auto-scroll is enabled by default. Reading starts after 2.5 seconds, at 160 words/minute by default; adjust the top pace control between 80 and 260 wpm or untick Auto. The pace is approximate and based on rendered document height. Text appended during generation preserves reading position. Manual wheel/scrollbar interaction holds automatic movement for four seconds. Collapsing or pausing suspends movement; a new answer starts from the top. Short answers that fit do not scroll. The final lines remain visible at the end.


## Completion and transcription update
Answer budget raised to 1536 tokens while requested answer length remains at most 120 words. A final answer ending mid-sentence triggers at most one full repair request; this can incur an additional Replicate charge and delay. If that also truncates, the session pauses with an explicit message rather than pretending completion. Completeness detection is punctuation-based, not a guarantee of semantic completeness. Authoritative prediction snapshots are polled; short-lived SSE consumption is disabled for the live answer path.

Transcription WAV uploads are converted in memory from 16-bit mono/stereo PCM to 16 kHz mono. For 48 kHz stereo this reduces payload by approximately 83 percent while preserving duration. Silence endpoint lowered from 650 to 450 ms. Provider and network latency still vary; new end-to-end Groq timing has not yet been measured. Twenty tests include truncation repair/failure and audio resampling checks.


## Scrollable session Q&A
Click History in the overlay to browse all question/suggested-answer pairs for the current session. Click Live to return to the latest answer. Browsing history does not pause listening; incoming results update the stored history without taking over your reader or moving your scroll position. Auto-scroll is disabled while browsing history. The setup window also has a larger Q&A history tab.

Each generated question is paired with its response and completion status. Completed suggestions are retained in model session memory; recent suggestions and relevant older entries are used for follow-ups. All visible entries remain available to scroll back through. Suggested answers are not represented as words actually spoken by the candidate. History remains after End so you can review it, but clears when starting a new session or closing the app. Nothing is saved to disk automatically.

Validation: 22 checks pass, including paired Q&A recording, scroll preservation during incoming updates, returning to live text, and new-session history reset. Startup smoke check passes; no paid API calls were required for this update.
