# Public architecture and trust boundaries

- **Windows local app:** pystray system tray, optional holographic UI, user-initiated speech/Vosk or Whisper, optional Kokoro TTS.
- **Local diagnostics:** Unity/log scanners, process and project health. Reads should be constrained to user-approved directories.
- **Providers:** OpenAI or other user-selected models via local `.env`; never bundle credentials.
- **Cloud:** optional user-owned Supabase project. Use a publishable/anon client key and row-level security, never a service-role key in the desktop. A Supabase URL does not grant data access without the owner's security policies.
- **Remote:** optional user-controlled channel, independently paired and authenticated; allow-listed commands only. Do not expose raw shell execution or localhost dashboards publicly.
- **Data:** user notes, chat history, provider tokens, screenshots, and logs stay local unless specifically enabled by the owner.

This public source originated from an ApexIQ-specific app. Proprietary cloud tables and Steam publisher integrations are examples, **not** automatically portable to arbitrary Supabase projects. Provide your own migrations and policies for any integration you enable.

## Safe publishing
See PUBLIC_SECURITY.md. Review all changes for secrets and personal information before making a public commit.
