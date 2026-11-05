# APEX Companion — Public Source (v0.11.0 foundation)

**Community distribution.** This is the original APEX Windows tray, hologram, voice, and companion source with sensitive per-owner integrations removed or disabled by default. Each installation must supply its own credentials and backend. No access to the developer's ApexIQ Moto cloud, Steam account, or personal project data is included.

**Status:** Source release; Windows microphone/audio, remote connectivity, and cloud provider configurations need end-user testing. Existing features do not mean every advertised integration works without your own provider setup.

## Quick start
1. Install Python 3.12 on Windows.
2. Extract this source archive and run `Install_Companion.cmd`, then `Launch_APEX_Diagnostics.cmd`.
3. Copy `config.example.json` to `config.json`, edit only the services you own; copy `.env.example` to `.env` and fill in your own keys locally.
4. Grant microphone, camera, cloud and automation permissions only if you need them.
5. Never commit `.env`, `config.json`, `data/`, logs, credentials, tokens, models, or a Windows user profile directory.

Read `docs/PUBLIC_ARCHITECTURE.md` and `docs/PUBLIC_SECURITY.md` before enabling remote functions.

---

**NEW v0.11.0:** Automatic multi-provider AI routing (OpenAI, Claude, DeepSeek, OpenRouter, Groq, Hugging Face, Mistral, Together, Fireworks, Cerebras, DeepInfra, and optional local Ollama/LM Studio/UnfilteredAI-1B). Task selection is automatic. New cloud providers are opt-in and require explicit price configuration. See [`docs/MODEL_ROUTING_v0_11.md`](docs/MODEL_ROUTING_v0_11.md).

**NEW v0.10.4:** See [`docs/VOICE_CONVERSATION_v0_10_4.md`](docs/VOICE_CONVERSATION_v0_10_4.md). After the normal update, run the optional `Install_Natural_Voice.cmd` in your installed APEX folder and choose Kokoro in voice output settings. For higher-quality speech recognition run `Install_Enhanced_Recognition.cmd` (larger optional offline model).

# APEX v0.11.0 - Business + Personal Voice Companion

APEX is a **Windows system-tray-first voice assistant**. **v0.10.4 adds pause-aware voice turns, WebRTC noise rejection, optional Kokoro natural voice, optional Whisper recognition, and lower-cost conversational requests:** the compact hologram now has **TALK TO APEX** to open a conversation without relying on a wake phrase, **CHECK AI** for free local configuration checks, and visible status when speech is heard but ignored, queued, or failed. The Windows text-to-speech fixes from v0.10.2 remain included. See `docs/VOICE_TO_AI_FIX_v0_10_3.md`.

The compact hologram is the primary conversation surface; the full business, personal, intelligence and operations dashboards remain available on demand.

## Upgrade and launch

1. Quit the existing APEX process before upgrading.
2. Extract this ZIP outside the installed APEX folder and run **`Update_Existing_Install.cmd`**.
3. Run **`Download_Offline_Voice_Model.cmd`** once if you have not installed the free offline Vosk model yet.
4. Use **`Launch_Companion.cmd`** for quiet, tray-first launch. The APEX tray icon opens the compact hologram; right-click it for the full dashboard or Quit.
5. For diagnostics use **`Launch_APEX_Diagnostics.cmd`** / `start_windows.bat`.

See **[`docs/TRAY_VOICE_SETUP_v0_10.md`](docs/TRAY_VOICE_SETUP_v0_10.md)** for Windows tray, microphone, wake phrase, safety and troubleshooting instructions.

## Talk to APEX

Say **"Apex"**, **"Open Apex"**, **"Start Apex"**, or **"Hey Apex"**, **or click TALK TO APEX** to open a deliberate conversation without the wake phrase. Click **CHECK AI** if speech is recognized but the model does not respond. Once awake, you can speak naturally for two minutes after each response without repeating the name. Say **"Let's talk business"** or use the Business button to begin with questions about beta riders, social content, Replay Studio marketing, or revenue. Use Personal for goals and daily planning. Say **"Stop listening"** to close the session; the offline wake listener remains enabled unless you toggle Voice off.

APEX pauses listening while its local TTS speaks or an AI response is processing; **this is turn-taking speech, not full-duplex voice**. It only makes paid model calls when the user makes an AI request and enforces the existing daily/monthly usage ceilings. Webcam sensing remains separately configurable.

## Existing features retained

| Domain | Capabilities in this codebase |
|---|---|
| AI conversation | User-initiated model Q&A, recent-turn history, relevant local memory, permission-scoped read tools, explicit cost accounting |
| Business Studio | Local content ideas, scripts, captions, creator outreach, campaigns, UTM links, CSV metrics, leads/qualification, calculated conversion/ROI |
| Social account OAuth | Setup for Instagram, TikTok, YouTube, GA4, Google Ads, Meta Ads, TikTok Ads; consent/configuration only |
| Marketing research | Public industry research and opportunity radar |
| Personal | Local memory, structured knowledge graph, timelines, permission controls, restricted private imports |
| Unity | Approved-folder indexing/log scans, diagnostics, read-only Git status, optional Edit Mode tests, safe verified patch review |
| Operations | Durable task queue, paused/away mode, limited deterministic C# cleanup with rollback, event audit |
| Cloud and Steam | Owner-authenticated A.R.I.S Cloud statistics and Steam metrics with freshness caveats |
| Telegram | Paired status reports and authorized small command allowlist |
| Desktop | Optional window inspection, per-image approved screenshot AI analysis, camera presence sensing |

**Not yet supported:** automatic live social analytics imports; posting or buying ads; autonomous creator outreach; unrestricted code edits or PC control; real-time overlapping spoken conversation. The 0.10 update has not connected accounts.

Existing `.env`, `config.json`, `data/`, `.venv`, OAuth secrets and user credentials are excluded from the safe update. Installer backs up existing code.

## Tests

Use the existing Python 3.12 Windows virtual environment:

```cmd
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests cover original operations, cloud/auth abstractions, memory, business studio, wake/conversation state and UI code. Windows tray behavior, microphone/TTS hardware and social OAuth must be validated on your PC.
