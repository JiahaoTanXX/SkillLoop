"""Strict control-plane handoffs, separate from core orchestration RPC envelopes."""
import json
from pathlib import Path
P=Path(__file__).resolve().parent
S={'type':'string','minLength':1,'maxLength':256};I={'type':'integer','minimum':0,'maximum':9007199254740991};B={'type':'boolean'}
D={'type':'string','pattern':'^sha256:[0-9a-f]{64}$'};T={'type':'string','format':'date-time'}
def obj(**fields):return {'type':'object','properties':fields,'required':list(fields),'additionalProperties':False}
def arr(value):return {'type':'array','items':value}
def nullable(value):return {'anyOf':[value,{'type':'null'}]}
def enum(*v):return {'enum':list(v)}
VERDICT=enum('pass','fail','needs_contract','inconclusive')
METHODS={}
def method(name,output,**params):METHODS[name]={'params':obj(**params),'result_kind':output}
method('activate_approval','ApprovalResult',approval_digest=D,expected_trust_revision=I)
method('revoke_approval','ApprovalResult',approval_digest=D,expected_trust_revision=I)
method('start_run','Lease',run_request_digest=D,task_binding_digest=D)
method('cancel_run','CancellationResult',run_id=S,expected_fence=I,reason=S)
method('recover_operation','RecoveryResult',run_id=S,tool=S,idempotency_key=S)
method('reserve_campaign','CampaignInspection',campaign_digest=D,plan_digest=D)
method('register_call_batch','RegistrationResult',run_id=S,fence=I,response_id=S,calls=arr(obj(call_digest=D,native_tool_call_id=S,batch_index=I)))
for name in ['read_resource','build_artifact','write_artifact','validate_artifact','prepare_publication','publish_artifact']:
 method(name,'ToolResult',call_digest=D)
method('record_terminal_output','ObjectAck',run_id=S,fence=I,raw_output_digest=D)
method('create_epoch','EpochRecord',campaign_digest=D,finalist_digest=D,factory_profile_digest=D)
method('reserve_protected_session','ProtectedSession',epoch_record_digest=D,plan_digest=D)
method('resolve_private_case','PrivateCaseAccess',session_digest=D,opaque_case_ref=S,run_id=S)
method('read_private_evidence','EvidenceIndex',session_digest=D,evidence_index_digest=D)
method('read_authoritative_manifest','SuiteManifest',campaign_digest=D)
method('write_gate_result','ObjectAck',gate_result_digest=D)
method('read_dev_evidence','EvidenceIndex',campaign_digest=D,evidence_index_digest=D)
method('write_attack_proposal','ObjectAck',attack_plan_digest=D)
method('write_patch_proposal','ObjectAck',patch_proposal_digest=D)
method('read_import_snapshot','SourceSnapshot',snapshot_digest=D)
method('write_scan_report','ObjectAck',scanner_report_digest=D)
method('read_public_projection','PublicReport',campaign_digest=D)
method('approve_domain','ApprovalResult',domain_digest=D,contract_digest=D,config_digest=D,factory_profile_digest=D,expires_at=nullable(T))
method('approve_factory','ApprovalResult',factory_profile_digest=D,expires_at=nullable(T))
method('review_finding','FindingDisposition',disposition_digest=D)
method('retire_history','HistoryRetirement',history_case_digest=D,reason=enum('equivalent_merge','not_applicable','project_retired'),evidence_digests=arr(D))
method('export','ArchiveManifest',campaign_digest=D,destination_ref=S)
method('archive','ArchiveResult',campaign_digest=D,archive_manifest_digest=D)
method('restore','RestoreResult',archive_manifest_digest=D,new_deployment_epoch=S)
method('infer_current_context','InferenceResult',inference_request_digest=D)
method('get_operation','OperationStatus',operation_ref=S)

