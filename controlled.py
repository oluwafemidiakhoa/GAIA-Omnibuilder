"""GAIA v0.3: bounded, local, policy-gated pure operations. No external execution."""
import argparse
from contextlib import contextmanager
import json
import math
import re
import sqlite3
import sys
import time
from pathlib import Path
from gaia import canonical, digest, add, collect, echo

VERSION = '0.3'
# Static dispatch table: no dynamic imports, shell, network or skill execution.
OPERATIONS = {'sum': add, 'echo': echo, 'collect': collect}
CAPABILITIES = {'sum': 'local.compute.sum', 'echo': 'local.data.echo',
                'collect': 'local.data.collect'}
MAX_FILE = 262144
MAX_VALUE = 16384
MAX_TASKS = 64
MAX_NUMBER = 10**12
IDENTIFIER = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z')
DEFAULT_POLICY = {'allowed_operations': [], 'max_attempts': 0, 'max_tasks': MAX_TASKS}
ERRORS = {'INVALID_ARGUMENTS', 'OUTPUT_LIMIT'}
ZERO = '0' * 64


def bounded_json(value, limit=MAX_VALUE):
    """Reject oversized/deep/non-JSON values before serialization."""
    nodes = 0
    def walk(x, depth):
        nonlocal nodes
        nodes += 1
        if nodes > 16384 or depth > 16:
            raise ValueError('JSON complexity limit')
        if x is None or type(x) is bool:
            return
        if type(x) is int or type(x) is float:
            if (type(x) is float and not math.isfinite(x)) or abs(x) > MAX_NUMBER:
                raise ValueError('numeric limit')
        elif type(x) is str:
            if len(x) > MAX_VALUE:
                raise ValueError('string limit')
            # Reject lone surrogates before canonicalization or DB writes.
            x.encode('utf-8')
        elif type(x) is list:
            for item in x:
                walk(item, depth+1)
        elif type(x) is dict:
            for k, v in x.items():
                if type(k) is not str or len(k) > 256:
                    raise ValueError('invalid JSON object key')
                walk(k, depth+1)
                walk(v, depth+1)
        else:
            raise ValueError('unsupported JSON type')
    walk(value, 0)
    result = canonical(value)
    if len(result.encode('utf-8')) > limit:
        raise ValueError('JSON byte limit')
    return result


def _pairs(items):
    out = {}
    for key, value in items:
        if key in out:
            raise ValueError('duplicate JSON key')
        out[key] = value
    return out


def _nonfinite(value):
    raise ValueError('non-finite JSON number')


def read_json(path):
    with Path(path).open('rb') as f:
        raw = f.read(MAX_FILE+1)
    if len(raw) > MAX_FILE:
        raise ValueError('input file size limit')
    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=_pairs, parse_constant=_nonfinite)


def validate_policy(policy):
    if type(policy) is not dict or set(policy) != set(DEFAULT_POLICY):
        raise ValueError('invalid policy fields')
    allowed = policy['allowed_operations']
    if (type(allowed) is not list or any(type(x) is not str or x not in OPERATIONS for x in allowed)
            or len(set(allowed)) != len(allowed)):
        raise ValueError('invalid or unregistered allowed operation')
    for key, lo, hi in [('max_attempts', 0, MAX_TASKS), ('max_tasks', 1, MAX_TASKS)]:
        if type(policy[key]) is not int or not lo <= policy[key] <= hi:
            raise ValueError('invalid ' + key)
    if policy['max_attempts'] > policy['max_tasks']:
        raise ValueError('attempt budget exceeds task limit')
    return {'allowed_operations': sorted(allowed), 'max_attempts': policy['max_attempts'],
            'max_tasks': policy['max_tasks']}


def validate_plan(plan, policy):
    bounded_json(plan, MAX_FILE)
    if type(plan) is not list or not 1 <= len(plan) <= policy['max_tasks']:
        raise ValueError('invalid plan size')
    ids = set()
    for t in plan:
        if type(t) is not dict or set(t) != {'id', 'deps', 'op', 'args', 'expect'}:
            raise ValueError('invalid task fields')
        if type(t['id']) is not str or not IDENTIFIER.fullmatch(t['id']) or t['id'] in ids:
            raise ValueError('invalid or duplicate task ID')
        ids.add(t['id'])
        if type(t['op']) is not str or t['op'] not in OPERATIONS:
            raise ValueError('unregistered operation')
        deps = t['deps']
        if (type(deps) is not list or len(deps) > MAX_TASKS or
                any(type(d) is not str or not IDENTIFIER.fullmatch(d) for d in deps) or
                len(set(deps)) != len(deps)):
            raise ValueError('invalid dependencies')
        if type(t['args']) is not dict:
            raise ValueError('invalid arguments')
        bounded_json(t['args'])
        bounded_json(t['expect'])
    done = set()
    while len(done) < len(ids):
        ready = {t['id'] for t in plan if t['id'] not in done and set(t['deps']) <= done}
        if not ready:
            raise ValueError('cycle or unknown dependency')
        done.update(ready)


