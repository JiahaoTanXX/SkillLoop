"""Independent private M7 reconstruction with API4 execution/attestation chain."""
import argparse,datetime,json,os,sqlite3,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.dgx_m5b_gate import _recompute_run
from scripts.dgx_m6_repair import load,save,source_index
from scripts.dgx_m7_orders import BASE,M6,PROFILE,CONTAINER,DEPLOYMENT,checked
from skillloop.protocol import digest_jcs,digest_bytes,make_envelope
from skillloop.protection.authority import ProtectionAuthority
from skillloop.families.fixtures import load_example_skill
from skillloop.runtime.gateway import ExactDockerTokenizer
from scripts.spec_v22_core import (reduce_case,execution_record,attach_execution_records,evaluate_gate,
    build_ci_result,validate_required_run_manifest,validate_attestation)

def utc(offset=0):return (datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(seconds=offset)).isoformat(timespec='seconds').replace('+00:00','Z')

def gate(out,runtime):
    m=load(out/'manifest.json');plan=load(out/'plan.json');compiled=load(out/'compiled.json');parent=checked(load(M6/'m6-gate.json'))
    if m['source_index']!=source_index(runtime) or m['m6_gate_digest']!=parent['digest']:
        raise ValueError('source_or_parent_binding')
    if m['clock']!=load(M6/'manifest.json')['admission_clock'] or m['freeze_digest']!=parent['subjects'][PROFILE]['freeze']['digest']:
        raise ValueError('clock_or_freeze_binding')
    closed=load(out/'execution-closed.json');state=load(out/'spending.json');prior=checked(load(M6/PROFILE/'closed-development-spending.json'))
    if closed['ledger']!=state or state['executions'][:42]!=prior['ledger']['executions']:
        raise ValueError('spending_prefix_binding')
    expected_keys=[{'item_key':'protected.'+i['item_id'],'attempt':0} for i in plan['body']['items'] if i['phase']=='protected']
    if (state['executions'][42:]!=expected_keys or state['victim_attempts']!=66 or state['retries']!=0 or
        state['charged_wall_seconds']!=66*265 or state['campaign_started_at']!=m['clock']['started_at_unix_ms']/1000 or
        closed['finished_at_unix_ms']-m['clock']['started_at_unix_ms']+600000>28800000):
        raise ValueError('actual_budget_or_clock')
    if plan['body']['parent_plan_digest']!=load(M6/PROFILE/'plan-1.json')['digest']:raise ValueError('plan_parent_binding')
    inputs={p.name:p.read_bytes() for p in (out/'inputs').iterdir()}
    authority=ProtectionAuthority(BASE/'m7-private-authority');tokenizer=ExactDockerTokenizer(CONTAINER)
    run_ids=set();task_ids=set();cases=[];records={};results={};gates={};attestations={};summaries={};contexts={}
    usage={'model_responses':0,'prompt_tokens':0,'completion_tokens':0,'reasoning_tokens':0,'usage_missing':0}
    try:
        for role,subject in m['subjects'].items():
            subject_compiled={**compiled,'subject_digest':subject['subject_digest'],'skill_digest':subject['skill_digest']}
            skill=load_example_skill(PROFILE,root=Path(subject['skill_root']))
            if digest_bytes(skill)!=subject['skill_digest']:raise ValueError('frozen_skill_changed')
            per_case={cid:[] for cid in compiled['cases']};per_record={cid:[] for cid in compiled['cases']};entries=[]
            summary={'required_runs':33,'private_required_runs':12,'private_attempts':0,'private_complete':0,'private_incomplete':0,
                'private_security_violations':0,'private_utility_failures':0,'private_elapsed_seconds':0}
            for item in [i for i in plan['body']['items'] if i['subject_digest']==subject['subject_digest']]:
                cid=next(cid for cid,c in compiled['cases'].items() if c['digest']==item['case_digest'])
                rep=item['repetition_index'];case=compiled['cases'][cid]
                if item['phase']=='dev':
                    # Parent raw evidence was independently audited before M7. Preserve original request/suite identity.
                    from scripts.dgx_m5b_attack import run_directory
                    base=M6/'submitted' if role=='submitted' else M6
                    p=run_directory(base,PROFILE,cid,rep,0)/'result.json'
                    data=load(p);r=data['result']
                    if r['body']['subject_digest']!=subject['subject_digest'] or r['body']['case_digest']!=case['digest']:
                        raise ValueError('parent_development_identity')
                else:
                    index=next(index for index,i in enumerate(i for i in plan['body']['items'] if i['phase']=='protected') if i['item_id']==item['item_id'])
                    folder=out/'runs'/role/str(index).zfill(2);p=folder/'result.json';summary['private_attempts']+=1
                    timing=load(folder/'timing.json');summary['private_elapsed_seconds']+=timing['elapsed_seconds']
                    key=digest_jcs([DEPLOYMENT,m['campaign_id'],m['epoch_id'],subject['subject_digest'],case['digest'],rep])
                    if timing['session_key']!=key or timing['plan_digest']!=plan['digest']:raise ValueError('session_timing_binding')
                    if not p.exists():summary['private_incomplete']+=1;entries.append({'item_id':item['item_id'],'run_record_digests':[]});continue
                    data=load(p)
                    if data['runner_source_digest']!=digest_jcs(m['source_index']):raise ValueError('runner_source_binding')
                    r=_recompute_run(p,profile=PROFILE,case_id=cid,repetition=rep,attempt=0,case=case,compiled=subject_compiled,
                        suite=compiled['suite'],plan=plan,run_ids=run_ids,task_ids=task_ids,tokenizer=tokenizer,
                        expected_config=m['config'],inputs_override=inputs,deployment_epoch=DEPLOYMENT)
                    if authority.state(key)!=('complete',r['digest']):raise ValueError('authority_delivery_binding')
                    summary['private_complete']+=int(r['body']['coverage_complete']);summary['private_incomplete']+=int(not r['body']['coverage_complete'])
                    summary['private_security_violations']+=int(r['body']['security_violation']);summary['private_utility_failures']+=int(r['body']['utility_status']=='fail')
                    context_files=list((folder/'evidence/contexts').iterdir())
                    if not context_files:raise ValueError('actual_context_missing')
                    for c in context_files:
                        messages=load(c)
                        if len(messages)<2 or not messages[1].get('content','').startswith(skill.decode()+'\n\nTask input bindings: '):raise ValueError('skill_not_in_actual_context')
                    for trace in (folder/'evidence').glob('*.jsonl'):
                        for line in trace.read_text().splitlines():
                            event=json.loads(line)
                            if event.get('type')=='model_response':
                                raw=event['response'];u=raw.get('usage') or {}
                                if u.get('reasoning_tokens')!=0:raise ValueError('reasoning_tokens_not_zero')
                                usage['model_responses']+=1
                                for k in ('prompt_tokens','completion_tokens','reasoning_tokens'):
                                    if type(u.get(k)) is not int:raise ValueError('raw_usage_missing')
                                    usage[k]+=u[k]
                rec=execution_record(data['run_request'],r,data['evidence_index'],data['task_binding'])
                records[rec['digest']]=rec;results[r['digest']]=r;per_case[cid].append(r);per_record[cid].append(rec)
                entries.append({'item_id':item['item_id'],'run_record_digests':[rec['digest']]})
            selected=[]
            for cid,rs in per_case.items():
                if rs:selected.append(attach_execution_records(reduce_case(rs,compiled['cases'][cid]),per_record[cid],results))
            cases.extend(selected)
            # Cohosted controller/runtime harness lacks the production UID boundary.
            # Preserve measured outcomes but withhold full M7 qualification.
            context=make_envelope('GateContext',{'contract_approved':True,'approval_digest':None,'runtime_verified':False,
                'source_immutable':True,'scanner_complete':True,'authorization_verified':True,'evidence_verified':True,
                'unresolved_high_findings':0,'definite_failures':[],
                'incomplete_reasons':['production_runtime_role_boundary_unverified'],'config_digest':plan['body']['config_digest']})
            contexts[role]=context;g=evaluate_gate(subject['subject_digest'],compiled['suite'],plan,selected,context)
            gates[role]=g;summaries[role]={**summary,'verdict':g['body']['verdict'],'coverage':g['body']['coverage']}
            if all(e['run_record_digests'] for e in entries):
                manifest=make_envelope('RequiredRunManifest',{'subject_digest':subject['subject_digest'],'plan_digest':plan['digest'],'entries':entries})
                validate_required_run_manifest(manifest,plan,records,results)
                a=make_envelope('EvaluationAttestation',{'subject_digest':subject['subject_digest'],'plan_digest':plan['digest'],
                    'suite_digest':compiled['suite']['digest'],'config_digest':plan['body']['config_digest'],
                    'required_run_manifest_digest':manifest['digest'],'gate_result_digest':g['digest'],'verdict':g['body']['verdict'],
                    'issuer':'local-authority','issued_at':utc(),'expires_at':utc(86400),'trust_revision':1})
                validate_attestation(a,g,manifest,plan,compiled['suite'],records,results,list(compiled['cases'].values()),context)
                attestations[role]=a;save(out/(role+'-required-run-manifest.json'),manifest)
    finally:tokenizer.close()
    ci=build_ci_result(gates['submitted'],gates['finalist'],cases)
    private={'kind':'M7IndependentGate','campaign_id':m['campaign_id'],'parent_m6_gate_digest':parent['digest'],
        'manifest_digest':digest_jcs(m),'subjects':gates,'contexts':contexts,'case_results':cases,'execution_records':records,
        'result_index':results,'attestations':attestations,'ci_result':ci,'actual_usage':usage,'spending':closed,
        'review_status':'pending_runtime_role_boundary','production_ready':False}
    private['digest']=digest_jcs(private);save(out/'acceptance-review.json',private)
    public={'kind':'OrdersDemoPublicReport','profile':PROFILE,'campaign_public_ref':m['campaign_id'],
        'opaque_ref':m['opaque_ref'],'status':'held','review_status':private['review_status'],
        'protected_aggregate':summaries,'usage':usage,'ci_exit_code':ci['body']['exit_code'],
        'frozen':True,'actual_victim_attempts':66,'retry_count':0,
        'clock_started_at_unix_ms':m['clock']['started_at_unix_ms'],'finished_at_unix_ms':closed['finished_at_unix_ms'],
        'wall_limit_seconds':28800,'production_ready':False,'github_check_published':False,
        'limitations':['original_development_pair_has_two_incomplete_runs','production_runtime_role_boundary_unverified',
            'github_integration_not_accepted','single_profile_scope']}
    public['digest']=digest_jcs(public);save(out/'public-report.json',public)
    print(json.dumps({'status':public['status'],'review_status':public['review_status'],'subjects':summaries,'usage':usage}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--runtime-source',required=True,type=Path);a=p.parse_args()
    os.umask(0o077);gate(a.output,a.runtime_source)
