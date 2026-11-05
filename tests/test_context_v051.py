from datetime import datetime, timezone
from unittest import TestCase

from companion.ai_context import gather_dashboard_context
from companion.dashboard_state import bounded_ai_context
from companion.settings import DEFAULTS


class FakeCloud:
    def __init__(self):
        self.calls = 0

    def snapshot(self):
        self.calls += 1
        return {"checked_at_utc": "2026-11-04T12:00:00+00:00", "device_freshness": "stale >150s",
                "tables": {"Device heartbeats": {"visible_count": 1, "latest": {
                    "last_seen_at": "2026-11-03T20:11:00Z", "gps_status": "ready",
                    "latitude": 99.111, "email": "tester1@example.com", "secret": "NEVER_EXPOSE"}},
                    "Ride uploads": {"visible_count": 10, "latest": {"received_at": "2026-11-01"}},
                    "Beta applications": {"error": "HTTP 403"}}}


class FakeSteamReader:
    def __init__(self, monitor):
        self.monitor = monitor

    def fetch(self, days):
        self.monitor.steam_calls = getattr(self.monitor, 'steam_calls', 0) + 1
        return {"status": "ok", "latest_date": "2026-11-02",
                "latest": {"wishlist_adds": 2, "wishlist_deletes": 0,
                           "wishlist_purchases": 0, "wishlist_gifts": 0},
                "last7_adds": 2, "last7_coverage_days": 1}


class BrokenCloud(FakeCloud):
    def snapshot(self):
        raise RuntimeError('server error containing credential xyz')


class AIContextTests(TestCase):
    def test_new_install_defaults_to_context_off_for_public_release(self):
        self.assertFalse(DEFAULTS['send_aggregates_to_ai'])

    def test_refreshes_missing_metrics_before_prompt(self):
        monitor = FakeCloud()
        ctx, cloud, steam, refreshed, errors = gather_dashboard_context(
            monitor=monitor, cloud_cached=None, steam_cached=None,
            marketing=None, news=None, signed_in=True,
            steam_reader_factory=FakeSteamReader)
        self.assertEqual(refreshed, frozenset({'cloud', 'steam'}))
        self.assertEqual(monitor.calls, 1)
        self.assertEqual(monitor.steam_calls, 1)
        self.assertIn('wishlist_adds: 2', ctx)
        self.assertIn('2026-11-02', ctx)
        self.assertIn('stale >150s', ctx)
        self.assertIn('Restricted', ctx)
        self.assertNotIn('tester1@example.com', ctx)
        self.assertNotIn('99.111', ctx)
        self.assertNotIn('NEVER_EXPOSE', ctx)
        self.assertFalse(errors)

    def test_uses_fresh_cache_without_duplicate_network_calls(self):
        monitor = FakeCloud()
        cached = {'checked_at_utc': '2026-11-04T12:00:00Z', 'device_freshness': 'unknown', 'tables': {}}
        existing_steam = {'status': 'ok', 'latest': {'wishlist_adds': 3}, 'latest_date': '2026-11-03'}
        now = datetime.now(timezone.utc)
        ctx, _, _, refreshed, errors = gather_dashboard_context(
            monitor=monitor, cloud_cached=cached, steam_cached=existing_steam,
            marketing=None, news=None, signed_in=True,
            cloud_last=now, steam_last=now, steam_reader_factory=FakeSteamReader)
        self.assertEqual(monitor.calls, 0)
        self.assertEqual(refreshed, frozenset())
        self.assertIn('wishlist_adds: 3', ctx)
        self.assertFalse(errors)

    def test_refresh_failure_does_not_dump_sensitive_exception(self):
        monitor = BrokenCloud()
        ctx, _, _, refreshed, errors = gather_dashboard_context(
            monitor=monitor, cloud_cached=None, steam_cached=None,
            marketing=None, news=None, signed_in=True,
            steam_reader_factory=FakeSteamReader)
        self.assertIn('A.R.I.S Cloud refresh failed (RuntimeError)', ctx)
        self.assertNotIn('credential xyz', ctx)
        self.assertNotIn('gmail', ctx)
        self.assertIn('Steamworks report', ctx)
        self.assertTrue(errors)

    def test_no_auth_never_uses_private_cached_report(self):
        ctx = bounded_ai_context({'device_freshness': 'live <=60s'},
              {'status': 'ok', 'latest': {'wishlist_adds': 999}, 'latest_date':'2026-11-02'},
              None, None, False)
        self.assertNotIn('999', ctx)
        self.assertIn('not authenticated', ctx)

class BrainPromptTests(TestCase):
    def test_ai_request_attaches_authorized_context_to_provider_instructions(self):
        import os
        import sys
        import types
        from unittest.mock import patch
        from companion.assistant import CompanionBrain
        from companion.settings import DEFAULTS
        class Ledger:
            def month_total(self): return 0
            def today_count(self): return 0
            def record(self, model, incoming, outgoing): return 0.001
        captured = {}
        class ResponseAPI:
            def create(self, **kw):
                captured.update(kw)
                return types.SimpleNamespace(output_text='Context received',
                    usage=types.SimpleNamespace(input_tokens=100, output_tokens=20))
        class Client:
            def __init__(self, **kw):
                self.responses = ResponseAPI()
        with patch.dict(os.environ, {'OPENAI_API_KEY':'unit-test-key'}), \
             patch.dict(sys.modules, {'openai': types.SimpleNamespace(OpenAI=Client)}):
            brain = CompanionBrain(DEFAULTS, Ledger())
            text, _, _ = brain.ask('Give me my Steam report',
                    context='Steam reporting date 2026-11-02; wishlist_adds: 2')
        self.assertEqual(text, 'Context received')
        self.assertIn('wishlist_adds: 2', captured['instructions'])
        self.assertIn('historical', captured['instructions'].lower())
        self.assertEqual(captured['input'][-1]['role'], 'user')
        self.assertNotIn('unit-test-key', captured['instructions'])

class UpgradeSafetyTests(TestCase):
    def test_updater_preserves_existing_keys_user_files_and_environment(self):
        from pathlib import Path
        p=Path(__file__).resolve().parents[1] / 'Update_Existing_Install.cmd'
        s=p.read_text(encoding='utf-8')
        self.assertIn('robocopy', s.lower())
        self.assertIn('/XF .env config.json', s)
        self.assertIn('/XD .venv data', s)
        self.assertIn('choice /M', s)
