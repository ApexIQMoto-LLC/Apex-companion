# Install v0.6.3.1 over v0.6.3

1. Close APEX Companion fully, including its Python/Command Prompt window.
2. Extract the complete ApexIQ_Companion_v0_6_3_1.zip into a NEW folder.
3. Double-click Update_Existing_Install.cmd in that extracted folder.
4. Check the target location (normally C:\ApexIQCompanion), then approve the update.
5. Run start_windows.bat from your ORIGINAL installed folder.

The updater leaves .env, config.json, local data directory (memory and history databases), usage tracking, Windows Credential Manager session, and .venv untouched.

# Validation
- Ask for the full six-part operational intelligence briefing again. A normal response may use a larger output-token budget, which can cost more than a short response.
- Review MEMORY / CONTROL to confirm the quoted priority was saved if your prompt included an explicit `Remember this priority:` instruction.
- Approve the Unity project folder separately before testing Unity logs or source analysis.
- If you still encounter a failure, copy the exact error text and note whether you were in DEEP REASONING. Do not share API keys, tokens, or session files.

The app is not allowed to edit code without your approval; it does not schedule paid AI work unless you opt in.
