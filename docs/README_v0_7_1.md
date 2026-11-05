# APEX Companion v0.7.1 — Holographic Intelligence Core

APEX is a locally running Windows desktop assistant for ApexIQ Moto and Replay Studio. The v0.7.1 interface replaces the small right-column chatbot with a full-width holographic voice console, animated radial sound-form avatar, large conversation, dedicated Intelligence tab, always-on-by-default local voice/camera sensing, idle-and-presence-based away detection, scoped unattended warning cleanup, and optional private phone status reports. The v0.7 platform includes a source-attributed knowledge graph, activity timeline, local memory consolidation, cautious trend analysis, goal-based daily planning, explicit data permissions, a narrowly permitted autonomous C# cleanup rule, and optional one-way Telegram phone briefings. It retains the original v0.6.3.1 OpenAI conversation engine, Supabase user-scoped readers, Steam reporting, Unity analysis, voice/camera options, and human-reviewed code patching.

**Safety rule: No unattended paid OpenAI calls, purchases, deployments, arbitrary shell/PowerShell execution, account changes, major code refactors, or broad deletions.** Unattended source edits are limited to **compiler-identified CS0105 duplicate C# `using` directives**, in first-party `Assets/*.cs` files under a previously approved Unity project, with a local backup and a limit of **two automatic fixes per day**. These are statically verified only; Unity compilation is not run. More complex errors are reported to you for review.

> **Operational requirements:** Your PC must be on and Companion running for local monitoring, repairs, and Telegram messages. The independent Supabase Steamworks cron continues server-side even when the PC is off. No financial, health, email, calendar, or browser account is automatically connected.

## Recommended update from v0.6.3.1

1. **Completely close APEX**, including its command window.
2. Extract the entire `ApexIQ_Companion_v0_7_1.zip` to a temporary folder. Do not double-click the installer inside the ZIP viewer.
3. Run `Update_Existing_Install.cmd` in the extracted folder.
4. Confirm the path of your existing APEX installation (usually `C:\ApexIQCompanion`) and approve the upgrade.
5. The updater **installs new Python dependencies before copying code**, backs up the old `main.py` and `companion` modules to `data\upgrade_backups`, then copies only program files. If the copy or import verification fails, it attempts to restore the backup.
6. Start your existing `start_windows.bat`. If it fails to start, run `Launch_Companion.cmd` and inspect the displayed error. Run `Run_Diagnostics.cmd` to check installed modules without printing credentials.

The updater excludes **`.env`, `config.json`, the full `data` folder, `.venv`, logs, and local SQLite files**. It does not touch Windows Credential Manager; the saved Supabase login and local secret material stay in place. The full previous user data and settings are reused, not migrated destructively.

**Fresh install:** Install Python 3.12 x64, extract to `C:\ApexIQCompanion`, run `Install_Companion.cmd`, then `start_windows.bat`. Configure the OpenAI key locally in `.env` and log into Supabase as your ordinary ApexIQ user. A privileged `service_role` key must never be placed on the desktop.

## New in the holographic update

- **Main screen:** large responsive radial audio waveform avatar and a wide chat transcript; speaking animation is driven by local TTS status, microphone response by local RMS, and thinking/away have distinct states. The original cloud, marketing, Unity, and personal-intelligence dashboard lives under **INTELLIGENCE**.
- **Camera & microphone:** user-requested always-on **startup defaults**, migrated once for existing installations. You can turn either OFF in the left sidebar; later upgrades preserve that opt-out. Video stays on-device, with face **presence only**, not identity recognition. Voice requires the optional Vosk local speech model and OS audio permissions; if unavailable, the UI reports that it cannot start.
- **Away mode:** Windows keyboard/mouse idle time (default eight minutes) plus local face-presence state and a short grace interval. Explicit **WORK / AWAY MODE** manually declares away; it cannot determine whether you are literally at work. An awake, running PC is required.
- **Background tasks:** monitor approved Unity logs, owner-visible cloud data, Steam and news; generate local priority suggestions from saved goals and alerts without paid API calls. While AWAY only, use the **existing strict CS0105** cleanup rule (maximum two/day), with backup, undo, and audit. Everything else is a recommendation for manual review.
- **Phone:** after you pair a private Telegram bot, enable phone delivery, and allow `operations / PHONE`, the program can send sanitized away/return notices plus its daily digest. `projects / PHONE` enables optional code-cleanup alerts. No secrets or source code are sent. Phone delivery is not active until paired and approved.
- **Hard limits:** no purchases, no paid unattended AI, no arbitrary command or file execution, no production changes, no major code edits, no deployment, and no remote PC control.

## What's included

| System | Actual behavior in v0.7 |
|---|---|
| Unified graph | Evidence-tagged projects, observations, decisions, goals, related resources, and links. Search is scope-aware; project seeds are created idempotently. |
| Activity timeline | Companions' app events, owner-visible Steam/cloud report changes, Unity diagnostics, goals, and auto-fix audit records. Opt-in foreground **executable names only** (no screen, keystrokes, browser URLs, window titles) sampled once per minute. |
| Memory consolidation | Once per day, imports **explicit project-related memories** from existing local memory. It does not infer personality or silently import health/finance data. |
| Trends and daily planner | Counts observed events with sample coverage; flags insufficient evidence. Prioritizes owner-entered tasks and current local alerts; no automatic calendar writes. |
| Permissions | Per-category `LOCAL`, `AI`, and `PHONE` controls. Sensitive categories are off by default. AI/PHONE permissions require LOCAL. Revocation blocks later reads; use ERASE to delete locally stored entries. |
| Private imports | Manual selection of bounded CSV, JSON, ICS or TXT exports. Credential/identifier fields removed where recognized, content encrypted at rest with a Fernet key stored in Windows Credential Manager. If OS key storage fails, imports are blocked. AI access is a **separate opt-in**. |
| Limited autonomy | At most two/day **CS0105 duplicate-using** removals in approved first-party Unity C# scripts, followed by local backup and static verification. No AI costs or command execution. `UNDO LAST AUTO-FIX` uses backup/hash conflict protection. |
| Phone reporting | Optional private Telegram bot + private chat pairing via `Pair_Phone.cmd` (token/chat ID stored in Windows Credential Manager). One-way daily operational digest after configured local hour; short notifications for safe automatic fixes if project PHONE permission permits. Default OFF. |
| Existing AI | OpenAI text questions with owner-scoped Supabase, Steam, local memory, project-index, Unity, and new personal-intelligence read-only tools. User-initiated API calls still incur API charges; local estimated limits are not guaranteed billing caps. |

