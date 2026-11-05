"""Local, inspectable long-term memory. Nothing syncs to a cloud database.

Conversation text is stored on this PC if enabled. Selected snippets are sent to
OpenAI only when the user makes an AI request. Do not store tokens or passwords.
"""
from __future__ import annotations

import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from .project_index import redact

MEMORY_PATTERN = re.compile(r"^\s*(?:apex[:,]?\s*)?(?:please\s+)?(?:remember\s+(?:that\s+)?|make\s+a\s+note\s+(?:that\s+)?)\s*(.+)$", re.I | re.S)
PRIORITY_PATTERN = re.compile(r"^\s*(?:[-*]\s*)?(?:apex[:,]?\s*)?remember\s+this\s+priority\s*:\s*(.+?)\s*$", re.I)
WORDS = re.compile(r"[a-z0-9_]{3,}", re.I)
STOP = {"about", "what", "when", "where", "this", "that", "there", "were", "have", "from", "your", "with", "them", "then", "into", "will", "should", "does", "some", "tell", "show", "please", "apex", "could", "would", "current", "latest", "update", "status"}
# Redact likely user-supplied credentials before persisting a memory.
PRIVATE = re.compile(r"(?i)\b(?:password|api[_ -]?key|refresh[_ -]?token|secret|2fa|otp)\b\s*(?::|=|is)\s*\S+")


def clean(text: str, limit: int = 1200) -> str:
    text = PRIVATE.sub("[REDACTED]", redact(str(text)))
    return text.replace("\x00", "").strip()[:limit]


def keywords(text: str) -> set[str]:
    return {w for w in WORDS.findall(text.lower()) if w not in STOP}


class MemoryVault:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        with self._db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fact TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'explicit',
                created_at TEXT NOT NULL,
                last_used_at TEXT)""")
            db.execute("""CREATE TABLE IF NOT EXISTS conversation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                at_utc TEXT NOT NULL,
                user_text TEXT NOT NULL,
                assistant_text TEXT NOT NULL)""")

    def _db(self):
        return sqlite3.connect(self.path, timeout=5)

    def add(self, fact: str, category="explicit") -> int:
        fact = clean(fact)
        if not fact or fact == "[REDACTED]":
            raise ValueError("Nothing safe to remember")
        if len(fact) < 5:
            raise ValueError("Memory is too short")
        if len(fact) > 1000:
            fact = fact[:1000]
        now = datetime.now(timezone.utc).isoformat()
        with self.lock, self._db() as db:
            existing = db.execute("SELECT id FROM memories WHERE lower(fact)=lower(?)", (fact,)).fetchone()
            if existing:
                return int(existing[0])
            cursor = db.execute("INSERT INTO memories(fact,category,created_at) VALUES (?,?,?)", (fact, category, now))
            return int(cursor.lastrowid)

    def remember_from_message(self, user_text: str) -> int | None:
        """Capture explicit commands, including a `Remember this priority:` line
        inside a larger numbered briefing request. Never infer a memory merely
        because the user discussed a topic.
        """
        lines=str(user_text).splitlines()
        for line in lines:
            priority=PRIORITY_PATTERN.match(line)
            if priority:
                fact=priority.group(1).strip().strip('"\u201c\u201d').strip()
                return self.add(fact)
        matched=MEMORY_PATTERN.match(user_text)
        if not matched:
            return None
        return self.add(matched.group(1).strip().rstrip(".!"))

    def log_exchange(self, user_text: str, assistant_text: str, max_turns: int = 350):
        user = clean(user_text, 3000)
        assistant = clean(assistant_text, 5000)
        if not user or not assistant:
            return
        with self.lock, self._db() as db:
            db.execute("INSERT INTO conversation(at_utc,user_text,assistant_text) VALUES (?,?,?)",
                       (datetime.now(timezone.utc).isoformat(), user, assistant))
            # Bounded history limits the amount of personal data retained.
            db.execute("DELETE FROM conversation WHERE id NOT IN (SELECT id FROM conversation ORDER BY id DESC LIMIT ?)", (max(0, max_turns),))

    def recent(self, limit=6) -> list[dict]:
        with self.lock, self._db() as db:
            rows = db.execute("SELECT id,at_utc,user_text,assistant_text FROM conversation ORDER BY id DESC LIMIT ?", (min(max(limit,0),15),)).fetchall()
        return [{"id":r[0], "at_utc":r[1], "user":r[2], "assistant":r[3]} for r in reversed(rows)]

    def search(self, question: str, limit=5, include_conversation=True) -> list[dict]:
        terms = keywords(question)
        with self.lock, self._db() as db:
            facts = db.execute("SELECT id,fact,created_at FROM memories ORDER BY id DESC LIMIT 1500").fetchall()
            conversations = (db.execute("SELECT id,at_utc,user_text,assistant_text FROM conversation ORDER BY id DESC LIMIT 150").fetchall()
                             if include_conversation else [])
        scored: list[tuple[float,dict]] = []
        for i, fact, at in facts:
            hits = len(terms & keywords(fact)) if terms else 0
            score = 5.0 + hits * 4.0
            scored.append((score, {"kind":"memory", "id": i, "date":at[:10], "text":fact[:850]}))
        for i, at, user, answer in conversations:
            body = user + " " + answer[:700]
            hits = len(terms & keywords(body))
            if not hits and terms:
                continue
            # Recent conversations supplement user-approved memories, but are not facts.
            scored.append((hits * 2 + 0.2, {"kind":"past_conversation", "id":i, "date":at[:10],
                                               "text": "User: " + user[:420] + " | Apex: " + answer[:500]}))
        scored.sort(key=lambda item: (item[0], item[1]["id"]), reverse=True)
        return [entry for _, entry in scored[:max(0,min(limit,12))]]

    def list_memories(self, limit=100):
        with self.lock, self._db() as db:
            rows = db.execute("SELECT id,fact,category,created_at FROM memories ORDER BY id DESC LIMIT ?", (max(1,min(limit,250)),)).fetchall()
        return [{"id": i,"fact":fact,"category":category,"created_at":at} for i,fact,category,at in rows]

    def delete(self, memory_id: int) -> bool:
        with self.lock, self._db() as db:
            return db.execute("DELETE FROM memories WHERE id=?", (int(memory_id),)).rowcount > 0

    def forget_all(self):
        with self.lock, self._db() as db:
            db.execute("DELETE FROM memories")
            db.execute("DELETE FROM conversation")

    def clear_conversation(self):
        with self.lock, self._db() as db:
            db.execute("DELETE FROM conversation")
