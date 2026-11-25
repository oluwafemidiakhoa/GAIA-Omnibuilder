import unittest, tempfile
from pathlib import Path
from gaia import Runtime, validate

def task(id='a',deps=None,op='sum',args=None,expect=3):
    return dict(id=id,deps=deps or [],op=op,args={'values':[1,2]} if args is None else args,expect=expect)
class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.path=Path(self.tmp.name)/'project.db'; self.r=Runtime(self.path)
    def tearDown(self): self.r.db.close(); self.tmp.cleanup()
    def test_dag(self):
        self.r.init([task('b',['a'],'collect',{}, {'a':3}),task()]); self.assertEqual(self.r.run()['b']['status'],'PASS'); self.assertTrue(self.r.verify())
    def test_cycle(self):
        with self.assertRaises(ValueError): validate([task('a',['b']),task('b',['a'])])
    def test_unknown_dep(self):
        with self.assertRaises(ValueError): validate([task('a',['x'])])
    def test_duplicate(self):
        with self.assertRaises(ValueError): validate([task(),task()])
    def test_unknown_op(self):
        with self.assertRaises(ValueError): validate([task(op='shell')])
    def test_failure_blocks(self):
        self.r.init([task(expect=4),task('b',['a'])]); s=self.r.run(); self.assertEqual(s['a']['status'],'FAIL'); self.assertEqual(s['b']['status'],'PENDING')
    def test_restart(self):
        self.r.init([task()]); self.r.run(); self.r.db.close(); self.r=Runtime(self.path); self.r.run(); self.assertEqual(self.r.db.execute('select count(*) from ledger').fetchone()[0],2)
    def test_tamper_ledger(self):
        self.r.init([task()]); self.r.db.execute("update ledger set hash='x'"); self.r.db.commit(); self.assertFalse(self.r.verify()); self.assertRaises(ValueError,self.r.run)
    def test_tamper_state(self):
        self.r.init([task()]); self.r.db.execute("update tasks set status='PASS'"); self.r.db.commit(); self.assertFalse(self.r.verify())
    def test_invalid_args(self):
        self.r.init([task(args={'values':['1']})]); self.assertEqual(self.r.run()['a']['status'],'FAIL')
    def test_bool_not_integer(self):
        self.r.init([task(args={'values':[True]})]); self.assertEqual(self.r.run()['a']['status'],'FAIL')
    def test_no_reinitialize(self):
        self.r.init([task()]); self.assertRaises(ValueError,self.r.init,[task()])