### First time in the v0.7.1 holographic interface

- Switch to **INTELLIGENCE**, then open **INTELLIGENCE / PLAN** to view the source-tagged knowledge graph, timeline, priority queue and actual observed trend coverage. Use **ADD GOAL**, **ADD FACT**, **CONSOLIDATE MEMORIES**, and **IMPORT FILE** as needed.
- Open **DATA PERMISSIONS** to inspect all categories. `operations` and `projects` default to local+AI; the `personal`, `computer`, `calendar`, `communications`, `finance`, and `health` categories default OFF. Grant permission only for sources you specifically want to use. Turning on `FOREGROUND APP NAMES` also requires `computer / LOCAL` permission.
- Switch to **INTELLIGENCE** and approve a Unity project with **CHOOSE UNITY FOLDER**. **AUTO SMALL FIX** is initially enabled but remains inactive without an approved project and a matching compiler error. It only fixes CS0105; code review is still required for other source modifications. You can disable auto-fixes from the dashboard.
- To receive phone updates: create a private Telegram bot with **@BotFather**, open a chat with it and send `/start`, run **`Pair_Phone.cmd`** on your Windows PC, restart APEX, open **PHONE BRIEFING**, enable it, and click **SEND TEST**. To receive cloud metrics in the digest, turn on `operations / PHONE`; to receive auto-fix notifications, turn on `projects / PHONE`. Nothing is sent without these opt-ins.
- For local sensitive files, enable the category's LOCAL permission, choose **IMPORT FILE**, preview the record count and fields, confirm the import, then separately grant AI permission if you want that category searchable in model responses. The original CSV/JSON/ICS/TXT remains outside Companion and is not monitored.

## Suggested tests

1. Ask: **"Apex, what are my three highest-priority tasks and where did your evidence come from?"**
2. Save a goal in **INTELLIGENCE / PLAN**, restart Companion and see that it persists.
3. Ask: **"What source-attributed facts do you have about Replay Studio?"**
4. Enable `computer / LOCAL` + optional foreground-app sampling, then use apps for several minutes and inspect the timeline. Disable afterwards to confirm sampling stops.
5. With Telegram configured, enable PHONE BRIEFING and send a test. The code does **not** accept Telegram messages as remote commands.
6. With an approved **test Unity project**, reproduce warning CS0105 on a duplicate top-level `using` directive. Verify one line is removed, a backup exists, the action is audited, and that **UNDO LAST AUTO-FIX** restores it when you explicitly approve. Do not treat a static check as a Unity build/test pass.

## Privacy, limitations and costs

- Existing `data/apex_memory.sqlite3` chat history and ordinary graph/timeline SQLite databases are **not encrypted at rest**. New **selected sensitive imports** use Fernet encryption; don't equate this with full-disk encryption. Windows account security and BitLocker are recommended.
- Data permissions are explicit. Granting permission lets an AI *read* bounded authorized material on user-initiated questions; it never grants OS-wide access. The new graph contains facts the owner entered or previously authorized, with source/date fields. Trend analysis is descriptive, not a definitive behavioral profile.
- Phone messages pass through **Telegram's servers**. They are intentionally short, exclude raw rider GPS/code/private documents and attempt to redact credentials. Do not enable phone delivery for categories you don't want forwarded.
- APEX cannot autonomously perform broad Unity repair, reliably test code changes, launch/release the game, purchase items, post marketing, email riders, manage bank accounts, or work while the Windows PC is sleeping/off.
- **No unattended paid AI** is the default and intentionally overrides earlier opt-in daily AI briefing settings unless you deliberately edit `autonomy_no_paid_calls`. User-initiated API chat still costs money. `monthly_budget_usd`/`daily_request_limit` are application-side guardrails, not provider spend hard caps.
- Automatic CS0105 removals are limited, deterministic, audited, and reversible, are allowed only while APEX detects AWAY or the owner sets MANUAL AWAY, but you should compile the project in Unity and inspect the results afterwards.

## Reference and troubleshooting

- `docs/RELEASE_NOTES_v0_7_0.md` — implementation and test details.
- `docs/SECURITY_AND_LIMITS.md` — security architecture and limits.
- `docs/PHONE_SETUP_v0_7.md` — Telegram pairing and safe message contents.
- `docs/README_v0_6_3_1.md` — preserved previous release documentation and voice setup.
- `Run_Diagnostics.cmd` — installed dependencies, source scopes, configuration presence **without printing keys**.
- `Launch_Companion.cmd` — persistent traceback window.
- `install.log` — installer errors (do not share full files if they contain private local paths).

Unit tests can run locally via `.venv\Scripts\python.exe -m unittest discover -s tests -v`. Tests in this package are simulated; the Windows microphone, webcam, Telegram account, real OpenAI responses, and Unity compile/patch behavior must still be validated on your PC.
