"""Agent regression tests: evidence, isolation, retrieval and bounded tool calls."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from backend.agent import CaseAgent, KnowledgeBase


class AgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import joblib
        root = Path(__file__).resolve().parents[1]
        metadata = json.loads((root / 'models/metadata.json').read_text(encoding='utf-8'))
        cls.agent = CaseAgent(joblib.load(root / 'models/best_model.joblib'), metadata['feature_names'], metadata['threshold'])
        cls.values = pd.read_csv(root / 'data/test.csv')[cls.agent.features].iloc[0].tolist()

    def test_actual_model_sensitivity(self):
        before = self.values.copy()
        for item in self.agent.sensitivity(self.values):
            changed = self.values.copy()
            changed[self.agent.features.index(item['feature'])] = item['train_median']
            expected = (self.agent.probability([self.values])[0] - self.agent.probability([changed])[0]) * 100
            self.assertAlmostEqual(item['delta_percentage_points'], expected)
        self.assertEqual(before, self.values)
        self.assertEqual(len(self.agent.inspect(self.values)['features']), 30)

    def test_retrieval_and_empty_corpus(self):
        docs = self.agent.knowledge.search('độ lõm nhân tế bào concavity radius')
        self.assertTrue(any(doc['id'].startswith('uci-wdbc') for doc in docs))
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as directory:
            self.assertEqual(KnowledgeBase(directory).search('HER2'), [])

    @patch.dict(os.environ, {'AGENT_ENABLED': 'false', 'OPENAI_API_KEY': ''})
    def test_offline_never_calls_provider(self):
        with patch('backend.agent.urlopen') as network:
            result = self.agent.run(self.values, 'Vì sao kích thước nhỏ nhưng ác tính?')
        network.assert_not_called()
        self.assertEqual(result['mode'], 'local')
        source_ids = {s['id'] for s in result['sources']}
        self.assertTrue(source_ids)
        self.assertTrue(all(set(p['source_ids']) <= source_ids for p in result['paragraphs']))

    @patch.dict(os.environ, {'AGENT_ENABLED': 'true', 'OPENAI_API_KEY': 'test-key'})
    def test_llm_calls_tool_and_validates_sources(self):
        class Response:
            def __init__(self, message): self.message = message
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, *args): return json.dumps({'choices': [{'message': self.message}]}).encode()
        messages = [Response({'role': 'assistant', 'content': None, 'tool_calls': [
            {'id': 'call_1', 'type': 'function', 'function': {'name': 'search_guidelines', 'arguments': '{"query":"ER PR HER2 điều trị"}'}}]}),
            Response({'role': 'assistant', 'content': json.dumps({'paragraphs': [
                {'text': 'Cần thông tin ER, PR, HER2 để thảo luận điều trị.', 'source_ids': ['nci-pdq-1']}]})})]
        with patch('backend.agent.urlopen', side_effect=messages) as network:
            result = self.agent.run(self.values, 'Cần thông tin gì?')
        self.assertEqual(result['mode'], 'llm')
        self.assertEqual(network.call_count, 2)
        second_payload = json.loads(network.call_args_list[1].args[0].data)
        self.assertTrue(any(m['role'] == 'tool' for m in second_payload['messages']))
        self.assertEqual(second_payload['messages'][-1]['tool_call_id'], 'call_1')
        bad = Response({'content': json.dumps({'paragraphs': [{'text': 'Sai nguồn', 'source_ids': ['invented-nccn']} ]})})
        with patch('backend.agent.urlopen', side_effect=[messages[0], bad]):
            self.assertEqual(self.agent.run(self.values, 'Phân tích')['mode'], 'fallback')

    @patch.dict(os.environ, {'AGENT_ENABLED': 'false'})
    def test_out_of_distribution_warning(self):
        values = self.values.copy()
        values[0] = float(self.agent.train.iloc[:, 0].max()) * 100
        result = self.agent.run(values, 'Phân tích')
        self.assertTrue(result['case']['features'][0]['outside_train_range'])
        self.assertIn('ngoài khoảng', result['paragraphs'][0]['text'])

    @patch.dict(os.environ, {'AGENT_ENABLED': 'true', 'OPENAI_API_KEY': 'test-key'})
    def test_tool_loop_is_bounded(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, *args):
                return json.dumps({'choices': [{'message': {'role': 'assistant', 'content': None,
                    'tool_calls': [{'id': 'repeat', 'type': 'function', 'function': {
                        'name': 'inspect_case', 'arguments': '{}'}}]}}]}).encode()
        with patch('backend.agent.urlopen', return_value=Response()) as network:
            result = self.agent.run(self.values, 'Phân tích')
        self.assertEqual(network.call_count, 5)
        self.assertEqual(result['mode'], 'fallback')

    @patch.dict(os.environ, {'AGENT_ENABLED': 'true', 'OPENAI_API_KEY': 'test-key'})
    def test_provider_failure_falls_back(self):
        with patch('backend.agent.urlopen', side_effect=TimeoutError('secret-provider-error')):
            result = self.agent.run(self.values, 'Giải thích')
        self.assertEqual(result['mode'], 'fallback')
        self.assertNotIn('secret-provider-error', json.dumps(result))

