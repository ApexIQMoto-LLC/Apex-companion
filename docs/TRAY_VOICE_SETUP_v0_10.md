# APEX 0.10 - Windows Tray + Natural Voice Conversation

APEX is now a **tray-first, voice-first desktop companion**. Its earlier business, personal, cloud, development and operations features remain in the full dashboard.

## Installation / upgrade

1. **Quit APEX fully**, from the tray menu if an older version is running. Closing a v0.10 window only hides it, so choose **Quit APEX** before upgrading.
2. Unzip the new package to a temporary folder outside the existing APEX installation.
3. Run `Update_Existing_Install.cmd`, select the existing installation, and allow it to install the new **pystray** dependency. The update is designed to preserve `.env`, `config.json`, `data/`, `.venv`, Windows Credential Manager, and existing account sessions. Existing code is backed up before replacement.
4. If the offline speech model is missing, run `Download_Offline_Voice_Model.cmd` **once**. This explicitly downloads the official Vosk small English model (~40 MB, Apache 2.0) into `models/vosk-model-small-en-us-0.15`. Or obtain it manually from <https://alphacephei.com/vosk/models>.
5. Launch **`Launch_Companion.cmd`**. This uses `pythonw.exe` with no persistent command window. `start_windows.bat` / `Launch_APEX_Diagnostics.cmd` remain available for troubleshooting.

## Notification area behavior

- APEX starts without its full dashboard open. On Windows it creates a small **APEX** notification-area icon via pystray. Windows, not APEX, determines whether it appears directly on the taskbar or under the `^` hidden-icons overflow.
- Click/double-click the tray icon to open the **small hologram**; right-click for the menu to access the full dashboard, start a business conversation, toggle voice, or **Quit APEX**.
- Close/hide the hologram or full dashboard to keep the assistant running in the tray.
- If the tray backend fails or pystray is unavailable, APEX displays the small window instead of becoming unreachable.
- Windows startup can use the existing `enable_autostart.bat` to configure the user's Startup shortcut. APEX does **not** run while the computer is powered off or asleep.

## Voice usage

With the microphone active and the free offline model installed:

1. Say **"Apex"**, **"Hey Apex"**, **"Open Apex"**, **"Start Apex"**, or **"Apex, open Apex"** to open the compact hologram and invite a conversation.
2. Say, for example, **"Let's talk business"**. APEX offers specific choices such as beta acquisition, content planning, Replay Studio, or revenue. Use the **BUSINESS** or **PERSONAL** button for the same local, no-cost opening question.
3. Reply normally; you do **not** need to repeat the wake phrase after each answer. The active session expires after **120 seconds without user speech** (configurable with `conversation_idle_seconds`, 15-600 seconds).
4. Say **"Stop listening"**, **"Go to sleep"**, or **"Close Apex"** to end the session. The wake detector continues listening locally unless you turn the microphone **OFF**.
5. **VOICE** toggles microphone use; **STOP** stops speaking; **DASHBOARD** opens all earlier features.

Voice recognizes phrases **on-device** using Vosk. The recognized text of an *explicit user request* may be sent to the configured OpenAI API for an answer. APEX does not save raw microphone audio or perform unattended paid voice queries. Standard local monthly/daily model budgets still apply; each new back-and-forth AI answer can consume API usage. APEX's spoken replies are intentionally short, and normally ask one relevant follow-up question when useful.

**This is turn-taking speech, not full-duplex real-time audio.** Listening pauses while APEX speaks or processes an answer to avoid microphone echo and overlapping requests. It cannot interrupt the model mid-generation by talking over APEX. The offline small English Vosk model will also make transcription errors, especially in noisy spaces or with proper names.

If the microphone remains **VOICE - SETUP**, install the model or check Windows microphone permissions. If Windows has no compatible TTS device, typed chat still works. For full app diagnostics, run `Launch_APEX_Diagnostics.cmd`.

## What is unchanged

- Business Studio: local campaign/content/creator management, sample dashboards, CSV imports and conversion history; account OAuth setup, **but no automatic live social analytics ingestion yet**.
- Personal Intelligence: local memory, permissions, knowledge graph, import/export and user goals.
- A.R.I.S. Cloud / Steam: owner-account read access and permitted live status/reporting.
- Unity/Operations: read-only diagnostics, project-scoped Git status, optional tests, reversible small fixes, audited tasks.
- Telegram: limited private remote controls, when paired/authorized.

No automatic social posting, spending, major autonomous edits, production deployment or arbitrary desktop control has been added.

## Configuration

Keep preferences in your existing `config.json`. Optional new keys:

```json
{
  "launch_minimized_to_tray": true,
  "conversation_idle_seconds": 120,
  "microphone_autostart": true
}
```

`launch_minimized_to_tray=false` opens the small hologram on startup while still providing the tray menu. Set `microphone_autostart=false` to disable persistent local wake listening. These settings do not automatically turn the camera on or off; camera settings are separately controlled.

## Limitations / verification

Unit tests and a Linux virtual-display GUI smoke test validate the state machine and core window behavior. Actual Windows notification-area placement, mouse default action, microphone hardware, Vosk accuracy, Windows TTS, camera startup, and your live account configuration must be tested on your PC. The update has not signed in to any account or configured social developer credentials on your behalf.
