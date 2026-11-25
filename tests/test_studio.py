import hashlib, io, tempfile, threading, unittest, urllib.request, urllib.error, urllib.parse, zipfile
from pathlib import Path
from http.server import ThreadingHTTPServer
import studio
class StudioTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.lib=studio.Library(studio.ROOT/'skills',Path(self.tmp.name)/'drafts'); self.server=ThreadingHTTPServer(('127.0.0.1',0),studio.handler(self.lib,'token')); self.thread=threading.Thread(target=self.server.serve_forever,daemon=True); self.thread.start(); self.base=f'http://127.0.0.1:{self.server.server_port}'
    def tearDown(self): self.server.shutdown(); self.server.server_close(); self.thread.join(); self.tmp.cleanup()
    def get(self,p): return urllib.request.urlopen(self.base+p).read()
    def post(self,**changes):
        data=dict(token='token',name='sample-draft',description='Example',body='Test instructions'); data.update(changes)
        return urllib.request.urlopen(urllib.request.Request(self.base+'/new',data=urllib.parse.urlencode(data).encode(),headers={'Origin':self.base}))
    def test_catalog(self): self.assertEqual(len(self.lib.catalog()),22); self.assertIn(b'22 results',self.get('/'))
    def test_search(self): self.assertIn(b'0 results',self.get('/?q=zzzzzzzz'))
    def test_zip_hash(self):
        name='universal-builder-router'; b=self.get('/download/'+name); self.assertEqual(hashlib.sha256(b).hexdigest(),self.lib.get(name)[1]['archive_sha256']); self.assertIn(name+'/SKILL.md',zipfile.ZipFile(io.BytesIO(b)).namelist())
    def test_passport(self): self.assertIn(b'"execution_authorized":false',self.get('/passport/universal-builder-router'))
    def test_create_and_persist(self):
        with self.post() as r: self.assertEqual(r.status,201)
        self.assertEqual(len(self.lib.catalog()),23); self.assertIn(b'Test instructions',self.get('/skill/sample-draft'))
    def test_duplicate(self):
        with self.post(): pass
        with self.assertRaises(urllib.error.HTTPError) as e: self.post()
        self.assertEqual(e.exception.code,400)
    def test_token(self):
        with self.assertRaises(urllib.error.HTTPError) as e: self.post(token='wrong')
        self.assertEqual(e.exception.code,403)
    def test_origin(self):
        with self.assertRaises(urllib.error.HTTPError) as e: urllib.request.urlopen(urllib.request.Request(self.base+'/new',data=b'x'))
        self.assertEqual(e.exception.code,403)
    def test_escape(self):
        with self.post(body='<script>alert(1)</script>'): pass
        self.assertIn(b'&lt;script&gt;',self.get('/skill/sample-draft'))
    def test_invalid_name(self):
        with self.assertRaises(urllib.error.HTTPError): self.post(name='../escape')
    def test_host(self):
        with self.assertRaises(urllib.error.HTTPError) as e: urllib.request.urlopen(urllib.request.Request(self.base+'/',headers={'Host':'evil.example'}))
        self.assertEqual(e.exception.code,403)
