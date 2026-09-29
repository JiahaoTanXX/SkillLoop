"""Orders-only protected evaluation. Private evidence never crosses the report API.

Separate frozen snapshot; carries the M6 admission clock and spending prefix.
Delivered/unknown sessions cannot be executed again. Independent Gate is separate.
"""
import argparse, copy, fcntl, json, os, subprocess, sys, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.dgx_m6_repair import CONFIG, REDTEAM, load, save, source_index
from scripts.dgx_m5_development import run_one
from skillloop.protocol import digest_jcs,digest_bytes
from skillloop.families.fixtures import load_example_skill
from skillloop.protection.authority import ProtectionAuthority
from skillloop.protection.suite import compile_private,protected_plan
from skillloop.repair.acceptance import review_profile
from skillloop.repair.budget import SpendingLedger
from skillloop.repair.spending import remaining_capacity
from skillloop.runtime.gateway import ExactDockerTokenizer
from skillloop.protection.runtime import container_execute
from scripts.spec_v22_families import generate_private_suite,validate_private_suite

BASE=Path('/home/asus_gx10/skillloop'); M6=BASE/'m6-n11o'; PROFILE='orders_total'
CONTAINER='skillloop-m7-orders'; DEPLOYMENT='m7-orders-protected-v1'
ROOT=Path(__file__).resolve().parents[1]

def checked(record):
    if record['digest']!=digest_jcs({k:v for k,v in record.items() if k!='digest'}):raise ValueError('digest_binding')
    return record

def prepare(out):
    if out.exists():raise ValueError('protected_activity_already_exists')
    g=checked(load(M6/'m6-gate.json')); row=g['subjects'][PROFILE]; m=load(M6/'manifest.json')
    receipt=checked(load(BASE/'m6-v11-sequence1/orders-profile-acceptance-review.json'))
    if receipt!=review_profile([g],profile=PROFILE,m5_gate_digest=g['baseline_gate_digest']) or not receipt['m7_entry_ready']:
        raise ValueError('profile_acceptance_not_ready')
    spending=checked(load(M6/PROFILE/'closed-development-spending.json')); ledger=load(M6/PROFILE/'spending.json')
    if ledger!=spending['ledger'] or not row['frozen'] or row['freeze']!=load(M6/PROFILE/'freeze.json'):
        raise ValueError('frozen_spending_binding')
    cap=remaining_capacity(ledger,started_at_unix_ms=m['admission_clock']['started_at_unix_ms'],
        at_unix_ms=int(time.time()*1000),planned_attempts=68,auxiliary_seconds=720)
    if cap['admission']!='ready':raise ValueError('remaining_full_capacity_does_not_fit_clock')
    isolation=checked(load(BASE/'m7-orders-model-isolation.json'))
    if not isolation['ready'] or isolation['container']!=CONTAINER:raise ValueError('protected_suite_unavailable')
    current=json.loads(subprocess.check_output(['docker','inspect',CONTAINER]))[0]
    if current['Id']!=isolation['container_id'] or not current['State']['Running']:raise ValueError('model_role_binding')
    out.mkdir(mode=0o700)
    authority=ProtectionAuthority(BASE/'m7-private-authority')
    bundle=generate_private_suite(PROFILE,os.urandom(32))
    oldepochs,oldprojections,oldpayloads=authority.used()
    dev=load(M6/PROFILE/'compiled.json')
    oldpayloads += [x['body']['payload_bytes_digest'] for x in dev['mutations'].values()]
    validation=validate_private_suite(bundle,oldepochs,oldprojections,oldpayloads)
    tokenizer=ExactDockerTokenizer(CONTAINER)
    try: compiled=compile_private(bundle,tokenizer,dev)
    finally: tokenizer.close()
    factory=digest_bytes((ROOT/'specs/v2.2/families/private-suite-factory.json').read_bytes())
    info=m['subjects'][PROFILE]
    subjects={role:{'subject_digest':info[key]['digest'],'skill_digest':digest_bytes(load_example_skill(PROFILE,root=skillroot)),
        'skill_root':str(skillroot),'bundle':info[key]} for role,key,skillroot in (
        ('submitted','submitted_bundle',REDTEAM),('finalist','candidate_bundle',M6/'candidate'))}
    if subjects['finalist']['subject_digest']!=row['subject_digest']:raise ValueError('frozen_subject_changed')
    opaque=authority.create_epoch(campaign=m['campaign_id'],finalist=row['subject_digest'],validation=validation,factory_digest=factory)
    (out/'inputs').mkdir(mode=0o700)
    for slot,data in bundle['inputs'].items():
        p=out/'inputs'/slot;p.write_bytes(data);os.chmod(p,0o600)
    save(out/'compiled.json',compiled);save(out/'plan.json',protected_plan(compiled,subjects,m['campaign_id'],CONFIG,parent=load(M6/PROFILE/'plan-1.json')))
    save(out/'spending.json',ledger)
    manifest={'kind':'M7ProtectedActivity','profile':PROFILE,'campaign_id':m['campaign_id'],'clock':m['admission_clock'],
        'm6_gate_digest':g['digest'],'profile_acceptance_digest':receipt['digest'],'freeze_digest':row['freeze']['digest'],
        'prior_spending_digest':spending['digest'],'config':CONFIG,'source_index':source_index(),
        'epoch_id':bundle['epoch_id'],'opaque_ref':opaque,'factory_digest':factory,'factory_validation':validation,
        'subjects':subjects,'model_isolation_digest':isolation['digest'],'remaining_capacity_at_entry':cap,
        'runtime_role_isolation':'per_run_container_uid_21002_current_request_only',
        'production_ready':False}
    save(out/'manifest.json',manifest)
    save(out/'public-progress.json',{'profile':PROFILE,'phase':'protected','status':'prepared','required_runs':24,
        'actual_attempts':0,'complete':0,'incomplete':0,'security_violations':0,'opaque_ref':opaque})

