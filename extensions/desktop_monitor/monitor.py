"""Read-only process and Unity log diagnostics; no desktop control."""
from __future__ import annotations
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
import re
from .settings import Settings

# Do not send raw secrets or arbitrary log files to external services.
SECRET_PATTERN = re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+|api[_-]?key\s*[:=]\s*|token\s*[:=]\s*|password\s*[:=]\s*)([^\s,;]+)")
WINDOWS_PATH = re.compile(r"[a-zA-Z]:\\(?:[^\\\r\n]+\\)*[^\\\r\n ]+")
HOME_PATH = re.compile(r"/(?:home|Users)/[^/\s]+")

def clean_text(value: str, redact_paths: bool = True) -> str:
    value = SECRET_PATTERN.sub(lambda m: m.group(1) + "[REDACTED]", value)
    if redact_paths:
        value = WINDOWS_PATH.sub("[LOCAL_PATH]", value)
        value = HOME_PATH.sub("[HOME]", value)
    return value

def process_snapshot(names: list[str]) -> dict[str, object]:
    if not names:
        return {"available": True, "matches": []}
    try:
        import psutil  # type: ignore
    except ImportError:
        return {"available": False, "reason": "Install psutil (pip install -e '.[processes]')", "matches": []}
    selected = {n.casefold() for n in names}
    found = []
    for proc in psutil.process_iter(attrs=["pid", "name"]):
        try:
            info = proc.info
            if str(info.get("name") or "").casefold() in selected:
                found.append({"name": info["name"], "pid": info["pid"]})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return {"available": True, "matches": sorted(found, key=lambda p: (str(p["name"]), int(p["pid"])))}

def log_snapshot(path: str, lines: int, redact_paths: bool) -> dict[str, object]:
    if not path:
        return {"configured": False, "recent": [], "errors": 0, "warnings": 0}
    fp = Path(path).expanduser()
    if not fp.is_file():
        return {"configured": True, "exists": False, "recent": [], "errors": 0, "warnings": 0}
    # Restrict size of read to most recent 128 KiB to avoid huge Unity Editor logs.
    with fp.open("rb") as handle:
        handle.seek(0, 2)
        size = handle.tell()
        handle.seek(max(0, size - 131072))
        raw = handle.read().decode("utf-8", errors="replace")
    recent = raw.splitlines()[-lines:] if lines else []
    errors = sum(1 for line in raw.splitlines() if re.search(r"(?i)(\berror\b|exception)", line))
    warnings = sum(1 for line in raw.splitlines() if re.search(r"(?i)\bwarning\b", line))
    return {"configured": True, "exists": True, "errors": errors, "warnings": warnings,
            "recent": [clean_text(s[:500], redact_paths) for s in recent]}

def capture(settings: Settings) -> dict[str, object]:
    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source": "local",
        "mode": "read-only",
        "processes": process_snapshot(settings.watch_processes),
        "unity": log_snapshot(settings.unity_editor_log,
                              settings.log_tail_lines if settings.show_log_tail else 0,
                              settings.redact_paths),
    }
    return result
