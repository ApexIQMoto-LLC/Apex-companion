"""Windows built-in speech synthesis without third-party speech drivers.

Uses Windows PowerShell 5.1 System.Speech with a safe encoded payload rather
than interpolating untrusted assistant output into executable PowerShell.
"""
from __future__ import annotations

import base64
import os
import subprocess
import threading


def build_windows_speech_command(text: str, rate: int = 0, volume: int = 100) -> list[str]:
    """Return a PowerShell argument vector with data-only encoded speech text."""
    rate = max(-10, min(10, int(rate)))
    volume = max(0, min(100, int(volume)))
    payload = base64.b64encode(str(text)[:1300].encode("utf-8")).decode("ascii")
    script = (
        "$ErrorActionPreference='Stop';"
        "Add-Type -AssemblyName System.Speech;"
        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        "try {"
        "$s.SetOutputToDefaultAudioDevice();"
        f"$s.Rate={rate};$s.Volume={volume};"
        f"$text=[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('{payload}'));"
        "$s.Speak($text);"
        "} finally {$s.Dispose()}"
    )
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    return ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded]


class WindowsSpeech:
    """One utterance at a time. Caller owns the worker thread."""

    def __init__(self, rate=0, volume=100):
        self.rate = rate
        self.volume = volume
        self.process = None
        self.lock = threading.Lock()

    def speak(self, text: str) -> None:
        if os.name != "nt":
            raise RuntimeError("Windows speech synthesis requires Windows")
        args = build_windows_speech_command(text, self.rate, self.volume)
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        p = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                             stdin=subprocess.DEVNULL, creationflags=flags)
        with self.lock:
            self.process = p
        try:
            _out, stderr = p.communicate(timeout=75)
            if p.returncode:
                details = stderr.decode("utf-8", errors="replace").strip()
                raise RuntimeError((details or f"PowerShell exited {p.returncode}")[:350])
        except subprocess.TimeoutExpired:
            p.kill()
            p.communicate()
            raise RuntimeError("Windows speech synthesis timed out")
        finally:
            with self.lock:
                if self.process is p:
                    self.process = None

    def stop(self) -> None:
        with self.lock:
            p = self.process
        if p is not None and p.poll() is None:
            try:
                p.terminate()
            except OSError:
                pass
