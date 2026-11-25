import json, unittest
from unittest.mock import patch
import planner

P={'allowed_operations':['sum'],'max_attempts':1,'max_tasks':2}
class PlannerTests(unittest.TestCase):
    def test_mock(self):
        r=planner.propose('Add 2, 3, 5',['architecture'],P)
        self.assertFalse(r['execution_authorized']); self.assertEqual(r['plan'][0]['expect'],10); self.assertEqual(len(r['specialists']),1)
    def test_network_optin(self):
        with self.assertRaises(ValueError): planner.propose('x',[],P,'openai','model')
    def test_missing(self):
        with self.assertRaises(ValueError): planner.propose('x',['quantum-hardware'],P)
    def test_budget(self):
        with self.assertRaises(ValueError): planner.propose('x',[],P,tokens=True)
    def test_denied(self):
        with self.assertRaises(ValueError): planner.propose('x',[],{'allowed_operations':['echo'],'max_attempts':1,'max_tasks':1})
    def test_duplicate(self):
        with patch('planner.request',return_value=('[{"id":"a","id":"b"}]',{})):
            with self.assertRaises(ValueError): planner.propose('x',[],P)
    def test_unregistered(self):
        with patch('planner.request',return_value=(json.dumps([{'id':'a','deps':[],'op':'shell','args':{},'expect':0}]),{})):
            with self.assertRaises(ValueError): planner.propose('x',[],P)
    def test_openai_contract(self):
        def send(url, headers, payload):
            self.assertEqual(url,'https://api.openai.com/v1/responses'); self.assertFalse(payload['store']); self.assertEqual(payload['max_output_tokens'],512)
            return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'[]'}]}]}
        with patch.dict('os.environ',{'OPENAI_API_KEY':'test'}): self.assertEqual(planner.request('openai','test','x',512,send)[0],'[]')
    def test_anthropic_contract(self):
        def send(url, headers, payload):
            self.assertEqual(url,'https://api.anthropic.com/v1/messages'); self.assertEqual(payload['max_tokens'],512)
            return {'stop_reason':'end_turn','content':[{'type':'text','text':'[]'}]}
        with patch.dict('os.environ',{'ANTHROPIC_API_KEY':'test'}): self.assertEqual(planner.request('anthropic','test','x',512,send)[0],'[]')
    def test_incomplete(self):
        with patch.dict('os.environ',{'OPENAI_API_KEY':'test'}):
            with self.assertRaises(ValueError): planner.request('openai','test','x',512,lambda *a:{'status':'incomplete'})
