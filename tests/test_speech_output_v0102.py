"""Offline tests for APEX's Windows speech output repair."""
import base64
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from companion.speech_output import build_windows_speech_command, WindowsSpeech
from companion.voice import LocalSpeaker
from companion.settings import DEFAULTS


class SpeechOutputTests(unittest.TestCase):
    def test_windows_command_does_not_interpolate_user_text_as_code(self):
        malicious = "I'm Apex'; Remove-Item -Recurse C:\\Things; #"
        argv = build_windows_speech_command(malicious, volume=88)
        self.assertEqual(argv[:3], ["powershell.exe", "-NoProfile", "-NonInteractive"])
        script = base64.b64decode(argv[-1]).decode("utf-16le")
        self.assertNotIn("Remove-Item", script)
        self.assertIn("$s.Volume=88", script)
        self.assertIn("$s.SetOutputToDefaultAudioDevice()", script)
        embedded = script.split("FromBase64String('")[1].split("')")[0]
        self.assertEqual(base64.b64decode(embedded).decode("utf-8"), malicious)

    def test_volume_and_rate_clamped(self):
        script = base64.b64decode(build_windows_speech_command("Hi", volume=300, rate=-90)[-1]).decode("utf-16le")
        self.assertIn("$s.Volume=100", script)
        self.assertIn("$s.Rate=-10", script)

    def test_windows_speech_process_success(self):
        child = MagicMock()
        child.communicate.return_value = (b"", b"")
        child.returncode = 0
        child.poll.return_value = 0
        with patch("companion.speech_output.os", SimpleNamespace(name="nt")), \
             patch("companion.speech_output.subprocess.Popen", return_value=child) as popen:
            ws = WindowsSpeech(volume=80)
            ws.speak("Hello")
            self.assertIsNone(ws.process)
            self.assertEqual(popen.call_args.args[0][0], "powershell.exe")

    def test_windows_speech_reports_failure(self):
        child = MagicMock()
        child.communicate.return_value = (b"", b"No output device")
        child.returncode = 1
        with patch("companion.speech_output.os", SimpleNamespace(name="nt")), \
             patch("companion.speech_output.subprocess.Popen", return_value=child):
            with self.assertRaisesRegex(RuntimeError, "No output device"):
                WindowsSpeech().speak("Hello")

    def test_fallback_from_windows_to_legacy_speaker(self):
        notices = []
        speaker = LocalSpeaker.__new__(LocalSpeaker)
        speaker.backend = "windows"
        speaker.windows = SimpleNamespace(speak=MagicMock(side_effect=RuntimeError("no voice")))
        speaker._speak_pyttsx = MagicMock()
        speaker.status_callback = notices.append
        speaker.available = None
        import threading
        speaker.cancelled = threading.Event()
        speaker._speak_one("Hello")
        speaker._speak_pyttsx.assert_called_once_with("Hello")
        self.assertTrue(speaker.available)
        self.assertTrue(any("fallback" in x.lower() for x in notices))

    def test_both_backends_fail_and_report_reason(self):
        notices = []
        speaker = LocalSpeaker.__new__(LocalSpeaker)
        speaker.backend = "windows"
        speaker.windows = SimpleNamespace(speak=MagicMock(side_effect=RuntimeError("no voice")))
        speaker._speak_pyttsx = MagicMock(side_effect=RuntimeError("no pyttsx"))
        speaker.status_callback = notices.append
        speaker.available = None
        import threading
        speaker.cancelled = threading.Event()
        speaker._speak_one("Hello")
        self.assertFalse(speaker.available)
        self.assertTrue(any("Speech output error" in x for x in notices))

    def test_default_is_local_windows_speaker(self):
        self.assertEqual(DEFAULTS["speech_output_backend"], "windows")
        self.assertEqual(DEFAULTS["speech_output_volume"], 100)
        self.assertFalse(DEFAULTS["marketing_auto_spend"])


if __name__ == "__main__":
    unittest.main()
