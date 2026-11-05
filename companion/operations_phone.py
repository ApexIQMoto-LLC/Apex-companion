"""Owner-only, restricted Telegram command channel for APEX operations.

Allowed: /status /queue /scan /git /pause /resume /help.
No free-form prompts, edits, scripts, deployments, purchases, approvals, or
administrative actions are accepted from phone commands. Requires explicit
PHONE permission, phone briefing opt-in, and remote_commands opt-in.
"""
from __future__ import annotations

import json
import re
from .sqlite_utils import open_sqlite
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .operations_queue import OperationsQueue
from .phone_brief import PhoneBriefing

COMMANDS={
    "/status":"Read local APEX operations status",
    "/queue":"Show recent queued and completed operations",
    "/scan":"Queue an approved Unity diagnostics scan",
    "/git":"Queue a read-only Git health inspection",
    "/pause":"Pause execution of queued operations",
    "/resume":"Resume execution of queued operations",
    "/help":"List supported phone commands",
}


class RemoteOperations:
    def __init__(self,dbpath, queue:OperationsQueue, phone:PhoneBriefing):
        self.db=str(dbpath)
        Path(self.db).parent.mkdir(parents=True,exist_ok=True)
        self.queue=queue
        self.phone=phone
        with open_sqlite(self.db) as db:
            db.execute("CREATE TABLE IF NOT EXISTS remote_state(key TEXT PRIMARY KEY, value TEXT NOT NULL)")

    def _offset(self):
        with open_sqlite(self.db) as db:
            row=db.execute("SELECT value FROM remote_state WHERE key='offset'").fetchone()
        return int(row[0]) if row else 0

    def _save_offset(self,offset):
        with open_sqlite(self.db) as db:
            db.execute("INSERT INTO remote_state(key,value) VALUES('offset',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(str(int(offset)),))

    @staticmethod
    def _command(message):
        if not isinstance(message,dict) or not isinstance(message.get("text"),str):
            return None
        # Only exact slash commands. No arbitrary user-supplied code or text.
        text=message["text"].strip()
        if not re.fullmatch(r"/[a-z]+(?:@ApexIQ_[A-Za-z0-9_]+)?",text,re.I):
            return None
        cmd=text.split("@",1)[0].lower()
        return cmd if cmd in COMMANDS else None

    def handle_updates(self,updates,*,owner_id,approved_project=False,authorized=True,
                       status_line="APEX is running; consult desktop for details"):
        if not authorized:
            return [{"state":"disabled"}]
        out=[]
        offset=self._offset()
        for update in sorted(updates if isinstance(updates,list) else [],key=lambda x:x.get("update_id",-1) if isinstance(x,dict) else -1)[:40]:
            if not isinstance(update,dict):continue
            uid=update.get("update_id")
            if not isinstance(uid,int) or uid<offset:continue
            offset=uid+1
            self._save_offset(offset)  # avoid replay even if a later action fails
            msg=update.get("message")
            if not isinstance(msg,dict):continue
            chat=msg.get("chat",{})
            sender=msg.get("from",{})
            if (not isinstance(chat,dict) or chat.get("type")!="private" or
                str(chat.get("id"))!=str(owner_id) or not isinstance(sender,dict) or
                str(sender.get("id"))!=str(owner_id)):
                continue
            if msg.get("forward_origin") or msg.get("forward_from"):
                continue
            command=self._command(msg)
            if command is None:continue
            if command=="/pause":
                self.queue.set_paused(True);answer="Operations paused. Active Unity test run is not interrupted."
            elif command=="/resume":
                self.queue.set_paused(False);answer="Operations resumed; pending tasks use the same local permission rules."
            elif command=="/queue":
                records=self.queue.recent(5)
                answer="Recent operations:\n"+("\n".join(x['kind']+" / "+x['status'] for x in records) if records else "No tasks")
            elif command=="/status":
                counts=self.queue.counts()
                answer=("APEX operations: "+("paused" if self.queue.paused() else "enabled")+
                        ". Pending "+str(counts.get('queued',0))+"; completed "+str(counts.get('completed',0))+
                        ". "+str(status_line)[:150])
            elif command=="/help":
                answer="APEX private commands: "+" ".join(COMMANDS)
            elif command in ("/scan","/git"):
                if not approved_project:
                    answer="No Unity project approved on this PC. Choose one in APEX first."
                else:
                    kind="unity_diagnostics" if command=="/scan" else "git_health"
                    try:
                        task_id=self.queue.enqueue(kind,origin="phone",dedupe_key="phone:"+str(uid))
                        answer="Queued "+kind.replace("_"," ")+". Task "+task_id+"."
                    except (RuntimeError,ValueError,PermissionError):
                        answer="Could not queue task; check APEX operations panel."
            else:continue
            out.append({"update_id":uid,"command":command,"reply":answer})
        return out

    def poll(self,*,authorized,approved_project, status_line="APEX running", transport=None):
        if not authorized:return [{"state":"disabled"}]
        token,chat=self.phone._credentials()
        if not self.phone.configured():return [{"state":"not_configured"}]
        # Telegram bot API getUpdates requires no webhook configured.
        # 0 timeout is short polling: bounded, no background thread held open.
        params={"offset":self._offset(),"limit":30,"timeout":0,"allowed_updates":["message"]}
        endpoint="https://api.telegram.org/bot"+quote(token,safe=":")+"/getUpdates"
        req=Request(endpoint,data=json.dumps(params).encode("utf-8"),method="POST",
                    headers={"Content-Type":"application/json"})
        try:
            opener=transport or urlopen
            with opener(req,timeout=12) as response:
                obj=json.loads(response.read(120_000).decode("utf-8"))
            if obj.get("ok") is not True or not isinstance(obj.get("result"),list):
                return [{"state":"api_unavailable"}]
            return self.handle_updates(obj["result"],owner_id=chat,approved_project=approved_project,
                                       authorized=authorized,status_line=status_line)
        except (HTTPError,URLError,TimeoutError,OSError,ValueError,TypeError):
            return [{"state":"unavailable"}]
