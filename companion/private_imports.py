"""Encrypted, permission-gated manual imports of OWNER-SELECTED local files.

No bank, medical, email, calendar or browser account is silently connected.
No key is written into the app directory. A Windows Credential Manager entry
holds the Fernet key used for this database. Import is local; AI context is
separately controlled by PersonalIntelStore scope permission.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sqlite3
from datetime import datetime,timezone
from pathlib import Path

from .personal_intelligence import SCOPES,utc_now
from .project_index import redact

VAULT_SERVICE="APEXIQ Companion Encrypted Imports"
MAX_BYTES=3_000_000
EXTENSIONS={".csv",".json",".ics",".txt"}
BLOCKED_KEYS=re.compile(r"(?i)(password|passwd|api.?key|access.?token|refresh.?token|secret|routing|account.?number|card.?number|cvv|pin|social.?security|ssn|cookie|auth|credential)")
PAYMENT_NUMBER=re.compile(r"\b(?:\d[ -]?){13,19}\b")
SSN=re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def clean_value(value,limit=600):
    text=redact(str(value or ""))
    text=PAYMENT_NUMBER.sub("[REDACTED IDENTIFIER]",text)
    text=SSN.sub("[REDACTED IDENTIFIER]",text)
    return text[:limit]


def rows_from_selected_file(path:Path,limit=600):
    if path.is_symlink() or not path.is_file() or path.suffix.lower() not in EXTENSIONS:
        raise ValueError("Only selected normal CSV, JSON, ICS and TXT files are supported")
    if path.stat().st_size>MAX_BYTES:
        raise ValueError("Import exceeds 3 MB; export a smaller, relevant file")
    raw=path.read_text(encoding="utf-8-sig")
    ext=path.suffix.lower()
    rows=[]
    if ext==".csv":
        for row in csv.DictReader(io.StringIO(raw)):
            rows.append({str(k):v for k,v in row.items() if k and not BLOCKED_KEYS.search(str(k))})
            if len(rows)>=limit:break
    elif ext==".json":
        obj=json.loads(raw)
        if isinstance(obj,list):records=obj
        elif isinstance(obj,dict):
            records=next((v for v in obj.values() if isinstance(v,list)),[obj])
        else:records=[]
        for row in records[:limit]:
            if isinstance(row,dict):
                rows.append({str(k):v for k,v in row.items() if not BLOCKED_KEYS.search(str(k))})
            else:
                rows.append({"text":str(row)[:500]})
    elif ext==".ics":
        current=None
        for line in raw.splitlines():
            if line=="BEGIN:VEVENT":current={}
            elif line=="END:VEVENT" and current is not None:
                rows.append(current);current=None
                if len(rows)>=limit:break
            elif current is not None and ":" in line:
                key,val=line.split(":",1)
                key=key.split(";",1)[0].upper()
                if key in ("SUMMARY","DTSTART","DTEND","LOCATION","DESCRIPTION"):
                    current[key]=val[:500]
    else:
        # TXT: treat non-empty lines as owner-selected notes, not raw transcripts.
        rows=[{"note":line[:900]} for line in raw.splitlines() if line.strip()][:limit]
    sanitized=[]
    for row in rows:
        safe={str(k)[:70]:clean_value(v) for k,v in row.items() if not BLOCKED_KEYS.search(str(k)) and v is not None}
        if safe:sanitized.append(safe)
    return sanitized


class EncryptedImportVault:
    def __init__(self,dbpath,permissions, key_bytes=None):
        self.db=str(dbpath)
        Path(self.db).parent.mkdir(parents=True,exist_ok=True)
        self.permissions=permissions
        self._test_key=key_bytes
        with sqlite3.connect(self.db) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS encrypted_imports(
               id INTEGER PRIMARY KEY AUTOINCREMENT,scope TEXT NOT NULL,source_tag TEXT NOT NULL,
               observed_at TEXT NOT NULL,imported_at TEXT NOT NULL,ciphertext BLOB NOT NULL)""")
            db.execute("CREATE INDEX IF NOT EXISTS encrypted_scope ON encrypted_imports(scope)")

    def _cipher(self):
        try:from cryptography.fernet import Fernet
        except ImportError as e:raise RuntimeError("Install cryptography first") from e
        if self._test_key is not None:
            return Fernet(self._test_key)
        try:
            import keyring
            key=keyring.get_password(VAULT_SERVICE,"encryption_key")
            if not key:
                key=Fernet.generate_key().decode()
                keyring.set_password(VAULT_SERVICE,"encryption_key",key)
                if keyring.get_password(VAULT_SERVICE,"encryption_key")!=key:
                    raise RuntimeError("Credential storage verification failed")
            return Fernet(key.encode())
        except Exception as e:
            raise RuntimeError("Windows Credential Manager unavailable; sensitive import blocked. No plaintext fallback.") from e

    def preview(self,selected_path):
        rows=rows_from_selected_file(Path(selected_path))
        return {"rows":len(rows),"sample_fields":sorted({k for r in rows[:8] for k in r})[:18],
                "notice":"Identifiers and credential fields removed; actual records are not sent to AI without separate permission."}

    def import_file(self,selected_path,scope):
        if scope not in SCOPES or not self.permissions.permitted(scope,"local"):
            raise PermissionError("Enable this category's LOCAL permission first")
        path=Path(selected_path)
        rows=rows_from_selected_file(path)
        if not rows:raise ValueError("Selected file contains no importable records")
        cipher=self._cipher()
        source_tag=hashlib.sha256(path.name.encode("utf-8","replace")).hexdigest()[:16]
        now=utc_now()
        with sqlite3.connect(self.db) as db:
            for item in rows:
                observed=str(item.get("date") or item.get("Date") or item.get("DTSTART") or now)[:40]
                payload=json.dumps(item,ensure_ascii=False).encode()
                db.execute("INSERT INTO encrypted_imports(scope,source_tag,observed_at,imported_at,ciphertext) VALUES(?,?,?,?,?)",
                           (scope,source_tag,observed,now,cipher.encrypt(payload)))
        self.permissions.audit("private_import","success",f"Imported {len(rows)} encrypted {scope} rows from owner-selected file")
        return {"imported":len(rows),"scope":scope,"encrypted":True}

    def search(self,scope,query,destination="local",limit=8):
        if scope not in SCOPES or not self.permissions.permitted(scope,destination):
            return {"status":"permission_denied","scope":scope}
        cipher=self._cipher()
        terms=re.findall(r"[a-z0-9]{3,}",str(query).lower())[:7]
        with sqlite3.connect(self.db) as db:
            rows=db.execute("SELECT observed_at,imported_at,ciphertext FROM encrypted_imports WHERE scope=? ORDER BY id DESC LIMIT 1800",(scope,)).fetchall()
        matching=[]
        for observed,imported,encrypted in rows:
            try:payload=json.loads(cipher.decrypt(encrypted).decode())
            except Exception:continue
            body=json.dumps(payload,ensure_ascii=False).lower()
            if not terms or any(term in body for term in terms):
                matching.append({"observed_at":observed,"imported_at":imported,"source":"owner-selected encrypted import","data":payload})
            if len(matching)>=max(1,min(limit,20)):break
        return {"status":"ok","scope":scope,"matching":matching,
                "caveat":"Owner-imported snapshot, not a live bank, email, health or calendar connection."}

    def counts(self):
        with sqlite3.connect(self.db) as db:
            rows=db.execute("SELECT scope,count(*) FROM encrypted_imports GROUP BY scope").fetchall()
        return {scope:n for scope,n in rows if self.permissions.permitted(scope,"local")}

    def erase_scope(self,scope):
        if scope not in SCOPES:raise ValueError("Invalid permission category")
        with sqlite3.connect(self.db) as db:
            db.execute("PRAGMA secure_delete=ON")
            db.execute("DELETE FROM encrypted_imports WHERE scope=?",(scope,))
        self.permissions.audit("private_import_erase","done",f"Erased encrypted {scope} imports")
