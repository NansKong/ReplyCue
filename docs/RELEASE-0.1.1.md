# 0.1.1 — Playback capture fix

- Release the buffered question after 450 ms without further callbacks. Previously the capture loop only counted explicit silent PCM buffers, so a WASAPI endpoint that stopped callbacks could leave a question pending indefinitely.
- Compute turn duration from actual PCM byte counts, not an assumed 1024-frame callback size.
- Detect quieter playback (PCM16 RMS threshold 60, previously 180), retain a short pre-roll, and discard very short clicks/silence.
- Select the meeting's speaker/headphone loopback device in the Windows workspace. Windows default remains the default; Refresh discovers changed endpoints before a session.
- Surface the current source and playback signal level. After six seconds without detected playback, the reader displays a useful hint instead of only Listening. This is a signal indicator, not a speech-recognition confidence score.
- Queue overflow and stopped streams surface an error rather than silently dropping audio.
- Startup smoke checks use an isolated temporary profile and do not interfere with an existing installed instance.

Tests use synthetic PCM and mocked cloud responses, including the complete capture → transcription → question → answer path. They do not capture a real meeting or spend API credits. Real Meet routing still needs a user retest with the selected device.

Install Copilot-Setup-0.1.1.exe after ending the current session and closing the old app. Your per-user .env is retained. In Meet, check Settings → Audio → Speakers and select the matching Audio source in Copilot before starting.

Reference: https://support.google.com/meet/answer/10409699?hl=en

Validation: six new audio/pipeline regression tests pass; all 28 engine assertions report OK (the existing Qt suite teardown still exits 1). Three source/frozen transport checks pass with exit code 0. Next.js production build and TypeScript checks pass.
Final packaged desktop startup check passed: preload ready, zero failed local assets, engine connected, exit code 0. Installer generated successfully.
