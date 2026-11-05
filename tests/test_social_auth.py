"""All OAuth tests are offline: never call real providers or use actual credentials."""
import io
import json
import secrets
import threading
import time
import unittest
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import urlopen

from companion.social_auth import (
    PLATFORMS, AuthError, OAuthFlow, WindowsVault, _pkce, _post_token,
    desktop_authorize, access_token, TIKTOK_CALLBACK,
)


class MemoryKeyring:
    def __init__(self):
        self.values = {}
    def get_password(self, service, account):
        return self.values.get((service, account))
    def set_password(self, service, account, value):
        self.values[service, account] = value
    def delete_password(self, service, account):
        self.values.pop((service, account), None)


class MockResponse(io.BytesIO):
    def __init__(self, payload):
        super().__init__(json.dumps(payload).encode())


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.keyring = MemoryKeyring()
        self.vault = WindowsVault(self.keyring)

    def config(self, platform):
        self.vault.set_client_id(platform, "example-client-id")
        self.vault.set_secret(platform, "example-secret")
        if PLATFORMS[platform].mode == "external_https":
            self.vault.save(platform, "redirect_uri", "https://apexiqmoto.com/oauth/companion/callback")
        if platform == "tiktok_ads":
            self.vault.save(platform, "auth_url", "https://business-api.tiktok.com/portal/oauth?partner=123")

    def test_all_seven_platforms_configurable(self):
        self.assertEqual(len(PLATFORMS), 7)
        for platform in PLATFORMS:
            self.config(platform)
            with self.subTest(platform=platform):
                self.assertEqual(self.vault.status(platform), "READY TO CONNECT")
                self.assertEqual(self.vault.client_id(platform), "example-client-id")

    def test_google_three_share_one_client(self):
        self.vault.set_client_id("youtube", "one-google-client")
        self.assertEqual(self.vault.client_id("ga4"), "one-google-client")
        self.assertEqual(self.vault.client_id("google_ads"), "one-google-client")
        self.vault.save("youtube", "tokens", '{"access_token":"a"}')
        self.assertIsNone(self.vault.read("ga4", "tokens"))

    def test_pkce_hex_tiktok_vs_base64_google(self):
        self.assertEqual(len(_pkce("abc" * 15, "tiktok")), 64)
        self.assertEqual(len(_pkce("abc" * 15, "google")), 43)
        self.assertNotEqual(_pkce("abc" * 15, "tiktok"), _pkce("abc" * 15, "google"))

    def test_auth_urls_default_read_scopes(self):
        for platform in ("youtube", "ga4", "google_ads", "tiktok"):
            self.config(platform)
            redirect = TIKTOK_CALLBACK if platform == "tiktok" else "http://127.0.0.1:12345/callback"
            flow = OAuthFlow(platform, self.vault)
            params = parse_qs(urlparse(flow.authorize_url(redirect)).query)
            self.assertEqual(params["state"], [flow.state])
            self.assertEqual(params["response_type"], ["code"])
            self.assertEqual(params["code_challenge_method"], ["S256"])
            self.assertNotIn("client_secret", params)
            self.assertNotIn("ads_management", str(params))

    def test_external_require_https(self):
        self.config("instagram")
        self.vault.save("instagram", "redirect_uri", "http://apexiqmoto.com/callback")
        with self.assertRaises(AuthError):
            OAuthFlow("instagram", self.vault).authorize_url()
        self.vault.save("instagram", "redirect_uri", "https://apexiqmoto.com/callback?x=1")
        with self.assertRaises(AuthError):
            OAuthFlow("instagram", self.vault).authorize_url()

    def test_fail_closed_state_replay_and_path(self):
        self.config("instagram")
        flow = OAuthFlow("instagram", self.vault)
        flow.authorize_url()
        base = self.vault.read("instagram", "redirect_uri")
        with self.assertRaises(AuthError):
            flow.complete(base + "?state=incorrect&code=sensitive")
        with self.assertRaises(AuthError):
            flow.complete("https://example.org/?state=" + flow.state + "&code=x")
        with self.assertRaises(AuthError):
            flow.complete(base + "?error=access_denied&state=" + flow.state)
        self.assertIsNone(self.vault.read("instagram", "tokens"))

    def test_success_one_use_token_not_in_public_fields(self):
        self.config("instagram")
        flow = OAuthFlow("instagram", self.vault,
            sender=lambda req, timeout: MockResponse({"access_token":"ACCESS_SENSITIVE", "expires_in":3600}))
        flow.authorize_url()
        callback = flow.redirect_uri + "?" + urlencode({"state":flow.state,"code":"ONE_TIME"})
        result = flow.complete(callback)
        self.assertEqual(result["connected"], True)
        self.assertNotIn("ACCESS_SENSITIVE", str(result))
        self.assertEqual(self.vault.status("instagram"), "CONNECTED")
        with self.assertRaises(AuthError):
            flow.complete(callback)
        self.vault.disconnect("instagram")
        self.assertEqual(self.vault.status("instagram"), "READY TO CONNECT")

    def test_expired_state(self):
        self.config("youtube")
        flow = OAuthFlow("youtube", self.vault)
        flow.authorize_url("http://127.0.0.1:7777/callback")
        flow.created -= 300
        with self.assertRaises(AuthError):
            flow.complete(flow.redirect_uri + "?state=" + flow.state + "&code=one")

    def test_no_http_token_post_and_no_provider_body_leaks(self):
        with self.assertRaises(AuthError):
            _post_token("http://localhost:3333/token", {"client_secret":"SECRET"})
        self.assertNotIn("SECRET", str(AuthError("failed")))

    def test_desktop_local_callback_google(self):
        self.config("youtube")
        captured = []
        def opener(url):
            captured.append(url)
            params = parse_qs(urlparse(url).query)
            redirect = params["redirect_uri"][0]
            def callback():
                target = redirect + "?" + urlencode({"state": params["state"][0], "code": "fake-auth-code"})
                with urlopen(target, timeout=5) as resp:
                    self.assertEqual(resp.status, 200)
            threading.Thread(target=callback, daemon=True).start()
            return True
        calls=[]
        def sender(req, timeout):
            calls.append((req.full_url, req.data))
            return MockResponse({"access_token":"ACCESS_TOKEN", "refresh_token":"REFRESH_TOKEN", "expires_in":3600})
        result=desktop_authorize("youtube", self.vault, opener=opener, sender=sender, timeout=5)
        self.assertTrue(result["connected"])
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0][0], "https://oauth2.googleapis.com/token")
        self.assertIn(b"code_verifier=", calls[0][1])
        self.assertIn("CONNECTED", self.vault.status("youtube"))

    def test_tiktok_hex_pkce_auth(self):
        self.config("tiktok")
        flow=OAuthFlow("tiktok",self.vault)
        params=parse_qs(urlparse(flow.authorize_url(TIKTOK_CALLBACK)).query)
        self.assertEqual(params["scope"][0], "user.info.basic,video.list")
        self.assertEqual(params["code_challenge"][0], _pkce(flow.verifier, "tiktok"))

    def test_google_token_refresh_maintains_refresh_token(self):
        self.config("youtube")
        self.vault.save("youtube", "tokens", json.dumps({
            "access_token": "expired", "refresh_token": "original-refresh", "expires_at": 1, "scopes": "readonly"}))
        calls = []
        def sender(req, timeout):
            calls.append(req.data)
            return MockResponse({"access_token": "renewed-access", "expires_in": 3600})
        token = access_token("youtube", self.vault, sender=sender)
        self.assertEqual(token, "renewed-access")
        self.assertIn(b"grant_type=refresh_token", calls[0])
        self.assertEqual(json.loads(self.vault.read("youtube", "tokens"))["refresh_token"], "original-refresh")

    def test_expired_without_refresh_denied(self):
        self.config("meta_ads")
        self.vault.save("meta_ads", "tokens", json.dumps({
            "access_token": "expired", "expires_at": 1}))
        with self.assertRaises(AuthError):
            access_token("meta_ads", self.vault)

    def test_tiktok_refresh_uses_correct_client_keys(self):
        self.config("tiktok")
        self.vault.save("tiktok", "tokens", json.dumps({
            "access_token": "expired", "refresh_token": "refresh", "expires_at": 1}))
        sent=[]
        def sender(req, timeout):
            sent.append(req.data)
            return MockResponse({"access_token":"newtoken", "refresh_token":"rotated", "expires_in":900})
        self.assertEqual(access_token("tiktok", self.vault, sender=sender), "newtoken")
        self.assertIn(b"client_key=", sent[0])
        self.assertIn(b"grant_type=refresh_token", sent[0])

    def test_external_tiktok_ads_requires_portal_url(self):
        self.config("tiktok_ads")
        flow=OAuthFlow("tiktok_ads", self.vault)
        url=flow.authorize_url()
        self.assertEqual(parse_qs(urlparse(url).query)["state"], [flow.state])
        self.assertIn("business-api.tiktok.com", url)

    def test_no_secrets_in_app_config(self):
        self.config("youtube")
        from companion.settings import DEFAULTS
        self.assertNotIn("example-secret", str(DEFAULTS))
        self.assertNotIn("example-client-id", str(DEFAULTS))


if __name__ == "__main__":
    unittest.main()
