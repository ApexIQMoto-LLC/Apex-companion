# APEX v0.9.0 — Business Studio and Social Account Connections

**Built from APEX v0.8.0.**

- New Business Studio: local campaign attribution and UTM links, recorded lead/purchase outcomes, CSV performance imports, creator relationship tracker, deterministic content drafts and approvals, and segmented campaign evaluation.
- New **ACCOUNTS** tab with seven developer-app/authorization profiles: YouTube, GA4, Google Ads, TikTok, Instagram, Meta Ads, TikTok Ads.
- Google and TikTok Desktop OAuth use loopback browser authorization, one-time state validation and PKCE. TikTok follows its mandated hex SHA-256 challenge encoding.
- Instagram/Meta/TikTok Business require **owner-registered HTTPS redirect callbacks**. APEX provides a one-time manual callback URL completion path; provider registration/review remains mandatory.
- Windows Credential Manager stores secrets and access/refresh tokens. No credentials included in the distribution or sent to the AI.
- Google, TikTok and long-lived Instagram token refresh helpers prepared for future data collection. Token refresh is **not** unattended polling.
- No actual live social accounts, ads accounts, or developer APIs were connected during development. No daily API analytics sync yet. No publishing/spend.
- Existing v0.8 operations, holographic UI, phone briefings, Supabase/Steam reports and personal memories remain intact.

Read `SOCIAL_ACCOUNT_SETUP_v0_9.md` before configuring provider applications.
