import json
import os
import unittest
from unittest.mock import patch
import assurance
import studio_lab
import studio_local

MODEL = 'test-model:latest'
DIGEST = 'a'*64
TAGS = {'models':[{'name':MODEL,'digest':DIGEST,'size':100}]}
ENV = {'GAIA_ENABLE_LOCAL_MODEL':'1','OLLAMA_NO_CLOUD':'1'}


def reply():
    submission = assurance.fixture()
    submission['submission_kind']='MANUAL_UNVERIFIED'
    return {'model':MODEL,'done':True,'done_reason':'stop','message':{'content':json.dumps(submission)},'eval_count':12}


class LocalTests(unittest.TestCase):
    def test_disabled(self):
        with patch.dict(os.environ,{'GAIA_ENABLE_LOCAL_MODEL':'0','OLLAMA_NO_CLOUD':'1'}), patch.object(studio_local,'request') as req:
            with self.assertRaises(ValueError): studio_local.compare(MODEL,studio_lab.parse_response)
            req.assert_not_called()

    def test_two_separate_requests(self):
        with patch.dict(os.environ,ENV), patch.object(studio_local,'request',side_effect=[TAGS,reply(),reply(),TAGS]) as req:
            report=studio_local.compare(MODEL,studio_lab.parse_response)
        self.assertEqual(report['mode'],'LOCAL_RUNTIME_UNVERIFIED')
        self.assertEqual(report['ties'],30)
        self.assertFalse(report['behavioral_claim_authorized'])
        self.assertFalse(report['local_only_configuration_independently_verified'])
        calls=req.call_args_list
        self.assertEqual([c.args[0] for c in calls],['/api/tags','/api/chat','/api/chat','/api/tags'])
        b,a=calls[1].args[1],calls[2].args[1]
        self.assertEqual(len(b['messages']),1); self.assertEqual(len(a['messages']),1)
        self.assertEqual(b['options'],a['options']); self.assertNotEqual(b['messages'],a['messages'])
        self.assertEqual(report['local_model_digest_reported'],DIGEST)

    def test_cloud_and_unknown_models(self):
        with patch.dict(os.environ,ENV), patch.object(studio_local,'request',return_value=TAGS) as req:
            for name in ('model-cloud','https://bad','missing:latest'):
                with self.assertRaises(ValueError): studio_local.compare(name,studio_lab.parse_response)
            self.assertEqual(req.call_count,1)

    def test_incomplete_no_retry(self):
        bad=reply();bad['done_reason']='length'
        with patch.dict(os.environ,ENV), patch.object(studio_local,'request',side_effect=[TAGS,bad]) as req:
            with self.assertRaises(ValueError): studio_local.compare(MODEL,studio_lab.parse_response)
            self.assertEqual(req.call_count,2)
        self.assertFalse(studio_local.RUN_LOCK.locked())

    def test_digest_changed(self):
        changed={'models':[{'name':MODEL,'digest':'b'*64,'size':100}]}
        with patch.dict(os.environ,ENV), patch.object(studio_local,'request',side_effect=[TAGS,reply(),reply(),changed]):
            with self.assertRaises(ValueError): studio_local.compare(MODEL,studio_lab.parse_response)

    def test_concurrent_rejected(self):
        studio_local.RUN_LOCK.acquire()
        try:
            with patch.dict(os.environ,ENV), patch.object(studio_local,'request') as req:
                with self.assertRaises(ValueError): studio_local.compare(MODEL,studio_lab.parse_response)
                req.assert_not_called()
        finally: studio_local.RUN_LOCK.release()

    def test_fixed_loopback_no_redirect(self):
        with patch('studio_local.http.client.HTTPConnection') as cls:
            conn=cls.return_value;conn.getresponse.return_value.status=302
            with self.assertRaises(ValueError): studio_local.request('/api/tags')
            cls.assert_called_once_with('127.0.0.1',11434,timeout=120)
            conn.request.assert_called_once();conn.close.assert_called_once()
            with self.assertRaises(ValueError): studio_local.request('/api/pull',{})
            self.assertEqual(cls.call_count,1)
