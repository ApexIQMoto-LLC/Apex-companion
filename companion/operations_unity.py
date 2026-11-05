"""Bounded, allowlisted Git inspections and Unity EditMode test runs.

No arbitrary terminal, PowerShell, builds, network deployments, package
installation, or model-generated commands. A Unity executable must be chosen
explicitly by the owner; passing a path to arbitrary EXEs is forbidden.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from .dev_assistant import WorkspaceGuard, digest


def project_fingerprint(root):
    return hashlib.sha256(str(Path(root).expanduser().resolve()).encode()).hexdigest()[:20]


def safe_unity_executable(path):
    exe=Path(path).expanduser().resolve(strict=True)
    if not exe.is_file() or exe.name.lower()!="unity.exe":
        raise ValueError("Select Unity.exe from your installed Unity Editor folder")
    # Prevent accidental execution of a renamed arbitrary EXE from Downloads,
    # project Assets, or a user-writeable temporary directory.
    norm=[part.lower() for part in exe.parts]
    if "editor" not in norm or "unity" not in norm and "hub" not in norm:
        raise ValueError("Unity.exe must be inside Unity/Editor or Unity Hub/Editor")
    if len(norm)>=2 and norm[-2]!="editor":
        raise ValueError("Unity.exe must be located directly inside an Editor folder")
    return exe


def approved_unity_root(path):
    root=WorkspaceGuard(path).root
    if not (root/"Assets").is_dir() or not (root/"ProjectSettings"/"ProjectVersion.txt").is_file():
        raise ValueError("This is not a verified Unity project root")
    if (root/"Assets").is_symlink() or (root/"ProjectSettings").is_symlink():
        raise PermissionError("Symlinked Unity roots are unsupported")
    return root


def git_health(approved_root, *, runner=None):
    root=Path(approved_root).expanduser().resolve(strict=True)
    if not root.is_dir():raise ValueError("Approved project no longer exists")
    git=shutil.which("git")
    if not git:return {"state":"unavailable", "reason":"Git not installed or not on PATH"}
    run=runner or subprocess.run
    def call(args):
        p=run([git]+args,cwd=str(root),capture_output=True,text=True,timeout=12,check=False)
        return p.returncode,(p.stdout or "")[:2500]
    try:
        code,repo=call(["rev-parse","--show-toplevel"])
        if code:return {"state":"not_a_repository", "reason":"Project is not in a Git worktree"}
        repo=Path(repo.strip()).resolve(strict=True)
        if not root.is_relative_to(repo):raise PermissionError("Git root outside authorized folder")
        code,head=call(["rev-parse","--verify","HEAD"])
        if code or not re.fullmatch(r"[a-f0-9]{40,64}",head.strip()):
            return {"state":"unborn", "reason":"Repository has no initial commit"}
        code,status=call(["status","--porcelain","--untracked-files=no","--","."])
        if code:return {"state":"unavailable","reason":"Cannot read Git status"}
        code,branch=call(["branch","--show-current"])
        lines=[x for x in status.splitlines() if x.strip()]
        return {"state":"ok", "head":head.strip()[:12],"branch":branch.strip()[:70] if code==0 else "",
                "tracked_changes":len(lines),"worktree_clean":len(lines)==0,
                "note":"Git status is read-only. No branch, commit, stash, reset, or push was performed."}
    except (subprocess.TimeoutExpired,OSError,ValueError,PermissionError):
        return {"state":"unavailable","reason":"Git inspection did not complete safely"}


def parse_nunit(xmlpath):
    path=Path(xmlpath)
    if not path.is_file() or path.stat().st_size>10_000_000:
        return {"verified":False,"reason":"Unity did not produce a bounded NUnit result file"}
    try:
        tree=ET.parse(str(path))
        root=tree.getroot()
        if root.tag not in {"test-run","test-results"}:
            return {"verified":False,"reason":"Unexpected Unity test results format"}
        cases=root.findall(".//test-case")
        total=len(cases)
        passed=sum(c.attrib.get("result","").lower() in {"passed","success"} for c in cases)
        failures=sum(c.attrib.get("result","").lower() in {"failed","failure","error"} for c in cases)
        skipped=total-passed-failures
        success=total>0 and failures==0 and passed>0 and all(c.attrib.get("result","").lower() in {"passed","success","skipped","ignored","inconclusive"} for c in cases)
        return {"verified":success, "total":total,"passed":passed,"failed":failures,"skipped":skipped,
                "reason":"NUnit test report parsed" if success else "Tests failed, were inconclusive, or no tests ran"}
    except (ET.ParseError,OSError,ValueError):
        return {"verified":False,"reason":"Cannot parse Unity test results"}


class UnityEditModeRunner:
    def __init__(self, output_dir):
        self.output_dir=Path(output_dir)
        self.output_dir.mkdir(parents=True,exist_ok=True)

    def prepare(self,project_root,unity_executable):
        root=approved_unity_root(project_root)
        exe=safe_unity_executable(unity_executable)
        # Unity does not safely support two Editor processes on the same
        # project; a possibly stale lock must be resolved by the owner.
        if (root/"Temp"/"UnityLockfile").exists():
            raise RuntimeError("Unity project is open or locked; close the Editor and retry")
        return root,exe

    @staticmethod
    def command(executable,project_root,result_path,log_path):
        return [str(executable),"-batchmode","-nographics","-projectPath",str(project_root),
                "-runTests","-testPlatform","EditMode","-testResults",str(result_path),
                "-logFile",str(log_path)]

    def run(self,project_root,unity_executable,*,timeout_seconds=420,executor=None):
        root,exe=self.prepare(project_root,unity_executable)
        seconds=max(60,min(int(timeout_seconds),600))
        job=self.output_dir / (datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_")+os.urandom(4).hex())
        job.mkdir(parents=True,exist_ok=False)
        result=job/"nunit.xml"
        log=job/"editor.log"
        cmd=self.command(exe,root,result,log)
        code=-1
        try:
            if executor is not None:
                # Dependency injection for controlled tests; production never
                # accepts a transport/command from Telegram or an AI tool.
                code=int(executor(cmd,seconds))
            else:
                child=subprocess.Popen(cmd,cwd=str(root),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                                       shell=False,creationflags=getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0))
                try:
                    code=child.wait(timeout=seconds)
                except subprocess.TimeoutExpired:
                    if sys.platform=="win32":
                        # Fixed Windows built-in kill command, numeric PID only.
                        taskkill=Path(os.environ.get("SystemRoot",r"C:\Windows"))/"System32"/"taskkill.exe"
                        if taskkill.is_file():
                            subprocess.run([str(taskkill),"/PID",str(int(child.pid)),"/T","/F"],
                                           timeout=12,check=False,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                        else:
                            child.kill()
                    else:
                        child.kill()
                    child.wait(timeout=12)
                    return {"state":"failed","reason":"Unity test run timed out and was stopped",
                            "tests_verified":False,"exit_code":None,"results_dir":str(job)}
        except (OSError,ValueError,subprocess.SubprocessError):
            return {"state":"failed","reason":"Unable to launch approved Unity editor", "tests_verified":False}
        report=parse_nunit(result)
        ok=(code==0 and report.get("verified") is True)
        return {"state":"passed" if ok else "failed","exit_code":code,"tests_verified":ok,
                "total":report.get("total",0),"passed":report.get("passed",0),
                "failed":report.get("failed",0),"skipped":report.get("skipped",0),
                "reason":report.get("reason"),"results_dir":str(job),
                "note":"Verified NUnit Edit Mode results only, not gameplay behavior or a Steam release."}


class VerifiedPatchTrial:
    """Owner-approved, single-file patch; restores backup after failing tests.

    This does *not* run on model suggestions unattended. Future verified
    auto-fix rules may use the same transaction after independent validation.
    """
    def __init__(self,runner,backups):
        self.runner=runner
        self.backups=Path(backups)

    def apply_and_test(self,guard,proposal,unity_executable,*,approved=False,timeout_seconds=420):
        if not approved:raise PermissionError("Single-file patch requires direct approval")
        if proposal.root!=guard.root:raise PermissionError("Project authorization changed")
        self.runner.prepare(guard.root,unity_executable)  # fail before modifying file
        backup=guard.apply(proposal,self.backups,approved=True)
        current=guard.target(proposal.relative_path)
        after_hash=digest(current.read_bytes())
        try:
            report=self.runner.run(guard.root,unity_executable,timeout_seconds=timeout_seconds)
        except Exception:
            report={"state":"failed","reason":"Verification could not complete","tests_verified":False}
        if report.get("tests_verified") is True:
            return {"state":"verified","file":proposal.relative_path,"report":report,"backup_name":backup.name}
        # Only restore if no other actor edited file in the meantime.
        if digest(current.read_bytes())!=after_hash:
            return {"state":"conflict","file":proposal.relative_path,"report":report,
                    "reason":"Another actor changed the file. Refused to overwrite newer work."}
        original=backup.read_bytes()
        if digest(original)!=proposal.before_sha256:
            return {"state":"conflict","file":proposal.relative_path,"report":report,
                    "reason":"Backup checksum mismatch; manual recovery needed"}
        fd,tmp=tempfile.mkstemp(prefix=".apex-verified-restore-",suffix=current.suffix,dir=str(current.parent))
        try:
            with os.fdopen(fd,"wb") as out:
                out.write(original);out.flush();os.fsync(out.fileno())
            if digest(current.read_bytes())!=after_hash:
                return {"state":"conflict","file":proposal.relative_path,"report":report,
                        "reason":"File changed during rollback; manual recovery needed"}
            os.replace(tmp,current)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
        return {"state":"rolled_back","file":proposal.relative_path,"report":report,
                "reason":"Unity tests did not verify the patch; original restored."}
