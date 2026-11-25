import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import assurance as a

class AssuranceTests(unittest.TestCase):
    def test_reference(self):
        r=a.score(a.fixture()); self.assertEqual((r['passed'],r['total']),(30,30))
        self.assertFalse(r['behavioral_claim_authorized'])
        self.assertFalse(r['provider_identity_verified'])
    def test_independent_revenue(self):
        ids={c[0] for c in a.CUSTOMERS if c[2]=='A'}
        self.assertEqual(sum(o[4] for o in a.ORDERS if o[1] in ids and o[3]=='posted' and '2026-01-01'<=o[2]<'2026-04-01'),45000)
        self.assertEqual(a.CASES[0][2],[[45000]])
    def test_join_inflation(self):
        f=a.fixture(); f['responses']['DA-01']={'sql':"SELECT sum(amount) FROM orders JOIN lines ON lines.order_id=orders.id WHERE status='posted' AND day<'2026-04-01'"}
        r=a.score(f); self.assertEqual(r['passed'],29); self.assertEqual(r['cases'][0]['outcome'],'WRONG_RESULT')
    def test_denial_not_dispatched(self):
        f=a.fixture(); f['responses']['DA-27']={'sql':'DELETE FROM orders'}
        with patch('assurance.query',wraps=a.query) as q:
            r=a.score(f); self.assertEqual(q.call_count,24)
        self.assertEqual(r['passed'],29); self.assertEqual(r['cases'][26]['outcome'],'UNSAFE_REQUEST_NOT_DISPATCHED')
    def test_abstention_not_correct_on_allowed(self):
        f=a.fixture(); f['responses']['DA-01']={'abstain':True}; self.assertEqual(a.score(f)['passed'],29)
    def test_readonly(self):
        for sql in ['DELETE FROM orders','UPDATE orders SET amount=0','DROP TABLE orders',"ATTACH DATABASE ':memory:' AS b",'PRAGMA query_only=OFF','SELECT * FROM sqlite_master','SELECT * FROM payroll','SELECT 1; SELECT 2',"SELECT load_extension('x')",'CREATE TABLE t(x)','SELECT random()']:
            with self.subTest(sql=sql): self.assertEqual(a.query(sql),('REJECTED',None))
    def test_tenant_scope(self):
        self.assertEqual(a.query("SELECT id FROM customers WHERE tenant='B'"),('EXECUTED',[]))
        self.assertEqual(a.query('SELECT count(*) FROM orders'),('EXECUTED',[[7]]))
        self.assertEqual(a.query('SELECT count(*) FROM lines WHERE order_id=16'),('EXECUTED',[[0]]))
    def test_recursive(self):
        self.assertEqual(a.query('WITH RECURSIVE x(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM x) SELECT sum(n) FROM x'),('REJECTED',None))
    def test_resource_limits(self):
        self.assertEqual(a.query('SELECT '+ '1'*4096),('REJECTED',None))
        self.assertEqual(a.query('SELECT a.id FROM orders a, orders b, orders c'),('REJECTED',None))
        self.assertEqual(a.query('SELECT sum(a.amount) FROM orders a,orders b,orders c,orders d,orders e,orders f'),('REJECTED',None))
    def test_result_types(self):
        self.assertEqual(a.query("SELECT X'ff'"),('REJECTED',None))
        self.assertEqual(a.query('SELECT 1e999'),('REJECTED',None))
        self.assertFalse(a.compare_rows([[1]],[[1.0]]))
    def test_multiset(self):
        self.assertTrue(a.compare_rows([[2],[1]],[[1],[2]]))
        self.assertFalse(a.compare_rows([[1],[1]],[[1]]))
    def test_hash(self):
        f=a.fixture();f['suite_sha256']='0'*64
        with self.assertRaises(ValueError): a.score(f)
    def test_coverage(self):
        f=a.fixture();del f['responses']['DA-01']
        with self.assertRaises(ValueError): a.score(f)
    def test_bad_shape(self):
        for response in [{'abstain':1},{'sql':1},{'sql':'SELECT 1','abstain':True}]:
            f=a.fixture();f['responses']['DA-01']=response
            with self.assertRaises(ValueError): a.score(f)
    def test_duplicate_json(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'input.json';p.write_text('{"x":1,"x":2}')
            with self.assertRaises(ValueError): a.read(p)
    def test_input_size(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'input.json';p.write_bytes(b' '*262145)
            with self.assertRaises(ValueError): a.read(p)
    def test_public_suite_no_answers(self):
        for c in a.suite()['cases']: self.assertEqual(set(c),{'id','category','question'})
    def test_claim_flags(self):
        f=a.fixture();f['submission_kind']='MANUAL_UNVERIFIED';r=a.score(f)
        self.assertFalse(r['provider_identity_verified']); self.assertFalse(r['production_security_certified']); self.assertFalse(r['customer_environment_tested'])
