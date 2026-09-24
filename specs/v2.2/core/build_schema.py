"""Deterministic schema source; run to regenerate ../protocol.schema.json."""
import json
from pathlib import Path
S={'type':'string','minLength':1}; B={'type':'boolean'}; I={'type':'integer','minimum':0,'maximum':9007199254740991}; D={'type':'string','pattern':'^sha256:[0-9a-f]{64}$'}; T={'type':'string','format':'date-time','pattern':r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$'}
def enum(*v):return {'enum':list(v)}
def arr(x,minimum=0):return {'type':'array','items':x,'minItems':minimum}
def nul(x):return {'anyOf':[x,{'type':'null'}]}
def obj(**p):return {'type':'object','additionalProperties':False,'properties':p,'required':list(p)}
def ref(n):return {'$ref':'#/$defs/'+n}
def entity(name,body):return obj(api_major={'const':4},kind={'const':name},body=body,digest=D)
TOOLS=['read_resource','build_artifact','write_artifact','validate_artifact','prepare_publication','publish_artifact']
TRI=enum('pass','fail','unknown'); VERDICT=enum('pass','fail','needs_contract','inconclusive'); ROLE=enum('submitted','candidate','finalist','active_baseline'); SPLIT=enum('dev','protected'); ACCESS=enum('read','write','publish'); RCLASS=enum('skill','input','artifact','sink')
bind=obj(parameter=S,slot=S,access=ACCESS)
action=obj(tool=enum(*TOOLS),bindings=arr(bind,1),destination_slot=nul(S),check_set_id=nul(S),transform_id=nul(S))
resource=obj(resource_id={'type':'string','pattern':'^(skill|input|artifact|sink):[A-Za-z0-9_-]+$'},resource_class=RCLASS,access=enum('read','write','read_write','publish'),bytes_digest=nul(D),tenant_id=S)
slot=obj(slot=S,resource_class=RCLASS,allowed_access=arr(ACCESS,1),tenant_id=S)
caseentry=obj(case_digest=D,case_kind=enum('clean','attack'),split=SPLIT,repetitions={'type':'integer','minimum':1,'maximum':10},objective_ids=arr(S),clean_pair_digest=nul(D),business_projection_digest=D,fixture_digest=D,mutation_digest=nul(D))
planitem=obj(item_id=S,subject_digest=D,case_digest=D,repetition_index=I,phase=SPLIT,subject_role=ROLE,requirement=enum('required','abandoned','not_applicable'),reason_code=nul(S),attempts_reserved={'type':'integer','minimum':1,'maximum':2},timeout_ms={'type':'integer','minimum':1})
coverage=obj(subject_digest=D,required_cases=I,completed_cases=I,required_repetitions=I,completed_repetitions=I)
edit=obj(path=S,parent_bytes_digest=D,start_byte=I,end_byte=I,replacement_utf8={'type':'string'})
objectiveout=obj(objective_id=S,objective_digest=D,attempt=TRI,effect=TRI,prohibited=B,event_digests=arr(D))
endpoint=obj(artifact_id=S,artifact_version={'type':'integer','minimum':1},artifact_digest=D,task_instance_id=S,run_id=S,subject_digest=D)
commonarg={'idempotency_key':S}; output={'output_id':S}; artifact={'output_id':S,'artifact_digest':D}
argdefs={
 'read_resource':obj(resource_id=S),
 'build_artifact':obj(input_bindings={'type':'object','minProperties':1,'propertyNames':{'pattern':'^[a-z][a-z0-9_]*$'},'additionalProperties':{'type':'string','pattern':'^(input|skill):[A-Za-z0-9_-]+$'}},output_id=S,transform_id=S,expected_version={'const':0},idempotency_key=S),
 'write_artifact':obj(output_id=S,expected_version=I,content_utf8={'type':'string','maxLength':16384},idempotency_key=S),
 'validate_artifact':obj(output_id=S,artifact_digest=D,check_set_id=S),
 'prepare_publication':obj(output_id=S,artifact_digest=D,destination_id=S,validation_receipt_id=S,idempotency_key=S),
 'publish_artifact':obj(output_id=S,artifact_digest=D,destination_id=S,validation_receipt_id=S,idempotency_key=S,grant_ref=S)}
successdefs={
 'read_resource':obj(content_utf8={'type':'string'},source_bytes_digest=D,rendered_bytes_digest=D),
 'build_artifact':obj(artifact_version=I,artifact_digest=D),
 'write_artifact':obj(artifact_version=I,artifact_digest=D),
 'validate_artifact':obj(validation_receipt_id=S,artifact_digest=D),
 'prepare_publication':obj(grant_ref=S,action_digest=D),
 'publish_artifact':obj(publication_id=S,artifact_digest=D)}
DEFS={
 'Contract':obj(contract_id=S,family_id=S,profile_id=S,profile_digest=D,oracle_digest=D,factory_rule_digest=D,tool_registry_digest=D,version={'type':'integer','minimum':1}),
 'SourceSnapshot':obj(source_kind=enum('git_commit','local_scan'),source_commit_sha=nul({'type':'string','pattern':'^[0-9a-f]{40}$'}),immutable=B,files=arr(obj(path=S,bytes_digest=D,size_bytes=I),1),skill_digest=D,loader_profile_digest=D),
 'ObjectiveDefinition':obj(objective_id=S,version={'type':'integer','minimum':1},category=enum('security','utility'),prohibited=B,event_type=enum('effect','utility'),allowed_channels=arr(enum('final_answer','mock_publication','private_evidence','public_diagnostic','public_sink_tool_args'),1),predicate_id=S,observer_role=enum('oracle','evaluator','proxy')),
 'TrustedEvent':obj(event_id=S,sequence=I,run_id=S,task_instance_id=S,subject_digest=D,event_type=enum('utility','attempt','effect','terminal'),objective_id=nul(S),channel=enum('final_answer','mock_publication','private_evidence','public_diagnostic','public_sink_tool_args'),outcome=TRI,observer_role=enum('oracle','evaluator','proxy'),source_digest=D,recipient_scope=enum('private','public'),predicate_version=S),
 'EvidenceIndex':obj(run_id=S,task_instance_id=S,subject_digest=D,event_digests=arr(D),trace_digest=nul(D),complete=B,issuer={'const':'trusted-collector'},trust_revision={'type':'integer','minimum':1}),
 'RunObservation':obj(run_id=S,task_instance_id=S,subject_digest=D,case_digest=D,repetition_index=I,attempt_index=I,case_validity=enum('valid','invalid','harness_error','unknown'),infra_status=enum('ok','config_error','timeout','cancelled','runtime_error','clock_error'),exposure_status=enum('exposed','not_read','delivery_failed','context_exceeded','not_applicable'),policy_decisions=arr(enum('allow','deny','unknown','not_applicable')),evidence_complete=B,terminal_reason=enum('completed','agent_stopped','agent_budget_exhausted','infra_timeout','cancelled','runtime_error')),
 'RunResultBody':obj(run_id=S,task_instance_id=S,subject_digest=D,case_digest=D,repetition_index=I,attempt_index=I,case_validity=enum('valid','invalid','harness_error','unknown'),coverage_complete=B,utility_status=TRI,security_violation=B,objective_outcomes=arr(objectiveout),exposure_status=enum('exposed','not_read','delivery_failed','context_exceeded','not_applicable'),incomplete_reasons=arr(S),evidence_index_digest=D),
 'CaseTemplate':obj(case_id=S,case_kind=enum('clean','attack'),split=SPLIT,fixture_digest=D,business_projection_digest=D,mutation_digest=nul(D),clean_pair_digest=nul(D),objective_ids=arr(S),repetitions={'type':'integer','minimum':1,'maximum':10}),
 'CaseResult':obj(subject_digest=D,case_digest=D,case_kind=enum('clean','attack'),split=SPLIT,coverage_complete=B,utility_status=TRI,security_status=TRI,attempt_success=B,effect_success=B,required_repetitions=I,completed_repetitions=I,run_record_digests=arr(D),result_body_digests=arr(D),incomplete_reasons=arr(S)),
 'SuiteManifest':obj(suite_id=S,profile_id=S,epoch_id=nul(S),visibility=enum('public_dev','private_evaluation','synthetic_test'),objective_registry_digest=D,cases=arr(caseentry,1),base_case_digests=arr(D,9),history_case_digests=arr(D)),
 'ExecutionPlan':obj(campaign_id=S,revision={'type':'integer','minimum':1},parent_plan_digest=nul(D),suite_digest=D,config_digest=D,phase=enum('dev','finalist_frozen','protected','finished'),items=arr(planitem,1),reserved_rollouts=I,reserved_execution_ms=I,reserved_auxiliary_ms=I,terminal_reserve_ms=I,max_campaign_rollouts={'type':'integer','minimum':1},max_campaign_execution_ms={'type':'integer','minimum':1},runtime_profile_digest=D),
 'GateContext':obj(contract_approved=B,approval_digest=nul(D),runtime_verified=B,source_immutable=B,scanner_complete=B,authorization_verified=B,evidence_verified=B,unresolved_high_findings=I,definite_failures=arr(enum('forbidden_patch','policy_expansion','subject_mismatch','utility_regression')),incomplete_reasons=arr(S),config_digest=D),
 'GateResult':obj(subject_digest=D,verdict=VERDICT,plan_digest=D,suite_digest=D,config_digest=D,required_case_digests=arr(D),case_result_digests=arr(D),coverage=coverage,failure_reasons=arr(S),incomplete_reasons=arr(S),contract_approved=B),
 'CIResult':obj(submitted_decision=ref('GateResult'),candidate_decision=nul(ref('GateResult')),coverage=arr(coverage,1),exit_code=enum(0,1,3,4),repair_required=B),
 'AuthorizationDomain':obj(domain_id=S,contract_digest=D,tenant_id=S,slots=arr(slot,1),approved_actions=arr(action,1),max_tool_calls={'type':'integer','minimum':1,'maximum':12},prerequisites_profile={'const':'strict-v2'}),
 'TaskBinding':obj(task_instance_id=S,run_id=S,subject_digest=D,domain_digest=D,tenant_id=S,resources=arr(resource,1),slot_bindings=arr(obj(slot=S,resource_id=S),1)),
 'Policy':obj(contract_digest=D,domain_digest=D,allowed_actions=arr(action,1),max_tool_calls={'type':'integer','minimum':1,'maximum':12},prerequisites_profile={'const':'strict-v2'}),
 'ApprovedCap':obj(domain_digest=D,task_binding_digest=D,task_instance_id=S,run_id=S,actions=arr(obj(tool=enum(*TOOLS),bindings=arr(obj(parameter=S,resource_id=S,access=ACCESS),1),destination_id=nul(S),check_set_id=nul(S),transform_id=nul(S)),1),max_tool_calls={'type':'integer','minimum':1,'maximum':12}),
 'RepairObligations':obj(domain_digest=D,requirements=arr(obj(obligation=enum('require_validation','restrict_destination','restrict_resources'),slots=arr(S),check_set_id=nul(S)))),
 'CandidateBundle':obj(skill_digest=D,policy_digest=D,obligation_digest=D,compiler_digest=D),
 'RunRequest':obj(subject_digest=D,case_digest=D,suite_digest=D,plan_digest=D,config_digest=D,authorization_domain_digest=D,initial_world_digest=D,repetition_index=I),
 'ExecutionRecord':obj(request_digest=D,result_digest=D,evidence_index_digest=D,task_binding_digest=D,run_id=S,task_instance_id=S),
 'EvaluationAttestation':obj(subject_digest=D,plan_digest=D,suite_digest=D,config_digest=D,required_run_manifest_digest=D,gate_result_digest=D,verdict=VERDICT,issuer={'const':'local-authority'},issued_at=T,expires_at=T,trust_revision={'type':'integer','minimum':1}),
 'RequiredRunManifest':obj(subject_digest=D,plan_digest=D,entries=arr(obj(item_id=S,run_record_digests=arr(D,1)),1)),
 'MutationSpec':obj(slot_id=S,mode=enum('append','replace'),payload_utf8={'type':'string','minLength':1},payload_bytes_digest=D,delivery={'const':'every_read_same_rendered_bytes'},exposure_requirement={'const':'optional'},max_rendered_bytes={'type':'integer','minimum':1,'maximum':4096},source_bytes_digest=nul(D)),
 'AttackPlan':obj(finding_digest=nul(D),objective_ids=arr(S,1),case_template_digest=D,mutation_digest=D,allowed_slot_ids=arr(S,1),clean_pair_digest=D,generator_config_digest=D,variant_of_case_digest=nul(D)),
 'LogicalFinding':obj(finding_id=S,scanner_report_digest=D,rule_id=S,severity=enum('critical','high','medium','low','unknown'),location=obj(path=S,start_line={'type':'integer','minimum':1},end_line={'type':'integer','minimum':1}),description=S,dynamic_applicability=enum('applicable','static_only','unsupported','unknown'),objective_ids=arr(S)),
 'FindingDisposition':obj(finding_digest=D,verification=enum('unverified','confirmed','not_reproduced','not_applicable','inconclusive'),disposition=enum('open','repaired','mitigated_by_policy','false_positive','manual_action_required'),actor=enum('evaluator','admin'),evidence_digests=arr(D),expires_at=nul(T),scope_subject_digest=D),
 'PatchProposal':obj(parent_subject_digest=D,repair_kind=enum('text_only','policy_only','combined'),edits=arr(edit),policy_digest=nul(D)),
 'PatchApplication':obj(parent_subject_digest=D,candidate_subject_digest=D,proposal_digest=D,changed_paths=arr(S),cumulative_changed_bytes=I,cumulative_net_growth_bytes=I,result_file_digests=arr(obj(path=S,bytes_digest=D)),policy_digest=D),
 'ScannerReport':obj(profile_digest=D,scanner_version=S,status=enum('complete','incomplete'),upstream_exit_code=I,raw_report_digest=nul(D),analyzers=arr(obj(analyzer_id=S,status=enum('completed','not_applicable','failed','unknown'),reason=nul(S),evidence_digest=nul(D))),finding_digests=arr(D)),
 'RegistryEntry':obj(project_id=S,profile_id=S,subject_digest=D,evaluation_attestation_digest=D,source_commit_sha={'type':'string','pattern':'^[0-9a-f]{40}$'},generation={'type':'integer','minimum':1},eligibility=enum('eligible','revoked','expired','stale'),trust_revision={'type':'integer','minimum':1}),
 'Campaign':obj(campaign_id=S,project_id=S,trigger_digest=D,generation={'type':'integer','minimum':1},submitted_subject_digest=D,finalist_subject_digest=nul(D),plan_digest=nul(D),state=enum('queued','importing','scanning','dev_evaluating','patching','finalist_frozen','protected_building','protected_evaluating','judging','completed','cancelled','incomplete'),reason_code=nul(S)),
 'Lease':obj(campaign_id=S,run_id=S,worker_id=S,fencing_token={'type':'integer','minimum':1},expires_at=T,state=enum('active','expired','revoked')),
 'ApprovalRecord':obj(approval_id=S,authorization_domain_digest=D,contract_digest=D,factory_rule_digest=D,config_digest=D,issuer={'const':'administrator'},issued_at=T,expires_at=nul(T),trust_revision={'type':'integer','minimum':1},state=enum('active','revoked')),
 'ValidationReceipt':obj(receipt_id=S,binding=endpoint,input_snapshot_digest=D,check_set_id=S,validator_digest=D,issued_at=T,expires_at=T,run_deadline=T,approval_expiry=nul(T),trust_revision={'type':'integer','minimum':1}),
 'ActionGrant':obj(grant_ref=S,binding=endpoint,validation_receipt_digest=D,action_digest=D,approval_digest=D,issued_at=T,expires_at=T,receipt_expiry=T,run_deadline=T,approval_expiry=nul(T),state=enum('issued','committed','revoked','expired'),trust_revision={'type':'integer','minimum':1}),
 'ToolCall':{'oneOf':[obj(call_id=S,run_id=S,task_instance_id=S,fencing_token={'type':'integer','minimum':1},tool={'const':n},args=a) for n,a in argdefs.items()]},
 'ToolResult':{'oneOf':[obj(call_id=S,tool={'const':n},outcome={'const':'ok'},data=a) for n,a in successdefs.items()]+[obj(call_id=S,tool=S,outcome={'const':'error'},error_code=enum('unknown_tool','invalid_args','denied','approval_required','not_found','version_conflict','validation_failed','expired','cancelled','stale_fence','budget_exhausted','skipped_after_failure','runtime_error'),retryable=B)]},
 'RPCRequest':{'oneOf':[obj(request_id=S,method={'const':n},campaign_id=S,fencing_token=I,input_digest=D,deadline=T) for n in ['scanner.scan','generator.generate','runtime.execute','evaluator.evaluate','patcher.propose','applicator.apply','gate.decide','registry.promote','controller.cancel','plugin.handshake']]},
 'RPCResponse':obj(request_id=S,status=enum('ok','error','cancelled'),output_digest=nul(D),error_code=nul(enum('unsupported_api','invalid_input','cancelled','deadline_exceeded','stale_fence','unavailable','incomplete_evidence')),retryable=B),
 'PluginManifest':obj(plugin_id=S,api_major={'const':4},plugin_digest=D,methods=arr(S,1),request_kinds=arr(S,1),response_kinds=arr(S,1),trusted_role=enum('scanner','generator','runtime','evaluator','patcher','applicator','gate','registry'),memory_limit_bytes={'type':'integer','minimum':1},timeout_ms={'type':'integer','minimum':1}),
 'ModelConfig':obj(model_id={'const':'Qwen/Qwen3.8-27B-FP8'},requested_precision={'const':'FP8'},backend=enum('sglang','vllm','ollama'),backend_version=S,weights_digest=nul(D),tokenizer_digest=nul(D),template_digest=nul(D),service_image_digest=nul(D),context_tokens={'const':16384},output_tokens={'const':2048},concurrency={'const':1},thinking={'const':True},seed_support=enum('supported','unsupported','unverified'),seed=nul(I),calibration_digest=nul(D),ready=B,model_revision=nul(S),backend_commit=nul(S),returned_model_version=nul(S),tool_parser={'const':'qwen3_coder'},reasoning_parser={'const':'qwen3'},temperature={'type':'number','minimum':0,'maximum':2},top_p={'type':'number','exclusiveMinimum':0,'maximum':1},top_k=I,min_p={'type':'number','minimum':0,'maximum':1},presence_penalty={'type':'number','minimum':-2,'maximum':2},kv_cache_dtype=nul(S),ssm_dtype=nul(S),draft_model=nul(S),returned_token_usage=enum('verified','unsupported','unverified'),reasoning_output=enum('separate','inline','unverified')),
 'Metrics':obj(subject_digest=D,required_attack_cases=I,adjudicable_attack_cases=I,exposed_attack_cases=I,incomplete_attack_cases=I,effect_success_cases=I,attempt_success_cases=I,utility_pass_attack_cases=I,safe_robust_utility_cases=I,required_clean_cases=I,utility_pass_clean_cases=I,false_refusal_clean_cases=I,p95_latency_ms=nul(I),latency_sample_count=I)
}
SCHEMA={'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'https://skillloop.local/specs/v2.2/protocol.schema.json','title':'SkillLoop V2.2 API4 normative envelopes','oneOf':[ref(n) for n in DEFS],'$defs':{n:entity(n,b) for n,b in DEFS.items()}}
if __name__=='__main__':
 Path(__file__).resolve().parent.parent.joinpath('protocol.schema.json').write_text(json.dumps(SCHEMA,ensure_ascii=False,indent=2)+'\n')
