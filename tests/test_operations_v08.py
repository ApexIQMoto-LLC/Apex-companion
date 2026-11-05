import io
import json
import os
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from companion.operations_queue import OperationsQueue
from companion.operations_unity import (UnityEditModeRunner, VerifiedPatchTrial, git_health,
    parse_nunit, safe_unity_executable, project_fingerprint)
from companion.operations_phone import RemoteOperations
from companion.operations_desktop import DesktopInspector
from companion.dev_assistant import WorkspaceGuard
from companion.phone_brief import PhoneBriefing
from companion.assistant import CompanionBrain


class TempTest(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.base=Path(t.name)


class QueueTests(TempTest):
    def setUp(self):
        super().setUp()
        self.path=self.base/'ops.db';self.q=OperationsQueue(self.path)

    def test_roundtrip_and_restart(self):
        tid=self.q.enqueue('git_health',project_hash='fingerprint',origin='away')
        self.assertEqual(OperationsQueue(self.path).get(tid)['status'],'queued')
        row=self.q.claim();self.assertEqual(row['kind'],'git_health')
        self.assertEqual(row['attempts'],1)
        self.assertTrue(self.q.finish(tid,'completed',{'state':'ok','tracked_changes':1}))
        self.assertEqual(OperationsQueue(self.path).get(tid)['result']['tracked_changes'],1)
        self.assertIsNone(self.q.claim())
        self.assertFalse(self.q.finish(tid,'failed'))

    def test_pause_and_resume(self):
        self.q.enqueue('unity_diagnostics')
        self.q.set_paused(True)
        self.assertIsNone(self.q.claim())
        self.assertTrue(OperationsQueue(self.path).paused())
        self.q.set_paused(False)
        self.assertEqual(self.q.claim()['kind'],'unity_diagnostics')

    def test_duplicate_away_debounce(self):
        first=self.q.enqueue('git_health',dedupe_key='day1:repo1')
        second=self.q.enqueue('git_health',dedupe_key='day1:repo1')
        self.assertEqual(first,second)
        self.assertEqual(self.q.counts()['queued'],1)

    def test_crash_recovery_never_reruns(self):
        tid=self.q.enqueue('unity_editmode_tests')
        self.q.claim()
        self.assertEqual(OperationsQueue(self.path).recover_interrupted(),1)
        self.assertEqual(self.q.get(tid)['status'],'blocked')
        self.assertEqual(self.q.get(tid)['error_code'],'interrupted_restart')
        self.assertIsNone(self.q.claim())

    def test_disallowed_task_and_payload_and_origin(self):
        for cmd in ('powershell','delete','deploy','purchase','run_shell','change_db'):
            with self.assertRaises(ValueError):self.q.enqueue(cmd)
        with self.assertRaises(PermissionError):self.q.enqueue('unity_editmode_tests',origin='phone')
        with self.assertRaises(ValueError):self.q.enqueue('unity_diagnostics',payload={'command':'whoami'})
        with self.assertRaises(ValueError):self.q.enqueue('unity_diagnostics',origin='webhook')

    def test_queue_limit_and_cancel(self):
        tids=[self.q.enqueue('git_health') for _ in range(25)]
        with self.assertRaises(RuntimeError):self.q.enqueue('git_health')
        self.assertTrue(self.q.cancel(tids[0]))
        self.assertFalse(self.q.cancel(tids[0]))
        self.assertTrue(self.q.enqueue('git_health'))

    def test_no_sensitive_raw_args_in_db(self):
        tid=self.q.enqueue('unity_diagnostics',origin='phone',note='Approved Unity scan')
        data=self.path.read_bytes()
        self.assertNotIn(b'API_KEY',data)
        self.assertEqual(self.q.get(tid)['payload'],{})


class UnityOpsTests(TempTest):
    def setUp(self):
        super().setUp()
        self.project=self.base/'Game';(self.project/'Assets').mkdir(parents=True)
        (self.project/'ProjectSettings').mkdir()
        (self.project/'ProjectSettings'/'ProjectVersion.txt').write_text('m_EditorVersion: 6000.1.0f1')
        self.src=self.project/'Assets'/'Bike.cs'
        self.src.write_text('using System;\nclass Bike { int a=1; }\n',encoding='utf-8')
        self.exe=self.base/'Unity'/'Hub'/'Editor'/'6000.1.0'/'Editor'/'Unity.exe'
        self.exe.parent.mkdir(parents=True)
        self.exe.write_bytes(b'TEST DUMMY, not executed')
        self.runner=UnityEditModeRunner(self.base/'runs')

    def test_safe_unity_path_validation(self):
        self.assertEqual(safe_unity_executable(self.exe),self.exe.resolve())
        evil=self.base/'Downloads'/'Unity.exe';evil.parent.mkdir();evil.write_bytes(b'fake')
        with self.assertRaises(ValueError):safe_unity_executable(evil)

    def test_test_command_is_fixed_and_no_quit(self):
        c=self.runner.command(self.exe,self.project,self.base/'result.xml',self.base/'log.txt')
        self.assertIn('-runTests',c)
        self.assertIn('EditMode',c)
        self.assertIn('-batchmode',c)
        self.assertNotIn('-quit',c)
        self.assertNotIn('cmd.exe',c)

    def test_no_run_when_project_locked(self):
        (self.project/'Temp').mkdir()
        (self.project/'Temp'/'UnityLockfile').write_bytes(b'x')
        with self.assertRaises(RuntimeError):self.runner.run(self.project,self.exe,executor=lambda c,t:0)

    def test_nunit_pass_and_failure_and_missing(self):
        xml=self.base/'tests.xml'
        xml.write_text('<test-run><test-case result="Passed"/><test-case result="Skipped"/></test-run>')
        self.assertTrue(parse_nunit(xml)['verified'])
        xml.write_text('<test-run><test-case result="Failed"/></test-run>')
        self.assertFalse(parse_nunit(xml)['verified'])
        xml.unlink()
        self.assertFalse(parse_nunit(xml)['verified'])

    def test_fake_test_run_verifies_nunit(self):
        def fake_run(cmd,timeout):
            out=Path(cmd[cmd.index('-testResults')+1])
            out.write_text('<test-run><test-case result="Passed"/><test-case result="Passed"/></test-run>')
            return 0
        result=self.runner.run(self.project,self.exe,executor=fake_run)
        self.assertEqual(result['state'],'passed');self.assertEqual(result['passed'],2)
        self.assertTrue(result['tests_verified'])

    def test_missing_xml_not_false_pass(self):
        report=self.runner.run(self.project,self.exe,executor=lambda cmd,t:0)
        self.assertEqual(report['state'],'failed')
        self.assertFalse(report['tests_verified'])

    def test_nonzero_exit_not_pass(self):
        def fake_run(cmd,timeout):
            Path(cmd[cmd.index('-testResults')+1]).write_text('<test-run><test-case result="Passed"/></test-run>')
            return 1
        result=self.runner.run(self.project,self.exe,executor=fake_run)
        self.assertFalse(result['tests_verified'])

    def test_verified_patch_rolls_back_on_failed_editmode(self):
        guard=WorkspaceGuard(self.project)
        proposal=guard.propose('Assets/Bike.cs','int a=1','int a=2')
        class Stub:
            def prepare(self,*a):return None
            def run(self,*a,**kw):return {'tests_verified':False,'state':'failed'}
        trial=VerifiedPatchTrial(Stub(),self.base/'backups')
        ret=trial.apply_and_test(guard,proposal,self.exe,approved=True)
        self.assertEqual(ret['state'],'rolled_back')
        self.assertIn('int a=1',self.src.read_text())
        self.assertEqual(len(list((self.base/'backups').glob('*.bak'))),1)

    def test_verified_patch_keeps_passing_edit(self):
        guard=WorkspaceGuard(self.project)
        proposal=guard.propose('Assets/Bike.cs','int a=1','int a=2')
        class Stub:
            def prepare(self,*a):return None
            def run(self,*a,**kw):return {'tests_verified':True,'state':'passed'}
        ret=VerifiedPatchTrial(Stub(),self.base/'backups').apply_and_test(guard,proposal,self.exe,approved=True)
        self.assertEqual(ret['state'],'verified');self.assertIn('int a=2',self.src.read_text())

    def test_patch_no_permission_no_write(self):
        guard=WorkspaceGuard(self.project)
        proposal=guard.propose('Assets/Bike.cs','int a=1','int a=2')
        class Stub:
            def prepare(self,*a):return None
            def run(self,*a,**kw):return None
        with self.assertRaises(PermissionError):
            VerifiedPatchTrial(Stub(),self.base/'backups').apply_and_test(guard,proposal,self.exe,approved=False)
        self.assertIn('int a=1',self.src.read_text())

    def test_patch_conflict_doesnt_clobber_other_edits(self):
        guard=WorkspaceGuard(self.project)
        proposal=guard.propose('Assets/Bike.cs','int a=1','int a=2')
        src=self.src
        class Stub:
            def prepare(self,*a):return None
            def run(self,*a,**kw):
                src.write_text('using System;\nclass Bike { int a=4; }\n')
                return {'tests_verified':False,'state':'failed'}
        ret=VerifiedPatchTrial(Stub(),self.base/'backups').apply_and_test(guard,proposal,self.exe,approved=True)
        self.assertEqual(ret['state'],'conflict');self.assertIn('int a=4',src.read_text())

    def test_git_health_on_non_git_repo(self):
        r=git_health(self.project)
        self.assertIn(r['state'],{'not_a_repository','unavailable'})


class RemoteTests(TempTest):
    def setUp(self):
        super().setUp()
        self.q=OperationsQueue(self.base/'task.db')
        self.phone=PhoneBriefing(self.base/'phone.db')
        self.remote=RemoteOperations(self.base/'remote.db',self.q,self.phone)
        self.env=patch.dict(os.environ,{'APEX_TELEGRAM_BOT_TOKEN':'123456789:AAAABBBBCCCCDDDDEEEEFFFFGGGG',
                                        'APEX_TELEGRAM_CHAT_ID':'123456789'},clear=False)
        self.env.start();self.addCleanup(self.env.stop)
    def msg(self,update_id,cmd,uid=123456789,type='private',chat=123456789,**overrides):
        message={'text':cmd,'chat':{'id':chat,'type':type},'from':{'id':uid}}
        message.update(overrides)
        return {'update_id':update_id,'message':message}

    def test_authorized_owner_scans(self):
        rows=self.remote.handle_updates([self.msg(5,'/scan'),self.msg(6,'/git')],owner_id='123456789',approved_project=True)
        self.assertEqual(len(rows),2)
        self.assertEqual(len(self.q.recent()),2)
        self.assertTrue(all(x['origin']=='phone' for x in self.q.recent()))
        self.assertEqual(self.remote.handle_updates([self.msg(5,'/scan')],owner_id='123456789',approved_project=True),[])

    def test_group_and_other_sender_ignored(self):
        rows=self.remote.handle_updates([self.msg(1,'/pause',type='group'),self.msg(2,'/pause',uid=333),self.msg(3,'/pause',chat=9)],owner_id='123456789')
        self.assertEqual(rows,[]);self.assertFalse(self.q.paused())

    def test_forwarded_and_unknown_commands_ignored(self):
        rows=self.remote.handle_updates([self.msg(1,'/scan',forward_origin={'x':1}),self.msg(2,'/deploy'),self.msg(3,'/shell rm -rf /'),self.msg(4,'/tests')],owner_id='123456789',approved_project=True)
        self.assertEqual(rows,[]);self.assertEqual(self.q.recent(),[])

    def test_pause_resume(self):
        result=self.remote.handle_updates([self.msg(1,'/pause')],owner_id='123456789')
        self.assertTrue(self.q.paused());self.assertEqual(result[0]['command'],'/pause')
        self.remote.handle_updates([self.msg(2,'/resume')],owner_id='123456789')
        self.assertFalse(self.q.paused())

    def test_permission_revocation_prevents_poll(self):
        self.assertEqual(self.remote.poll(authorized=False,approved_project=True)[0]['state'],'disabled')
        self.assertEqual(self.remote.handle_updates([self.msg(1,'/scan')],owner_id='123456789',authorized=False),[{'state':'disabled'}])

    def test_remote_without_project_cannot_enqueue(self):
        rows=self.remote.handle_updates([self.msg(1,'/scan')],owner_id='123456789',approved_project=False)
        self.assertIn('No Unity project',rows[0]['reply'])
        self.assertEqual(self.q.recent(),[])

    def test_poll_uses_fixed_telegram_method_and_owner(self):
        calls=[]
        class MockResponse:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,n):return json.dumps({'ok':True,'result':[self_row]}).encode()
        self_row=self.msg(10,'/status')
        def fake(req,timeout):
            calls.append((req,timeout))
            return MockResponse()
        out=self.remote.poll(authorized=True,approved_project=True,transport=fake)
        self.assertEqual(out[0]['command'],'/status')
        self.assertTrue(calls[0][0].full_url.endswith('/getUpdates'))
        self.assertEqual(json.loads(calls[0][0].data)['allowed_updates'],['message'])


