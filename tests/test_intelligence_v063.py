"""Regression + security tests for APEX 0.6.3's new intelligence layer."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from companion.memory import MemoryVault, clean
from companion.alerts import AlertCenter, cloud_alerts, steam_alerts, beta_alerts
from companion.dev_assistant import WorkspaceGuard, parse_proposal_response
from companion.live_tools import LiveToolbox, TOOL_DEFINITIONS
from companion.unity_diagnostics import scan_unity_logs
from companion.project_index import ProjectIndexer
from companion.assistant import CompanionBrain
from companion.costs import SpendLedger
from companion.settings import DEFAULTS


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.db = Path(self.t.name) / "memory.db"
        self.m = MemoryVault(self.db)

    def test_explicit_memory_persists_after_restart(self):
        ident=self.m.remember_from_message("Remember that Replay Studio uses Unity")
        self.assertIsInstance(ident,int)
        reopened=MemoryVault(self.db)
        self.assertEqual(reopened.list_memories()[0]["fact"],"Replay Studio uses Unity")

    def test_memory_requires_explicit_command(self):
        self.assertIsNone(self.m.remember_from_message("Could you explain how memory works?"))

    def test_memory_deduplicates(self):
        a=self.m.add("Use 93 octane on the ZX6R")
        b=self.m.add("use 93 octane on the zx6r")
        self.assertEqual(a,b)
        self.assertEqual(len(self.m.list_memories()),1)

    def test_search_and_individual_delete(self):
        chosen=self.m.add("Replay Studio needs Unity road elevation")
        self.m.add("Cycle Gear beta follow-up")
        found=self.m.search("Unity elevation road",include_conversation=False)
        self.assertEqual(found[0]["id"],chosen)
        self.assertTrue(self.m.delete(chosen))
        self.assertFalse(any(o["id"]==chosen for o in self.m.search("Unity",include_conversation=False)))

    def test_history_persists_and_is_erasable(self):
        self.m.log_exchange("How many beta applications?", "Three were recorded previously")
        self.assertEqual(len(MemoryVault(self.db).recent()),1)
        self.m.clear_conversation()
        self.assertEqual(MemoryVault(self.db).recent(),[])

    def test_redacts_obvious_api_key(self):
        self.assertNotIn("sk-testthisisnotrealvalue12345",clean("my key is sk-testthisisnotrealvalue12345"))
        self.assertNotIn("shhh",clean("password: shhh"))

    def test_full_erasure(self):
        self.m.add("Apex project memory fact")
        self.m.log_exchange("user", "response")
        self.m.forget_all()
        self.assertEqual(self.m.list_memories(),[])
        self.assertEqual(self.m.recent(),[])


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root=Path(self.t.name)
        (self.root/"Assets").mkdir()
        (self.root/"Assets"/"Bike.cs").write_text("class Bike { int speed = 1; }\n",encoding="utf-8")
        self.guard=WorkspaceGuard(self.root)

    def test_no_write_without_approval_and_creates_backup(self):
        proposal=self.guard.propose("Assets/Bike.cs","speed = 1", "speed = 2", "Fix speed")
        self.assertIn("-class Bike",proposal.diff)
        with self.assertRaises(PermissionError):self.guard.apply(proposal,self.root/"backups")
        backup=self.guard.apply(proposal,self.root/"backups",approved=True)
        self.assertTrue(backup.exists())
        self.assertIn("speed = 1",backup.read_text())
        self.assertIn("speed = 2",(self.root/"Assets"/"Bike.cs").read_text())

    def test_reject_stale_proposal(self):
        proposal=self.guard.propose("Assets/Bike.cs","speed = 1", "speed = 3")
        (self.root/"Assets"/"Bike.cs").write_text("class Bike { int speed = 9; }\n")
        with self.assertRaises(RuntimeError):self.guard.apply(proposal,self.root/"backups",approved=True)

    def test_no_traversal_or_secrets(self):
        for candidate in ("../outside.cs", ".env", "Assets/../../.ssh/id_rsa", "Assets/no.cs"):
            with self.subTest(candidate=candidate), self.assertRaises((ValueError,FileNotFoundError)):
                self.guard.read(candidate)

    def test_no_symlink_escape(self):
        external=self.root.parent/"external-example-v063.cs"
        external.write_text("public class Other {}")
        try:
            (self.root/"Assets"/"Link.cs").symlink_to(external)
        except (NotImplementedError,OSError):
            external.unlink(missing_ok=True)
            self.skipTest("Symlink creation restricted")
        try:
            with self.assertRaises(ValueError):self.guard.read("Assets/Link.cs")
        finally:external.unlink(missing_ok=True)

    def test_reject_ambiguous_patch(self):
        with self.assertRaises(ValueError):self.guard.propose("Assets/Bike.cs","not_found", "replacement")
        with self.assertRaises(ValueError):self.guard.propose("Assets/Bike.cs","speed = 1", "password: test-secret")

    def test_response_json_not_exec(self):
        parsed=parse_proposal_response('{"find":"old","replace":"new","explanation":"safe"}')
        self.assertEqual(parsed["replace"],"new")
        with self.assertRaises(ValueError):parse_proposal_response('execute this script')


class ScopeTests(unittest.TestCase):
    def test_code_search_scoped_to_one_approved_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            a=base/"a";b=base/"b";a.mkdir();b.mkdir()
            (a/"a.cs").write_text("public class BlueBrake{}")
            (b/"b.cs").write_text("public class RedBrake{}")
            index=ProjectIndexer(base/"index.sqlite")
            index.index(a);index.index(b)
            self.assertTrue(Path(index.search("Brake",root=a)[0]["path"]).samefile(a/"a.cs"))
            self.assertEqual(len(index.search("Brake",root=a)),1)
            toolbox=LiveToolbox(indexer=index,approved_project=a)
            matched=toolbox.run("search_approved_code",{"query":"Brake"})["matches"]
            self.assertEqual(len(matched),1)
            self.assertEqual(matched[0]["relative_path"],"a.cs")
            index.clear_root(a)
            self.assertEqual(index.search("Brake",root=a),[])

    def test_cloud_disabled_removes_private_tools(self):
        names={x["name"] for x in LiveToolbox(allow_cloud=False).schemas()}
        self.assertNotIn("get_steam_growth",names)
        self.assertNotIn("get_cloud_health",names)
        self.assertEqual(LiveToolbox(allow_cloud=False).run("get_cloud_health"),{"error":"tool_not_allowed"})

    def test_no_write_tools(self):
        self.assertTrue(all(t["name"].startswith(("get_","recall_","search_","inspect_")) for t in TOOL_DEFINITIONS))
        self.assertEqual(LiveToolbox().run("run_shell",{"cmd":"rm -rf /"}),{"error":"tool_not_allowed"})

    def test_unity_logs_extract_code_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/"Logs").mkdir()
            (root/"Logs"/"editor.log").write_text("Assets/Bike.cs(10,3): error CS1061: missing method\nNullReferenceException: Object reference\n")
            report=scan_unity_logs(root)
            self.assertEqual(report["sampled_errors"],2)
            self.assertEqual(report["issues"][-1]["file"],"Assets/Bike.cs")
            self.assertEqual(report["issues"][-1]["line"],10)


class AlertTests(unittest.TestCase):
    def test_alert_dedupes_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            db=Path(directory)/"alerts.sqlite"
            center=AlertCenter(db)
            item={"key":"stale-device-at-001","title":"Device stale","details":"No recent heartbeat"}
            self.assertEqual(len(center.ingest([item])),1)
            self.assertEqual(len(AlertCenter(db).ingest([item])),0)
            self.assertEqual(len(center.recent(only_unread=True)),1)
            center.acknowledge()
            self.assertEqual(center.recent(only_unread=True),[])

    def test_stale_not_healthy(self):
        stale={"device_freshness":"stale >150s","tables":{"Device heartbeats":{"latest":{"last_seen_at":"2026-11-01T09:00:00+00:00"}}}}
        self.assertEqual(len(cloud_alerts(stale)),1)
        self.assertEqual(cloud_alerts({"device_freshness":"live <=60s"}),[])

    def test_steam_and_beta_change_rules(self):
        a={"status":"ok","latest_date":"2026-11-02","latest":{"wishlist_adds":2}}
        b={"status":"ok","latest_date":"2026-11-03","latest":{"wishlist_adds":5}}
        self.assertEqual(len(steam_alerts(a,b)),1)
        self.assertEqual(steam_alerts(b,b),[])
        self.assertEqual(len(beta_alerts({"tables":{"Beta applications":{"visible_count":2}}},
                                         {"tables":{"Beta applications":{"visible_count":4}}})),1)


class FakeCall:
    type="function_call"
    name="recall_memory"
    arguments='{"query":"Replay Studio"}'
    call_id="call_abc"
    def model_dump(self,exclude_none=True):
        return {"type":"function_call","call_id":self.call_id,"name":self.name,"arguments":self.arguments}


class BrainToolTests(unittest.TestCase):
    def test_api_tool_loop_uses_source_data_without_persisting_server_state(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            m=MemoryVault(base/"memory.db");m.add("Replay Studio Unity uses ARIS")
            brain=CompanionBrain(dict(DEFAULTS),SpendLedger(base/"usage.db"),memory=m)
            call=FakeCall()
            outputs=[SimpleNamespace(output_text="",output=[call],status="completed",
                                     usage=SimpleNamespace(input_tokens=100,output_tokens=20)),
                     SimpleNamespace(output_text="Memory says Replay Studio uses ARIS",output=[],status="completed",
                                     usage=SimpleNamespace(input_tokens=110,output_tokens=35))]
            class FakeResponses:
                def __init__(self):self.kw=[]
                def create(self,**kwargs):
                    self.kw.append(kwargs)
                    return outputs.pop(0)
            f=FakeResponses()
            brain._client=SimpleNamespace(responses=f)
            with patch.dict(os.environ,{"OPENAI_API_KEY":"test_key_for_mock_only"}):
                text,usd,model=brain.ask("What do you remember about Replay Studio?",
                                         tools=LiveToolbox(memory=m))
            self.assertIn("Replay Studio uses ARIS",text)
            self.assertEqual(len(f.kw),2)
            self.assertFalse(f.kw[0]["store"])
            self.assertTrue(any(item.get("type")=="function_call_output" for item in f.kw[1]["input"] if isinstance(item,dict)))
            self.assertGreater(usd,0)
            self.assertEqual(len(m.recent()),1)

    def test_memory_disabled_means_no_log(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);m=MemoryVault(base/"memo.sqlite")
            config=dict(DEFAULTS);config["enable_local_memory"]=False
            brain=CompanionBrain(config,SpendLedger(base/"usage.sqlite"),memory=m)
            brain._client=SimpleNamespace(responses=SimpleNamespace(create=lambda **kwargs:
                                 SimpleNamespace(output_text="Okay",output=[],status="completed",usage=None)))
            with patch.dict(os.environ,{"OPENAI_API_KEY":"test_key_for_mock_only"}):
                brain.ask("Hello")
            self.assertEqual(m.recent(),[])



class GuardrailTests(unittest.TestCase):
    def test_revoked_cloud_session_blocks_tools_without_network(self):
        class FakeMonitor:
            signed_in=True
            def snapshot(self):
                raise AssertionError("No network call permitted after sign-out")
        guarded=LiveToolbox(monitor=FakeMonitor(),authorization_check=lambda:False)
        self.assertEqual(guarded.run("get_cloud_health"),{"error":"cloud_user_session_changed"})
        self.assertEqual(guarded.run("get_steam_growth"),{"error":"cloud_user_session_changed"})

    def test_revoked_project_blocks_code_and_log_access(self):
        with tempfile.TemporaryDirectory() as directory:
            guarded=LiveToolbox(approved_project=directory,
                                project_authorization_check=lambda:False)
            self.assertEqual(guarded.run("inspect_unity_errors"),{"error":"project_permission_revoked"})
            self.assertEqual(guarded.run("search_approved_code",{"query":"unity"}),{"error":"project_permission_revoked"})

    def test_background_paid_ai_is_opt_in(self):
        self.assertFalse(DEFAULTS["auto_paid_ai_daily"])
        self.assertTrue(DEFAULTS["enable_readonly_tools"])
        self.assertTrue(DEFAULTS["enable_local_memory"])

if __name__=="__main__":unittest.main()
