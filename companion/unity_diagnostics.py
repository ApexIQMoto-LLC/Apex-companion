"""Read-only diagnostics for an explicitly selected Unity project.

Never traverses the entire PC and never interprets log contents as commands.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from datetime import datetime, timezone
from .project_index import redact

ERROR = re.compile(r"(\berror\s+CS\d+\b|\bException\b|\bNullReferenceException\b|\bBuildFailed\b|\b(?:error|fatal)\s*:)" ,re.I)
WARN = re.compile(r"\b(?:warning\s+CS\d+|warning\s*:|obsolete\b)\b",re.I)
FILE_LINE = re.compile(r"(?P<path>Assets[/\\][^\r\n:()]{1,260}\.cs)\((?P<line>\d{1,7}),(?P<column>\d{1,6})\)")


def allowed_logs(project_root: str | Path, include_editor_log=False) -> list[Path]:
    root = Path(project_root).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Choose an existing Unity project folder")
    candidates = []
    for local in ("Logs", "logs"):
        folder = root / local
        if folder.is_dir() and not folder.is_symlink():
            candidates.extend(sorted(folder.glob("*.log"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)[:4])
    if include_editor_log and os.name == "nt":
        base = os.environ.get("LOCALAPPDATA", "")
        if base:
            candidates.append(Path(base) / "Unity" / "Editor" / "Editor.log")
    return [p for p in candidates if p.is_file() and not p.is_symlink()][:5]


def scan_unity_logs(project_root: str | Path, include_editor_log=False, tail_bytes=240_000, max_issues=25) -> dict:
    root = Path(project_root).expanduser().resolve(strict=True)
    found: list[dict] = []
    reports = []
    for path in allowed_logs(root, include_editor_log):
        try:
            with path.open("rb") as fp:
                fp.seek(0, os.SEEK_END)
                size=fp.tell()
                fp.seek(max(0,size-tail_bytes))
                raw=fp.read(tail_bytes)
            text=raw.decode("utf-8", errors="replace")
            if size>tail_bytes:
                text="\n".join(text.splitlines()[1:])
            for line in text.splitlines():
                severity = "error" if ERROR.search(line) else ("warning" if WARN.search(line) else None)
                if not severity:
                    continue
                loc=FILE_LINE.search(line)
                found.append({"severity":severity, "message":redact(line.strip())[:360],
                              "file":loc.group("path").replace("\\","/") if loc else "",
                              "line":int(loc.group("line")) if loc else None})
            reports.append({"source": path.name, "checked_mtime_utc":datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat(),"bytes_scanned":min(size,tail_bytes)})
        except (OSError,UnicodeError):
            reports.append({"source":path.name, "error":"Cannot read file"})
    # Latest first; repeated error lines are generally low value.
    unique=[];seen=set()
    for issue in reversed(found):
        signature = (issue["severity"],issue["message"][:180])
        if signature in seen:continue
        seen.add(signature);unique.append(issue)
        if len(unique)>=max_issues:break
    return {"checked_at_utc":datetime.now(timezone.utc).isoformat(),
            "project":root.name,"log_sources":reports,"sampled_errors":sum(e["severity"]=="error" for e in unique),
            "sampled_warnings":sum(e["severity"]=="warning" for e in unique),
            "issues":unique,"note":"Tail samples of approved logs, not a complete Unity diagnostic or proof of current compile errors."}
