import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from companion.autonomy import SmallFixAutonomy
from companion.dev_assistant import WorkspaceGuard
from companion.personal_intelligence import PersonalIntelStore
from companion.phone_brief import PhoneBriefing, sanitize_phone_text


class AutofixTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)
        self.project=self.folder/'MyUnity';(self.project/'Assets').mkdir(parents=True)
        self.source=self.project/'Assets'/'Bike.cs'
        self.source.write_text('using System;\nusing UnityEngine;\nusing System;\npublic class Bike {}\n',encoding='utf-8')
        self.guard=WorkspaceGuard(self.project)
        self.ai=SmallFixAutonomy(self.folder/'audit.sqlite3',self.folder/'backups')
        self.issue={'message':'Assets/Bike.cs(3,1): warning CS0105: duplicate using',
                    'file':'Assets/Bike.cs','line':3,'severity':'warning'}

    def test_deterministic_cleanup_and_backup(self):
        outcome=self.ai.handle_unity_warnings(self.guard,[self.issue],enabled=True,authorized_project=self.project)
        self.assertEqual(outcome[0]['status'],'static_verified')
        self.assertEqual(self.source.read_text().count('using System;'),1)
        self.assertEqual(self.ai.today_fixes(),1)
        self.assertEqual(len(list((self.folder/'backups').glob('*.bak'))),1)
        self.assertIn('Unity compilation was not run',outcome[0]['warning'])
        self.assertEqual(self.ai.handle_unity_warnings(self.guard,[self.issue],enabled=True,
                       authorized_project=self.project)[0]['status'],'skipped')

    def test_disabled_means_no_changes(self):
        self.assertEqual(self.ai.handle_unity_warnings(self.guard,[self.issue],enabled=False,
                         authorized_project=self.project)[0]['status'],'disabled')
        self.assertEqual(self.source.read_text().count('using System;'),2)

    def test_non_assets_file_is_not_modified(self):
        path=self.project/'Packages';path.mkdir()
        f=path/'Bike.cs';f.write_text(self.source.read_text())
        issue=dict(self.issue,file='Packages/Bike.cs')
        outcome=self.ai.handle_unity_warnings(self.guard,[issue],enabled=True,authorized_project=self.project)
        self.assertEqual(outcome[0]['status'],'skipped')
        self.assertEqual(f.read_text().count('using System;'),2)

    def test_preprocessor_blocks_autofix(self):
        self.source.write_text('using System;\n#if DEBUG\nusing System;\n#endif\npublic class Bike {}\n')
        self.assertEqual(self.ai.handle_unity_warnings(self.guard,[self.issue],enabled=True,
                         authorized_project=self.project)[0]['status'],'skipped')

    def test_revoked_project_blocks_autofix(self):
        self.assertEqual(self.ai.handle_unity_warnings(self.guard,[self.issue],enabled=True,
                         authorized_project=self.project,permission_check=lambda:False)[0]['status'],'blocked')

    def test_unlinked_warning_not_modified(self):
        issue=dict(self.issue,message='CS0618 obsolete API warning')
        self.assertEqual(self.ai.handle_unity_warnings(self.guard,[issue],enabled=True,
                         authorized_project=self.project),[])
        self.assertEqual(self.source.read_text().count('using System;'),2)

    def test_rate_limit(self):
        self.ai.handle_unity_warnings(self.guard,[self.issue],enabled=True,authorized_project=self.project,max_per_day=1)
        other=self.project/'Assets'/'Other.cs'
        other.write_text('using System;\nusing UnityEngine;\nusing System;\npublic class Other {}\n')
        issue=dict(self.issue,file='Assets/Other.cs')
        self.assertEqual(self.ai.handle_unity_warnings(self.guard,[issue],enabled=True,
                         authorized_project=self.project,max_per_day=1),[])
        self.assertEqual(other.read_text().count('using System;'),2)


class FakeHTTP:
    def __init__(self):self.response=io.BytesIO(b'{"ok":true}')
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,n):return self.response.read(n)


class PhoneTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.phone=PhoneBriefing(Path(self.tmp.name)/'phone.sqlite3')
        self.env=patch.dict(os.environ,{'APEX_TELEGRAM_BOT_TOKEN':'123456789:AAAABBBBCCCCDDDDEEEEFFFFGGGG','APEX_TELEGRAM_CHAT_ID':'123456789'},clear=False)
        self.env.start();self.addCleanup(self.env.stop)

    def test_no_auto_phone_delivery_by_default(self):
        self.assertEqual(self.phone.send('hi',enabled=False)['status'],'disabled')

    def test_telegram_dedup_delivery(self):
        sent=[]
        def fake(req,timeout):
            sent.append(req)
            return FakeHTTP()
        self.assertTrue(self.phone.configured())
        self.assertEqual(self.phone.send('One status',enabled=True,transport=fake,digest_id='today')['status'],'sent')
        self.assertEqual(self.phone.send('One status',enabled=True,transport=fake,digest_id='today')['status'],'already_sent')
        self.assertEqual(len(sent),1)
        self.assertTrue(self.phone.delivered('today'))
        self.assertEqual(json.loads(sent[0].data)['chat_id'],'123456789')

    def test_unknown_type_rejected(self):
        self.assertEqual(self.phone.send('post an ad',enabled=True,message_type='purchase')['status'],'blocked_type')

    def test_redacts_secrets(self):
        s=sanitize_phone_text('my sk-abcdefghijklmnopqrs and secret C:\\Users\\x\\Desktop\\Code.cs')
        self.assertNotIn('sk-abcdefghijklmnopqrs',s)
        self.assertNotIn('C:\\Users',s)


if __name__=='__main__':unittest.main()
