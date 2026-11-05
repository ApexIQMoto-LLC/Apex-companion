import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULTS = {
    "assistant_name": "Apex",
    "wake_phrases": ["hey apex", "hey jarvis"],
    "chat_model": "gpt-6-luna",
    "deep_model": "gpt-6.1-terra",
    "monthly_budget_usd": 15.00,
    "supabase_url": "",
    "supabase_publishable_key": "",  # Public client key; RLS enforces access.
    "daily_request_limit": 70,
    "max_output_tokens": 1300,
    "enable_local_memory": True,
    "enable_readonly_tools": True,
    "approved_project_root": "",
    "scan_unity_minutes": 10,
    "unity_include_editor_log": False,
    "desktop_alerts": True,
    "speak_alerts": False,
    "auto_paid_ai_daily": False,  # Only runs after explicit opt-in; local spend caps still apply.
    "daily_ai_brief_hour": 9,
    "max_context_turns": 6,
    "camera_index": 0,
    "camera_autostart": False,
    "remember_cloud_session": True,
    "send_aggregates_to_ai": False,  # User may opt out; only sanitized stats in user-initiated AI chat.
    "cloud_refresh_minutes": 5,
    "steam_refresh_minutes": 30,
    "microphone_autostart": False,
    "greeting_cooldown_minutes": 180,
    "presence_absence_seconds": 60,
    "quiet_hours_start": 23,
    "quiet_hours_end": 8,
    "vosk_model_path": "models/vosk-model-small-en-us-0.15",
    "news_topics": [
        "motorcycle technology industry",
        "business and startups",
        "artificial intelligence business",
        "gaming industry Steam Unity"
    ],
}


def load_settings():
    path = ROOT / "config.json"
    merged = dict(DEFAULTS)
    if path.exists():
        incoming = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(incoming, dict):
            raise ValueError("config.json must contain an object")
        merged.update(incoming)
    return merged


def ensure_local_files():
    (ROOT / "data").mkdir(exist_ok=True)
    notes = ROOT / "data" / "apexiq_notes.md"
    if not notes.exists():
        notes.write_text(
            "# ApexIQ Moto working notes\n"
            "This file is local to your PC. Add the project details you want "
            "the assistant to know. Only the contents of this file are "
            "provided to the AI when you ask an AI question.\n\n"
            "- ApexIQ Moto: motorcycle telemetry and rider coaching.\n"
            "- Replay Studio: Unity-based ride replay and analysis project.\n"
            "- Focus: development, testing, business, marketing, and operations.\n",
            encoding="utf-8",
        )

# v0.7 settings are merged with existing config.json, never overwrite existing
# keys; values here are conservative compatibility defaults.
DEFAULTS.update({
    "autonomous_small_fixes": False,   # Only documented deterministic CS0105; needs approved project folder.
    "autonomy_no_paid_calls": True,   # No unattended paid OpenAI requests.
    "phone_brief_enabled": False,     # Phone transmission always separately opted in.
    "phone_brief_hour": 9,
    "phone_alert_on_autofix": True,
    "personal_activity_enabled": False,  # Companion-only operations, never screen/browser monitoring.
    "foreground_app_sampling": False, # Also requires COMPUTER / LOCAL permission.
    "away_idle_minutes": 8,
    "away_camera_grace_seconds": 150,
})

# v0.8 adds a durable local work queue; only finite read-only jobs are enabled
# automatically while AWAY. Unity testing and phone commands remain opt-in.
DEFAULTS.update({
    "ops_auto_away": True,
    "ops_allow_unity_tests": False,
    "ops_unity_timeout": 420,
    "unity_editor_path": "",
    "ops_phone_commands": False,
})

# v0.9 local-first content production; one deterministic daily draft, no API cost.
DEFAULTS.update({
    "marketing_auto_daily_draft": True,
    "marketing_external_oauth_enabled": True,   # Owner-initiated OAuth available; no automatic API imports or publishing.
    "marketing_auto_publish": False,
    "marketing_auto_spend": False,
    "marketing_auto_outreach": False,
})

# v0.10: Tray-first UI and time-bounded natural follow-up dialogue.
DEFAULTS.update({
    "launch_minimized_to_tray": True,
    "conversation_idle_seconds": 120,
})

# v0.10.1: Explicit input-device selection can fix silent default microphones.
# Null follows the Windows default input device; PortAudio indices are local to the PC.
DEFAULTS.update({"microphone_input_device": None})

# v0.10.2: local spoken output through built-in Windows SAPI by default.
DEFAULTS.update({
    "speech_output_backend": "windows",
    "speech_output_volume": 100,
    "microphone_input_device": None,
})

# v0.10.4: quiet-turn endpoints, optional enhanced offline speech and voice.
DEFAULTS.update({
    "speech_pause_seconds": 2.1,
    "speech_vad_mode": 3,
    "speech_enhanced_recognition": False,
    "speech_voice_name": "af_heart",
})

# v0.11: automatic task routing. External cloud providers are OFF by default
# until the owner authorizes cross-provider transfer of conversation content.
DEFAULTS.update({
    "auto_model_routing": True,
    "coding_model": "gpt-6.1-sol",
    "analysis_model": "gpt-6.1-terra",
    "allow_external_ai_providers": False,
})

# v0.11 extended provider pool: every additional provider is opt-in. The
# attached price for each third-party model must be configured before routing.
DEFAULTS.update({
    "enabled_ai_providers": [],
    "allow_local_ai": False,
    "enabled_local_ai_providers": [],
    "provider_models": {},
    "provider_task_models": {},
    "local_ai_urls": {},
    "model_rates_usd_per_million": {},
    "max_model_attempts": 5,
})