def _input_hash(task, deps):
    return digest({'args': task['args'], 'dependencies': deps})


class ControlledRuntime:
    """Local trusted-operator database; one atomic committed attempt at a time."""
    def __init__(self, path):
        self.db = sqlite3.connect(path, timeout=5, isolation_level=None)
        try:
            with self.transaction():
                if self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name IN ('plan','tasks','ledger')").fetchone():
                    raise ValueError('legacy database refused; use a new v0.3 database')
                self.db.execute('CREATE TABLE IF NOT EXISTS control_config (id INTEGER PRIMARY KEY CHECK(id=1), plan TEXT NOT NULL, policy TEXT NOT NULL)')
                self.db.execute('CREATE TABLE IF NOT EXISTS control_tasks (id TEXT PRIMARY KEY, status TEXT NOT NULL CHECK(status IN (\'PENDING\',\'PASS\',\'FAIL\')), result TEXT)')
                self.db.execute('CREATE TABLE IF NOT EXISTS control_receipts (seq INTEGER PRIMARY KEY, body TEXT NOT NULL, hash TEXT NOT NULL)')
        except BaseException:
            self.db.close()
            raise

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self, write=True):
        self.db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def _append(self, event):
        last = self.db.execute('SELECT seq,hash FROM control_receipts ORDER BY seq DESC LIMIT 1').fetchone()
        seq, prev = (last[0]+1, last[1]) if last else (1, ZERO)
        record = {'seq': seq, 'prev': prev, 'event': event}
        h = digest(record)
        self.db.execute('INSERT INTO control_receipts VALUES (?,?,?)', (seq, canonical(record), h))
        return h

    def init(self, plan, policy=None):
        policy = validate_policy(DEFAULT_POLICY if policy is None else policy)
        validate_plan(plan, policy)
        with self.transaction():
            if self.db.execute('SELECT 1 FROM control_config').fetchone():
                raise ValueError('project already initialized; policy cannot be replaced')
            if self.db.execute('SELECT 1 FROM control_tasks').fetchone() or self.db.execute('SELECT 1 FROM control_receipts').fetchone():
                raise ValueError('nonempty orphan state refused')
            self.db.execute('INSERT INTO control_config VALUES (1,?,?)', (canonical(plan), canonical(policy)))
            self.db.executemany("INSERT INTO control_tasks VALUES (?, 'PENDING', NULL)", [(t['id'],) for t in plan])
            self._append({'kind': 'init', 'version': VERSION, 'plan_hash': digest(plan), 'policy_hash': digest(policy)})

    def _snapshot(self):
        """Replay all receipts without invoking operations; check config, policy, state."""
        row = self.db.execute('SELECT plan,policy FROM control_config WHERE id=1').fetchone()
        if not row:
            raise ValueError('project not initialized')
        plan, policy = json.loads(row[0]), json.loads(row[1])
        if validate_policy(policy) != policy:
            raise ValueError('noncanonical policy')
        validate_plan(plan, policy)
        if (canonical(plan), canonical(policy)) != row:
            raise ValueError('noncanonical config')
        ph, ah = digest(plan), digest(policy)
        tasks = {t['id']: t for t in plan}
        state = {i: ('PENDING', None) for i in tasks}
        head, count, attempts = ZERO, 0, 0
        for seq, body, h in self.db.execute('SELECT seq,body,hash FROM control_receipts ORDER BY seq'):
            record = json.loads(body)
            count += 1
            if (set(record) != {'seq', 'prev', 'event'} or type(record['seq']) is not int or
                    seq != count or record['seq'] != count or record['prev'] != head or
                    digest(record) != h or canonical(record) != body):
                raise ValueError('receipt chain mismatch')
            e = record['event']
            if count == 1:
                if e != {'kind': 'init', 'version': VERSION, 'plan_hash': ph, 'policy_hash': ah}:
                    raise ValueError('genesis mismatch')
            else:
                keys = {'kind', 'id', 'op', 'capability', 'plan_hash', 'policy_hash', 'input_hash',
                        'expect_hash', 'output_hash', 'outcome', 'status', 'result', 'attempt'}
                if type(e) is not dict or set(e) != keys or e['kind'] != 'execution':
                    raise ValueError('invalid execution receipt')
                attempts += 1
                t = tasks[e['id']]
                if (type(e['attempt']) is not int or e['attempt'] != attempts or
                        attempts > policy['max_attempts'] or state[t['id']][0] != 'PENDING' or
                        t['op'] not in policy['allowed_operations'] or
                        any(state[d][0] != 'PASS' for d in t['deps'])):
                    raise ValueError('invalid execution transition')
                deps = {d: state[d][1] for d in t['deps']}
                bounded_json(e['result'])
                if (e['op'] != t['op'] or e['capability'] != CAPABILITIES[t['op']] or
                        e['plan_hash'] != ph or e['policy_hash'] != ah or
                        e['input_hash'] != _input_hash(t, deps) or e['expect_hash'] != digest(t['expect']) or
                        e['output_hash'] != digest(e['result'])):
                    raise ValueError('execution binding mismatch')
                if e['outcome'] == 'RETURN':
                    expected_status = 'PASS' if canonical(e['result']) == canonical(t['expect']) else 'FAIL'
                elif e['outcome'] == 'ERROR' and type(e['result']) is dict and set(e['result']) == {'error'} and e['result']['error'] in ERRORS:
                    expected_status = 'FAIL'
                else:
                    raise ValueError('invalid operation outcome')
                if e['status'] != expected_status:
                    raise ValueError('invalid result verdict')
                state[t['id']] = (e['status'], e['result'])
            head = h
        if count == 0:
            raise ValueError('missing genesis receipt')
        actual = dict((i, (s, r)) for i, s, r in self.db.execute('SELECT id,status,result FROM control_tasks'))
        expected = {i: (s, None if s == 'PENDING' else canonical(r)) for i, (s, r) in state.items()}
        if actual != expected:
            raise ValueError('task state mismatch')
        return plan, policy, state, attempts, head

    def verify(self, expected_head=None):
        try:
            with self.transaction(write=False):
                _, _, _, attempts, head = self._snapshot()
                if expected_head is not None and head != expected_head:
                    raise ValueError('external head mismatch')
            return {'valid': True, 'head': head, 'attempts': attempts,
                    'external_head_checked': expected_head is not None, 'execution_authenticated': False}
        except (ValueError, TypeError, KeyError, OverflowError, RecursionError, sqlite3.DatabaseError) as exc:
            return {'valid': False, 'reason': str(exc), 'execution_authenticated': False}

    def _step(self):
        with self.transaction():
            plan, policy, state, attempts, _ = self._snapshot()
            if attempts >= policy['max_attempts']:
                return False
            eligible = [t for t in plan if state[t['id']][0] == 'PENDING' and
                        t['op'] in policy['allowed_operations'] and
                        all(state[d][0] == 'PASS' for d in t['deps'])]
            if not eligible:
                return False
            t = eligible[0]
            deps = {d: state[d][1] for d in t['deps']}
            outcome = 'RETURN'
            try:
                # Combined dependency input also has a fixed per-operation bound.
                bounded_json({'args': t['args'], 'dependencies': deps}, MAX_FILE)
                result = OPERATIONS[t['op']](t['args'], deps)
            except (ValueError, TypeError, KeyError):
                outcome, result = 'ERROR', {'error': 'INVALID_ARGUMENTS'}
            if outcome == 'RETURN':
                try:
                    bounded_json(result)
                except (ValueError, TypeError, OverflowError, RecursionError):
                    outcome, result = 'ERROR', {'error': 'OUTPUT_LIMIT'}
            status = 'PASS' if outcome == 'RETURN' and canonical(result) == canonical(t['expect']) else 'FAIL'
            self.db.execute('UPDATE control_tasks SET status=?,result=? WHERE id=?', (status, canonical(result), t['id']))
            self._append({'kind': 'execution', 'id': t['id'], 'op': t['op'], 'capability': CAPABILITIES[t['op']],
                          'plan_hash': digest(plan), 'policy_hash': digest(policy), 'input_hash': _input_hash(t, deps),
                          'expect_hash': digest(t['expect']), 'output_hash': digest(result), 'outcome': outcome,
                          'status': status, 'result': result, 'attempt': attempts+1})
            return True

    def status(self):
        with self.transaction(write=False):
            plan, policy, state, attempts, head = self._snapshot()
            tasks = {}
            for t in plan:
                s, result = state[t['id']]
                blocker = None
                if s == 'PENDING':
                    if t['op'] not in policy['allowed_operations']:
                        blocker = 'DENIED'
                    elif any(state[d][0] == 'FAIL' for d in t['deps']):
                        blocker = 'DEPENDENCY_FAILED'
                    elif attempts >= policy['max_attempts']:
                        blocker = 'BUDGET_EXHAUSTED'
                    elif any(state[d][0] != 'PASS' for d in t['deps']):
                        blocker = 'WAITING_FOR_DEPENDENCY'
                    else:
                        blocker = 'READY'
                tasks[t['id']] = {'status': s, 'result': result, 'blocker': blocker}
            verdict = 'PASS' if all(x['status'] == 'PASS' for x in tasks.values()) else ('FAIL' if any(x['status'] == 'FAIL' for x in tasks.values()) else 'INCOMPLETE')
            return {'verdict': verdict, 'tasks': tasks, 'attempts_used': attempts,
                    'attempts_remaining': policy['max_attempts']-attempts, 'receipt_head': head}

    def run(self, max_steps=MAX_TASKS, max_seconds=30.0):
        if type(max_steps) is not int or not 0 <= max_steps <= MAX_TASKS:
            raise ValueError('invalid step limit')
        if type(max_seconds) not in (int, float) or not math.isfinite(max_seconds) or not 0 < max_seconds <= 30:
            raise ValueError('invalid soft run deadline')
        start = time.monotonic()
        steps = 0
        while steps < max_steps and time.monotonic()-start < max_seconds:
            if not self._step():
                break
            steps += 1
        report = self.status()
        report['steps_this_run'] = steps
        report['soft_deadline_reached'] = time.monotonic()-start >= max_seconds
        return report

    def receipts(self):
        with self.transaction(write=False):
            self._snapshot()
            return [{'record': json.loads(b), 'hash': h} for b, h in self.db.execute('SELECT body,hash FROM control_receipts ORDER BY seq')]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db', default='controlled.db')
    p.add_argument('command', choices=['init', 'run', 'status', 'verify', 'receipts', 'operations'])
    p.add_argument('plan', nargs='?')
    p.add_argument('--policy', help='operator-selected local policy JSON, init only')
    p.add_argument('--max-steps', type=int, default=MAX_TASKS)
    p.add_argument('--max-seconds', type=float, default=30.0, help='soft deadline checked between steps')
    p.add_argument('--expected-head', help='optional independently retained receipt head, verify only')
    a = p.parse_args()
    if (a.policy or a.plan) and a.command != 'init':
        p.error('plan and policy are accepted only at initialization')
    if a.expected_head is not None and a.command != 'verify':
        p.error('expected head is accepted only for verify')
    if a.command == 'init' and not a.plan:
        p.error('init requires a plan file')
    if a.command == 'operations':
        print(json.dumps([{'operation': k, 'capability': v, 'kind': 'PURE_LOCAL', 'default_authorized': False} for k, v in CAPABILITIES.items()], indent=2))
        return 0
    r = None
    try:
        r = ControlledRuntime(a.db)
        if a.command == 'init':
            r.init(read_json(a.plan), read_json(a.policy) if a.policy else None)
            result, code = {'initialized': True, 'version': VERSION}, 0
        elif a.command == 'verify':
            result = r.verify(a.expected_head)
            code = 0 if result['valid'] else 1
        elif a.command == 'receipts':
            result, code = r.receipts(), 0
        else:
            result = r.run(a.max_steps, a.max_seconds) if a.command == 'run' else r.status()
            code = 0 if result['verdict'] == 'PASS' else 1
        print(json.dumps(result, indent=2))
        return code
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError, sqlite3.DatabaseError) as exc:
        print(json.dumps({'error': str(exc)}), file=sys.stderr)
        return 2
    finally:
        if r is not None:
            r.close()


if __name__ == '__main__':
    sys.exit(main())
