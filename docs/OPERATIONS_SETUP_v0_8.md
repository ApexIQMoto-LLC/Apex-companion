# APEX 0.8 — Windows Operations setup

## A. Install safely over v0.7.1

1. Close APEX fully (including its terminal). Download and extract the new ZIP to a temporary folder.
2. Run `Update_Existing_Install.cmd` **from the extracted folder**, not inside Windows' ZIP viewer.
3. Confirm the existing APEX installation folder, normally `C:\ApexIQCompanion`.
4. The updater installs dependencies **before copying application code**, then backs up previous `main.py` and `companion/` in `data\upgrade_backups`. It excludes the existing `.env`, `config.json`, `data`, `.venv`, local SQL databases and Windows Credential Manager secrets.
5. Start using your existing `start_windows.bat`; if the app closes, use `Launch_Companion.cmd` or `Run_Diagnostics.cmd` to retain the error trace.

## B. Set up autonomous Unity work

1. From **INTELLIGENCE**, select **CHOOSE UNITY FOLDER** and approve `C:\Users\YOUR_NAME\ApexIQUnity` (or the actual project you use). The folder must contain `Assets` and `ProjectSettings/ProjectVersion.txt` for Unity test execution.
2. Click **OPERATIONS** in the navigation. Leave **Auto-queue away checks** enabled to have APEX inspect logs and Git state while away.
3. Click **CHOOSE UNITY.EXE** and select the installed `Unity.exe`, typically under `C:\Program Files\Unity\Hub\Editor\<version>\Editor\Unity.exe`. This is saved as a path in `config.json`, not as a secret.
4. To allow bounded headless tests, enable **Allow Unity EditMode tests**. Do this only after confirming Unity Test Framework tests are configured and the Unity Editor project is closed during headless runs.
5. Use **SCAN UNITY LOGS**, **INSPECT GIT**, or **RUN EDIT MODE TESTS** to create explicit tasks. APEX records outcomes in a persistent operations journal. You can manually pause/resume the queue. Pending work remains across restarts; interrupted running work is blocked for review.
6. For auto fixes, v0.7's `AUTO SMALL FIX` must also be enabled, and a matching compiler warning CS0105 must be present in approved Unity logs. That small edit is backed up; test builds are not proof of gameplay.

## C. See desktop applications and ask APEX about a screenshot

1. Go to **DATA PERMISSIONS**, enable **COMPUTER / LOCAL** for selected-window UI inspection.
2. In **OPERATIONS**, click **CHOOSE WINDOW / INSPECT UIA** to inspect an open window. This reads accessible controls but does not click anything.
3. Click **LOCAL WINDOW SCREENSHOT** and select a window. APEX asks before saving its image in `data\screen_captures`.
4. For optional *paid* AI visual analysis, also enable **COMPUTER / AI**. After capturing a screenshot, separately approve sending that one image to your OpenAI model. This may reveal account names or other content visible on the screen. No screenshot is automatically uploaded.

## D. Connect phone commands (separate opt-in)

1. Pair your bot using the existing `Pair_Phone.cmd` and ensure you can receive the **SEND TEST** phone briefing. The Telegram bot must be chatting **privately with you**; group messages are ignored.
2. In **PHONE BRIEFING** turn on phone delivery; in **DATA PERMISSIONS**, enable **OPERATIONS / PHONE**.
3. Under **OPERATIONS**, enable **private Telegram commands**.
4. Message the bot one of: `/status`, `/queue`, `/scan`, `/git`, `/pause`, `/resume`, `/help`.
5. It polls Telegram while APEX is running, and replies with short, sanitized statuses. It accepts **no** code changes, Unity test commands, shell commands, payments or production actions. On a lost/stolen phone, disable commands from APEX and revoke the Telegram bot token in BotFather.
6. Do not attach a separate webhook or another polling client to the same bot; `getUpdates` works only if no webhook is active.

## E. Context questions to test

- `Apex, what did you investigate in the last 24 hours? Separate completed scans, test-verified changes, and unverified notes.`
- `Apex, check Git status.` (queues a read-only local job)
- `Apex, run Unity tests.` (queues only if Editor path and test permission are configured)
- `Apex, what do I need to verify before the next Replay Studio release?`

**Do not assume "completed" means "fixed".** Check the specific result, NUnit counts and real Unity Console. User-initiated paid API requests still count toward your OpenAI usage.
