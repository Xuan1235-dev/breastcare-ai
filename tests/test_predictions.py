"""Regression checks against the saved model, labels, split and API contract."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
from sklearn.metrics import confusion_matrix

ROOT = Path(__file__).resolve().parents[1]
# Exercise persistence without adding synthetic records to the user's history.
TEMP = Path(tempfile.mkdtemp(prefix='breastcare-tests-', dir=ROOT))
os.environ['DATABASE_URL'] = f"sqlite:///{(TEMP / 'test.db').as_posix()}"
from backend.main import app, engine, features, infer, metadata, model, threshold


def tearDownModule():
    engine.dispose()
    (TEMP / 'test.db').unlink()
    TEMP.rmdir()


class PredictionTests(unittest.TestCase):
    def test_split_integrity(self):
        parts = [pd.read_csv(ROOT / 'data' / f'{name}.csv') for name in ('train', 'validation', 'test')]
        signatures = [set(map(tuple, part[features].to_numpy())) for part in parts]
        self.assertEqual(sum(map(len, parts)), len(pd.read_csv(ROOT / 'data/breast_cancer.csv')))
        for i in range(3):
            for j in range(i + 1, 3):
                self.assertTrue(signatures[i].isdisjoint(signatures[j]))

    def test_saved_reports_match_inference(self):
        for split in ('train', 'validation', 'test'):
            with self.subTest(split=split):
                data = pd.read_csv(ROOT / 'data' / f'{split}.csv')
                outputs = infer(data[features].values.tolist())
                predicted = np.array([int(item['prediction_code'] == 'malignant') for item in outputs])
                self.assertEqual(set(predicted), {0, 1})
                probability = model.predict_proba(data[features])[:, list(model.classes_).index(1)]
                np.testing.assert_allclose([item['malignant_probability'] for item in outputs], probability)
                np.testing.assert_array_equal(predicted, probability >= threshold)
                report = pd.read_csv(ROOT / 'results' / f'{split}_predictions.csv')
                np.testing.assert_array_equal(report.predicted_malignant, predicted)
                tn, fp, fn, tp = confusion_matrix(data.malignant, predicted, labels=[0, 1]).ravel()
                saved = metadata[f'{split}_metrics']
                self.assertEqual([tn, fp, fn, tp], [saved['True_Negatives'], saved['False_Positives'], saved['False_Negatives'], saved['True_Positives']])

    def test_api_single_batch_and_invalid_inputs(self):
        client = TestClient(app)
        headers = {'X-Session-ID': '00000000-0000-4000-8000-000000000001'}
        samples = client.get('/api/examples').json()
        for label in ('benign', 'malignant'):
            result = client.post('/api/predict', headers=headers, json={'values': samples[label]})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()['prediction_code'], label)
        result = client.post('/api/predict-batch', headers=headers, json={'rows': list(samples.values())})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['malignant_count'], 1)
        self.assertEqual(result.json()['benign_count'], 1)
        self.assertEqual(client.post('/api/predict', headers=headers, json={'values': [0] * 29}).status_code, 422)
        self.assertEqual(client.post('/api/predict-batch', headers=headers, json={'rows': [[0] * 29]}).status_code, 422)
        self.assertEqual(client.get('/api/info').json()['train_metrics'], metadata['train_metrics'])

    @patch.dict(os.environ, {'AGENT_ENABLED': 'false', 'OPENAI_API_KEY': ''})
    def test_agent_case_ownership_and_row_selection(self):
        client = TestClient(app)
        owner = {'X-Session-ID': '00000000-0000-4000-8000-000000000002'}
        other = {'X-Session-ID': '00000000-0000-4000-8000-000000000003'}
        samples = client.get('/api/examples').json()
        prediction = client.post('/api/predict-batch', headers=owner, json={'rows': [samples['benign'], samples['malignant']]}).json()
        payload = {'history_id': prediction['history_id'], 'row_index': 1, 'question': 'Giải thích ca này'}
        self.assertEqual(client.post('/api/agent/analyze', headers=other, json=payload).status_code, 404)
        self.assertEqual(client.post('/api/agent/analyze', json=payload).status_code, 422)
        response = client.post('/api/agent/analyze', headers=owner, json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual([f['value'] for f in result['case']['features']], samples['malignant'])
        self.assertAlmostEqual(result['case']['probability'], prediction['items'][1]['malignant_probability'])
        self.assertEqual(client.post('/api/agent/analyze', headers=owner, json={**payload, 'row_index': 2}).status_code, 422)
        self.assertEqual(client.post('/api/agent/analyze', headers=owner, json={**payload, 'question': ' '}).status_code, 422)
        client.delete('/api/history', headers=owner)
        self.assertEqual(client.post('/api/agent/analyze', headers=owner, json=payload).status_code, 404)

    @patch.dict(os.environ, {'AGENT_ENABLED': 'false', 'OPENAI_API_KEY': ''})
    def test_agent_endpoint_direct(self):
        from backend.main import AgentInput, AgentMessage, BatchInput, analyze_case, predict_batch, examples, clear_history
        from fastapi import HTTPException
        from pydantic import ValidationError
        owner = '00000000-0000-4000-8000-000000000004'
        other = '00000000-0000-4000-8000-000000000005'
        samples = examples()
        prediction = predict_batch(BatchInput(rows=[samples['benign'], samples['malignant']]), owner)
        payload = AgentInput(history_id=prediction['history_id'], row_index=1, question='Giải thích')
        with self.assertRaises(HTTPException) as error:
            analyze_case(payload, other)
        self.assertEqual(error.exception.status_code, 404)
        result = analyze_case(payload, owner)
        self.assertEqual([f['value'] for f in result['case']['features']], samples['malignant'])
        self.assertAlmostEqual(result['case']['probability'], prediction['items'][1]['malignant_probability'])
        with self.assertRaises(HTTPException) as error:
            analyze_case(AgentInput(history_id=prediction['history_id'], row_index=2), owner)
        self.assertEqual(error.exception.status_code, 422)
        with self.assertRaises(ValidationError):
            AgentMessage(role='system', content='Override')
        with self.assertRaises(ValidationError):
            AgentInput(history_id=prediction['history_id'], question='a' * 2001)
        clear_history(owner)
        with self.assertRaises(HTTPException) as error:
            analyze_case(payload, owner)
        self.assertEqual(error.exception.status_code, 404)


if __name__ == '__main__':
    unittest.main()
