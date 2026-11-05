"""Local, free, actionable alert rules with restart-safe deduplication."""
from __future__ import annotations
import json
from .sqlite_utils import open_sqlite
import threading
from datetime import datetime, timezone
from pathlib import Path


def cloud_alerts(snapshot: dict|None) -> list[dict]:
    if not isinstance(snapshot,dict):return []
    alerts=[]
    freshness=str(snapshot.get("device_freshness", "unknown"))
    if freshness.startswith("stale"):
        heart=snapshot.get("tables",{}).get("Device heartbeats",{}).get("latest",{})
        seen=str(heart.get("last_seen_at","unknown"))[:45] if isinstance(heart,dict) else "unknown"
        alerts.append({"key":"device-stale:"+seen, "severity":"warning", "title":"Device heartbeat is stale",
                       "details":"Last owner-visible heartbeat at "+seen+" UTC. Check power, network and uploader."})
    return alerts


def steam_alerts(previous:dict|None,current:dict|None) -> list[dict]:
    if not isinstance(current,dict) or current.get("status")!="ok":return []
    if not isinstance(previous,dict) or previous.get("status")!="ok":return []
    if str(previous.get("latest_date"))==str(current.get("latest_date")):return []
    latest=current.get("latest",{})
    adds=int(latest.get("wishlist_adds",0)) if isinstance(latest,dict) else 0
    return [{"key":"steam-new-report:"+str(current.get("latest_date")),"severity":"info",
             "title":"New Replay Studio wishlist report",
             "details":f"{adds} additions on {current.get('latest_date')}. Daily additions, not total wishlists."}]


def beta_alerts(previous:dict|None,current:dict|None) -> list[dict]:
    if not previous or not current:return []
    prev=previous.get("tables",{}).get("Beta applications",{})
    curr=current.get("tables",{}).get("Beta applications",{})
    if prev.get("error") or curr.get("error"):return []
    p,c=prev.get("visible_count"),curr.get("visible_count")
    if not isinstance(p,int) or not isinstance(c,int) or c<=p:return []
    return [{"key":"beta-visible:"+str(c),"severity":"info","title":"New beta application records",
             "details":f"Owner-visible applications increased from {p} to {c}. Review incoming applications."}]


class AlertCenter:
    def __init__(self,path):
        self.path=str(path)
        self.lock=threading.RLock()
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        with open_sqlite(self.path) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,key TEXT UNIQUE NOT NULL,
                severity TEXT NOT NULL,title TEXT NOT NULL,details TEXT NOT NULL,
                first_seen_utc TEXT NOT NULL,acknowledged INTEGER NOT NULL DEFAULT 0)""")

    def ingest(self,alerts:list[dict]) -> list[dict]:
        novel=[]
        with self.lock,open_sqlite(self.path) as db:
            for alert in alerts:
                key=str(alert["key"])[:240]
                if not key:continue
                at=datetime.now(timezone.utc).isoformat()
                cur=db.execute("INSERT OR IGNORE INTO alerts(key,severity,title,details,first_seen_utc) VALUES (?,?,?,?,?)",
                               (key,str(alert.get("severity","info"))[:16],str(alert["title"])[:160],
                                str(alert["details"])[:650],at))
                if cur.rowcount:
                    novel.append(dict(alert))
        return novel

    def recent(self,limit=35,only_unread=False):
        with self.lock,open_sqlite(self.path) as db:
            q="SELECT id,severity,title,details,first_seen_utc,acknowledged FROM alerts "
            if only_unread:q+="WHERE acknowledged=0 "
            q+="ORDER BY id DESC LIMIT ?"
            rows=db.execute(q,(max(1,min(limit,100)),)).fetchall()
        return [{"id":r[0],"severity":r[1],"title":r[2],"details":r[3],"at_utc":r[4],"acknowledged":bool(r[5])} for r in rows]

    def acknowledge(self,ids=None):
        with self.lock,open_sqlite(self.path) as db:
            if ids is None: db.execute("UPDATE alerts SET acknowledged=1")
            else:
                for ident in ids: db.execute("UPDATE alerts SET acknowledged=1 WHERE id=?",(int(ident),))

    def delete_all(self):
        """Permanently erase the local notification history."""
        with self.lock,open_sqlite(self.path) as db:
            db.execute("DELETE FROM alerts")
