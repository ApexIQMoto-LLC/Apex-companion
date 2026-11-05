"""Optional free offline Kokoro ONNX voice. No hosted speech APIs.

Models are explicitly installed by the owner in models/kokoro, not fetched
silently when APEX starts. Only locally generated audio is played.
"""
from __future__ import annotations

from pathlib import Path

VOICE_CHOICES = ('af_heart', 'af_bella', 'am_michael', 'am_adam')


class NaturalVoice:
    def __init__(self, model_dir, voice='af_heart', speed=1.0):
        from kokoro_onnx import Kokoro
        self.model_dir = Path(model_dir)
        model = self.model_dir / 'kokoro-v1.0.int8.onnx'
        voices = self.model_dir / 'voices-v1.0.bin'
        if not model.is_file() or not voices.is_file():
            raise FileNotFoundError('Kokoro voice model not installed. Run Install_Natural_Voice.cmd.')
        self.voice = voice if voice in VOICE_CHOICES else VOICE_CHOICES[0]
        self.speed = min(1.25, max(0.75, float(speed)))
        self.engine = Kokoro(str(model), str(voices))

    def speak(self, text):
        import sounddevice as sd
        audio, sample_rate = self.engine.create(str(text)[:1300],
                                                voice=self.voice, speed=self.speed,
                                                lang='en-us')
        sd.play(audio, samplerate=sample_rate, blocking=True)

    def stop(self):
        import sounddevice as sd
        sd.stop()
