"""APEX v0.7 local, permission-scoped, source-attributed knowledge graph.

Existing 0.6.3 MemoryVault remains untouched. Sensitive integrations are
opt-in. This graph stores ordinary project context; owner-selected financial,
health and similar imports should use the separately encrypted import vault.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
import threading
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

from .memory import clean

SCOPES=("operations","projects","personal","computer","calendar","communications","finance","health")
DEFAULT_PERMISSIONS={
    "operations":(1,1,0),"projects":(1,1,0),"personal":(0,0,0),
    "computer":(0,0,0),"calendar":(0,0,0),"communications":(0,0,0),
    "finance":(0,0,0),"health":(0,0,0),
}
VALID_KINDS={"goal","project","decision","milestone","person","organization","preference","resource","risk","task","observation","other"}
VALID_STATUS={"todo","in_progress","blocked","done","cancelled"}
VALID_SOURCE={"owner_input","cloud_summary","steam_daily","unity_logs","companion_activity","derived","manual_import","conversation"}


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean(x,n=400):
    return clean(str(x or ""),n).replace("\x00","")


class PersonalIntelStore:
    def __init__(self,path):
        self.path=str(path)
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock()
        with self._db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS permissions(scope TEXT PRIMARY KEY,local_read INTEGER NOT NULL,
               send_to_ai INTEGER NOT NULL,send_to_phone INTEGER NOT NULL,changed_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS entities(id TEXT PRIMARY KEY,kind TEXT NOT NULL,title TEXT NOT NULL,
               details TEXT NOT NULL,scope TEXT NOT NULL,source TEXT NOT NULL,source_ref TEXT NOT NULL,
               observed_at TEXT NOT NULL,confidence REAL NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_entity_scope ON entities(scope,updated_at);
            CREATE TABLE IF NOT EXISTS links(source_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
               target_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,relationship TEXT NOT NULL,
               PRIMARY KEY(source_id,target_id,relationship));
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,dedupe_key TEXT UNIQUE NOT NULL,
               category TEXT NOT NULL,title TEXT NOT NULL,summary TEXT NOT NULL,scope TEXT NOT NULL,
               source TEXT NOT NULL,observed_at TEXT NOT NULL,recorded_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_event_time ON events(observed_at);
            CREATE TABLE IF NOT EXISTS plan(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,
               rationale TEXT NOT NULL,source TEXT NOT NULL,scope TEXT NOT NULL,priority INTEGER NOT NULL,
               status TEXT NOT NULL,due_day TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS insights(id INTEGER PRIMARY KEY AUTOINCREMENT,
               fingerprint TEXT UNIQUE NOT NULL,text TEXT NOT NULL,provenance TEXT NOT NULL,
               scope TEXT NOT NULL,sample_size INTEGER NOT NULL,generated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS action_audit(id INTEGER PRIMARY KEY AUTOINCREMENT,
               at_utc TEXT NOT NULL,action TEXT NOT NULL,outcome TEXT NOT NULL,summary TEXT NOT NULL);
            """)
            for scope,flags in DEFAULT_PERMISSIONS.items():
                db.execute("INSERT OR IGNORE INTO permissions VALUES(?,?,?,?,?)",(scope,*flags,utc_now()))

    @contextmanager
    def _db(self):
        db=sqlite3.connect(self.path,timeout=8)
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA secure_delete=ON")
            with db:yield db
        finally:db.close()

    def permissions(self):
        with self.lock,self._db() as db:
            rows=db.execute("SELECT scope,local_read,send_to_ai,send_to_phone,changed_at FROM permissions").fetchall()
        return {s:{"local":bool(loc),"ai":bool(ai),"phone":bool(ph),"changed_at":at} for s,loc,ai,ph,at in rows}

    def permitted(self,scope,destination="local"):
        if scope not in SCOPES or destination not in ("local","ai","phone"):return False
        with self.lock,self._db() as db:
            row=db.execute("SELECT local_read,send_to_ai,send_to_phone FROM permissions WHERE scope=?",(scope,)).fetchone()
        if not row or not row[0]:return False
        return bool({"local":row[0],"ai":row[1],"phone":row[2]}[destination])

    def set_permission(self,scope,*,local,ai=False,phone=False):
        if scope not in SCOPES:raise ValueError("Unknown data permission category")
        if not local and (ai or phone):raise ValueError("AI and phone transmission require LOCAL to be enabled")
        with self.lock,self._db() as db:
            db.execute("UPDATE permissions SET local_read=?,send_to_ai=?,send_to_phone=?,changed_at=? WHERE scope=?",
                       (int(local),int(ai),int(phone),utc_now(),scope))
        self.audit("permission","changed",f"{scope}: local={bool(local)}, ai={bool(ai)}, phone={bool(phone)}")

    def audit(self,action,outcome,summary):
        with self.lock,self._db() as db:
            db.execute("INSERT INTO action_audit(at_utc,action,outcome,summary) VALUES(?,?,?,?)",
                       (utc_now(),_clean(action,80),_clean(outcome,35),_clean(summary,280)))
            db.execute("DELETE FROM action_audit WHERE id NOT IN (SELECT id FROM action_audit ORDER BY id DESC LIMIT 2000)")

    def recent_audit(self,limit=30):
        with self.lock,self._db() as db:
            rows=db.execute("SELECT at_utc,action,outcome,summary FROM action_audit ORDER BY id DESC LIMIT ?",(max(1,min(limit,100)),)).fetchall()
        return [{"at":r[0],"action":r[1],"outcome":r[2],"summary":r[3]} for r in rows]

    @staticmethod
    def _id_for(kind,scope,source,ref):
        return hashlib.sha256(f"{kind}|{scope}|{source}|{ref}".encode()).hexdigest()[:32]

    def add_entity(self,kind,title,details="",scope="projects",source="owner_input",source_ref=None,
                   observed_at=None,confidence=1.0):
        if kind not in VALID_KINDS or scope not in SCOPES or source not in VALID_SOURCE:
            raise ValueError("Invalid graph entity kind, scope or source")
        if not self.permitted(scope,"local"):raise PermissionError("Scope not enabled")
        title=_clean(title,140);details=_clean(details,1300)
        if len(title)<3:raise ValueError("Entity title too short")
        ref=_clean(source_ref if source_ref is not None else title.lower(),220)
        ident=self._id_for(kind,scope,source,ref)
        at=str(observed_at or utc_now())[:40]
        now=utc_now()
        with self.lock,self._db() as db:
            db.execute("""INSERT INTO entities(id,kind,title,details,scope,source,source_ref,observed_at,confidence,created_at,updated_at)
              VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
              title=excluded.title,details=excluded.details,observed_at=excluded.observed_at,
              confidence=excluded.confidence,updated_at=excluded.updated_at""",
              (ident,kind,title,details,scope,source,ref,at,max(0.0,min(1.0,float(confidence))),now,now))
        return ident

    def link(self,source_id,target_id,relationship="related_to"):
        if source_id==target_id:raise ValueError("Cannot link an entity to itself")
        with self.lock,self._db() as db:
            rows=db.execute("SELECT id,scope FROM entities WHERE id IN (?,?)",(source_id,target_id)).fetchall()
            if len(rows)!=2:raise ValueError("Two existing graph entities required")
            if not all(self.permitted(s,"local") for _,s in rows):raise PermissionError("Graph scope revoked")
            db.execute("INSERT OR IGNORE INTO links(source_id,target_id,relationship) VALUES(?,?,?)",
                       (source_id,target_id,_clean(relationship,45)))

    def graph_snapshot(self,*,destination="local",limit=80):
        allowed={scope for scope in SCOPES if self.permitted(scope,destination)}
        if not allowed:return {"nodes":[],"edges":[]}
        with self.lock,self._db() as db:
            rows=db.execute("SELECT id,kind,title,details,scope,source,observed_at,confidence FROM entities ORDER BY updated_at DESC LIMIT 900").fetchall()
            nodes=[{"id":r[0],"kind":r[1],"title":r[2],"details":r[3][:230],"scope":r[4],
                    "source":r[5],"observed_at":r[6],"confidence":r[7]}
                   for r in rows if r[4] in allowed][:max(1,min(limit,150))]
            ids={r["id"] for r in nodes}
            links=db.execute("SELECT source_id,target_id,relationship FROM links LIMIT 2000").fetchall()
        edges=[{"from":a,"to":b,"kind":rel} for a,b,rel in links if a in ids and b in ids]
        return {"nodes":nodes,"edges":edges,"note":"Source-attributed links, not inferred causal claims"}

    def search(self,text,*,destination="local",limit=12):
        tokens=re.findall(r"[a-z0-9_]{3,}",str(text).lower())[:6]
        if not tokens:return []
        snapshot=self.graph_snapshot(destination=destination,limit=150)
        scored=[]
        for node in snapshot["nodes"]:
            phrase=(node["title"]+" "+node["details"]).lower()
            hits=sum((3 if t in node["title"].lower() else 1) if t in phrase else 0 for t in tokens)
            if hits:scored.append((hits,node))
        scored.sort(key=lambda o:o[0],reverse=True)
        return [node for _,node in scored[:max(0,min(limit,30))]]

    def related(self,entity_id,*,destination="local",limit=12):
        graph=self.graph_snapshot(destination=destination,limit=150)
        nodes={n["id"]:n for n in graph["nodes"]}
        if entity_id not in nodes:return []
        related=[]
        for edge in graph["edges"]:
            other=edge["to"] if edge["from"]==entity_id else edge["from"] if edge["to"]==entity_id else None
            if other in nodes:
                related.append({"id":other,"kind":nodes[other]["kind"],"title":nodes[other]["title"],
                               "scope":nodes[other]["scope"],"source":nodes[other]["source"],
                               "relationship":edge["kind"]})
        return related[:max(0,min(limit,30))]

    def add_event(self,category,title,summary="",*,scope="operations",source="companion_activity",
                  observed_at=None,dedupe_key=None):
        if scope not in SCOPES or source not in VALID_SOURCE:raise ValueError("Unknown event source or scope")
        if not self.permitted(scope,"local"):return None
        title=_clean(title,145);summary=_clean(summary,360)
        if not title:return None
        at=str(observed_at or utc_now())[:40]
        dedupe_key=_clean(dedupe_key or hashlib.sha256((source+title+at).encode()).hexdigest(),140)
        with self.lock,self._db() as db:
            cur=db.execute("INSERT OR IGNORE INTO events(dedupe_key,category,title,summary,scope,source,observed_at,recorded_at) VALUES(?,?,?,?,?,?,?,?)",
                           (dedupe_key,_clean(category,45),title,summary,scope,source,at,utc_now()))
            db.execute("DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT 6000)")
        return bool(cur.rowcount)

    def timeline(self,*,destination="local",limit=30,days=30,scope=None):
        allowed={s for s in SCOPES if self.permitted(s,destination) and (scope is None or s==scope)}
        if not allowed:return []
        since=(datetime.now(timezone.utc)-timedelta(days=max(1,min(int(days),3650)))).isoformat()
        with self.lock,self._db() as db:
            rows=db.execute("SELECT observed_at,category,title,summary,scope,source FROM events WHERE observed_at>=? ORDER BY observed_at DESC LIMIT 1200",(since,)).fetchall()
        return [{"at":at,"category":c,"title":t,"summary":desc,"scope":s,"source":src}
                for at,c,t,desc,s,src in rows if s in allowed][:max(1,min(limit,250))]

    def add_plan(self,title,rationale="",*,scope="projects",source="owner_input",priority=3,due_day=None):
        if scope not in SCOPES or source not in VALID_SOURCE or not self.permitted(scope,"local"):
            raise PermissionError("Plan category not authorized")
        due=date.fromisoformat(str(due_day)[:10]).isoformat() if due_day else None
        now=utc_now()
        with self.lock,self._db() as db:
            cur=db.execute("INSERT INTO plan(title,rationale,source,scope,priority,status,due_day,created_at,updated_at) VALUES(?,?,?,?,?,'todo',?,?,?)",
                (_clean(title,170),_clean(rationale,750),source,scope,max(1,min(int(priority),5)),due,now,now))
        return cur.lastrowid

    def update_plan(self,ident,status):
        if status not in VALID_STATUS:raise ValueError("Unknown task status")
        with self.lock,self._db() as db:
            row=db.execute("SELECT scope FROM plan WHERE id=?",(int(ident),)).fetchone()
            if not row or not self.permitted(row[0],"local"):return False
            cur=db.execute("UPDATE plan SET status=?,updated_at=? WHERE id=?",(status,utc_now(),int(ident)))
        return bool(cur.rowcount)

    def list_plan(self,*,destination="local",limit=30,include_done=False):
        with self.lock,self._db() as db:
            rows=db.execute("SELECT id,title,rationale,source,scope,priority,status,due_day,created_at FROM plan ORDER BY priority ASC,created_at DESC LIMIT 400").fetchall()
        return [{"id":ident,"title":title,"rationale":rationale,"source":src,"scope":scope,
                 "priority":priority,"status":status,"due_day":due,"created_at":at}
                for ident,title,rationale,src,scope,priority,status,due,at in rows
                if self.permitted(scope,destination) and (include_done or status not in ("done","cancelled"))][:max(1,min(limit,100))]

    def remember_insight(self,text,provenance,sample_size,*,scope="operations"):
        if not self.permitted(scope,"local"):return None
        txt=_clean(text,550);prov=_clean(provenance,500)
        fp=hashlib.sha256((txt+"|"+prov).encode()).hexdigest()
        with self.lock,self._db() as db:
            db.execute("INSERT OR IGNORE INTO insights(fingerprint,text,provenance,scope,sample_size,generated_at) VALUES(?,?,?,?,?,?)",
                       (fp,txt,prov,scope,int(sample_size),utc_now()))
        return fp

    def list_insights(self,*,destination="local",limit=12):
        with self.lock,self._db() as db:
            rows=db.execute("SELECT text,provenance,scope,sample_size,generated_at FROM insights ORDER BY id DESC LIMIT 150").fetchall()
        return [{"insight":txt,"provenance":prov,"scope":scope,"sample_size":n,"generated_at":at}
                for txt,prov,scope,n,at in rows if self.permitted(scope,destination)][:max(1,min(limit,30))]

    def trends(self,*,destination="local",days=30):
        events=self.timeline(destination=destination,limit=250,days=days)
        per_cat=Counter(e["category"] for e in events)
        per_day=Counter(e["at"][:10] for e in events)
        return {"window_days":days,"observed_events":len(events),
                "earliest_sample":min((e["at"] for e in events),default=None),
                "days_with_records":len(per_day),"by_category":dict(per_cat),
                "samples_per_day":dict(sorted(per_day.items())),
                "evidence_quality":"insufficient" if len(events)<6 or len(per_day)<3 else "descriptive",
                "caveat":"Only explicitly enabled and observed Companion events. Missing records are not zero activity."}

    def erase_scope(self,scope):
        if scope not in SCOPES:raise ValueError("Unknown scope")
        with self.lock,self._db() as db:
            db.execute("DELETE FROM links WHERE source_id IN (SELECT id FROM entities WHERE scope=?) OR target_id IN (SELECT id FROM entities WHERE scope=?)",(scope,scope))
            for table in ("entities","events","plan","insights"):
                db.execute(f"DELETE FROM {table} WHERE scope=?",(scope,))
        self.audit("erase","done",f"Erased {scope} knowledge entities, events, plans and insights")

    def export_scope(self,scope,destination="local"):
        if scope not in SCOPES or not self.permitted(scope,destination):raise PermissionError("Scope not authorized")
        with self.lock,self._db() as db:
            nodes=db.execute("SELECT id,kind,title,details,source,observed_at,confidence FROM entities WHERE scope=?",(scope,)).fetchall()
            events=db.execute("SELECT category,title,summary,source,observed_at FROM events WHERE scope=?",(scope,)).fetchall()
        return {"scope":scope,
                "entities":[{"id":r[0],"kind":r[1],"title":r[2],"details":r[3],"source":r[4],"at":r[5],"confidence":r[6]} for r in nodes],
                "events":[{"category":r[0],"title":r[1],"summary":r[2],"source":r[3],"at":r[4]} for r in events]}
