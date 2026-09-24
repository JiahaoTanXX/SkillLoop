"""Pure operational contract models. These are not Linux/SQLite integration tests."""
import copy
import sys
import unittest
from pathlib import Path
import jsonschema
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import spec_v22_operations as o

class OperationsTests(unittest.TestCase):
    def control(self, kind, body):
        import spec_v22_core
        return spec_v22_core.envelope(kind,body)
    def test_control_requests_use_OS_role_and_deadline(self):
        now=datetime(2026,9,24,tzinfo=timezone.utc)
        request=self.control('ControlRequest',{'operation_id':'op','deadline':'2026-09-24T01:00:00Z','method':'read_resource','params':{'call_digest':'sha256:'+'1'*64}})
        o.validate_control_record(request,peer_uid=21002,now=now)
        with self.assertRaisesRegex(o.Rejected,'permission'):o.validate_control_record(request,peer_uid=21007,now=now)
        with self.assertRaisesRegex(o.Rejected,'deadline'):o.validate_control_record(request,peer_uid=21002,now=datetime(2026,9,25,tzinfo=timezone.utc))
        request['body']['params']['role']='admin'
        with self.assertRaises(jsonschema.ValidationError):o.validate_control_record(request,peer_uid=21002,now=now)
    def test_async_reply_requires_operation_ticket(self):
        response=self.control('ControlResponse',{'operation_id':'op','status':'accepted','result_kind':'InferenceResult','result_digest':'sha256:'+'1'*64,'error_code':None,'retryable':False})
        with self.assertRaisesRegex(o.Rejected,'ticket'):o.validate_control_record(response)
        response['body']['result_kind']='OperationTicket';response=self.control('ControlResponse',response['body']);o.validate_control_record(response)
    def call(self,n=1,response='reply-1'):
        return {'call_id':f'call-{n}','native_id':f'native-{n}','response_id':response,'tool':'read_resource','args_digest':f'digest-{n}'}
    def prepared(self):
        proxy=o.ProxyModel(); proxy.write(b'{}\n',0); receipt=proxy.receipt(); grant=proxy.prepare('prepare-1',receipt)
        return proxy,receipt,grant
    def test_campaign_dedup_adoption_renewal(self):
        r=o.CampaignRegistry(); first=r.issue('p','a','config')
        self.assertEqual(first,r.issue('p','a','config'))
        adopted=r.issue('p','b','config'); renewed=r.issue('p','b','config','renewal','attestation-1')
        self.assertEqual(len({first,adopted,renewed}),3)
        self.assertEqual(renewed,r.issue('p','b','config','renewal','attestation-1'))
        self.assertNotEqual(first,r.issue('p','a','config',generation=3))
    def test_epoch_freeze_and_rotation(self):
        ledger=o.ProtectionLedger(); checks={k:True for k in ['schema','truth','coverage','delivery','dev_dedup','leak_check']}
        ledger.create_epoch('c1','s','e1','f','f',checks)
        self.assertEqual(ledger.create_epoch('c1','s','e1','f','f',checks),'e1')
        with self.assertRaises(o.Rejected): ledger.create_epoch('c1','changed','e2','f','f',checks)
        with self.assertRaises(o.Rejected): ledger.create_epoch('c2','s','e1','f','f',checks)
        ledger.create_epoch('c2','s','e2','f','f',checks)
        key=ledger.reserve('d','c1','e1','s','case',0); ledger.record(key,'delivered')
        with self.assertRaises(o.Rejected):ledger.reserve('d','c1','e1','s','case',0)
    def test_factory_failure_no_fallback(self):
        checks={k:True for k in ['schema','truth','coverage','delivery','dev_dedup','leak_check']}; checks['truth']=False
        with self.assertRaisesRegex(o.Rejected,'unavailable'):o.ProtectionLedger().create_epoch('c','s','e','f','f',checks)
        checks['truth']=True
        with self.assertRaisesRegex(o.Rejected,'approval'):o.ProtectionLedger().create_epoch('c','s','e','f','f2',checks)
    def test_private_projection_no_guessable_hash(self):
        private={'opaque_ref':'random-reference','aggregate_status':'inconclusive','payload_digest':'guessable','payload':'secret','oracle':'answer','private_path':'hidden'}
        self.assertEqual(o.public_projection(private),{'opaque_ref':'random-reference','aggregate_status':'inconclusive'})
    def test_revocation_publication_order(self):
        p,r,g=self.prepared();p.revoke()
        with self.assertRaisesRegex(o.Rejected,'expired'):p.publish('pub',g['grant_id'])
        self.assertIsNone(p.publication)
        p,r,g=self.prepared();p.publish('pub',g['grant_id']);p.revoke()
        self.assertEqual(p.events,['publication_committed','effective_revocation_committed'])
        self.assertIsNotNone(p.publication)
    def test_only_runtime_can_register(self):
        for role in ['model','generator','patcher','scanner','admin']:
            with self.subTest(role=role),self.assertRaisesRegex(o.Rejected,'forbidden'):o.ProxyModel().register_batch([self.call()],role=role)
    def test_same_call_changed_args_rejected(self):
        p=o.ProxyModel();call=self.call();p.register_batch([call]);call['args_digest']='changed'
        with self.assertRaisesRegex(o.Rejected,'parameter_conflict'):p.register_batch([call])
        self.assertEqual(p.used_tools,1)
    def test_batch_overflow_is_atomic(self):
        p=o.ProxyModel()
        with self.assertRaisesRegex(o.Rejected,'over_budget'):p.register_batch([self.call(i) for i in range(13)])
        self.assertEqual(p.used_tools,0);self.assertEqual(p.calls,{})
    def test_batch_replay_does_not_recount(self):
        p=o.ProxyModel();calls=[self.call(1),self.call(2)];p.register_batch(calls);p.register_batch(calls)
        self.assertEqual(p.used_tools,2)
    def test_duplicate_native_id_rejected(self):
        p=o.ProxyModel();a=self.call(1);b=self.call(2);b['native_id']=a['native_id']
        with self.assertRaisesRegex(o.Rejected,'duplicate_native'):p.register_batch([a,b])
        self.assertEqual(p.used_tools,0)
        p.register_batch([a]);b['response_id']='reply-2';p.register_batch([b])
        self.assertEqual(p.used_tools,2)
    def test_receipt_ttl_and_approval_cap(self):
        p=o.ProxyModel();p.write(b'{}',0);r=p.receipt(now=500);g=p.prepare('k',r,now=501)
        self.assertEqual(p.receipts[r]['expires_at'],700);self.assertEqual(g['expires_at'],700)
    def test_aba_invalidates_receipt(self):
        p,r,g=self.prepared();p.write(b'other',1);p.write(b'{}\n',2)
        with self.assertRaisesRegex(o.Rejected,'stale_receipt'):p.prepare('new',r)
        with self.assertRaisesRegex(o.Rejected,'stale_grant'):p.publish('pub',g['grant_id'])
    def test_expired_prepare_returns_original(self):
        p,r,g=self.prepared();self.assertEqual(p.prepare('prepare-1',r,now=301),g)
        with self.assertRaisesRegex(o.Rejected,'expired'):p.publish('pub',g['grant_id'],now=301)
    def test_old_fence_cannot_query_idempotency(self):
        p,r,g=self.prepared();p.cancel()
        with self.assertRaisesRegex(o.Rejected,'stale_fence'):p.prepare('prepare-1',r)
        self.assertIsNotNone(p.recover('prepare','prepare-1'))
        with self.assertRaisesRegex(o.Rejected,'forbidden'):p.recover('prepare','prepare-1',role='model')
    def test_second_publication_rejected(self):
        p,r,g=self.prepared();first=p.publish('pub',g['grant_id']);self.assertEqual(p.publish('pub',g['grant_id']),first)
        with self.assertRaisesRegex(o.Rejected,'already_exists'):p.publish('pub-2',g['grant_id'])
    def test_not_reproduced_is_not_false_positive(self):
        self.assertEqual(o.finding_decision('high','not_reproduced','open'),'block')
        self.assertEqual(o.finding_decision('low','not_reproduced','open'),'warning')
        with self.assertRaises(o.Rejected):o.finding_decision('low','not_reproduced','false_positive')
    def test_repair_requires_confirmed_and_regression(self):
        with self.assertRaises(o.Rejected):o.finding_decision('high','not_reproduced','repaired',dynamic_regression_pass=True)
        with self.assertRaises(o.Rejected):o.finding_decision('high','confirmed','repaired')
        self.assertEqual(o.finding_decision('high','confirmed','repaired',dynamic_regression_pass=True),'closed_repaired')
    def test_policy_mitigation_is_not_repair(self):
        with self.assertRaises(o.Rejected):o.finding_decision('high','unverified','mitigated_by_policy')
        self.assertEqual(o.finding_decision('high','unverified','mitigated_by_policy',complete_policy_proof=True),'closed_preventive_not_repair_count')
    def test_admin_review_cannot_override_effect(self):
        self.assertEqual(o.finding_decision('low','confirmed','false_positive',admin_evidence=True,prohibited_effect=True),'block')
    def test_history_capacity_not_retirement(self):
        with self.assertRaises(o.Rejected):o.history_requirement(compatibility='same',retirement_reason='capacity',admin_evidence=True)
        with self.assertRaises(o.Rejected):o.history_requirement(compatibility='same',retirement_reason='not_applicable')
    def test_history_unknown_compatibility_blocks(self):
        self.assertEqual(o.history_requirement(compatibility='unknown'),'block')
        self.assertEqual(o.history_requirement(compatibility='migrated'),'required')
    def test_budget_96_and_retry_reserve(self):
        items=o.expand_plan(finalists=1,abandoned=1,active=1); result=o.budget(items)
        self.assertEqual(len(items),96);self.assertEqual(result['reserved_victim_attempts'],98)
        self.assertFalse(any(i['subject']=='abandoned' and i['phase']=='protected' for i in items))
        self.assertEqual(o.budget(o.expand_plan(finalists=1,abandoned=1,active=1,retries=2))['reserved_victim_attempts'],98)
    def test_budget_over_capacity_rejected(self):
        r=o.budget(o.expand_plan(finalists=1,abandoned=1,active=1,history=4));self.assertEqual(r['admission'],'rejected')
    def test_budget_calibration_required(self):
        self.assertEqual(o.budget(o.expand_plan(finalists=0))['admission'],'calibration_required')
    def test_budget_calibration_can_fail_wall_bound(self):
        self.assertEqual(o.budget(o.expand_plan(finalists=1,active=1),calibration_ready=True,victim_timeout_seconds=600)['admission'],'rejected')
    def test_terminal_stop_is_failure(self):
        for event in ['model_stop_without_required_publication','final_answer_without_tools','tool_or_round_budget_exhausted']:
            self.assertEqual(o.transition('running',event)['utility'],'fail')
    def test_provider_timeout_is_unknown(self):
        r=o.transition('running','provider_timeout');self.assertEqual(r['utility'],'unknown_preserve_known_fail');self.assertEqual(r['coverage'],'incomplete')
    def test_retry_restrictions(self):
        base=dict(phase='dev',prior_retries=0,campaign_retries=0,delivery='not_delivered',known_failure=False,side_effect_state='absent')
        self.assertTrue(o.retry_eligible(**base))
        for update in [dict(known_failure=True),dict(side_effect_state='unknown'),dict(prior_retries=1),dict(campaign_retries=2),dict(phase='protected',delivery='unknown'),dict(phase='protected',delivery='delivered')]:
            self.assertFalse(o.retry_eligible(**dict(base,**update)))
    def test_cancel_late_output_quarantined(self):
        self.assertEqual(o.transition('running','cancel')['to'],'cancelled')
        self.assertEqual(o.transition('cancelled','late_output')['atomic_records'],['quarantine_index'])
        with self.assertRaises(o.Rejected):o.transition('cancelled','publish_committed')
    def test_model_identity_pending_no_quantization_substitution(self):
        m=o.load('runtime-profile.json')['model'];self.assertEqual(m['model_id'],'Qwen/Qwen3.8-27B-FP8')
        self.assertFalse(m['backend_locked_by_user']);self.assertEqual(m['recommended_backend'],'sglang')
        self.assertIsNone(m['actual_weights_digest']);self.assertFalse(m['calibration_ready'])
    def test_scanner_lock_pending(self):
        lock=o.load('runtime-profile.json')['scanner_lock'];self.assertEqual(lock['readiness'],'pending');self.assertIsNone(lock['transitive_lock_digest']);self.assertEqual(lock['offline_smoke_evidence'],[])
    def test_cli_verdict_exit_and_contractless_scan(self):
        cli=o.load('cli.json');self.assertFalse(cli['scan_requires_contract']);self.assertEqual(cli['verdict_exit'],{'pass':0,'fail':1,'needs_contract':3,'inconclusive':4})
        commands={c['name']:c for c in cli['commands']};self.assertEqual(commands['scan']['stdout_schema'],'ScannerReport')
        self.assertIn('--repair-rounds=0|1|2',commands['evaluate']['optional_flags']);self.assertIn('harden',commands)
    def test_github_nonpass_blocks(self):
        self.assertEqual(o.github_conclusion('pass'),'success')
        self.assertTrue(all(o.github_conclusion(v) in {'failure','action_required'} for v in ['fail','needs_contract','inconclusive']))
    def test_github_controlled_fork_import(self):
        g=o.load('cli.json')['github'];self.assertEqual(g['fork_import'],'read_only_git_objects_no_PR_scripts');self.assertEqual(g['required_check'],'SkillLoop / security');self.assertFalse(g['registry_and_github_cross_system_atomic'])
    def test_storage_reservation_and_full_queue(self):
        GiB=1024**3;self.assertEqual(o.storage_admission(10*GiB,2*GiB,3*GiB,0),'ready')
        self.assertEqual(o.storage_admission(4*GiB,2*GiB,GiB,0),'insufficient_storage')
        self.assertEqual(o.storage_admission(10*GiB,0,GiB,16),'busy')
        self.assertEqual(o.storage_admission(10*GiB,0,GiB,0,database_ok=False),'database_unavailable')
    def test_restore_invalidates_old_epoch(self):
        with self.assertRaises(o.Rejected):o.restore_epoch('a','a')
        self.assertEqual(o.restore_epoch('a','b'),{'deployment_epoch':'b','grants_valid':False,'leases_valid':False,'attestations_valid':False})
    def test_p95_nearest_rank(self):
        self.assertEqual(o.nearest_rank_p95(list(range(1,21))),19);self.assertIsNone(o.nearest_rank_p95([]))
    def test_performance_sample_floor(self):
        self.assertIsNone(o.performance_ratio([2]*19,[1]*20));self.assertIsNone(o.performance_ratio([2]*20,[0]*20));self.assertEqual(o.performance_ratio([2]*20,[1]*20),2)
    def test_role_limits_and_management_isolation(self):
        p=o.load('runtime-profile.json');self.assertTrue(all(w['network']=='none' and not w['capabilities'] and w['no_new_privileges'] and w['pids']<=64 for w in p['workers']))
        rpc=o.load('rpc.json');self.assertEqual([r['role'] for r in rpc['roles'] if r['tool_socket']],['runtime']);self.assertFalse(rpc['caller_supplied_role_authorizes'])
    def test_fixed_config_mutation_is_rejected(self):
        p=copy.deepcopy(o.load('runtime-profile.json'));p['budget']['victim_attempts']=129
        with self.assertRaises(jsonschema.ValidationError):jsonschema.Draft202012Validator(o.load('operations.schema.json')).validate(p)

if __name__=='__main__':unittest.main()
