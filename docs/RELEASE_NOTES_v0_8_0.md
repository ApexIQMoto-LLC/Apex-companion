# APEX Companion v0.8.0 — Autonomous Operations Engine

This release extends v0.7.1. It is a **local Windows Python application**, not a general-purpose AI that can execute unreviewed code or arbitrary desktop commands. The OpenAI API is used only for **user-initiated** chat, patch proposals and **per-screenshot opt-in** image analysis. No unattended paid AI calls are introduced.

## Implemented

1. **Persistent, finite work queue** (`companion/operations_queue.py`) stored in `data/apex_operations.sqlite3`. Only four kinds are executable: Unity diagnostics, Git health, Unity Edit Mode tests, and manual desktop inspection. The queue records state, source, timestamps, and bounded results. Duplicate away jobs are deduplicated per day/project. A crash marks in-progress jobs **blocked**, not silently retried. Pause, resume and cancellation of pending tasks are supported.
2. **Context-triggered away jobs**. On local away detection or manual AWAY, APEX can queue approved Unity-log and Git checks, with optional Unity Edit Mode tests. It continues v0.7.1's separate narrowly verified **CS0105** import cleanup (up to two fixes/day, only while away, backup and undo). It cannot make general AI-generated edits unattended.
3. **Read-only Git integration** (`companion/operations_unity.py`): uses an allowlisted `git rev-parse`, `git branch --show-current`, and `git status --porcelain` on the approved workspace; no commit, push, branch creation, stash, reset, or checkout is performed. Git is optional. A Git HEAD revision is evidence, **not** a code backup.
4. **Unity Edit Mode runner**: configured `Unity.exe`, approved Unity project, `-batchmode -nographics -runTests -testPlatform EditMode -testResults ...`. The Editor must not be using the same project (`Temp/UnityLockfile` blocks). Runs are bounded to 60–600 seconds and tested through NUnit XML; a zero process exit alone is **not** considered success. Test suites may be unavailable or contain no tests.
5. **Approved patch + verification** (`VerifiedPatchTrial`). From the existing owner-reviewed single-file diff, choose **APPROVE + TEST / ROLLBACK**. The exact patch is backed up and applied; if Unity Edit Mode testing does not verify it, APEX restores the original file **only when the hash still matches the version APEX wrote**. Conflicting edits are never overwritten. Gameplay verification is still required.
6. **Windows UI Automation / selected-window inspection**. The OPERATIONS window can inspect an explicitly selected open application via optional pywinauto (Windows only), open an approved Unity project via an allowlisted launch, and—with per-capture permission—save a screenshot locally. No background screenshots, keylogging, clipboard scraping or arbitrary clicking.
7. **One-shot optional vision**. With COMPUTER / LOCAL and COMPUTER / AI enabled, the user may individually approve uploading one locally captured window image to Luna for visual analysis. The API call uses `store=False` and counts in the existing local spend ledger. It is **never automatic** and can transmit visible private information.
8. **Two-way private Telegram**. After separate pairing/permissions and enabling `ops_phone_commands`, the private owner can use `/status`, `/queue`, `/scan`, `/git`, `/pause`, `/resume`, and `/help`. Calls are authenticated against both Telegram private `chat.id` and sender ID and deduplicated using the Telegram update ID. No prompt text, code edit, test-run, purchase, deployment, shell command or arbitrary URL can be initiated from Telegram. Existing one-way phone briefings remain.
9. **Audit accessible to the AI** through the new **get_operations_history** read-only tool. Only sanitized task type, outcome, counts and timestamps are included; raw errors, screen captures, source code, local paths, credentials and personal records are not returned. `operations / AI` permission is required.
10. **Holographic UI preserved**. New OPERATIONS window is accessible from the left navigation; cloud, Steam, memory, voice, presence and prior UI remain.

## Important limitations

- **Not full autonomous programming**: arbitrary C# bug fixing is not safe without reliable tests. The only unattended source modification remains confirmed CS0105 removal. Larger AI patches require explicit desktop approval and preferably Unity tests.
- Tests can pass while behavior is wrong. A passing Edit Mode suite is **not** proof of gameplay correctness, race stability or Steam release readiness.
- The local app must be running, Windows logged in, and the PC awake to do background work. Supabase's preexisting server-side Steam cron remains independent.
- The Unity executable must be configured manually. Unity test execution defaults **OFF** because it can consume substantial PC resources; it requires the project not be open in another Editor. The app cannot guarantee all third-party Unity packages behave in batch mode.
- Remote commands require your preexisting Telegram bot credentials, `phone_brief_enabled`, `operations / PHONE` and the separate `ops_phone_commands` option; OFF by default. Telegram's `getUpdates` polling cannot coexist with another active webhook on the same bot.
- All screenshot analysis is owner-initiated and potentially billable. Local estimated AI budgets are **not** provider hard spending limits. No automatic paid AI actions are permitted.
- Prior databases and chats are not universally encrypted. Selected sensitive imports still use v0.7's Windows Credential Manager-backed encryption. Screenshots are ordinary local PNG files; manually delete them if unnecessary.
- The screen inspection functionality is limited to Windows and depends on accessibility support exposed by the target application; Unity custom views may expose little text. There is **no arbitrary desktop mouse/keyboard agent** in this release.

## Verification

- 135 automated tests, including v0.7 regressions and simulated task/Telegram/Unity/NUnit/rollback tests.
- Tkinter desktop window and operations panel launched in an offscreen display.
- Not tested here on the owner's actual Windows installation, Unity Editor version, private Telegram account, microphone, camera, or connected OpenAI/Supabase session. Real Windows testing remains required.
