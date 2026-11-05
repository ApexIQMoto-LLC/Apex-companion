import unittest
from companion.settings import DEFAULTS

class PublicConfigTests(unittest.TestCase):
    def test_no_production_cloud_by_default(self):
        self.assertFalse(DEFAULTS['supabase_url'])
        self.assertFalse(DEFAULTS['supabase_publishable_key'])

    def test_sensitive_surfaces_opt_in(self):
        for key in ('camera_autostart', 'microphone_autostart', 'send_aggregates_to_ai', 'autonomous_small_fixes', 'personal_activity_enabled'):
            self.assertFalse(DEFAULTS[key], key)
