/**
 * ApexIQ Companion - server-only Steamworks wishlist sync.
 * Requires Supabase function auth mode "secret" (never a public/desktop key).
 * Steamworks Financial API key stays in the Edge Function environment.
 * The only outbound Steam request is GetAppWishlistReporting for APP_ID.
 * No app finances, other publisher games, raw responses, or credentials are stored.
 *
 * See docs/STEAMWORKS_SETUP.md before deploying.
 */
import { withSupabase } from "npm:@supabase/server@1";

const APP_ID = 5384270;
const STEAM_API_URL =
  "https://partner.steam-api.com/IPartnerFinancialsService/GetAppWishlistReporting/v001/";

function utcDate(daysAgo: number): string {
  const d = new Date();
  d.setUTCHours(0, 0, 0, 0);
  d.setUTCDate(d.getUTCDate() - daysAgo);
  return d.toISOString().slice(0, 10);
}

function nonnegativeInt(input: unknown): number | null {
  const value = typeof input === "number" ? input :
    typeof input === "string" && /^\d+$/.test(input) ? Number(input) : NaN;
  return Number.isSafeInteger(value) && value >= 0 && value <= 2147483647
    ? value : null;
}

function parseSteamDaily(payload: unknown, expectedDay: string) {
  if (!payload || typeof payload !== "object") return null;
  const outer = payload as Record<string, unknown>;
  const result = outer.response;
  if (!result || typeof result !== "object") return null;
  const report = result as Record<string, unknown>;
  if (report.appid !== undefined && Number(report.appid) !== APP_ID) return null;
  if (report.date !== undefined &&
      String(report.date).replaceAll("/", "-") !== expectedDay) return null;
  if (!report.wishlist_summary || typeof report.wishlist_summary !== "object") {
    // No data yet, NOT a day of zero activity.
    return null;
  }
  const summary = report.wishlist_summary as Record<string, unknown>;
  const adds = nonnegativeInt(summary.wishlist_adds);
  const deletes = nonnegativeInt(summary.wishlist_deletes);
  const purchases = nonnegativeInt(summary.wishlist_purchases);
  const gifts = nonnegativeInt(summary.wishlist_gifts);
  if ([adds, deletes, purchases, gifts].some((v) => v === null)) {
    return null;
  }
  return {
    wishlist_adds: adds!, wishlist_deletes: deletes!,
    wishlist_purchases: purchases!, wishlist_gifts: gifts!,
  };
}

async function fetchWishlist(day: string, steamKey: string) {
  const url = new URL(STEAM_API_URL);
  url.searchParams.set("appid", String(APP_ID));
  url.searchParams.set("date", day);
  // Steamworks documents this Financial API's required `key` query field.
  // Only this server makes the request; never log the URL or its query.
  url.searchParams.set("key", steamKey);
  const res = await fetch(url.toString(), {
    method: "GET",
    redirect: "error", signal: AbortSignal.timeout(12_000),
  });
  if (!res.ok) throw new Error(`steam_http_${res.status}`);
  const data = await res.json();
  return parseSteamDaily(data, day);
}

export default {
  fetch: withSupabase({ auth: "secret" }, async (req, ctx) => {
    if (req.method !== "POST") {
      return Response.json({ error: "POST required" }, { status: 405 });
    }
    const key = Deno.env.get("COMPANION_STEAM_FINANCIAL_KEY");
    const owner = Deno.env.get("COMPANION_OWNER_USER_ID");
    if (!key || !owner ||
        !/^[0-9a-fA-F-]{36}$/.test(owner)) {
      return Response.json({ error: "Steam integration not configured" }, { status: 503 });
    }
    let body: Record<string, unknown> = {};
    try {
      body = (await req.json()) as Record<string, unknown>;
    } catch (_) {
      // A blank body means a normal daily 2-day sync.
    }
    const count = body?.days === undefined ? 2 : Number(body.days);
    if (!Number.isInteger(count) || count < 1 || count > 30) {
      return Response.json({ error: "days must be an integer between 1 and 30" }, { status: 400 });
    }

    let saved = 0, noData = 0;
    const failures: Array<{ date: string; reason: string }> = [];
    // Always use CLOSED UTC dates; Steam refreshes reports daily.
    for (let age = count; age >= 1; age--) {
      const day = utcDate(age);
      try {
        const summary = await fetchWishlist(day, key);
        if (!summary) {
          noData++;
          continue;
        }
        const { error } = await ctx.supabaseAdmin
          .from("apexiq_companion_steam_daily")
          .upsert({
            owner_id: owner, app_id: APP_ID, report_date: day,
            ...summary, fetched_at: new Date().toISOString(),
          }, { onConflict: "owner_id,app_id,report_date" });
        if (error) {
          failures.push({ date: day, reason: "database_error" });
        } else {
          saved++;
        }
      } catch (e) {
        // Never send upstream Steam payloads or credentials to callers/logs.
        const reason = e instanceof Error && /^steam_http_\d+$/.test(e.message)
          ? e.message : "upstream_error";
        failures.push({ date: day, reason });
      }
    }
    return Response.json({ ok: failures.length === 0, app_id: APP_ID,
      days_requested: count, days_saved: saved, days_unavailable: noData,
      failed_dates: failures });
  }),
};
