"""Offline regression checks for speech recognition -> conversation -> AI handoff.

These tests intentionally do not use a microphone or make paid model calls.
"""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from companion.conversation import ConversationSession, DEFAULT_WAKE_PHRASES
from companion.voice import WakeMicrophone
from main import CompanionApp


class VoiceHandoffTests(unittest.TestCase):
    def make_mic(self):
        mic = WakeMicrophone.__new__(WakeMicrophone)
        mic.phrases = DEFAULT_WAKE_PHRASES
        mic.session = ConversationSession(DEFAULT_WAKE_PHRASES)
        mic.on_wake = Mock()
        mic.on_command = Mock()
        mic.on_sleep = Mock()
        mic.on_transcript = Mock()
        return mic

    def test_background_words_do_not_call_ai(self):
        mic = self.make_mic()
        self.assertEqual(mic.route_recognized("we need to grow the beta"), ("ignore", ""))
        mic.on_command.assert_not_called()
        mic.on_transcript.assert_called_once_with("we need to grow the beta", "ignore")

    def test_wake_then_follow_up_reaches_ai_callback(self):
        mic = self.make_mic()
        self.assertEqual(mic.route_recognized("open apex"), ("wake", ""))
        mic.on_wake.assert_called_once_with(False)
        mic.on_command.assert_not_called()
        self.assertEqual(mic.route_recognized("how do we get beta testers"),
                         ("utterance", "how do we get beta testers"))
        mic.on_command.assert_called_once_with("how do we get beta testers", True)

    def test_wake_plus_question_routes_once(self):
        mic = self.make_mic()
        self.assertEqual(mic.route_recognized("hey a pecks what should we post"),
                         ("utterance", "what should we post"))
        mic.on_wake.assert_called_once_with(True)
        mic.on_command.assert_called_once_with("what should we post", True)

    def test_explicit_talk_without_wake_routes_directly(self):
        mic = self.make_mic()
        mic.session.activate("business")
        self.assertEqual(mic.route_recognized("what did our content achieve"),
                         ("utterance", "what did our content achieve"))
        mic.on_command.assert_called_once_with("what did our content achieve", True)
        self.assertEqual(mic.session.mode, "business")

    def test_sleep_stops_processing_follow_up(self):
        mic = self.make_mic()
        mic.session.activate()
        self.assertEqual(mic.route_recognized("stop listening"), ("sleep", ""))
        mic.on_sleep.assert_called_once()
        self.assertEqual(mic.route_recognized("private background discussion"),
                         ("ignore", ""))
        mic.on_command.assert_not_called()

    def test_recognition_dispatch_reaches_actual_send_ai_branch(self):
        """Check the UI's spoken path, not just the voice state machine."""
        mic = self.make_mic()
        mic.session.activate("business")
        app = CompanionApp.__new__(CompanionApp)
        app.entry = SimpleNamespace(get=lambda: "")
        app.microphone = mic
        app.voice_topic = "business"
        app._chat = Mock()
        app._ask_ai = Mock()
        app._start_conversation = Mock()
        mic.on_command.side_effect = lambda text, speak: app.send(phrase=text, speak=speak)
        mic.route_recognized("what should we improve for marketing")
        app._chat.assert_any_call("YOU", "what should we improve for marketing")
        app._ask_ai.assert_called_once_with("what should we improve for marketing",
                                            deep=False, speak=True,
                                            label="VOICE CONVERSATION", voice_conversation=True)

    def test_local_ai_check_fails_closed_without_paid_call(self):
        app = CompanionApp.__new__(CompanionApp)
        app.brain = SimpleNamespace(_ensure_ready=Mock(side_effect=RuntimeError("OPENAI_API_KEY is not set")))
        app.mini = SimpleNamespace(set_recognition_status=Mock())
        app._chat = Mock()
        self.assertFalse(app.check_ai_configuration())
        app.mini.set_recognition_status.assert_called_once()
        self.assertIn("NOT READY", app.mini.set_recognition_status.call_args.args[0])

    def test_local_ai_check_ready_is_not_a_remote_connection_test(self):
        app = CompanionApp.__new__(CompanionApp)
        app.brain = SimpleNamespace(_ensure_ready=Mock())
        app.mini = SimpleNamespace(set_recognition_status=Mock())
        app._chat = Mock()
        self.assertTrue(app.check_ai_configuration())
        app._chat.assert_called_once()
        self.assertIn("Live connectivity", app._chat.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
