# APEX 0.6.3 — consolidated release notes

**0.6.0**: Persistent local SQLite conversation/fact memory; inspection/deletion controls; OpenAI Responses API function-call loop using source-labeled, bounded, read-only cloud, Steam, marketing, memory, code-index and Unity log tools. No write tools exposed to the model.

**0.6.1**: Offline Vosk push-to-talk in addition to existing local wake phrases; local TTS response and user-triggered SILENCE; optional presence greetings. Audio devices and Vosk model need local setup.

**0.6.2**: Restart-safe local alerts for stale heartbeats, new Steam reporting dates, new RLS-visible beta applications and Unity error signatures. Acknowledgement/erase panel. Optional paid daily AI briefing explicitly defaults OFF. Free research and local morning briefing remain available.

**0.6.3**: Approved project folder picker; project-scoped code index, Unity log inspection (optional Editor.log), model-suggested single-file change, user-reviewed unified diff, explicit approval, SHA-256 conflict detection, backup and atomic replacement. Project revocation clears indexed snippets. No self-deployment, shell access, Git or unapproved file edits.

**Migration:** Use `Update_Existing_Install.cmd` over v0.5.1. Exclusions: `.env`, `config.json`, `data/`, `.venv/`. Your cloud refresh session remains in Windows Credential Manager. If you previously disabled AI CLOUD CONTEXT, the upgrade respects your preference.

**Verification:** 59 local automated tests, Python compileall, headless Tk window tests (including 1366×768 layout). Live Windows hardware, Supabase user login, API function-calling with the user's key, and actual Unity project diagnosis were not exercised here.
