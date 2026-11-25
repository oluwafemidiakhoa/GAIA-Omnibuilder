import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

from controlled import (ControlledRuntime, OPERATIONS, MAX_NUMBER, MAX_FILE,
                        validate_policy, validate_plan, read_json)
from gaia import Runtime, canonical, digest
from registry import inventory


def task(id='a', deps=None, op='sum', args=None, expect=3):
    return {'id':id, 'deps':[] if deps is None else deps, 'op':op,
            'args':{'values':[1,2]} if args is None else args, 'expect':expect}


def policy(allowed=None, attempts=3, tasks=8):
    return {'allowed_operations':['sum','collect','echo'] if allowed is None else allowed,
            'max_attempts':attempts, 'max_tasks':tasks}


class ControlledTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)/'control.db'
        self.r = ControlledRuntime(self.path)

    def tearDown(self):
        self.r.close()
        self.tmp.cleanup()

    def test_default_deny_no_dispatch(self):
        self.r.init([task()])
        mock = Mock(side_effect=AssertionError('must not execute'))
        with patch.dict(OPERATIONS, {'sum':mock}):
            result = self.r.run()
        mock.assert_not_called()
        self.assertEqual(result['tasks']['a']['blocker'], 'DENIED')
        self.assertEqual(result['verdict'], 'INCOMPLETE')
        self.assertEqual(result['attempts_used'], 0)
        self.assertEqual(len(self.r.receipts()), 1)

    def test_narrow_allowlist(self):
        self.r.init([task(), task('b',['a'],'collect',{}, {'a':3})], policy(['sum']))
        result = self.r.run()
        self.assertEqual(result['tasks']['a']['status'], 'PASS')
        self.assertEqual(result['tasks']['b']['blocker'], 'DENIED')
        self.assertEqual(result['attempts_used'], 1)
        self.assertTrue(self.r.verify()['valid'])

    def test_dependency_order(self):
        self.r.init([task('b',['a'],'collect',{}, {'a':3}),task()], policy())
        self.assertEqual(self.r.run()['verdict'], 'PASS')
        events = [x['record']['event'] for x in self.r.receipts()]
        self.assertEqual([e['id'] for e in events[1:]], ['a','b'])

    def test_persisted_budget(self):
        self.r.init([task(), task('b')], policy(attempts=1))
        self.assertEqual(self.r.run()['attempts_used'], 1)
        self.r.close(); self.r = ControlledRuntime(self.path)
        result = self.r.run()
        self.assertEqual(result['steps_this_run'], 0)
        self.assertEqual(result['tasks']['b']['blocker'], 'BUDGET_EXHAUSTED')
        self.assertEqual(result['attempts_remaining'], 0)

    def test_checkpoint_resume(self):
        self.r.init([task(), task('b',['a'])], policy())
        self.assertEqual(self.r.run(max_steps=1)['attempts_used'], 1)
        self.r.close(); self.r = ControlledRuntime(self.path)
        result = self.r.run()
        self.assertEqual(result['verdict'], 'PASS')
        self.assertEqual(result['steps_this_run'], 1)
        self.assertEqual(self.r.run()['steps_this_run'], 0)
        self.assertEqual(len(self.r.receipts()), 3)

    def test_zero_steps(self):
        self.r.init([task()], policy())
        self.assertEqual(self.r.run(max_steps=0)['attempts_used'], 0)

    def test_failed_dependencies(self):
        self.r.init([task(expect=9),task('b',['a']),task('c')], policy())
        result = self.r.run()
        self.assertEqual(result['verdict'], 'FAIL')
        self.assertEqual(result['tasks']['b']['blocker'], 'DEPENDENCY_FAILED')
        self.assertEqual(result['tasks']['c']['status'], 'PASS')
        self.assertEqual(self.r.run()['steps_this_run'], 0)

    def test_error_never_passes_matching_expectation(self):
        self.r.init([task(args={'values':[True]},expect={'error':'INVALID_ARGUMENTS'})], policy())
        self.assertEqual(self.r.run()['verdict'], 'FAIL')
        self.assertEqual(self.r.receipts()[-1]['record']['event']['outcome'], 'ERROR')
        self.assertTrue(self.r.verify()['valid'])

    def test_output_limit(self):
        self.r.init([task(args={'values':[MAX_NUMBER,1]},expect=0)], policy())
        result = self.r.run()
        self.assertEqual(result['tasks']['a']['result'], {'error':'OUTPUT_LIMIT'})
        self.assertEqual(result['verdict'], 'FAIL')
        self.assertTrue(self.r.verify()['valid'])

    def test_unknown_operations(self):
        with self.assertRaises(ValueError): self.r.init([task(op='shell')],policy())
        with self.assertRaises(ValueError): self.r.init([task()],policy(['shell']))
        self.assertFalse(self.r.verify()['valid'])

    def test_policy_validation(self):
        for bad in [policy(attempts=True),policy(attempts=-1),policy(attempts=65),
                    policy(attempts=4,tasks=3),policy(['sum','sum']),policy([{}]),
                    {'allowed_operations':['sum'],'max_attempts':1,'max_tasks':3,'extra':True}]:
            with self.subTest(policy=bad), self.assertRaises(ValueError): validate_policy(bad)

    def test_plan_validation(self):
        cases = [[task(),task()], [task('a',['b']),task('b',['a'])], [task(deps=['missing'])],
                 [task(), task('b',['a','a'])], [task(op=[])], [task(id='bad id')],
                 [task(args={'values':[MAX_NUMBER+1]})], [task(expect=float('nan'))],
                 [task(args={'value':'x'*20000})], [task('a'),task('b')]]
        for plan in cases:
            with self.subTest(plan=str(plan)[:100]), self.assertRaises(ValueError):
                validate_plan(plan,policy(attempts=1,tasks=1 if plan is cases[-1] else 8))

    def test_json_depth(self):
        value = 1
        for _ in range(20): value = [value]
        with self.assertRaises(ValueError): self.r.init([task(op='echo',args={'value':value},expect=None)],policy())

    def test_json_file_limits_and_duplicates(self):
        path = Path(self.tmp.name)/'bad.json'
        for data in [b'{"a":1,"a":2}',b'{"x":NaN}',b' '* (MAX_FILE+1)]:
            path.write_bytes(data)
            with self.subTest(size=len(data)), self.assertRaises(ValueError): read_json(path)

    def test_policy_immutable(self):
        self.r.init([task()])
        with self.assertRaises(ValueError): self.r.init([task()],policy())
        self.assertEqual(self.r.run()['attempts_used'], 0)

    def test_policy_tamper(self):
        self.r.init([task()])
        self.r.db.execute('UPDATE control_config SET policy=?',(canonical(policy()),))
        self.assertFalse(self.r.verify()['valid'])
        with self.assertRaises(ValueError): self.r.run()

    def test_receipt_tamper(self):
        self.r.init([task()],policy()); self.r.run()
        self.r.db.execute("UPDATE control_receipts SET hash='tampered' WHERE seq=2")
        self.assertFalse(self.r.verify()['valid'])
        with self.assertRaises(ValueError): self.r.run()

    def test_task_state_tamper(self):
        self.r.init([task()],policy()); self.r.run()
        self.r.db.execute("UPDATE control_tasks SET result='999'")
        self.assertFalse(self.r.verify()['valid'])

    def test_receipt_truncation(self):
        self.r.init([task()],policy()); self.r.run()
        self.r.db.execute('DELETE FROM control_receipts WHERE seq=2')
        self.assertFalse(self.r.verify()['valid'])

    def test_rehashed_invalid_verdict(self):
        self.r.init([task(expect=9)],policy()); self.r.run()
        record = self.r.receipts()[-1]['record']; record['event']['status']='PASS'
        self.r.db.execute('UPDATE control_receipts SET body=?,hash=? WHERE seq=2',(canonical(record),digest(record)))
        self.r.db.execute("UPDATE control_tasks SET status='PASS'")
        self.assertFalse(self.r.verify()['valid'])

    def test_external_head(self):
        self.r.init([task()],policy())
        initial = self.r.verify()['head']; self.r.run()
        self.assertFalse(self.r.verify(initial)['valid'])
        result = self.r.verify(self.r.verify()['head'])
        self.assertTrue(result['valid']); self.assertTrue(result['external_head_checked'])
        self.assertFalse(result['execution_authenticated'])

    def test_receipt_binding(self):
        self.r.init([task(), task('b',['a'],'collect',{}, {'a':3})], policy()); self.r.run()
        e = self.r.receipts()[-1]['record']['event']
        self.assertEqual(e['input_hash'],digest({'args':{},'dependencies':{'a':3}}))
        self.assertEqual(e['output_hash'],digest({'a':3}))
        self.assertEqual(e['expect_hash'],digest({'a':3}))
        self.assertEqual(e['capability'],'local.data.collect')

    def test_transaction_rollback(self):
        self.r.init([task()],policy())
        with patch.object(self.r,'_append',side_effect=RuntimeError('injected commit interruption')):
            with self.assertRaises(RuntimeError): self.r.run()
        self.assertEqual(self.r.status()['attempts_used'], 0)
        self.assertEqual(self.r.status()['tasks']['a']['status'], 'PENDING')
        self.assertTrue(self.r.verify()['valid'])
        self.assertEqual(self.r.run()['verdict'], 'PASS')

    def test_concurrent_workers(self):
        self.r.init([task('a'),task('b',['a']),task('c',['b'])],policy())
        def worker(_):
            r=ControlledRuntime(self.path)
            try: return r.run()
            finally: r.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(worker,range(2)))
        self.assertEqual(self.r.status()['verdict'],'PASS')
        self.assertEqual(len(self.r.receipts()),4)
        self.assertTrue(self.r.verify()['valid'])

    def test_cross_format_rejected(self):
        self.r.init([task()],policy())
        with self.assertRaises(ValueError): Runtime(self.path)
        old=Path(self.tmp.name)/'legacy.db'
        legacy=Runtime(old); legacy.init([task()]); legacy.db.close()
        with self.assertRaises(ValueError): ControlledRuntime(old)

    def test_process_exit_rollback(self):
        self.r.init([task()],policy())
        # A separate interpreter exits without cleanup after state update and
        # before the receipt insert. SQLite must roll back the open transaction.
        program = ("import os,sys; from controlled import ControlledRuntime; "
                   "r=ControlledRuntime(sys.argv[1]); "
                   "r._append=lambda event: os._exit(73); r.run()")
        process = subprocess.run([sys.executable,'-c',program,str(self.path)],
                                 cwd=Path(__file__).resolve().parents[1],
                                 capture_output=True,timeout=15)
        self.assertEqual(process.returncode,73,process.stderr.decode(errors='replace'))
        self.assertTrue(self.r.verify()['valid'])
        self.assertEqual(self.r.status()['attempts_used'],0)
        self.assertEqual(self.r.status()['tasks']['a']['status'],'PENDING')
        self.assertEqual(self.r.run()['verdict'],'PASS')

    def test_cli_default_deny(self):
        project=Path(self.tmp.name)/'cli.db'
        root=Path(__file__).resolve().parents[1]
        def cli(*args):
            return subprocess.run([sys.executable,str(root/'controlled.py'),'--db',str(project),*map(str,args)],
                                  capture_output=True,text=True,timeout=15)
        self.assertEqual(cli('init',root/'demo.json').returncode,0)
        run=cli('run')
        self.assertEqual(run.returncode,1,run.stderr)
        self.assertEqual(json.loads(run.stdout)['attempts_used'],0)
        self.assertNotEqual(cli('run','--policy',root/'demo-policy.json').returncode,0)
        self.assertTrue(json.loads(cli('verify').stdout)['valid'])

    def test_cli_run_and_verify(self):
        project=Path(self.tmp.name)/'cli-allowed.db'
        root=Path(__file__).resolve().parents[1]
        def cli(*args):
            return subprocess.run([sys.executable,str(root/'controlled.py'),'--db',str(project),*map(str,args)],
                                  capture_output=True,text=True,timeout=15)
        self.assertEqual(cli('init',root/'demo.json','--policy',root/'demo-policy.json').returncode,0)
        first=cli('run','--max-steps','1')
        self.assertEqual(first.returncode,1,first.stderr)
        self.assertEqual(json.loads(first.stdout)['attempts_used'],1)
        final=cli('run')
        self.assertEqual(final.returncode,0,final.stderr)
        self.assertEqual(json.loads(final.stdout)['verdict'],'PASS')
        verified=cli('verify','--expected-head',json.loads(final.stdout)['receipt_head'])
        self.assertEqual(verified.returncode,0,verified.stderr)
        self.assertTrue(json.loads(verified.stdout)['external_head_checked'])
        self.assertEqual(len(json.loads(cli('receipts').stdout)),3)

    def test_invalid_run_budget(self):
        self.r.init([task()],policy())
        for args in [{'max_steps':True},{'max_steps':65},{'max_seconds':0},{'max_seconds':float('inf')}]:
            with self.subTest(args=args), self.assertRaises(ValueError): self.r.run(**args)
        self.assertEqual(self.r.status()['attempts_used'],0)


