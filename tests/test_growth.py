import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from companion.marketing import scan, render_report, save_report, rank_item, STREAMS
from companion.steamworks import APP_ID, summarize_daily, render_summary
from companion.supabase_monitor import freshness, parse_total


def row(d, adds=3, deletes=1, purchases=0, gifts=0):
    return {"report_date": d.isoformat(), "app_id": APP_ID,
            "wishlist_adds": adds, "wishlist_deletes": deletes,
            "wishlist_purchases": purchases, "wishlist_gifts": gifts}


class SteamGrowthTests(unittest.TestCase):
    def test_not_connected_is_not_zero(self):
        result = summarize_daily([], today=date(2026, 11, 4))
        self.assertEqual(result["status"], "not_synced")
        self.assertNotIn("last7_adds", result)
        self.assertIn("No synchronized", render_summary(result))

    def test_latest_and_seven_days(self):
        today = date(2026, 11, 4)
        rows = [row(today - timedelta(days=age), adds=age) for age in range(1, 8)]
        result = summarize_daily(rows, today=today)
        self.assertEqual(result["latest_date"], "2026-11-03")
        self.assertEqual(result["last7_adds"], 28)
        self.assertEqual(result["last7_coverage_days"], 7)
        self.assertIsNone(result["week_over_week_adds_change"])
        self.assertIn("Daily activity", render_summary(result))

    def test_full_week_comparison(self):
        today = date(2026, 11, 4)
        rows = [row(today - timedelta(days=age), adds=4 if age <= 7 else 2)
                for age in range(1, 15)]
        result = summarize_daily(rows, today=today)
        self.assertEqual(result["week_over_week_adds_change"], 14)

    def test_missing_day_not_assumed_zero(self):
        today = date(2026, 11, 4)
        rows = [row(today - timedelta(days=age)) for age in range(1, 15) if age != 2]
        result = summarize_daily(rows, today=today)
        self.assertEqual(result["last7_coverage_days"], 6)
        self.assertIsNone(result["week_over_week_adds_change"])

    def test_reject_wrong_app_negative_invalid_future(self):
        today = date(2026, 11, 4)
        bad = [dict(row(today - timedelta(days=1)), app_id=9999),
               row(today - timedelta(days=1), adds=-4),
               row(today + timedelta(days=1)),
               {"app_id": APP_ID, "report_date": "bad", "wishlist_adds": 4}]
        self.assertEqual(summarize_daily(bad, today=today)["status"], "not_synced")


class PublicMarketingTests(unittest.TestCase):
    def test_scan_writes_ranked_links_and_is_not_verified(self):
        def fake_feed(query, limit=4, days=7):
            return [{"title": "Motorcycle creator track-day demo event",
                     "url": "https://example.com/news", "published": "2026-11-04T00:00:00+00:00"}]
        report = scan(fetcher=fake_feed, per_stream=4)
        self.assertEqual(len(report["opportunities"]), 1)
        self.assertEqual(report["opportunities"][0]["status"], "UNVERIFIED_RESEARCH_LEAD")
        self.assertIn("SOURCE:", render_report(report))
        with tempfile.TemporaryDirectory() as td:
            path = save_report(report, Path(td))
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["opportunities"][0]["status"], "UNVERIFIED_RESEARCH_LEAD")
            self.assertTrue((Path(td) / "latest.md").exists())

    def test_bad_links_rejected(self):
        def fake_feed(query, limit=4, days=7):
            return [{"title": "Something", "url": "http://insecure.test"},
                    {"title": "Something else", "url": ""}]
        self.assertEqual(scan(fetcher=fake_feed)["opportunities"], [])

    def test_rank_item_is_number(self):
        self.assertIsInstance(rank_item(STREAMS[0], {"title": "motorcycle retail event", "published": ""}), int)


class HealthTests(unittest.TestCase):
    def test_content_range(self):
        self.assertEqual(parse_total("0-0/263"), 263)
        self.assertIsNone(parse_total("0-0/*"))

    def test_freshness_missing_is_unknown(self):
        self.assertEqual(freshness(None), "unknown")


if __name__ == "__main__":
    unittest.main()
