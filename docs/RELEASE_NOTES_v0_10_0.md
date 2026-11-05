# APEX Companion v0.10.0 - Tray and Conversation Release

## Added

- Windows tray-first background service using `pystray` with a default menu action and full dashboard recovery.
- Compact 458 x 650 animated holographic conversation window with Business, Personal, Voice, Stop and Dashboard controls.
- Offline wake phrases: Apex, Hey Apex, Open Apex, Start Apex, Apex Open Apex and earlier configurable names.
- Bounded voice session that accepts subsequent speech without repeating the wake phrase, with 120-second configurable inactivity timeout and spoken sleep commands.
- User-initiated business and personal conversation starters and model-side concise spoken replies with relevant follow-up questions.
- Silent `pythonw.exe` launcher and optional Vosk offline model downloader.
- Safer microphone behavior during queued/pending TTS and concurrent AI processing; no raw audio persistence.

## Unchanged or not implemented

Existing business, operations, personal memory, Steam, cloud, account OAuth and Telegram features are preserved. No social analytics synchronization, automatic posting, purchases, high-risk self-modifying code, or full-duplex real-time voice was added. Vosk recognition, Windows tray and TTS still need real hardware testing.

## Verification

Unit-test suite: see `docs/TEST_RESULTS_v0_10_0.txt`.
Virtual X desktop Tk smoke test: hidden root, compact UI, Business starter, full dashboard recovery, hide-to-mini fallback, and rendered hologram.
