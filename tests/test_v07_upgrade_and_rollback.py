"""Regression tests for the owner-authorized small-edit and update boundaries."""
import hashlib
import sys
import types
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from companion.autonomy import SmallFixAutonomy
from companion.dev_assistant import WorkspaceGuard
from companion.personal_intelligence import PersonalIntelStore
from companion.private_imports import EncryptedImportVault
from companion.phone_brief import PhoneBriefing


class AutoFixRollback(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        self.root=self.base/'Unity';(self.root/'Assets').mkdir(parents=True)
        self.file=self.root/'Assets'/'Bike.cs'
        self.original='using System;\nusing UnityEngine;\nusing System;\npublic class Bike {}\n'
        self.file.write_text(self.original)
        self.guard=WorkspaceGuard(self.root)
        self.autofix=SmallFixAutonomy(self.base/'audits.sqlite3',self.base/'backups')
        self.issue={'message':'warning CS0105: duplicate using', 'file':'Assets/Bike.cs','line':3}

    def test_owner_rollback_restores_exact_original(self):
        fixed=self.autofix.handle_unity_warnings(self.guard,[self.issue],enabled=True,authorized_project=self.root)
        self.assertEqual(fixed[0]['status'],'static_verified')
        with self.assertRaises(PermissionError):self.autofix.rollback_last(self.guard,approved=False)
        result=self.autofix.rollback_last(self.guard,approved=True)
        self.assertEqual(result['status'],'rolled_back')
        self.assertEqual(self.file.read_text(),self.original)
        self.assertEqual(self.autofix.recent()[0]['status'],'rolled_back')
        with self.assertRaises(ValueError):self.autofix.rollback_last(self.guard,approved=True)

    def test_file_changed_since_fix_never_overwritten(self):
        self.autofix.handle_unity_warnings(self.guard,[self.issue],enabled=True,authorized_project=self.root)
        changed=self.file.read_text()+'// someone else edited this\n'
        self.file.write_text(changed)
        with self.assertRaises(RuntimeError):self.autofix.rollback_last(self.guard,approved=True)
        self.assertEqual(self.file.read_text(),changed)

    def test_other_workspace_cannot_restore_original(self):
        self.autofix.handle_unity_warnings(self.guard,[self.issue],enabled=True,authorized_project=self.root)
        other=self.base/'Other';(other/'Assets').mkdir(parents=True)
        (other/'Assets'/'Bike.cs').write_text('using UnityEngine;\n')
        with self.assertRaises(ValueError):self.autofix.rollback_last(WorkspaceGuard(other),approved=True)


class SecureUpgradeChecks(unittest.TestCase):
    def setUp(self):
        self.project=Path(__file__).resolve().parent.parent

    def test_updater_skips_credentials_and_personal_data(self):
        script=(self.project/'Update_Existing_Install.cmd').read_text()
        self.assertIn('/XF .env config.json',script)
        self.assertIn('/XD .venv data __pycache__',script)
        self.assertIn('pip install --disable-pip-version-check -r',script)
        self.assertLess(script.index('pip install --disable-pip-version-check -r'),script.index('robocopy "%SOURCE%" "%TARGET%"'))
        self.assertIn('upgrade_backups',script)

    def test_sensitive_import_needs_os_credential_store(self):
        with tempfile.TemporaryDirectory() as folder:
            scope=PersonalIntelStore(Path(folder)/'intelligence.sqlite3')
            scope.set_permission('finance',local=True)
            vault=EncryptedImportVault(Path(folder)/'import.sqlite3',scope)
            with patch.dict(sys.modules,{'keyring':types.SimpleNamespace(get_password=lambda *a: (_ for _ in ()).throw(RuntimeError('No credential manager')))}):
                with self.assertRaisesRegex(RuntimeError,'Credential Manager unavailable'):
                    vault._cipher()
            f=Path(folder)/'private.csv';f.write_text('date,description,amount\n2026-11-04,Test,10.00\n')
            with patch.dict(sys.modules,{'keyring':types.SimpleNamespace(get_password=lambda *a: (_ for _ in ()).throw(RuntimeError('No credential manager')))}):
                with self.assertRaises(RuntimeError):vault.import_file(f,'finance')
            self.assertEqual(vault.counts(),{})

    def test_phone_off_by_default(self):
        with tempfile.TemporaryDirectory() as folder:
            phone=PhoneBriefing(Path(folder)/'phone.sqlite3')
            self.assertEqual(phone.send('private',enabled=False)['status'],'disabled')


if __name__=='__main__':unittest.main()
