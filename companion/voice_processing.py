"""Local-only, conservative speech gating and pause-aware turn assembly.

The VAD is not speaker identification. A dog bark or television can still be
classified as speech; use push-to-talk in noisy surroundings when necessary.
"""
from __future__ import annotations

from collections import deque
import math
import time
from array import array


class SpeechGate:
    """Evaluate 30ms PCM frames with WebRTC VAD; conservative energy fallback.

    Returns voiced milliseconds (not a transcript). No audio is saved to disk.
    """
    def __init__(self, rate: int, mode: int = 3):
        self.rate = int(rate)
        self.mode = max(0, min(3, int(mode)))
        self.remainder = b""
        self.frame_bytes = self.rate * 30 // 1000 * 2
        self.engine = None
        if self.rate in (8000, 16000, 32000, 48000):
            try:
                import webrtcvad
                self.engine = webrtcvad.Vad(self.mode)
            except ImportError:
                pass

    @property
    def neural(self):
        return self.engine is not None

    def process(self, data: bytes) -> float:
        if not self.frame_bytes:
            return 0.0
        self.remainder += data
        voiced_ms = 0.0
        while len(self.remainder) >= self.frame_bytes:
            frame, self.remainder = self.remainder[:self.frame_bytes], self.remainder[self.frame_bytes:]
            if self.engine is not None:
                try:
                    voiced = bool(self.engine.is_speech(frame, self.rate))
                except Exception:
                    voiced = False
            else:
                samples = array('h')
                samples.frombytes(frame)
                if not samples:
                    continue
                # Energy fallback is only a weak filter. Normal speech VAD
                # is installed by the normal update dependencies.
                rms = math.sqrt(sum(x*x for x in samples[::4]) / len(samples[::4]))
                voiced = rms >= 450
            if voiced:
                voiced_ms += 30.0
        return voiced_ms


class PauseAwareTurn:
    """Accumulate recognizer finals across natural pauses before dispatch.

    `mark_voice` accepts VAD-labelled voiced frame durations. `add_final`
    does not immediately dispatch, allowing multi-clause sentences.
    """
    def __init__(self, pause_seconds=1.65, min_voice_ms=150, clock=None):
        self.pause_seconds = max(0.75, min(4.0, float(pause_seconds)))
        self.min_voice_ms = max(60, min(900, int(min_voice_ms)))
        self.clock = clock or time.monotonic
        self.reset()

    def reset(self):
        self.parts = []
        self.last_voice_at = None
        self.first_voice_at = None
        self.voiced_ms = 0.0

    def mark_voice(self, voiced_ms, now=None):
        if voiced_ms <= 0:
            return
        now = self.clock() if now is None else now
        if self.first_voice_at is None:
            self.first_voice_at = now
        self.last_voice_at = now
        self.voiced_ms = min(30000.0, self.voiced_ms + float(voiced_ms))

    def add_final(self, text):
        cleaned = ' '.join(str(text or '').strip().split())
        if cleaned:
            self.parts.append(cleaned[:400])
            if len(self.parts) > 12:
                self.parts = self.parts[-12:]

    def due(self, now=None):
        now = self.clock() if now is None else now
        return (bool(self.parts) and self.last_voice_at is not None
                and now - self.last_voice_at >= self.pause_seconds)

    def finish(self, require_voice=True):
        text = ' '.join(self.parts)[:1400].strip()
        verified = (self.voiced_ms >= self.min_voice_ms or not require_voice)
        self.reset()
        return text if verified else ''


class VoiceConfidenceFilter:
    """Filter common low-confidence single-token recognizer hallucinations.

    No keyword list can determine whether the speaker is the user. This is a
    supplementary guard; VAD, optional better ASR, and manual mic controls
    provide primary protection.
    """
    GARBAGE = frozenset(('um', 'uh', 'huh', 'the', 'a', 'you', 'thank you'))

    @staticmethod
    def should_route(text, conversation_active):
        value = ' '.join(str(text or '').lower().split())
        if not value:
            return False
        if value in VoiceConfidenceFilter.GARBAGE:
            return False
        # Single substantive words are sometimes valid answers to a follow-up.
        if len(value.split()) == 1 and not conversation_active:
            return value in ('apex', 'hey', 'jarvis')
        return True
