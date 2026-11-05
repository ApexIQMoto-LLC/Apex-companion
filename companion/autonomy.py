"""Narrow autonomy for deterministic, reversible Unity C# hygiene fixes.

This is deliberately NOT a generic AI coding agent. It never runs a shell,
build, deploy, database migration, network mutation, purchase or AI request.
The only unattended write is a compiler-identified duplicate C# `using`
directive (CS0105), with strict path/diff limits, backup and verification.
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

from .dev_assistant import WorkspaceGuard, digest

DUPLICATE_USING=re.compile(r"^\s*using\s+[A-Za-z_][A-Za-z_0-9.]*(?:\s*=\s*[A-Za-z_][A-Za-z_0-9.]*)?;\s*$")
CS0105=re.compile(r"\b(?:warning|error)\s+CS0105\b",re.I)
PROHIBITED_PARTS={"Editor","Plugins","Packages","StreamingAssets","Resources","Tests","Test","ThirdParty"}


class SmallFixAutonomy:
    def __init__(self, audit_dbpath, backup_root):
        self.db=str(audit_dbpath)
        self.backup_root=Path(backup_root)
        Path(self.db).parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(self.db) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS autonomous_fixes(
              id INTEGER PRIMARY KEY AUTOINCREMENT, at_utc TEXT NOT NULL,
              project_hash TEXT NOT NULL, path TEXT NOT NULL,
              rule TEXT NOT NULL, before_hash TEXT NOT NULL,
              after_hash TEXT NOT NULL, backup_name TEXT NOT NULL,
              status TEXT NOT NULL)""")

    def today_fixes(self):
        with sqlite3.connect(self.db) as db:
            return int(db.execute("SELECT count(*) FROM autonomous_fixes WHERE at_utc LIKE ? AND status='static_verified'",
                                  (date.today().isoformat()+"%",)).fetchone()[0])

    @staticmethod
    def _prepare(guard, relative, line_number):
        path,before,raw=guard.read(relative)
        rel=Path(relative)
        if (rel.suffix.lower()!=".cs" or not rel.parts or rel.parts[0].lower()!="assets" or
            any(part.lower() in {p.lower() for p in PROHIBITED_PARTS} for part in rel.parts)):
            raise PermissionError("Only first-party C# files under Assets are eligible")
        lines=before.splitlines(keepends=True)
        idx=int(line_number)-1
        if idx<0 or idx>=len(lines) or idx>110:
            raise ValueError("Warning line outside safe leading imports region")
        line=lines[idx]
        if not DUPLICATE_USING.fullmatch(line.rstrip("\r\n")):
            raise ValueError("Warning line is not a simple using declaration")
        if any(ln.lstrip().startswith(("#if","#elif","#else","#endif")) for ln in lines[:idx+1]):
            raise ValueError("Conditional compilation directives present")
        norm=line.strip()
        if sum(ln.strip()==norm for ln in lines[:idx])!=1:
            raise ValueError("Not an exact earlier duplicate")
        # The C# compiler may cite the duplicated directive in either position.
        # Only remove the *second* one, and only on the exact reported line.
        start=max(0,idx-2)
        stop=min(len(lines),idx+3)
        snippet="".join(lines[start:stop])
        patched="".join(lines[start:idx]+lines[idx+1:stop])
        if before.count(snippet)!=1:
            raise ValueError("Patch context is ambiguous")
        proposal=guard.propose(relative,snippet,patched,"CS0105 duplicate top-level using directive")
        removed=[s for s in proposal.diff.splitlines() if s.startswith("-") and not s.startswith("---")]
        added=[s for s in proposal.diff.splitlines() if s.startswith("+") and not s.startswith("+++")]
        if len(removed)!=1 or added or removed[0].lstrip("-").strip()!=norm:
            raise ValueError("Patch is not a single deterministic deletion")
        return proposal

    def handle_unity_warnings(self, guard: WorkspaceGuard, issues: list, *, enabled: bool,
                              authorized_project: str | Path | None, permission_check=lambda: True,
                              max_per_day=2):
        if not enabled:
            return [{"status":"disabled","reason":"Autonomous fixes disabled"}]
        if not authorized_project or guard.root!=Path(authorized_project).expanduser().resolve():
            return [{"status":"blocked","reason":"Workspace not authorized"}]
        if not permission_check():return [{"status":"blocked","reason":"Authorization changed"}]
        results=[]
        for issue in (issues or [])[:50]:
            if self.today_fixes()>=max(0,min(int(max_per_day),3)):
                break
            message=str(issue.get("message",""))
            if not CS0105.search(message):continue
            rel=str(issue.get("file") or "").replace("\\","/")
            line=issue.get("line")
            if not rel or not isinstance(line,int):continue
            try:
                if not permission_check():break
                proposal=self._prepare(guard,rel,line)
                if not permission_check():break
                backup=guard.apply(proposal,self.backup_root,approved=True)
                path=guard.target(rel)
                after=path.read_bytes()
                # Static verification: previous exact warning line gone, and
                # the originally duplicate directive occurs once now.
                if after!=proposal.replacement.encode("utf-8"):
                    # Don't overwrite a file if another actor changed it.
                    results.append({"status":"manual_review","rule":"CS0105","file":rel,
                                    "reason":"Post-edit file changed; backup retained"})
                    continue
                with sqlite3.connect(self.db) as db:
                    db.execute("""INSERT INTO autonomous_fixes(at_utc,project_hash,path,rule,before_hash,after_hash,backup_name,status)
                                  VALUES(?,?,?,?,?,?,?,?)""",
                               (datetime.now(timezone.utc).isoformat(),
                                hashlib.sha256(str(guard.root).encode()).hexdigest()[:16],
                                rel,"CS0105",proposal.before_sha256,digest(after),backup.name,"static_verified"))
                results.append({"status":"static_verified","rule":"CS0105","file":rel,
                                "backup":backup.name,
                                "warning":"Only the duplicate import was removed; Unity compilation was not run."})
            except (ValueError,PermissionError,OSError,RuntimeError):
                # Uncertain patches are skipped, not guessed at.
                results.append({"status":"skipped","rule":"CS0105","file":rel,
                                "reason":"Static safety requirements not met"})
        return results

    def rollback_last(self, guard: WorkspaceGuard, *, approved: bool=False):
        """Owner-approved rollback of last eligible fix, with conflict checks.

        Never rolls back an edit if someone else has changed that file since
        the automated fix. Restores exactly the recorded pre-fix bytes.
        """
        if not approved:
            raise PermissionError("Owner approval required to roll back a code edit")
        project_hash=hashlib.sha256(str(guard.root).encode()).hexdigest()[:16]
        with sqlite3.connect(self.db) as db:
            row=db.execute("""SELECT id,path,before_hash,after_hash,backup_name
                           FROM autonomous_fixes WHERE project_hash=? AND status='static_verified'
                           ORDER BY id DESC LIMIT 1""",(project_hash,)).fetchone()
        if not row:
            raise ValueError("No eligible auto-fix backup for this approved Unity project")
        ident,rel,before_hash,after_hash,backup_name=row
        target=guard.target(rel)  # enforces workspace, symlink, type and size guards
        backup=(self.backup_root / backup_name)
        if (not backup.exists() or backup.is_symlink() or backup.parent.resolve()!=self.backup_root.resolve()):
            raise ValueError("Original backup file is missing or unsafe")
        original=backup.read_bytes()
        if digest(original)!=before_hash:
            raise RuntimeError("Original backup checksum changed; refusing rollback")
        if digest(target.read_bytes())!=after_hash:
            raise RuntimeError("Current source changed since the auto-fix; refusing rollback")
        fd,tmp=tempfile.mkstemp(prefix='.apex-rollback-',suffix=target.suffix,dir=str(target.parent))
        try:
            with os.fdopen(fd,'wb') as writer:
                writer.write(original);writer.flush();os.fsync(writer.fileno())
            os.chmod(tmp,target.stat().st_mode)
            if digest(target.read_bytes())!=after_hash:
                raise RuntimeError("Source changed during rollback; refusing overwrite")
            os.replace(tmp,target)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
        with sqlite3.connect(self.db) as db:
            db.execute("UPDATE autonomous_fixes SET status='rolled_back' WHERE id=? AND status='static_verified'",(ident,))
        return {"status":"rolled_back","file":rel,"rule":"CS0105","restored_original":True,
                "warning":"Source restored; Unity compilation has not been run."}

    def recent(self,limit=20):
        with sqlite3.connect(self.db) as db:
            rows=db.execute("SELECT at_utc,path,rule,backup_name,status FROM autonomous_fixes ORDER BY id DESC LIMIT ?",
                            (max(1,min(limit,100)),)).fetchall()
        return [{"at_utc":r[0],"file":r[1],"rule":r[2],"backup":r[3],"status":r[4]} for r in rows]
