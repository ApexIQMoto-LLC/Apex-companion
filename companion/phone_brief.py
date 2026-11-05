"""Opt-in owner-only Telegram phone digest. Zero auto outbound by default.

The bot token is read only from the local process environment (.env), never
written into JSON, the personal database or the model prompt.
"""
from __future__ import annotations

import json
import os
import re
from .sqlite_utils import open_sqlite
from datetime import date,datetime,timezone
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.parse import quote
from urllib.request import Request,urlopen

from .project_index import redact

# No raw Unity errors, file bodies, names, GPS traces, finances or credentials.
SAFE_TYPES={"health", "steam", "autofix", "planning", "summary"}
SERVICE="APEXIQ Companion Telegram"


def sanitize_phone_text(text):
    text=redact(str(text or ""))
    text=re.sub(r"(?i)(bearer\s+\S+|https?://\S*token\S*|sk-proj-\S+|[A-Za-z]:\\[^\s]+)","[REDACTED]",text)
    # Avoid forwarding unexpected multi-line code blocks, personal paths or HTML.
    text=text.replace("<","(").replace(">",")")
    return text[:1600]


class PhoneBriefing:
    def __init__(self,dbpath):
        self.path=str(dbpath)
        Path(self.path).parent.mkdir(parents=True,exist_ok=True)
        with open_sqlite(self.path) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS phone_deliveries(
              digest_id TEXT PRIMARY KEY, sent_at TEXT NOT NULL, message_type TEXT NOT NULL,
              outcome TEXT NOT NULL)""")

    @staticmethod
    def _credentials():
        # Prefer the Windows Credential Manager, never persist tokens in the app DB.
        try:
            import keyring
            token=keyring.get_password(SERVICE,"bot_token") or ""
            chat=keyring.get_password(SERVICE,"chat_id") or ""
        except Exception:
            token=chat=""
        # Compatibility for manually configured installations.
        token=token or os.getenv("APEX_TELEGRAM_BOT_TOKEN", "").strip()
        chat=chat or os.getenv("APEX_TELEGRAM_CHAT_ID", "").strip()
        return token,chat

    def configured(self):
        token,chat=self._credentials()
        return bool(re.fullmatch(r"\d{5,20}:[A-Za-z0-9_-]{20,}",token) and
                    re.fullmatch(r"-?\d{5,20}",chat))

    def delivered(self,digest_id):
        with open_sqlite(self.path) as db:
            return bool(db.execute("SELECT 1 FROM phone_deliveries WHERE digest_id=? AND outcome='sent'",(digest_id,)).fetchone())

    def send(self, message, *, message_type="summary", enabled=False, digest_id=None, transport=None):
        if not enabled: return {"status":"disabled"}
        if message_type not in SAFE_TYPES:return {"status":"blocked_type"}
        if not self.configured():return {"status":"missing_telegram_configuration"}
        digest_id=str(digest_id or f"{date.today().isoformat()}:{message_type}")[:100]
        with open_sqlite(self.path) as db:
            if db.execute("SELECT 1 FROM phone_deliveries WHERE digest_id=? AND outcome='sent'",(digest_id,)).fetchone():
                return {"status":"already_sent"}
        body=sanitize_phone_text(message)
        if not body:return {"status":"empty"}
        token,chat=self._credentials()
        endpoint="https://api.telegram.org/bot"+quote(token,safe=":")+"/sendMessage"
        payload=json.dumps({"chat_id":chat,"text":body,"disable_web_page_preview":True}).encode()
        request=Request(endpoint,data=payload,headers={"Content-Type":"application/json"},method="POST")
        try:
            # A caller may inject a fake transport in tests; never print URL.
            opener=transport or urlopen
            with opener(request,timeout=9) as response:
                obj=json.loads(response.read(1200).decode("utf-8"))
            ok=(obj.get("ok") is True)
        except (URLError,HTTPError,TimeoutError,OSError,ValueError):
            ok=False
        if ok:
            with open_sqlite(self.path) as db:
                db.execute("INSERT OR REPLACE INTO phone_deliveries(digest_id,sent_at,message_type,outcome) VALUES(?,?,?,?)",
                           (digest_id,datetime.now(timezone.utc).isoformat(),message_type,"sent"))
        return {"status":"sent" if ok else "delivery_failed", "digest_id":digest_id}
