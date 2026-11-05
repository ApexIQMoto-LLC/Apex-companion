"""Small holographic primary window; existing full dashboard remains intact."""
from __future__ import annotations

import tkinter as tk
from datetime import datetime

from .holographic_ui import HolographicCore

BG = "#080F1A"
CARD = "#101F30"
CYAN = "#67E8DB"
INK = "#E8F5FC"
MUTED = "#91A8B9"


class MiniCompanion:
    WIDTH = 458
    HEIGHT = 650

    def __init__(self, master, *, on_submit, on_hide, on_dashboard, on_microphone,
                 on_business, on_personal, on_stop, on_test_voice, on_voice_setup,
                 on_begin_voice, on_check_ai):
        win = tk.Toplevel(master)
        self.window = win
        win.withdraw()
        win.title("APEX | Voice Companion")
        win.configure(bg=BG)
        win.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        win.minsize(385, 520)
        win.protocol("WM_DELETE_WINDOW", on_hide)
        win.resizable(True, True)
        self.on_submit = on_submit

        header = tk.Frame(win, bg=BG, padx=15, pady=10)
        header.pack(fill="x")
        tk.Label(header, text="A P E X  /  LIVE", fg=CYAN, bg=BG,
                 font=("Segoe UI", 15, "bold")).pack(side="left")
        tk.Button(header, text="HIDE  -", command=on_hide, bg=CARD, fg=INK,
                  activebackground="#264657", relief="flat", padx=10).pack(side="right")
        self.state = tk.StringVar(value="SAY 'APEX' TO BEGIN")
        self.holo = HolographicCore(win, height=165)
        self.holo.pack(fill="x", padx=8, pady=(0, 4))
        tk.Label(win, textvariable=self.state, bg=BG, fg=CYAN,
                 font=("Consolas", 10, "bold")).pack(pady=(0, 9))

        body = tk.Frame(win, bg=CARD, padx=9, pady=6)
        body.pack(fill="both", expand=True, padx=12, pady=(0, 9))
        self.transcript = tk.Text(body, bg="#0A1C2D", fg=INK, wrap="word", font=("Segoe UI", 10),
                                  state="disabled", borderwidth=0, padx=8, pady=7, spacing1=4, height=6)
        self.transcript.pack(fill="both", expand=True)
        self.transcript.tag_configure("user", foreground="#B4C9FF")
        self.transcript.tag_configure("apex", foreground=CYAN)
        self.recognition_note = tk.StringVar(value="VOICE INPUT / SAY APEX, OR TAP TALK TO APEX")

        row = tk.Frame(win, bg=BG, padx=12)
        row.pack(fill="x", pady=(0, 9))
        self.entry = tk.Entry(row, bg="#123047", fg=INK, insertbackground=CYAN,
                              borderwidth=0, font=("Segoe UI", 11))
        self.entry.pack(side="left", fill="x", expand=True, ipady=10, padx=(0, 6))
        self.entry.bind("<Return>", lambda e: self.submit())
        tk.Button(row, text="SEND", command=self.submit, bg="#116479", fg="white",
                  activebackground="#218399", relief="flat", padx=10, pady=8).pack(side="right")
        voice_row = tk.Frame(win, bg=BG, padx=12)
        voice_row.pack(fill="x", pady=(0, 5))
        tk.Button(voice_row, text="TALK TO APEX", command=on_begin_voice, bg="#116479",
                  fg="white", activebackground="#218399", relief="flat", padx=9,
                  pady=7, font=("Segoe UI", 9, "bold")).pack(side="left", fill="x", expand=True, padx=(0, 6))
        tk.Button(voice_row, text="CHECK AI", command=on_check_ai, bg=CARD,
                  fg=INK, relief="flat", padx=9, pady=7).pack(side="right")
        tk.Label(win, textvariable=self.recognition_note, bg=BG, fg=MUTED,
                 anchor="w", font=("Segoe UI", 8), wraplength=410,
                 justify="left").pack(fill="x", padx=16, pady=(0, 6))
        tools = tk.Frame(win, bg=BG, padx=10)
        tools.pack(fill="x", pady=(0, 10))
        for title, command in (("BUSINESS", on_business), ("PERSONAL", on_personal),
                               ("VOICE", on_microphone), ("STOP", on_stop),
                               ("DASHBOARD", on_dashboard)):
            tk.Button(tools, text=title, command=command, bg=CARD, fg=MUTED,
                      activeforeground=INK, activebackground="#25475C", borderwidth=0,
                      font=("Segoe UI", 8), padx=5, pady=9).pack(side="left", expand=True, padx=2)
        speech_controls = tk.Frame(win, bg=BG, padx=12)
        speech_controls.pack(fill="x", pady=(0, 4))
        tk.Button(speech_controls, text="TEST VOICE", command=on_test_voice, bg=CARD,
                  fg=CYAN, relief="flat", padx=9, pady=5).pack(side="left", padx=(0, 8))
        tk.Button(speech_controls, text="VOICE OUTPUT SETTINGS", command=on_voice_setup,
                  bg=CARD, fg=INK, relief="flat", padx=9, pady=5).pack(side="left")
        self.audio_note = tk.StringVar(value="SPEAKER / NOT TESTED")
        tk.Label(win, textvariable=self.audio_note, bg=BG, fg=MUTED,
                 anchor="w", font=("Segoe UI", 8)).pack(fill="x", padx=17, pady=(0, 5))
        self.append("APEX", "Ready. Say 'Apex', 'Open Apex', or 'Start Apex' to begin.")

    def submit(self):
        text = self.entry.get().strip()
        if text:
            self.entry.delete(0, "end")
            self.on_submit(text)

    def show(self):
        win = self.window
        if not win.winfo_exists():
            return
        if win.state() == "withdrawn":
            sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
            win.geometry(f"{self.WIDTH}x{self.HEIGHT}+{max(0, sw-self.WIDTH-35)}+{max(0, sh-self.HEIGHT-85)}")
        win.deiconify()
        win.lift()
        self.entry.focus_set()

    def hide(self):
        self.window.withdraw()

    def append(self, author, text):
        if not self.window.winfo_exists():
            return
        value = str(text).split("\nModel: ", 1)[0][:1300]
        self.transcript.configure(state="normal")
        self.transcript.insert("end", f"{author.upper()}  {datetime.now():%H:%M}\n", "user" if author.upper() == "YOU" else "apex")
        self.transcript.insert("end", value + "\n\n")
        lines = int(self.transcript.index("end-1c").split(".")[0])
        if lines > 280:
            self.transcript.delete("1.0", "80.0")
        self.transcript.configure(state="disabled")
        self.transcript.see("end")

    def set_recognition_status(self, message):
        """Ephemeral local UI text; does not persist recognized speech."""
        self.recognition_note.set(str(message).strip()[:165])

    def set_audio_status(self, message):
        text = str(message).strip()
        if not text:
            return
        # Voice diagnostics must be visible in the compact window, not only
        # the hidden full dashboard's status bar.
        self.audio_note.set(("SPEAKER / " + text.replace("Speech:", "").strip())[:130])

    def render(self, mode, level, voice, camera, presence, away, conversation):
        if self.window.state() != "normal":
            return
        self.holo.update_state(mode=mode, microphone_level=level,
            voice_ready=voice, camera_ready=camera, presence=presence, away=away)
        self.holo.render()
        if not voice:
            status = "MIC OFF  /  TURN ON VOICE OR TYPE BELOW"
        elif mode == "THINKING":
            status = "APEX / PROCESSING YOUR REQUEST"
        elif mode == "SPEAKING":
            status = "APEX / SPEAKING"
        elif conversation:
            status = "CONVERSATION OPEN  /  JUST TALK"
        else:
            status = "LISTENING FOR 'APEX'"
        self.state.set(status)
