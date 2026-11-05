"""Owner-initiated read-mostly OAuth for APEX Business Studio.

Tokens/client secrets remain in Windows Credential Manager. No credentials are
written to config, source, SQLite, diagnostic logs, cloud or AI context.
Provider approval, developer configuration and account consent are required.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import secrets
import socket
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen
import webbrowser

SERVICE = "ApexIQCompanion.Business.OAuth.v1"


@dataclass(frozen=True)
class Platform:
    id: str
    label: str
    vendor: str
    mode: str  # desktop | external_https
    scope: tuple[str, ...]
    portal: str
    needs_secret: bool = False
    developer_token: bool = False


PLATFORMS = {
    "youtube": Platform("youtube", "YouTube Analytics", "google", "desktop", (
        "https://www.googleapis.com/auth/youtube.readonly",
        "https://www.googleapis.com/auth/yt-analytics.readonly"),
        "https://console.cloud.google.com/apis/credentials"),
    "ga4": Platform("ga4", "Google Analytics 4", "google", "desktop", (
        "https://www.googleapis.com/auth/analytics.readonly",),
        "https://console.cloud.google.com/apis/credentials"),
    "google_ads": Platform("google_ads", "Google Ads", "google", "desktop", (
        "https://www.googleapis.com/auth/adwords",),
        "https://developers.google.com/google-ads/api/docs/oauth/overview", developer_token=True),
    "tiktok": Platform("tiktok", "TikTok Organic", "tiktok", "desktop", (
        "user.info.basic", "video.list"),
        "https://developers.tiktok.com/", needs_secret=True),
    "instagram": Platform("instagram", "Instagram Insights", "instagram", "external_https", (
        "instagram_business_basic", "instagram_business_manage_insights"),
        "https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/", needs_secret=True),
    "meta_ads": Platform("meta_ads", "Meta Ads", "meta", "external_https", (
        "ads_read",),
        "https://developers.facebook.com/docs/marketing-apis/", needs_secret=True),
    "tiktok_ads": Platform("tiktok_ads", "TikTok Ads", "tiktok_business", "external_https", (),
        "https://business-api.tiktok.com/portal/", needs_secret=True),
}

# TikTok desktop callback must exactly match a portal-registered URI.
TIKTOK_CALLBACK = "http://127.0.0.1:8769/callback"
GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
TIKTOK_AUTH = "https://www.tiktok.com/v2/auth/authorize/"
TIKTOK_TOKEN = "https://open.tiktokapis.com/v2/oauth/token/"
IG_AUTH = "https://www.instagram.com/oauth/authorize"
IG_TOKEN = "https://api.instagram.com/oauth/access_token"
META_AUTH = "https://www.facebook.com/v25.0/dialog/oauth"
META_TOKEN = "https://graph.facebook.com/v25.0/oauth/access_token"
TT_ADS_TOKEN = "https://business-api.tiktok.com/open_api/v1.3/oauth2/access_token/"
AUTH_TIMEOUT = 180


class AuthError(RuntimeError):
    """Safe error suitable for display. No tokens or raw response bodies."""


class WindowsVault:
    """Credential Manager only; deliberately no plaintext fallback."""

    def __init__(self, backend=None, *, require_windows=True):
        if backend is None:
            if require_windows and sys.platform != "win32":
                raise AuthError("Credential Manager is only supported on Windows")
            try:
                import keyring
            except ImportError as exc:
                raise AuthError("Install keyring before connecting accounts") from exc
            backend = keyring
        self._backend = backend

    def _account(self, platform, field):
        if platform not in PLATFORMS and platform != "google":
            raise ValueError("Unknown platform")
        if field not in ("client_id", "client_secret", "redirect_uri", "developer_token", "auth_url", "tokens"):
            raise ValueError("Invalid credential field")
        return f"{platform}:{field}"

    def read(self, platform, field):
        try:
            return self._backend.get_password(SERVICE, self._account(platform, field))
        except Exception as exc:
            raise AuthError("Windows Credential Manager could not read the connection") from exc

    def save(self, platform, field, value):
        if not isinstance(value, str) or not value.strip() or len(value) > 16000:
            raise ValueError("Missing or invalid credential value")
        try:
            self._backend.set_password(SERVICE, self._account(platform, field), value.strip())
        except Exception as exc:
            raise AuthError("Windows Credential Manager could not save the connection") from exc

    def clear(self, platform, field):
        try:
            self._backend.delete_password(SERVICE, self._account(platform, field))
        except Exception:
            pass

    def config_owner(self, platform):
        return "google" if PLATFORMS[platform].vendor == "google" else platform

    def set_client_id(self, platform, value):
        self.save(self.config_owner(platform), "client_id", value)

    def set_secret(self, platform, value):
        self.save(self.config_owner(platform), "client_secret", value)

    def client_id(self, platform):
        return self.read(self.config_owner(platform), "client_id")

    def secret(self, platform):
        return self.read(self.config_owner(platform), "client_secret")

    def status(self, platform):
        if not self.client_id(platform):
            return "SET UP APP ID"
        if PLATFORMS[platform].needs_secret and not self.secret(platform):
            return "SET UP APP SECRET"
        if PLATFORMS[platform].mode == "external_https" and not self.read(platform, "redirect_uri"):
            return "SET UP HTTPS CALLBACK"
        if platform == "tiktok_ads" and not self.read(platform, "auth_url"):
            return "SET UP PORTAL AUTH URL"
        record = self.read(platform, "tokens")
        if not record:
            return "READY TO CONNECT"
        try:
            data = json.loads(record)
            return "CONNECTED" if float(data.get("expires_at", 0)) > time.time() + 60 else (
                "REFRESH AVAILABLE" if data.get("refresh_token") else "RECONNECT NEEDED")
        except (ValueError, TypeError):
            return "RECONNECT NEEDED"

    def disconnect(self, platform):
        """Forget local tokens. Revocation at the provider is a separate user action."""
        self.clear(platform, "tokens")


def _pkce(verifier, vendor):
    hashed = hashlib.sha256(verifier.encode("ascii")).digest()
    if vendor == "tiktok":
        return hashed.hex()  # TikTok explicitly uses *hex* SHA-256 for desktop.
    return base64.urlsafe_b64encode(hashed).rstrip(b"=").decode("ascii")


def _validate_https_redirect(uri):
    parsed = urlparse(uri)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment or parsed.query:
        raise AuthError("Register a fixed HTTPS callback URI (without query, fragment or credentials)")
    return uri


def _url(base, params):
    return base + "?" + urlencode(params)


def _post_token(endpoint, data, *, json_payload=False, sender=None):
    """Bounded HTTPS POST. Error bodies are intentionally never exposed."""
    if urlparse(endpoint).scheme != "https":
        raise AuthError("Blocked insecure token endpoint")
    body = (json.dumps(data).encode("utf-8") if json_payload else urlencode(data).encode("utf-8"))
    req = Request(endpoint, data=body, method="POST", headers={
        "Content-Type": "application/json" if json_payload else "application/x-www-form-urlencoded",
        "Accept": "application/json", "User-Agent": "APEX-Companion/0.9"})
    try:
        result = sender(req, timeout=20) if sender else urlopen(req, timeout=20)
        with result as response:
            payload = response.read(256_000)
        output = json.loads(payload)
        if not isinstance(output, dict):
            raise ValueError("Invalid response")
        return output
    except (HTTPError, URLError, OSError, ValueError, TimeoutError) as exc:
        raise AuthError(f"Provider token request failed ({type(exc).__name__}); check app approval, redirect URI and permissions") from None


def _get_token_json(endpoint, params, *, sender=None):
    """Read-only HTTPS token exchange used by Instagram long-lived tokens.

    The URL contains provider tokens by API design; never log it or print
    provider HTTP error messages.
    """
    if urlparse(endpoint).scheme != "https":
        raise AuthError("Blocked insecure token refresh endpoint")
    req = Request(_url(endpoint, params), headers={"Accept": "application/json",
                  "User-Agent": "APEX-Companion/0.9"}, method="GET")
    try:
        response = sender(req, timeout=20) if sender else urlopen(req, timeout=20)
        with response as stream:
            value = json.loads(stream.read(256_000))
        if not isinstance(value, dict):
            raise ValueError("Invalid provider token response")
        return value
    except (HTTPError, URLError, OSError, ValueError, TimeoutError):
        raise AuthError("Provider long-lived token request failed; reconnect when necessary") from None


def access_token(platform, vault, *, sender=None, leeway_seconds=120):
    """Return an authenticated token for a user-requested read-only API call.

    Refreshes Google and TikTok tokens if possible. Never exports credentials
    into AI prompts, reports or application logs. Other providers may require
    reconnect when expired, unless their official refresh is supported here.
    """
    if platform not in PLATFORMS:
        raise ValueError("Unknown provider")
    stored = vault.read(platform, "tokens")
    if not stored:
        raise AuthError("Connect the account first")
    try:
        data = json.loads(stored)
        if not isinstance(data.get("access_token"), str) or not data["access_token"]:
            raise ValueError("Missing access token")
        expiry = float(data.get("expires_at", 0))
    except (ValueError, TypeError):
        raise AuthError("Stored session is incomplete; reconnect the account") from None
    if expiry > time.time() + leeway_seconds:
        return data["access_token"]
    refresh = data.get("refresh_token")
    spec = PLATFORMS[platform]
    if spec.vendor == "google" and refresh:
        form = {"client_id": vault.client_id(platform), "grant_type": "refresh_token", "refresh_token": refresh}
        if vault.secret(platform):
            form["client_secret"] = vault.secret(platform)
        result = _post_token(GOOGLE_TOKEN, form, sender=sender)
    elif spec.vendor == "tiktok" and refresh:
        result = _post_token(TIKTOK_TOKEN, {
            "client_key": vault.client_id(platform), "client_secret": vault.secret(platform),
            "grant_type": "refresh_token", "refresh_token": refresh}, sender=sender)
    elif spec.vendor == "instagram" and data.get("long_lived"):
        # Instagram long-lived tokens may be refreshed after 24 hours and
        # before expiration; only try near expiry (this method's trigger).
        result = _get_token_json("https://graph.instagram.com/refresh_access_token", {
            "grant_type": "ig_refresh_token", "access_token": data["access_token"]}, sender=sender)
    else:
        raise AuthError("Provider session expired; reconnect or use the platform's authorization controls")
    token = result.get("access_token")
    if not isinstance(token, str) or not token:
        raise AuthError("Provider refresh did not return an access token")
    try:
        seconds = max(60, min(int(result.get("expires_in", 3600)), 86400*365))
    except (ValueError, TypeError):
        seconds = 3600
    data.update({"access_token": token,
                 "refresh_token": result.get("refresh_token") or data.get("refresh_token") or "",
                 "expires_at": time.time() + seconds})
    vault.save(platform, "tokens", json.dumps(data))
    return token


class OAuthFlow:
    """One authorization attempt. Secrets and state never persist to disk."""

    def __init__(self, platform, vault, *, sender=None):
        if platform not in PLATFORMS:
            raise ValueError("Unknown platform")
        self.platform = platform
        self.spec = PLATFORMS[platform]
        self.vault = vault
        self.sender = sender
        self.state = secrets.token_urlsafe(32)
        self.verifier = secrets.token_urlsafe(56)
        self.created = time.monotonic()
        self.used = False
        self.redirect_uri = None

    def authorize_url(self, redirect_uri=None):
        client_id = self.vault.client_id(self.platform)
        if not client_id:
            raise AuthError("Configure the developer app ID or Google client ID first")
        if self.spec.needs_secret and not self.vault.secret(self.platform):
            raise AuthError("Configure the app secret in Windows Credential Manager first")
        if self.spec.mode == "desktop":
            if redirect_uri is None:
                raise AuthError("Desktop connection requires its local callback listener")
            if urlparse(redirect_uri).hostname != "127.0.0.1" or urlparse(redirect_uri).scheme != "http":
                raise AuthError("Desktop callback must use the local loopback listener")
        else:
            redirect_uri = _validate_https_redirect(redirect_uri or self.vault.read(self.platform, "redirect_uri") or "")
        self.redirect_uri = redirect_uri
        if self.spec.vendor == "google":
            return _url(GOOGLE_AUTH, {
                "client_id": client_id, "response_type": "code", "redirect_uri": redirect_uri,
                "scope": " ".join(self.spec.scope), "access_type": "offline", "prompt": "consent",
                "state": self.state, "code_challenge": _pkce(self.verifier, "google"),
                "code_challenge_method": "S256"})
        if self.spec.vendor == "tiktok":
            return _url(TIKTOK_AUTH, {
                "client_key": client_id, "response_type": "code", "redirect_uri": redirect_uri,
                "scope": ",".join(self.spec.scope), "state": self.state,
                "code_challenge": _pkce(self.verifier, "tiktok"), "code_challenge_method": "S256"})
        if self.spec.vendor == "instagram":
            return _url(IG_AUTH, {
                "client_id": client_id, "response_type": "code", "redirect_uri": redirect_uri,
                "scope": ",".join(self.spec.scope), "state": self.state})
        if self.spec.vendor == "meta":
            return _url(META_AUTH, {
                "client_id": client_id, "response_type": "code", "redirect_uri": redirect_uri,
                "scope": ",".join(self.spec.scope), "state": self.state})
        if self.spec.vendor == "tiktok_business":
            auth_url = self.vault.read(self.platform, "auth_url")
            if not auth_url or urlparse(auth_url).scheme != "https" or urlparse(auth_url).hostname not in (
                    "business-api.tiktok.com", "business.tiktok.com"):
                raise AuthError("Use the advertiser authorization URL from TikTok Business API portal")
            # The portal generates this URL; only append state if it does not already exist.
            parsed = urlparse(auth_url)
            params = parse_qs(parsed.query)
            params["state"] = [self.state]
            return urlunparse(parsed._replace(query=urlencode(params, doseq=True)))
        raise AuthError("Unsupported provider")

    def _verify_callback(self, callback):
        if self.used:
            raise AuthError("Authorization response already processed")
        if time.monotonic() - self.created > AUTH_TIMEOUT:
            raise AuthError("Authorization expired; start again")
        if not self.redirect_uri:
            raise AuthError("Authorization was not started")
        url = urlparse(callback)
        expected = urlparse(self.redirect_uri)
        if (url.scheme, url.netloc, url.path) != (expected.scheme, expected.netloc, expected.path) or url.fragment:
            raise AuthError("OAuth callback does not match the registered redirect URI")
        params = parse_qs(url.query, keep_blank_values=True)
        if len(params.get("state", [])) != 1 or not secrets.compare_digest(params["state"][0], self.state):
            raise AuthError("OAuth state mismatch; authorization rejected")
        if params.get("error"):
            raise AuthError("Account consent denied or interrupted")
        codes = params.get("code", []) or params.get("auth_code", [])
        if len(codes) != 1 or not codes[0]:
            raise AuthError("Provider did not return a valid authorization code")
        self.used = True
        return codes[0], params

    def complete(self, callback):
        code, params = self._verify_callback(callback)
        cid = self.vault.client_id(self.platform)
        secret = self.vault.secret(self.platform)
        if self.spec.vendor == "google":
            data = {"client_id": cid, "code": code, "grant_type": "authorization_code",
                    "redirect_uri": self.redirect_uri, "code_verifier": self.verifier}
            if secret:
                data["client_secret"] = secret
            raw = _post_token(GOOGLE_TOKEN, data, sender=self.sender)
        elif self.spec.vendor == "tiktok":
            raw = _post_token(TIKTOK_TOKEN, {
                "client_key": cid, "client_secret": secret, "code": code,
                "grant_type": "authorization_code", "redirect_uri": self.redirect_uri,
                "code_verifier": self.verifier}, sender=self.sender)
        elif self.spec.vendor == "instagram":
            raw = _post_token(IG_TOKEN, {
                "client_id": cid, "client_secret": secret, "code": code,
                "grant_type": "authorization_code", "redirect_uri": self.redirect_uri}, sender=self.sender)
        elif self.spec.vendor == "meta":
            raw = _post_token(META_TOKEN, {
                "client_id": cid, "client_secret": secret, "code": code,
                "redirect_uri": self.redirect_uri}, sender=self.sender)
        else:
            raw = _post_token(TT_ADS_TOKEN, {
                "app_id": cid, "secret": secret, "auth_code": code},
                json_payload=True, sender=self.sender)
            if isinstance(raw.get("data"), dict):
                raw = raw["data"]
        if not raw.get("access_token") or not isinstance(raw["access_token"], str):
            raise AuthError("No access token returned; verify provider app permissions")
        long_lived = False
        if self.spec.vendor == "instagram":
            # Exchange short-lived token using Instagram's official long-lived
            # endpoint; do not report it as long-lived if the exchange fails.
            try:
                extended = _get_token_json("https://graph.instagram.com/access_token", {
                    "grant_type": "ig_exchange_token", "client_secret": secret,
                    "access_token": raw["access_token"]}, sender=self.sender)
                if isinstance(extended.get("access_token"), str) and extended["access_token"]:
                    raw = {**raw, **extended}
                    long_lived = True
            except AuthError:
                pass
        granted = raw.get("scope") or raw.get("scopes") or ",".join(self.spec.scope)
        expires_in = raw.get("expires_in", 3600 if self.spec.vendor != "tiktok_business" else 86400)
        try:
            expires_in = max(60, min(int(expires_in), 86400 * 365))
        except (TypeError, ValueError):
            expires_in = 3600
        record = {
            "access_token": raw["access_token"],
            "refresh_token": raw.get("refresh_token") or "",
            "expires_at": time.time() + expires_in,
            "scopes": granted,
            "account_ref": raw.get("open_id") or raw.get("user_id") or "",
            "connected_at": datetime.now(timezone.utc).isoformat(),
            "long_lived": long_lived,
        }
        self.vault.save(self.platform, "tokens", json.dumps(record))
        return {"platform": self.platform, "connected": True, "scopes": granted}


def desktop_authorize(platform, vault, *, opener=None, sender=None, timeout=AUTH_TIMEOUT):
    """Local one-shot listener: bind first; browser consent; validate state+path; exchange."""
    if platform not in PLATFORMS or PLATFORMS[platform].mode != "desktop":
        raise AuthError("Only Google and TikTok desktop connections support loopback login")
    bind_port = 8769 if platform == "tiktok" else 0
    flow = OAuthFlow(platform, vault, sender=sender)
    result = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urlparse(self.path)
            if path.path != "/callback":
                self.send_error(404)
                return
            callback_params = parse_qs(path.query)
            valid_state = (len(callback_params.get("state", [])) == 1 and
                secrets.compare_digest(callback_params["state"][0], flow.state))
            if not valid_state:
                self.send_error(400)
                return
            if "callback" not in result:
                result["callback"] = f"http://127.0.0.1:{server.server_port}{self.path}"
            message = b"<html><body>Return to APEX Companion. This window may be closed.</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(message)))
            self.end_headers()
            self.wfile.write(message)

        def log_message(self, *_args):
            return  # NEVER log URL query (contains one-time OAuth code).

    try:
        server = HTTPServer(("127.0.0.1", bind_port), Handler)
    except OSError as exc:
        raise AuthError("Could not bind local OAuth callback port (TikTok uses 8769)") from exc
    try:
        callback_uri = f"http://127.0.0.1:{server.server_port}/callback"
        url = flow.authorize_url(callback_uri)
        open_fn = opener or webbrowser.open
        if not open_fn(url):
            raise AuthError("Browser did not open the login URL")
        server.timeout = 0.5
        deadline = time.monotonic() + min(timeout, AUTH_TIMEOUT)
        while time.monotonic() < deadline and "callback" not in result:
            server.handle_request()
        if "callback" not in result:
            raise AuthError("Login timed out or was cancelled")
        return flow.complete(result["callback"])
    finally:
        server.server_close()


def external_start(platform, vault):
    if platform not in PLATFORMS or PLATFORMS[platform].mode != "external_https":
        raise AuthError("External authorization is only supported for Meta/Instagram/TikTok Ads")
    flow = OAuthFlow(platform, vault)
    return flow, flow.authorize_url()
