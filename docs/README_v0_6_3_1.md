> **v0.6.3.1 hotfix:** fixes long requests failing at 1,300 output tokens, adds one bounded length-only retry, and saves explicit `Remember this priority:` instructions inside numbered prompts. See `docs/RELEASE_NOTES_v0_6_3_1.md`. This update does not modify cloud infrastructure or expose credentials.

# APEX / ApexIQ Companion v0.6.3 — Intelligence Core

A **working Windows Python desktop prototype** that combines the original ApexIQ Moto command center with **persistent memory, read-only AI-selected tools, opt-in voice, scheduled research/alerts, and a review-before-write Unity coding assistant**.

**Upgrade rather than reinstall.** If v0.5.1 already works with GPT-6 Luna and A.R.I.S Cloud, use `Update_Existing_Install.cmd` from this ZIP. It preserves your local OpenAI `.env`, `config.json`, `data/` (including historical notes and usage), Windows Credential Manager Supabase refresh session, and `.venv`. You do **not** need to paste the Steamworks Financial key, create a new Supabase table, or repeat server setup.

> This is **not** a fully autonomous OS-controlling agent. It has a concrete, locally running tool/approval boundary. Windows voice and real API/Unity workflows must be verified on your PC. It does not work while your PC is off or asleep. Existing Supabase Steam synchronization runs separately on the server.

## 1. Upgrade from v0.5.1 (recommended)

1. **Close Companion** completely, including any leftover command window.
2. Extract **the entire v0.6.3 ZIP into a NEW temporary folder** (not inside the ZIP viewer).
3. Run **`Update_Existing_Install.cmd`** from the extracted folder.
4. The updater looks for `C:\ApexIQCompanion`; if your installation is elsewhere, paste the folder containing your existing `main.py`.
5. Confirm the update; wait for **"program files updated successfully"**. It does not overwrite `.env`, `config.json`, your `data` folder, or `.venv`.
6. Open your *existing* installation folder and run **`start_windows.bat`**. If the app crashes, run **`Launch_Companion.cmd`** to keep the traceback on screen.
7. Confirm **AI CLOUD CONTEXT / ON** and that Supabase restored your existing user session. If needed, sign in once with your **normal ApexIQ user account** (never a service-role key).

**Fresh installation:** Install Python **3.12 x64**, extract the ZIP to `C:\ApexIQCompanion`, run `Install_Companion.cmd`, then `start_windows.bat`; follow normal API key and cloud login steps. The installer writes `install.log` for diagnostics. Do not run programs directly inside the ZIP preview.

## 2. Features by release

### v0.6.0 — Memory and live data tools

- **SQLite long-term memory**: keeps up to 350 local user/assistant exchanges, explicit `remember that ...` facts, local keyword search and review/erase controls. `MEMORY / CONTROL` allows deleting individual facts, clearing conversations, or erasing all memory; memory can be disabled.
- **Actual OpenAI Responses API function-calling loop**: Luna can choose approved read-only tools to fetch RLS-visible cloud health, synchronized Steam wishlist reports, cached public research, indexed code excerpts, Unity errors and local historical memory.
- **Private-by-design**: only source-labeled, bounded summaries/excerpts reach OpenAI on user-initiated requests. No private Steam key, bank data, GPS routes, rider identities, OAuth tokens, or Supabase service keys are provided to the model.
- **Source discipline**: timestamps and provenance are passed to the model; it is instructed to distinguish current measurements, cached public research and historical notes.

### v0.6.1 — Voice and presence

- Existing **wake-phrase voice** (`hey apex`, `hey jarvis`) with offline Vosk transcription and local pyttsx3 speaking.
- New **PUSH TO TALK** button for a short, manually triggered local speech recording, with spoken AI reply; useful if you don't want a continuously open microphone.
- New **SILENCE** button requests cancellation of current speech and clears queued responses. Driver support for mid-sentence cancellation varies.
- Existing **camera presence greeting** remains optional; it detects a face locally but does **not** identify a person. Camera and microphone remain OFF by default.
- To enable either voice mode, manually install the free `vosk-model-small-en-us-0.15` directory under `models/` (details below). Voice is not neural realtime conversation and does not support true full-duplex audio.

### v0.6.2 — Proactive intelligence

- Automated, **free** public RSS business/marketing research, A.R.I.S Cloud and Steam checks on the same intervals as v0.5.1, while the app runs.
- Dedupe-persisted local alerts for stale device heartbeats, new owner-visible beta-application counts, new Steam report dates and unique Unity error text.
- **ALERTS** panel to review, acknowledge or erase local alerts. Quiet hours suppress unsolicited alert chat/speech, but not the saved alert record.
- Existing local morning briefing is free. A **separate AUTO AI BRIEF toggle** allows **one opt-in paid AI synthesis per local day**, budgeted and not triggered while the app is closed. Default: **OFF**.

### v0.6.3 — Unity / development partner

