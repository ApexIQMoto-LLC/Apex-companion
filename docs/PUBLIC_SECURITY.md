# Public distribution security

- No `.env`, `config.json`, populated `data/`, local notes, logs, credentials, refresh tokens, Steam keys or service-role secrets belong in git.
- No ApexIQ production Supabase project is preconfigured. Create your own Supabase project and set its URL and publishable key in your own local config.
- Enable row-level security for all user data, and verify isolation with multiple separate test users.
- Start microphone and camera disabled; enable only with local consent and OS permissions.
- Enable autonomous edits and remote commands only after reviewing scope, pairing and audit controls.
- Do not port the developer's production Steam integration migrations without verifying schema and credentials.
- Before opening a PR, scan for hard-coded keys, URLs, email addresses, personal notes, user directories and stored sessions.
- **Security note:** No independent security audit has been completed; do not treat this as secure remote management out of the box.
