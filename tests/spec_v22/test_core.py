"""Executable-spec counterexamples; no production runtime is exercised."""
import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
try:
    import spec_v22_core as m
except ModuleNotFoundError:
    m = None

class CoreSpec(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(m, 'API4 executable specification has not been implemented')
        self.world = m.load('core/gate-world.json')
    def run_result(self, **changes):
        obs = copy.deepcopy(self.world['observation'])
        obs['body'].update(changes)
        obs = m.reseal(obs)
        return m.evaluate_run(obs, self.world['objectives'], self.world['events'], self.world['evidence'])
    def test_delivery_failure_never_passes(self):
        r = self.run_result(exposure_status='delivery_failed')
        c = m.reduce_case([r], self.world['case'])
        self.assertFalse(c['body']['coverage_complete'])
        self.assertEqual(c['body']['security_status'], 'unknown')
    def test_unknown_policy_is_incomplete(self):
        r = self.run_result(policy_decisions=['unknown'])
        self.assertFalse(m.reduce_case([r], self.world['case'])['body']['coverage_complete'])
    def test_effect_truth_comes_from_authorized_events(self):
        w = self.world
        event = copy.deepcopy(w['events'][0]); event['body'].update(event_id='event-leak',event_type='effect',objective_id='forbidden-leak',channel='final_answer',outcome='pass',sequence=2,observer_role='evaluator',recipient_scope='public')
        event = m.reseal(event)
        w['events'].append(event); w['evidence']['body']['event_digests'].append(event['digest']); w['evidence']=m.reseal(w['evidence'])
        r=m.evaluate_run(w['observation'],w['objectives'],w['events'],w['evidence'])
        self.assertTrue(r['body']['security_violation'])
        self.assertEqual(m.reduce_case([r],w['case'])['body']['security_status'],'fail')
    def test_untrusted_event_cannot_set_outcome(self):
        w=self.world; w['events'][0]['body']['outcome']='fail'; w['events'][0]=m.reseal(w['events'][0])
        with self.assertRaisesRegex(ValueError,'evidence'):
            m.evaluate_run(w['observation'],w['objectives'],w['events'],w['evidence'])
    def test_unknown_utility_remains_unknown(self):
        w=self.world; w['events']=[]; w['evidence']['body']['event_digests']=[]; w['evidence']=m.reseal(w['evidence'])
        r=m.evaluate_run(w['observation'],w['objectives'],[],w['evidence'])
        c=m.reduce_case([r],w['case'])
        self.assertEqual(c['body']['utility_status'],'unknown'); self.assertFalse(c['body']['coverage_complete'])
    def test_known_failure_survives_missing_coverage(self):
        w=self.world; e=w['events'][0]; e['body']['outcome']='fail'; e=m.reseal(e); w['evidence']['body']['event_digests']=[e['digest']]; w['evidence']=m.reseal(w['evidence'])
        w['observation']['body']['evidence_complete']=False; w['observation']=m.reseal(w['observation'])
        r=m.evaluate_run(w['observation'],w['objectives'],[e],w['evidence'])
        c=m.reduce_case([r],w['case']); self.assertEqual(c['body']['utility_status'],'fail'); self.assertFalse(c['body']['coverage_complete'])
    def test_optional_not_read_is_complete(self):
        self.assertTrue(m.reduce_case([self.run_result(exposure_status='not_read')],self.world['case'])['body']['coverage_complete'])
    def test_retry_cannot_erase_valid_failure(self):
        r=self.run_result(); r['body']['security_violation']=True
        next(x for x in r['body']['objective_outcomes'] if x['prohibited'])['effect']='pass';r=m.reseal(r)
        retry=self.run_result();retry['body']['attempt_index']=1;retry=m.reseal(retry)
        self.assertEqual(m.reduce_case([r,retry],self.world['case'])['body']['security_status'],'fail')
    def test_scanner_complete_requires_full_profile(self):
        r=m.load('core/scanner-example.json'); r['body'].update(status='complete',upstream_exit_code=2,raw_report_digest=None,analyzers=[]); r=m.reseal(r)
        with self.assertRaisesRegex(ValueError,'scanner'):
            m.validate_scanner_report(r,m.load('core/scanner-profile.json'))
    def test_plan_reservation_derived_from_matrix(self):
        w=m.load('core/gate-authority.json'); p=w['plan']; p['body']['reserved_rollouts']=1; p=m.reseal(p)
        with self.assertRaisesRegex(ValueError,'reservation'):
            m.validate_plan(p,w['suite'])
    def test_pass_requires_exact_manifest_not_nine_arbitrary_tokens(self):
        w=m.load('core/gate-authority.json'); w['cases'][0]['body']['case_digest']='sha256:'+'f'*64; w['cases'][0]=m.reseal(w['cases'][0])
        with self.assertRaisesRegex(ValueError,'case|manifest'):
            m.evaluate_gate(w['subject'],w['suite'],w['plan'],w['cases'],w['context'])
    def test_ci_nested_semantics_and_coverage(self):
        w=m.load('core/gate-authority.json'); g=m.evaluate_gate(w['subject'],w['suite'],w['plan'],w['cases'],w['context'])
        ci=m.build_ci_result(g,None,w['cases']); ci['body']['submitted_decision']['body']['incomplete_reasons']=['missing']; ci['body']['submitted_decision']=m.reseal(ci['body']['submitted_decision']); ci=m.reseal(ci)
        with self.assertRaisesRegex(ValueError,'pass|incomplete'):
            m.validate_ci_result(ci,w['cases'])
        ci=m.build_ci_result(g,None,w['cases']); ci['body']['coverage'][0]['completed_cases']=0; ci=m.reseal(ci)
        with self.assertRaisesRegex(ValueError,'coverage'):
            m.validate_ci_result(ci,w['cases'])
    def test_action_requires_tool_specific_binding(self):
        p=m.load('core/policy-example.json'); p['body']['allowed_actions'][0]['bindings']=[]; p=m.reseal(p)
        with self.assertRaisesRegex(ValueError,'binding'):
            m.canonical_policy(p)
    def test_policy_set_order_has_one_identity(self):
        p=m.load('core/policy-example.json'); other=copy.deepcopy(p); other['body']['allowed_actions'].reverse()
        self.assertEqual(m.canonical_policy(p)['digest'],m.canonical_policy(m.reseal(other))['digest'])
    def test_policy_duplicates_cannot_hide_as_set(self):
        p=m.load('core/policy-example.json'); p['body']['allowed_actions'].append(copy.deepcopy(p['body']['allowed_actions'][0]))
        with self.assertRaisesRegex(ValueError,'duplicate'):
            m.canonical_policy(m.reseal(p))
    def test_attack_requires_payload_objective_clean_pair(self):
        c=copy.deepcopy(self.world['case']); c['body'].update(mutation_digest=None,objective_ids=[],clean_pair_digest=None); c=m.reseal(c)
        with self.assertRaisesRegex(ValueError,'attack'):
            m.validate_record(c)
    def test_resource_identity_is_unique_per_instance(self):
        t=m.load('core/task-binding-example.json'); t['body']['resources'].append(copy.deepcopy(t['body']['resources'][0])); t=m.reseal(t)
        with self.assertRaisesRegex(ValueError,'duplicate_resource'):
            m.validate_record(t)
    def test_policy_only_cannot_edit_files(self):
        p=m.load('core/patch-example.json'); p['body']['repair_kind']='policy_only'; p=m.reseal(p)
        with self.assertRaisesRegex(ValueError,'policy_only'):
            m.apply_patch(p,m.load('core/patch-files.json'),[],m.load('core/policy-example.json'))
    def test_utf8_edit_boundaries_and_parent_digest(self):
        p=m.load('core/patch-example.json'); files=m.load('core/patch-files.json')
        good=m.apply_patch(p,files,[],m.load('core/policy-example.json'))
        self.assertIn('SKILL.md',good['files'])
        p['body']['edits'][0]['start_byte']=1; p=m.reseal(p)
        with self.assertRaises(ValueError): m.apply_patch(p,files,[],m.load('core/policy-example.json'))
    def test_mutation_final_bytes_and_digest(self):
        mutation=m.load('core/mutation-example.json')
        result=m.render_mutation('安全说明',mutation,64)
        self.assertNotEqual(result['source_bytes_digest'],result['rendered_bytes_digest'])
        with self.assertRaisesRegex(ValueError,'slot_bytes'):
            m.render_mutation('x'*64,mutation,64)
    def test_gate_permutation_is_invariant_and_failure_sticky(self):
        w=m.load('core/gate-authority.json'); a=m.evaluate_gate(w['subject'],w['suite'],w['plan'],w['cases'],w['context'])
        b=m.evaluate_gate(w['subject'],w['suite'],w['plan'],list(reversed(w['cases'])),w['context'])
        self.assertEqual(a,b); self.assertEqual(a['body']['verdict'],'pass')
        w['cases'][0]['body'].update(utility_status='fail',coverage_complete=False);w['cases'][0]=m.reseal(w['cases'][0])
        self.assertEqual(m.evaluate_gate(w['subject'],w['suite'],w['plan'],w['cases'],w['context'])['body']['verdict'],'fail')
    def test_effect_conflict_is_rejected_on_ingestion(self):
        r=self.run_result(); r['body']['security_violation']=True
        with self.assertRaisesRegex(ValueError,'security_effect_conflict'): m.validate_record(m.reseal(r))
    def test_nonprohibited_effect_is_not_security_violation(self):
        w=self.world; d=copy.deepcopy(w['objectives'][1]);d['body'].update(objective_id='utility.hijack.v1',category='utility',prohibited=False);d=m.reseal(d);w['objectives'].append(d)
        e=copy.deepcopy(w['events'][0]);e['body'].update(event_id='utility-hijack',sequence=2,event_type='effect',objective_id='utility.hijack.v1',channel='final_answer',observer_role='evaluator',recipient_scope='public');e=m.reseal(e)
        w['events'].append(e);w['evidence']['body']['event_digests'].append(e['digest']);w['evidence']=m.reseal(w['evidence'])
        self.assertFalse(m.evaluate_run(w['observation'],w['objectives'],w['events'],w['evidence'])['body']['security_violation'])
    def test_unknown_effect_is_incomplete(self):
        w=self.world;e=copy.deepcopy(w['events'][0]);e['body'].update(event_id='unknown-effect',sequence=2,event_type='effect',objective_id='forbidden-leak',channel='final_answer',observer_role='evaluator',recipient_scope='public',outcome='unknown');e=m.reseal(e)
        w['events'].append(e);w['evidence']['body']['event_digests'].append(e['digest']);w['evidence']=m.reseal(w['evidence'])
        self.assertFalse(m.evaluate_run(w['observation'],w['objectives'],w['events'],w['evidence'])['body']['coverage_complete'])
    def test_candidate_identity_uses_normative_bundle(self):
        p=m.load('core/patch-example.json');files=m.load('core/patch-files.json');out=m.apply_patch(p,files,[],m.load('core/policy-example.json'))
        self.assertEqual(out['candidate_subject_digest'],out['candidate_bundle']['digest']);m.validate_record(out['candidate_bundle'])
    def test_history_same_length_replacement_cannot_claim_zero_cost(self):
        files=m.load('core/patch-files.json');policy=m.load('core/policy-example.json');p=m.load('core/patch-example.json')
        first=m.apply_patch(p,files,[],policy);h=first['history_entry'];h['changed_bytes']=0
        files.update(files=first['files'],subject_digest=first['candidate_subject_digest'])
        p['body']['parent_subject_digest']=files['subject_digest'];e=p['body']['edits'][0];raw=files['files']['SKILL.md'].encode();e.update(parent_bytes_digest=m.bytes_digest(raw),end_byte=len(raw),replacement_utf8='保持任务和可信授权边界。\n');p=m.reseal(p)
        with self.assertRaisesRegex(ValueError,'history_cost'):m.apply_patch(p,files,[h],policy)
    def test_history_current_parent_is_bound(self):
        files=m.load('core/patch-files.json');policy=m.load('core/policy-example.json');p=m.load('core/patch-example.json');first=m.apply_patch(p,files,[],policy)
        with self.assertRaisesRegex(ValueError,'history_current_parent'):m.apply_patch(p,files,[first['history_entry']],policy)
    def test_execution_record_is_not_result_body_digest(self):
        w=self.world;r=self.run_result();b=m.load('core/task-binding-example.json');q=m.envelope('RunRequest',dict(subject_digest=r['body']['subject_digest'],case_digest=r['body']['case_digest'],suite_digest=m.canonical_digest('suite'),plan_digest=m.canonical_digest('plan'),config_digest=m.canonical_digest('config'),authorization_domain_digest=b['body']['domain_digest'],initial_world_digest=m.canonical_digest('world'),repetition_index=0))
        rec=m.execution_record(q,r,w['evidence'],b);c=m.reduce_case([r],w['case']);self.assertEqual(c['body']['run_record_digests'],[])
        c=m.attach_execution_records(c,[rec],{r['digest']:r});self.assertEqual(c['body']['run_record_digests'],[rec['digest']]);self.assertNotEqual(rec['digest'],r['digest'])
        with self.assertRaisesRegex(ValueError,'missing_result'):m.attach_execution_records(c,[rec],{})
    def test_source_package_frontmatter_duplicate_and_case_collision(self):
        f=m.load('core/patch-files.json')['files'];m.validate_skill_package(f)
        bad=copy.deepcopy(f);bad['SKILL.md']=bad['SKILL.md'].replace('api_major: 4','name: evil\napi_major: 4')
        with self.assertRaisesRegex(ValueError,'frontmatter_duplicate'):m.validate_skill_package(bad)
        bad=copy.deepcopy(f);bad['skill.md']='x'
        with self.assertRaisesRegex(ValueError,'case_collision'):m.validate_skill_package(bad)
    def test_suite_attack_control_is_same_business_projection(self):
        w=m.load('core/gate-authority.json');templates=m.load('core/suite-templates.json');m.validate_suite(w['suite'],templates,self.world['objectives'])
        entry=next(x for x in w['suite']['body']['cases'] if x['case_kind']=='attack');entry['clean_pair_digest']=m.canonical_digest('missing');w['suite']=m.reseal(w['suite'])
        with self.assertRaisesRegex(ValueError,'suite_case_reference'):m.validate_suite(w['suite'],templates,self.world['objectives'])
    def test_grant_receipt_and_attestation_time_order(self):
        records=m.load('core/valid-records.json')
        # Time fields are checked by the operational transition model; this ensures parsing is strict.
        q=m.envelope('EvaluationAttestation',dict(subject_digest=m.canonical_digest('s'),plan_digest=m.canonical_digest('p'),suite_digest=m.canonical_digest('suite'),config_digest=m.canonical_digest('c'),required_run_manifest_digest=m.canonical_digest('runs'),gate_result_digest=m.canonical_digest('gate'),verdict='pass',issuer='local-authority',issued_at='2026-09-24T00:00:00Z',expires_at='2026-09-25T00:00:00Z',trust_revision=1))
        m.validate_record(q);q['body']['expires_at']='tomorrow'
        with self.assertRaises(ValueError):m.validate_record(m.reseal(q))
    def test_attestation_requires_all_plan_runs(self):
        w=m.load('core/gate-authority.json');c=m.load('core/required-run-chain.json')
        m.validate_attestation(c['attestation'],c['gate'],c['manifest'],w['plan'],w['suite'],c['records'],c['results'],m.load('core/suite-templates.json'),w['context'])
        c['manifest']['body']['entries'].pop();c['manifest']=m.reseal(c['manifest'])
        with self.assertRaisesRegex(ValueError,'required_set'):m.validate_required_run_manifest(c['manifest'],w['plan'],c['records'],c['results'])
    def test_attestation_cannot_substitute_successful_run(self):
        w=m.load('core/gate-authority.json');c=m.load('core/required-run-chain.json');c['manifest']['body']['entries'][1]['run_record_digests']=c['manifest']['body']['entries'][0]['run_record_digests'];c['manifest']=m.reseal(c['manifest'])
        with self.assertRaisesRegex(ValueError,'item_binding'):m.validate_required_run_manifest(c['manifest'],w['plan'],c['records'],c['results'])
    def test_attestation_recomputes_gate_instead_of_trusting_signed_claim(self):
        w=m.load('core/gate-authority.json');c=m.load('core/required-run-chain.json')
        c['gate']['body']['case_result_digests'][0]='sha256:'+'f'*64;c['gate']=m.reseal(c['gate'])
        c['attestation']['body']['gate_result_digest']=c['gate']['digest'];c['attestation']=m.reseal(c['attestation'])
        with self.assertRaisesRegex(ValueError,'not_derived'):
            m.validate_attestation(c['attestation'],c['gate'],c['manifest'],w['plan'],w['suite'],c['records'],c['results'],m.load('core/suite-templates.json'),w['context'])
    def test_manifest_cannot_hide_an_executed_failed_attempt(self):
        w=m.load('core/gate-authority.json');c=m.load('core/required-run-chain.json')
        old=next(iter(c['records'].values()));result=copy.deepcopy(c['results'][old['body']['result_digest']])
        result['body'].update(attempt_index=1,run_id='retry-hidden',utility_status='fail');result=m.reseal(result)
        extra=copy.deepcopy(old);extra['body'].update(result_digest=result['digest'],run_id='retry-hidden');extra=m.reseal(extra)
        c['records'][extra['digest']]=extra;c['results'][result['digest']]=result
        with self.assertRaisesRegex(ValueError,'omitted_executed'):
            m.validate_required_run_manifest(c['manifest'],w['plan'],c['records'],c['results'])
    def test_verify_contracts(self):
        result=m.verify();self.assertEqual(result['status'],'pass');self.assertFalse(result['runtime_verified'])

if __name__=='__main__': unittest.main()
