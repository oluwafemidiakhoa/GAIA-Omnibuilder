import copy, unittest
from pathlib import Path
from controlled import read_json
from benchmark import freeze, score
from gaia import digest
ROOT=Path(__file__).resolve().parents[1]
class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.c=read_json(ROOT/'benchmark-cases.json'); self.f=freeze(self.c); self.r=read_json(ROOT/'benchmark-fixture.json'); self.h=self.f['sha256']
    def score(self): return score(self.f,self.r,self.h)
    def test_frozen(self): self.assertEqual(self.f,read_json(ROOT/'benchmark-frozen.json'))
    def test_fixture_counts(self):
        s=self.score(); self.assertEqual((s['baseline_passes'],s['candidate_passes'],s['wins'],s['losses'],s['ties']),(7,9,3,1,6)); self.assertAlmostEqual(s['paired_delta'],.2); self.assertEqual(s['exact_two_sided_sign_p'],.625)
    def test_no_promotion(self): self.assertFalse(self.score()['performance_claim_authorized'])
    def test_missing(self):
        del self.r['candidate']['DEV-01']; s=self.score(); self.assertEqual(s['status'],'INCOMPLETE'); self.assertIsNone(s['exact_two_sided_sign_p'])
    def test_tamper(self):
        self.f['body']['cases'][0]['mission']='changed'
        with self.assertRaises(ValueError): self.score()
    def test_rehash(self):
        self.f['body']['cases'][0]['mission']='changed'; self.f['sha256']=digest(self.f['body'])
        with self.assertRaises(ValueError): self.score()
    def test_duplicate(self):
        self.c['cases'].append(copy.deepcopy(self.c['cases'][0]))
        with self.assertRaises(ValueError): freeze(self.c)
    def test_bad_contract(self):
        self.c['cases'][0]['contract']['tasks'][0]['expect']=11
        with self.assertRaises(ValueError): freeze(self.c)
    def test_unknown_case(self):
        self.r['baseline']['extra']={}
        with self.assertRaises(ValueError): self.score()
    def test_invalid_authority(self):
        self.r['candidate']['DEV-01']['execution_authorized']=True
        self.assertEqual(self.score()['rows'][0]['candidate'],'INVALID')
    def test_suite_binding(self):
        self.r['suite_sha256']='0'*64
        with self.assertRaises(ValueError): self.score()
    def test_invalid_kind(self):
        self.r['kind']='verified_live'
        with self.assertRaises(ValueError): self.score()
