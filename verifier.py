"""Independent local oracle for operator-defined sum/echo/collect contracts.
Never invokes a provider, executes a proposal, or grants authorization.
"""
import argparse
import json
import sys
from pathlib import Path
from controlled import validate_plan, validate_policy, bounded_json, read_json, MAX_FILE
from gaia import canonical, digest


def verify(proposal, contract, policy):
    bounded_json(proposal, MAX_FILE)
    bounded_json(contract, MAX_FILE)
    policy = validate_policy(policy)
    if type(contract) is not dict or set(contract) != {'tasks'}:
        raise ValueError('invalid operator contract')
    # Contract specifies exact operation inputs, dependency structure and oracle outputs.
    required = contract['tasks']
    validate_plan(required, policy)
    if type(proposal) is not dict or proposal.get('execution_authorized') is not False:
        raise ValueError('proposal must not claim authority')
    plan = proposal.get('plan')
    validate_plan(plan, policy)
    findings = []
    def check(name, ok):
        findings.append({'check': name, 'pass': bool(ok)})
    check('policy_binding', proposal.get('policy') == policy)
    check('within_budget', len(plan) <= policy['max_attempts'])
    check('allowlisted_operations', all(t['op'] in policy['allowed_operations'] for t in plan))
    actual = {t['id']: t for t in plan}
    trusted = {t['id']: t for t in required}
    check('exact_task_set', set(actual) == set(trusted))
    results = {}
    pending = list(required)
    while pending:
        for t in pending[:]:
            if not set(t['deps']) <= results.keys():
                continue
            op, args, tid = t['op'], t['args'], t['id']
            # Independent implementation: no runtime dispatch table or model expectations.
            if op == 'sum' and set(args) == {'values'} and type(args['values']) is list and all(type(x) is int for x in args['values']):
                value = 0
                for x in args['values']:
                    value += x
            elif op == 'echo' and set(args) == {'value'}:
                value = args['value']
            elif op == 'collect' and not args:
                value = {d: results[d] for d in t['deps']}
            else:
                raise ValueError('invalid operator oracle inputs')
            bounded_json(value)
            results[tid] = value
            check(tid + ':contract_oracle', canonical(value) == canonical(t['expect']))
            candidate = actual.get(tid)
            check(tid + ':exact_inputs', candidate is not None and all(canonical(candidate[k]) == canonical(t[k]) for k in ('op','args','deps')))
            check(tid + ':oracle_output', candidate is not None and canonical(candidate['expect']) == canonical(value))
            pending.remove(t)
    return {'verdict': 'PASS' if all(f['pass'] for f in findings) else 'FAIL',
            'scope': 'operator_contract_only', 'execution_authorized': False,
            'execution_observed': False, 'natural_language_mission_verified': False,
            'proposal_sha256': digest(proposal), 'contract_sha256': digest(contract),
            'policy_sha256': digest(policy), 'findings': findings}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--proposal', required=True)
    p.add_argument('--contract', required=True)
    p.add_argument('--policy', required=True)
    p.add_argument('--out', required=True)
    a = p.parse_args()
    try:
        result = verify(read_json(a.proposal), read_json(a.contract), read_json(a.policy))
        with Path(a.out).open('x', encoding='utf-8') as f:
            json.dump(result, f, indent=2)
        print(json.dumps(result, indent=2))
        return 0 if result['verdict'] == 'PASS' else 1
    except (ValueError, TypeError, OSError, KeyError, RecursionError) as exc:
        print('Verification rejected: ' + type(exc).__name__, file=sys.stderr)
        return 2

if __name__ == '__main__':
    sys.exit(main())
