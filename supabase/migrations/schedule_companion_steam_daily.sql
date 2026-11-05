-- Example only: replace YOUR_SUPABASE_PROJECT_REF with the ID of a project YOU own.
-- Do not run this on any ApexIQ production database. Deploy your own function first.
-- Requires pg_cron, pg_net, Vault and an explicitly configured secret.
select cron.schedule(
    'apex-companion-steam-daily',
    '30 9 * * *',
    $job$
      select net.http_post(
        url := 'https://YOUR_SUPABASE_PROJECT_REF.supabase.co/functions/v1/apexiq-companion-steam-sync',
        headers := jsonb_build_object(
          'Content-Type', 'application/json',
          'apikey', decrypted_secret
        ),
        body := '{"days":2}'::jsonb,
        timeout_milliseconds := 20000
      ) as request_id
      from vault.decrypted_secrets
      where name = 'companion_cron_secret_key'
      limit 1;
    $job$
);
