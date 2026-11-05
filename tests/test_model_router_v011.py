"""No network traffic: validate external/local authorization, routing and budget gates."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from companion.model_router import (Route, detect_task, routes_for, provider_ready,
                                    text_completion, LOCAL_PROVIDERS)
from companion.assistant import CompanionBrain
from companion.costs import SpendLedger
from companion.settings import DEFAULTS


class MultiProviderRouterTests(unittest.TestCase):
    def settings(self, **kw):
        return {**DEFAULTS, **kw}

    def test_automatic_task_selection(self):
        self.assertEqual(detect_task('Write a 15 second Instagram Reel script'), 'planning')
        self.assertEqual(detect_task('Fix the Unity C# compile error'), 'coding')
        self.assertEqual(detect_task('Analyze marketing conversion metrics'), 'analysis')
        self.assertEqual(detect_task('How is your day?'), 'conversation')
        self.assertEqual(detect_task('And can we do that?', 'coding'), 'coding')

    def test_major_and_many_minor_providers_disabled_by_default(self):
        for name in ('anthropic','deepseek','openrouter','groq','huggingface','mistral',
                     'together','fireworks','cerebras','deepinfra','ollama','unfiltered_local'):
            self.assertFalse(provider_ready(name, self.settings(), {name.upper()+'_API_KEY':'test'}))

    def test_cloud_needs_explicit_opt_in_model_and_price(self):
        env={'GROQ_API_KEY':'test-groq'}
        s=self.settings(allow_external_ai_providers=True, enabled_ai_providers=['groq'])
        self.assertTrue(provider_ready('groq', s, env))
        self.assertEqual(routes_for('conversation', s, env), [])
        s['model_rates_usd_per_million']={'groq:openai/gpt-oss-20b':[0.11,0.50]}
        self.assertEqual(routes_for('conversation', s, env)[0].provider,'groq')
        self.assertEqual(routes_for('coding', s, env)[0].provider,'groq')
        self.assertEqual(routes_for('coding', s, env, require_tools=True),[])

    def test_task_specific_model(self):
        env={'GROQ_API_KEY':'test'}
        s=self.settings(allow_external_ai_providers=True,enabled_ai_providers=['groq'],
                        provider_task_models={'groq':{'coding':'openai/gpt-oss-120b'}},
                        model_rates_usd_per_million={'groq:openai/gpt-oss-20b':[.1,.4],
                                                     'groq:openai/gpt-oss-120b':[.2,.5]})
        self.assertEqual(routes_for('coding',s,env)[0].model,'openai/gpt-oss-120b')
        self.assertEqual(routes_for('conversation',s,env)[0].model,'openai/gpt-oss-20b')

    def test_local_unfiltered_is_opt_in_and_loopback_only(self):
        s=self.settings(allow_local_ai=True,enabled_local_ai_providers=['unfiltered_local'])
        candidates=routes_for('conversation',s,{})
        self.assertEqual(candidates[0].model,'UnfilteredAI/UNfilteredAI-1B')
        for url in ('http://evil.test:8000/v1/chat/completions',
                    'http://127.0.0.1:8000/secret',
                    'https://127.0.0.1:8000/v1/chat/completions',
                    'http://localhost.evil:8000/v1/chat/completions'):
            s['local_ai_urls']={'unfiltered_local':url}
            self.assertFalse(provider_ready('unfiltered_local',s,{}))
        s['local_ai_urls']={'unfiltered_local':'http://127.0.0.1:8000/v1/chat/completions'}
        self.assertTrue(provider_ready('unfiltered_local',s,{}))

    def test_local_model_has_no_cloud_key_and_bounded_context(self):
        route=Route('unfiltered_local','UnfilteredAI/UNfilteredAI-1B','conversation')
        s=self.settings(allow_local_ai=True,enabled_local_ai_providers=['unfiltered_local'])
        captured=[]
        def fake(url,body,headers,timeout=45):
            captured.append((url,body,headers))
            return {'choices':[{'message':{'content':'Hello'}}]}
        with patch('companion.model_router._post_json',side_effect=fake):
            result=text_completion(route,'Private long prompt'*500,
                [{'role':'user','content':'Hello'*2000}],1000,settings=s,environ={})
        self.assertEqual(result.output_text,'Hello')
        self.assertNotIn('Authorization',captured[0][2])
        self.assertLessEqual(captured[0][1]['max_tokens'],256)
        self.assertLessEqual(len(captured[0][1]['messages'][0]['content']),900)

    def test_cloud_no_network_mock_and_no_tool_authority(self):
        route=Route('groq','openai/gpt-oss-20b','conversation')
        s=self.settings(allow_external_ai_providers=True,enabled_ai_providers=['groq'],
                        model_rates_usd_per_million={'groq:openai/gpt-oss-20b':[.1,.5]})
        calls=[]
        def fake(url,body,headers,timeout=45):
            calls.append((url,body,headers))
            return {'choices':[{'message':{'content':'Text reply'}}],
                    'usage':{'prompt_tokens':50,'completion_tokens':20}}
        with patch('companion.model_router._post_json',side_effect=fake):
            result=text_completion(route,'Follow the user',[{'role':'user','content':'Hi'}],512,
                                   settings=s,environ={'GROQ_API_KEY':'testing'})
        self.assertEqual(result.usage.output_tokens,20)
        self.assertTrue(calls[0][0].startswith('https://api.groq.com/'))
        self.assertNotIn('tools',calls[0][1])

    def test_rate_limit_falls_back_to_authorized_minor_model(self):
        settings=self.settings(allow_external_ai_providers=True, enabled_ai_providers=['groq'],
                model_rates_usd_per_million={'groq:openai/gpt-oss-20b':[.1,.5]})
        with tempfile.TemporaryDirectory() as folder:
            brain=CompanionBrain(settings,SpendLedger(Path(folder)/'costs.sqlite3'))
            def failed(**kw):
                raise SimpleFake429()
            brain._client=SimpleNamespace(responses=SimpleNamespace(create=failed))
            with patch.dict(os.environ,{'OPENAI_API_KEY':'test','GROQ_API_KEY':'test'},clear=True), \
                 patch('companion.assistant.text_completion',return_value=SimpleNamespace(
                     status='completed',output_text='Groq replied',output=[],
                     usage=SimpleNamespace(input_tokens=30,output_tokens=10))):
                answer,cost,model=brain.ask('Hello',voice_mode='general')
            self.assertEqual(answer,'Groq replied')
            self.assertTrue(model.startswith('groq/'))
            self.assertGreater(cost,0)
            self.assertEqual(brain.ledger.today_count(),1)


class SimpleFake429(Exception):
    status_code=429
    def __str__(self): return '429 limit reached'


if __name__=='__main__': unittest.main()
