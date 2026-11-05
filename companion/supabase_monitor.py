"""Read-only, RLS-scoped, authenticated Supabase telemetry summaries.

No service-role keys, Postgres connection strings, or payment credentials.
Tokens stay in RAM and are never passed to a language model.
"""
from __future__ import annotations
import json
import time
import threading
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# No rider coordinates, emails, device tokens, auth keys, or raw payloads.
ALLOWED = {
    "Device heartbeats": ("apexiq_device_heartbeats", "last_seen_at,created_at,device_status,gps_status,imu_status,sync_status,ride_active", "created_at"),
    "Ride uploads": ("apexiq_ride_uploads", "received_at", "received_at"),
    "Telemetry frames": ("apexiq_telemetry_frames", "created_at", "created_at"),
    "ARIS reports": ("apexiq_aris_reports", "created_at,analysis_status", "created_at"),
    "Finalized journeys": ("apexiq_finalized_journey_projections", "updated_at,projection_status", "updated_at"),
    "Pull sessions": ("apexiq_pull_sessions", "ingested_at", "ingested_at"),
    "Beta applications": ("beta_applications", "created_at,status", "created_at"),
}


def _json_response(request: Request, timeout: int = 10):
    try:
        with urlopen(request, timeout=timeout) as resp:
            raw = resp.read(250_000)
            data = json.loads(raw.decode("utf-8")) if raw else None
            return data, dict(resp.info())
    except HTTPError as exc:
        # Do not expose server-returned details containing user data or headers.
        raise RuntimeError(f"HTTP {exc.code} from Supabase") from None
    except URLError as exc:
        raise RuntimeError(f"Supabase network connection failed: {exc.reason}") from None


def parse_total(content_range: str):
    try:
        tail = content_range.rsplit("/", 1)[1].strip()
        return int(tail) if tail != "*" else None
    except (IndexError, ValueError):
        return None


def freshness(last_seen: str | None, now=None) -> str:
    if not last_seen:
        return "unknown"
    try:
        at = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
        if at.tzinfo is None:
            return "unknown"
        delta = ((now or datetime.now(timezone.utc)) - at.astimezone(timezone.utc)).total_seconds()
        if delta < -10:
            return "clock mismatch"
        if delta <= 60:
            return "live <=60s"
        if delta <= 150:
            return "recent <=150s"
        return "stale >150s"
    except ValueError:
        return "unknown"


class SupabaseMonitor:
    def __init__(self, url: str, publishable_key: str):
        if not url.startswith("https://") or ".supabase.co" not in url:
            raise ValueError("A trusted HTTPS Supabase project URL is required")
        if not publishable_key.startswith("sb_publishable_"):
            raise ValueError("Only a publishable key is accepted; never use service_role")
        self.url = url.rstrip("/")
        self.key = publishable_key
        self._access = None
        self._refresh_token = None
        self._expires = 0.0
        self._lock = threading.RLock()
        self.on_session_update = None

    @property
    def signed_in(self) -> bool:
        return bool(self._access and self._refresh_token)

    def sign_out(self):
        # Local session forget; server-side revocation is a separate operation.
        self._access = self._refresh_token = None
        self._expires = 0.0

    def _auth_request(self, grant, payload):
        body = json.dumps(payload).encode("utf-8")
        req = Request(f"{self.url}/auth/v1/token?{urlencode({'grant_type': grant})}",
                      data=body, method="POST",
                      headers={"apikey": self.key, "Content-Type": "application/json",
                               "User-Agent": "ApexIQ-Companion/0.2"})
        response, _ = _json_response(req)
        if not isinstance(response, dict) or not response.get("access_token") or not response.get("refresh_token"):
            raise RuntimeError("Supabase Auth returned no usable user session")
        self._access = response["access_token"]
        self._refresh_token = response["refresh_token"]
        self._expires = time.time() + max(60, int(response.get("expires_in", 3600)) - 90)
        if self.on_session_update is not None:
            try:
                self.on_session_update(self._refresh_token)
            except Exception:
                pass  # Session remains usable in RAM even if Credential Manager fails.
        return True

    def sign_in(self, email, password):
        if not email or not password:
            raise ValueError("Email and password required")
        return self._auth_request("password", {"email": email, "password": password})

    def restore(self, refresh_token):
        """Restore an authorized user session from an OS-managed refresh token."""
        if not refresh_token or not isinstance(refresh_token, str):
            raise ValueError("A valid saved refresh token is required")
        with self._lock:
            return self._auth_request("refresh_token", {"refresh_token": refresh_token})

    def _token(self):
        with self._lock:
            if not self.signed_in:
                raise RuntimeError("Sign in with your ApexIQ Supabase user account first")
            if time.time() >= self._expires:
                self._auth_request("refresh_token", {"refresh_token": self._refresh_token})
            return self._access

    def table_summary(self, label, token):
        table, fields, order = ALLOWED[label]
        q = urlencode({"select": fields, "order": f"{order}.desc", "limit": "1"})
        req = Request(f"{self.url}/rest/v1/{table}?{q}",
                      headers={"apikey": self.key, "Authorization": "Bearer " + token,
                               "Prefer": "count=exact", "Range": "0-0",
                               "User-Agent": "ApexIQ-Companion/0.2"})
        data, headers = _json_response(req)
        if not isinstance(data, list):
            raise RuntimeError("Unexpected API response")
        # Whitelisted columns only, with no private identity fields.
        most_recent = {k: v for k, v in data[0].items() if k in fields.split(",")} if data else {}
        total = parse_total(headers.get("Content-Range", headers.get("content-range", "")))
        return {"visible_count": total, "latest": most_recent}

    def user_id(self):
        """Return only the authenticated UUID, useful when configuring the sync worker."""
        request = Request(f"{self.url}/auth/v1/user",
                          headers={"apikey": self.key,
                                   "Authorization": "Bearer " + self._token(),
                                   "User-Agent": "ApexIQ-Companion/0.3"})
        payload, _ = _json_response(request)
        import uuid
        try:
            return str(uuid.UUID(str(payload["id"])))
        except (TypeError, ValueError, KeyError):
            raise RuntimeError("Supabase Auth returned an invalid user identity") from None

    def snapshot(self):
        token = self._token()
        result = {"project": self.url, "checked_at_utc": datetime.now(timezone.utc).isoformat(), "tables": {}}
        for label in ALLOWED:
            try:
                result["tables"][label] = self.table_summary(label, token)
            except RuntimeError as exc:
                result["tables"][label] = {"error": str(exc), "note": "May require a user-scoped authorized API endpoint or RLS policy"}
        item = result["tables"].get("Device heartbeats", {})
        result["device_freshness"] = freshness(item.get("latest", {}).get("last_seen_at"))
        return result


def render_snapshot(snapshot):
    lines = ["APEXIQ SUPABASE / USER-SCOPED READ-ONLY SNAPSHOT",
             f"Checked UTC: {snapshot['checked_at_utc']}",
             f"Heartbeat freshness: {snapshot['device_freshness']}",
             "Counts are visible to YOUR signed-in role under RLS, not global database totals.", ""]
    for name, row in snapshot["tables"].items():
        if "error" in row:
            lines.append(f"- {name}: unavailable ({row['error']})")
        else:
            lines.append(f"- {name}: visible records={row.get('visible_count', 'unknown')} | latest={row.get('latest', {})}")
    lines.extend(["", "No raw GPS data, rider identities, API secrets, or tokens are sent to the AI."])
    return "\n".join(lines)