- **CHOOSE UNITY FOLDER** explicitly authorizes one local project. APEX automatically indexes only allowlisted text/source files in that folder, no symlink traversal, no `.env`, no `Library`, no `node_modules`, no private key files. Index is kept in local SQLite.
- Explicit consent to inspect Windows' `%LOCALAPPDATA%\Unity\Editor\Editor.log`, which is often where Unity compile/console errors appear. You can decline and use only the chosen project's `Logs` directory.
- **SCAN UNITY ERRORS** reports log excerpts read-only, plus source file/line for compile errors when present. Scheduled scans repeat while the program runs; findings are evidence, not claims the whole project compiles cleanly.
- **PROPOSE CODE FIX**: select one approved UTF-8 source file (up to 32 KB) and describe a change. A deep model suggests a **single, narrow find/replace**. Review its unified diff. Nothing is written until you click **APPROVE AND BACK UP** and confirm. The app rejects path traversal, symlinks, ambiguous replacements, large files and file-change conflicts; it backs up the original under `data/source_backups/` before atomic replacement.
- No shell/PowerShell execution, Unity build triggering, scene modifications, automatic database migrations, account actions, external messaging or deployment tools.
- **REVOKE PROJECT ACCESS** stops future project reads and removes indexed snippets for that folder. In-flight results from old permissions are discarded.

## 3. First prompts to try

- **Current business situation:** "Apex, check my latest Steam report and live device health, compare those with our beta plan, and give me three next actions. Cite each information source and date."
- **Memory:** "Remember that our next major priority is accurate mountain elevation in Replay Studio." Then restart Companion and ask "What was our mountain road priority?"
- **Unity:** Choose the project folder, then ask "Check my approved Unity logs. Which errors have the highest impact, and which source files should I inspect?"
- **Marketing:** "Compare recent public motorcycle trends with our current Steam wishlist activity. Separate research leads from confirmed opportunities."
- **Code edits:** Click **PROPOSE CODE FIX**, select one `.cs` file, describe the issue, review the full diff, approve only if correct, then compile manually in Unity.

## 4. Configure voice

1. Download `vosk-model-small-en-us-0.15` from https://alphacephei.com/vosk/models .
2. Extract it as `C:\ApexIQCompanion\models\vosk-model-small-en-us-0.15\` (or the corresponding chosen app path).
3. Select **VOICE • OFF** to activate the always-listening local wake phrase, or leave it off and click **PUSH TO TALK** for seven seconds.
4. Camera greeting is separately opt-in. Microphone/camera streams stay local. Only locally recognized **text** is sent to OpenAI when you ask it to answer.

## 5. Data sources, consent, and costs

| Integration | Scope | User action |
|---|---|---|
| A.R.I.S Cloud | Supabase Auth + publishable key + RLS; counts and selected status fields only | Existing signed-in ApexIQ user session |
| Steamworks | Private daily report read through owner-only Supabase table, Steam key remains on server | Supabase user login; server job was configured previously |
| OpenAI | Text API calls from your own paid API project | `.env` API key from existing install; initiated question or explicit daily opt-in |
| Memory | Local SQLite plaintext store for conversations and facts | Enabled by default; can disable/erase in memory panel |
| Unity/code | One user-approved folder, redacted indexed snippets and optional Editor.log | Explicit folder selection, optional Editor.log consent, plus per-file approval before edits |
| RSS research | Unverified public-feed headlines and ideas | Automatic while app is running |
| Banking, Gmail and desktop control | **Not connected** | Future separately authorized integrations only |

- The local cost tracker is an **estimate**, **not a guaranteed provider billing limit**. Defaults: $15/month local guard, up to 70 requests/day, no automatic paid AI requests without opting in. Tool-using questions can require multiple API calls; their token usage is recorded separately.
- `data/apex_memory.sqlite3` and `data/apex_alerts.sqlite3` are **not encrypted at rest**. The account file permissions on Windows still apply. Use the controls to erase contents and protect the PC account.
- Never paste API keys, passwords, service-role keys or Steam financial keys into chat, `.md` project notes or code files. Keep your `.env` local. The desktop uses only the public Supabase publishable key.
- Raw webcam frames, live mic samples, raw GPS routes, private rider telemetry, and financial records do not go to the OpenAI API.
- An automatically synced Steam daily wishlist report shows daily additions/removals, **not the current total wishlist balance**. Missing report dates do not mean zero activity.
- AI replies are probabilistic and generated patches must be reviewed and compiled in Unity. A source edit is not proof that the issue is fixed.

## 6. Tests, troubleshooting and files

Run unit tests from your install directory:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m compileall -q main.py companion
```

`docs/TEST_RESULTS.txt` includes test results from the development environment. These are not a substitute for real testing on Windows with your mic, camera, Supabase user account, OpenAI key and Unity installation.

- `main.py` — single-screen dashboard, event queue, background jobs, permission windows.
- `companion/assistant.py` — bounded OpenAI Responses tool loop and budget/usage recording.
- `companion/live_tools.py` — read-only cloud, Steam, research, memory, approved-code, Unity diagnostic tools.
- `companion/memory.py` — inspectable/deletable SQLite memory.
- `companion/alerts.py` — local deduplicated alerts and acknowledgement history.
- `companion/unity_diagnostics.py` — bounded tail of approved Unity logs.
- `companion/dev_assistant.py` — source path validation, AI diff proposal, explicit approval and backup.
- `companion/project_index.py` — safe, root-scoped local code index.
- `companion/voice.py` — Vosk + pyttsx3 + short push-to-talk capture.
- `companion/supabase_monitor.py` and `steamworks.py` — user-authenticated cloud readers.
- `docs/SECURITY_AND_LIMITS.md` — trust boundaries and supported autonomy.

The app is a desktop program you run. ChatGPT cannot remotely control or keep it running after this conversation.
