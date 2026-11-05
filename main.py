"""APEX Companion 0.11.0 — local-first business and personal intelligence.

Only owner-authenticated, RLS-scoped Supabase data reaches this desktop.
Background news and marketing are free RSS research; paid AI is user-initiated.
"""
from __future__ import annotations

import json
import os
import queue
import threading
import tkinter as tk
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from tkinter import messagebox, filedialog, simpledialog, scrolledtext
from urllib.parse import urlparse

from companion.settings import ROOT, load_settings, ensure_local_files
from companion.costs import SpendLedger
from companion.assistant import CompanionBrain
from companion.presence import PresenceCamera
from companion.voice import LocalSpeaker, WakeMicrophone, input_devices
from companion.conversation import (
    DEFAULT_WAKE_PHRASES, opening_question, conversational_instructions,
)
from companion.mini_ui import MiniCompanion
from companion.tray import TrayController
from companion.news import fetch_brief
from companion.marketing import scan as scan_marketing, save_report, analysis_prompt
from companion.business_studio import BusinessStudioStore
from companion.business_ui import open_business_studio
from companion.supabase_monitor import SupabaseMonitor
from companion.steamworks import SteamworksReader
from companion.session_store import CloudSessionStore
from companion.ai_context import gather_dashboard_context
from companion.memory import MemoryVault
from companion.live_tools import LiveToolbox
from companion.project_index import ProjectIndexer
from companion.unity_diagnostics import scan_unity_logs
from companion.dev_assistant import WorkspaceGuard, propose_with_ai
from companion.alerts import AlertCenter, cloud_alerts, steam_alerts, beta_alerts
from companion.personal_intelligence import PersonalIntelStore, SCOPES
from companion.intelligence_engine import consolidate, analysis_report, plan_today
from companion.phone_brief import PhoneBriefing
from companion.autonomy import SmallFixAutonomy
from companion.private_imports import EncryptedImportVault
from companion.activity_capture import CoarseActivityCapture
from companion.holographic_ui import HolographicCore
from companion.away_mode import AwayMonitor
from companion.operations_queue import OperationsQueue
from companion.operations_unity import UnityEditModeRunner, VerifiedPatchTrial, project_fingerprint, git_health
from companion.operations_desktop import DesktopInspector
from companion.operations_phone import RemoteOperations
from companion.operations_ui import open_operations_panel
from companion.voice import transcribe_push_to_talk
from companion.dashboard_state import (
    due, readable_count, cloud_status, steam_status, marketing_previews,
    news_previews, local_brief, bounded_ai_context,
)

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

BG = "#080F1A"
SIDE = "#0D1725"
CARD = "#101F30"
CARD2 = "#13283B"
EDGE = "#233B50"
CYAN = "#67E8DB"
BLUE = "#72BFFF"
INK = "#E8F5FC"
MUTED = "#91A8B9"
DIM = "#5F8299"
AMBER = "#F3BE6D"
RED = "#F08485"
FONT = "Segoe UI"
MONO = "Consolas"


def safe_open(url: str) -> bool:
    parsed = urlparse(str(url))
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    webbrowser.open(url, new=2)
    return True


def load_cached_marketing() -> dict | None:
    folder = ROOT / "data" / "marketing"
    for candidate in sorted(folder.glob("????-??-??.json"), reverse=True)[:3] if folder.exists() else []:
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "opportunities" in data:
                return data
        except (ValueError, OSError):
            continue
    return None


