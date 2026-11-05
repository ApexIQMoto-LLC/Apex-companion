import json
import queue
import threading
import time
import re
from array import array
import math
from .conversation import ConversationSession, wake_remainder
from pathlib import Path
from .speech_output import WindowsSpeech
from .voice_processing import SpeechGate, PauseAwareTurn, VoiceConfidenceFilter
from .settings import ROOT


def input_devices(sd=None):
    """Return microphone-capable PortAudio devices. IDs are not stable across PCs."""
    if sd is None:
        import sounddevice as sd
    options = []
    for index, item in enumerate(sd.query_devices()):
        if int(item.get("max_input_channels", 0)) >= 1:
            options.append({"id": index, "name": str(item.get("name", "Microphone")),
                            "rate": int(float(item.get("default_samplerate", 16000) or 16000))})
    return options


def capture_settings(sd=None, device=None):
    """Use 16 kHz if supported; otherwise select the input's native rate.

    Vosk's recognizer receives the *actual* capture rate, avoiding the broken
    sample-rate mismatch that can make audio unintelligible.
    """
    if sd is None:
        import sounddevice as sd
    if device in (None, "", "default"):
        selected = None
    else:
        selected = int(device)
        if selected < 0:
            raise ValueError("Microphone device index must be nonnegative")
    details = sd.query_devices(selected, "input")
    if int(details.get("max_input_channels", 0)) < 1:
        raise ValueError("Selected audio device has no microphone input")
    native = int(round(float(details.get("default_samplerate", 16000) or 16000)))
    last_error = None
    for rate in dict.fromkeys([16000, native]):
        try:
            sd.check_input_settings(device=selected, channels=1, dtype="int16", samplerate=rate)
            return selected, rate, str(details.get("name", "System default microphone"))
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Cannot open selected microphone at 16 kHz or its native rate ({native} Hz): {last_error}")


def find_wake_phrase(text, phrases):
    """Return (matched, remainder) for fully transcribed speech."""
    normalized = " ".join(text.lower().split())
    for phrase in sorted(phrases, key=len, reverse=True):
        phrase = phrase.lower().strip()
        if normalized == phrase:
            return True, ""
        if normalized.startswith(phrase + " "):
            return True, normalized[len(phrase):].strip()
    return False, ""


class LocalSpeaker:
    """Non-blocking spoken replies with Windows SAPI and pyttsx3 fallback.

    On Windows, System.Speech is the default. The pyttsx3 backend remains
    available for users who select it or on other platforms. Neither backend
    needs to send text or audio to the cloud.
    """

    def __init__(self, status_callback=None, backend="auto", volume=100, voice="af_heart"):
        self.queue = queue.Queue()
        self.busy = threading.Event()
        self.pending = threading.Event()
        self.cancelled = threading.Event()
        self.status_callback = status_callback or (lambda x: None)
        self.backend = str(backend or "auto").lower()
        self.volume = max(0, min(100, int(volume)))
        self.engine = None
        self.windows = WindowsSpeech(volume=self.volume)
        self.voice = voice
        self.natural = None
        self.available = None
        self._shutdown = False
        self.thread = threading.Thread(target=self._worker, name="LocalSpeaker", daemon=True)
        self.thread.start()

    def say(self, text):
        if self._shutdown:
            return False
        plain = re.sub(r"[`*_#>]+", "", str(text))
        plain = re.sub(r"https?://\S+", "source link", plain)
        if not plain.strip():
            return False
        self.cancelled.clear()
        self.pending.set()
        self.queue.put(plain[:1300])
        return True

    def cancel(self):
        self.cancelled.set()
        self.pending.clear()
        while True:
            try:
                item = self.queue.get_nowait()
                if item is None:
                    self.queue.put(None)
                    break
            except queue.Empty:
                break
        # Windows SAPI is a separate process so cancellation can terminate it.
        self.windows.stop()
        if self.natural is not None:
            try: self.natural.stop()
            except Exception: pass
        # Don't call pyttsx3.stop() across COM threads; it can deadlock.

    def _speak_pyttsx(self, text):
        if self.engine is None:
            import pyttsx3
            self.engine = pyttsx3.init()
            self.engine.setProperty("rate", 175)
            self.engine.setProperty("volume", self.volume / 100)
        self.engine.say(text)
        self.engine.runAndWait()

    def _speak_one(self, text):
        mode = self.backend
        if mode == "auto":
            mode = "windows" if __import__("os").name == "nt" else "pyttsx3"
        if mode not in ("windows", "pyttsx3", "kokoro"):
            raise ValueError("Invalid speech output backend")
        try:
            if mode == "windows":
                self.windows.speak(text)
            elif mode == "kokoro":
                if self.natural is None:
                    from .natural_voice import NaturalVoice
                    self.natural = NaturalVoice(ROOT / "models" / "kokoro", voice=self.voice)
                self.natural.speak(text)
            else:
                self._speak_pyttsx(text)
            self.available = True
            self.status_callback("Speech: finished speaking through " + mode)
        except Exception as primary:
            if self.cancelled.is_set():
                self.status_callback("Speech: stopped")
                return
            if mode in ("windows", "kokoro"):
                try:
                    fallback = "pyttsx3" if mode == "windows" else "Windows built-in"
                    self.status_callback(f"Speech: {mode} unavailable ({str(primary)[:140]}); using {fallback} fallback")
                    if mode == "windows":
                        self._speak_pyttsx(text)
                    else:
                        self.windows.speak(text)
                    self.available = True
                    self.status_callback(f"Speech: finished speaking through {fallback} fallback")
                    return
                except Exception as secondary:
                    self.available = False
                    self.status_callback(f"Speech output error ({mode}: {primary}; fallback: {secondary})"[:400])
            else:
                self.available = False
                self.status_callback(f"Speech output error: {primary}"[:400])

    def _worker(self):
        while True:
            text = self.queue.get()
            if text is None:
                break
            try:
                if not self.cancelled.is_set():
                    self.busy.set()
                    self.status_callback("Speech: speaking now")
                    self._speak_one(text)
            finally:
                self.busy.clear()
                if self.queue.empty():
                    self.pending.clear()

    def shutdown(self):
        self._shutdown = True
        self.cancel()
        self.queue.put(None)


