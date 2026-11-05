-- Prepared schema for Steamworks daily aggregated metrics, not raw publisher data.
-- Safe to apply more than once. Review and apply using your migration workflow.
create table if not exists public.apexiq_companion_steam_daily (
    owner_id uuid not null references auth.users(id) on delete cascade,
    app_id bigint not null check (app_id = 5384270),
    report_date date not null,
    wishlist_adds integer not null check (wishlist_adds >= 0),
    wishlist_deletes integer not null check (wishlist_deletes >= 0),
    wishlist_purchases integer not null check (wishlist_purchases >= 0),
    wishlist_gifts integer not null check (wishlist_gifts >= 0),
    fetched_at timestamptz not null default now(),
    primary key (owner_id, app_id, report_date)
);

alter table public.apexiq_companion_steam_daily enable row level security;
revoke all on public.apexiq_companion_steam_daily from public, anon, authenticated;
grant select on public.apexiq_companion_steam_daily to authenticated;

-- Normal users cannot write or see another owner's sales or wishlist data.
do $$ begin
    if not exists (select 1 from pg_policies
                   where schemaname = 'public'
                     and tablename = 'apexiq_companion_steam_daily'
                     and policyname = 'companion_owner_can_read') then
        create policy companion_owner_can_read
          on public.apexiq_companion_steam_daily
          for select to authenticated
          using (owner_id = (select auth.uid()));
    end if;
end $$;
