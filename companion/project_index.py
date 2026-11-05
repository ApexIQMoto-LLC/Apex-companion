"""Explicitly authorized local-folder code index; never sends file content to AI."""
from __future__ import annotations
import os
from pathlib import Path
import re
import sqlite3

SKIP_DIRS = {
    ".git", ".vs", ".venv", "node_modules", "library", "temp", "obj", "bin",
    "logs", "build", "builds", "cache", "caches", "packages", "userSettings".lower(),
    ".idea", ".vscode", ".next", "dist", "coverage", "data"
}
EXTENSIONS = {".cs", ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".md", ".txt", ".cpp", ".h", ".hpp", ".shader", ".compute", ".uxml", ".uss", ".sql", ".yaml", ".yml"}
BLOCKED_FILENAME = re.compile(r"(^\.|\.env|secret|credential|token|password|private|keyfile|\.pem$|\.pfx$|\.p12$|\.key$|\.sqlite)", re.I)
SENSITIVE_PATTERNS = (
    re.compile(r"(?i)(OPENAI_API_KEY|SUPABASE_SERVICE_ROLE_KEY|PRIVATE_KEY|PASSWORD|SECRET|ACCESS_TOKEN|REFRESH_TOKEN)\s*[=:]\s*[^\s'\";,]+"),
    re.compile(r"sb_secret_[A-Za-z0-9_-]{8,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----"),
)


def redact(text):
    for pat in SENSITIVE_PATTERNS:
        text = pat.sub("[REDACTED]", text)
    return text


class ProjectIndexer:
    def __init__(self, dbpath):
        self.dbpath = str(dbpath)
        with sqlite3.connect(self.dbpath) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS project_files (
                path TEXT PRIMARY KEY, root TEXT NOT NULL, content TEXT NOT NULL,
                indexed_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_project_root ON project_files(root)")

    def index(self, root, max_files=1500, max_file_bytes=100_000, max_total_bytes=12_000_000):
        root = Path(root).resolve()
        if not root.is_dir():
            raise ValueError("The selected project directory does not exist")
        count, bytes_read, skipped = 0, 0, 0
        with sqlite3.connect(self.dbpath) as db:
            # Only this user's selected root is refreshed. No other indexed roots are touched.
            db.execute("DELETE FROM project_files WHERE root=?", (str(root),))
            for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
                dirnames[:] = [x for x in dirnames if x.lower() not in SKIP_DIRS and not (Path(dirpath) / x).is_symlink()]
                for name in filenames:
                    candidate = Path(dirpath) / name
                    if (candidate.suffix.lower() not in EXTENSIONS or BLOCKED_FILENAME.search(name) or candidate.is_symlink()):
                        skipped += 1
                        continue
                    try:
                        size = candidate.stat().st_size
                    except OSError:
                        skipped += 1
                        continue
                    if size > max_file_bytes or size == 0:
                        skipped += 1
                        continue
                    if count >= max_files or bytes_read + size > max_total_bytes:
                        return {"indexed": count, "skipped": skipped, "bytes_read": bytes_read, "limit_reached": True}
                    try:
                        source = candidate.read_text(encoding="utf-8")
                    except (UnicodeDecodeError, OSError):
                        skipped += 1
                        continue
                    if "\x00" in source:
                        skipped += 1
                        continue
                    # Store a bounded, locally redacted preview, not raw secrets.
                    db.execute("INSERT OR REPLACE INTO project_files(path,root,content) VALUES (?,?,?)",
                               (str(candidate), str(root), redact(source[:22_000])))
                    count += 1
                    bytes_read += size
        return {"indexed": count, "skipped": skipped, "bytes_read": bytes_read, "limit_reached": False}

    def search(self, query, limit=12, root=None):
        words = [w.lower() for w in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{1,50}", query)][:5]
        if not words:
            return []
        with sqlite3.connect(self.dbpath) as db:
            # No user-controlled SQL fragments: all values parameterized.
            clauses = " OR ".join(["lower(content) LIKE ? OR lower(path) LIKE ?" for _ in words])
            args = []
            for word in words:
                args.extend([f"%{word}%", f"%{word}%"])
            if root is not None:
                clauses = "root = ? AND (" + clauses + ")"
                args = [str(Path(root).resolve())] + args
            rows = db.execute(f"SELECT path,content FROM project_files WHERE {clauses} LIMIT ?", args + [limit]).fetchall()
        result = []
        for path, content in rows:
            lc = content.lower()
            matches = [lc.find(x) for x in words if x in lc]
            pos = min(matches) if matches else 0
            snippet = content[max(0, pos - 130):pos + 300].replace("\n", " ")
            result.append({"path": path, "snippet": snippet})
        return result

    def clear_root(self, root):
        """Forget all cached snippets for one formerly approved workspace."""
        with sqlite3.connect(self.dbpath) as db:
            db.execute("DELETE FROM project_files WHERE root=?", (str(Path(root).resolve()),))
