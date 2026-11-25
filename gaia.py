"""Local, single-worker, deterministic orchestration demonstrator."""
import argparse, hashlib, json, sqlite3, sys
from pathlib import Path

def canonical(x): return json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False)
def digest(x): return hashlib.sha256(canonical(x).encode()).hexdigest()

def validate(plan):
    if not isinstance(plan, list) or not plan: raise ValueError('nonempty task list required')
    ids = set()
    for t in plan:
        if set(t) != {'id','deps','op','args','expect'}: raise ValueError('invalid task fields')
        if not isinstance(t['id'],str) or not t['id'] or t['id'] in ids: raise ValueError('invalid or duplicate id')
        ids.add(t['id'])
        if t['op'] not in OPS: raise ValueError('operation not allowlisted')
        if not isinstance(t['deps'],list) or any(not isinstance(d,str) for d in t['deps']): raise ValueError('invalid dependencies')
        if not isinstance(t['args'],dict): raise ValueError('invalid arguments')
    done=set()
    while len(done)<len(ids):
        ready={t['id'] for t in plan if t['id'] not in done and set(t['deps'])<=done}
        if not ready: raise ValueError('cycle or unknown dependency')
        done.update(ready)
    canonical(plan)

def add(args, inputs):
    if set(args)!={'values'} or not isinstance(args['values'],list) or any(type(v)!=int for v in args['values']): raise ValueError('integer values required')
    return sum(args['values'])
def collect(args, inputs):
    if args: raise ValueError('collect takes no arguments')
    return inputs
def echo(args, inputs):
    if set(args)!={'value'}: raise ValueError('value required')
    return args['value']
OPS={'sum':add,'collect':collect,'echo':echo}

class Runtime:
    def __init__(self,path):
        self.db=sqlite3.connect(path)
        try:
            # Serialize the schema check with initialization by the controlled runner.
            self.db.execute('BEGIN IMMEDIATE')
            if self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='control_config'").fetchone():
                raise ValueError('v0.3 controlled database refused by legacy runner')
            self.db.execute('CREATE TABLE IF NOT EXISTS plan (body TEXT NOT NULL)')
            self.db.execute('CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, status TEXT NOT NULL, result TEXT)')
            self.db.execute('CREATE TABLE IF NOT EXISTS ledger (seq INTEGER PRIMARY KEY, body TEXT NOT NULL, hash TEXT NOT NULL)')
            self.db.commit()
        except BaseException:
            self.db.rollback()
            self.db.close()
            raise
    def event(self,body):
        last=self.db.execute('SELECT seq,hash FROM ledger ORDER BY seq DESC LIMIT 1').fetchone()
        seq,prev=(last[0]+1,last[1]) if last else (1,'0'*64)
        record={'seq':seq,'prev':prev,'event':body}
        self.db.execute('INSERT INTO ledger VALUES (?,?,?)',(seq,canonical(record),digest(record)))
    def init(self,plan):
        validate(plan)
        with self.db:
            if self.db.execute('SELECT 1 FROM plan').fetchone(): raise ValueError('project already initialized')
            self.db.execute('INSERT INTO plan VALUES (?)',(canonical(plan),))
            self.db.executemany('INSERT INTO tasks VALUES (?,\'PENDING\',NULL)',[(t['id'],) for t in plan])
            self.event({'kind':'init','plan_hash':digest(plan)})
    def verify(self):
        prev='0'*64; n=0; expected={}; plan_hash=None
        for seq,body,h in self.db.execute('SELECT seq,body,hash FROM ledger ORDER BY seq'):
            n+=1; r=json.loads(body)
            if seq!=n or r['seq']!=seq or r['prev']!=prev or digest(r)!=h: return False
            e=r['event']
            if e['kind']=='init': plan_hash=e['plan_hash']
            else: expected[e['id']]=(e['status'],canonical(e['result']))
            prev=h
        p=self.db.execute('SELECT body FROM plan').fetchone()
        if not p: return n==0 and not self.db.execute('SELECT 1 FROM tasks').fetchone()
        plan=json.loads(p[0])
        if digest(plan)!=plan_hash: return False
        actual={i:(s,r) for i,s,r in self.db.execute('SELECT * FROM tasks')}
        return actual=={t['id']:expected.get(t['id'],('PENDING',None)) for t in plan}
    def run(self):
        if not self.verify(): raise ValueError('integrity check failed')
        p=self.db.execute('SELECT body FROM plan').fetchone()
        if not p: raise ValueError('initialize first')
        plan=json.loads(p[0]); validate(plan)
        while True:
            state={i:(s,r) for i,s,r in self.db.execute('SELECT * FROM tasks')}
            ready=[t for t in plan if state[t['id']][0]=='PENDING' and all(state[d][0]=='PASS' for d in t['deps'])]
            if not ready: break
            for t in ready:
                try:
                    result=OPS[t['op']](t['args'],{d:json.loads(state[d][1]) for d in t['deps']})
                    status='PASS' if canonical(result)==canonical(t['expect']) else 'FAIL'
                except (ValueError, TypeError, KeyError) as exc:
                    result={'error':str(exc)}; status='FAIL'
                with self.db:
                    self.db.execute('UPDATE tasks SET status=?,result=? WHERE id=?',(status,canonical(result),t['id']))
                    self.event({'kind':'execution','id':t['id'],'status':status,'result':result})
        return self.status()
    def status(self):
        return {i:{'status':s,'result':json.loads(r) if r is not None else None} for i,s,r in self.db.execute('SELECT * FROM tasks ORDER BY id')}

def main():
    p=argparse.ArgumentParser(); p.add_argument('--db',default='project.db'); p.add_argument('command',choices=['init','run','status','verify']); p.add_argument('plan',nargs='?'); a=p.parse_args(); r=Runtime(a.db)
    if a.command=='init': r.init(json.loads(Path(a.plan).read_text())); print('initialized')
    elif a.command=='verify':
        ok=r.verify(); print(json.dumps({'valid':ok})); return 0 if ok else 1
    else:
        result=r.run() if a.command=='run' else r.status(); print(json.dumps(result,indent=2)); return 0 if all(t['status']=='PASS' for t in result.values()) and result else 1
    return 0
if __name__=='__main__': sys.exit(main())
