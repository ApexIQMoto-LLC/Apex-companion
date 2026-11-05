# APEX v0.10.3 — Speech recognition → AI conversation repair

## What was wrong

The previous build could show microphone audio levels ("Listening") without displaying the actual Vosk recognized text or its routing outcome. The voice handler intentionally ignored phrases unless Vosk recognized a configured wake phrase or a conversation session was already open. Some users therefore saw sound input with no AI request and no explanation. This fix **does not claim the user's exact audio was reproduced**.

## What changed

- A prominent **TALK TO APEX** control opens an explicitly user-initiated, time-limited conversation. Speak **after the short opening response**. No wake phrase is required for that conversation's follow-up turns.
- Existing wake phrases continue working: "Apex", "Open Apex", "Start Apex", "Hey Apex". Once awakened, you can ask your question after APEX finishes speaking.
- The mini hologram now shows live local recognition phases: `HEARING`, `HEARD — NOT SENT`, `WAKE RECOGNIZED`, `ACCEPTED FOR PROCESSING`, `AI REQUEST QUEUED`, `AI ANSWER RECEIVED`, or `AI REQUEST FAILED`.
- The **CHECK AI** button validates the local API-key availability and local spending/rate caps. This is not a remote model test and **does not use paid API tokens**. The first user-initiated question validates live API access and model availability.
- If an explicitly spoken AI request fails, APEX speaks a short error notification. The detailed error appears in the mini transcript.
- The hologram layout was resized so the new buttons and existing speaker controls fit at the default compact-window size.
- Recognized partial/final text is shown only in the opened mini window; it is **not stored in diagnostics, logs, or databases** unless accepted as a user-authored AI request under existing conversation/memory settings. Raw audio remains local to Vosk.

## Install and test on Windows

1. Right-click APEX in the system tray, then choose **Quit**. Hiding the window is not sufficient.
2. Extract the v0.10.3 ZIP to a new folder. Run **Update_Existing_Install.cmd** from that extracted folder.
3. Launch the upgraded APEX app, open the hologram, and press **CHECK AI**. If the result says `OPENAI_API_KEY is not set`, configure the key in your existing install's `.env` file; never paste secrets into a chat or screenshot.
4. Press **TALK TO APEX**. Wait until the spoken "I'm listening" response finishes. Say: **"What should we focus on for ApexIQ Moto marketing?"**
5. Observe the recognition status. If you see `HEARING` but never `RECOGNIZED`, adjust your Vosk model/microphone/noise or speak, then pause naturally. If you see `HEARD — NOT SENT`, you are outside an active conversation; press TALK again or say "Apex" first.
6. `AI REQUEST QUEUED` indicates the recognized question reached the app's AI request path; `AI ANSWER RECEIVED` indicates the response came back. `AI REQUEST FAILED` gives a specific safe error message in the transcript (such as an API key, model, usage cap or network failure).
7. You can also enter a typed question in the mini window; if typing fails too, the issue is the AI provider/configuration, not microphone recognition.

## Notes

- Speech is **turn-taking**, not simultaneous full-duplex. APEX intentionally suspends microphone recognition while speaking and while a model request is in flight.
- Voice requests may consume the user's existing API budget. Neither **CHECK AI**, voice recognition, nor the local speech test does.
- No change was made to cloud accounts, Supabase data, social OAuth, marketing metrics, installed speech models, saved memory or credentials.
- This update was tested with synthetic voice-recognition inputs and unit tests. It has **not** been tested with the user's actual Windows microphone, speakers, OAuth sessions, network or API key.
