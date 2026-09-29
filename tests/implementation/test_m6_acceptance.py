import copy
import unittest

from skillloop.protocol import digest_bytes, digest_jcs
from skillloop.repair.acceptance import PROFILES, review
from skillloop.repair.budget import freeze


BASELINE = digest_bytes(b'accepted-m5-gate')


def report():
    subjects = {}
    for profile in PROFILES:
        subject = digest_bytes(profile.encode())
        row = {'subject_digest':subject,'verdict':'pass','required_cases':1,'required_runs':3,
            'missing':[],'known_failures':[],'unresolved_high':[],'scan_complete':True,
            'case_results':[{'body':{'subject_digest':subject,'case_digest':digest_bytes((profile+'case').encode()),
                'coverage_complete':True,'required_repetitions':3,'completed_repetitions':3,
                'utility_status':'pass','security_status':'pass'}}],
            'submitted_verdict':'fail','submitted_missing':[],'paired_development_coverage_complete':True,
            'submitted_required_runs':3,'submitted_executed_required_runs':3,'submitted_absent_items':[],
            'paired_to_submitted':{'improved':1,'regressed':0,'unchanged':2,'unknown':0},
            'budget':{'admission':'ready','reasons':[]},'generated_proposals':1,
            'spending_audit':{'admission':'ready','reasons':[]},
            'applications_succeeded':1,'evaluable_candidates':1,'reasoning_tokens':0,'model_responses':18,
            'frozen':False}
        row['freeze'] = freeze(subject=subject,development_verdict='pass',missing=[],unresolved_high=[],
            budget=row['budget'],proposal_attempts=1,applied_candidates=1,evaluable_candidates=1,
            evidence_digest=digest_jcs(row))
        row['frozen'] = True
        subjects[profile] = row
    value = {'kind':'M6IndependentGate','subjects':subjects,'baseline_gate_digest':BASELINE,
        'campaign_id':'m6-test-campaign','campaign_manifest_digest':digest_bytes(b'manifest'),
        'config_digest':digest_bytes(b'config'),'parent_gate_digests':[],
        'reducer_source_digest':digest_bytes(b'reducer'),
        'production_ready':False,'protected_evaluation':'not_started'}
    return {**value,'digest':digest_jcs(value)}


def reseal(value):
    for row in value['subjects'].values():
        if 'freeze' not in row:
            continue
        previous = {k:v for k,v in row.items() if k != 'freeze'}
        previous['frozen'] = False
        row['freeze']['development_gate_digest'] = digest_jcs(previous)
        row['freeze']['digest'] = digest_jcs({k:v for k,v in row['freeze'].items() if k != 'digest'})
    value['digest'] = digest_jcs({k:v for k,v in value.items() if k != 'digest'})
    return value


class M6AcceptanceTests(unittest.TestCase):
    def test_complete_candidates_and_failed_submitted_allow_m6_review(self):
        result = review([report()],m5_gate_digest=BASELINE)
        self.assertEqual(result['status'],'ready')
        self.assertTrue(result['m7_entry_ready'])
        self.assertFalse(result['production_ready'])

    def test_candidate_failure_missing_repetition_scan_and_original_gap_block(self):
        for field, value in (('known_failures',['failed-run']),('unresolved_high',['high']),
                             ('submitted_absent_items',['missing-original']),('reasoning_tokens',1)):
            with self.subTest(field=field):
                value_report = report()
                value_report['subjects']['orders_total'][field] = value
                self.assertEqual(review([reseal(value_report)],m5_gate_digest=BASELINE)['status'],'pending')
        value_report = report()
        value_report['subjects']['orders_total']['case_results'][0]['body']['completed_repetitions'] = 2
        self.assertEqual(review([reseal(value_report)],m5_gate_digest=BASELINE)['status'],'pending')

    def test_report_and_freeze_tampering_rejected(self):
        value_report = report()
        value_report['subjects']['orders_total']['verdict'] = 'fail'
        with self.assertRaisesRegex(ValueError,'report_binding'):
            review([value_report],m5_gate_digest=BASELINE)
        value_report = report()
        value_report['subjects']['orders_total']['freeze']['budget_digest'] = digest_bytes(b'wrong')
        reseal(value_report)
        with self.assertRaisesRegex(ValueError,'freeze_binding'):
            review([value_report],m5_gate_digest=BASELINE)

    def test_partial_reports_never_authorize_next_milestone(self):
        value_report = report()
        del value_report['subjects']['markdown_index']
        self.assertFalse(review([reseal(value_report)],m5_gate_digest=BASELINE)['m7_entry_ready'])

    def test_later_round_does_not_borrow_other_profile_success(self):
        first = report()
        second = copy.deepcopy(first)
        second['subjects'] = {'markdown_index': second['subjects']['markdown_index']}
        second['subjects']['markdown_index']['known_failures'] = ['new-failure']
        second['parent_gate_digests'] = [first['digest']]
        self.assertEqual(review([first,reseal(second)],m5_gate_digest=BASELINE)['status'],'pending')

    def test_cross_campaign_and_missing_parent_rejected(self):
        first = report()
        second = copy.deepcopy(first)
        second['campaign_id'] = 'another-campaign'
        second['parent_gate_digests'] = [first['digest']]
        with self.assertRaisesRegex(ValueError,'cross_campaign'):
            review([first,reseal(second)],m5_gate_digest=BASELINE)
        second = report()
        with self.assertRaisesRegex(ValueError,'gate_lineage'):
            review([first,second],m5_gate_digest=BASELINE)

    def test_incomplete_original_results_limit_pairing_without_rewriting_candidate(self):
        value_report = report()
        row = value_report['subjects']['orders_total']
        row['submitted_missing'] = ['incomplete-original-case']
        row['paired_development_coverage_complete'] = False
        row['paired_to_submitted']['unknown'] = 1
        result = review([reseal(value_report)],m5_gate_digest=BASELINE)
        self.assertEqual(result['status'],'ready_with_limits')
        self.assertTrue(result['m7_entry_ready'])
        self.assertEqual(result['subjects']['orders_total']['submitted_verdict'],'fail')
        self.assertIn('orders_total:submitted_pair_coverage_incomplete',result['limitations'])

    def test_independently_admitted_disjoint_profiles_keep_separate_campaigns(self):
        reports = []
        for profile in PROFILES:
            value = report()
            value['subjects'] = {profile:value['subjects'][profile]}
            value['campaign_id'] = 'independent-' + profile
            reports.append(reseal(value))
        result = review(reports,m5_gate_digest=BASELINE)
        self.assertTrue(result['m7_entry_ready'])
        self.assertIsNone(result['campaign_id'])
        self.assertEqual(len(set(result['profile_campaign_ids'].values())),3)

    def test_actual_spending_missing_blocks_freeze_review(self):
        value = report()
        del value['subjects']['orders_total']['spending_audit']
        self.assertIn('orders_total:actual_spending_not_verified',
            review([reseal(value)],m5_gate_digest=BASELINE)['reasons'])


if __name__ == '__main__':
    unittest.main()
