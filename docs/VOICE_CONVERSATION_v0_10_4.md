# APEX v0.10.4 — Better Speech, Natural Offline Voice and Conversation

This update fixes the three issues shown in the November 4 speech transcript: background sounds being transcribed into commands, multi-clause speech being cut off, and generic/misinterpreted responses. It also makes casual voice chats much lighter on API token usage. Actual audio performance must be confirmed on your Windows machine.

## Installation

1. Fully quit APEX from the Windows hidden-icons system tray.
2. Extract `ApexIQ_Companion_v0_10_4.zip` to its own folder.
3. Run `Update_Existing_Install.cmd` in the extracted folder. Keep your existing installation folder as the target, typically `C:\ApexIQCompanion`. The updater preserves `data`, `.env`, `config.json`, `.venv`, and Windows Credential Manager.
4. Start APEX with `Launch_Companion.cmd` from the installed folder. The normal updater includes the lightweight WebRTC voice-activity detector; no audio goes to WebRTC servers.
5. Select **Microphone Setup** from the tray to change the pause threshold (default **2.1 seconds**) and noise-rejection strength (default **3**, the strictest). Voice restarts when you save.
6. Start a normal voice conversation with **TALK TO APEX**.

## Free natural voice (optional)

Run `Install_Natural_Voice.cmd` from your **installed APEX folder**, not the extracted update package. This installs the optional `kokoro-onnx` inference package, then downloads the official Kokoro ONNX `model-files-v1.1` INT8 model and voice bank (approximately 140 MB total) from GitHub. Restart APEX and open **VOICE OUTPUT SETTINGS**, select **Kokoro — natural, free, offline**, choose one of `af_heart`, `af_bella`, `am_michael`, `am_adam`, and click **SAVE + TEST VOICE**.

The actual speech output is locally generated; there is no recurring TTS API charge. If Kokoro is not installed or produces an error, APEX shows the reason and falls back to Windows speech. Some local playback/system configurations still require troubleshooting; it has not been audibly tested on your PC.

## More accurate local recognition (optional)

After verifying the basic speech gate works, fully quit APEX, then run `Install_Enhanced_Recognition.cmd` from your installed folder. This installs Faster Whisper and downloads the `Systran/faster-whisper-small.en` model from Hugging Face (approximately 500 MB of model weights plus Python dependencies). It automatically sets `speech_enhanced_recognition=true` in your local `config.json` only after a successful download. Restart APEX.

Vosk remains responsible for wake recognition; Whisper re-transcribes a completed, locally gated speech turn. Audio is processed **on your PC**, not sent to the model host. On first enable, loading the Whisper model may take time, and CPU transcription introduces additional response latency. This feature has been code-reviewed and unit-tested, but runtime model behavior has **not** been verified on your Windows machine. The fallback remains Vosk.

## How the new turn detection works

- The default WebRTC voice-activity detector evaluates audio in short PCM frames; non-speech noise does not, by itself, qualify as a user utterance.
- Several Vosk finalized clauses can be accumulated before delivery to the AI. APEX waits **2.1 seconds after the last detected voice**. Increase to around 2.5–3 seconds if you're thinking between phrases; reduce if the interaction feels slow.
- A short fragment without sufficient voiced audio is rejected. Common Vosk hallucinations like isolated `uh` or `thank you` can also be filtered.
- If a sentence is still unrecognized, open the hologram and use typed text or the existing push-to-talk workflow as a fallback.
- WebRTC VAD is **not speaker recognition**. TVs, people, barking and wind can still occasionally trigger it. For noisy surroundings, turn off continuous listening, use push-to-talk, or select a noise-cancelling headset microphone.

## Conversational intelligence and model usage

- In conversational mode, APEX now sends a small, targeted project description, recent dialogue, and at most a small number of pertinent memory facts, rather than always attaching the full project brief, every local note, live dashboard material, and all available tool schemas.
- Read-only tools and business dashboard context remain available when you explicitly ask about relevant current business metrics.
- Replies are instructed to be concrete and natural, not repetitive, and to treat garbled ASR phrases as uncertain rather than insisting they are what you meant.
- Voice responses use a 420-output-token cap by default. The AI request still counts as a paid API call. Offline speech recognition and offline speech synthesis do not incur model API charges.
- An API 429 token-per-minute limit is not a TTS or microphone failure. APEX now stops automatic retries, respects a server-provided cooldown where available, and displays a short reason instead of repeatedly hitting the model.

## Diagnostic test

With audio connected and speaking volume confirmed, click **TALK TO APEX** and say:

> Let's make a fifteen-second Instagram Reel about ApexIQ Moto. I'm thinking a camera intro ... (pause one second) ... then fast motorcycle POV cuts with the telemetry overlay.

APEX should wait for the full phrase and propose a short hook and shot sequence. Watch the recognition status and test alternative pause/VAD settings before spending many AI requests. Do not use background TV/music for the first test.

## What is and isn't verified

- Verified: Windows application source builds, offline unit tests, pause accumulation logic, compact conversation instructions, optional install commands, package structure, and non-destructive updater behavior.
- Not yet verified on your PC: your microphone's VAD confidence, Kokoro model download/playback/voice quality, Whisper real-time latency, and live OpenAI API response while the reported rate limit is active.

Sources: https://pypi.org/project/webrtcvad-wheels/ , https://pypi.org/project/kokoro-onnx/ , https://github.com/thewh1teagle/kokoro-onnx/releases , https://github.com/SYSTRAN/faster-whisper , https://developers.openai.com/api/docs/guides/rate-limits
