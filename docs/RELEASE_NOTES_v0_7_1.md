# APEX 0.7.1 — Holographic Command Center + Away Mode

**Basis:** All v0.7.0 personal intelligence modules, Steam/Supabase user-scoped reporting, local memory, opt-in Telegram, and approved project diagnostics remain in place.

## New UI

- `companion/holographic_ui.py`: generative radial waveform avatar (speaking/listening/thinking/away), responsive Tk Canvas, static frequency bars and motion effects. Not generated artwork. Uses local RMS input, no voice recording. Speaking waves indicate TTS engine busy, not exact audio amplitude.
- Large conversation dominates the default APEX home screen. Full dashboard moved to the Intelligence tab, with the same existing data features.
- Camera and voice auto-start true by default and enabled once for upgrades via `tools/enable_hologram_defaults.py`. The owner can turn either off afterwards and that preference persists.

## Away automation

- `companion/away_mode.py`: Windows idle-time estimate plus local presence; optional manual override. Does **not** detect real-world physical location, work shift or person identity.
- When away, previously authorized project warnings can trigger deterministic CS0105 duplicate using cleanup within one first-party Assets C# file at a time, max 2/day. Existing backup + conflict-checked rollback still apply. No code edit while present, no unpaid/paid autonomous LLM coding. Source changes still need Unity compilation.
- No-cost work queue based on owner goals and local alerts; logs evidence-based suggestion, doesn't pretend to complete tasks.
- Optional Telegram away/return notices and existing repair/daily digest. Telegram pairing and PHONE permission are still required.

## Security / limitations

Always-on mic and camera are easily disabled from the main screen. OS permissions, device availability and Vosk local model are prerequisites. No raw frames/audio are logged or uploaded by sensing services. Local memory databases remain plaintext; encrypted selected private imports unchanged. No purchases, deployments, shell execution, major code changes, or autonomous paid AI calls. App and Windows must remain running for local work and phone messages. Steam cron is separate.

## Verification

Run `python -m unittest discover -s tests -q` to run regression and hologram/away/migration tests. Visual mock desktop launch tested using Xvfb; real Windows camera, microphone, installer, and Unity compile must be checked on the user's PC.
