"""Presentation-safe, owner-scoped summary functions for the Companion dashboard.

No fabricated metric defaults. Caller is responsible for authenticating the
Supabase monitor and preserving the original data provenance.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


def due(last: datetime | None, every_minutes: int, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    if last is None:
        return True
    if last.tzinfo is None:
        return True
    return now - last >= timedelta(minutes=max(1, every_minutes))


def readable_count(data: dict | None, table: str) -> str:
    if not data:
        return "--"
    record = data.get("tables", {}).get(table, {})
    if record.get("error"):
        return "Restricted"
    count = record.get("visible_count")
    return f"{count:,}" if isinstance(count, int) and count >= 0 else "--"


def cloud_status(data: dict | None, signed_in: bool = False) -> tuple[str, str]:
    if not signed_in:
        return ("SIGN IN NEEDED", "Connect with your ApexIQ account")
    if not data:
        return ("CONNECTED", "Waiting for an authorized health snapshot")
    freshness = data.get("device_freshness", "unknown")
    if freshness.startswith("live"):
        return ("HEARTBEAT LIVE", "Latest authorized device heartbeat is fresh")
    if freshness.startswith("recent"):
        return ("HEARTBEAT RECENT", "Device heartbeat is under 150 seconds old")
    if freshness.startswith("stale"):
        return ("HEARTBEAT STALE", "Last visible heartbeat is more than 150 seconds old")
    return ("SIGNED IN", "Heartbeat status unavailable under current permissions")


def steam_status(data: dict | None, signed_in: bool = False) -> tuple[str, str]:
    if not signed_in:
        return ("SIGN IN NEEDED", "Wishlist data is private to the owner")
    if not data or data.get("status") != "ok":
        return ("NO REPORT VISIBLE", "Waiting for an owner-scoped daily Steam report")
    day = data.get("latest_date", "unknown date")
    return ("REPORT AVAILABLE", f"Daily activity from {day}; not total wishlist count")


def marketing_previews(data: dict | None, max_items: int = 3) -> list[dict[str, str]]:
    if data and data.get("opportunities"):
        previews = []
        for item in data["opportunities"][:max_items]:
            previews.append({
                "title": str(item.get("title", "Unknown headline"))[:160],
                "subtitle": str(item.get("category", "Research")),
                "action": str(item.get("next_step", "Verify the source before acting"))[:250],
                "url": str(item.get("url", "")),
                "kind": "UNVERIFIED SIGNAL",
            })
        return previews
    return [
        {"title": "In-store motorcycle hardware demo", "subtitle": "Retail outreach",
         "action": "Prepare a working demo and a short retailer pitch for review.", "url": "", "kind": "STANDING IDEA"},
        {"title": "Creator evaluation kits", "subtitle": "Beta recruitment",
         "action": "Shortlist suitable motorcycle creators once hardware ride testing passes.", "url": "", "kind": "STANDING IDEA"},
        {"title": "Replay Studio Steam trailer", "subtitle": "Steam visibility",
         "action": "Test a gameplay-first trailer and measure subsequent wishlist activity.", "url": "", "kind": "STANDING IDEA"},
    ][:max_items]


def news_previews(brief: list[tuple[str, list[dict]]] | None, limit: int = 3) -> list[dict]:
    out = []
    for topic, items in brief or []:
        for item in items:
            url = str(item.get("url", ""))
            if url.startswith("https://"):
                out.append({"topic": topic, "title": str(item.get("title", ""))[:190],
                            "url": url, "published": str(item.get("published", ""))})
            if len(out) >= limit:
                return out
    return out


def local_brief(cloud: dict | None, steam: dict | None, marketing: dict | None,
                brief: list | None, signed_in: bool) -> str:
    status, desc = cloud_status(cloud, signed_in)
    lines = ["APEXIQ COMPANION — CURRENT LOCAL BRIEFING", "", f"Cloud: {status}. {desc}."]
    if cloud:
        for label in ("Device heartbeats", "Ride uploads", "ARIS reports", "Beta applications"):
            lines.append(f"{label}: {readable_count(cloud, label)} visible records (RLS-scoped)")
    steam_label, steam_info = steam_status(steam, signed_in)
    lines.append(f"Steam: {steam_label}. {steam_info}.")
    if steam and steam.get("status") == "ok":
        latest = steam["latest"]
        lines.append(f"Latest closed report: {latest.get('wishlist_adds', '--')} additions, "
                     f"{latest.get('wishlist_deletes', '--')} deletions.")
    lines.append("Marketing: " + (f"{len(marketing.get('opportunities', []))} unverified research signals collected."
                                  if marketing else "No current scan yet; standing ideas are suggestions only."))
    lines.append(f"Business news: {sum(len(items) for _, items in brief) if brief else 0} cached public headlines.")
    lines.append("This brief is based on the information visible in the desktop, not unrestricted production database access.")
    return "\n".join(lines)


def _safe_value(value: object, max_len: int = 64) -> str:
    """Single-line short values only; no raw payloads or identifiers."""
    if value is None or value == "":
        return "unavailable"
    return "".join(ch for ch in str(value) if ch.isprintable() and ch not in "\r\n")[:max_len]


def bounded_ai_context(cloud: dict | None, steam: dict | None, marketing: dict | None,
                       brief: list | None, signed_in: bool) -> str:
    """User-approved, owner-visible operational data for AI conversations.

    No rider identity, location, coordinates, telemetry frames, passwords,
    payment information, API keys, or Supabase tokens enter this summary.
    Tables and fields are exhaustively whitelisted below.
    """
    lines = ["AUTHORIZED APEXIQ DASHBOARD SNAPSHOT / READ ONLY",
             "Source: the user's RLS-protected Supabase session and cached public research.",
             "These are historical/as-of observations, not evidence of real-time access.",
             "Use available verified figures; do not say Steamworks is inaccessible when a report exists.",
             "Never equate wishlist *daily adds* with the current wishlist *balance*."]
    lines.append("Cloud session: " + ("user authenticated" if signed_in else "not authenticated"))
    if signed_in and cloud:
        lines.append("Cloud snapshot checked at UTC: " + _safe_value(cloud.get("checked_at_utc")))
        lines.append("Most recent visible device heartbeat freshness: " + _safe_value(cloud.get("device_freshness")))
        heart = cloud.get("tables", {}).get("Device heartbeats", {})
        if isinstance(heart, dict) and not heart.get("error"):
            latest = heart.get("latest", {}) or {}
            if isinstance(latest, dict):
                for field in ("last_seen_at", "device_status", "gps_status", "imu_status", "sync_status", "ride_active"):
                    if field in latest:
                        lines.append("Last visible heartbeat " + field + ": " + _safe_value(latest[field]))
        for name in ("Device heartbeats", "Ride uploads", "Telemetry frames", "ARIS reports",
                     "Finalized journeys", "Pull sessions", "Beta applications"):
            lines.append(name + " (user-visible record count, NOT fleet global): " + readable_count(cloud, name))
        for name, datefield in (("Ride uploads", "received_at"), ("ARIS reports", "created_at"),
                                ("Pull sessions", "ingested_at"), ("Beta applications", "created_at")):
            row = cloud.get("tables", {}).get(name, {})
            if isinstance(row, dict) and not row.get("error") and isinstance(row.get("latest"), dict):
                if datefield in row["latest"]:
                    lines.append(name + " last visible " + datefield + ": " + _safe_value(row["latest"][datefield]))
    elif signed_in:
        lines.append("Cloud: authenticated, but health metrics have not been retrieved. Do not infer zero records or a healthy device.")
    else:
        lines.append("Cloud: not signed in; private metrics unavailable. This is not proof the cloud is offline.")

    if signed_in and steam and steam.get("status") == "ok":
        numbers = steam.get("latest", {})
        lines.append("Verified owner-visible Replay Studio Steamworks report for UTC date "
                     + _safe_value(steam.get("latest_date")) + ":")
        for field in ("wishlist_adds", "wishlist_deletes", "wishlist_purchases", "wishlist_gifts"):
            lines.append("  " + field + ": " + _safe_value(numbers.get(field)))
        lines.append("  Last 7 days: " + _safe_value(steam.get("last7_adds")) +
                     " wishlist additions across " + _safe_value(steam.get("last7_coverage_days")) +
                     "/7 reporting dates. Missing days do NOT equal zero activity.")
        lines.append("Total active wishlists / Steam traffic attribution: NOT AVAILABLE in this report.")
    elif signed_in:
        lines.append("Steam: no owner-visible synchronized daily report returned yet. Do not infer zero wishlists.")
    else:
        lines.append("Steam: no authenticated report available.")

    if marketing:
        lines.append("Marketing public RSS scan UTC: " + _safe_value(marketing.get("created_at_utc")))
        lines.append("Number of UNVERIFIED research signals: " +
                     _safe_value(len(marketing.get("opportunities", []))))
        for item in marketing_previews(marketing, 3):
            lines.append("UNVERIFIED research idea: " + _safe_value(item["title"], 120))
    else:
        lines.append("Marketing: no fresh local research scan cached.")
    if brief:
        for item in news_previews(brief, 2):
            lines.append("UNVERIFIED public news headline: " + _safe_value(item["title"], 115))
    lines.append("NOT INCLUDED: raw GPS, riding histories, rider identities, credentials, banking data, or private records.")
    return "\n".join(lines)[:4700]
