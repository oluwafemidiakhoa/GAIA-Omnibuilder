"""Paired, offline contract benchmark. No API calls or execution authorization."""
import argparse, json, math, sys
from pathlib import Path
from controlled import read_json, validate_policy, validate_plan
from gaia import digest
from verifier import verify


def freeze(cases):
    if type(cases) is not dict or set(cases) != {'cases'} or type(cases['cases']) is not list or not 1 <= len(cases['cases']) <= 100:
        raise ValueError('invalid suite')
    ids = set()
    for c in cases['cases']:
        if type(c) is not dict or set(c) != {'id','mission','contract','policy'} or type(c['id']) is not str or not c['id'] or c['id'] in ids or type(c['mission']) is not str or not c['mission'].strip():
            raise ValueError('invalid case')
        ids.add(c['id'])
        p = validate_policy(c['policy'])
        if c['policy'] != p: raise ValueError('noncanonical policy')
        # Establish that the operator's expected results are independently consistent.
        r = verify({'execution_authorized':False,'plan':c['contract']['tasks'],'policy':p},c['contract'],p)
        if r['verdict'] != 'PASS': raise ValueError('inconsistent contract')
    body = {'protocol':'paired-contract-v1','cases':cases['cases'],'missing':'incomplete_not_success','primary':'paired exact contract pass'}
    return {'body':body,'sha256':digest(body)}


def score(frozen, responses, expected_hash):
    body = frozen['body']
    if frozen['sha256'] != expected_hash or digest(body) != expected_hash or freeze({'cases':body['cases']}) != frozen:
        raise ValueError('freeze mismatch')
    if type(responses) is not dict or set(responses) != {'suite_sha256','kind','baseline','candidate'} or responses['suite_sha256'] != expected_hash or responses['kind'] not in ('synthetic_fixture','unverified_import'):
        raise ValueError('invalid responses')
    ids = {c['id'] for c in body['cases']}
    for arm in ('baseline','candidate'):
        if type(responses[arm]) is not dict or not set(responses[arm]) <= ids: raise ValueError('unexpected case')
    rows = []
    for c in body['cases']:
        row = {'id':c['id']}
        for arm in ('baseline','candidate'):
            if c['id'] not in responses[arm]: row[arm] = 'MISSING'; continue
            try:
                row[arm] = verify(responses[arm][c['id']],c['contract'],c['policy'])['verdict']
            except (ValueError, TypeError, KeyError, RecursionError): row[arm] = 'INVALID'
        rows.append(row)
    complete = [r for r in rows if 'MISSING' not in (r['baseline'],r['candidate'])]
    wins = sum(r['candidate']=='PASS' and r['baseline']!='PASS' for r in complete)
    losses = sum(r['baseline']=='PASS' and r['candidate']!='PASS' for r in complete)
    n = len(complete); d = wins+losses
    p = min(1.0, 2*sum(math.comb(d,k) for k in range(min(wins,losses)+1))/2**d) if d else 1.0
    return {'suite_sha256':expected_hash,'response_sha256':digest(responses),'kind':responses['kind'],'cases':len(rows),'complete_pairs':n,'baseline_passes':sum(r['baseline']=='PASS' for r in complete),'candidate_passes':sum(r['candidate']=='PASS' for r in complete),'wins':wins,'losses':losses,'ties':n-d,'paired_delta':(wins-losses)/n if n else None,'exact_two_sided_sign_p':p if n==len(rows) else None,'rows':rows,'status':'SCORED' if n==len(rows) else 'INCOMPLETE','provider_identity_verified':False,'matched_budgets_verified':False,'performance_claim_authorized':False,'promotion':'NOT_EVALUATED'}


def write(path, obj):
    with Path(path).open('x',encoding='utf-8') as f: json.dump(obj,f,indent=2,allow_nan=False)
    print(json.dumps(obj,indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='cmd',required=True)
    f=sub.add_parser('freeze'); f.add_argument('cases'); f.add_argument('--out',required=True)
    s=sub.add_parser('score'); s.add_argument('frozen'); s.add_argument('responses'); s.add_argument('--expected-hash',required=True); s.add_argument('--out',required=True)
    a=p.parse_args()
    try:
        r=freeze(read_json(a.cases)) if a.cmd=='freeze' else score(read_json(a.frozen),read_json(a.responses),a.expected_hash)
        write(a.out,r); return 1 if r.get('status')=='INCOMPLETE' else 0
    except (ValueError,TypeError,KeyError,OSError,RecursionError):
        print('Benchmark rejected input',file=sys.stderr); return 2
if __name__=='__main__': sys.exit(main())
