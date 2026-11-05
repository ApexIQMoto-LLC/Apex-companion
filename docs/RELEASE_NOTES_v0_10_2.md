# APEX Companion v0.10.2 - Voice output hotfix

- Switch default speech output to the local Windows System.Speech synthesizer on Windows.
- Keep pyttsx3 as an alternate/fallback engine.
- Add one-click Test Voice in the mini hologram and Windows tray.
- Add voice output setup (backend and volume) with Save + Test.
- Surface speech status/errors in the compact window instead of only the hidden dashboard.
- Make Windows speech cancellable and encode speech text as data (no script injection).
- Include a standalone Windows speech diagnostic, plus v0.10.1 microphone selection and sample-rate fixes.
- All existing business/personal/marketing/voice/tray features remain; no online TTS or paid voice API is added.

Actual Windows playback is not verified in the build environment. Validate with TEST VOICE after updating.
