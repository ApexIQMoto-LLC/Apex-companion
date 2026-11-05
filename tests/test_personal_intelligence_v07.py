import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime,timezone

from cryptography.fernet import Fernet

from companion.memory import MemoryVault
from companion.personal_intelligence import PersonalIntelStore,SCOPES
from companion.intelligence_engine import consolidate,plan_today,analysis_report
from companion.private_imports import EncryptedImportVault,rows_from_selected_file
from companion.live_tools import LiveToolbox
from companion.activity_capture import CoarseActivityCapture


class PersonalIntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.d=Path(self.temp.name)
        self.db=PersonalIntelStore(self.d/'personal.sqlite3')

    def test_sensitive_scopes_start_off(self):
        permissions=self.db.permissions()
        for scope in ("finance","health","personal","communications","calendar","computer"):
            self.assertFalse(permissions[scope]['local'])
            self.assertFalse(permissions[scope]['ai'])
            self.assertFalse(permissions[scope]['phone'])
        self.assertTrue(permissions['projects']['local'])
        self.assertTrue(permissions['projects']['ai'])
        self.assertFalse(permissions['projects']['phone'])

    def test_scopes_cannot_send_to_ai_without_local(self):
        with self.assertRaises(ValueError):
            self.db.set_permission('finance',local=False,ai=True)
        with self.assertRaises(ValueError):
            self.db.set_permission('health',local=False,phone=True)
        with self.assertRaises(ValueError):
            self.db.set_permission('private_filez',local=True)

    def test_entity_cannot_be_stored_without_optin(self):
        with self.assertRaises(PermissionError):
            self.db.add_entity('preference','Private budget','Sensitive',scope='finance')
        self.db.set_permission('finance',local=True)
        self.db.add_entity('resource','My budget','USD 123',scope='finance')
        self.assertEqual(self.db.search('budget',destination='ai'),[])
        self.db.set_permission('finance',local=True,ai=True)
        self.assertEqual(len(self.db.search('budget',destination='ai')),1)
        self.db.set_permission('finance',local=False)
        self.assertEqual(self.db.search('budget',destination='local'),[])

    def test_links_filtered_by_scope(self):
        p=self.db.add_entity('project','Replay Studio','Unity project',scope='projects')
        self.db.set_permission('personal',local=True)
        q=self.db.add_entity('goal','Personal schedule','Some personal plan',scope='personal')
        self.db.link(p,q,'contributes_to')
        self.assertEqual(self.db.related(p,destination='ai'),[])
        self.db.set_permission('personal',local=True,ai=True)
        self.assertEqual(self.db.related(p,destination='ai')[0]['id'],q)

    def test_timeline_dedup_and_scope(self):
        self.assertTrue(self.db.add_event('test','Device status','stale',dedupe_key='heartbeat-1'))
        self.assertFalse(self.db.add_event('test','Device status','stale',dedupe_key='heartbeat-1'))
        self.assertEqual(len(self.db.timeline()),1)
        self.assertIsNone(self.db.add_event('private','Finance import',scope='finance'))
        self.assertEqual(self.db.trends()['observed_events'],1)
        self.assertEqual(self.db.trends()['evidence_quality'],'insufficient')

    def test_plan_prioritization_and_done(self):
        ident=self.db.add_plan('Review Unity compile errors',scope='projects',priority=1,due_day='2026-01-01')
        self.db.add_plan('Nice marketing idea',scope='projects',priority=5)
        plan=plan_today(self.db)['items']
        self.assertEqual(plan[0]['task_id'],ident)
        self.assertTrue(self.db.update_plan(ident,'done'))
        self.assertEqual(len(self.db.list_plan()),1)
        with self.assertRaises(ValueError):self.db.update_plan(ident,'overwrote_everything')

    def test_erasure_both_nodes_links_events_goals_insights(self):
        self.db.set_permission('personal',local=True,ai=True)
        p=self.db.add_entity('project','Project Alpha',scope='projects')
        q=self.db.add_entity('goal','Personal goal',scope='personal')
        self.db.link(p,q)
        self.db.add_event('test','Personal history',scope='personal')
        self.db.add_plan('Personal task',scope='personal')
        self.db.remember_insight('Some repeated fact','sources',3,scope='personal')
        self.db.erase_scope('personal')
        self.assertEqual(self.db.search('Personal',destination='ai'),[])
        self.assertEqual(self.db.related(p),[])
        self.assertEqual(self.db.list_insights(),[])
        self.assertEqual(self.db.list_plan(),[])
        self.assertEqual(self.db.timeline(scope='personal'),[])

    def test_project_only_consolidation_ignores_finance_and_health_memory(self):
        mem=MemoryVault(self.d/'old_mem.sqlite3')
        mem.add('Our Replay Studio mountain pass is a launch blocker')
        mem.add('My bank balance is 500 dollars')
        mem.add('My health issue is private')
        result=consolidate(self.db,mem)
        self.assertEqual(result['imported'],1)
        result=consolidate(self.db,mem)
        self.assertEqual(result['imported'],1) # idempotent upsert
        exported=self.db.export_scope('projects')
        self.assertTrue(any('Replay Studio' in r['title'] for r in exported['entities']))
        self.assertFalse(any('bank' in r['title'].lower() for r in exported['entities']))

    def test_activity_capture_requires_double_optin_and_only_app_name(self):
        capture=CoarseActivityCapture(self.db)
        self.assertEqual(capture.tick('my-secret.exe')['status'],'disabled')
        self.db.set_permission('computer',local=True)
        self.assertEqual(capture.tick('Unity.exe')['status'],'sampled')
        self.assertEqual(len(self.db.timeline(scope='computer')),1)
        self.assertNotIn('my-secret',str(self.db.timeline(scope='computer')))
        self.db.set_permission('computer',local=False)
        self.assertEqual(capture.tick('Steam.exe')['status'],'disabled')

    def test_tools_ai_scope_no_bypass(self):
        self.db.set_permission('finance',local=True,ai=False)
        self.db.add_entity('resource','Banking secret amounts','Save 500',scope='finance')
        t=LiveToolbox(personal=self.db,personal_authorization_check=lambda:True)
        self.assertIn('search_personal_knowledge',[x['name'] for x in t.schemas()])
        self.assertNotIn('Save 500',t.safe_run('search_personal_knowledge',{'query':'Banking amounts'}))
        self.db.set_permission('finance',local=True,ai=True)
        self.assertIn('Save 500',t.safe_run('search_personal_knowledge',{'query':'Banking amounts'}))
        x=LiveToolbox(personal=self.db,personal_authorization_check=lambda:False)
        self.assertEqual(x.run('search_personal_knowledge',{'query':'Banking'}),{'error':'personal_permission_revoked'})


class EncryptedImportsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)
        self.personal=PersonalIntelStore(self.path/'scope.sqlite3')
        self.private=EncryptedImportVault(self.path/'encrypted.sqlite3',self.personal,key_bytes=Fernet.generate_key())

    def test_ciphertext_does_not_contain_plaintext(self):
        self.personal.set_permission('finance',local=True)
        file=self.path/'transactions.csv'
        file.write_text('date,description,amount,account_number,password\n2026-11-04,Hardware,39.25,1234567890123456,hide-me\n',encoding='utf-8')
        r=self.private.import_file(file,'finance')
        self.assertEqual(r['imported'],1)
        raw=(self.path/'encrypted.sqlite3').read_bytes()
        self.assertNotIn(b'Hardware',raw)
        self.assertNotIn(b'hide-me',raw)
        self.assertNotIn(b'1234567890123456',raw)
        self.assertEqual(self.private.search('finance','Hardware','ai')['status'],'permission_denied')
        self.personal.set_permission('finance',local=True,ai=True)
        m=self.private.search('finance','Hardware','ai')['matching']
        self.assertEqual(m[0]['data']['description'],'Hardware')
        self.assertNotIn('password',m[0]['data'])
        self.assertNotIn('account_number',m[0]['data'])
        self.personal.set_permission('finance',local=False)
        self.assertEqual(self.private.search('finance','Hardware')['status'],'permission_denied')
        self.private.erase_scope('finance')
        self.personal.set_permission('finance',local=True)
        self.assertEqual(self.private.counts().get('finance',0),0)

    def test_calendar_ics(self):
        f=self.path/'schedule.ics'
        f.write_text('BEGIN:VCALENDAR\nBEGIN:VEVENT\nSUMMARY:Study cybersecurity\nDTSTART:20261105T190000\nDESCRIPTION:Study block\nEND:VEVENT\nEND:VCALENDAR',encoding='utf-8')
        rows=rows_from_selected_file(f)
        self.assertEqual(rows[0]['SUMMARY'],'Study cybersecurity')
        with self.assertRaises(PermissionError):self.private.import_file(f,'calendar')
        self.personal.set_permission('calendar',local=True)
        self.assertEqual(self.private.import_file(f,'calendar')['encrypted'],True)

    def test_export_never_imports_key_columns(self):
        f=self.path/'data.json'
        f.write_text(json.dumps([{'note':'Motorcycle progress','api_key':'secret','ssn':'123-45-6789'}]),encoding='utf-8')
        rows=rows_from_selected_file(f)
        self.assertNotIn('api_key',rows[0]);self.assertNotIn('ssn',rows[0])

    def test_source_path_symlink_rejected(self):
        f=self.path/'real.txt';f.write_text('sample')
        link=self.path/'link.txt'
        link.symlink_to(f)
        with self.assertRaises(ValueError):rows_from_selected_file(link)


if __name__=='__main__':unittest.main()