def worker(out,role,cid,rep,directory):
    m=load(out/'manifest.json'); compiled=load(out/'compiled.json');subject=m['subjects'][role]
    compiled.update(subject_digest=subject['subject_digest'],skill_digest=subject['skill_digest'])
    inputs={p.name:p.read_bytes() for p in (out/'inputs').iterdir()}
    run_one(cid,rep,directory,compiled_suite=compiled,skill_root=Path(subject['skill_root']),campaign_id=m['campaign_id'],
        runtime_config=m['config'],execution_plan=load(out/'plan.json'),inputs_override=inputs,
        deployment_epoch=DEPLOYMENT,tokenizer_container=CONTAINER,approval_factory_digest=m["factory_digest"],runtime_uid=21002,runtime_executor=container_execute)
    data=load(directory/'result.json');data['runner_source_digest']=digest_jcs(source_index());save(directory/'result.json',data)

def run(out):
    lock=open(out/'run.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    m=load(out/'manifest.json')
    if m['source_index']!=source_index():raise ValueError('runtime_source_changed')
    ledger=SpendingLedger(out/'spending.json',victim_seconds=265,campaign_started_at=m['clock']['started_at_unix_ms']/1000)
    authority=ProtectionAuthority(BASE/'m7-private-authority');plan=load(out/'plan.json');progress=load(out/'public-progress.json')
    for index,item in enumerate(i for i in plan['body']['items'] if i['phase']=='protected'):
        role=item['subject_role'];rep=item['repetition_index']
        cid=next(k for k,c in load(out/'compiled.json')['cases'].items() if c['digest']==item['case_digest'])
        directory=out/'runs'/role/(str(index).zfill(2))
        key=digest_jcs([DEPLOYMENT,m['campaign_id'],m['epoch_id'],item['subject_digest'],item['case_digest'],rep])
        if authority.state(key):
            raise ValueError('existing_protected_session_recover_only')
        cap=remaining_capacity(ledger.read(),started_at_unix_ms=m['clock']['started_at_unix_ms'],at_unix_ms=int(time.time()*1000),
            planned_attempts=68,auxiliary_seconds=600)
        if cap['admission']!='ready':raise ValueError('remaining_full_capacity_does_not_fit_clock')
        authority.reserve(DEPLOYMENT,m['campaign_id'],m['epoch_id'],item['subject_digest'],item['case_digest'],rep)
        ledger.consume('protected.'+item['item_id'],0)
        # Conservative delivery: a crash after this point may have delivered; never retry.
        authority.transition(key,'reserved','delivered');started=time.monotonic()
        try:
            p=subprocess.run([sys.executable,__file__,'worker','--output',str(out),'--role',role,'--case',cid,
                '--rep',str(rep),'--directory',str(directory)],capture_output=True,timeout=265)
            code,stderr=p.returncode,p.stderr
        except subprocess.TimeoutExpired as e:code,stderr=124,e.stderr or b''
        directory.mkdir(mode=0o700,parents=True,exist_ok=True)
        (directory/'worker-stderr.log').write_bytes(stderr);os.chmod(directory/'worker-stderr.log',0o600)
        save(directory/'timing.json',{'elapsed_seconds':time.monotonic()-started,'exit_code':code,'item_id':item['item_id'],
            'plan_digest':plan['digest'],'session_key':key,'index':index})
        progress['actual_attempts']+=1
        if (directory/'result.json').is_file():
            r=load(directory/'result.json')['result'];b=r['body'];authority.transition(key,'delivered','complete',r['digest'])
            progress['complete']+=int(b['coverage_complete']);progress['incomplete']+=int(not b['coverage_complete'])
            progress['security_violations']+=int(b['security_violation'])
        else:authority.transition(key,'delivered','unknown');progress['incomplete']+=1
        progress.update(status='running',updated_at_unix_ms=int(time.time()*1000));save(out/'public-progress.json',progress)
    progress['status']='awaiting_independent_gate';save(out/'public-progress.json',progress)
    save(out/'execution-closed.json',{'finished_at_unix_ms':int(time.time()*1000),'ledger':ledger.read(),
        'required_runs':24,'actual_attempts':progress['actual_attempts']})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('operation',choices=['prepare','run','worker']);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--role');p.add_argument('--case');p.add_argument('--rep',type=int);p.add_argument('--directory',type=Path);a=p.parse_args()
    os.umask(0o077)
    try:
        if a.operation=='worker':worker(a.output,a.role,a.case,a.rep,a.directory)
        else:globals()[a.operation](a.output)
    except Exception:
        if a.operation!='worker' and a.output.exists():save(a.output/'failure-status.json',{'status':'held','reason':'protection_operation_failed','operation':a.operation,'at_unix_ms':int(time.time()*1000)})
        raise
