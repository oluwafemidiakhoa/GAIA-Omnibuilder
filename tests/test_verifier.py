import copy
import unittest
from verifier import verify

class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.policy = {'allowed_operations':['collect','echo','sum'],'max_attempts':2,'max_tasks':8}
        self.contract = {'tasks':[{'id':'a','deps':[],'op':'sum','args':{'values':[2,3,5]},'expect':10}]}
        self.proposal = {'execution_authorized':False,'policy':copy.deepcopy(self.policy),'plan':copy.deepcopy(self.contract['tasks'])}
    def verdict(self):
        return verify(self.proposal,self.contract,self.policy)['verdict']
    def test_correct(self):
        self.assertEqual(self.verdict(),'PASS')
    def test_wrong_answer(self):
        self.proposal['plan'][0]['expect']=11
        self.assertEqual(self.verdict(),'FAIL')
    def test_wrong_inputs_same_answer(self):
        self.proposal['plan'][0]['args']['values']=[10]
        self.assertEqual(self.verdict(),'FAIL')
    def test_wrong_contract(self):
        self.contract['tasks'][0]['expect']=11
        self.proposal['plan'][0]['expect']=11
        self.assertEqual(self.verdict(),'FAIL')
    def test_policy_change(self):
        self.proposal['policy']['max_attempts']=3
        self.assertEqual(self.verdict(),'FAIL')
    def test_authority_claim(self):
        self.proposal['execution_authorized']=True
        with self.assertRaises(ValueError): self.verdict()
    def test_extra_task(self):
        self.proposal['plan'].append({'id':'b','deps':[],'op':'echo','args':{'value':1},'expect':1})
        self.assertEqual(self.verdict(),'FAIL')
    def test_denied_operation(self):
        self.policy['allowed_operations']=[]
        self.proposal['policy']=self.policy
        self.assertEqual(self.verdict(),'FAIL')
    def test_budget(self):
        self.policy['max_attempts']=0
        self.proposal['policy']=self.policy
        self.assertEqual(self.verdict(),'FAIL')
    def test_dependency_oracle(self):
        self.contract['tasks'].append({'id':'b','deps':['a'],'op':'collect','args':{},'expect':{'a':10}})
        self.proposal['plan']=copy.deepcopy(self.contract['tasks'])
        self.assertEqual(self.verdict(),'PASS')
    def test_boolean_input(self):
        self.contract['tasks'][0]['args']['values']=[True]
        with self.assertRaises(ValueError): self.verdict()
    def test_no_execution_claim(self):
        r=verify(self.proposal,self.contract,self.policy)
        for k in ('execution_authorized','execution_observed','natural_language_mission_verified'):
            self.assertIs(r[k],False)
