"""ApexIQ Companion v0.4: local-first development and growth assistant."""
import os
import queue
import threading
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime
from tkinter import messagebox, scrolledtext, simpledialog

from companion.settings import ROOT, load_settings, ensure_local_files
from companion.costs import SpendLedger
from companion.assistant import CompanionBrain
from companion.presence import PresenceCamera
from companion.voice import LocalSpeaker, WakeMicrophone
from companion.news import fetch_brief, render_brief
from companion.marketing import scan as scan_marketing, render_report as render_marketing, save_report, analysis_prompt
from companion.supabase_monitor import SupabaseMonitor, render_snapshot
from companion.steamworks import SteamworksReader, render_summary

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

BG = "#101722"
PANEL = "#172332"
ACCENT = "#3AE1C5"
TEXT = "#ECF6FA"
MUTED = "#A0B4C1"


class CompanionApp:
    def __init__(self):
        ensure_local_files()
        self.settings = load_settings()
        self.ledger = SpendLedger(ROOT / "data" / "usage.sqlite3")
        self.brain = CompanionBrain(self.settings, self.ledger)
        self.events = queue.Queue()
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.speaker = LocalSpeaker(lambda msg: self.events.put(("status", msg)))
        self.camera = None
        self.microphone = None
        self.working = False
        self.cloud = None
        self.marketing_running = False
        self.steam_running = False
        cloud_url = str(self.settings.get("supabase_url", ""))
        cloud_key = str(self.settings.get("supabase_publishable_key", ""))
        if cloud_url and cloud_key.startswith("sb_publishable_"):
            try:
                self.cloud = SupabaseMonitor(cloud_url, cloud_key)
            except ValueError:
                pass

        root = tk.Tk()
        self.root = root
        root.title("ApexIQ Companion | 0.4")
        root.geometry("1040x720")
        root.minsize(780, 560)
        root.configure(bg=BG)
        root.protocol("WM_DELETE_WINDOW", self.close)

        side = tk.Frame(root, bg=PANEL, width=220, padx=16, pady=18)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Label(side, text="APEXIQ", fg=ACCENT, bg=PANEL,
                 font=("Segoe UI", 22, "bold")).pack(anchor="w")
        tk.Label(side, text="COMPANION / 0.4", fg=MUTED, bg=PANEL,
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 25))

        self.camera_button = self._side_button(side, "Enable Camera", self.toggle_camera)
        self.mic_button = self._side_button(side, "Enable Wake Voice", self.toggle_microphone)
        self._side_button(side, "Business News", self.business_news)
        self._side_button(side, "Marketing Scan", self.marketing_scan)
        self._side_button(side, "Marketing AI Insights", self.marketing_insights)
        self._side_button(side, "Connect ApexIQ Cloud", self.connect_cloud)
        self._side_button(side, "Cloud Health", self.cloud_health)
        self._side_button(side, "Steam Growth", self.steam_growth)
        self._side_button(side, "Automation Status", self.automation_status)
        self._side_button(side, "Clear Chat Context", self.clear_context)
        self._side_button(side, "Local Notes File", self.open_notes)
        tk.Label(side, text="Offline wake word + local camera\nNo continuous AI session.",
                 fg=MUTED, bg=PANEL, justify="left", wraplength=180,
                 font=("Segoe UI", 9)).pack(side="bottom", anchor="w", pady=(10, 0))

        content = tk.Frame(root, bg=BG, padx=18, pady=15)
        content.pack(side="left", fill="both", expand=True)
        tk.Label(content, text="APEX IS ONLINE", fg=ACCENT, bg=BG,
                 font=("Segoe UI", 18, "bold")).pack(anchor="w")
        self.status_var = tk.StringVar(value="Ready | Camera OFF | Mic OFF")
        tk.Label(content, textvariable=self.status_var, fg=MUTED, bg=BG,
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 8))

        self.log = scrolledtext.ScrolledText(content, bg=PANEL, fg=TEXT,
                                            insertbackground=TEXT, wrap="word",
                                            font=("Consolas", 11),
                                            padx=14, pady=14, relief="flat")
        self.log.pack(fill="both", expand=True)
        self.log.configure(state="disabled")

        bottom = tk.Frame(content, bg=BG)
        bottom.pack(fill="x", pady=(12, 0))
        self.entry = tk.Entry(bottom, font=("Segoe UI", 12), bg=PANEL, fg=TEXT,
                              insertbackground=TEXT, relief="flat")
        self.entry.pack(side="left", fill="x", expand=True, ipady=11, padx=(0, 8))
        self.entry.bind("<Return>", lambda event: self.send())
        self._action_button(bottom, "Ask", self.send).pack(side="left", padx=(0, 5))
        self._action_button(bottom, "Deep", lambda: self.send(deep=True)).pack(side="left")
        self.budget_var = tk.StringVar()
        tk.Label(content, textvariable=self.budget_var, fg=MUTED, bg=BG,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(8, 0))

        self.write("SYSTEM", "Welcome to ApexIQ Companion v0.4.\n"
                   "Enable camera for a local presence greeting, or install the Vosk "
                   "model and enable wake voice. Type a question below.\n"
                   "Commands: news, marketing, steam, cloud, status.\n"
                   "'Deep' uses the stronger model; ordinary 'Ask' uses the budget model.")
        self.update_budget()
        root.after(150, self.drain_events)
        root.after(30_000, self.daily_brief_check)
        if self.settings.get("camera_autostart"):
            root.after(650, self.toggle_camera)
        if self.settings.get("microphone_autostart"):
            root.after(950, self.toggle_microphone)

    def _side_button(self, parent, label, command):
        btn = tk.Button(parent, text=label, command=command, bg="#273849", fg=TEXT,
                        activebackground="#345467", activeforeground=TEXT,
                        relief="flat", borderwidth=0, font=("Segoe UI", 10),
                        anchor="w", padx=12, pady=11)
        btn.pack(fill="x", pady=5)
        return btn

    def _action_button(self, parent, text, cmd):
        return tk.Button(parent, text=text, command=cmd, bg=ACCENT, fg="#071D21",
                         activebackground="#86F3DE", relief="flat", borderwidth=0,
                         font=("Segoe UI", 10, "bold"), padx=13, pady=10)

    def write(self, author, message):
        self.log.configure(state="normal")
        self.log.insert("end", f"\n[{author}]\n{message}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def update_budget(self):
        self.budget_var.set(
            "AI text spend estimate this month: "
            f"${self.ledger.month_total():.4f} / ${float(self.settings['monthly_budget_usd']):.2f} "
            "| Camera, local wake word, and local TTS: $0 API cost"
        )

    def status(self, text):
        self.events.put(("status", text))

    def _greet(self):
        self.events.put(("greet", "Welcome back. ApexIQ Companion is ready."))

    def toggle_camera(self):
        if self.camera and self.camera.thread and self.camera.thread.is_alive():
            self.camera.stop()
            self.camera_button.configure(text="Enable Camera")
            self.status("Camera stopping")
            return
        self.camera = PresenceCamera(self.settings, self._greet, self.status)
        self.camera.start()
        self.camera_button.configure(text="Disable Camera")

    def toggle_microphone(self):
        if self.microphone and self.microphone.thread and self.microphone.thread.is_alive():
            self.microphone.stop()
            self.mic_button.configure(text="Enable Wake Voice")
            return
        model_path = ROOT / self.settings["vosk_model_path"]
        self.microphone = WakeMicrophone(model_path, self.settings["wake_phrases"],
                                         self._voice_command, self.speaker, self.status)
        try:
            self.microphone.start()
            self.mic_button.configure(text="Disable Wake Voice")
        except Exception as ex:
            messagebox.showerror("Wake voice", str(ex))

    def _voice_command(self, text, should_speak):
        self.events.put(("voice", (text, should_speak)))

    def send(self, deep=False, phrase=None, speak=False):
        if self.working:
            self.write("SYSTEM", "An answer is still being prepared. Try again shortly.")
            return
        message = (self.entry.get() if phrase is None else phrase).strip()
        if not message:
            return
        if phrase is None:
            self.entry.delete(0, "end")
        self.write("YOU", message)
        lowered = message.lower()
        if lowered in ("news", "business news", "brief", "business brief", "what's the news"):
            self.business_news()
            return
        if lowered in ("marketing", "marketing news", "opportunities", "growth"):
            self.marketing_scan()
            return
        if lowered in ("steam", "steam growth", "wishlists", "wishlist"):
            self.steam_growth()
            return
        if lowered in ("cloud", "cloud health", "apexiq cloud"):
            self.cloud_health()
            return
        if lowered in ("status", "usage", "budget"):
            self.write("APEX", f"This month: ${self.ledger.month_total():.4f}. "
                       f"AI requests today: {self.ledger.today_count()}.")
            return
        self.working = True
        self.status_var.set("Thinking (remote API for text only)...")

        def work():
            try:
                result = self.brain.ask(message, deep=deep)
                self.events.put(("reply", (result, speak)))
            except Exception as ex:
                self.events.put(("error", str(ex)))
            finally:
                self.events.put(("idle", None))
        self.executor.submit(work)

    def business_news(self):
        self.write("SYSTEM", "Fetching live headlines from public RSS feeds...")
        topics = list(self.settings["news_topics"])
        def work():
            brief, errors = fetch_brief(topics)
            self.events.put(("news", render_brief(brief, errors)))
        self.executor.submit(work)

    def daily_brief_check(self):
        # Schedule is local to the running app, not an always-active cloud job.
        now = datetime.now()
        statefile = ROOT / "data" / "last_daily_brief.txt"
        last = statefile.read_text(encoding="utf-8").strip() if statefile.exists() else ""
        if 9 <= now.hour < int(self.settings["quiet_hours_start"]) and last != now.date().isoformat():
            statefile.write_text(now.date().isoformat(), encoding="utf-8")
            self.business_news()
        # A separate local once-a-day marketing scan. No paid AI request.
        research_state = ROOT / "data" / "last_marketing_scan.txt"
        researched = research_state.read_text(encoding="utf-8").strip() if research_state.exists() else ""
        if 9 <= now.hour < int(self.settings["quiet_hours_start"]) and researched != now.date().isoformat():
            research_state.write_text(now.date().isoformat(), encoding="utf-8")
            self.marketing_scan(auto=True)
        self.root.after(60_000, self.daily_brief_check)

    def automation_status(self):
        """Report only observable local automation states, never claim cloud sync is live."""
        state = ROOT / "data"
        lines = ["AUTOMATION STATUS (local desktop)",
                 "Daily marketing scan runs after 9 AM while this PC is on and the app is open.",
                 "Daily Steam sync is a separate Supabase Cron job; it runs with the PC off once configured."]
        for file, label in (("last_marketing_scan.txt", "Marketing scan"),
                            ("last_daily_brief.txt", "Business news")):
            p = state / file
            try:
                value = p.read_text(encoding="utf-8").strip() if p.exists() else "never"
            except OSError:
                value = "unavailable"
            lines.append(f"{label} last attempted: {value}")
        self.write("AUTOMATION", "\n".join(lines))

    def connect_cloud(self):
        if not self.cloud:
            messagebox.showinfo("ApexIQ Cloud configuration",
                                "Configure supabase_url and supabase_publishable_key in config.json. "
                                "Use a PUBLISHABLE key, never a service-role or secret key.")
            return
        email = simpledialog.askstring("ApexIQ Cloud", "ApexIQ account email:", parent=self.root)
        if not email:
            return
        password = simpledialog.askstring("ApexIQ Cloud", "Account password (RAM only):",
                                          show="*", parent=self.root)
        if not password:
            return
        self.status_var.set("Authenticating with ApexIQ Cloud...")
        def work(login_email=email.strip(), login_password=password):
            try:
                self.cloud.sign_in(login_email, login_password)
                user_id = self.cloud.user_id()
                self.events.put(("cloud_login", user_id))
            except Exception as ex:
                self.events.put(("error", f"ApexIQ Cloud login: {ex}"))
        self.executor.submit(work)
        del password

    def cloud_health(self):
        if not self.cloud or not self.cloud.signed_in:
            self.write("SYSTEM", "Connect ApexIQ Cloud first. User-scoped RLS login required.")
            return
        self.status_var.set("Reading owner-authorized cloud summaries...")
        def work():
            try:
                snapshot = self.cloud.snapshot()
                self.events.put(("cloud", render_snapshot(snapshot)))
            except Exception as ex:
                self.events.put(("error", f"Cloud health: {ex}"))
        self.executor.submit(work)

    def steam_growth(self):
        if not self.cloud or not self.cloud.signed_in:
            self.write("SYSTEM", "Steam Growth needs ApexIQ Cloud login. "
                       "Steam publisher key stays in Supabase Edge Function secrets.")
            return
        if self.steam_running:
            self.write("SYSTEM", "Steam Growth request already running.")
            return
        self.steam_running = True
        self.status_var.set("Reading private daily Steam wishlist summaries...")
        def work():
            try:
                summary = SteamworksReader(self.cloud).fetch(days=30)
                self.events.put(("steam", render_summary(summary)))
            except Exception as ex:
                self.events.put(("error", f"Steam Growth: {ex}"))
            finally:
                self.events.put(("steam_done", None))
        self.executor.submit(work)

    def marketing_scan(self, auto=False):
        if self.marketing_running:
            if not auto:
                self.write("SYSTEM", "A marketing scan is already in progress.")
            return
        self.marketing_running = True
        if not auto:
            self.write("SYSTEM", "Researching public marketing and competitor headlines. No paid AI calls.")
        self.status_var.set("Marketing research in progress...")
        def work():
            try:
                report = scan_marketing()
                save_report(report, ROOT / "data" / "marketing")
                self.events.put(("marketing", render_marketing(report)))
            except Exception as ex:
                self.events.put(("error", f"Marketing scan: {ex}"))
            finally:
                self.events.put(("marketing_done", None))
        self.executor.submit(work)

    def marketing_insights(self):
        # Paid analysis only on explicit button click, not in the daily scheduler.
        path = ROOT / "data" / "marketing" / "latest.md"
        if not path.exists():
            self.write("SYSTEM", "Run Marketing Scan first; no report is saved yet.")
            return
        from json import loads
        from datetime import timezone
        json_path = ROOT / "data" / "marketing" / (datetime.now(timezone.utc).date().isoformat() + ".json")
        if not json_path.exists():
            self.write("SYSTEM", "Run Marketing Scan today before requesting AI analysis.")
            return
        try:
            report = loads(json_path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as ex:
            self.write("ERROR", f"Cannot open report: {ex}")
            return
        if self.working:
            self.write("SYSTEM", "An AI response is already in progress.")
            return
        self.working = True
        self.status_var.set("Analyzing marketing opportunities (paid AI call)...")
        def work():
            try:
                result = self.brain.ask(analysis_prompt(report), include_history=False, include_notes=False)
                self.events.put(("reply", (result, False)))
            except Exception as ex:
                self.events.put(("error", f"Marketing AI analysis: {ex}"))
            finally:
                self.events.put(("idle", None))
        self.executor.submit(work)

    def clear_context(self):
        self.brain.history.clear()
        self.write("SYSTEM", "Recent conversation context cleared (local notes retained).")

    def open_notes(self):
        os.startfile(str(ROOT / "data" / "apexiq_notes.md"))

    def drain_events(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "status":
                    self.status_var.set(payload)
                    self.write("STATUS", payload)
                    if payload == "Camera stopped":
                        self.camera_button.configure(text="Enable Camera")
                    elif payload == "Microphone stopped":
                        self.mic_button.configure(text="Enable Wake Voice")
                elif kind == "voice":
                    message, speak = payload
                    self.send(phrase=message, speak=speak)
                elif kind == "greet":
                    self.write("APEX", payload)
                    self.speaker.say(payload)
                elif kind == "reply":
                    (text, usd, model), speak = payload
                    self.write("APEX", text + f"\n[Model: {model} | estimated text API cost: ${usd:.5f}]")
                    if speak:
                        self.speaker.say(text[:450])
                    self.update_budget()
                elif kind == "error":
                    self.write("ERROR", payload)
                elif kind == "news":
                    self.write("NEWS", payload)
                elif kind == "cloud_login":
                    self.write("CLOUD", "Signed in with your ApexIQ user account.\n"
                               "Your user UUID for COMPANION_OWNER_USER_ID: " + payload +
                               "\nUse this ID in Supabase Edge Function secrets; never use your password there.")
                elif kind == "cloud":
                    self.write("CLOUD HEALTH", payload)
                elif kind == "steam":
                    self.write("STEAM GROWTH", payload)
                elif kind == "marketing":
                    self.write("MARKETING", payload)
                elif kind == "steam_done":
                    self.steam_running = False
                elif kind == "marketing_done":
                    self.marketing_running = False
                elif kind == "idle":
                    self.working = False
                    self.status_var.set("Ready")
        except queue.Empty:
            pass
        self.root.after(150, self.drain_events)

    def close(self):
        if self.camera:
            self.camera.stop()
        if self.microphone:
            self.microphone.stop()
        self.speaker.shutdown()
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()


def main():
    app = CompanionApp()
    app.root.mainloop()


if __name__ == "__main__":
    main()
