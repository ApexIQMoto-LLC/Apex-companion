"""Local user configuration; no vendor account or cloud required."""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path

@dataclass(frozen=True)
class Settings:
    app_name: str = "APEX Companion"
    bind_host: str = "127.0.0.1"
    port: int = 8765
    poll_seconds: int = 10
    watch_processes: list[str] = field(default_factory=lambda: ["Unity.exe", "Unity Hub.exe", "python.exe"])
    unity_editor_log: str = ""
    show_log_tail: bool = False
    log_tail_lines: int = 15
    redact_paths: bool = True

    @classmethod
    def load(cls, path: str | Path) -> "Settings":
        fp = Path(path)
        if not fp.exists():
            raise FileNotFoundError(f"Config not found: {fp}. Copy config.example.json to config.local.json")
        content = json.loads(fp.read_text(encoding="utf-8"))
        if not isinstance(content, dict):
            raise ValueError("Configuration must be a JSON object")
        supported = set(cls.__dataclass_fields__)
        unknown = set(content) - supported
        if unknown:
            raise ValueError(f"Unknown config keys: {', '.join(sorted(unknown))}")
        value = cls(**content)
        # This starter deliberately refuses public network binding.
        if value.bind_host not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("Public network binding disabled. Use an authenticated private tunnel; see docs/REMOTE.md")
        if not 1 <= value.port <= 65535 or value.poll_seconds < 1:
            raise ValueError("Invalid port or poll interval")
        if not 0 <= value.log_tail_lines <= 100:
            raise ValueError("log_tail_lines must be 0..100")
        return value
