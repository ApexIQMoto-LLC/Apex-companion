# APEX v0.7.0 — Release notes

**Upgrade basis:** v0.6.3.1 (AI tool use and memory, responses-length hotfix, Supabase user auth, Steam daily reports, Unity diagnostics). This is an in-place source upgrade. There is no destructive migration and no Supabase schema change.

## New functional modules

1. **Unified knowledge graph — `companion/personal_intelligence.py`:** source/date/confidence-tagged SQLite entities and explicit typed edges. Only allowed scopes are visible to the new model-read tools. Project context is pre-seeded, not speculative personal history.
2. **Continuous activity timeline:** events for APEX operations, cloud/Steam updates, Unity observations, saved tasks and actions; optional Windows foreground executable basename sampled roughly each minute, with no titles, full paths, screen, audio, keys or clipboard.
3. **Smart memory consolidation — `companion/intelligence_engine.py`:** imports only explicit project-scoped memories (not sensitive unknown conversations), periodically and idempotently. Records source provenance; includes conservative topic clustering.
4. **Behavior/trend analysis:** descriptive frequency and coverage of *observed* events only. No claims of reliable traits, productivity, stress or private behavior without evidence.
5. **Proactive planner:** owner-authored tasks + alerts ranked locally; no autonomous calendar changes and no paid inference needed.
6. **Permission-controlled integrations:** separate local/AI/phone permissions for eight categories; manual encrypted CSV/JSON/ICS/TXT import with Windows Credential Manager key; option to erase per-scope records.
7. **Bounded autonomy — `companion/autonomy.py`:** deterministic CS0105 duplicate top-level `using` deletion, strictly approved Unity Assets C# code only; max 2/day, backups, file-hash checks, static result check, owner rollback with conflict protection. No shell, network action, build, deploy or API spending.
8. **Phone brief — `companion/phone_brief.py`:** owner-paired private Telegram bot, short one-way daily digest and optional small-fix alerts. All phone delivery is disabled initially. Telegram pairing stores secrets through Windows Credential Manager, not in `config.json`.
9. **New model-selected read tools:** scoped personal graph, knowledge search, activity trends, planner, consent registry, and encrypted selected-file search (only when category AI permission is active).
10. **Upgrade safety:** dependency preflight before source replacement, old-code backup, preservation of prior user data and credentials, diagnostic utility.

## Safe defaults

- Sensitive categories `personal`, `computer`, `calendar`, `communications`, `finance`, `health`: LOCAL/AI/PHONE all OFF.
- Existing authorized `operations`, `projects`: LOCAL/AI ON, PHONE OFF.
- Phone briefing OFF; sample foreground app names OFF; no unattended paid AI calls; no autonomous purchases, deployments or shell execution.
- Small automatic C# fixes permitted only after existing Unity folder approval, only for CS0105, max two per day; can be disabled.
- Unity Editor.log access still requires separate permission; the original review-before-apply AI patch tool still requires approval.

## Verification

Run `.venv\Scripts\python.exe -m unittest discover -s tests -q` and compare against `docs/TEST_RESULTS_v0_7_0.txt`. The suite contains regression tests for old components, new scope controls, encryption, autonomous file edits, rollback conflicts, and basic UI startup. No new production Supabase changes or remote account actions were performed as part of this package.

## Known limitations

Unattended fixes are **not general-purpose AI bug fixing**. They are a single deterministic compiler-hygiene transformation that must subsequently be compiled in Unity. Telegram is one-way; no bot-based remote control, voice calls, or mobile app. Financial, medical, email and calendar accounts are not live connectors—only deliberately selected encrypted local exports are available. Existing chat/graph data is plain local SQLite; only sensitive import payloads are encrypted by this release. Local automations require Windows and APEX running.
