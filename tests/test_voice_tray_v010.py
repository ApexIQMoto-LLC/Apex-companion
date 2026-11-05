"""Pure session and lightweight UI checks for APEX 0.10 voice-first update."""
import unittest

from companion.conversation import (
    ConversationSession, DEFAULT_WAKE_PHRASES,
    normalized_words, wake_remainder, opening_question, conversational_instructions,
)
from companion.settings import DEFAULTS


class FakeClock:
    def __init__(self):
        self.now = 1000
    def __call__(self):
        return self.now


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.clock=FakeClock()
        self.session=ConversationSession(DEFAULT_WAKE_PHRASES, idle_seconds=120, clock=self.clock)

    def test_new_wake_phrases(self):
        for text in ("Apex", "Open Apex", "Start Apex", "APEX OPEN APEX", "Hey Apex", "Hey Jarvis"):
            self.assertEqual(wake_remainder(text)[0], True, text)

    def test_wake_and_command_combination(self):
        self.assertEqual(wake_remainder("Apex open Apex how is the beta looking"),
                         (True, "how is the beta looking"))
        self.assertEqual(wake_remainder("hey apex what's new"), (True,"what's new"))

    def test_wake_only_no_paid_question(self):
        self.assertEqual(self.session.accept("Start Apex"),("wake",""))
        self.assertTrue(self.session.active)

    def test_follow_up_no_wake_word(self):
        self.session.accept("Hey Apex")
        self.assertEqual(self.session.accept("Let's focus on beta riders"),
                         ("utterance", "let's focus on beta riders"))

    def test_timer_extends_on_each_turn(self):
        self.session.accept("Apex")
        self.clock.now += 90
        self.session.accept("Tell me about marketing")
        self.clock.now += 90
        self.assertTrue(self.session.active)
        self.assertEqual(self.session.accept("What about creators")[0],"utterance")

    def test_expiry_requires_new_wake(self):
        self.session.accept("Apex")
        self.clock.now += 121
        self.assertFalse(self.session.active)
        self.assertEqual(self.session.accept("what's my status"),("ignore",""))
        self.assertEqual(self.session.accept("apex"),("wake",""))

    def test_stop_listening_exits_session(self):
        self.session.accept("Apex")
        self.assertEqual(self.session.accept("stop listening"),("sleep",""))
        self.assertFalse(self.session.active)

    def test_direct_sleep_without_session_is_ignored(self):
        self.assertEqual(self.session.accept("go to sleep"),("ignore",""))

    def test_no_false_wake_for_apexiq_product_name(self):
        self.assertEqual(wake_remainder("ApexIQ Moto"),(False,""))
        self.assertEqual(wake_remainder("The apex of the mountain"),(False,""))

    def test_never_invokes_ai_from_state_machine(self):
        self.assertEqual(self.session.accept("What's the current paid ad spend"),("ignore",""))

    def test_question_modes(self):
        self.assertIn("beta riders",opening_question("business"))
        self.assertIn("goals",opening_question("personal"))
        self.assertIn("follow-up",conversational_instructions("business"))

    def test_config_maintains_hard_limits(self):
        self.assertTrue(DEFAULTS["launch_minimized_to_tray"])
        self.assertFalse(DEFAULTS["marketing_auto_publish"])
        self.assertFalse(DEFAULTS["marketing_auto_spend"])
        self.assertFalse(DEFAULTS["marketing_auto_outreach"])
        self.assertFalse(DEFAULTS["auto_paid_ai_daily"])


if __name__ == "__main__":
    unittest.main()