class DesktopTests(TempTest):
    def test_perms_before_os_or_screen(self):
        inspector=DesktopInspector(self.base/'screens')
        with self.assertRaises(PermissionError):inspector.list_windows(permitted=False)
        with self.assertRaises(PermissionError):inspector.active_window(permitted=False)
        with self.assertRaises(PermissionError):inspector.capture_window(100,permitted=False,consented=False)
        self.assertFalse((self.base/'screens').exists())

    def test_image_input_bounded_and_explicit(self):
        from PIL import Image
        im=self.base/'capture.png';Image.new('RGB',(250,180)).save(im)
        class FakeLedger:
            def month_total(self):return 0
            def today_count(self):return 0
            def record(self,*args):return 0.0002
        settings={'monthly_budget_usd':5,'daily_request_limit':10,'max_context_turns':2,
                  'chat_model':'gpt-6-luna','deep_model':'gpt-6.1-terra','max_output_tokens':1300}
        brain=CompanionBrain(settings,FakeLedger())
        body=[]
        class Responses:
            def create(self,**kw):
                body.append(kw)
                return SimpleNamespace(status='completed',output_text='I see a window.',usage=SimpleNamespace(input_tokens=120,output_tokens=20))
        brain._client=SimpleNamespace(responses=Responses())
        with patch.dict(os.environ,{'OPENAI_API_KEY':'sk-fake-test-only'},clear=False):
            answer,cost,model=brain.inspect_owner_screenshot(im,'Analyze this UI')
        self.assertIn('window',answer)
        self.assertEqual(cost,0.0002)
        self.assertEqual(body[0]['input'][0]['content'][1]['type'],'input_image')
        self.assertTrue(body[0]['store'] is False)
        self.assertEqual(body[0]['model'],'gpt-6-luna')


