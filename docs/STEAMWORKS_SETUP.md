# Steamworks sync status for ApexIQ Companion v0.5

**Already completed in your Supabase project as of Nov 4, 2026:**

- A.R.I.S Cloud project: `YOUR_SUPABASE_PROJECT_REF`
- Steam application: ApexIQ Replay Studio, AppID `5384270`
- Owner-scoped table `public.apexiq_companion_steam_daily` with RLS enabled
- Function `apexiq-companion-steam-sync` deployed (v5 at last successful test)
- Daily cron `apexiq-companion-steam-daily` scheduled at `30 9 * * *` UTC
- Valid server-side Steamworks Financial API key confirmed by successful authenticated import
- First successful live report: **Nov 2, 2026: 2 wishlist additions, 0 deletions, 0 purchases, 0 gifts.** This is daily activity, **not a total wishlist balance**. A missing date is *not* treated as zero.

**Nothing on this page requires recreating your Steamworks secret or database.** The Windows desktop only needs a normal ApexIQ user sign-in. Steam credentials remain in the Supabase Edge Function secret store, never shipped with the desktop app.

## If the Steam panel shows no data after sign-in

1. Confirm the dashboard shows **A.R.I.S CLOUD — AUTHENTICATED**, not **SIGN IN NEEDED**.
2. Use the same Supabase user who owns the private Steam report. User ID is matched by RLS.
3. Click **REFRESH EVERYTHING** and inspect the activity feed for errors.
4. Check the table `public.apexiq_companion_steam_daily` in the Supabase dashboard, and the Edge Function logs for `apexiq-companion-steam-sync`. Avoid pasting sensitive logs or keys into chat.
5. Remember that Steam may not publish the latest closed day immediately; the sync function leaves missing dates unavailable rather than inserting zeros.

This client is **read-only** toward Steamworks and Supabase. Do not add a Steam Financial API key or `sb_secret_` key to `.env`, `config.json`, or the application source.
