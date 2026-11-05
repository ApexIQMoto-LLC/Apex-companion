"""Read-only Steam growth summaries through user-authenticated Supabase RLS.

The Steamworks Financial API key NEVER enters this desktop app. Only aggregate
and app-filtered snapshots, materialized on a trusted server, are consumed.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request

from .supabase_monitor import _json_response

APP_ID = 5384270
TABLE = "apexiq_companion_steam_daily"
FIELDS = ("report_date,app_id,wishlist_adds,wishlist_deletes,"
          "wishlist_purchases,wishlist_gifts,fetched_at")


def summarize_daily(rows: list[dict], today: date | None = None) -> dict:
    """Aggregate verified daily Steam snapshots; never imply a total wishlist count."""
    today = today or datetime.now(timezone.utc).date()
    valid = {}
    for row in rows:
        if not isinstance(row, dict) or int(row.get("app_id", -1)) != APP_ID:
            continue
        try:
            when = date.fromisoformat(str(row["report_date"]))
        except (ValueError, KeyError, TypeError):
            continue
        if when > today or when < today - timedelta(days=90):
            continue
        numbers = {}
        for label in ("wishlist_adds", "wishlist_deletes", "wishlist_purchases", "wishlist_gifts"):
            try:
                value = int(row[label])
            except (ValueError, TypeError, KeyError):
                break
            if not 0 <= value <= 2_147_483_647:
                break
            numbers[label] = value
        if len(numbers) == 4:
            valid[when] = numbers
    if not valid:
        return {"status": "not_synced", "days": 0, "notes": "No authorized Steam snapshots are visible yet."}
    dates = sorted(valid)
    latest_date = dates[-1]
    latest = valid[latest_date]
    last7 = [valid[d] for d in dates if today - timedelta(days=7) <= d < today]
    previous7 = [valid[d] for d in dates if today - timedelta(days=14) <= d < today - timedelta(days=7)]
    last7_adds = sum(r["wishlist_adds"] for r in last7)
    previous7_adds = sum(r["wishlist_adds"] for r in previous7)
    comparison = None
    # Only compare full windows; missing snapshots are not zero-activity days.
    if len(last7) == 7 and len(previous7) == 7:
        comparison = last7_adds - previous7_adds
    return {
        "status": "ok", "days": len(valid), "latest_date": latest_date.isoformat(),
        "latest": latest, "last7_adds": last7_adds, "last7_coverage_days": len(last7),
        "previous7_adds": previous7_adds, "previous7_coverage_days": len(previous7),
        "week_over_week_adds_change": comparison,
        "notice": "Daily activity, not current wishlist balance; financial data not included.",
    }


def render_summary(summary: dict) -> str:
    if summary["status"] != "ok":
        return ("STEAMWORKS / APEXIQ REPLAY STUDIO\n"
                "No synchronized Steam data visible yet.\n"
                "Complete the private Steamworks Financial key setup and server sync.\n"
                "Public marketing research works independently of this connection.")
    newest = summary["latest"]
    lines = ["STEAMWORKS / APEXIQ REPLAY STUDIO", f"AppID: {APP_ID}",
             f"Latest Steam reporting date (UTC): {summary['latest_date']}",
             f"Wishlist adds: {newest['wishlist_adds']}",
             f"Wishlist deletes: {newest['wishlist_deletes']}",
             f"Wishlist purchases: {newest['wishlist_purchases']}",
             f"Wishlist gifts: {newest['wishlist_gifts']}",
             f"Past 7 closed UTC days: {summary['last7_adds']} adds "
             f"({summary['last7_coverage_days']}/7 reporting days observed)"]
    delta = summary.get("week_over_week_adds_change")
    if delta is not None:
        lines.append(f"Compared with previous full week: {delta:+d} adds")
    else:
        lines.append("Week-over-week trend unavailable until 14 complete days are synced.")
    lines.append("Data source: owner-scoped Supabase snapshot; Steamworks Financial API.")
    lines.append(summary["notice"])
    return "\n".join(lines)


class SteamworksReader:
    def __init__(self, supabase_monitor):
        self.monitor = supabase_monitor

    def fetch(self, days=30):
        # Enforce hard upper bounds; never query unrestricted tables or sensitive columns.
        days = max(1, min(60, int(days)))
        cutoff = (datetime.now(timezone.utc).date() - timedelta(days=days)).isoformat()
        params = urlencode({"select": FIELDS, "app_id": f"eq.{APP_ID}",
                            "report_date": f"gte.{cutoff}",
                            "order": "report_date.asc", "limit": str(days + 2)})
        token = self.monitor._token()
        request = Request(
            f"{self.monitor.url}/rest/v1/{TABLE}?{params}",
            headers={"apikey": self.monitor.key, "Authorization": f"Bearer {token}",
                     "User-Agent": "ApexIQ-Companion/0.3"})
        rows, _ = _json_response(request)
        if not isinstance(rows, list):
            raise RuntimeError("Unexpected Steam summary response from Supabase")
        return summarize_daily(rows)
