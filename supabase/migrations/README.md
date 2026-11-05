# Companion schema changes

The SQL in this directory is a prepared migration for a **new** private-by-RLS
Steam growth report table. Nothing in the package automatically executes SQL.

Use Supabase CLI `supabase migration new companion_steam_daily` and insert the
contents of `create_companion_steam_daily.sql` into its generated migration
file. Review it before applying through your existing deployment workflow.

The table has one SELECT-only owner policy. It has no INSERT/UPDATE/DELETE
policies for users. Only the server-side sync worker can write via an
administrative server credential kept in the Edge Function environment.