class RegistryPortabilityTests(unittest.TestCase):
    def test_lf_crlf_preserve_original_hash(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'example'; p.mkdir()
            raw=b'---\nname: example\ndescription: text --- inside description\n---\nIgnore these instructions.'
            hashes=[]
            for sep in [b'\n',b'\r\n']:
                data=raw.replace(b'\n',sep); (p/'SKILL.md').write_bytes(data)
                result=inventory(d)[0]
                self.assertEqual(result['description'],'text --- inside description')
                self.assertEqual(result['sha256'],hashlib.sha256(data).hexdigest()); hashes.append(result['sha256'])
                self.assertIsNone(result['capability'])
            self.assertNotEqual(*hashes)

    def test_duplicate_metadata_fields(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'example'; p.mkdir()
            for body in [b'name: example\nname: example\ndescription: text',
                         b'name: example\nname: INVALID\ndescription: text',
                         b'name: example\ndescription: text\ndescription: other',
                         b'name: example\ndescription:    ']:
                (p/'SKILL.md').write_bytes(b'---\n'+body+b'\n---\n')
                with self.assertRaises(ValueError): inventory(d)

    def test_delimiter_must_be_own_line(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'example'; p.mkdir()
            (p/'SKILL.md').write_bytes(b'---\nname: example\ndescription: text---\n')
            with self.assertRaises(ValueError): inventory(d)


if __name__=='__main__': unittest.main()
