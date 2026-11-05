"""Purely offline tests of continuous voice, prompt budgets, and local TTS selection."""
import unittest
import time
from unittest.mock import Mock, patch
from types import SimpleNamespace
from array import array

from companion.voice_processing import PauseAwareTurn, VoiceConfidenceFilter, SpeechGate
from companion.assistant import CompanionBrain, rate_limit_delay_seconds, VOICE_SYSTEM


class TurnAssemblyTests(unittest.TestCase):
    def test_collects_clause_after_short_pause(self):
        clock = [0.0]
        turn = PauseAwareTurn(pause_seconds=2.1, clock=lambda:clock[0])
        turn.mark_voice(350)
        turn.add_final('i want to show the camera')
        clock[0] = 1.4
        self.assertFalse(turn.due())
        turn.mark_voice(600)
        turn.add_final('and then quick cuts of the product')
        clock[0] = 3.0
        self.assertFalse(turn.due())
        clock[0] = 3.7
        self.assertTrue(turn.due())
        self.assertEqual(turn.finish(), 'i want to show the camera and then quick cuts of the product')

    def test_noise_utterance_filtered_by_voiced_duration(self):
        turn = PauseAwareTurn(pause_seconds=1.5, min_voice_ms=150)
        turn.mark_voice(30, now=0)
        turn.add_final('you')
        self.assertEqual(turn.finish(), '')

    def test_reject_common_transcription_artifacts(self):
        self.assertFalse(VoiceConfidenceFilter.should_route('thank you', True))
        self.assertFalse(VoiceConfidenceFilter.should_route('uh', True))
        self.assertTrue(VoiceConfidenceFilter.should_route('yes', True))
        self.assertTrue(VoiceConfidenceFilter.should_route('help with an Instagram intro', True))

    def test_silence_is_not_speech(self):
        gate = SpeechGate(16000)
        self.assertEqual(gate.process(b'\x00\x00' * 960), 0.0)


class NaturalSpeechTests(unittest.TestCase):
    def test_rate_reset_parse(self):
        self.assertEqual(rate_limit_delay_seconds('Please try again in 1h52m1'), 6723)
        self.assertEqual(rate_limit_delay_seconds('429 error', '45'),45)
        self.assertEqual(rate_limit_delay_seconds('429 error','bad'),120)

    def test_voice_system_has_user_context(self):
        self.assertIn('Replay Studio', VOICE_SYSTEM)
        self.assertLess(len(VOICE_SYSTEM), 950)

    def test_voice_chat_does_not_transmit_full_notes_or_dashboard(self):
        ledger = SimpleNamespace(month_total=lambda:0, today_count=lambda:0)
        settings = {'max_context_turns':6,'chat_model':'gpt-6-luna','deep_model':'gpt-6-luna',
                    'max_output_tokens':1000,'enable_local_memory':False}
        brain = CompanionBrain(settings, ledger)
        brain._ensure_ready = lambda: None
        calls = []
        fake = SimpleNamespace(status='completed',output_text='Try opening with your bike on a mountain road.',
                               usage=None,output=[])
        brain._client = SimpleNamespace(responses=SimpleNamespace(create=lambda **kw:(calls.append(kw),fake)[1]))
        answer,*_ = brain.ask('I want a short Instagram reel', voice_mode='business',
                              include_notes=False, context='', limit_output_tokens=420)
        self.assertIn('mountain road',answer)
        request = calls[0]
        self.assertLess(len(request['instructions']),2200)
        self.assertEqual(request['max_output_tokens'],420)
        self.assertNotIn('AUTHORIZED DASHBOARD DATA',request['instructions'])
        self.assertNotIn('OWNER\'S LOCAL NOTES',request['instructions'])

    def test_rate_block_prevents_repeat_api_attempt(self):
        ledger = SimpleNamespace(month_total=lambda:0, today_count=lambda:0)
        settings={'max_context_turns':6,'monthly_budget_usd':15,'daily_request_limit':50}
        brain=CompanionBrain(settings, ledger)
        brain._rate_block_until=time.monotonic()+80
        with self.assertRaisesRegex(RuntimeError,'cooling down'):
            brain._ensure_ready()

if __name__ == '__main__':
    unittest.main()
