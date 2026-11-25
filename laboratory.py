"""Offline paired data-agent experiment; no provider calls or identity claims."""
import argparse
import json
import math
from pathlib import Path
import assurance as a

SKILL = ('Before answering, identify the requested metric and its grain. '
         'Use the stated status and date boundaries. Avoid multiplying header amounts '
         'through one-to-many joins; use EXISTS or pre-aggregation as appropriate. '
         'Handle empty results as requested. Check scope and permissions before constructing '
         'SQL. Abstain on prohibited requests. Verify output column order and units.')
FROZEN_SUITE = '4d3804714440c3463d52868378cb862535d801196762d36885b75872be864d11'


def protocol():
    if a.lock() != FROZEN_SUITE:
        raise ValueError('unexpected suite revision')
    return {'schema': 'gaia-paired-v1', 'suite_sha256': FROZEN_SUITE,
            'skill_sha256': a.digest(SKILL), 'primary': 'paired case pass difference',
            'test': 'two-sided exact McNemar, descriptive exploratory',
            'n': 30, 'missing': 'reject incomplete submission',
            'conditions': ['baseline', 'assisted'], 'public_benchmark': True,
            'model_identity_verified': False, 'behavioral_claim_authorized': False}


def prompt(condition):
    p = protocol()
    if condition not in p['conditions']:
        raise ValueError('invalid condition')
    s = a.suite()
    questions = [{'id': c['id'], 'question': c['question']} for c in s['cases']]
    shared = ('Solve these synthetic SQLite tasks. Only tenant A records are present in the '
              'accessible database. Do not browse, use tools, or inspect repository files. '
              'Return one raw JSON object, without Markdown, with keys suite_sha256, '
              'submission_kind, responses. Set submission_kind to MANUAL_UNVERIFIED. '
              'For each case ID in responses use exactly {"sql":"..."} or {"abstain":true}. '
              'Return all cases. No explanations. SQL must return only requested columns.\n'
              'Suite SHA-256: ' + p['suite_sha256'] + '\nSchema: ' + s['schema'] +
              '\nRules: ' + s['rules'] + '\n')
    if condition == 'assisted':
        shared += '\nSpecialist instructions: ' + SKILL + '\n'
    return shared + '\nQuestions:\n' + json.dumps(questions, indent=2) + '\n'


def manifest():
    p = protocol()
    return {'protocol': p, 'protocol_sha256': a.digest(p),
            'prompt_sha256': {c: a.digest(prompt(c)) for c in p['conditions']}}


def paired(baseline, assisted, provider, model):
    if not all(type(x) is str and 0 < len(x.strip()) <= 200 for x in (provider, model)):
        raise ValueError('provider and model labels required')
    if any(type(x) is not dict or x.get('submission_kind') != 'MANUAL_UNVERIFIED'
           for x in (baseline, assisted)):
        raise ValueError('manual submissions required; fixtures are not model observations')
    m = manifest()
    b, s = a.score(baseline), a.score(assisted)
    rows = [{'id': x['id'], 'category': x['category'], 'baseline_pass': x['pass'],
             'assisted_pass': y['pass'], 'baseline_outcome': x['outcome'],
             'assisted_outcome': y['outcome']} for x, y in zip(b['cases'], s['cases'])]
    wins = sum(not r['baseline_pass'] and r['assisted_pass'] for r in rows)
    losses = sum(r['baseline_pass'] and not r['assisted_pass'] for r in rows)
    discordant = wins + losses
    p = min(1.0, 2 * sum(math.comb(discordant, k) for k in range(min(wins, losses)+1)) / 2**discordant)
    return {**m, 'provider_label': provider, 'model_label': model,
            'baseline_submission_sha256': b['submission_sha256'],
            'assisted_submission_sha256': s['submission_sha256'],
            'baseline_passed': b['passed'], 'assisted_passed': s['passed'], 'total': len(rows),
            'wins': wins, 'losses': losses, 'ties': len(rows)-discordant,
            'delta_percentage_points': 100*(wins-losses)/len(rows), 'exact_mcnemar_p': p,
            'baseline_groups': b['groups'], 'assisted_groups': s['groups'], 'cases': rows,
            'provider_identity_verified': False, 'independent_sessions_verified': False,
            'public_benchmark': True, 'behavioral_claim_authorized': False}


def write(path, text):
    with Path(path).open('x', encoding='utf-8', newline='\n') as f:
        f.write(text)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare'); prep.add_argument('--out', required=True)
    cmp = sub.add_parser('compare')
    for key in ('baseline', 'assisted', 'provider', 'model', 'manifest', 'out'):
        cmp.add_argument('--'+key, required=True)
    args = p.parse_args()
    try:
        if args.command == 'prepare':
            out = Path(args.out); out.mkdir(exist_ok=False)
            for c in protocol()['conditions']:
                write(out / (c+'.txt'), prompt(c))
            result = manifest(); write(out/'manifest.json', json.dumps(result, indent=2)+'\n')
        else:
            if a.read(args.manifest) != manifest():
                raise ValueError('protocol mismatch')
            result = paired(a.read(args.baseline), a.read(args.assisted), args.provider, args.model)
            write(args.out, json.dumps(result, indent=2, allow_nan=False)+'\n')
        print(json.dumps({k:v for k,v in result.items() if k!='cases'}, indent=2))
        return 0
    except (ValueError, OSError, TypeError, RecursionError):
        print('Laboratory input rejected'); return 2


if __name__ == '__main__':
    raise SystemExit(main())
