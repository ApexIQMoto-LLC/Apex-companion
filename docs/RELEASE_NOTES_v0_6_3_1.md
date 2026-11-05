# APEX 0.6.3.1 - Reliable Briefings Hotfix

Observed on Nov 4, 2026: a six-section operating brief repeatedly failed with `AI response incomplete; try again with a shorter question`, while a shorter live-data market analysis worked.

## Changes
- Diagnostic root cause: v0.6.3 had `max_output_tokens: 1300` for every request, including six-part reports. The API status `incomplete` was immediately treated as a failure. A response can be incomplete for reasons other than length; those still fail safely.
- Adaptive request output budgets: 1,300 for routine short chat, at least 2,800 for more involved questions, 4,000-4,600 for complex/multipart briefings. Your saved `config.json` is preserved.
- **At most one paid retry** only when the provider specifically reports `incomplete_details.reason == max_output_tokens`. Maximum 7,000 output tokens. Failed/incomplete attempts with usage remain included in the local spending ledger and daily request count.
- Bounded tool execution: up to six rounds, with at most 12 read-tool executions; every tool-call ID receives an output, including a clear limit error when out of budget.
- Persistent memory can recognize a clearly requested `Remember this priority:` line inside a long numbered request. The app confirms saving locally and keeps processing the remaining tasks. Previous memory deletion and opt-out controls remain.
- Nothing touches your production Supabase schema, Edge Functions, Steam key, Windows API key, or Unity source files.

## Install and verify
1. Close APEX. Extract ZIP to a new folder.
2. Run `Update_Existing_Install.cmd`. It preserves `.env`, `config.json`, `data`, saved Windows Credential Manager Supabase account and `.venv`.
3. Ask for a full operating briefing again. If it still fails, capture the exact new error and whether DEEP REASONING is enabled.
4. Verify memory through MEMORY / CONTROL. For Unity logs, approve the actual Unity project folder first.

## Limitations
Tests use simulated OpenAI API responses and a headless UI. A real OpenAI API call on your Windows machine has not been verified by this build. Long complex requests can still fail due to model limits, network failures or permissions, but the app should no longer fail solely because it applies 1,300 tokens to every briefing.
