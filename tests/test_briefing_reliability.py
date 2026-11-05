"""Regression coverage for six-part operating brief failures observed in live use."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from companion.assistant import CompanionBrain
from companion.costs import SpendLedger
from companion.memory import MemoryVault
from companion.settings import DEFAULTS


class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base=Path(self.tmp.name)
        self.ledger=SpendLedger(base/'usage.sqlite3')
        self.memory=MemoryVault(base/'mem.sqlite3')
        self.brain=CompanionBrain(dict(DEFAULTS),self.ledger,memory=self.memory)
        self.token=patch.dict(os.environ,{'OPENAI_API_KEY':'test_mock_key_only'})
        self.token.start()
        self.addCleanup(self.token.stop)

    @staticmethod
    def response(status='completed',text='Answer completed',calls=None,reason=None, in_tokens=90,out_tokens=100):
        return SimpleNamespace(status=status,output_text=text,output=calls or [],
                               incomplete_details=SimpleNamespace(reason=reason),
                               usage=SimpleNamespace(input_tokens=in_tokens,output_tokens=out_tokens))

    def test_short_chat_remains_inexpensive(self):
        seen=[]
        def create(**kwargs):
            seen.append(kwargs)
            return self.response()
        self.brain._client=SimpleNamespace(responses=SimpleNamespace(create=create))
        answer,spend,model=self.brain.ask('Hello')
        self.assertEqual(answer,'Answer completed')
        self.assertEqual(seen[0]['max_output_tokens'],1300)
        self.assertEqual(len(seen),1)
        self.assertGreater(spend,0)

    def test_multipart_brief_gets_large_initial_budget(self):
        seen=[]
        prompt='Apex: complete business intelligence report.\n'+''.join(f'{i}. Analyze section with evidence.\n' for i in range(1,7))
        self.brain._client=SimpleNamespace(responses=SimpleNamespace(create=lambda **kw: (seen.append(kw),self.response())[1]))
        answer,_,_=self.brain.ask(prompt)
        self.assertEqual(answer,'Answer completed')
        self.assertGreaterEqual(seen[0]['max_output_tokens'],4000)
        self.assertEqual(len(seen),1)

    def test_max_output_incomplete_retries_once_and_bills_both(self):
        seen=[]
        outputs=[self.response('incomplete','',reason='max_output_tokens',out_tokens=1200),self.response()]
        def create(**kwargs):
            seen.append(kwargs)
            return outputs.pop(0)
        self.brain._client=SimpleNamespace(responses=SimpleNamespace(create=create))
        answer,cost,_=self.brain.ask('Explain why Steam and live hardware data disagree.')
        self.assertEqual(answer,'Answer completed')
        self.assertEqual(len(seen),2)
        self.assertGreater(seen[1]['max_output_tokens'],seen[0]['max_output_tokens'])
        self.assertEqual(self.ledger.today_count(),2)
        self.assertGreater(cost,0)

    def test_no_retry_for_content_filter_or_other_status(self):
        seen=[]
        def create(**kw):
            seen.append(kw)
            return self.response('incomplete','',reason='content_filter')
        self.brain._client=SimpleNamespace(responses=SimpleNamespace(create=create))
        with self.assertRaisesRegex(RuntimeError,'content_filter'):
            self.brain.ask('Question')
        self.assertEqual(len(seen),1)

    def test_max_output_retry_is_bounded(self):
        seen=[]
        def create(**kw):
            seen.append(kw)
            return self.response('incomplete','',reason='max_output_tokens')
        self.brain._client=SimpleNamespace(responses=SimpleNamespace(create=create))
        with self.assertRaisesRegex(RuntimeError,'output limit'):
            self.brain.ask('Briefing')
        self.assertEqual(len(seen),2)
        self.assertLessEqual(max(x['max_output_tokens'] for x in seen),7000)

    def test_model_calls_more_than_budget_get_all_outputs_and_no_extra_reads(self):
        seen=[];tool_calls=[]
        class FakeCall:
            type='function_call'
            def __init__(self,num):
                self.call_id=f'call_{num}'
                self.name='recall_memory'
                self.arguments='{"query":"motorcycles"}'
            def model_dump(self,exclude_none=True):
                return {'type':'function_call','name':self.name,'call_id':self.call_id,'arguments':self.arguments}
        calls1=[FakeCall(x) for x in range(1,9)]
        calls2=[FakeCall(x) for x in range(9,17)]
        outputs=[self.response(text='',calls=calls1),self.response(text='',calls=calls2),self.response()]
        def create(**kw):
            seen.append(kw)
            return outputs.pop(0)
        class Tool:
            def schemas(self):return [{'type':'function','name':'recall_memory','parameters':{'type':'object','properties':{}}}]
            def safe_run(self,name,args):
                tool_calls.append(name)
                return '{"source":"local"}'
        self.brain._client=SimpleNamespace(responses=SimpleNamespace(create=create))
        answer,_,_=self.brain.ask('Get all available records',tools=Tool())
        self.assertEqual(answer,'Answer completed')
        self.assertEqual(len(tool_calls),12)
        messages=[x for x in seen[-1]['input'] if isinstance(x,dict) and x.get('type')=='function_call_output']
        self.assertEqual(len(messages),16)
        self.assertEqual({x['call_id'] for x in messages},{f'call_{i}' for i in range(1,17)})
        self.assertTrue(any('read_tool_budget_reached' in x['output'] for x in messages))

    def test_numbered_memory_command_persists_even_when_embedded(self):
        large='''Apex, prepare a business intelligence briefing.
1. LIVE INTELLIGENCE
Get Steam information.
4. MEMORY
Remember this priority: "Reliable hardware beta and Replay Studio stability before new features."
5. AUTONOMY
Explain the limits.'''
        ident=self.memory.remember_from_message(large)
        self.assertIsInstance(ident,int)
        reopened=MemoryVault(self.memory.path)
        self.assertEqual(reopened.list_memories()[0]['fact'],'Reliable hardware beta and Replay Studio stability before new features.')
        self.assertIsNone(self.memory.remember_from_message('Did you remember this priority?'))


if __name__=='__main__':unittest.main()
