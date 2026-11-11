import json
import os
from pathlib import Path
import sys
import uuid
import types
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from breastcare_agent.api import explain, install, AgentRequest
from breastcare_agent.retrieval import Retriever

FEATURES = ['mean radius','mean texture','mean concavity'] + ['feature '+str(i) for i in range(27)]
DATA = pd.DataFrame(np.arange(240).reshape(8,30)/100,columns=FEATURES)
DATA['malignant'] = [0,0,0,0,1,1,1,1]

def infer(rows):
    return [{'malignant_probability':float(1/(1+np.exp(-sum(row)/30))), 'prediction':'Ác tính','prediction_code':'malignant'} for row in rows]

class FakeResponses:
    def __init__(self, mode='valid'):
        self.mode = mode
        self.calls = []
    def create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls)==1:
            item = types.SimpleNamespace(type='function_call',name='search_guidelines',arguments='{"query":"breast cancer nuclei radius"}',call_id='call1')
            item.model_dump=lambda **kw: {'type':'function_call','name':item.name,'arguments':item.arguments,'call_id':item.call_id}
            return types.SimpleNamespace(output=[item],output_text='')
        source = 'S111111111111' if self.mode=='valid' else 'S999999999999'
        answer = {'answer':'Nhân tế bào, không phải kích thước u ['+source+'].', 'citations':[source], 'limitations':['Không phải chẩn đoán.'],'missing_data':['Mô bệnh học']}
        return types.SimpleNamespace(output=[],output_text=json.dumps(answer))

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path.cwd()/('test_tmp_'+uuid.uuid4().hex)
        self.tmp.mkdir()
        self.path = self.tmp/'corpus.json'
        self.path.write_text(json.dumps([{'id':'S111111111111','title':'Nuclear features','text':'WDBC breast cancer cell nuclei radius texture concavity definitions.', 'source':'https://example.org/reference','version':'test only','page':1}]),encoding='utf-8')
    def tearDown(self):
        self.path.unlink(missing_ok=True)
        self.tmp.rmdir()
    def test_retrieval_and_missing_corpus(self):
        r = Retriever(self.path)
        self.assertTrue(r.search('bán kính tế bào'))
        self.assertEqual(Retriever(self.tmp/'missing').search('test'),[])
    def test_sensitivity_has_30_finite_features(self):
        row = [1.5]*30
        result = explain(row,FEATURES,DATA,infer)
        self.assertEqual(len(result['features']),30)
        self.assertTrue(all(np.isfinite(x['delta_probability']) for x in result['features']))
        self.assertEqual(row,[1.5]*30)
    def client(self, mode='valid'):
        fake = FakeResponses(mode)
        module = types.SimpleNamespace(OpenAI=lambda **kw: types.SimpleNamespace(responses=fake))
        record = types.SimpleNamespace(inputs_json=json.dumps([[1.5]*30]), results_json=json.dumps(infer([[1.5]*30])))
        def owned(hid,sid):
            if hid!='owned' or sid!='session': raise HTTPException(404,'Not owned')
            return record
        app = FastAPI()
        with patch('breastcare_agent.api.Retriever',lambda p: Retriever(self.path)):
            install(app,owned,lambda s:s,FEATURES,DATA,infer)
        endpoint = next(route.endpoint for route in app.routes if route.path == '/api/agent/chat')
        return endpoint,fake,module
    def request(self, client, **changes):
        data = dict(history_id='owned',sample_index=0,question='Tại sao bán kính tế bào nhỏ?',consent=True)
        data.update(changes)
        try:
            result = client(AgentRequest(**data), x_session_id='session')
            return types.SimpleNamespace(status_code=200,text=json.dumps(result),json=lambda:result)
        except HTTPException as e:
            return types.SimpleNamespace(status_code=e.status_code,text=e.detail)
    def test_tools_and_citations(self):
        client,fake,module = self.client()
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-not-real'}),patch.dict(sys.modules,{'openai':module}):
            response = self.request(client)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['sources'][0]['id'],'S111111111111')
        self.assertEqual(len(fake.calls),2)
        self.assertFalse(fake.calls[0]['store'])
        self.assertEqual(len(response.json()['sensitivity']['features']),30)
    def test_fabricated_citation_rejected(self):
        client,fake,module = self.client('invalid')
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test'}),patch.dict(sys.modules,{'openai':module}):
            self.assertEqual(self.request(client).status_code,422)
    def test_other_case_consent_and_index_blocked_before_ai(self):
        client,fake,module = self.client()
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test'}),patch.dict(sys.modules,{'openai':module}):
            self.assertEqual(self.request(client,history_id='someone-else').status_code,404)
            self.assertEqual(self.request(client,sample_index=1).status_code,400)
            self.assertEqual(self.request(client,consent=False).status_code,400)
        self.assertFalse(fake.calls)
    def test_missing_key(self):
        client,_,_ = self.client()
        with patch.dict(os.environ,{},clear=True):
            self.assertEqual(self.request(client).status_code,503)

if __name__=='__main__':
    unittest.main()
