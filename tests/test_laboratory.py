import copy
import unittest
from unittest.mock import patch
import assurance as a
import laboratory as lab


class LaboratoryTests(unittest.TestCase):
    def manual(self):
        f = a.fixture(); f['submission_kind'] = 'MANUAL_UNVERIFIED'; return f

    def test_frozen(self):
        self.assertEqual(lab.protocol()['suite_sha256'], a.lock())
        with patch('assurance.lock', return_value='changed'):
            with self.assertRaises(ValueError): lab.protocol()

    def test_prompts(self):
        b, s = lab.prompt('baseline'), lab.prompt('assisted')
        self.assertEqual(s.replace('\nSpecialist instructions: '+lab.SKILL+'\n', ''), b)
        for case in a.suite()['cases']:
            self.assertIn(case['question'], b)
        for case in a.CASES:
            if case[3]: self.assertNotIn(case[3], s)
        self.assertNotIn('45000', s)
        self.assertNotIn('REFERENCE_FIXTURE', s)

    def test_fixture_rejected(self):
        with self.assertRaises(ValueError): lab.paired(a.fixture(), self.manual(), 'test', 'test')

    def test_ties(self):
        r = lab.paired(self.manual(), self.manual(), 'test', 'test')
        self.assertEqual((r['wins'],r['losses'],r['ties'],r['exact_mcnemar_p']), (0,0,30,1.0))
        self.assertFalse(r['behavioral_claim_authorized'])

    def test_win_loss(self):
        b, s = self.manual(), self.manual()
        b['responses']['DA-01'] = {'abstain':True}
        b['responses']['DA-02'] = {'abstain':True}
        s['responses']['DA-03'] = {'abstain':True}
        r = lab.paired(b,s,'test','test')
        self.assertEqual((r['wins'],r['losses'],r['ties']), (2,1,27))
        self.assertAlmostEqual(r['delta_percentage_points'],100/30)
        self.assertEqual(r['exact_mcnemar_p'],1.0)

    def test_exact(self):
        b = self.manual()
        for n in range(1,7): b['responses'][f'DA-{n:02}'] = {'abstain':True}
        r = lab.paired(b,self.manual(),'test','test')
        self.assertEqual(r['exact_mcnemar_p'],0.03125)

    def test_coverage(self):
        b=self.manual(); del b['responses']['DA-01']
        with self.assertRaises(ValueError): lab.paired(b,self.manual(),'test','test')

    def test_manifest(self):
        m=lab.manifest(); self.assertEqual(m['protocol_sha256'],a.digest(m['protocol']))
        self.assertNotEqual(m['prompt_sha256']['baseline'],m['prompt_sha256']['assisted'])
