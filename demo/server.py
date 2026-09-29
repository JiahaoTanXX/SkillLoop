"""Loopback-only orders Demo. Only a validated, allowlisted public projection is served."""
import argparse,base64,hmac,json,secrets,sys,threading,time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from demo.profiles import catalog
from demo.submissions import Submissions
from skillloop.ci.decision import decide
from skillloop.protocol import digest_jcs
ROOT=Path(__file__).resolve().parent
EXPERIMENTS_PAUSED=True
PUBLIC=ROOT/'public-report.json'
STATIC={'/orders':('orders.html','text/html; charset=utf-8'),'/hub.js':('hub.js','text/javascript; charset=utf-8'),'/hub.css':('hub.css','text/css; charset=utf-8'),'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
STATIC.update({'/workbench':('workbench.html','text/html; charset=utf-8'),'/workbench.js':('workbench.js','text/javascript; charset=utf-8')})
STATIC.update({'/login':('login.html','text/html; charset=utf-8'),'/login.js':('login.js','text/javascript; charset=utf-8')})
STATIC.update({'/showcase':('showcase.html','text/html; charset=utf-8'),'/showcase.js':('showcase.js','text/javascript; charset=utf-8')})
STATIC.update({'/custom':('custom.html','text/html; charset=utf-8'),'/custom.js':('custom.js','text/javascript; charset=utf-8'),
               '/custom.css':('custom.css','text/css; charset=utf-8')})
TOP_LEVEL={'schema_version','profile','name','campaign_id','scope','data_source','evidence_updated_at','global_m6_accepted',
 'production_ready','submitted','candidate','paired','pair_note','usage','budget','m7','stages','evidence','limitations','other_profiles','api_configuration'}
FORBIDDEN={'payload','payload_utf8','payload_digest','fixture_digest','private_path','private_seed','synthetic_secret','trace','model_response','case_result_matrix','objective_ids'}

def validate_public(value):
    if set(value)!=TOP_LEVEL or value['profile']!='orders_total' or value['scope']!=['orders_total']:
        raise ValueError('public_scope')
    def walk(v):
        if isinstance(v,dict):
            if FORBIDDEN.intersection(v):raise ValueError('private_field')
            for child in v.values():walk(child)
        elif isinstance(v,list):
            for child in v:walk(child)
        elif isinstance(v,str) and any(token in v for token in ('SIM_SECRET_','DEV_ONLY_','/home/asus_gx10')):
            raise ValueError('private_content')
    walk(value)
    allowed_shapes = {
        'evidence': {'candidate_bundle_digest','config_digest','source_index_digest','m6_gate_digest','freeze_digest','profile_acceptance_digest','spending_digest'},
        'm7': {'status','actual_runs','required_runs','accepted','mechanism_tests_passed'},
        'usage': {'model_responses','prompt_tokens','completion_tokens','reasoning_tokens','usage_missing','scope'},
        'paired': {'improved','regressed','unchanged','unknown'},
        'api_configuration': {'model','status','formal_runs','calibration_requests','calibration_elapsed_seconds','prompt_tokens','completion_tokens','raw_reasoning_tokens','cost_limit_rmb','conservative_reserved_rmb','protected_24_runs_forecast_rmb','full_66_runs_forecast_rmb','input_rmb_per_million','output_rmb_per_million','blockers','counts_as_m6_evidence'},
    }
    for name, keys in allowed_shapes.items():
        if set(value[name]) != keys: raise ValueError('public_nested_scope')
    for stage in value['stages']:
        if set(stage) != {'id','number','name','status','label','detail'}: raise ValueError('public_stage_scope')
    if value['api_configuration']['counts_as_m6_evidence'] or value['api_configuration']['formal_runs'] != 0:
        raise ValueError('api_evidence_scope')
    if value['production_ready'] or value['global_m6_accepted']:raise ValueError('unaccepted_claim')
    for role in ('submitted','candidate'):
        row=value[role]
        if row['complete']+row['incomplete']!=row['attempts'] or row['required']!=21:raise ValueError('denominator')
    if sum(value['paired'].values())!=21:raise ValueError('pair_denominator')
    if value['m7']['status']!='sealed' or value['m7']['actual_runs']!=0 or value['m7']['accepted']:raise ValueError('m7_seal')
    return value

def report():
    v=validate_public(json.loads(PUBLIC.read_text()))
    v['local_ci']=decide(submitted_verdict=v['submitted']['verdict'],candidate_verdict=v['candidate']['verdict'],
        m7_accepted=v['m7']['accepted'],source_kind='immutable_snapshot')
    v['public_report_digest']=digest_jcs(v)
    return v

class Handler(BaseHTTPRequestHandler):
    def authenticated(self):
        password=getattr(self.server,'password',None)
        if password is None:return True
        try:
            cookies=SimpleCookie(self.headers.get('Cookie',''));token=cookies.get('skillloop_session')
            with self.server.session_lock:
                if token and self.server.sessions.get(token.value,0)>time.time():return True
            raw=self.headers.get('Authorization','')
            user,provided=base64.b64decode(raw.removeprefix('Basic '),validate=True).decode().split(':',1)
            if user=='demo' and hmac.compare_digest(provided.encode(),password.encode()):return True
        except Exception:pass
        self.send_response(401);self.send_header('WWW-Authenticate','Basic realm="SkillLoop Demo", charset="UTF-8"')
        self.send_header('Content-Length','0');self.end_headers();return False
    def json_response(self,value,code=200):
        raw=json.dumps(value,ensure_ascii=False).encode();self.send_response(code)
        self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        path=urlsplit(self.path).path
        if path in ('/login','/login.js','/style.css'):pass
        elif path in ('/','/orders','/workbench','/showcase','/custom') and self.server.password and not self.headers.get('Cookie') and not self.headers.get('Authorization'):
            self.send_response(303);self.send_header('Location','/login');self.send_header('Content-Length','0');self.end_headers();return
        elif not self.authenticated():return
        if path=='/api/profiles':
            value=catalog(getattr(self.server,'profile_status_root',None),getattr(self.server,'workflow',None))
            value['experiments_paused']=EXPERIMENTS_PAUSED
            self.json_response(value);return
        if path=='/api/submissions':
            submissions=getattr(self.server,'submissions',None)
            if submissions is None:self.json_response({'error_code':'demo_submissions_dgx_only'},503);return
            self.json_response({'submissions':submissions.list(),'experiments_paused':True});return
        if path.startswith('/api/custom'):
            workflow=getattr(self.server,'workflow',None)
            if workflow is None:self.json_response({'error_code':'demo_workflow_dgx_only'},503);return
            try:
                if path=='/api/custom':self.json_response({'jobs':workflow.list_custom()});return
                jid=path.removeprefix('/api/custom/')
                if not jid.startswith('custom-') or len(jid)!=39 or any(c not in '0123456789abcdef' for c in jid[7:]):raise KeyError()
                self.json_response(workflow.get_custom(jid));return
            except KeyError:self.json_response({'error_code':'demo_job_missing'},404);return
        if path=='/api/workflow/default':
            from workflow import DEFAULT_SKILL
            self.json_response({'skill':DEFAULT_SKILL});return
        if path.startswith('/api/workflow'):
            workflow=getattr(self.server,'workflow',None)
            if workflow is None:self.json_response({'error_code':'demo_workflow_dgx_only'},503);return
            try:
                if path=='/api/workflow':self.json_response({'jobs':workflow.list()});return
                jid=path.removeprefix('/api/workflow/')
                is_review=jid.endswith('/review')
                if is_review:jid=jid.removesuffix('/review')
                if not jid.startswith('demo-') or len(jid)!=37 or any(c not in '0123456789abcdef' for c in jid[5:]):raise KeyError()
                if is_review:self.json_response(workflow.review(jid));return
                self.json_response(workflow.get(jid));return
            except KeyError:self.json_response({'error_code':'demo_job_missing'},404);return
            except ValueError:self.json_response({'error_code':'demo_review_unavailable'},503);return
        if path in {'/api/report','/api/check','/api/export'}:
            try:
                r=report();body=r['local_ci'] if path=='/api/check' else r
                raw=json.dumps(body,ensure_ascii=False,indent=2).encode();mime='application/json; charset=utf-8'
            except Exception:
                self.send_error(503,'Public report unavailable');return
        elif path in STATIC:
            file,mime=STATIC[path];raw=(ROOT/'web'/file).read_bytes()
        else:self.send_error(404);return
        self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
        if path=='/api/export':self.send_header('Content-Disposition','attachment; filename="skillloop-orders-report.json"')
        self.end_headers();self.wfile.write(raw)
    def do_POST(self):
        if urlsplit(self.path).path=='/api/login':
            if not self.server.password:self.json_response({'ok':True});return
            try:
                origin=self.headers.get('Origin')
                if self.headers.get('X-SkillLoop-Request')!='1' or (origin and urlsplit(origin).netloc!=self.headers.get('Host')):raise ValueError()
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=1024:raise ValueError()
                value=json.loads(self.rfile.read(length));password=value.get('password','')
                if not isinstance(password,str) or not hmac.compare_digest(password.encode(),self.server.password.encode()):raise ValueError()
                token=secrets.token_urlsafe(32)
                with self.server.session_lock:
                    self.server.sessions={k:v for k,v in self.server.sessions.items() if v>time.time()}
                    self.server.sessions[token]=time.time()+7200
                self.send_response(200);self.send_header('Set-Cookie','skillloop_session='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=7200')
                self.send_header('Content-Length','2');self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(b'{}')
            except Exception:self.json_response({'error_code':'demo_login_failed'},401)
            return
        if not self.authenticated():return
        path=urlsplit(self.path).path
        if path in ('/api/workflow','/api/custom') and EXPERIMENTS_PAUSED:
            self.json_response({'error_code':'demo_experiments_paused'},423);return
        if path not in ('/api/workflow','/api/custom','/api/submissions'):self.send_error(405);return
        workflow=getattr(self.server,'workflow',None)
        if path!='/api/submissions' and workflow is None:self.json_response({'error_code':'demo_workflow_dgx_only'},503);return
        origin=self.headers.get('Origin')
        if (self.headers.get('X-SkillLoop-Request')!='1' or self.headers.get('Content-Type')!='application/json' or
            (origin and urlsplit(origin).netloc!=self.headers.get('Host'))):self.send_error(403);return
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=16384:raise ValueError('demo_request_size')
            value=json.loads(self.rfile.read(length))
            if path=='/api/submissions':
                submissions=getattr(self.server,'submissions',None)
                if submissions is None:raise ValueError('demo_submissions_dgx_only')
                self.json_response(submissions.save(value),202);return
            if path=='/api/custom':
                if set(value)!={'skill','task','expected','forbidden','request_key'}:raise ValueError('demo_request_schema')
                job=workflow.start_custom(value['skill'],value['task'],value['expected'],value['forbidden'],value['request_key'])
            else:
                if set(value)!={'skill','request_key'}:raise ValueError('demo_request_schema')
                job=workflow.start(value['skill'],value['request_key'])
            self.json_response(job,202)
        except ValueError as error:
            code=str(error)
            self.json_response({'error_code':code if code.startswith('demo_') else 'demo_request_invalid'},409)
    def log_message(self,*args):pass

def main():
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8765);p.add_argument('--bind',default='127.0.0.1')
    for name in ('private-root','config','ledger','auth-file'):p.add_argument('--'+name,type=Path)
    a=p.parse_args();report()
    if a.bind!='127.0.0.1' and not all((a.private_root,a.config,a.ledger,a.auth_file)):p.error('Public service requires authenticated DGX workflow')
    server=ThreadingHTTPServer((a.bind,a.port),Handler);server.password=None;server.workflow=None
    server.submissions=None
    server.sessions={};server.session_lock=threading.Lock()
    server.profile_status_root=a.private_root/'profile-status' if a.private_root else None
    if a.private_root:
        from workflow import Workflow,DemoAPI
        if not a.auth_file or a.auth_file.stat().st_mode&0o077:p.error('Private authentication file required')
        server.password=a.auth_file.read_text().strip()
        if len(server.password)<16:p.error('Demo authentication password too short')
        server.workflow=Workflow(a.private_root,DemoAPI(a.config,a.ledger))
        server.submissions=Submissions(a.private_root/'submissions')
    print(f'SkillLoop orders Demo: http://{a.bind}:{a.port}',flush=True)
    server.serve_forever()
if __name__=='__main__':main()
