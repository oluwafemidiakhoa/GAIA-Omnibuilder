import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
import assurance
import studio
import studio_lab


class StudioLabTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        lib = studio.Library(studio.ROOT/'skills', Path(self.tmp.name)/'drafts')
        self.server = ThreadingHTTPServer(('127.0.0.1',0),studio.handler(lib,'token'))
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.base = 'http://127.0.0.1:'+str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); self.tmp.cleanup()

    def post(self, path, values, origin=None):
        data = urllib.parse.urlencode(values).encode()
        return urllib.request.urlopen(urllib.request.Request(self.base+path,data=data,headers={'Origin':origin or self.base}))

    def manual(self):
        fixture = assurance.fixture()
        fixture['submission_kind'] = 'MANUAL_UNVERIFIED'
        return json.dumps(fixture)

    def test_navigation_and_manifest(self):
        with urllib.request.urlopen(self.base+'/') as r:
            self.assertIn(b'Assurance Laboratory',r.read())
        with urllib.request.urlopen(self.base+'/lab') as r:
            self.assertIn(b'Run demonstration',r.read())
        with urllib.request.urlopen(self.base+'/lab/manifest') as r:
            self.assertEqual(json.load(r)['protocol']['n'],30)

    def test_demo(self):
        with self.post('/lab/demo',{'token':'token','download':'1'}) as r:
            self.assertIn('attachment',r.headers['Content-Disposition']); report=json.load(r)
        self.assertEqual(report['reference']['passed'],30)
        self.assertEqual(report['defective']['passed'],28)
        self.assertFalse(report['behavioral_claim_authorized'])

    def test_demo_html(self):
        with self.post('/lab/demo',{'token':'token'}) as r:
            self.assertIn(b'Synthetic demonstration',r.read())

    def test_compare(self):
        raw=self.manual()
        with self.post('/lab/compare',{'token':'token','provider':'Test','model':'Synthetic test only','baseline':raw,'assisted':'```json\n'+raw+'\n```','download':'1'}) as r:
            report=json.load(r)
        self.assertEqual(report['ties'],30)
        self.assertFalse(report['behavioral_claim_authorized'])

    def test_invalid_json_and_fixture(self):
        for raw in ('{}','{"a":1,"a":2}',json.dumps(assurance.fixture())):
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                self.post('/lab/compare',{'token':'token','provider':'Test','model':'Test','baseline':raw,'assisted':self.manual()})
            self.assertEqual(ctx.exception.code,400)

    def test_origin_and_token(self):
        for token,origin in [('wrong',self.base),('token','https://evil.example')]:
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                self.post('/lab/demo',{'token':token},origin)
            self.assertEqual(ctx.exception.code,403)

    def test_parser(self):
        self.assertEqual(studio_lab.parse_response('\ufeff{"x":1}'),{'x':1})
        for raw in ('{"x":NaN}','{"x":1,"x":2}','x'*262145):
            with self.assertRaises(ValueError): studio_lab.parse_response(raw)

    def test_escape_model(self):
        raw=self.manual()
        with self.post('/lab/compare',{'token':'token','provider':'Test','model':'<script>alert(1)</script>','baseline':raw,'assisted':raw}) as r:
            html=r.read()
        self.assertNotIn(b'<script>',html)
        self.assertIn(b'&lt;script&gt;',html)

    def test_local_disabled_route(self):
        from unittest.mock import patch
        with patch('studio_local.enabled',return_value=False), self.assertRaises(urllib.error.HTTPError) as ctx:
            self.post('/lab/local',{'token':'token','model':'test:latest'})
        self.assertEqual(ctx.exception.code,400)

    def test_local_route_mock(self):
        from unittest.mock import patch
        report=studio_lab.evaluate_manual(self.manual(),self.manual(),'Test','Test')
        report['mode']='LOCAL_RUNTIME_UNVERIFIED'
        with patch('studio_local.compare',return_value=report) as run:
            with self.post('/lab/local',{'token':'token','model':'test:latest'}) as r:
                self.assertIn(b'Download evidence JSON',r.read())
            run.assert_called_once()
