import tempfile
import unittest
from pathlib import Path
from companion.costs import SpendLedger, estimate_text_cost
from companion.voice import find_wake_phrase


class CoreTests(unittest.TestCase):
    def test_luna_pricing(self):
        self.assertAlmostEqual(estimate_text_cost("gpt-6-luna", 3000, 600), 0.0006)

    def test_terra_pricing(self):
        self.assertAlmostEqual(estimate_text_cost("gpt-6.1-terra", 3000, 600), 0.006)

    def test_wake_phrase(self):
        self.assertEqual(find_wake_phrase("hey apex tell me the news", ["hey apex"]), (True, "tell me the news"))
        self.assertEqual(find_wake_phrase("something else", ["hey apex"]), (False, ""))

    def test_ledger(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = SpendLedger(Path(folder) / "cost.sqlite3")
            self.assertEqual(ledger.month_total(), 0.0)
            ledger.record("gpt-6-luna", 3000, 600)
            self.assertAlmostEqual(ledger.month_total(), 0.0006)
            self.assertEqual(ledger.today_count(), 1)


if __name__ == "__main__":
    unittest.main()