DEFS={
'OperationTicket':obj(operation_ref=S,owner_role=S,deadline=T,expected_result_kind=S),
'OperationStatus':obj(operation_ref=S,state=enum('accepted','running','completed','failed','cancelled'),result_kind=nullable(S),result_digest=nullable(D),error_code=nullable(S)),
'DeploymentLock':obj(deployment_epoch=S,platform=enum('linux-aarch64-dgx-spark'),driver_version=S,cuda_version=S,container_runtime_version=S,model_config_digest=D,scanner_image_digest=D,scanner_dependency_lock_digest=D,scanner_rules_digest=D,offline_intelligence_digest=D,calibration_report_digest=D,ready=B),
'PublicReport':obj(campaign_public_ref=S,submitted_verdict=VERDICT,candidate_verdict=nullable(VERDICT),coverage=enum('complete','incomplete'),reason_codes=arr(S),evidence_opaque_refs=arr(S),repair_value=enum('demonstrated_in_tested_scope','repair_value_not_demonstrated','not_applicable')),
'CampaignInspection':obj(campaign_public_ref=S,state=S,generation=I,qualification=enum('eligible','promoted','revoked','expired','stale','cancelled','none'),report_digest=nullable(D)),
'ApprovalResult':obj(operation_id=S,approval_ref=S,effective_trust_revision=I,state=enum('active','revoked'),committed_at=T,expires_at=nullable(T)),
'HardenResult':obj(campaign_public_ref=S,verdict=VERDICT,parent_subject_digest=D,candidate_subject_digest=nullable(D),patch_application_digest=nullable(D),reason_codes=arr(S)),
'HistoryRetirement':obj(case_digest=D,reason=enum('equivalent_merge','not_applicable','project_retired'),admin_evidence_digests=arr(D),retired_at=T),
'CancellationResult':obj(campaign_public_ref=S,run_id=nullable(S),effective_fence=I,committed_at=T),
'ArchiveManifest':obj(campaign_public_ref=S,source_deployment_epoch=S,encrypted_bundle_digest=D,evidence_manifest_digest=D,created_at=T),
'ArchiveResult':obj(archive_manifest_digest=D,qualification_withdrawn=B,local_inactive_removed=B),
'RestoreResult':obj(archive_manifest_digest=D,new_deployment_epoch=S,old_credentials_invalidated={'const':True},old_attestations_invalidated={'const':True},requires_full_reevaluation={'const':True}),
'CalibrationReport':obj(deployment_epoch=S,model_config_digest=D,scanner_lock_digest=D,probe_records=arr(obj(probe_id=S,profile_id=S,raw_trace_digest=D,peak_memory_bytes=I,input_tokens=I,output_tokens=I,elapsed_ms=I,verdict=VERDICT)),ready=B),
'ObjectAck':obj(object_kind=S,object_digest=D,committed_at=T),
'RegistrationResult':obj(run_id=S,fence=I,registered_call_digests=arr(D),consumed_calls=I,remaining_calls=I),
'RecoveryResult':obj(run_id=S,state=enum('committed','proven_not_started','unknown'),tool_result_digest=nullable(D)),
'EpochRecord':obj(campaign_digest=D,epoch_id=S,factory_profile_digest=D,private_suite_digest=D,created_at=T,sealed={'const':True}),
'ProtectedSession':obj(campaign_digest=D,epoch_record_digest=D,plan_digest=D,session_id=S,state=enum('reserved','active','complete','incomplete','cancelled')),
'PrivateCaseAccess':obj(session_digest=D,case_digest=D,mutation_digest=nullable(D),task_binding_digest=D,expires_at=T),
'InferenceRequest':obj(run_id=S,model_config_digest=D,message_bundle_digest=D,tool_schema_digest=D,round_index=I,output_token_limit={'const':2048}),
'MessageBundle':obj(run_id=S,messages=arr(obj(role=enum('system','user','assistant','tool'),content_blob_digest=D,call_correlation_id=nullable(S))),tokenizer_digest=D,input_tokens=I),
'InferenceResult':obj(run_id=S,raw_response_digest=D,parsed_tool_call_digests=arr(D),final_text_blob_digest=nullable(D),usage_input_tokens=nullable(I),usage_output_tokens=nullable(I),finish_reason=enum('stop','tool_calls','length','error','cancelled'),returned_model_version=S),
'ControlRequest':{'oneOf':[obj(operation_id=S,deadline=T,method={'const':name},params=spec['params']) for name,spec in METHODS.items()]},
'ControlResponse':obj(operation_id=S,status=enum('ok','accepted','error','cancelled'),result_kind=nullable(S),result_digest=nullable(D),error_code=nullable(enum('invalid_args','permission_denied','unresolved_reference','conflict','cancelled','stale_fence','deadline_exceeded','busy','unavailable')),retryable=B)
}
SCHEMA={'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'urn:skillloop:control:4',
 'oneOf':[{'$ref':'#/$defs/'+kind} for kind in DEFS],
 '$defs':{kind:obj(api_major={'const':4},kind={'const':kind},body=body,digest=D) for kind,body in DEFS.items()}}
if __name__=='__main__':
 (P/'control.schema.json').write_text(json.dumps(SCHEMA,ensure_ascii=False,indent=2)+'\n')
 rpc=json.loads((P/'rpc.json').read_text())
 admin=next(r for r in rpc['roles'] if r['role']=='admin')
 if 'export' not in admin['methods']:admin['methods'].append('export')
 for role in rpc['roles']:
  if role['role'] in ('runtime','generator','patcher') and 'infer_current_context' not in role['methods']:role['methods'].append('infer_current_context')
  if role['methods'] and 'get_operation' not in role['methods']:role['methods'].append('get_operation')
 rpc['long_operation_protocol']='acknowledge_accepted_with_OperationTicket_within_10s_then_get_operation; owner/run/role_bound; only_completed_yields_result_digest'
 (P/'rpc.json').write_text(json.dumps(rpc,ensure_ascii=False,indent=2)+'\n')
 data={'spec_version':'2.2','api_major':4,'kind':'ControlMethodRegistry','schema':'control.schema.json',
       'digest_lookup':'authenticated_protected_store_only; content hash never authenticates issuer',
       'request_reply_digest_projection':'JCS({api_major,kind,body}); digest omitted',
       'methods':[{'method':name,'request_params_schema':f'control.schema.json#/$defs/ControlRequest',
                   'result_kind':spec['result_kind'],
                   'allowed_roles':[r['role'] for r in rpc['roles'] if name in r['methods']],
                   'timeout_seconds':10,'async_allowed':name not in ('get_operation','register_call_batch','recover_operation'),
                   'cancellation':'stop_new_effects_then_persist_cancel; late_reply_quarantined'} for name,spec in METHODS.items()]}
 (P/'control-methods.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
