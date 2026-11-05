# APEX v0.10.2 - Windows voice output repair

**Symptom:** The hologram shows the text response and the mic is listening, but APEX doesn't speak aloud.

In older builds, response text could appear even when `pyttsx3` could not start or play. The compact window did not show voice errors. This release introduces Windows' built-in local `System.Speech` synthesizer, a fallback to `pyttsx3`, output status, and an instant test button. Spoken voice remains local and does **not** spend OpenAI credits.

## Update

1. Completely quit APEX from the Windows notification area (close/hide is not quit).
2. Extract the new ZIP outside your installed APEX directory.
3. Run `Update_Existing_Install.cmd` and upgrade your existing installation. It is designed to preserve your `.env`, `config.json`, `data/`, `.venv`, saved sessions, and Windows credential store.
4. Start APEX with `Launch_Companion.cmd` and open the small hologram.
5. Click **TEST VOICE**. You should hear: "Hello. I'm Apex. My voice output is working. What would you like to talk about?"
6. If silent, open **VOICE OUTPUT SETTINGS**, select **Windows built-in speech**, set volume to 100, choose **SAVE + TEST VOICE**.
7. Confirm the correct speaker/headphones in **Windows Settings -> System -> Sound -> Output** and that your output is not muted. In **Volume mixer**, ensure Python/PowerShell audio isn't muted.
8. If still silent, run **`Test_Windows_Voice.cmd`**. The standalone test separates Windows/system sound problems from APEX's UI/AI logic and prints errors.
9. Try **pyttsx3 (legacy voice)** in Voice Output Settings only if Windows built-in speech fails.

APEX now shows local speech status below the controls in the small hologram. An error indicates which backend failed. A successful completion message reports only that the speech command finished; it cannot independently detect whether a headset or speaker is muted.

## Notes

- `VOICE` controls microphone input; **TEST VOICE** exercises audio output. They are separate paths.
- `STOP` cancels queued and Windows-spoken audio.
- The built-in Windows speech engine uses the default system playback output, no subscription or voice download required.
- This is turn-taking conversation, not simultaneous full-duplex audio.
- Settings are stored in `config.json` under `speech_output_backend` (`windows` or `pyttsx3`) and `speech_output_volume` (0-100). Existing config values remain intact.
- The release also includes the pending microphone device selection/recognizer sample-rate improvements from v0.10.1. The microphone you selected in Windows stays system-owned; if APEX chooses a different one, use Tray > Microphone setup.
- Live spoken output, device routing, and microphone accuracy require verification on your Windows PC; automated tests cannot guarantee an audible sound.