class WakeMicrophone:
    def __init__(self, model_path, phrases, on_command, speaker, status_callback, on_level=None,
                 on_wake=None, on_sleep=None, can_accept=None, session_seconds=120, device=None,
                 on_transcript=None, on_partial=None, speech_pause_seconds=2.1,
                 speech_vad_mode=3, improved_recognition=False):
        self.model_path = Path(model_path)
        self.device = device
        self.input_name = ""
        self.input_rate = None
        self._signal_reported = False
        self.phrases = phrases
        self.on_command = on_command
        self.speaker = speaker
        self.status = status_callback
        self.on_level = on_level or (lambda x: None)
        self.on_wake = on_wake or (lambda has_command: None)
        self.on_sleep = on_sleep or (lambda: None)
        self.can_accept = can_accept or (lambda: True)
        # Only user-intentional utterances are sent to AI. Recognition
        # diagnostics never persist transcripts or start paid requests.
        self.on_transcript = on_transcript or (lambda text, kind: None)
        self.on_partial = on_partial or (lambda text: None)
        self.session = ConversationSession(phrases, idle_seconds=session_seconds)
        self.speech_pause_seconds = float(speech_pause_seconds)
        self.speech_vad_mode = max(0, min(3, int(speech_vad_mode)))
        self.improved_recognition = bool(improved_recognition)
        self._last_level = 0.0
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Offline Vosk model missing: {self.model_path}. See README.md."
            )
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, name="WakeMicrophone", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def route_recognized(self, sentence):
        """Handle one completed local Vosk utterance; returns its routing action.

        A live audio level is NOT a recognized instruction. The caller can show
        that distinction without disclosing audio or silently paying for AI.
        """
        sentence = str(sentence or "").strip()
        if not sentence:
            return "ignore", ""
        kind, remainder = self.session.accept(sentence)
        self.on_transcript(sentence, kind)
        if kind == "wake":
            self.on_wake(False)
        elif kind == "utterance":
            woke, _ = wake_remainder(sentence, self.phrases)
            if woke:
                self.on_wake(True)
            self.on_command(remainder, True)
        elif kind == "sleep":
            self.on_sleep()
        return kind, remainder

    def _run(self):
        try:
            import sounddevice as sd
            from vosk import Model, KaldiRecognizer, SetLogLevel
            SetLogLevel(-1)
            model = Model(str(self.model_path))
            selected, sample_rate, microphone_name = capture_settings(sd, self.device)
            self.input_name, self.input_rate = microphone_name, sample_rate
            recognizer = KaldiRecognizer(model, sample_rate)
            audio_q = queue.Queue(maxsize=30)
            gate = SpeechGate(sample_rate, mode=self.speech_vad_mode)
            turn = PauseAwareTurn(pause_seconds=self.speech_pause_seconds)
            turn_pcm = bytearray()
            enhancer = None
            if self.improved_recognition:
                try:
                    from .voice_transcription import WhisperEnhancer
                    enhancer = WhisperEnhancer(ROOT / "models" / "whisper-small.en")
                    self.status("Microphone: enhanced Whisper transcription enabled")
                except Exception as err:
                    self.status("Microphone: enhanced recognition unavailable; using Vosk (" + str(err)[:100] + ")")
            self.status("Microphone: speech filter " + ("WebRTC enabled" if gate.neural else "energy fallback; install webrtcvad-wheels"))
            last_partial = ""
            last_partial_time = 0.0
            self._signal_reported = False
            self.status(f"Microphone: using {microphone_name} at {sample_rate} Hz")

            def callback(indata, frames, time_info, status):
                if self.stop_event.is_set() or self.speaker.busy.is_set() or self.speaker.pending.is_set() or not self.can_accept():
                    return
                try:
                    # RMS only, sampled from local audio; no raw samples are persisted.
                    samples=array("h")
                    samples.frombytes(bytes(indata))
                    if samples:
                        subset = samples[::16]
                        power = math.sqrt(sum(x*x for x in subset)/len(subset))
                        normalized = min(1.0, power/5500.)
                        self.on_level(normalized)
                        if normalized > 0.045 and not self._signal_reported:
                            self._signal_reported = True
                            self.status("Microphone: input signal detected; waiting for speech recognition")
                    audio_q.put_nowait(bytes(indata))
                except queue.Full:
                    pass

            with sd.RawInputStream(samplerate=sample_rate, blocksize=max(1024, sample_rate // 4),
                                   dtype="int16", channels=1, device=selected, callback=callback):
                self.status(f"Microphone: listening on {microphone_name}")
                while not self.stop_event.is_set():
                    if self.speaker.busy.is_set() or self.speaker.pending.is_set() or not self.can_accept():
                        while not audio_q.empty():
                            try:
                                audio_q.get_nowait()
                            except queue.Empty:
                                break
                        recognizer.Reset()
                        turn.reset()
                        turn_pcm.clear()
                        gate.remainder = b""
                        last_partial = ""
                        time.sleep(0.1)
                        continue
                    try:
                        data = audio_q.get(timeout=0.25)
                    except queue.Empty:
                        data = None
                    now = time.monotonic()
                    if data:
                        voiced = gate.process(data)
                        if voiced:
                            turn.mark_voice(voiced, now)
                        # Bound raw temporary data to 20 s; never store to disk.
                        if turn.first_voice_at is not None:
                            turn_pcm.extend(data)
                            cap = sample_rate * 2 * 20
                            if len(turn_pcm) > cap:
                                del turn_pcm[:len(turn_pcm)-cap]
                        if recognizer.AcceptWaveform(data):
                            turn.add_final(json.loads(recognizer.Result()).get("text", ""))
                            last_partial = ""
                        else:
                            partial = json.loads(recognizer.PartialResult()).get("partial", "").strip()
                            if partial and partial != last_partial and now-last_partial_time > 0.5:
                                last_partial, last_partial_time = partial, now
                                self.on_partial(partial)
                    # If a phrase has been VAD-positive but Vosk has not yet
                    # finalized it, request a final hypothesis once the full
                    # natural pause has elapsed. Also clear old noise-only data.
                    if (turn.last_voice_at is not None and not turn.parts
                            and now - turn.last_voice_at >= turn.pause_seconds):
                        turn.add_final(json.loads(recognizer.FinalResult()).get("text", ""))
                        recognizer.Reset()
                        last_partial = ""
                        if not turn.parts:
                            turn.reset()
                            turn_pcm.clear()
                    if turn.due(now):
                        # Vosk may not yet have finalized the last clause. Finish
                        # it only once the user has paused for the full interval.
                        if last_partial:
                            turn.add_final(json.loads(recognizer.FinalResult()).get("text", ""))
                            recognizer.Reset()
                        text = turn.finish(require_voice=True)
                        if enhancer is not None and text:
                            try:
                                better = enhancer.transcribe(bytes(turn_pcm), sample_rate)
                                if better:
                                    text = better
                                else:
                                    text = ''  # No speech according to enhanced recognizer.
                            except Exception as err:
                                self.status("Microphone: enhanced ASR failed; Vosk fallback: " + str(err)[:100])
                        turn_pcm.clear()
                        last_partial = ""
                        if text and VoiceConfidenceFilter.should_route(text, self.session.active):
                            self.status("Microphone: complete speech turn; evaluating wake phrase")
                            self.route_recognized(text)
                        elif text:
                            self.status("Microphone: filtered likely noise or low-confidence words")
        except Exception as ex:
            self.status(f"Microphone error: {ex}")
        finally:
            self.status("Microphone stopped")


def transcribe_push_to_talk(model_path, seconds=8, device=None):
    """Capture a short, user-initiated microphone utterance entirely offline.

    Does not record to disk or upload audio. A local Vosk model is required.
    Caller must run this in a background worker, never the tkinter UI thread.
    """
    from pathlib import Path
    model_path=Path(model_path)
    if not model_path.is_dir():
        raise FileNotFoundError("Download the Vosk offline speech model first; see README")
    import sounddevice as sd
    from vosk import Model, KaldiRecognizer, SetLogLevel
    SetLogLevel(-1)
    selected, sample_rate, _ = capture_settings(sd, device)
    recognizer=KaldiRecognizer(Model(str(model_path)), sample_rate)
    fragments=[]
    blocksize = max(1024, sample_rate // 4)
    with sd.RawInputStream(samplerate=sample_rate,blocksize=blocksize,dtype="int16",channels=1,device=selected) as stream:
        for _ in range(max(1,min(15,int(seconds)))*4):
            data,_=stream.read(blocksize)
            if recognizer.AcceptWaveform(bytes(data)):
                value=json.loads(recognizer.Result()).get("text","").strip()
                if value:fragments.append(value)
    last=json.loads(recognizer.FinalResult()).get("text","").strip()
    if last:fragments.append(last)
    return " ".join(fragments)[:1000].strip()
