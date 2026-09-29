import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.dgx_m6_repair import prepare, stage_bounds, claim_second_round
from skillloop.repair.budget import SpendingLedger
from skillloop.repair.clock import make_clock, start_seconds
from skillloop.repair.spending import snapshot, verify_snapshot, remaining_capacity


class AdmissionClockTests(unittest.TestCase):
    def test_profiles_start_when_individually_admitted(self):
        starts = []
        for profile, stamp in [('orders_total',1000000),('refunds_total',2000000)]:
            manifest = {'campaign_id':profile,'subjects':{profile:{}},
                'admission_clock':make_clock(profile,profile,stamp)}
            starts.append(start_seconds(manifest,profile,legacy_started_at=1))
        self.assertEqual(starts,[1000,2000])

    def test_clock_binding_and_shared_admission_rejected(self):
        manifest = {'campaign_id':'c','subjects':{'orders_total':{}},
            'admission_clock':make_clock('c','orders_total',1000000)}
        for field in ('digest','profile','campaign_id'):
            changed = copy.deepcopy(manifest)
            changed['admission_clock'][field] = 'changed'
            with self.assertRaisesRegex(ValueError,'clock_binding'):
                start_seconds(changed,'orders_total',legacy_started_at=1)
        manifest['subjects']['refunds_total'] = {}
        with self.assertRaisesRegex(ValueError,'clock_binding'):
            start_seconds(manifest,'orders_total',legacy_started_at=1)

    def test_legacy_clock_stays_unchanged(self):
        manifest = {'campaign_id':'old','subjects':{'orders_total':{}}}
        self.assertEqual(start_seconds(manifest,'orders_total',legacy_started_at=123.5),123.5)
        self.assertNotIn('admission_clock',manifest)

    def test_new_prepare_requires_one_profile_before_creating_output(self):
        with self.assertRaisesRegex(ValueError,'requires_single_profile'):
            prepare(SimpleNamespace(profile=None))

    def test_restart_cannot_refund_campaign_elapsed_time(self):
        with tempfile.TemporaryDirectory() as temporary, patch('time.time',return_value=1100):
            path = Path(temporary)/'spent.json'
            ledger = SpendingLedger(path,victim_seconds=265,campaign_started_at=1000)
            ledger.consume('s.case.0',0)
            SpendingLedger(path,victim_seconds=265,campaign_started_at=1000)
            with self.assertRaisesRegex(ValueError,'clock_changed'):
                SpendingLedger(path,victim_seconds=265,campaign_started_at=1100)

    def test_three_gate_checks_and_durability_share_the_finalization_reserve(self):
        final = next(s for s in stage_bounds() if s['name']=='finalization')
        self.assertEqual((final['count'],final['seconds']),(4,150))
        self.assertEqual(final['count']*final['seconds'],600)

    def test_second_round_claim_survives_restart_and_disallows_another_branch(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'claim.json'
            output = Path(temporary)/'second'
            claim_second_round(path,parent_gate_digest='exact-parent',output=output)
            original = path.read_bytes()
            for next_output in (output,Path(temporary)/'another'):
                with self.assertRaises(FileExistsError):
                    claim_second_round(path,parent_gate_digest='exact-parent',output=next_output)
            self.assertEqual(path.read_bytes(),original)


class SpendingAuditTests(unittest.TestCase):
    def setUp(self):
        self.clock = make_clock('c','orders_total',1000000)
        self.executions = [{'item_key':'subject.case.0','attempt':0,
            'record_digests':{'result.json':'result-hash','timing.json':'timing-hash'},
            'last_write_unix_ms':1100000}]
        self.state = {'victim_attempts':1,'retries':0,'elapsed_seconds':100.0,
            'charged_wall_seconds':265,'campaign_started_at':1000,
            'executions':[{'item_key':'subject.case.0','attempt':0}]}

    def seal(self,state=None,executions=None,finish=1200000):
        return snapshot(state or self.state,clock=self.clock,victim_seconds=265,
            executions=executions or self.executions,finished_at_unix_ms=finish)

    def test_snapshot_checks_actual_execution_bindings_and_counters(self):
        sealed = self.seal()
        self.assertEqual(sealed['admission'],'ready')
        self.assertEqual(verify_snapshot(sealed,current_state=self.state,clock=self.clock,
            victim_seconds=265,executions=self.executions),sealed)
        for key,value in [('victim_attempts',2),('retries',1),('charged_wall_seconds',0),
                          ('campaign_started_at',1100),('elapsed_seconds',-1)]:
            state = copy.deepcopy(self.state);state[key] = value
            with self.assertRaises(ValueError):self.seal(state=state)
        with self.assertRaisesRegex(ValueError,'execution_bindings'):
            self.seal(executions=[dict(self.executions[0],attempt=1)])

    def test_changed_result_and_removed_spending_rejected(self):
        sealed = self.seal()
        changed = copy.deepcopy(self.executions)
        changed[0]['record_digests']['result.json'] = 'replacement'
        with self.assertRaisesRegex(ValueError,'snapshot_changed'):
            verify_snapshot(sealed,current_state=self.state,clock=self.clock,
                victim_seconds=265,executions=changed)
        state = copy.deepcopy(self.state);state['executions'] = []
        with self.assertRaisesRegex(ValueError,'prefix'):
            verify_snapshot(sealed,current_state=state,clock=self.clock,
                victim_seconds=265,executions=self.executions)

    def test_second_round_append_preserves_first_snapshot(self):
        sealed = self.seal()
        later = copy.deepcopy(self.state)
        later['executions'].append({'item_key':'second.case.0','attempt':0})
        later.update(victim_attempts=2,charged_wall_seconds=530)
        self.assertEqual(verify_snapshot(sealed,current_state=later,clock=self.clock,
            victim_seconds=265,executions=self.executions),sealed)

    def test_finalization_time_is_reserved_and_post_close_writes_rejected(self):
        rejected = self.seal(finish=(1000+28800-599)*1000)
        self.assertEqual(rejected['admission'],'rejected')
        self.assertIn('actual_wall_or_finalization_reserve_exceeded',rejected['reasons'])
        with self.assertRaisesRegex(ValueError,'closed_before_execution'):
            self.seal(finish=1099999)

    def test_complete_current_matrix_still_needs_remaining_protected_capacity(self):
        for elapsed,expected in [(1000,'ready'),(27000,'rejected')]:
            result = remaining_capacity(self.state,started_at_unix_ms=1000000,
                at_unix_ms=(1000+elapsed)*1000,planned_attempts=27,auxiliary_seconds=720)
            self.assertEqual(result['admission'],expected)
            self.assertEqual(result['remaining_reserved_attempts'],26)

    def test_remaining_clock_never_refunds_recorded_elapsed_or_extra_attempts(self):
        state = dict(self.state,elapsed_seconds=28000)
        result = remaining_capacity(state,started_at_unix_ms=1000000,at_unix_ms=1200000,
            planned_attempts=10,auxiliary_seconds=720)
        self.assertEqual(result['admission'],'rejected')
        self.assertEqual(result['observed_elapsed_seconds'],28000)
        result = remaining_capacity(self.state,started_at_unix_ms=1000000,at_unix_ms=1200000,
            planned_attempts=0,auxiliary_seconds=720)
        self.assertEqual(result['admission'],'rejected')


if __name__ == '__main__':
    unittest.main()
