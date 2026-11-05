"""Optional offline Whisper transcription of a locally gated speech turn.

The voice stream uses Vosk for wake detection and initial recognition.
Whisper runs only on completed, VAD-positive speech when explicitly enabled.
"""
from __future__ import annotations

from array import array
from pathlib import Path


class WhisperEnhancer:
    def __init__(self, model_dir):
        directory = Path(model_dir)
        if not (directory / 'model.bin').is_file():
            raise FileNotFoundError('Enhanced recognition model missing. Run Install_Enhanced_Recognition.cmd.')
        from faster_whisper import WhisperModel
        self.model = WhisperModel(str(directory), device='cpu', compute_type='int8', cpu_threads=6)

    def transcribe(self, pcm, sample_rate):
        import numpy as np
        rate = int(sample_rate)
        if rate < 8000 or not pcm:
            return ''
        audio = np.frombuffer(pcm, dtype='<i2').astype(np.float32) / 32768.0
        if len(audio) < rate * 0.25:
            return ''
        if rate != 16000:
            # Our capture device can fall back to its supported native rate.
            # Resample in memory, without network transfer or temporary files.
            from scipy.signal import resample_poly
            from math import gcd
            g = gcd(rate, 16000)
            audio = resample_poly(audio, 16000 // g, rate // g)
        segments, _ = self.model.transcribe(
            audio, language='en', beam_size=3, condition_on_previous_text=False,
            vad_filter=True, vad_parameters={'min_silence_duration_ms': 500},
            no_speech_threshold=0.55, initial_prompt='Apex, ApexIQ Moto, ARIS, Instagram Reels, Replay Studio, sportbike, telemetry.')
        values = []
        for seg in segments:
            if getattr(seg, 'no_speech_prob', 0.0) > 0.75:
                continue
            if getattr(seg, 'avg_logprob', 0) < -1.15:
                continue
            values.append(seg.text.strip())
        text = ' '.join(values).strip()
        # Avoid accepting common ASR hallucinations in otherwise silent clips.
        if text.lower().strip(' .,!') in {'thank you', 'thanks for watching', 'you', 'the'}:
            return ''
        return text[:1400]
