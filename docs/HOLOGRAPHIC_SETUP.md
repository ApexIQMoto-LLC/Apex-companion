# APEX Holographic Core — Setup

1. Close APEX completely and extract the ZIP. Run `Update_Existing_Install.cmd` for an existing installation. It copies program files while preserving `.env`, `config.json` apart from the explicit one-time sensor-autostart migration, `data`, `.venv`, and Windows Credential Manager records. An old source-code backup is made.
2. Start `start_windows.bat`. The **APEX / HOLOGRAM** tab is home; **INTELLIGENCE** contains cloud, Steam, marketing, personal graph, approved Unity project, and phone pairing.
3. APEX attempts microphone and camera auto-start. If Vosk model is absent, Voice reports unavailable. Install the documented `vosk-model-small-en-us-0.15` under `models/`; ensure Windows camera and microphone permissions permit Python. Buttons **CAMERA** and **VOICE** toggle each startup preference and retain an opt-out.
4. Under INTELLIGENCE, select the permitted Unity project folder. For one-off bug repairs, use the existing reviewed proposal workflow. **AUTO SMALL FIX** uses only the deterministic CS0105 removal. It is triggered only while the computer is away.
5. **WORK / AWAY MODE** is a manual override when leaving. Otherwise the app treats eight minutes of Windows inactivity and camera absence as possible away. It does not know your actual work location or schedule.
6. Run `Pair_Phone.cmd`, then enable Telegram **PHONE BRIEFING** and `operations / PHONE` in **DATA PERMISSIONS** to receive away/return notifications; enable `projects / PHONE` for auto-fix notifications. Outbound-only messages omit source, raw logs, passwords and coordinates. Phone service is optional and offline when app/PC off.
7. To inspect what APEX did, check the **ACTIVITY / AUDIT TRAIL** on the hologram page and the **INTELLIGENCE** page. Static verification is not proof of a passing Unity build. Use Undo Last Auto-Fix if appropriate.

Limits: no unattended paid AI calls, command execution, purchases, broad code changes, migrations, deployment, or financial/account actions. App runs only with PC awake. Some Windows hardware behaviors remain to be verified in the installed environment.
