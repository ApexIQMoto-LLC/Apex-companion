import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class AutomationTests(unittest.TestCase):
    def test_cron_is_daily_and_gated_on_vault(self):
        sql = (ROOT / 'supabase/migrations/schedule_companion_steam_daily.sql').read_text()
        self.assertIn("'30 9 * * *'", sql)
        self.assertIn("from vault.decrypted_secrets", sql)
        self.assertIn("where name = 'companion_cron_secret_key'", sql)
        self.assertNotIn('sb_secret_', sql)
        self.assertNotIn('service_role_key', sql)
        self.assertIn('"days":2', sql)

    def test_desktop_does_not_store_financial_api_key(self):
        for path in (ROOT / 'config.example.json', ROOT / '.env.example'):
            self.assertNotIn('COMPANION_STEAM_FINANCIAL_KEY=', path.read_text())
        self.assertTrue((ROOT / 'enable_autostart.bat').exists())

if __name__ == '__main__':
    unittest.main()
