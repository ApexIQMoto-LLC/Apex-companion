# Release 0.10.3 — Voice-to-AI handoff and diagnostics

- Added explicit TALK TO APEX conversation activation for speech without a wake phrase.
- Added visible recognition and AI request lifecycle status to the compact hologram.
- Added CHECK AI local credential and usage-budget preflight without billable calls.
- Added audio notification for unsuccessful spoken AI requests.
- Updated microphone recognition handoff to a testable `route_recognized` method.
- Preserved the normal wake-phrase requirement for passive/background microphone input.
- Reflowed the compact hologram so new controls and TEST VOICE are visible.
- Preserved the Windows speaker fixes from v0.10.2.
- Full suite: 178 tests passed in the validation environment (hardware verification outstanding).

Refer to docs/VOICE_TO_AI_FIX_v0_10_3.md for the Windows test sequence.