if __name__ == '__main__':unittest.main()

class OperationsAIToolTests(TempTest):
    def test_operations_tool_is_read_only_and_permission_scoped(self):
        from companion.live_tools import LiveToolbox
        q=OperationsQueue(self.base/'ops.db')
        taskid=q.enqueue('unity_diagnostics',origin='away',project_hash='test')
        q.claim()
        q.finish(taskid,'completed',{'state':'completed','sampled_errors':3,'private_path':'C:\\secret\\folder'})
        class Perm:
            allowed=True
            def permitted(self,scope,destination):return self.allowed and scope=='operations' and destination=='ai'
        owner=Perm()
        tools=LiveToolbox(personal=owner,operations=q)
        self.assertIn('get_operations_history',[x['name'] for x in tools.schemas()])
        data=tools.run('get_operations_history')
        self.assertEqual(data['items'][0]['sampled_errors'],3)
        self.assertNotIn('private_path',str(data))
        self.assertNotIn('C:\\secret',str(data))
        owner.allowed=False
        self.assertNotIn('get_operations_history',[x['name'] for x in tools.schemas()])
        self.assertEqual(tools.safe_run('get_operations_history',{}),'{"error": "tool_not_allowed"}')

    def test_operations_tool_denies_when_authorization_generation_changes(self):
        from companion.live_tools import LiveToolbox
        class Perm:
            def permitted(self,scope,destination):return scope=='operations'
        tools=LiveToolbox(personal=Perm(),operations=OperationsQueue(self.base/'ops.db'),
                          operations_authorization_check=lambda:False)
        self.assertEqual(tools.run('get_operations_history'),{'error':'operations_permission_revoked'})
