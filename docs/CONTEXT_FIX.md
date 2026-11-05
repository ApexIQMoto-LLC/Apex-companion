# Why APEX said it had no Steamworks or device access

In v0.5 the chat context flag defaulted to `false`. The user signed in to
Supabase successfully but the OpenAI request included only short local notes.
Also, the AI prompt was constructed before asynchronous cloud fetches necessarily
finished. This made the answer seem disconnected from the command center.

## v0.5.1 fixes
- AI CLOUD CONTEXT control is visible next to the assistant panel.
- New default ON (existing user-set OFF is honored and visible).
- Choice is written to `config.json` when changed.
- The AI request worker refreshes stale or missing owner-visible Supabase and
  Steam summaries **before** creating the bounded AI prompt.
- Dated owner project knowledge helps interpret development blockers and beta
  progress, but is clearly historical, not a live task tracker.
- Status prompt includes Steam UTC reporting date, adds/deletes, coverage and
  heartbeat freshness; no raw telemetry, GPS, email, bank, or credentials.

## Security note
This is only user-scoped read-only reporting. It does NOT give the OpenAI model
an unrestricted database connection, a privileged API key, permission to run SQL
or permission to take actions in production.