class CompanionApp:
    def __init__(self):
        ensure_local_files()
        self.settings = load_settings()
        self.ledger = SpendLedger(ROOT / "data" / "usage.sqlite3")
        self.memory = MemoryVault(ROOT / "data" / "apex_memory.sqlite3")
        self.indexer = ProjectIndexer(ROOT / "data" / "apex_code_index.sqlite3")
        self.alert_center = AlertCenter(ROOT / "data" / "apex_alerts.sqlite3")
        self.personal = PersonalIntelStore(ROOT / "data" / "apex_personal_intel.sqlite3")
        self.business = BusinessStudioStore(ROOT / "data" / "apex_business_studio.sqlite3")
        self._seed_business_graph()
        self.import_vault = EncryptedImportVault(ROOT / "data" / "apex_sensitive_imports.sqlite3",self.personal)
        self.activity_capture = CoarseActivityCapture(self.personal)
        self.away_monitor = AwayMonitor(idle_minutes=self.settings.get("away_idle_minutes", 8),
                                      camera_grace_seconds=self.settings.get("away_camera_grace_seconds",150))
        self.away_active = False
        self.mic_level = 0.0
        self.camera_active = False
        self.microphone_active = False
        self.face_visible = False
        self.phone = PhoneBriefing(ROOT / "data" / "apex_phone_delivery.sqlite3")
        self.autonomy = SmallFixAutonomy(ROOT / "data" / "apex_autofix.sqlite3", ROOT / "data" / "autofix_backups")
        self.ops_queue = OperationsQueue(ROOT / "data" / "apex_operations.sqlite3")
        self.ops_recovered = self.ops_queue.recover_interrupted()
        self.ops_unity_runner = UnityEditModeRunner(ROOT / "data" / "unity_test_runs")
        self.ops_desktop = DesktopInspector(ROOT / "data" / "screen_captures")
        self.ops_remote = RemoteOperations(ROOT / "data" / "apex_remote_commands.sqlite3", self.ops_queue, self.phone)
        self.personal_generation = 0
        self.brain = CompanionBrain(self.settings, self.ledger, memory=self.memory)
        self.approved_project = None
        candidate = self.settings.get("approved_project_root", "")
        if candidate:
            try:
                self.approved_project = WorkspaceGuard(candidate).root
            except (OSError, ValueError):
                pass
        self.unity_report = None
        self.last_unity_signature = None
        self.project_generation = 0
        self.auto_ai_pending = False
        self._ai_request_spoken = False
        self.executor = ThreadPoolExecutor(max_workers=6, thread_name_prefix="ApexIQ")
        self.events = queue.Queue()
        self.store = CloudSessionStore()
        self.speaker = LocalSpeaker(self._async_status,
            backend=self.settings.get("speech_output_backend", "auto"),
            volume=self.settings.get("speech_output_volume", 100),
            voice=self.settings.get("speech_voice_name", "af_heart"))
        self.camera = None
        self.microphone = None
        self.inflight: set[str] = set()
        self.last_try: dict[str, datetime] = {}
        self.last_success: dict[str, datetime] = {}
        self.cloud_snapshot = None
        self.steam_summary = None
        self.marketing_report = load_cached_marketing()
        self.news_brief = None
        self.logged_in_user = None
        self.last_heartbeat_alert = None
        self.session_generation = 0
        self.activity: list[str] = []
        self.activity_file = ROOT / "data" / "activity.jsonl"
        self.cloud = None
        cloud_url = str(self.settings.get("supabase_url") or "")
        cloud_key = str(self.settings.get("supabase_publishable_key") or "")
        if cloud_url and cloud_key.startswith("sb_publishable_"):
            try:
                self.cloud = SupabaseMonitor(cloud_url, cloud_key)
                if self.settings.get("remember_cloud_session", True):
                    self.cloud.on_session_update = self.store.save
            except ValueError:
                self.cloud = None

        self.root = tk.Tk()
        self.root.title("APEX / Business + Personal Companion 0.11.0")
        self.root.withdraw()
        self.compact = self.root.winfo_screenwidth() < 1480 or self.root.winfo_screenheight() < 850
        w = min(1530, max(1120, self.root.winfo_screenwidth() - 50))
        h = min(910, max(710, self.root.winfo_screenheight() - 90))
        self.root.geometry(f"{w}x{h}")
        self.root.minsize(1080, 680)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self.hide_dashboard)
        self._quitting = False
        self.tray = TrayController(lambda action: self.events.put(("tray", action)))
        self._tray_requested = False
        self._make_ui()
        self.voice_topic = "general"
        self.mini = MiniCompanion(self.root,
            on_submit=self._on_mini_submit,
            on_hide=self.hide_mini,
            on_dashboard=self.open_dashboard,
            on_microphone=self.toggle_microphone,
            on_business=lambda:self._start_conversation("business"),
            on_personal=lambda:self._start_conversation("personal"),
            on_stop=self.stop_speaking,
            on_test_voice=self.test_voice, on_voice_setup=self.voice_output_setup,
            on_begin_voice=self.begin_voice_conversation, on_check_ai=self.check_ai_configuration)
        self._update_clock()
        self._animate_orb()
        self._load_previous_activity()
        self._render_all()
        self._chat("APEX", "Business + Personal Companion v0.11.0 initialized. I can inspect approved Unity logs, "
                            "queue bounded work, monitor Git health, and run configured Unity Edit Mode tests. "
                            "Phone commands require private pairing and explicit PHONE permissions. "
                            "I never spend money or deploy changes autonomously.")
        if self.ops_recovered:
            self._activity("Recovery: interrupted operations blocked for owner review; nothing was silently rerun")
        self.root.after(125, self._drain)
        self.root.after(600, self._initialize_tray)
        self.root.after(1400, self._automation_tick)
        if self.marketing_report:
            try:
                last = datetime.fromisoformat(self.marketing_report["created_at_utc"].replace("Z", "+00:00"))
                if last.tzinfo:
                    self.last_try["marketing"] = last
            except (ValueError, KeyError, TypeError):
                pass
        if self.cloud and self.store.read():
            self._restore_cloud()
        if self.settings.get("camera_autostart", False):
            self.root.after(1700, lambda: self.toggle_camera(autostart=True))
        if self.settings.get("microphone_autostart", False):
            self.root.after(2100, lambda: self.toggle_microphone(autostart=True))

    # ----- Small voice-first tray interaction -----
    def _initialize_tray(self):
        self._tray_requested = bool(self.tray.start())
        if not self._tray_requested:
            # Never strand the user behind a missing tray dependency.
            self.show_mini()
        else:
            self.root.after(2200, self._check_tray_ready)

    def _check_tray_ready(self):
        if not self.tray.available and not self._quitting:
            self.show_mini()
            self._activity("Tray unavailable; compact window is visible instead")

    def show_mini(self):
        self.root.withdraw()
        self.mini.show()

    def hide_mini(self):
        if self.tray.available:
            self.mini.hide()
        else:
            # If Windows tray initialization failed, leave a reachable window.
            self.open_dashboard()

    def open_dashboard(self):
        self.mini.hide()
        self.root.deiconify()
        self.root.lift()
        self.show_page("core")

    def hide_dashboard(self):
        self.root.withdraw()
        if not self.tray.available:
            self.show_mini()

    def _on_mini_submit(self, text):
        if self.microphone:
            self.microphone.session.activate(self.microphone.session.mode)
        self.send(phrase=text, speak=True)

    def begin_voice_conversation(self):
        """Explicit foreground action: accept spoken turns without a wake word."""
        active = bool(self.microphone and self.microphone.thread and self.microphone.thread.is_alive()
                      and not self.microphone.stop_event.is_set())
        if not active:
            self.toggle_microphone()
        if not (self.microphone and self.microphone.thread and self.microphone.thread.is_alive()
                and not self.microphone.stop_event.is_set()):
            self.mini.set_recognition_status("VOICE INPUT / MICROPHONE UNAVAILABLE. CHECK VOICE SETUP")
            return
        self.microphone.session.activate(self.voice_topic)
        self.show_mini()
        self.mini.set_recognition_status("CONVERSATION OPEN / YOUR NEXT SPOKEN SENTENCE GOES TO AI")
        self._chat("SYSTEM", "Voice conversation enabled. Speak naturally; the next recognized sentence "
                             "will be sent to your configured AI. Say 'stop listening' to exit.")
        self.speaker.say("I'm listening. What would you like to discuss?")

    def check_ai_configuration(self):
        """Local preflight only. Does not contact OpenAI or consume credits."""
        try:
            self.brain._ensure_ready()
        except Exception as exc:
            # _ensure_ready emits only bounded local readiness reasons; never echo keys.
            message = str(exc)[:160]
            self.mini.set_recognition_status("AI / NOT READY: " + message)
            self._chat("SYSTEM", "AI is not ready: " + message)
            return False
        self.mini.set_recognition_status("AI / ROUTER READY; LIVE MODELS NOT TESTED")
        examples = (("CONVERSATION", "Hello"),
                    ("PLANNING", "Plan our motorcycle beta marketing campaign"),
                    ("CODING", "Fix the Unity C# compiler error"),
                    ("ANALYSIS", "Analyze campaign conversion metrics"))
        previews = []
        if callable(getattr(self.brain, "route_preview", None)):
            for label, example in examples:
                routes = self.brain.route_preview(example).get("candidates", [])
                previews.append(label + ": " + (" -> ".join(routes[:4]) if routes else "not configured"))
        self._chat("SYSTEM", "AI task router configured (offline check only). Live connectivity "
                   "and model quota are checked on real requests.\n" + "\n".join(previews))
        return True

    def _start_conversation(self, mode="general"):
        if self.microphone:
            self.microphone.session.activate(mode)
        self.voice_topic = mode
        self.show_mini()
        question = opening_question(mode)
        self._chat("APEX", question)
        self.speaker.say(question)

    def _voice_wake(self, has_command=False):
        self.show_mini()
        if not has_command:
            question = "I'm here. What's on your mind?"
            self._chat("APEX", question)
            self.speaker.say(question)

    def _voice_sleep(self):
        self.voice_topic = "general"
        self._chat("APEX", "I'll listen for 'Apex' whenever you need me.")
        self.speaker.say("All right. Just say Apex when you need me.")

    def _handle_tray(self, action):
        if action == "tray_ready":
            self.tray.available = True
            if self.settings.get("launch_minimized_to_tray", True):
                self.root.withdraw()
            else:
                self.show_mini()
        elif action == "tray_failed":
            self.tray.available = False
            self.show_mini()
        elif action == "mini":
            self.show_mini()
        elif action == "dashboard":
            self.open_dashboard()
        elif action == "business":
            self._start_conversation("business")
        elif action == "microphone":
            self.toggle_microphone()
        elif action == "microphone_setup":
            self.microphone_setup()
        elif action == "test_voice":
            self.test_voice()
        elif action == "voice_output_setup":
            self.voice_output_setup()
        elif action == "quit":
            self.close()

    def _seed_business_graph(self):
        # Previously confirmed owner project context; no new achievement claims.
        try:
            business=self.personal.add_entity("project","ApexIQ Moto",
                "Motorcycle telemetry and rider-coaching platform",scope="projects",source="owner_input",source_ref="project:apexiq")
            replay=self.personal.add_entity("project","ApexIQ Replay Studio",
                "Unity-based ride replay and analysis; Steam AppID 5384270",
                scope="projects",source="owner_input",source_ref="project:replay")
            cloud=self.personal.add_entity("resource","A.R.I.S Cloud",
                "Owner-authenticated cloud reporting",scope="projects",source="owner_input",source_ref="system:aris_cloud")
            self.personal.link(replay,business,"part_of")
            self.personal.link(cloud,business,"supports")
        except (PermissionError,OSError,ValueError):pass

    def _label(self, parent, text="", size=10, weight="normal", color=INK,
               bg=None, **kw):
        return tk.Label(parent, text=text, font=(FONT, size, weight), fg=color,
                        bg=bg or parent.cget("bg"), **kw)

    def _button(self, parent, text, cmd, accent=False, **kw):
        return tk.Button(parent, text=text, command=cmd,
                         fg=BG if accent else INK, bg=CYAN if accent else CARD2,
                         activebackground="#A7FFF2" if accent else "#1A3852",
                         activeforeground=BG if accent else INK,
                         font=(FONT, 10, "bold"), borderwidth=0, relief="flat",
                         cursor="hand2", padx=9 if self.compact else 12,
                         pady=7 if self.compact else 10, **kw)

    def _panel(self, parent, **pack):
        panel = tk.Frame(parent, bg=CARD, highlightbackground=EDGE, highlightthickness=1)
        if pack:
            panel.pack(**pack)
        return panel

    def _section_heading(self, parent, headline, subtitle):
        f = tk.Frame(parent, bg=parent.cget("bg"))
        f.pack(fill="x", pady=(0, 12))
        self._label(f, headline, 12, "bold", CYAN).pack(anchor="w")
        self._label(f, subtitle, 9, color=MUTED).pack(anchor="w", pady=(4, 0))

    def _make_ui(self):
        # Holographic voice/chat is the default and dominant surface.
        # The original command dashboard remains accessible as INTELLIGENCE.
        shell = tk.Frame(self.root,bg=BG)
        shell.pack(fill="both",expand=True)
        left=tk.Frame(shell,bg=SIDE,width=186 if self.compact else 208,
                      padx=10 if self.compact else 15,pady=12)
        left.pack(side="left",fill="y")
        left.pack_propagate(False)
        self._make_sidebar(left)
        workspace=tk.Frame(shell,bg=BG,padx=14,pady=9)
        workspace.pack(side="left",fill="both",expand=True)
        nav=tk.Frame(workspace,bg=BG)
        nav.pack(fill="x",pady=(0,5))
        self._label(nav,"A P E X   /   C O G N I T I V E   C O N S O L E",12,"bold",CYAN).pack(side="left")
        self.clock=self._label(nav,"",9,color=MUTED)
        self.clock.pack(side="right")
        self.command_page=tk.Frame(workspace,bg=BG)
        self.intelligence_page=tk.Frame(workspace,bg=BG)
        self._make_command_deck(self.command_page)
        self._make_intelligence_screen(self.intelligence_page)
        self.current_page=None
        self.show_page("core")
        self.status_var=tk.StringVar(value="APEX   /   BUSINESS + PERSONAL SERVICES INITIALIZING")
        self._label(workspace,textvariable=self.status_var,size=9,color=DIM).pack(fill="x",pady=(8,0))

    def _make_command_deck(self,parent):
        # One large animated voice core, one large conversation: no tiny chat rail.
        sky=tk.Frame(parent,bg="#06111F",highlightthickness=1,highlightbackground="#23516A")
        sky.pack(fill="x",pady=(0,8))
        self.holo=HolographicCore(sky,height=290 if self.compact else 330)
        self.holo.pack(fill="x")
        control=tk.Frame(parent,bg=BG)
        control.pack(fill="x",pady=(1,9))
        self.sense_var=tk.StringVar(value="INITIALIZING / VOICE & PRESENCE")
        self._label(control,textvariable=self.sense_var,size=9,color=CYAN,weight="bold").pack(side="left",padx=(2,6))
        self.away_var=tk.StringVar(value="LOCAL / ACTIVE")
        self._label(control,textvariable=self.away_var,size=9,color=AMBER).pack(side="right",padx=(4,2))
        self._make_chat_panel(parent)

    def _make_intelligence_screen(self,parent):
        top=tk.Frame(parent,bg=BG)
        top.pack(fill="x",pady=(6,10))
        self._label(top,"INTELLIGENCE / SYSTEM TELEMETRY",12,"bold",CYAN).pack(side="left")
        self._button(top,"RETURN TO APEX",lambda:self.show_page("core"),accent=True).pack(side="right")
        frame=tk.Frame(parent,bg=BG)
        frame.pack(fill="both",expand=True)
        self.canvas=tk.Canvas(frame,bg=BG,highlightthickness=0,borderwidth=0)
        scroll=tk.Scrollbar(frame,orient="vertical",command=self.canvas.yview,bg=CARD)
        scroll.pack(side="right",fill="y")
        self.canvas.pack(side="left",fill="both",expand=True)
        self.canvas.configure(yscrollcommand=scroll.set)
        self.body=tk.Frame(self.canvas,bg=BG,padx=2,pady=2)
        self.body_win=self.canvas.create_window((0,0),window=self.body,anchor="nw")
        self.body.bind("<Configure>",lambda e:self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>",lambda e:self.canvas.itemconfigure(self.body_win,width=e.width))
        self.canvas.bind("<MouseWheel>",lambda e:self.canvas.yview_scroll(-int(e.delta/120),"units"))
        self._make_dashboard(self.body)
        self._make_personal_intelligence(self.body)

    def show_page(self,page):
        if getattr(self,"current_page",None)==page:return
        self.command_page.pack_forget()
        self.intelligence_page.pack_forget()
        if page=="intelligence":
            self.intelligence_page.pack(fill="both",expand=True)
        else:
            self.command_page.pack(fill="both",expand=True)
        self.current_page=page

    def toggle_away_mode(self):
        self.away_monitor.manual_away=not self.away_monitor.manual_away
        self._activity("Away mode "+("manually enabled" if self.away_monitor.manual_away else "returned to automatic detection"))
        self._update_away_mode()

    def _notify_away_transition(self,away):
        if not self.settings.get("phone_brief_enabled",False):return
        if not self.phone.configured():return
        if not self.personal.permitted("operations","phone"):return
        now=datetime.now(timezone.utc)
        fixed=[r for r in self.autonomy.recent(limit=20) if r.get("status")=="static_verified"]
        if away:
            text="APEX AWAY MODE: monitoring authorized Unity logs and cloud alerts. Only bounded, reversible CS0105 C# hygiene edits are allowed. No spending, paid AI, deployment or broad project writes."
        else:
            text=f"APEX PRESENCE RESTORED: unattended edits paused. Previously statically verified C# cleanups in the audit log: {len(fixed)} (not verified by Unity compilation). Check your dashboard for details."
        ident="away:"+("on:" if away else "off:")+now.isoformat()
        self._spawn("phone",lambda:self.phone.send(text,message_type="planning",enabled=True,digest_id=ident),"phone_result")

    def _update_away_mode(self):
        previous=self.away_active
        self.away_active=self.away_monitor.status()
        if previous!=self.away_active:
            self._activity("AWAY / monitoring and safe automation enabled" if self.away_active else
                           "PRESENCE / resumed; unattended code edits paused")
            if not self.away_active:
                self._notify_away_transition(False)
            if self.away_active:
                # Generate a local no-API work queue from already-saved owner goals.
                try:
                    queued=plan_today(self.personal,self.alert_center).get("items",[])
                    if queued:
                        self._activity("AWAY WORK QUEUE: " + str(queued[0].get("title","review alerts"))[:90] + " (proposal only)")
                    else:
                        self._activity("AWAY WORK QUEUE: no evidence-backed tasks; continuing read-only monitoring")
                except (ValueError,PermissionError,OSError):
                    self._activity("AWAY WORK QUEUE unavailable; no action taken")
                self._notify_away_transition(True)
                # The durable job queue survives restarts; no arbitrary model
                # output can add an executable task type.
                if self.approved_project and self.settings.get("ops_auto_away",True):
                    fingerprint=project_fingerprint(self.approved_project)
                    for kind in ("unity_diagnostics","git_health"):
                        try:
                            self.ops_queue.enqueue(kind,origin="away",project_hash=fingerprint,
                                dedupe_key="away:"+datetime.now().date().isoformat()+":"+fingerprint+":"+kind,
                                note="Approved local project work while user away")
                        except (ValueError,PermissionError,RuntimeError):pass
                    if self.settings.get("ops_allow_unity_tests",False) and self.settings.get("unity_editor_path"):
                        try:
                            self.ops_queue.enqueue("unity_editmode_tests",origin="away",project_hash=fingerprint,
                                dedupe_key="away:"+datetime.now().date().isoformat()+":"+fingerprint+":tests")
                        except (ValueError,PermissionError,RuntimeError):pass
                # Continue the v0.7 narrow deterministic, reversible CS0105
                # cleanup; broader C# source changes never occur autonomously.
                if self.approved_project and self.settings.get("autonomous_small_fixes",False):
                    self.last_try.pop("unity",None)
                    self.scan_unity(automatic=True)
        if hasattr(self,"away_btn"):
            self.away_btn.configure(text="END MANUAL AWAY" if self.away_monitor.manual_away else "WORK / AWAY MODE")
        if hasattr(self,"away_var"):
            self.away_var.set(self.away_monitor.mode)
        return self.away_active

    def _make_sidebar(self, parent):
        self._label(parent, "A P E X", 25 if self.compact else 28, "bold", CYAN).pack(anchor="w")
        self._label(parent, "BUSINESS + PERSONAL  /  0.10.0", 8 if self.compact else 9, "bold", MUTED).pack(anchor="w", pady=(0, 15 if self.compact else 27))
        self._label(parent, "CONNECTIONS", 9, "bold", DIM).pack(anchor="w", pady=(0, 8))
        self.connection_text = tk.StringVar(value="A.R.I.S CLOUD\nUSER SIGN-IN REQUIRED")
        self._label(parent, text="", size=10, color=INK, justify="left",
                    textvariable=self.connection_text).pack(anchor="w", pady=(0, 10))
        self.auth_button = self._button(parent, "SIGN IN TO CLOUD", self.sign_in_dialog, accent=True)
        self.auth_button.pack(fill="x", pady=(0, 10 if self.compact else 20))
        self._label(parent,"NAVIGATION",9,"bold",DIM).pack(anchor="w",pady=(0,6))
        self._button(parent,"◉  APEX / HOLOGRAM",lambda:self.show_page("core"),accent=True).pack(fill="x",pady=(0,4))
        self._button(parent,"◈  INTELLIGENCE",lambda:self.show_page("intelligence")).pack(fill="x",pady=(0,4))
        self._button(parent,"◈  BUSINESS STUDIO",self.business_panel).pack(fill="x",pady=(0,4))
        self._button(parent,"◈  PERSONAL INTEL",self.intelligence_panel).pack(fill="x",pady=(0,4))
        self._button(parent,"◈  OPERATIONS",self.operations_panel).pack(fill="x",pady=(0,10))
        self._label(parent, "AUTOMATION", 9, "bold", DIM).pack(anchor="w", pady=(0, 8))
        self._button(parent, "REFRESH EVERYTHING", self.refresh_all).pack(fill="x", pady=(0, 6))
        self._button(parent, "DAILY BRIEFING", self.show_brief).pack(fill="x", pady=6)
        self.away_btn=self._button(parent,"WORK / AWAY MODE",self.toggle_away_mode)
        self.away_btn.pack(fill="x",pady=(4,8))
        self._label(parent, "SENSORS / USER CONTROL", 9, "bold", DIM).pack(anchor="w", pady=(12 if self.compact else 22, 8))
        self.camera_btn = self._button(parent, "CAMERA  •  OFF", self.toggle_camera)
        self.camera_btn.pack(fill="x", pady=6)
        self.mic_btn = self._button(parent, "VOICE  •  OFF", self.toggle_microphone)
        self.mic_btn.pack(fill="x", pady=6)
        self._button(parent, "SELECT MICROPHONE", self.microphone_setup).pack(fill="x", pady=(0,6))
        self.use_context = tk.BooleanVar(value=bool(self.settings.get("send_aggregates_to_ai", True)))
        self.context_cb = tk.Checkbutton(parent, text="Use cloud metrics\nin AI answers",
                                         variable=self.use_context, justify="left", bg=SIDE,
                                         fg=MUTED, activebackground=SIDE, activeforeground=INK,
                                         selectcolor=CARD, font=(FONT, 9), wraplength=148,
                                         command=self._context_changed)
        self.context_cb.pack(anchor="w", pady=(7 if self.compact else 17, 3))
        self._button(parent, "MEMORY / CONTROL", self.manage_memory).pack(fill="x", pady=(5 if self.compact else 12, 0))
        # Local notes remain accessible from INTELLIGENCE; keep the compact sidebar uncluttered.
        if not self.compact:
            self._label(parent, "LOCAL-FIRST\nRead-only monitoring\nNo automatic paid AI calls",
                        9, color=DIM, justify="left").pack(side="bottom", anchor="w")

    def _make_dashboard(self, parent):
        hero = self._panel(parent, fill="x", pady=(0, 13))
        orbital_box = tk.Frame(hero, bg=CARD, width=220 if self.compact else 234, height=226)
        orbital_box.pack(side="left", padx=(16, 4), pady=12)
        orbital_box.pack_propagate(False)
        self.orb = tk.Canvas(orbital_box, width=218, height=218, bg=CARD, bd=0,
                             highlightthickness=0)
        self.orb.pack()
        self.orb.create_oval(25, 25, 193, 193, outline=EDGE, width=2)
        self.orb.create_oval(46, 46, 172, 172, outline="#2B5E72", width=1)
        self.orb.create_oval(63, 63, 155, 155, fill="#123748", outline="#357888", width=1)
        self.orb.create_text(109, 99, text="A P E X", fill=CYAN,
                             font=(FONT, 16, "bold"))
        self.orb.create_text(109, 120, text="AI   C O R E", fill=MUTED,
                             font=(MONO, 8, "bold"))
        self.ring1 = self.orb.create_arc(17, 17, 201, 201, start=0, extent=105,
                                          outline=CYAN, width=3, style="arc")
        self.ring2 = self.orb.create_arc(37, 37, 181, 181, start=180, extent=76,
                                          outline=BLUE, width=3, style="arc")
        self.orb.create_oval(105, 191, 113, 199, fill=CYAN, outline="")
        hero_text = tk.Frame(hero, bg=CARD, padx=16, pady=20)
        hero_text.pack(fill="both", expand=True)
        self.hero_greeting = tk.StringVar(value="YOUR PERSONAL COMMAND CENTER")
        self._label(hero_text, text="", size=12, weight="bold", color=CYAN,
                    textvariable=self.hero_greeting).pack(anchor="w", pady=(5, 10))
        tk.Label(hero_text, text="Everything important. One interface.",
                 font=(FONT, 16 if self.compact else 18, "bold"), fg=INK, bg=CARD,
                 wraplength=360 if self.compact else 465, justify="left",
                 anchor="w").pack(anchor="w")
        self.hero_detail = tk.StringVar(value="Cloud health, Steam growth, news, marketing and assistant controls.")
        self._label(hero_text, text="", size=10, color=MUTED, wraplength=345 if self.compact else 460,
                    textvariable=self.hero_detail, justify="left").pack(anchor="w", pady=(10, 12))
        self.overview_status = tk.StringVar(value="Checking background services")
        self._label(hero_text, text="", size=9 if self.compact else 10, color=BLUE,
                    wraplength=340 if self.compact else 460, justify="left",
                    textvariable=self.overview_status).pack(anchor="w")

        metrics = tk.Frame(parent, bg=BG)
        metrics.pack(fill="x", pady=(0, 13))
        self.kpis = {}
        for i, (ident, label) in enumerate((
            ("cloud", "CLOUD HEARTBEATS"), ("steam", "LATEST WISHLIST ADDS"),
            ("market", "MARKETING SIGNALS"), ("news", "PUBLIC HEADLINES"),
        )):
            card = tk.Frame(metrics, bg=CARD, highlightbackground=EDGE,
                            highlightthickness=1, padx=15, pady=13)
            card.grid(row=0, column=i, padx=(0 if i == 0 else 5, 0), sticky="nsew")
            metrics.grid_columnconfigure(i, weight=1, uniform="kpi")
            self._label(card, label, 8 if self.compact else 9, "bold", DIM,
                        wraplength=140 if self.compact else 190, justify="left").pack(anchor="w")
            value = tk.StringVar(value="--")
            self.kpis[ident] = value
            self._label(card, text="", size=23, weight="bold", color=CYAN,
                        textvariable=value).pack(anchor="w", pady=(4, 1))
            sub = tk.StringVar(value="Awaiting data")
            self.kpis[ident + "_sub"] = sub
            self._label(card, text="", size=9, color=MUTED,
                        textvariable=sub, wraplength=170, justify="left").pack(anchor="w")

        health_row = tk.Frame(parent, bg=BG)
        health_row.pack(fill="x", pady=(0, 13))
        health_row.grid_columnconfigure(0, weight=1, uniform="health")
        health_row.grid_columnconfigure(1, weight=1, uniform="health")
        cloud_card = tk.Frame(health_row, bg=CARD, highlightbackground=EDGE,
                              highlightthickness=1, padx=17, pady=15)
        cloud_card.grid(row=0, column=0, padx=(0, 6), sticky="nsew")
        self._label(cloud_card, "A.R.I.S   /   CLOUD HEALTH", 11, "bold", CYAN).pack(anchor="w")
        self.cloud_heading = tk.StringVar(value="SIGN IN NEEDED")
        self._label(cloud_card, text="", size=14, weight="bold",
                    textvariable=self.cloud_heading).pack(anchor="w", pady=(12, 5))
        self.cloud_sub = tk.StringVar(value="Your project is preconfigured; user authentication is required.")
        self._label(cloud_card, text="", size=9, color=MUTED, wraplength=310,
                    textvariable=self.cloud_sub, justify="left").pack(anchor="w", pady=(0, 15))
        self.cloud_rows = {}
        for name in ("Ride uploads", "ARIS reports", "Beta applications", "Finalized journeys"):
            self.cloud_rows[name] = self._data_row(cloud_card, name)

        steam_card = tk.Frame(health_row, bg=CARD, highlightbackground=EDGE,
                              highlightthickness=1, padx=17, pady=15)
        steam_card.grid(row=0, column=1, padx=(6, 0), sticky="nsew")
        self._label(steam_card, "REPLAY STUDIO   /   STEAMWORKS", 11, "bold", CYAN).pack(anchor="w")
        self.steam_heading = tk.StringVar(value="AWAITING USER SESSION")
        self._label(steam_card, text="", size=14, weight="bold",
                    textvariable=self.steam_heading).pack(anchor="w", pady=(12, 5))
        self.steam_sub = tk.StringVar(value="Daily wishlist activity; not total wishlist count.")
        self._label(steam_card, text="", size=9, color=MUTED, wraplength=320,
                    textvariable=self.steam_sub, justify="left").pack(anchor="w", pady=(0, 15))
        self.steam_rows = {}
        for key, name in (("date", "Report date"), ("deletes", "Wishlist removals"),
                          ("purchases", "Wishlist purchases"), ("coverage", "Last 7 days covered")):
            self.steam_rows[key] = self._data_row(steam_card, name)

        market = self._panel(parent, fill="x", pady=(0, 13))
        self._section_in_panel(market, "MARKETING   /   OPPORTUNITY RADAR",
                               "Source-linked ideas; no outreach is sent without your approval.")
        self.marketing_holder = tk.Frame(market, bg=CARD, padx=17, pady=2)
        self.marketing_holder.pack(fill="x", padx=0, pady=(0, 13))
        self.marketing_meta = tk.StringVar(value="Standing campaign ideas; scan in progress.")
        self._label(market, text="", textvariable=self.marketing_meta, size=9,
                    color=DIM).pack(anchor="w", padx=17, pady=(0, 14))

        news_panel = self._panel(parent, fill="x", pady=(0, 13))
        self._section_in_panel(news_panel, "DAILY INTELLIGENCE   /   INDUSTRY & BUSINESS",
                               "Public RSS research refreshes automatically while Companion is running.")
        self.news_holder = tk.Frame(news_panel, bg=CARD, padx=17)
        self.news_holder.pack(fill="x", pady=(0, 10))
        self.news_meta = tk.StringVar(value="Searching public news feeds.")
        self._label(news_panel, text="", textvariable=self.news_meta, color=DIM,
                    size=9).pack(anchor="w", padx=17, pady=(0, 14))

        development = self._panel(parent, fill="x", pady=(0, 12))
        self._section_in_panel(development, "DEVELOPMENT   /   PROJECT CONTEXT",
                               "Local projects remain private; no unrestricted disk or server control.")
        self._label(development, "Unity / Replay Studio   •   Hardware telemetry   •   Cloud services",
                    10, color=INK, wraplength=680, justify="left").pack(anchor="w", padx=17, pady=(0, 8))
        self.dev_status = tk.StringVar(value="No local project approved. Choose a folder to enable diagnostics.")
        self._label(development, text="", textvariable=self.dev_status,
                    size=9, color=MUTED, wraplength=685, justify="left").pack(anchor="w", padx=17, pady=(0, 10))
        dev_buttons = tk.Frame(development, bg=CARD, padx=17)
        dev_buttons.pack(fill="x", pady=(0, 12))
        for label, handler in (("CHOOSE UNITY FOLDER", self.choose_project),
                               ("INDEX CODE", self.index_project),
                               ("SCAN UNITY ERRORS", self.scan_unity),
                               ("PROPOSE CODE FIX", self.propose_patch)):
            self._button(dev_buttons, label, handler).pack(side="left", padx=(0,7), pady=(2,0))
        revoke_line = tk.Frame(development,bg=CARD,padx=17)
        revoke_line.pack(fill="x",pady=(0,12))
        self._button(revoke_line,"REVOKE PROJECT ACCESS",self.revoke_project).pack(side="left")
        self._label(revoke_line,"Editor.log access is opt-in when choosing a folder.",9,color=DIM).pack(side="left",padx=9)
        alerts_frame = self._panel(parent, fill="x", pady=(0, 13))
        self._section_in_panel(alerts_frame, "APEX / PROACTIVE ALERTS",
                               "Local status transitions and development warnings. No external messages or paid AI required.")
        self.alerts_summary = tk.StringVar(value="No new alerts")
        self._label(alerts_frame, text="", textvariable=self.alerts_summary, size=10,
                    color=AMBER, wraplength=680, justify="left").pack(anchor="w", padx=17, pady=(0,12))

    def _make_personal_intelligence(self,parent):
        panel=self._panel(parent,fill="x",pady=(1,15))
        self._section_in_panel(panel,"APEX / PERSONAL INTELLIGENCE 0.7",
                               "Knowledge graph  /  activity  /  planner  /  permissions  /  limited autonomy")
        self.intel_summary=tk.StringVar(value="Local intelligence initialized; sensitive sources disabled")
        self._label(panel,textvariable=self.intel_summary,size=9,color=MUTED,wraplength=580,
                    justify="left").pack(anchor="w",padx=14,pady=(1,8))
        r1=tk.Frame(panel,bg=CARD);r1.pack(fill="x",padx=14,pady=(0,6))
        self._button(r1,"INTELLIGENCE / PLAN",self.intelligence_panel).pack(side="left",fill="x",expand=True,padx=(0,4))
        self._button(r1,"DATA PERMISSIONS",self.permissions_panel).pack(side="left",fill="x",expand=True,padx=(4,0))
        r2=tk.Frame(panel,bg=CARD);r2.pack(fill="x",padx=14,pady=(0,12))
        self.autofix_btn=self._button(r2,"AUTO SMALL FIX  /  ON",self.toggle_small_fixes)
        self.autofix_btn.pack(side="left",fill="x",expand=True,padx=(0,4))
        self._button(r2,"PHONE BRIEFING",self.phone_panel).pack(side="left",fill="x",expand=True,padx=(4,0))
        self._button(panel,"OPEN LOCAL NOTES",self.open_notes).pack(anchor="w",padx=14,pady=(0,12))

    def intelligence_panel(self):
        dialog=tk.Toplevel(self.root)
        dialog.title("APEX / Personal Intelligence & Daily Plan")
        dialog.geometry("940x700")
        dialog.configure(bg=SIDE)
        self._label(dialog,"PERSONAL INTELLIGENCE  /  EVIDENCE-BASED",14,"bold",CYAN).pack(anchor="w",padx=16,pady=(16,8))
        self._label(dialog,"Only authorized sources. Date and provenance included. No psychological conclusions from sparse logs.",
                    9,color=MUTED).pack(anchor="w",padx=16)
        out=scrolledtext.ScrolledText(dialog,bg=CARD,fg=INK,font=(MONO,10),wrap="word",relief="flat")
        out.pack(fill="both",expand=True,padx=16,pady=12)
        def render():
            report=analysis_report(self.personal,memory=self.memory)
            timeline=self.personal.timeline(limit=15,days=30)
            insights=self.personal.list_insights(limit=8)
            permissions=self.personal.permissions()
            data={"knowledge_graph":self.personal.graph_snapshot(limit=40),
                  "today_plan":report["plan"],"observed_trends":report["trends"],
                  "topic_clusters":report["topic_clusters"],"recent_activity":timeline,
                  "consolidated_insights":insights,
                  "permissions":permissions,"autonomous_fix_history":self.autonomy.recent(limit=8)}
            out.configure(state="normal");out.delete("1.0","end")
            out.insert("1.0",json.dumps(data,ensure_ascii=False,indent=2))
            out.configure(state="disabled")
        bar=tk.Frame(dialog,bg=SIDE);bar.pack(fill="x",padx=16,pady=(0,14))
        def add_goal():
            title=simpledialog.askstring("Add a goal","Goal or task:",parent=dialog)
            if not title:return
            rationale=simpledialog.askstring("Goal context","Why it matters (optional):",parent=dialog) or ""
            try:
                self.personal.add_plan(title,rationale,scope="projects",priority=2)
                self.personal.add_entity("goal",title,rationale,scope="projects",source="owner_input")
                self._activity("Owner saved a new development goal")
                render()
            except (PermissionError,ValueError) as e:messagebox.showerror("Goal not saved",str(e),parent=dialog)
        def consolidate_now():
            item=consolidate(self.personal,self.memory)
            self._activity("Explicit memories consolidated (local only): "+str(item.get("imported")))
            render()
        def mark_goal():
            ident=simpledialog.askinteger("Complete a saved goal","Goal/task numeric ID:",parent=dialog)
            if ident is not None:
                if not self.personal.update_plan(ident,"done"):
                    messagebox.showwarning("Unknown task","No accessible task with that ID",parent=dialog)
                render()
        def add_fact():
            title=simpledialog.askstring("Graph fact","Project fact, decision or observation:",parent=dialog)
            if not title:return
            details=simpledialog.askstring("Graph evidence","Details as you know them today:",parent=dialog) or ""
            try:
                node=self.personal.add_entity("observation",title,details,scope="projects",source="owner_input")
                business=self.personal.add_entity("project","ApexIQ Moto","Motorcycle telemetry and rider coaching",
                    scope="projects",source="owner_input",source_ref="project:apexiq")
                if node!=business:self.personal.link(node,business,"related_to")
                self._activity("Owner created a source-labelled graph fact")
                render()
            except (PermissionError,ValueError) as ex:messagebox.showerror("Fact not saved",str(ex),parent=dialog)
        self._button(bar,"ADD GOAL",add_goal).pack(side="left",padx=(0,6))
        self._button(bar,"ADD FACT",add_fact).pack(side="left",padx=(0,6))
        self._button(bar,"CONSOLIDATE MEMORIES",consolidate_now).pack(side="left",padx=(0,6))
        self._button(bar,"IMPORT FILE",lambda:self.import_personal_file(dialog,render)).pack(side="left",padx=(0,6))
        self._button(bar,"COMPLETE GOAL",mark_goal).pack(side="left",padx=(0,6))
        bar2=tk.Frame(dialog,bg=SIDE);bar2.pack(fill="x",padx=16,pady=(0,10))
        def undo_last_autofix():
            if not self.approved_project:
                messagebox.showwarning("No approved project","Choose and approve your Unity folder first",parent=dialog);return
            if not messagebox.askyesno("Restore last small automatic fix",
                 "Restore the original file from the last automatic fix backup?\n"
                 "If the file has changed since the fix, APEX will refuse to overwrite it.",parent=dialog):return
            try:
                restored=self.autonomy.rollback_last(WorkspaceGuard(self.approved_project),approved=True)
                self.personal.audit("autofix_rollback","restored","CS0105 backup restored")
                self._activity("Owner rolled back last small Unity source fix")
                self.index_project()
                render()
                messagebox.showinfo("Restored",restored["file"]+" restored. Verify in Unity.",parent=dialog)
            except (OSError,ValueError,PermissionError,RuntimeError) as error:
                messagebox.showerror("Rollback not performed",str(error),parent=dialog)
        self._button(bar2,"UNDO LAST AUTO-FIX",undo_last_autofix).pack(side="left",padx=(0,6))
        self._button(bar2,"REFRESH",render).pack(side="left",padx=(0,6))
        self._button(bar2,"CLOSE",dialog.destroy).pack(side="right")
        render()

    def import_personal_file(self,parent=None,after=None):
        scope=simpledialog.askstring("Import data into APEX","Category (must be enabled in Data Permissions):\n"+", ".join(SCOPES),parent=parent or self.root)
        if not scope:return
        scope=scope.lower().strip()
        if not self.personal.permitted(scope,"local"):
            messagebox.showwarning("Permission required","Enable "+scope+" / LOCAL first in DATA PERMISSIONS.",parent=parent or self.root);return
        selected=filedialog.askopenfilename(parent=parent or self.root,title="Select a local CSV, JSON, ICS or TXT export",
                filetypes=[("Approved exports","*.csv *.json *.ics *.txt"),("All","*.*")])
        if not selected:return
        try:
            preview=self.import_vault.preview(selected)
        except (ValueError,OSError,UnicodeError) as ex:
            messagebox.showerror("Invalid import",str(ex),parent=parent or self.root);return
        if not messagebox.askyesno("Encrypt local selected data",
                f"Import {preview['rows']} records as {scope}?\nFields: {', '.join(preview['sample_fields'][:11])}\n\n"
                "Only an explicitly selected file is read. Records are encrypted in local SQLite using Windows Credential Manager. "
                "No AI sharing unless that category's separate AI permission is enabled.",parent=parent or self.root):return
        try:
            outcome=self.import_vault.import_file(selected,scope)
            self._activity("Encrypted owner-selected "+scope+" import: "+str(outcome["imported"])+" records")
            if after:after()
        except (RuntimeError,PermissionError,ValueError,OSError) as ex:
            messagebox.showerror("Import refused",str(ex),parent=parent or self.root)

    def permissions_panel(self):
        dialog=tk.Toplevel(self.root)
        dialog.title("APEX / Scoped Data Permissions")
        dialog.geometry("780x650");dialog.configure(bg=SIDE)
        self._label(dialog,"SOURCE PERMISSIONS  /  OPT-IN",15,"bold",CYAN).pack(anchor="w",padx=16,pady=(15,8))
        self._label(dialog,"Local: store/retrieve  •  AI: send bounded matching context  •  Phone: allow digest metadata",
                    10,color=MUTED).pack(anchor="w",padx=16,pady=(0,10))
        current=self.personal.permissions();controls={}
        for scope in SCOPES:
            row=tk.Frame(dialog,bg=CARD);row.pack(fill="x",padx=16,pady=3)
            self._label(row,scope.upper(),10,"bold",INK,width=17,anchor="w").pack(side="left",padx=7,pady=4)
            controls[scope]={}
            for field in ("local","ai","phone"):
                var=tk.BooleanVar(value=current[scope][field]);controls[scope][field]=var
                tk.Checkbutton(row,text=field.upper(),variable=var,bg=CARD,fg=INK,
                               selectcolor=SIDE,activebackground=CARD,activeforeground=INK,
                               font=(FONT,9)).pack(side="left",padx=7)
        foreground=tk.BooleanVar(value=bool(self.settings.get("foreground_app_sampling",False)))
        tk.Checkbutton(dialog,text="Observe foreground executable NAMES once per minute (never window titles, keystrokes or screenshots)",
                       variable=foreground,bg=SIDE,fg=INK,selectcolor=SIDE,
                       activebackground=SIDE,activeforeground=INK).pack(anchor="w",padx=16,pady=(10,0))
        self._label(dialog,"Sensitive categories start OFF. Revocation blocks future reads; use ERASE to delete stored records.",
                    9,color=AMBER,wraplength=735,justify="left").pack(anchor="w",padx=16,pady=12)
        bar=tk.Frame(dialog,bg=SIDE);bar.pack(fill="x",padx=16,pady=8)
        def save():
            try:
                for scope,opts in controls.items():
                    vals={k:bool(v.get()) for k,v in opts.items()}
                    self.personal.set_permission(scope,**vals)
                self._persist_setting("foreground_app_sampling",bool(foreground.get()))
                self.personal_generation+=1
                self._activity("Personal intelligence permissions changed")
                self._render_all();dialog.destroy()
            except ValueError as ex:messagebox.showerror("Invalid permissions",str(ex),parent=dialog)
        def erase():
            scope=simpledialog.askstring("Erase a data category","Category to erase: "+", ".join(SCOPES),parent=dialog)
            if not scope:return
            if scope not in SCOPES:messagebox.showerror("Category unknown","Use a listed category",parent=dialog);return
            if messagebox.askyesno("Erase scope permanently",f"Delete all locally stored {scope} graph nodes, events, goals and insights? This does not erase existing legacy chat memory.",parent=dialog):
                self.personal.erase_scope(scope)
                self.import_vault.erase_scope(scope)
                self.personal_generation+=1
                self._activity("Erased scoped personal intelligence data: "+scope)
        self._button(bar,"SAVE PERMISSIONS",save,accent=True).pack(side="left",padx=(0,8))
        self._button(bar,"ERASE A CATEGORY",erase).pack(side="left",padx=(0,8))
        self._button(bar,"CLOSE",dialog.destroy).pack(side="right")

    def toggle_small_fixes(self):
        value=not bool(self.settings.get("autonomous_small_fixes",True))
        if value:
            if not self.approved_project:
                messagebox.showinfo("Approve workspace","Choose your Unity project folder before enabling unattended fixes.")
                return
            if not messagebox.askyesno("Enable limited autonomy",
                    "Permit ONLY compiler-identified CS0105 duplicate-using cleanup inside first-party Assets/*.cs files? "
                    "Maximum 2 per day, each backed up. No paid AI, scripts, installs, deployments, purchases or broad edits. "
                    "Unity still needs manual compilation after an edit.",parent=self.root):return
        if self._persist_setting("autonomous_small_fixes",value):
            self._activity("Limited automatic code fixes "+("enabled" if value else "disabled"))
            self._render_all()

    def operations_panel(self):
        open_operations_panel(self)

    def business_panel(self):
        open_business_studio(self)
        self._activity("Opened private Business Studio; no network calls or publishing")

    def business_brief(self):
        self._chat("APEX / BUSINESS", self.business.analysis())
        self._activity("Local business funnel report generated without paid AI")


    def analyze_screenshot(self, image_path):
        if not (self.personal.permitted("computer","local") and self.personal.permitted("computer","ai")):
            self._chat("SYSTEM","AI screenshot analysis needs COMPUTER / LOCAL and COMPUTER / AI permissions.")
            return
        if "ai" in self.inflight:
            self._chat("SYSTEM","Wait for the current AI request to finish before analyzing an image.")
            return
        from pathlib import Path
        dest=Path(image_path).expanduser().resolve()
        allowed=(ROOT/"data"/"screen_captures").resolve()
        if not dest.is_relative_to(allowed) or not dest.is_file():
            self._chat("SYSTEM","Only a locally captured, explicitly approved APEX screenshot can be analyzed.")
            return
        def work():
            return (self.brain.inspect_owner_screenshot(dest,
                    prompt="Describe the visible software interface and relevant development errors, with actionable diagnostics."),False)
        if self._spawn("ai",work,"ai_data"):
            self._chat("SYSTEM","Analyzing the ONE screenshot you approved. This is a paid API request; no further screen sharing is enabled.")

    def enqueue_operation(self,kind,origin="desktop"):
        from companion.operations_queue import ALLOWED_KINDS
        if kind not in ALLOWED_KINDS:
            self._chat("SYSTEM","That operation is not on the allowed task list.")
            return None
        if self.ops_queue.paused():
            self._chat("SYSTEM","Operations are paused. Resume in OPERATIONS before adding work.")
            return None
        if kind=="desktop_inspect":
            if origin!="desktop" or not self.personal.permitted("computer","local"):
                self._chat("SYSTEM","Grant computer/LOCAL in Data Permissions first; desktop inspection is manual only.")
                return None
        else:
            if not self.approved_project or not self.personal.permitted("projects","local"):
                self._chat("SYSTEM","Choose and approve a Unity project and PROJECTS / LOCAL permission first.")
                return None
        if kind=="unity_editmode_tests":
            if not self.settings.get("ops_allow_unity_tests",False):
                self._chat("SYSTEM","Enable Unity Edit Mode tests in OPERATIONS first.")
                return None
            if not self.settings.get("unity_editor_path"):
                self._chat("SYSTEM","Choose the installed Unity.exe in OPERATIONS first.")
                return None
        try:
            tid=self.ops_queue.enqueue(kind,origin=origin,project_hash=project_fingerprint(self.approved_project) if self.approved_project else "")
        except (PermissionError,RuntimeError,ValueError) as exc:
            self._chat("SYSTEM","Unable to queue task: "+str(exc)[:150]);return None
        self._activity("Operations task queued: "+kind)
        self.root.after(120,self._ops_tick)
        return tid

    def _execute_operation(self,task):
        kind=task["kind"]
        if self.ops_queue.paused():return {"state":"blocked","reason":"Operations paused"}
        if kind=="desktop_inspect":
            if task["origin"]!="desktop" or not self.personal.permitted("computer","local"):
                return {"state":"blocked","reason":"Desktop inspection authorization unavailable"}
            return self.ops_desktop.active_window(permitted=True,read_controls=True)
        project=self.approved_project
        if (not project or not self.personal.permitted("projects","local") or
            project_fingerprint(project)!=task.get("project_hash")):
            return {"state":"blocked","reason":"Project authorization is missing or changed"}
        if task["origin"]=="away" and not self.away_monitor.status():
            return {"state":"blocked","reason":"User returned before unattended operation began"}
        if kind=="unity_diagnostics":
            report=scan_unity_logs(project,include_editor_log=bool(self.settings.get("unity_include_editor_log",False)))
            return {"state":"completed","sampled_errors":report["sampled_errors"],
                    "sampled_warnings":report["sampled_warnings"],"sources":len(report["log_sources"]),
                    "checked_at_utc":report["checked_at_utc"],
                    "note":"Local approved log sampling; inspect Unity console for exact errors."}
        if kind=="git_health":
            report=git_health(project)
            return {"state":"completed",**report}
        if kind=="unity_editmode_tests":
            if not self.settings.get("ops_allow_unity_tests",False):
                return {"state":"blocked","reason":"Unity tests not enabled"}
            exe=self.settings.get("unity_editor_path","")
            if not exe:return {"state":"blocked","reason":"Unity.exe has not been configured"}
            try:
                return self.ops_unity_runner.run(project,exe,timeout_seconds=self.settings.get("ops_unity_timeout",420))
            except (ValueError,PermissionError,OSError,RuntimeError) as exc:
                return {"state":"blocked","reason":str(exc)[:150]}
        return {"state":"blocked","reason":"Operation not recognized"}

    def _ops_tick(self):
        if "operations_task" in self.inflight or self.ops_queue.paused():return
        if not self.ops_queue.counts().get("queued",0):return
        def work():
            task=self.ops_queue.claim()
            if task is None:return None
            try:
                result=self._execute_operation(task)
                state="blocked" if result.get("state")=="blocked" else (
                    "failed" if result.get("state") in ("failed","unavailable","unsupported","not_a_repository") else "completed")
            except Exception:
                result={"state":"failed","reason":"Operation failed safely; check configuration"};state="failed"
            self.ops_queue.finish(task["task_id"],state,result=result,error_code=str(result.get("state",""))[:50])
            return task["task_id"],task["kind"],state,result
        self._spawn("operations_task",work,"operations_data")

    def _phone_remote_tick(self):
        if not (self.settings.get("ops_phone_commands",False) and
                self.settings.get("phone_brief_enabled",False) and
                self.personal.permitted("operations","phone") and self.phone.configured()):
            return
        if not due(self.last_try.get("phone_remote"),1):return
        self.last_try["phone_remote"]=datetime.now(timezone.utc)
        def work():
            messages=self.ops_remote.poll(authorized=True,approved_project=bool(self.approved_project),
                                          status_line="No spending, deployments, or remote code edits allowed")
            summaries=[]
            for m in messages:
                if "reply" not in m:continue
                answer=self.phone.send(m["reply"],message_type="planning",enabled=True,
                    digest_id="cmd:"+str(m["update_id"]))
                summaries.append(m.get("command","")+":"+str(answer.get("status","unknown")))
            return {"commands":summaries,"count":len(summaries)}
        self._spawn("phone_commands",work,"phone_commands_data")

    def phone_panel(self):
        dialog=tk.Toplevel(self.root);dialog.title("APEX / Phone Briefings")
        dialog.geometry("710x455");dialog.configure(bg=SIDE)
        self._label(dialog,"PHONE BRIEFING  /  TELEGRAM (OPT-IN)",14,"bold",CYAN).pack(anchor="w",padx=16,pady=(17,10))
        explanation=("1. In Telegram, create a private bot with @BotFather.\n"
                     "2. Start a direct chat with your bot and obtain your personal numeric chat ID.\n"
                     "3. Run Pair_Phone.cmd in your Companion installation folder.\n"
                     "4. Restart Companion. Turn on phone briefs here; then send a test.\n\n"
                     "Only a compact, sanitized summary goes to Telegram. No logs, keys, GPS coordinates, financial records or code.\n"
                     "It sends at your configured briefing hour while this PC and Companion are running.")
        self._label(dialog,explanation,10,color=INK,justify="left",wraplength=670).pack(anchor="w",padx=16,pady=12)
        status=tk.StringVar(value="Telegram bot credentials: "+("CONFIGURED" if self.phone.configured() else "NOT CONFIGURED"))
        self._label(dialog,textvariable=status,color=AMBER,size=10).pack(anchor="w",padx=16,pady=(0,8))
        enabled=tk.BooleanVar(value=bool(self.settings.get("phone_brief_enabled",False)))
        tk.Checkbutton(dialog,text="ENABLE DAILY PHONE BRIEF",variable=enabled,bg=SIDE,fg=INK,
                       selectcolor=SIDE,activebackground=SIDE,activeforeground=INK).pack(anchor="w",padx=16)
        bar=tk.Frame(dialog,bg=SIDE);bar.pack(fill="x",padx=16,pady=14)
        def save():
            self._persist_setting("phone_brief_enabled",bool(enabled.get()))
            self._activity("Phone digest "+("enabled" if enabled.get() else "disabled"))
            dialog.destroy()
        def send_test():
            if not self.phone.configured():messagebox.showwarning("Not configured","Run Pair_Phone.cmd in your Companion folder, then restart.",parent=dialog);return
            def do_test():
                return self.phone.send("APEX / test briefing: private phone channel connected. No account or project secrets included.",
                                       enabled=True,message_type="summary",digest_id="test:"+datetime.now(timezone.utc).isoformat())
            self._spawn("phone",do_test,"phone_result")
            messagebox.showinfo("Test queued","Check Telegram and the APEX activity feed for the result.",parent=dialog)
        self._button(bar,"SAVE",save,accent=True).pack(side="left",padx=(0,8))
        self._button(bar,"SEND TEST",send_test).pack(side="left",padx=(0,8))
        self._button(bar,"CLOSE",dialog.destroy).pack(side="right")

    def _free_phone_brief(self):
        if not self.settings.get("phone_brief_enabled",False):return
        hour=datetime.now().hour
        if hour<int(self.settings.get("phone_brief_hour",9)):return
        if not self.phone.configured():return
        today_local=datetime.now().date().isoformat()
        if self.phone.delivered("daily:"+today_local):return
        if not due(self.last_try.get("phone"),60):return
        self.last_try["phone"]=datetime.now(timezone.utc)
        recent=self.autonomy.recent(limit=15)
        today=datetime.now(timezone.utc).date().isoformat()
        count=sum(1 for r in recent if r["at_utc"].startswith(today) and r["status"]=="static_verified")
        parts=["APEX daily operations report - "+datetime.now().date().isoformat()]
        if self.personal.permitted("operations","phone"):
            fresh=str((self.cloud_snapshot or {}).get("device_freshness","unknown"))
            parts.append("Latest visible device heartbeat: "+fresh)
            steam=(self.steam_summary or {})
            if steam.get("status")=="ok":
                latest=steam.get("latest") or {}
                parts.append("Steam "+str(steam.get("latest_date"))+": "+str(latest.get("wishlist_adds","?"))+" additions (daily, not total)")
            parts.append("Unacknowledged alerts: "+str(len(self.alert_center.recent(only_unread=True))))
            counts=self.ops_queue.counts()
            parts.append("Local operations: "+str(counts.get("completed",0))+" completed, "+
                         str(counts.get("blocked",0))+" blocked, "+str(counts.get("queued",0))+" waiting")
            last=self.ops_queue.recent(1)
            if last:
                parts.append("Latest work: "+last[0]["kind"].replace("_"," ")+" / "+last[0]["status"])
        if self.personal.permitted("projects","phone"):
            parts.append("Small C# repairs statically verified today: "+str(count))
        else:
            parts.append("Project repair details excluded by PHONE permissions")
        if not self.personal.permitted("operations","phone"):
            parts.append("Operational metrics excluded: enable OPERATIONS / PHONE in Data Permissions")
        self._spawn("phone",lambda:self.phone.send("\n".join(parts),message_type="summary",enabled=True,
                                         digest_id="daily:"+datetime.now().date().isoformat()),"phone_result")

    def _data_row(self, parent, label):
        bar = tk.Frame(parent, bg=CARD)
        bar.pack(fill="x", pady=(0, 10))
        self._label(bar, label, 10, color=MUTED).pack(side="left")
        data = tk.StringVar(value="--")
        self._label(bar, text="", size=10, weight="bold", color=INK,
                    textvariable=data).pack(side="right")
        return data

    def _section_in_panel(self, parent, title, sub):
        header = tk.Frame(parent, bg=CARD, padx=17, pady=15)
        header.pack(fill="x")
        self._label(header, title, 11, "bold", CYAN).pack(anchor="w")
        self._label(header, sub, 9, color=MUTED, wraplength=690,
                    justify="left").pack(anchor="w", pady=(5, 0))

    def _make_chat_panel(self,parent):
        # This pane fills the main screen. The editor is deliberately wide.
        heading=tk.Frame(parent,bg=BG)
        heading.pack(fill="x",pady=(0,7))
        self._label(heading,"NEURAL CONVERSATION / FULL CONTEXT",12,"bold",CYAN).pack(side="left")
        self.ai_context_status=tk.StringVar(value="AI CLOUD CONTEXT  /  INITIALIZING")
        self._label(heading,textvariable=self.ai_context_status,size=9,color=MUTED).pack(side="right")
        action_bar=tk.Frame(parent,bg=BG)
        action_bar.pack(fill="x",pady=(0,7))
        self._button(action_bar,"VOICE INPUT",self.push_to_talk).pack(side="left",padx=(0,6))
        self._button(action_bar,"SILENCE",self.stop_speaking).pack(side="left",padx=(0,6))
        self._button(action_bar,"ALERTS",self.show_alerts).pack(side="left",padx=(0,6))
        self._button(action_bar,"DAILY BRIEF",self.show_brief).pack(side="left",padx=(0,6))
        self._button(action_bar,"CLOUD CONTEXT",self.toggle_context).pack(side="left",padx=(0,6))
        self.auto_brief_btn=self._button(action_bar,"PAID AUTO AI • OFF",self.toggle_auto_ai_brief)
        self.auto_brief_btn.pack(side="right")
        chat_border=tk.Frame(parent,bg=CARD,highlightbackground="#245779",highlightthickness=1)
        chat_border.pack(fill="both",expand=True,pady=(0,9))
        self.chat=tk.Text(chat_border,wrap="word",bg="#071C2B",fg=INK,
                          insertbackground=CYAN,font=(FONT,12),borderwidth=0,
                          relief="flat",padx=22,pady=15,spacing1=6,spacing2=4,
                          height=8,width=1,state="disabled",selectbackground="#24637A")
        self.chat.pack(fill="both",expand=True)
        self.chat.tag_config("speaker",foreground=CYAN,font=(FONT,10,"bold"),spacing1=10)
        self.chat.tag_config("message",foreground=INK,font=(FONT,12))
        self.chat.tag_config("user",foreground="#B6CBFF",font=(FONT,12))
        row=tk.Frame(parent,bg=BG)
        row.pack(fill="x",pady=(0,7))
        self.entry=tk.Entry(row,bg="#0D283B",fg=INK,insertbackground=CYAN,
                            font=(FONT,13),relief="flat",borderwidth=0)
        self.entry.pack(side="left",fill="x",expand=True,ipady=13,padx=(0,9))
        self.entry.bind("<Return>",lambda e:self.send())
        self._button(row,"SEND  ↗",self.send,accent=True).pack(side="right",padx=(0,6))
        self._button(row,"DEEP",lambda:self.send(deep=True)).pack(side="right",padx=(0,6))
        foot=tk.Frame(parent,bg=BG)
        foot.pack(fill="x",pady=(0,3))
        self._label(foot,"ACTIVITY / AUDIT TRAIL",9,"bold",DIM).pack(side="left")
        self.budget_var=tk.StringVar(value="")
        self._label(foot,textvariable=self.budget_var,size=9,color=MUTED).pack(side="right")
        feed_frame=tk.Frame(parent,bg=CARD,highlightbackground=EDGE,highlightthickness=1,height=55)
        feed_frame.pack(fill="x")
        feed_frame.pack_propagate(False)
        self.feed=tk.Text(feed_frame,bg="#0C2435",fg=MUTED,font=(MONO,9),wrap="word",
                          relief="flat",borderwidth=0,padx=11,pady=6,state="disabled")
        self.feed.pack(fill="both",expand=True)

    def _chat(self, author, text):
        self.chat.configure(state="normal")
        self.chat.insert("end", author.upper() + "  •  " + datetime.now().strftime("%H:%M") + "\n", "speaker")
        self.chat.insert("end", str(text)[:8500] + "\n\n", "user" if author.upper()=="YOU" else "message")
        self.chat.configure(state="disabled")
        self.chat.see("end")
        if (getattr(self, "mini", None) and
                not (author.upper()=="APEX" and "initialized." in str(text))):
            self.mini.append(author, text)

    def _activity(self, text):
        msg = datetime.now().strftime("%H:%M") + "   " + str(text)[:180]
        self.activity.append(msg)
        self.activity = self.activity[-45:]
        self.feed.configure(state="normal")
        self.feed.delete("1.0", "end")
        self.feed.insert("end", "\n".join(self.activity[-5:]))
        self.feed.configure(state="disabled")
        try:
            with self.activity_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(),
                                    "event": str(text)[:180]}) + "\n")
            # Local Companion operational activity only; no global computer monitoring.
            self.personal.add_event("companion",str(text)[:140],scope="operations",source="companion_activity")
        except OSError:
            pass

    def _load_previous_activity(self):
        if not self.activity_file.exists():
            return
        try:
            # Log should not contain credentials or user information.
            records = self.activity_file.read_text(encoding="utf-8")[-11000:].splitlines()
            for line in records[-4:]:
                obj = json.loads(line)
                self.activity.append(str(obj.get("at", ""))[11:16] + "   " + str(obj.get("event", ""))[:180])
            self.feed.configure(state="normal")
            self.feed.insert("end", "\n".join(self.activity[-5:]))
            self.feed.configure(state="disabled")
        except (OSError, ValueError):
            return

    def _update_clock(self):
        self.clock.configure(text=datetime.now().strftime("%A  •  %b %d  •  %I:%M %p"))
        hour = datetime.now().hour
        self.hero_greeting.set("GOOD MORNING" if hour < 12 and hour >= 5 else
                               "GOOD AFTERNOON" if hour < 17 else "GOOD EVENING")
        self.root.after(30_000, self._update_clock)

    def _animate_orb(self):
        if not self.root.winfo_exists():return
        tick=getattr(self,"_orb_tick",0)+1
        self._orb_tick=tick
        speaker_busy=self.speaker.busy.is_set()
        processing="ai" in self.inflight
        mode="SPEAKING" if speaker_busy else "THINKING" if processing else \
             "AWAY" if self.away_active else "LISTENING" if self.microphone_active else "IDLE"
        self.holo.update_state(mode=mode,microphone_level=self.mic_level,
            voice_ready=self.microphone_active,camera_ready=self.camera_active,
            presence=self.face_visible,away=self.away_active)
        # Render only visible canvas; avoid 100ms CPU work while on telemetry tab.
        if self.current_page=="core" and self.root.state() == "normal":
            self.holo.render()
        conversation = bool(self.microphone and self.microphone.session.active)
        self.mini.render(mode, self.mic_level, self.microphone_active,
            self.camera_active, self.face_visible, self.away_active, conversation)
        self.sense_var.set("VOICE / "+("LISTENING" if self.microphone_active else "UNAVAILABLE")+
            "     |     CAMERA / "+("PRESENT" if self.face_visible else "SCANNING" if self.camera_active else "OFFLINE")+
            "     |     APEX / "+mode)
        self.root.after(85,self._animate_orb)

    def _render_all(self):
        is_in = bool(self.cloud and self.cloud.signed_in)
        head, desc = cloud_status(self.cloud_snapshot, is_in)
        sh, sd = steam_status(self.steam_summary, is_in)
        self.cloud_heading.set(head)
        self.cloud_sub.set(desc)
        self.steam_heading.set(sh)
        self.steam_sub.set(sd)
        self.connection_text.set("A.R.I.S CLOUD\n" + ("AUTHENTICATED" if is_in else "USER SIGN-IN REQUIRED"))
        self.auth_button.configure(text="SIGN OUT OF CLOUD" if is_in else "SIGN IN TO CLOUD",
                                   command=self.sign_out if is_in else self.sign_in_dialog)
        self.kpis["cloud"].set(readable_count(self.cloud_snapshot, "Device heartbeats"))
        self.kpis["cloud_sub"].set("Owner-visible records" if self.cloud_snapshot else "Sign in for private metrics")
        for name, var in self.cloud_rows.items():
            var.set(readable_count(self.cloud_snapshot, name))
        if self.steam_summary and self.steam_summary.get("status") == "ok":
            latest = self.steam_summary["latest"]
            self.kpis["steam"].set("+" + str(latest["wishlist_adds"]))
            self.kpis["steam_sub"].set("On " + self.steam_summary["latest_date"])
            self.steam_rows["date"].set(self.steam_summary["latest_date"])
            self.steam_rows["deletes"].set(str(latest["wishlist_deletes"]))
            self.steam_rows["purchases"].set(str(latest["wishlist_purchases"]))
            self.steam_rows["coverage"].set(f"{self.steam_summary.get('last7_coverage_days', 0)}/7 days")
        else:
            self.kpis["steam"].set("--")
            self.kpis["steam_sub"].set("Owner-scoped report")
            for v in self.steam_rows.values():
                v.set("--")
        if self.marketing_report:
            self.kpis["market"].set(str(len(self.marketing_report.get("opportunities", []))))
            self.kpis["market_sub"].set("Unverified research signals")
        else:
            self.kpis["market"].set("--")
            self.kpis["market_sub"].set("Daily scan scheduled")
        self.kpis["news"].set(str(sum(len(items) for _, items in self.news_brief)) if self.news_brief else "--")
        self.kpis["news_sub"].set("Public RSS headlines")
        self.hero_detail.set("A.R.I.S Cloud • " + head.lower() + ".  Replay Studio • " + sh.lower() +
                             ".  Daily research • " + ("loaded" if self.marketing_report else "pending") + ".")
        self.ai_context_status.set("AI CLOUD CONTEXT  /  " + ("ON" if self.use_context.get() else "OFF"))
        self.overview_status.set("LIMITED AUTONOMY   /   CLOUD READ-ONLY   /   NO AUTOMATIC PURCHASES OR PAID AI")
        self.status_var.set("A.R.I.S CLOUD  •  " + ("SIGNED IN" if is_in else "SIGN IN NEEDED")
                            + "     |     STEAM  •  " + ("REPORT READY" if sh == "REPORT AVAILABLE" else "WAITING")
                            + "     |     AI CONTEXT  •  " + ("ON" if self.use_context.get() else "OFF"))
        if hasattr(self, "auto_brief_btn"):
            self.auto_brief_btn.configure(text=("AUTO AI BRIEF • BLOCKED (NO SPEND)" if self.settings.get("autonomy_no_paid_calls",True) else
                                                  "AUTO AI BRIEF • ON" if self.settings.get("auto_paid_ai_daily",False) else "AUTO AI BRIEF • OFF"))
        if hasattr(self, "dev_status"):
            name = self.approved_project.name if self.approved_project else "none"
            logs = (str(self.unity_report.get("sampled_errors", 0)) + " sampled errors" if self.unity_report else "not scanned")
            self.dev_status.set(f"Approved project: {name}  •  {logs}  •  edits require your approval")
        if hasattr(self, "intel_summary"):
            stats=self.personal.trends(days=30)
            plan=self.personal.list_plan(limit=20)
            self.intel_summary.set(f"Local events (last 30d): {stats['observed_events']}   |   Goals open: {len(plan)}   |   Recent auto-fixes: {len(self.autonomy.recent(limit=20))}   |   Phone: {'ON' if self.settings.get('phone_brief_enabled',False) else 'OFF'}")
        if hasattr(self,"autofix_btn"):
            self.autofix_btn.configure(text="AUTO SMALL FIX  /  "+("ON" if self.settings.get("autonomous_small_fixes",True) else "OFF"))
        if hasattr(self, "alerts_summary"):
            unread = self.alert_center.recent(limit=3, only_unread=True)
            self.alerts_summary.set("  |  ".join(a["title"] for a in unread) if unread else "No unacknowledged alerts")
        self.budget_var.set(f"AI estimate this month  ${self.ledger.month_total():.4f} "
                            f"/ ${float(self.settings.get('monthly_budget_usd', 15)):.2f}")
        self._render_opportunities()
        self._render_news()

    def _render_opportunities(self):
        for child in self.marketing_holder.winfo_children():
            child.destroy()
        for item in marketing_previews(self.marketing_report):
            line = tk.Frame(self.marketing_holder, bg=CARD)
            line.pack(fill="x", pady=(1, 12))
            tag = item["kind"] + "   /   " + item["subtitle"]
            self._label(line, tag, 8, "bold", AMBER).pack(anchor="w")
            tk.Label(line, text=item["title"], bg=CARD, fg=INK, font=(FONT, 10, "bold"),
                     wraplength=675, justify="left", anchor="w").pack(fill="x", pady=(3, 3))
            tk.Label(line, text=item["action"], bg=CARD, fg=MUTED, font=(FONT, 9),
                     wraplength=675, justify="left", anchor="w").pack(fill="x")
            url = item.get("url", "")
            if url.startswith("https://"):
                button = self._button(line, "OPEN RESEARCH SOURCE", lambda u=url: safe_open(u))
                button.pack(anchor="w", pady=(7, 0))
        self.marketing_meta.set("Last scan: " + str(self.marketing_report.get("created_at_utc", "unknown"))[:19].replace("T", " ") +
                                 " UTC | Verify sources before acting" if self.marketing_report
                                 else "Standing campaign ideas — not verified fresh leads")

    def _render_news(self):
        for child in self.news_holder.winfo_children():
            child.destroy()
        items = news_previews(self.news_brief)
        if not items:
            self._label(self.news_holder, "Headlines will appear after the first free public RSS scan.",
                        10, color=MUTED).pack(anchor="w", pady=(3, 13))
        for item in items:
            line = tk.Frame(self.news_holder, bg=CARD)
            line.pack(fill="x", pady=(2, 12))
            self._label(line, item["topic"].upper(), 8, "bold", BLUE).pack(anchor="w")
            caption = tk.Label(line, text=item["title"], bg=CARD, fg=INK,
                               font=(FONT, 10), wraplength=670, justify="left",
                               anchor="w", cursor="hand2")
            caption.pack(fill="x", pady=(3, 0))
            caption.bind("<Button-1>", lambda e, u=item["url"]: safe_open(u))
        self.news_meta.set("Public research only • headlines are not independently verified")

    def _persist_setting(self, key, value):
        """Change a single preference without overwriting credentials or other settings."""
        target = ROOT / "config.json"
        try:
            cfg = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
            if not isinstance(cfg, dict):
                raise ValueError("config.json must be an object")
            cfg[key] = value
            temp = target.with_name("config.json.tmp")
            temp.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
            temp.replace(target)
            self.settings[key] = value
            return True
        except (ValueError, OSError) as exc:
            messagebox.showerror("APEX settings", "Couldn't save preference: " + type(exc).__name__)
            return False

    def manage_memory(self):
        dialog=tk.Toplevel(self.root)
        dialog.title("APEX / Local Memory Control")
        dialog.geometry("760x480")
        dialog.configure(bg=SIDE)
        self._label(dialog, "LOCAL MEMORY  /  REVIEW AND DELETE", 14, "bold", CYAN).pack(anchor="w",padx=18,pady=(17,6))
        self._label(dialog, "Stores explicit facts and recent chats in unencrypted SQLite on this PC. "
                    "Only selected snippets are supplied to OpenAI when you ask a question.",
                    9, color=MUTED, wraplength=720,justify="left").pack(anchor="w",padx=18,pady=(0,10))
        listbox=tk.Listbox(dialog,bg=CARD,fg=INK,selectbackground="#275F70",font=(FONT,10),relief="flat")
        listbox.pack(fill="both",expand=True,padx=18,pady=5)
        ids=[]
        def refresh():
            ids.clear();listbox.delete(0,"end")
            for row in self.memory.list_memories(limit=170):
                ids.append(row["id"])
                listbox.insert("end",f"#{row['id']:04d}  [{row['created_at'][:10]}]  {row['fact'][:150]}")
            if not ids:listbox.insert("end","No explicit memories saved. Say 'remember that ...' to add one.")
        def delete_selected():
            if not listbox.curselection() or not ids:return
            idx=int(listbox.curselection()[0])
            if idx>=len(ids):return
            if messagebox.askyesno("Delete memory", "Permanently delete selected saved fact?", parent=dialog):
                self.memory.delete(ids[idx]);refresh()
        def clear_chats():
            if messagebox.askyesno("Clear chat history", "Permanently delete locally recorded conversation history?",parent=dialog):
                self.memory.clear_conversation()
                self.brain.history.clear()
                self._activity("Local conversation history erased")
        def erase_all():
            if messagebox.askyesno("Delete ALL local memory", "Erase all explicit memories and conversation history from this PC?",parent=dialog):
                self.memory.forget_all();self.brain.history.clear();refresh()
        bar=tk.Frame(dialog,bg=SIDE)
        bar.pack(fill="x",padx=18,pady=12)
        for text,fn in (("DELETE SELECTED",delete_selected),("CLEAR CHATS",clear_chats),("FORGET ALL",erase_all)):
            self._button(bar,text,fn).pack(side="left",padx=(0,8))
        mem_enabled=bool(self.settings.get("enable_local_memory",True))
        def toggle():
            now=not bool(self.settings.get("enable_local_memory",True))
            if self._persist_setting("enable_local_memory",now):
                button.configure(text="TURN MEMORY OFF" if now else "TURN MEMORY ON")
                self._activity("Local memory " + ("enabled" if now else "disabled"))
        button=self._button(bar,"TURN MEMORY OFF" if mem_enabled else "TURN MEMORY ON",toggle)
        button.pack(side="right")
        refresh()

    def choose_project(self):
        folder=filedialog.askdirectory(title="Choose an ApexIQ / Unity project folder (read-only until you approve edits)",
                                      initialdir=str(self.approved_project or Path.home()))
        if not folder:return
        try:
            root=WorkspaceGuard(folder).root
        except (OSError,ValueError) as exc:
            messagebox.showerror("Project folder",str(exc));return
        if not messagebox.askyesno("Authorize local project", "Allow APEX to inspect the selected folder's "
                                   "approved source files and project Logs directory? No edits are allowed without a "
                                   "separate confirmation.\n\n" + str(root),parent=self.root):
            return
        if self._persist_setting("approved_project_root",str(root)):
            self.approved_project=root
            self.unity_report=None
            self.last_try.pop("unity",None)
            self.project_generation+=1
            self._activity("Local project approved: " + root.name)
            allow_global=messagebox.askyesno("Optional Unity Editor.log", "Also inspect your Windows Unity Editor.log? "
                                             "It can contain local file paths and build errors. Logs stay local "
                                             "unless you explicitly ask AI to analyze them.", parent=self.root)
            self._persist_setting("unity_include_editor_log",bool(allow_global))
            self._render_all()
            self.index_project()

    def index_project(self):
        if not self.approved_project:
            messagebox.showinfo("Code index", "Choose a Unity project folder first.");return
        root=self.approved_project
        generation=self.project_generation
        def work():
            result=self.indexer.index(root)
            if generation != self.project_generation:
                self.indexer.clear_root(root)
                return generation, {"indexed":0,"skipped":0,"revoked":True}
            return generation,result
        if self._spawn("index",work,"index_data"):
            self._activity("Indexing approved code locally: " + root.name)

    def scan_unity(self, automatic=False):
        if not self.approved_project:
            if not automatic:messagebox.showinfo("Unity logs","Choose an approved Unity folder first.")
            return
        if not automatic:self.unity_scan_requested=True
        root=self.approved_project
        generation=self.project_generation
        self._spawn("unity",lambda:(generation,scan_unity_logs(root,include_editor_log=bool(self.settings.get("unity_include_editor_log",False)))),"unity_data")

    def propose_patch(self):
        if not self.approved_project:
            messagebox.showinfo("Code patch","Choose and index a local Unity project folder first.");return
        selected=filedialog.askopenfilename(title="Select exactly one file to propose editing",
                                             initialdir=str(self.approved_project),
                                             filetypes=[("Source and config", "*.cs *.py *.json *.shader *.uxml *.uss *.md *.js *.ts *.yml *.yaml"),("All files","*.*")])
        if not selected:return
        try:
            guard=WorkspaceGuard(self.approved_project)
            rel=str(Path(selected).resolve(strict=True).relative_to(guard.root))
            guard.read(rel)
        except (OSError,ValueError) as exc:
            messagebox.showerror("File not approved",str(exc));return
        task=simpledialog.askstring("Propose a code change", "Describe the exact fix you want proposed for: " + Path(rel).name,
                                    parent=self.root)
        if not task or not task.strip():return
        if not messagebox.askyesno("Send approved source to AI", "This sends the selected source file (max 32 KB) "
                                   "to your configured OpenAI API for a PATCH PROPOSAL only. "
                                   "APEX will not write any file until you review a diff and click Approve.\n\n"+rel,
                                   parent=self.root):return
        self._activity("Preparing AI patch for " + Path(rel).name)
        generation=self.project_generation
        self._spawn("patch",lambda:(generation,propose_with_ai(self.brain,guard,rel,task)),"patch_data")

    def review_patch(self, proposal, spent, model):
        dialog=tk.Toplevel(self.root)
        dialog.title("APEX / Review Proposed Source Change")
        dialog.geometry("980x730")
        dialog.configure(bg=SIDE)
        self._label(dialog,"PROPOSED EDIT  /  NOT APPLIED",14,"bold",AMBER).pack(anchor="w",padx=16,pady=(16,7))
        self._label(dialog,"File: "+proposal.relative_path+f"  |  {model}  |  estimate ${spent:.5f}",
                    10,color=MUTED).pack(anchor="w",padx=16)
        self._label(dialog,proposal.explanation or "Review before applying",10,color=INK,
                    wraplength=940,justify="left").pack(anchor="w",padx=16,pady=(8,10))
        diff=scrolledtext.ScrolledText(dialog,bg=BG,fg=INK,insertbackground=INK,font=(MONO,10),
                                       wrap="none",relief="flat")
        diff.pack(fill="both",expand=True,padx=16,pady=(0,12))
        diff.insert("1.0",proposal.diff)
        diff.configure(state="disabled")
        actions=tk.Frame(dialog,bg=SIDE)
        actions.pack(fill="x",padx=16,pady=(0,18))
        def apply():
            if not messagebox.askyesno("Apply source patch", "Apply the EXACT reviewed text replacement? "
                                       "A timestamped backup will be made locally first. No build or deployment is run.",
                                       parent=dialog):return
            try:
                backup=WorkspaceGuard(proposal.root).apply(proposal,ROOT/"data"/"source_backups",approved=True)
            except (OSError,ValueError,RuntimeError,PermissionError) as exc:
                messagebox.showerror("Patch not applied",str(exc),parent=dialog);return
            self._activity("Approved source edit: " + proposal.relative_path)
            self._chat("APEX / CODE EDIT", "Applied your reviewed single-file patch. Backup saved locally at "+str(backup))
            dialog.destroy()
            self.index_project()
        self._button(actions,"APPROVE AND BACK UP",apply,accent=True).pack(side="left",padx=(0,9))
        def apply_verified():
            if not self.settings.get("ops_allow_unity_tests",False) or not self.settings.get("unity_editor_path"):
                messagebox.showwarning("Unity verification", "Enable tests and choose Unity.exe under OPERATIONS first.", parent=dialog);return
            if not messagebox.askyesno("Apply with Unity verification",
                "Apply ONLY the reviewed one-file patch, back up the original, then run Unity EditMode tests? "
                "If tests fail or produce no verifiable result, APEX will restore the original if nobody changed the file. "
                "Close Unity on this project before continuing.",parent=dialog):return
            generation=self.project_generation
            exe=self.settings.get("unity_editor_path")
            def work():
                trial=VerifiedPatchTrial(self.ops_unity_runner,ROOT/"data"/"verified_patch_backups")
                if generation!=self.project_generation or not self.personal.permitted("projects","local"):
                    raise PermissionError("Project access changed; patch not applied")
                result=trial.apply_and_test(WorkspaceGuard(proposal.root),proposal,exe,approved=True,
                         timeout_seconds=self.settings.get("ops_unity_timeout",420))
                return generation,result
            if self._spawn("verified_patch",work,"verified_patch_data"):
                self._activity("Reviewed one-file patch queued for Unity verification and automatic rollback on failure")
                dialog.destroy()
        self._button(actions,"APPROVE + TEST / ROLLBACK",apply_verified).pack(side="left",padx=(0,9))
        self._button(actions,"REJECT / CLOSE",dialog.destroy).pack(side="left")

    def _new_alerts(self, items):
        if not items:return
        for alert in self.alert_center.ingest(items):
            self._activity("ALERT: "+alert["title"])
            if self.settings.get("desktop_alerts",True):
                now=datetime.now().hour
                start=int(self.settings.get("quiet_hours_start",23))
                end=int(self.settings.get("quiet_hours_end",8))
                quiet=(now>=start or now<end) if start>=end else (start<=now<end)
                if not quiet:
                    self._chat("APEX / ALERT",alert["title"]+" — "+alert["details"][:250])
                    if self.settings.get("speak_alerts",False):
                        self.speaker.say(alert["title"])
        if hasattr(self,"alerts_summary"):self._render_all()

    def show_alerts(self):
        dialog=tk.Toplevel(self.root)
        dialog.title("APEX / Proactive Alerts")
        dialog.geometry("760x520")
        dialog.configure(bg=SIDE)
        self._label(dialog,"PROACTIVE ALERT CENTER",14,"bold",CYAN).pack(anchor="w",padx=16,pady=(16,6))
        self._label(dialog,"Based on observed local or owner-visible changes, not AI speculation.",
                    9,color=MUTED).pack(anchor="w",padx=16,pady=(0,9))
        feed=scrolledtext.ScrolledText(dialog,wrap="word",bg=CARD,fg=INK,font=(FONT,10),relief="flat")
        feed.pack(fill="both",expand=True,padx=16,pady=8)
        def refresh():
            feed.configure(state="normal");feed.delete("1.0","end")
            rows=self.alert_center.recent(limit=55)
            if not rows:feed.insert("end","No alerts recorded. Monitoring begins after you sign in or choose a Unity folder.")
            for row in rows:
                feed.insert("end",f"[{row['severity'].upper()}] {row['at_utc'][:19]}  {row['title']}\n{row['details']}\n"+
                            ("(acknowledged)\n\n" if row['acknowledged'] else "(new)\n\n"))
            feed.configure(state="disabled")
        def acknowledge():
            self.alert_center.acknowledge();refresh();self._render_all()
        bar=tk.Frame(dialog,bg=SIDE)
        bar.pack(fill="x",padx=16,pady=12)
        self._button(bar,"ACKNOWLEDGE ALL",acknowledge).pack(side="left",padx=(0,8))
        def delete_alerts():
            if messagebox.askyesno("Erase alerts", "Permanently delete ALL locally recorded alerts?",parent=dialog):
                self.alert_center.delete_all();refresh();self._render_all()
        self._button(bar,"ERASE ALERTS",delete_alerts).pack(side="left",padx=(0,8))
        self._button(bar,"CLOSE",dialog.destroy).pack(side="left")
        refresh()

    def stop_speaking(self):
        self.speaker.cancel()
        self._activity("Voice output interruption requested")

    def push_to_talk(self):
        if self.microphone and self.microphone.thread and self.microphone.thread.is_alive():
            self._chat("SYSTEM", "Voice wake listening is already active. Say 'Hey Apex' followed by your request, or toggle voice off for push-to-talk.")
            return
        model=ROOT/self.settings.get("vosk_model_path", "models/vosk-model-small-en-us-0.15")
        if not model.is_dir():
            messagebox.showinfo("Push to talk", "Install the free offline Vosk model described in README first.")
            return
        self.speaker.cancel()
        if self._spawn("ptt",lambda:transcribe_push_to_talk(model,seconds=7,
                        device=self.settings.get("microphone_input_device")),"ptt_data"):
            self._chat("SYSTEM", "Listening locally for seven seconds… audio stays on this PC.")

    def revoke_project(self):
        if not self.approved_project:
            messagebox.showinfo("Project permissions","No project currently authorized.");return
        old=self.approved_project
        if not messagebox.askyesno("Revoke project access", "Stop indexing, monitoring and searching "
                                   "the approved folder, and erase its indexed snippets?\n\n"+str(old),parent=self.root):return
        self.project_generation+=1
        self.approved_project=None
        self.unity_report=None
        self._persist_setting("approved_project_root","")
        self._persist_setting("unity_include_editor_log",False)
        self.indexer.clear_root(old)
        self._activity("Revoked project access: " + old.name)
        self._render_all()

    def toggle_auto_ai_brief(self):
        now = not bool(self.settings.get("auto_paid_ai_daily",False))
        if now:
            if self.settings.get("autonomy_no_paid_calls",True):
                messagebox.showinfo("No autonomous spending", "APEX v0.8 has unpaid-only background autonomy enabled. Turn off autonomy_no_paid_calls in config.json explicitly to allow optional scheduled AI usage.")
                return
            if not self.use_context.get():
                messagebox.showinfo("Auto AI brief", "Turn on AI CLOUD CONTEXT first, so the daily brief has reliable data.")
                return
            if not messagebox.askyesno("Enable daily AI request", "Allow one automatic OpenAI text request per day after 9 AM, while Companion is running? "
                                       "This consumes API credit subject to your local budget. You can turn it off anytime.",parent=self.root):return
        if self._persist_setting("auto_paid_ai_daily",now):
            self._activity("Daily AI brief " + ("enabled" if now else "disabled"))
            self._render_all()

    def _automatic_ai_brief(self):
        if self.settings.get("autonomy_no_paid_calls",True):return
        if not self.settings.get("auto_paid_ai_daily",False) or self.auto_ai_pending:return
        if not self.use_context.get():return
        hour=datetime.now().hour
        if hour < int(self.settings.get("daily_ai_brief_hour",9)) or hour >= int(self.settings.get("quiet_hours_start",23)):return
        marker=ROOT/"data"/"last_paid_brief_date.txt"
        try:
            if marker.exists() and marker.read_text(encoding="utf-8").strip()==datetime.now().date().isoformat():return
        except OSError:return
        if "ai" in self.inflight or "cloud" in self.inflight or "steam" in self.inflight:return
        # This action only occurs after an explicit opt-in and is charged to the user's local budget.
        self.auto_ai_pending=True
        self._chat("SYSTEM", "Generating your opt-in daily AI operating briefing from authorized current data…")
        self._ask_ai("Prepare today's concise ApexIQ Moto and Replay Studio operating briefing. "
                     "Use current owner-visible Steam and cloud data, dated project history, "
                     "available public research, actual risks, and three concrete next actions. "
                     "Clearly flag missing or stale sources.",label="DAILY AI BRIEF",show_prompt=False)
        if "ai" not in self.inflight:self.auto_ai_pending=False

    def _async_status(self, message):
        self.events.put(("status", str(message)))

    def _spawn(self, name, fn, event_kind=None):
        if name in self.inflight:
            return False
        self.inflight.add(name)
        self.last_try[name] = datetime.now(timezone.utc)
        def work():
            try:
                self.events.put((event_kind or name, fn()))
            except Exception as ex:
                # Safe, short diagnostics: no raw tokens/passwords/secret bodies in UI logs.
                from companion.project_index import redact
                import re
                safe = redact(str(ex)[:320])
                safe = re.sub(r"(?i)Bearer\s+[A-Za-z0-9._-]+", "Bearer [REDACTED]", safe)
                self.events.put(("job_error", (name, safe[:240])))
            finally:
                self.events.put(("job_done", name))
        self.executor.submit(work)
        return True

    def _restore_cloud(self):
        if not self.cloud:
            return
        def work():
            token = self.store.read()
            if not token:
                raise RuntimeError("No saved Windows user session")
            self.cloud.restore(token)
            return self.cloud.user_id()
        self._spawn("auth", work, "cloud_login")

    def sign_in_dialog(self):
        if not self.cloud:
            messagebox.showerror("A.R.I.S Cloud", "Project connection unavailable. Check the public Supabase key in config.json.")
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Connect to A.R.I.S Cloud")
        dialog.geometry("440x335")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg=SIDE)
        pad = tk.Frame(dialog, bg=SIDE, padx=25, pady=20)
        pad.pack(fill="both", expand=True)
        self._label(pad, "A.R.I.S CLOUD  /  OWNER SIGN-IN", 13, "bold", CYAN).pack(anchor="w", pady=(0, 9))
        self._label(pad, "Your normal ApexIQ user login. Never use a service-role key.",
                    9, color=MUTED, wraplength=375, justify="left").pack(anchor="w", pady=(0, 18))
        self._label(pad, "EMAIL", 9, "bold", MUTED).pack(anchor="w")
        email = tk.Entry(pad, bg=CARD, fg=INK, insertbackground=INK, relief="flat",
                         font=(FONT, 11))
        email.pack(fill="x", ipady=9, pady=(3, 12))
        self._label(pad, "PASSWORD", 9, "bold", MUTED).pack(anchor="w")
        password = tk.Entry(pad, bg=CARD, fg=INK, show="*", insertbackground=INK,
                            relief="flat", font=(FONT, 11))
        password.pack(fill="x", ipady=9, pady=(3, 12))
        self._label(pad, "Optional: encrypted refresh session in Windows Credential Manager.",
                    9, color=MUTED, wraplength=380, justify="left").pack(anchor="w")
        def perform():
            e = email.get().strip()
            p = password.get()
            password.delete(0, "end")
            dialog.destroy()
            if not e or not p:
                return
            self._spawn("auth", lambda: self._do_login(e, p), "cloud_login")
            self._activity("Signing in to A.R.I.S Cloud")
        self._button(pad, "CONNECT", perform, accent=True).pack(fill="x", pady=(15, 0))
        email.focus_set()
        dialog.bind("<Return>", lambda e: perform())

    def _do_login(self, email, password):
        self.cloud.sign_in(email, password)
        return self.cloud.user_id()

    def sign_out(self):
        if self.cloud:
            self.cloud.sign_out()
        self.store.forget()
        self.logged_in_user = None
        self.cloud_snapshot = None
        self.steam_summary = None
        self.session_generation += 1
        self._activity("User session removed from Companion")
        self._render_all()

    def cloud_health(self, force=False):
        if not (self.cloud and self.cloud.signed_in):
            if force:
                self._chat("SYSTEM", "Sign in to A.R.I.S Cloud once for owner-scoped metrics.")
            return
        generation = self.session_generation
        self._spawn("cloud", lambda: (generation, self.cloud.snapshot()), "cloud_data")

    def steam_growth(self, force=False):
        if not (self.cloud and self.cloud.signed_in):
            if force:
                self._chat("SYSTEM", "Sign in to A.R.I.S Cloud to view private Steam reporting.")
            return
        generation = self.session_generation
        self._spawn("steam", lambda: (generation, SteamworksReader(self.cloud).fetch(days=30)), "steam_data")

    def business_news(self, force=False):
        def work():
            brief, errors = fetch_brief(list(self.settings["news_topics"]))
            return brief, errors
        self._spawn("news", work, "news_data")

    def marketing_scan(self, force=False):
        def work():
            report = scan_marketing()
            save_report(report, ROOT / "data" / "marketing")
            return report
        if self._spawn("marketing", work, "marketing_data") and force:
            self._activity("Marketing scan started on request")

    def refresh_all(self):
        self.cloud_health()
        self.steam_growth()
        self.business_news(force=True)
        self.marketing_scan(force=True)
        self._activity("Refresh requested for connected sources")

    def _automation_tick(self):
        now = datetime.now(timezone.utc)
        if due(self.last_try.get("news"), 360):
            self.business_news()
        if due(self.last_try.get("marketing"), 1440):
            # The first scan is automatic. Subsequent scans are daily, no AI charge.
            self.marketing_scan()
        if self.settings.get("marketing_auto_daily_draft", True):
            try:
                _, created = self.business.ensure_daily_draft()
                if created:
                    self._activity("Content Lab created one local draft for review (not published)")
            except (OSError, ValueError):
                self._activity("Content Lab daily draft unavailable; no external action taken")
        if self.approved_project and due(self.last_try.get("unity"), max(2, int(self.settings.get("scan_unity_minutes", 10)))):
            self.scan_unity(automatic=True)
        if self.cloud and self.cloud.signed_in:
            if due(self.last_try.get("cloud"), max(1, int(self.settings.get("cloud_refresh_minutes", 5)))):
                self.cloud_health()
            if due(self.last_try.get("steam"), max(2, int(self.settings.get("steam_refresh_minutes", 30)))):
                self.steam_growth()
        self._update_away_mode()
        # Foreground executable sampling is separate opt-in, never global surveillance.
        if self.settings.get("foreground_app_sampling",False):
            self.activity_capture.tick()
        self._consolidate_project_memory_once_daily()
        self._automatic_morning_brief()
        self._free_phone_brief()
        self._phone_remote_tick()
        self._ops_tick()
        self._automatic_ai_brief()
        self.root.after(60_000, self._automation_tick)

    def _consolidate_project_memory_once_daily(self):
        if not self.settings.get("enable_local_memory",True):return
        if not self.personal.permitted("projects","local"):return
        marker=ROOT/"data"/"last_intel_consolidation.txt"
        today=datetime.now().date().isoformat()
        try:
            if marker.exists() and marker.read_text(encoding="utf-8").strip()==today:return
            result=consolidate(self.personal,self.memory)
            marker.write_text(today,encoding="utf-8")
            if result.get("imported"):
                self._activity("Source-attributed explicit PROJECT memory consolidation completed")
        except (OSError,ValueError,PermissionError):
            return

    def _automatic_morning_brief(self):
        """Create one free local morning briefing daily while the app is running.

        No ambient narration without the user explicitly enabling camera greetings.
        """
        local = datetime.now()
        quiet = int(self.settings.get("quiet_hours_start", 23))
        if not 9 <= local.hour < quiet:
            return
        marker = ROOT / "data" / "last_auto_brief_date.txt"
        try:
            if marker.exists() and marker.read_text(encoding="utf-8").strip() == local.date().isoformat():
                return
        except OSError:
            pass
        # Allow initial research/auth to settle so the briefing isn't empty.
        started = getattr(self, "_started_at", None)
        if started is None:
            self._started_at = datetime.now(timezone.utc)
            return
        if (datetime.now(timezone.utc) - started).total_seconds() < 40:
            return
        if "cloud" in self.inflight or "steam" in self.inflight:
            return
        self.show_brief()
        try:
            marker.write_text(local.date().isoformat(), encoding="utf-8")
        except OSError:
            pass

    def show_brief(self):
        text = local_brief(self.cloud_snapshot, self.steam_summary, self.marketing_report,
                           self.news_brief, bool(self.cloud and self.cloud.signed_in))
        self._chat("APEX / BRIEFING", text + "\n\n" + self.business.analysis())
        self._activity("Local briefing generated, no paid AI")

    def marketing_insights(self):
        evidence = self.business.analysis()
        radar = analysis_prompt(self.marketing_report) if self.marketing_report else "No public headline scan available."
        task = ("Use verified owner-imported local business metrics when available; public research "
                "headlines are unverified. Identify a responsible, inexpensive content experiment "
                "for ApexIQ Moto and Replay Studio. Distinguish correlation and attribution; "
                "do not claim an unmeasured conversion or send/publish anything.\n\n"
                + evidence[:3500] + "\n\n" + radar[:3500])
        self._ask_ai(task, deep=False, label="MARKETING ANALYSIS", show_prompt=False)

    def send(self, deep=False, phrase=None, speak=False):
        text = (self.entry.get() if phrase is None else phrase).strip()
        if not text:
            return
        if phrase is None:
            self.entry.delete(0, "end")
        self._chat("YOU", text)
        lowered = text.lower().strip(" ?!.")
        # Session mode is user-initiated; it never authorizes paid background calls.
        if speak and (getattr(self, "voice_topic", "general") != "general" or
                      bool(self.microphone and self.microphone.session.active)):
            if lowered in ("business", "business conversation", "let's talk business", "lets talk business",
                           "talk business", "start business conversation"):
                self._start_conversation("business")
                return
            if lowered in ("personal conversation", "let's talk personally", "lets talk personally",
                           "talk personally"):
                self._start_conversation("personal")
                return
            if lowered in ("open dashboard", "show dashboard", "full dashboard"):
                self.open_dashboard()
                self.speaker.say("Opening the dashboard.")
                return
            if lowered in ("close conversation", "end conversation", "goodbye"):
                if self.microphone:self.microphone.session.close()
                self.voice_topic="general"
                self.speaker.say("Okay. Talk to you later.")
                return
            if any(key in lowered for key in ("marketing", "beta riders", "creator", "sales", "revenue", "business")):
                self.voice_topic = "business"
                if self.microphone:self.microphone.session.activate("business")
            self._ask_ai(text, deep=deep, speak=True, label="VOICE CONVERSATION",
                         voice_conversation=True)
            return
        # Spoken commands may retain the wake name. Normalize it for the
        # bounded local command router; never reinterpret free-form speech as
        # permission to run arbitrary programs or modify source code.
        for prefix in ("hey apex, ","hey apex ","hey jarvis, ","hey jarvis ",
                       "apex, ","apex ","jarvis, ","jarvis "):
            if lowered.startswith(prefix):
                lowered=lowered[len(prefix):].strip(" ?!.")
                break
        memory_id = None
        if self.settings.get("enable_local_memory", True):
            try:
                memory_id = self.memory.remember_from_message(text)
                if memory_id is not None:
                    self._chat("APEX", f"Saved locally as memory #{memory_id}. Open MEMORY / CONTROL to review or delete it.")
                    self._activity("Explicit local memory stored")
                    # A standalone `remember` command is complete. For a
                    # multi-part user request, continue to answer the other tasks.
                    if len(text.splitlines())<=1 and len(text)<350:
                        return
            except ValueError:
                self._chat("APEX", "Couldn't safely save that memory. Avoid passwords, tokens and secrets.")
                return
        if lowered in ("how is everything looking", "daily brief", "briefing", "overview",
                       "status", "how's everything looking"):
            self.show_brief()
        elif lowered in ("cloud", "cloud health", "apexiq cloud"):
            self.cloud_health(force=True)
        elif lowered in ("steam", "steam growth", "wishlists", "wishlist"):
            self.steam_growth(force=True)
        elif lowered in ("marketing", "marketing scan", "opportunities"):
            self.marketing_scan(force=True)
        elif lowered in ("business", "business studio", "marketing dashboard", "content lab", "content studio"):
            self.business_panel()
        elif lowered in ("business report", "marketing report", "marketing funnel", "campaign performance"):
            self.business_brief()
        elif lowered in ("news", "business news", "headlines"):
            self.business_news(force=True)
        elif lowered in ("scan unity", "unity errors", "unity diagnostics", "apex scan unity"):
            self.enqueue_operation("unity_diagnostics")
        elif lowered in ("run unity tests", "run edit mode tests", "unity test runner"):
            self.enqueue_operation("unity_editmode_tests")
        elif lowered in ("check git", "git status", "inspect git"):
            self.enqueue_operation("git_health")
        elif lowered in ("operations", "operations panel", "work queue", "task queue"):
            self.operations_panel()
        elif lowered in ("my memories", "show memories", "memory manager"):
            self.manage_memory()
        else:
            self._ask_ai(text, deep=deep, speak=speak, label="AI RESPONSE", verified_memory_id=memory_id)

    def _ask_ai(self, message, deep=False, speak=False, label="AI RESPONSE", show_prompt=True,
                verified_memory_id=None, voice_conversation=False):
        if "ai" in self.inflight:
            self._chat("SYSTEM", "One AI request is already running. Please try again shortly.")
            return
        # Any source refresh happens in a worker, before the OpenAI request.
        # This fixes the post-login race where chat previously received no facts.
        needs_live_data = self._needs_business_context(message)
        context_enabled = bool(self.use_context.get()) and (not voice_conversation or needs_live_data)
        if not bool(self.use_context.get()) and needs_live_data:
            self._chat("SYSTEM", "AI CLOUD CONTEXT is OFF. Use TOGGLE AI CLOUD CONTEXT in the "
                                 "assistant panel to allow sanitized business metrics in AI answers.")
            if speak:
                self.speaker.say("AI business context is disabled. You can enable it in the full dashboard.")
            return
        generation = self.session_generation
        project_generation = self.project_generation
        personal_generation = self.personal_generation
        monitor = self.cloud if self.cloud and self.cloud.signed_in else None
        cloud_cached, steam_cached = self.cloud_snapshot, self.steam_summary
        marketing, news = self.marketing_report, self.news_brief
        cloud_last, steam_last = self.last_success.get("cloud"), self.last_success.get("steam")

        def work():
            context = ""
            if context_enabled:
                context, cloud_new, steam_new, refreshed, errors = gather_dashboard_context(
                    monitor=monitor, cloud_cached=cloud_cached, steam_cached=steam_cached,
                    marketing=marketing, news=news, signed_in=bool(monitor),
                    cloud_last=cloud_last, steam_last=steam_last,
                    cloud_ttl_minutes=int(self.settings.get("cloud_refresh_minutes", 5)),
                    steam_ttl_minutes=int(self.settings.get("steam_refresh_minutes", 30)))
                # Never attach context from a different account after a sign-out.
                if generation != self.session_generation:
                    raise RuntimeError("Cloud session changed while preparing AI context. Please ask again.")
                if "cloud" in refreshed:
                    self.events.put(("cloud_data", (generation, cloud_new)))
                if "steam" in refreshed:
                    self.events.put(("steam_data", (generation, steam_new)))
                if errors:
                    self.events.put(("context_warning", len(errors)))
            if verified_memory_id is not None:
                context += ("\nVERIFIED LOCAL APP ACTION: The user's explicit memory "
                            f"was saved to the local SQLite database as memory #{verified_memory_id}. "
                            "You may confirm this specific fact. Do not imply other actions succeeded.")
            toolbox = LiveToolbox(
                monitor=monitor, memory=self.memory if self.settings.get("enable_local_memory", True) else None,
                indexer=self.indexer, approved_project=self.approved_project,
                cloud=cloud_new if context_enabled else cloud_cached,
                steam=steam_new if context_enabled else steam_cached,
                marketing=marketing, news=news, allow_cloud=context_enabled,
                include_editor_logs=self.settings.get("unity_include_editor_log", False),
                authorization_check=lambda: generation==self.session_generation,
                project_authorization_check=lambda: project_generation==self.project_generation,
                personal=self.personal,
                intel_alerts=self.alert_center,
                import_vault=self.import_vault,
                personal_authorization_check=lambda: personal_generation==self.personal_generation,
                operations=self.ops_queue,
                operations_authorization_check=lambda: personal_generation==self.personal_generation)
            return (self.brain.ask(message, deep=deep, include_history=show_prompt,
                                   context=(context[:1200] if voice_conversation else context),
                                   tools=(toolbox if self.settings.get("enable_readonly_tools", True)
                                          and (needs_live_data or self._needs_local_tool(message)) else None),
                                   voice_mode=(getattr(self, "voice_topic", "general") if voice_conversation else None),
                                   include_notes=not voice_conversation,
                                   limit_output_tokens=(420 if voice_conversation else None)), speak)

        if context_enabled and monitor and (cloud_cached is None or steam_cached is None):
            self._chat("SYSTEM", "Gathering your authorized cloud and Steam data before answering…")
        self._ai_request_spoken = bool(speak)
        self._spawn("ai", work, "ai_data")
        if speak:
            self.mini.set_recognition_status("AI / REQUEST QUEUED. WAITING FOR RESPONSE")
        self._activity("AI request queued" + (" with cloud/business context" if context_enabled else " without cloud stats"))

    @staticmethod
    def _needs_local_tool(text):
        text = str(text).lower()
        return any(term in text for term in (
            "my memories", "remember about", "my saved", "our device", "device metrics",
            "cloud health", "check cloud", "steam growth", "steam data", "unity errors",
            "inspect source", "search code", "my source code", "project files",
            "our operations", "operations queue", "current beta applications"))

    @staticmethod
    def _needs_business_context(text):
        text = str(text).lower()
        return any(term in text for term in (
            "current situation", "situatuion", "business briefing", "steam", "wishlist", "device status",
            "cloud status", "apexiq status", "my situation", "hardware progress",
            "marketing performance", "our progress"))

    def toggle_context(self):
        self.use_context.set(not self.use_context.get())
        self._context_changed()

    def _context_changed(self):
        enabled = bool(self.use_context.get())
        # Persist only the explicit context choice; preserve all other settings.
        config_path = ROOT / "config.json"
        try:
            current = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
            if not isinstance(current, dict):
                raise ValueError("config.json must contain an object")
            current["send_aggregates_to_ai"] = enabled
            temp = config_path.with_name("config.json.tmp")
            temp.write_text(json.dumps(current, indent=2), encoding="utf-8")
            temp.replace(config_path)
            self.settings["send_aggregates_to_ai"] = enabled
        except (OSError, ValueError) as exc:
            self._chat("SYSTEM", "Unable to save AI context preference: " + type(exc).__name__)
        self._activity("AI cloud context " + ("enabled" if enabled else "disabled"))
        self._render_all()

    def _greet(self):
        self.events.put(("greet", "Welcome back. ApexIQ Companion is ready. "
                         "Your briefing is on screen."))

    def toggle_camera(self,autostart=False):
        if self.camera and self.camera.thread and self.camera.thread.is_alive():
            self.camera.stop()
            self.camera_btn.configure(text="CAMERA  •  OFF")
            self.camera_active=False
            self.face_visible=False
            self.away_monitor.camera_unavailable()
            self._persist_setting("camera_autostart",False)
            return
        self.camera = PresenceCamera(self.settings, self._greet, self._async_status,
                                    lambda present:self.events.put(("presence",present)))
        self.camera.start()
        if not autostart:self._persist_setting("camera_autostart",True)
        self.camera_btn.configure(text="CAMERA  •  STARTING")

    def test_voice(self):
        """One-click local TTS test; no AI call or token usage."""
        text = "Hello. I'm Apex. My voice output is working. What would you like to talk about?"
        self._chat("SYSTEM", "Testing local speaker output. This uses no AI credits.")
        self.speaker.cancel()
        self.speaker.say(text)

    def voice_output_setup(self):
        """Choose built-in Windows voice or pyttsx3 and test without API costs."""
        win = tk.Toplevel(self.root)
        win.title("APEX | Voice Output")
        win.geometry("485x390")
        win.configure(bg=BG)
        win.transient(self.root if self.root.state() == "normal" else self.mini.window)
        tk.Label(win, text="APEX SPOKEN VOICE", bg=BG, fg=CYAN,
                 font=(FONT, 14, "bold")).pack(pady=(16, 9))
        tk.Label(win, text="Use Windows speech output first. No online voice service required.",
                 bg=BG, fg=INK, wraplength=450).pack(pady=(0, 12))
        mode = tk.StringVar(value=str(self.settings.get("speech_output_backend", "windows")))
        for value, label in (("kokoro", "Kokoro - natural, free, offline (install model once)"),
                             ("windows", "Windows built-in speech (no download)"),
                             ("pyttsx3", "pyttsx3 (legacy voice)")):
            tk.Radiobutton(win, text=label, variable=mode, value=value,
                           bg=BG, fg=INK, selectcolor=CARD, activebackground=BG,
                           activeforeground=CYAN).pack(anchor="w", padx=25)
        tk.Label(win, text="Natural voice: after setup, select a Kokoro voice below.", bg=BG, fg=INK).pack(pady=(4, 0))
        selected_voice = tk.StringVar(value=str(self.settings.get("speech_voice_name", "af_heart")))
        tk.OptionMenu(win, selected_voice, "af_heart", "af_bella", "am_michael", "am_adam").pack()
        tk.Label(win, text="Volume (Windows/fallback voice)", bg=BG, fg=INK).pack(pady=(5, 0))
        volume = tk.IntVar(value=int(self.settings.get("speech_output_volume", 100)))
        tk.Scale(win, from_=0, to=100, orient="horizontal", variable=volume,
                 bg=BG, fg=INK, troughcolor=CARD, highlightthickness=0,
                 length=370).pack()
        def apply():
            chosen=mode.get()
            level=int(volume.get())
            self._persist_setting("speech_output_backend", chosen)
            self._persist_setting("speech_output_volume", level)
            self._persist_setting("speech_voice_name", selected_voice.get())
            old=self.speaker
            old.shutdown()
            self.speaker=LocalSpeaker(self._async_status,backend=chosen,volume=level,voice=selected_voice.get())
            if self.microphone is not None:
                self.microphone.speaker=self.speaker
            win.destroy()
            self.test_voice()
        tk.Button(win, text="SAVE + TEST VOICE", command=apply, bg="#116479",
                  fg="white", relief="flat", padx=14, pady=9).pack(pady=(7, 14))

    def microphone_setup(self):
        """Owner-selected Windows audio input. Safe to open from the tray."""
        try:
            choices = input_devices()
        except Exception as exc:
            messagebox.showerror("Microphone setup", "Unable to list audio inputs: " + str(exc)[:240])
            return
        win = tk.Toplevel(self.root)
        win.title("APEX | Select Microphone")
        win.geometry("570x535")
        win.configure(bg=BG)
        win.transient(self.root if self.root.state() == "normal" else self.mini.window)
        tk.Label(win, bg=BG, fg=INK, font=(FONT, 13, "bold"),
                 text="Choose which microphone APEX should listen to").pack(padx=16,pady=(16,8))
        tk.Label(win, bg=BG, fg=MUTED, font=(FONT, 9),
                 text="Speak after restarting voice. Watch for 'INPUT SIGNAL DETECTED'.").pack(padx=16,pady=(0,10))
        picker = tk.Listbox(win, bg=CARD, fg=INK, selectbackground="#185A79",
                            font=(FONT, 10), exportselection=False, height=7)
        picker.pack(fill="both", expand=True, padx=14,pady=5)
        options = [(None,"Windows default microphone")]
        options += [(row["id"], f'{row["id"]}: {row["name"]}  ({row["rate"]} Hz native)')
                    for row in choices]
        current = self.settings.get("microphone_input_device")
        selected = 0
        for idx, (device, name) in enumerate(options):
            picker.insert("end", name)
            if device == current:
                selected = idx
        picker.selection_set(selected)
        picker.see(selected)
        tk.Label(win, bg=BG, fg=MUTED, font=(FONT, 9), wraplength=530,
                 text="If no input device appears, check Windows Sound > Input and the privacy setting for desktop apps.").pack(padx=16,pady=8)
        tk.Label(win, text="Pause after your speech before APEX responds (seconds)",
                 bg=BG, fg=INK).pack(pady=(7,0))
        pause_sec = tk.DoubleVar(value=float(self.settings.get("speech_pause_seconds",2.1)))
        tk.Scale(win, from_=1.1, to=3.6, resolution=0.1, orient="horizontal", variable=pause_sec,
                 bg=BG, fg=INK, troughcolor=CARD, highlightthickness=0, length=385).pack()
        tk.Label(win, text="Noise rejection: 3 is strictest. Use 2 if speech is being missed.",
                 bg=BG, fg=MUTED, font=(FONT,9)).pack()
        vad_mode = tk.IntVar(value=int(self.settings.get("speech_vad_mode",3)))
        tk.Scale(win, from_=0, to=3, resolution=1, orient="horizontal", variable=vad_mode,
                 bg=BG, fg=INK, troughcolor=CARD, highlightthickness=0, length=280).pack()
        def apply_selection():
            selection = picker.curselection()
            if not selection:
                return
            target = options[selection[0]][0]
            was_active = bool(self.microphone and self.microphone.thread and self.microphone.thread.is_alive())
            if was_active:
                self.microphone.stop()
                self.microphone.thread.join(timeout=1.5)
            self._persist_setting("microphone_input_device", target)
            self._persist_setting("speech_pause_seconds", round(float(pause_sec.get()),1))
            self._persist_setting("speech_vad_mode", int(vad_mode.get()))
            self.microphone_active = False
            self.microphone = None
            win.destroy()
            self._chat("SYSTEM", "Input device selected. " + ("Restarting voice." if was_active else "Turn VOICE on to start listening."))
            if was_active:
                self.root.after(400, self.toggle_microphone)
        tk.Button(win,text="SAVE MICROPHONE + PAUSE", command=apply_selection,bg="#116479",fg="white",
                  relief="flat",padx=12,pady=8).pack(pady=(4,14))

    def toggle_microphone(self,autostart=False):
        if self.microphone and self.microphone.thread and self.microphone.thread.is_alive():
            self.microphone.stop()
            self.mic_btn.configure(text="VOICE  •  OFF")
            self.microphone_active=False
            self._persist_setting("microphone_autostart",False)
            return
        model = ROOT / self.settings["vosk_model_path"]
        phrases = list(dict.fromkeys(list(DEFAULT_WAKE_PHRASES) + list(self.settings.get("wake_phrases", []))))
        self.microphone = WakeMicrophone(model, phrases,
                                         lambda x, speak: self.events.put(("voice", (x, speak))),
                                         self.speaker, self._async_status,
                                         on_level=lambda level:self.events.put(("mic_level",level)),
                                         on_wake=lambda has_command:self.events.put(("voice_wake",has_command)),
                                         on_sleep=lambda:self.events.put(("voice_sleep",None)),
                                         can_accept=lambda:"ai" not in self.inflight,
                                         session_seconds=int(self.settings.get("conversation_idle_seconds",120)),
                                         device=self.settings.get("microphone_input_device"),
                                         on_transcript=lambda text, kind:self.events.put(("voice_transcript", (text,kind))),
                                         on_partial=lambda text:self.events.put(("voice_partial",text)),
                                         speech_pause_seconds=float(self.settings.get("speech_pause_seconds",2.1)),
                                         speech_vad_mode=int(self.settings.get("speech_vad_mode",3)),
                                         improved_recognition=bool(self.settings.get("speech_enhanced_recognition",False)))
        try:
            self.microphone.start()
            if not autostart:self._persist_setting("microphone_autostart",True)
            self.mic_btn.configure(text="VOICE  •  STARTING")
        except Exception as exc:
            if autostart:
                self._activity("Voice autostart unavailable; configure offline Vosk speech model")
                self.microphone_active=False
                self.mic_btn.configure(text="VOICE  •  SETUP")
            else:
                messagebox.showerror("Voice recognition", str(exc) +
                    "\n\nIf the offline speech model is missing, run Download_Offline_Voice_Model.cmd")

    def open_notes(self):
        path = ROOT / "data" / "apexiq_notes.md"
        try:
            os.startfile(str(path))
        except (AttributeError, OSError):
            messagebox.showinfo("Local notes", f"Open this file in a text editor:\n{path}")

    def _drain(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "cloud_login":
                    self.session_generation += 1
                    self.logged_in_user = data
                    self._activity("A.R.I.S Cloud owner session authenticated")
                    self._chat("SYSTEM", "A.R.I.S Cloud connected with your user account. "
                                         "Refreshing owner-visible metrics and Steam growth now.")
                    self.last_try.pop("cloud", None)
                    self.last_try.pop("steam", None)
                    self.cloud_health()
                    self.steam_growth()
                    self._render_all()
                elif kind == "cloud_data":
                    generation, snapshot = data
                    if generation != self.session_generation or not (self.cloud and self.cloud.signed_in):
                        continue
                    previous_cloud = self.cloud_snapshot
                    self.cloud_snapshot = snapshot
                    self.personal.add_event("cloud","Owner-visible cloud check",
                        "Heartbeat: "+str(snapshot.get("device_freshness","unknown"))[:75],
                        scope="operations",source="cloud_summary")
                    self._new_alerts(cloud_alerts(snapshot) + beta_alerts(previous_cloud, snapshot))
                    self.last_success["cloud"] = datetime.now(timezone.utc)
                    self._activity("Cloud health updated (owner-scoped)")
                    state = cloud_status(self.cloud_snapshot, True)[0]
                    if state == "HEARTBEAT STALE" and self.last_heartbeat_alert != state:
                        self._activity("ALERT: last visible device heartbeat is stale; check device connectivity")
                    self.last_heartbeat_alert = state
                    self._render_all()
                elif kind == "steam_data":
                    generation, steam_data = data
                    if generation != self.session_generation or not (self.cloud and self.cloud.signed_in):
                        continue
                    previous_steam = self.steam_summary
                    self.steam_summary = steam_data
                    if self.personal.permitted("operations","local") and steam_data.get("status")=="ok":
                        newest=steam_data.get("latest") or {}
                        d=str(steam_data.get("latest_date") or "")
                        if d:
                            desc=f"Steam daily wishlist additions: {newest.get('wishlist_adds','unknown')} (not total); coverage last7={steam_data.get('last7_coverage_days','unknown')} days"
                            self.personal.add_entity("milestone","Steam wishlist report "+d,desc,
                                scope="operations",source="steam_daily",source_ref=d,observed_at=d+"T12:00:00+00:00")
                            self.personal.add_event("steam","Steam wishlist daily report",desc,
                                scope="operations",source="steam_daily",observed_at=d+"T12:00:00+00:00",dedupe_key="steam:"+d)
                            try:
                                report_id=self.personal.add_entity("milestone","Steam wishlist report "+d,desc,
                                    scope="operations",source="steam_daily",source_ref=d,observed_at=d+"T12:00:00+00:00")
                                replay_id=self.personal.add_entity("project","ApexIQ Replay Studio","Unity / Steam product",
                                    scope="projects",source="owner_input",source_ref="project:replay")
                                self.personal.link(report_id,replay_id,"metric_for")
                            except (PermissionError,ValueError):pass
                    self._new_alerts(steam_alerts(previous_steam, steam_data))
                    self.last_success["steam"] = datetime.now(timezone.utc)
                    self._activity("Steam growth reporting updated")
                    self._render_all()
                elif kind == "marketing_data":
                    self.marketing_report = data
                    self.last_success["marketing"] = datetime.now(timezone.utc)
                    self._activity("Marketing research refreshed, " +
                                   str(len(data.get("opportunities", []))) + " unverified signals")
                    self._render_all()
                elif kind == "news_data":
                    self.news_brief, errors = data
                    self.last_success["news"] = datetime.now(timezone.utc)
                    self._activity("Public news briefing updated" +
                                   (f" ({len(errors)} feed errors)" if errors else ""))
                    self._render_all()
                elif kind == "index_data":
                    generation, data = data
                    if generation != self.project_generation:
                        continue
                    self._activity("Code index completed: " + str(data.get("indexed", 0)) + " files")
                    self._chat("APEX / DEVELOPMENT", f"Indexed {data.get('indexed', 0)} files locally; skipped {data.get('skipped', 0)}. Only approved-folder search snippets may be used by AI on request.")
                    self._render_all()
                elif kind == "unity_data":
                    generation, data = data
                    if generation != self.project_generation:
                        continue
                    self.unity_report = data
                    if (self.approved_project and self.settings.get("autonomous_small_fixes",True)
                            and self.away_active and self.personal.permitted("projects","local")):
                        issue_list=list(data.get("issues",[]))
                        root_project=self.approved_project
                        captured_generation=self.project_generation
                        def repair_worker():
                            guard=WorkspaceGuard(root_project)
                            result=self.autonomy.handle_unity_warnings(guard,issue_list,enabled=True,
                                   authorized_project=root_project,
                                   permission_check=lambda: captured_generation==self.project_generation and
                                     self.personal.permitted("projects","local") and self.away_monitor.status(),max_per_day=2)
                            return captured_generation,result
                        self._spawn("autofix",repair_worker,"autofix_data")
                    errors = [x for x in data.get("issues", []) if x.get("severity") == "error"]
                    new_alerts=[]
                    for issue in errors[:5]:
                        import hashlib
                        fingerprint=hashlib.sha256((issue.get("file", "")+issue.get("message", "")).encode("utf-8")).hexdigest()[:18]
                        new_alerts.append({"key":"unity:"+fingerprint,"severity":"warning", "title":"Unity error detected",
                                           "details":issue.get("message", "")[:250]})
                    self._new_alerts(new_alerts)
                    if getattr(self,"unity_scan_requested",False):
                        lines = [(e.get("file", "") + ": " + e.get("message", ""))[:250]
                                 for e in data.get("issues", [])[:8]]
                        self._chat("APEX / UNITY", f"Scanned {len(data.get('log_sources', []))} log sources. "
                                   f"Sampled {len(errors)} distinct errors and {data.get('sampled_warnings', 0)} warnings.\n"
                                   + "\n".join(lines))
                    self.unity_scan_requested=False
                    self._render_all()
                elif kind == "autofix_data":
                    generation, actions=data
                    if generation!=self.project_generation:continue
                    completed=[a for a in actions if a.get("status")=="static_verified"]
                    for item in completed:
                        self.personal.audit("autofix","static_verified","CS0105: "+str(item.get("file",""))[:190])
                        self._activity("AUTO-FIX: single duplicate C# using removed, static-verified; Unity compile still needed")
                        self._new_alerts([{"key":"auto-fix:"+str(item.get("backup","")),"severity":"info",
                            "title":"Small C# cleanup performed",
                            "details":"One duplicate using directive removed with a local backup. Run Unity compilation to verify."}])
                    if completed:
                        self.index_project()
                        if (self.settings.get("phone_brief_enabled",False)
                            and self.settings.get("phone_alert_on_autofix",True)
                            and self.personal.permitted("projects","phone") and self.phone.configured()):
                            text="APEX small fix: " + str(len(completed)) + " duplicate C# import(s) removed and locally backed up. Static check passed; full Unity compilation pending. No deployment."
                            self._spawn("phone",lambda:self.phone.send(text,message_type="autofix",enabled=True,
                                digest_id="fix:"+str(completed[0].get("backup",""))),"phone_result")
                elif kind == "operations_data":
                    if data is not None:
                        tid,job,state,result=data
                        details=" / "+str(result.get("reason",result.get("note","")))[:115] if result else ""
                        self._activity("OPS "+job+" → "+state+details)
                        if state!="completed":
                            self._new_alerts([{"key":"ops:"+tid,"severity":"warning","title":"Operations task needs attention",
                                "details":job+" / "+state+details}])
                        if (self.settings.get("phone_brief_enabled",False) and
                            self.personal.permitted("operations","phone") and self.phone.configured()):
                            # Only status and counts are transmitted; never local paths,
                            # source code, screenshots, raw logs or API credentials.
                            msg="APEX operations: "+job.replace("_"," ")+" / "+state+"."
                            if job=="unity_editmode_tests":
                                msg+=" Verified tests: "+str(bool(result.get("tests_verified",False)))+"."
                            self._spawn("ops_phone",lambda:self.phone.send(msg,message_type="planning",enabled=True,
                                digest_id="ops:"+tid),"phone_result")
                        self.root.after(450,self._ops_tick)
                elif kind == "phone_commands_data":
                    if data.get("count",0):
                        self._activity(str(data["count"])+" authorized private phone command(s) handled")
                        self.root.after(400,self._ops_tick)
                elif kind == "phone_result":
                    self._activity("Phone briefing: "+str(data.get("status","unknown")))
                elif kind == "verified_patch_data":
                    generation,result=data
                    if generation!=self.project_generation:
                        self._activity("Unity patch verification returned for a different project; inspect backups")
                    else:
                        state=str(result.get("state","unknown"))
                        self._activity("Reviewed Unity source patch → "+state)
                        if state=="verified":
                            self._chat("APEX / CODE EDIT", "Patch was approved and Unity EditMode tests verified a passing result. Gameplay behavior still needs owner inspection.")
                        elif state=="rolled_back":
                            self._chat("APEX / CODE EDIT", "Unity tests did not verify the patch; original file was restored from the backup.")
                        else:
                            self._chat("APEX / CODE EDIT", "Patch verification needs manual review: "+str(result.get("reason","Unknown"))[:250])
                        self.index_project()
                elif kind == "patch_data":
                    generation, (proposal, spent, model) = data
                    if generation != self.project_generation:
                        self._activity("Discarded patch because project authorization changed")
                        continue
                    self._activity("AI patch proposal received (not applied)")
                    self.review_patch(proposal, spent, model)
                    self._render_all()
                elif kind == "ptt_data":
                    phrase = str(data).strip()
                    if phrase:
                        self.send(phrase=phrase, speak=True)
                    else:
                        self._chat("SYSTEM", "No speech was recognized. Try push-to-talk again.")
                elif kind == "context_warning":
                    self._activity(str(data) + " cloud/Steam context source(s) could not refresh")
                elif kind == "ai_data":
                    self.mini.set_recognition_status("AI / ANSWER RECEIVED; READY FOR NEXT TURN")
                    self._ai_request_spoken = False
                    (text, usd, model), should_speak = data
                    if self.auto_ai_pending:
                        try:
                            (ROOT / "data" / "last_paid_brief_date.txt").write_text(datetime.now().date().isoformat(),encoding="utf-8")
                        except OSError:
                            self._activity("Could not save daily AI brief schedule marker")
                        self.auto_ai_pending=False
                    self._chat("APEX", text + f"\nModel: {model} • Estimated cost: ${usd:.5f}")
                    if should_speak:
                        self.speaker.say(text[:1250])
                    self._render_all()
                elif kind == "job_error":
                    job, reason = data
                    # Never dump HTTP response bodies, keys, auth session, or private records.
                    self._activity(job.upper() + " error — " + reason[:95])
                    if job in ("auth", "cloud", "steam", "ai"):
                        self._chat("SYSTEM", job.upper() + " couldn't complete: " + reason[:190])
                    if job == "ai":
                        self.auto_ai_pending=False
                        self.mini.set_recognition_status("AI / REQUEST FAILED. SEE SYSTEM MESSAGE ABOVE")
                        if self._ai_request_spoken:
                            self.speaker.say("I could not complete that AI request. Check the displayed error.")
                        self._ai_request_spoken=False
                    if job == "auth":
                        self.store.forget()  # Invalidated saved refresh sessions should not recur.
                    self._render_all()
                elif kind == "presence":
                    self.face_visible=bool(data)
                    self.away_monitor.presence(self.face_visible)
                elif kind == "mic_level":
                    self.mic_level=float(data)
                elif kind == "status":
                    if data.startswith("Camera: "):
                        self.camera_active=True
                        self.camera_btn.configure(text="CAMERA  •  ON")
                    elif data == "Camera stopped" or data.startswith("Camera error"):
                        self.camera_active=False
                        self.face_visible=False
                        self.away_monitor.camera_unavailable()
                        self.camera_btn.configure(text="CAMERA  •  OFF")
                    if data.startswith("Microphone: "):
                        self.microphone_active=True
                        self.mic_btn.configure(text="VOICE  •  ON")
                    elif data == "Microphone stopped" or data.startswith("Microphone error"):
                        self.microphone_active=False
                        self.mic_btn.configure(text="VOICE  •  OFF")
                    if data.startswith("Speech:") or data.startswith("Speech output error"):
                        self.mini.set_audio_status(data)
                    self.status_var.set(str(data)[:150])
                elif kind == "voice_partial":
                    if self.mini.window.state() == "normal":
                        self.mini.set_recognition_status("HEARING / " + str(data)[:115] + " ...")
                elif kind == "voice_transcript":
                    sentence, action = data
                    if action == "ignore":
                        status = "HEARD / " + sentence[:90] + " — NOT SENT. SAY APEX OR TAP TALK"
                    elif action == "wake":
                        status = "WAKE RECOGNIZED / CONVERSATION OPEN. ASK YOUR QUESTION"
                    elif action == "utterance":
                        status = "RECOGNIZED / " + sentence[:95] + " — ACCEPTED FOR PROCESSING"
                    else:
                        status = "CONVERSATION ENDED / SAY APEX TO RESTART"
                    if self.mini.window.state() == "normal":
                        self.mini.set_recognition_status(status)
                elif kind == "voice_wake":
                    self._voice_wake(bool(data))
                elif kind == "voice_sleep":
                    self._voice_sleep()
                elif kind == "voice":
                    self.send(phrase=data[0], speak=data[1])
                elif kind == "tray":
                    self._handle_tray(data)
                elif kind == "greet":
                    self._chat("APEX", data)
                    self.speaker.say(data)
                elif kind == "job_done":
                    self.inflight.discard(data)
        except queue.Empty:
            pass
        if not self._quitting:
            self.root.after(125, self._drain)

    def close(self):
        if self._quitting:
            return
        self._quitting = True
        if getattr(self, "tray", None):
            self.tray.stop()
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
