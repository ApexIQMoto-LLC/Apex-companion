from datetime import date, datetime, timedelta, timezone
from unittest import TestCase

from companion.dashboard_state import (due, readable_count, cloud_status, steam_status,
                                       marketing_previews, news_previews, local_brief,
                                       bounded_ai_context)
from companion.session_store import CloudSessionStore
from companion.supabase_monitor import SupabaseMonitor


class DashboardTests(TestCase):
    def test_unknown_does_not_fake_zero_metrics(self):
        self.assertEqual(readable_count(None, "Device heartbeats"), "--")
        self.assertEqual(cloud_status(None, False)[0], "SIGN IN NEEDED")
        self.assertEqual(steam_status(None, False)[0], "SIGN IN NEEDED")

    def test_rls_restriction_is_not_zero(self):
        snapshot = {"tables": {"Device heartbeats": {"error": "HTTP 403"}}}
        self.assertEqual(readable_count(snapshot, "Device heartbeats"), "Restricted")

    def test_freshness_warns_about_stale_heartbeats(self):
        self.assertEqual(cloud_status({"device_freshness": "stale >150s"}, True)[0], "HEARTBEAT STALE")

    def test_steam_adds_are_daily_not_total(self):
        steam = {"status": "ok", "latest_date": "2026-11-02",
                 "latest": {"wishlist_adds": 2, "wishlist_deletes": 0}}
        label, summary = steam_status(steam, True)
        self.assertEqual(label, "REPORT AVAILABLE")
        self.assertIn("not total", summary)

    def test_marketing_without_live_research_has_standing_ideas(self):
        rows = marketing_previews(None)
        self.assertTrue(all(x["kind"] == "STANDING IDEA" for x in rows))
        self.assertTrue(all(not x["url"] for x in rows))

    def test_news_bad_links_filtered(self):
        items = news_previews([("topic", [{"title": "bad", "url": "javascript:alert(1)"},
                                          {"title": "good", "url": "https://example.com"}])])
        self.assertEqual(len(items), 1)

    def test_brief_without_login_does_not_claim_live_server(self):
        text = local_brief(None, None, None, None, False)
        self.assertIn("SIGN IN NEEDED", text)
        self.assertNotIn("+2", text)

    def test_ai_context_whitelist(self):
        data = {"device_freshness": "stale >150s", "tables": {"Device heartbeats":
                {"visible_count": 4, "latest": {"private_email": "tester1@example.com"}}}}
        text = bounded_ai_context(data, None, None, None, True)
        self.assertIn("4", text)
        self.assertNotIn("tester1@example.com", text)

    def test_scheduler_due(self):
        now = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)
        self.assertTrue(due(None, 5, now))
        self.assertFalse(due(now-timedelta(minutes=4), 5, now))
        self.assertTrue(due(now-timedelta(minutes=6), 5, now))

    def test_secret_key_rejected_for_desktop(self):
        with self.assertRaises(ValueError):
            SupabaseMonitor("https://foo.supabase.co", "sb_secret_password")

    def test_keyring_is_not_plaintext_file_store(self):
        self.assertFalse(hasattr(CloudSessionStore(), "file_path"))


if __name__ == "__main__":
    import unittest
    unittest.main()
