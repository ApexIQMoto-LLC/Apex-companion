# APEX v0.8 Security, Permissions and Autonomy Contract

**APEX 0.8.0 away-mode constraint:** Only while Windows idle/face-presence monitor declares AWAY, or the owner selects MANUAL AWAY, may the narrowly allowlisted CS0105 cleanup run unattended. "At work" is not independently known. Voice and camera start by default at login after a one-time user-requested migration, but can be independently disabled and stay disabled. Source edits require manual Unity compile to confirm.

**User-granted authority:** APEX can autonomously inspect already authorized business/project data; build local plans; generate alerts; and apply a narrowly allowlisted, undoable Unity C# compile-warning cleanup while its process runs. This permission never implies authority to spend money, make purchases, send email, manipulate banks, execute arbitrary scripts or terminals, deploy to production, delete projects, bypass OS security, or perform major code changes.

## Permission matrix

| Category | Local default | AI default | Phone default | Notes |
|---|---:|---:|---:|---|
| Operations | On | On | Off | Existing owner-visible cloud and app operational summaries |
| Projects | On | On | Off | Authorized ApexIQ/Unity context and explicit project facts |
| Personal | Off | Off | Off | No automatic import of private preferences or history |
| Computer | Off | Off | Off | Foreground *executable names only*, separate opt-in flag |
| Calendar | Off | Off | Off | Manual selected ICS import only |
| Communications | Off | Off | Off | Manual selected export only; no email connector |
| Finance | Off | Off | Off | Manual selected export only; no bank connector |
| Health | Off | Off | Off | Manual selected export only; no health account connector |

AI/PHONE access requires Local. If permission is revoked during an AI call, tool results are discarded by the generation check where supported; newly revoked data is blocked on future retrieval. Existing prior conversation text from an earlier authorized request cannot be retroactively removed from OpenAI by revoking local access. To erase a category, use Data Permissions -> ERASE; legacy memory is managed separately in Memory / Control. Sensitive imports are encrypted individually; their source files remain outside Companion.

## Model access and data storage

APEX can retrieve only limited excerpts and metadata from approved sources. User-initiated OpenAI calls remain billable under the user's API account, even if background spending is disabled. The API key stays in local `.env`; the Steam Financial key stays in Supabase Edge secrets; the Supabase desktop connects with the user-scoped publishable key and refresh session in Windows Credential Manager. Never place privileged Supabase keys in the desktop application.

`data/apex_personal_intel.sqlite3`, legacy `data/apex_memory.sqlite3`, alerts, timeline and project-code index are **not encrypted**. Owner-selected private imports are encrypted with Fernet and use an encryption key in Windows Credential Manager. If keyring is missing, key storage fails, or access is revoked, the app blocks private import access rather than falling back to plaintext.

## Auto-fix boundaries

- Only compiler-identified `CS0105` duplicate `using` C# warnings, in a **single first-party** source file under `Assets/` in the owner-approved Unity project. No Editor, Packages, Plugins, or excluded third-party paths; no symlinks; maximum 32 KB file size.
- Edit exactly one redundant directive in the first 110 lines with matching duplicate and without conditional preprocessor context. Max two successful fixes in a local calendar day.
- Each file is backed up before an atomic edit; the result is compared against the known expected bytes and logged. This is static verification, *not* Unity compile verification.
- Undo requires a separate owner confirmation, matching project identity, intact backup hash, and current file equal to last fix's hash. No blind overwrite of later user/Unity changes.
- No unattended paid OpenAI calls or arbitrary shell/PowerShell execution. v0.8 may start a configured Unity executable with fixed, bounded EditMode test arguments **only after separately opting in**; read-only Git commands and explicit owner-approved Unity launches are also allowlisted.
- Reviewed single-file AI patch proposals can optionally run Unity Edit Mode tests and roll back the exact backed-up file after failure. A passing NUnit suite is not proof of gameplay correctness. Unattended AI-generated source edits remain prohibited.
- Windows UI Automation reads owner-selected accessible controls with COMPUTER / LOCAL consent; local screenshots require per-image approval, and optional paid vision needs COMPUTER / AI permission plus another per-image approval. Images are never uploaded automatically.

## Phone messages

Phone briefings use a private Telegram bot paired through `Pair_Phone.cmd`. Bot token and private chat ID are saved in the OS credential store. Telegram stores messages on Telegram's service; they are **not end-to-end encrypted** to the bot. Enable `operations / PHONE` to include business summary metadata; enable `projects / PHONE` to include auto-fix alerts. Default delivery is OFF, and messages omit source code, raw GPS, user identity lists and financial/medical entries. v0.8 adds **separately opt-in inbound commands**, polled from Telegram only when phone delivery, OPERATIONS / PHONE, and `ops_phone_commands` are all enabled. Messages must originate from the owner in a private chat. Allowed remote commands are limited to `/status`, `/queue`, `/scan`, `/git`, `/pause`, `/resume` and `/help`; none can spend money, inspect screenshots, run Unity tests, edit code or execute arbitrary scripts.

## Local activity sampling

Optional process name sampling uses Win32 `GetForegroundWindow` plus `QueryFullProcessImageNameW`, returns only executable basename. The opt-in *foreground app-name sampler* does not read window titles, keystrokes, clipboard, browser history, screens or audio. The new separate manually invoked Windows inspector **can read selected window titles and accessibility control labels**, and owner-approved screenshots can record visible content locally. Samples approximate foreground application, not attention/productivity. Disabling Computer / Local immediately prevents future samples.

## Reporting and audit

Plans and trend claims are labeled by source, date, and evidence coverage. Missing time windows are unknown rather than zeros. Fixes and permissions changes are logged locally; logs may contain filenames or safe event descriptions and are not sent to Telegram without an opt-in. All local monitoring stops with APEX or PC shutdown. The separately scheduled Steamworks Edge Function is an independent server-side process.

## v0.9 marketing and social account permissions

Social developer credentials and account tokens are stored only in Windows Credential Manager by `companion/social_auth.py`, never in Supabase, local SQLite marketing data, AI context, Telegram briefings, `.env`, or `config.json`. Authorization requires a direct owner interaction and provider consent. OAuth loopback listeners bind only to 127.0.0.1, use one-time CSRF state, and Google's and TikTok's respective PKCE encoding. Instagram/Meta/TikTok Ads need owner-registered HTTPS redirects; the initial owner-only pasted callback option is not an OAuth backend for distribution to other users. Do not log redirect query parameters at the company website/CDN. Disconnect clears the local token, and provider authorization should separately be revoked in the platform's account settings when necessary.

Google Ads uses the `adwords` OAuth scope, which is not read-only at the provider level. The application has no ad-write tools, but only authorize it if you accept the token's broader potential privileges. No automatic organic publishing, paid campaign creation/editing, spending, messages, or production cloud changes are enabled. Current login status is **not a verified API data import**; authorization alone cannot establish insight access, approvals, quotas or account ownership. Read `SOCIAL_ACCOUNT_SETUP_v0_9.md` for prerequisites.
