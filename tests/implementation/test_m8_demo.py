import base64,copy,http.cookiejar,importlib.util,json,sys,tempfile,threading,unittest,urllib.error,urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from skillloop.ci.decision import decide
from skillloop.ci.registry import LocalRegistry
from skillloop.protection.api_budget import APIBudget
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('orders_demo',ROOT/'demo/server.py');demo=importlib.util.module_from_spec(spec);spec.loader.exec_module(demo)
sys.path.insert(0,str(ROOT/'demo'))
from workflow import aggregate,custom_aggregate,Workflow
from demo.profiles import catalog,validate_status
from demo.submissions import Submissions

class ProfileCatalogTests(unittest.TestCase):
    def status(self):
        import time
        return dict(schema_version=1,profile='refunds_total',observed_at=time.time(),state='blocked_pre_matrix',
                    stage='业务校准',summary='校准尚未接受。',activity_id=None,matrix_attempts=0,
                    matrix_required=None,complete=0,incomplete=0,security_violations=None,
                    gate='rejected',frozen=False,blockers=['用量字段缺失'])
    def test_three_profiles_and_unknown_is_not_not_started(self):
        value=catalog();self.assertEqual(len(value['profiles']),3)
        self.assertEqual(value['profiles'][1]['live']['state'],'unknown')
        self.assertFalse(value['formal_global_accepted'])
        self.assertEqual(value['profiles'][0]['live']['complete'],40)
    def test_status_refresh_and_stale_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);v=self.status();file=root/'refunds_total.json';file.write_text(json.dumps(v))
            self.assertEqual(catalog(root)['profiles'][1]['live']['gate'],'rejected')
            v.update(observed_at=v['observed_at']-400,summary='较早观测。');file.write_text(json.dumps(v))
            row=catalog(root)['profiles'][1];self.assertTrue(row['stale']);self.assertEqual(row['live']['summary'],'较早观测。')
    def test_invalid_private_and_denominator_fail_closed(self):
        v=self.status();v['summary']='/home/asus_gx10/private'
        with self.assertRaises(ValueError):validate_status(v,'refunds_total')
        v=self.status();v['complete']=1
        with self.assertRaises(ValueError):validate_status(v,'refunds_total')
        v=self.status();v['payload']='forbidden'
        with self.assertRaises(ValueError):validate_status(v,'refunds_total')
    def test_malformed_status_and_missing_are_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'refunds_total.json').write_text('{broken')
            row=catalog(Path(tmp))['profiles'][1]
            self.assertEqual(row['source'],'unavailable');self.assertTrue(row['stale'])

class PausedSubmissionTests(unittest.TestCase):
    def test_private_draft_idempotent_and_public_projection(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);registry=Submissions.__new__(Submissions)
            registry.root=root;registry.db=root/'submissions.sqlite';registry.lock=threading.Lock()
            with registry.connect() as db:
                db.execute('CREATE TABLE submissions(id TEXT PRIMARY KEY, request_key TEXT UNIQUE, public TEXT NOT NULL)')
            value={'skill':'A text-only Skill with ordinary rules.','task':'Return OK','expected':'OK',
                   'forbidden':'MARKER','request_key':'12345678-1234-4234-8234-123456789abc'}
            first=registry.save(value);self.assertEqual(registry.save(value),first)
            self.assertEqual(len(registry.list()),1)
            self.assertNotIn('skill',first);self.assertFalse(first['experiment_started'])
            path=root/first['id']/'input.json';self.assertEqual(path.stat().st_mode&0o077,0)
            self.assertEqual(json.loads(path.read_text())['skill'],value['skill'])
            bad={**value,'request_key':'new','skill':'x'}
            with self.assertRaises(ValueError):registry.save(bad)

class CIDemoTests(unittest.TestCase):
    def test_failed_submission_stays_failed(self):
        d=decide(submitted_verdict='fail',candidate_verdict='pass',m7_accepted=False,source_kind='immutable_snapshot')
        self.assertEqual(d['exit_code'],1);self.assertEqual(d['candidate_decision'],'inconclusive');self.assertFalse(d['publishable'])
    def test_pass_requires_protected_gate(self):
        d=decide(submitted_verdict='pass',candidate_verdict='pass',m7_accepted=False,source_kind='git_commit',source_head='a'*40)
        self.assertEqual(d['exit_code'],4);self.assertFalse(d['publishable'])
    def test_invalid_head(self):
        with self.assertRaises(ValueError):decide(submitted_verdict='pass',candidate_verdict='pass',m7_accepted=True,source_kind='git_commit',source_head='fake')
    def test_failure_cannot_be_publishable_even_with_m7(self):
        d=decide(submitted_verdict='fail',candidate_verdict='pass',m7_accepted=True,source_kind='git_commit',source_head='a'*40)
        self.assertEqual(d['exit_code'],1);self.assertFalse(d['publishable'])
    def test_m7_requires_boolean(self):
        with self.assertRaises(ValueError):decide(submitted_verdict='pass',candidate_verdict='pass',m7_accepted='false',source_kind='immutable_snapshot')
    def test_exit_code_matrix(self):
        for verdict,code in [('pass',0),('fail',1),('needs_contract',3),('inconclusive',4)]:
            d=decide(submitted_verdict=verdict,candidate_verdict='pass',m7_accepted=True,source_kind='immutable_snapshot')
            self.assertEqual(d['exit_code'],code);self.assertFalse(d['publishable'])
    def test_generation_dedup_and_stale_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=LocalRegistry(Path(tmp)/'state.sqlite');first=r.trigger('orders','a'*40,'config')
            self.assertTrue(r.trigger('orders','a'*40,'config')['deduplicated'])
            second=r.trigger('orders','b'*40,'config');self.assertEqual(second['generation'],2)
            with self.assertRaises(ValueError):r.complete('orders','a'*40,'config',1,first['campaign'],{'verdict':'pass'})
            receipt=r.complete('orders','b'*40,'config',2,second['campaign'],{'verdict':'fail'})
            self.assertEqual(receipt,r.complete('orders','b'*40,'config',2,second['campaign'],{'verdict':'fail'}))
            with self.assertRaises(ValueError):r.complete('orders','b'*40,'config',2,second['campaign'],{'verdict':'pass'})
    def test_renewal_requires_prior(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=LocalRegistry(Path(tmp)/'state.sqlite')
            with self.assertRaises(ValueError):r.trigger('p','a'*40,'c','renewal')
    def test_configuration_and_verified_renewal(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=LocalRegistry(Path(tmp)/'state.sqlite');first=r.trigger('p','a'*40,'c')
            receipt=r.complete('p','a'*40,'c',1,first['campaign'],{'verdict':'inconclusive'})
            second=r.trigger('p','a'*40,'new','configuration');self.assertEqual(second['generation'],2)
            with self.assertRaises(ValueError):r.trigger('p','a'*40,'new','renewal','made-up')
            with self.assertRaises(ValueError):r.trigger('other','a'*40,'new','renewal',receipt)
            third=r.trigger('p','a'*40,'new','renewal',receipt);self.assertEqual(third['generation'],3)
            self.assertTrue(r.trigger('p','a'*40,'new','renewal',receipt)['deduplicated'])
    def test_restart_preserves_receipts_and_fencing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'state.sqlite';r=LocalRegistry(path);first=r.trigger('p','a'*40,'c')
            r.complete('p','a'*40,'c',1,first['campaign'],{'verdict':'fail'})
            recovered=LocalRegistry(path);self.assertTrue(recovered.trigger('p','a'*40,'c')['deduplicated'])
            with self.assertRaises(ValueError):recovered.complete('p','a'*40,'c',1,first['campaign'],{'verdict':'pass'})
            recovered.trigger('p','b'*40,'c')
            with self.assertRaises(ValueError):r.complete('p','a'*40,'c',1,first['campaign'],{'verdict':'fail'})
    def test_public_denominators(self):
        r=demo.report();self.assertEqual(r['candidate']['complete'],21);self.assertEqual(r['local_ci']['exit_code'],1)
        invalid=copy.deepcopy(json.loads(demo.PUBLIC.read_text()));invalid['submitted']['complete']=20
        with self.assertRaises(ValueError):demo.validate_public(invalid)
    def test_private_field_and_raw_content_rejected(self):
        invalid=copy.deepcopy(json.loads(demo.PUBLIC.read_text()));invalid['evidence']['private_path']='hidden'
        with self.assertRaises(ValueError):demo.validate_public(invalid)
        invalid=copy.deepcopy(json.loads(demo.PUBLIC.read_text()));invalid['pair_note']='/home/asus_gx10/private'
        with self.assertRaises(ValueError):demo.validate_public(invalid)
    def test_no_unaccepted_claim(self):
        invalid=copy.deepcopy(json.loads(demo.PUBLIC.read_text()));invalid['m7']['accepted']=True
        with self.assertRaises(ValueError):demo.validate_public(invalid)

class CostTests(unittest.TestCase):
    def test_unknown_charge_is_kept_and_replay_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'cost.sqlite';b=APIBudget(p,input_rate='1',output_rate='4',limit_rmb='10.00')
            b.reserve('r1',1000000,1000000);self.assertEqual(b.spent_micro(),5000000)
            recovered=APIBudget(p,input_rate='1',output_rate='4',limit_rmb='10.00')
            with self.assertRaises(ValueError):recovered.reserve('r1',1,1)
            with self.assertRaises(ValueError):recovered.reserve('r2',2000000,1000000)
    def test_reconcile_actual_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=APIBudget(Path(tmp)/'cost.sqlite',input_rate='0.8',output_rate='2',limit_rmb='10.00')
            b.reserve('r',1000,1000);self.assertEqual(b.finish('r',100,100),280)
            with self.assertRaises(ValueError):b.finish('r',100,100)
    def test_rates_are_immutable(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'cost.sqlite';APIBudget(p,input_rate='1',output_rate='2')
            with self.assertRaises(ValueError):APIBudget(p,input_rate='0',output_rate='0')

class HTTPDemoTests(unittest.TestCase):
    def setUp(self):
        self.server=ThreadingHTTPServer(('127.0.0.1',0),demo.Handler)
        self.server.password='local-test-login-only';self.server.workflow=None
        self.server.sessions={};self.server.session_lock=threading.Lock()
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base='http://127.0.0.1:'+str(self.server.server_port)
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
    def test_authentication_cookie_and_private_routes(self):
        with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(self.base+'/api/report')
        self.assertEqual(error.exception.code,401)
        cookies=http.cookiejar.CookieJar();opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
        request=urllib.request.Request(self.base+'/api/login',data=json.dumps({'password':self.server.password}).encode(),headers={'Content-Type':'application/json','X-SkillLoop-Request':'1'})
        with opener.open(request) as response:self.assertEqual(response.status,200)
        with opener.open(self.base+'/api/report') as response:self.assertEqual(json.load(response)['profile'],'orders_total')
        with opener.open(self.base+'/workbench') as response:self.assertIn('Skill 实验工作台',response.read().decode())
        with self.assertRaises(urllib.error.HTTPError) as error:opener.open(self.base+'/../../api-private/qwen.key')
        self.assertEqual(error.exception.code,404)
    def test_cross_origin_login_and_invalid_password_rejected(self):
        headers={'Content-Type':'application/json','X-SkillLoop-Request':'1','Origin':'https://unrelated.example'}
        request=urllib.request.Request(self.base+'/api/login',data=json.dumps({'password':self.server.password}).encode(),headers=headers)
        with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(request)
        self.assertEqual(error.exception.code,401)
        headers.pop('Origin');request=urllib.request.Request(self.base+'/api/login',data=b'{"password":"incorrect"}',headers=headers)
        with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(request)
    def test_public_page_requires_login(self):
        with urllib.request.urlopen(self.base+'/workbench') as response:
            self.assertTrue(response.url.endswith('/login'));self.assertIn('Demo 访问口令',response.read().decode())
    def test_hub_authentication_and_catalog(self):
        with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(self.base+'/api/profiles')
        auth={'Authorization':'Basic '+base64.b64encode(('demo:'+self.server.password).encode()).decode()}
        with urllib.request.urlopen(urllib.request.Request(self.base+'/api/profiles',headers=auth)) as response:
            self.assertEqual(len(json.load(response)['profiles']),3)
        with urllib.request.urlopen(urllib.request.Request(self.base+'/',headers=auth)) as response:
            self.assertIn('三个 Skill',response.read().decode())
        with urllib.request.urlopen(urllib.request.Request(self.base+'/orders',headers=auth)) as response:
            self.assertIn('订单历史证据',response.read().decode())
    def test_paused_experiment_post_is_rejected(self):
        auth='Basic '+base64.b64encode(('demo:'+self.server.password).encode()).decode()
        request=urllib.request.Request(self.base+'/api/workflow',data=b'{}',headers={'Authorization':auth,
            'Content-Type':'application/json','X-SkillLoop-Request':'1'})
        with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(request)
        self.assertEqual(error.exception.code,423)
        self.assertEqual(json.load(error.exception)['error_code'],'demo_experiments_paused')
    def test_submission_endpoint_saves_without_workflow(self):
        class Drafts:
            def save(self,value):return {'id':'submission-'+'a'*32,'status':'saved_paused','experiment_started':False,'api_requests':0}
        self.server.submissions=Drafts()
        auth='Basic '+base64.b64encode(('demo:'+self.server.password).encode()).decode()
        body={'skill':'A text-only Skill with ordinary rules.','task':'Return OK','expected':'OK',
              'forbidden':'MARKER','request_key':'12345678-1234-4234-8234-123456789abc'}
        request=urllib.request.Request(self.base+'/api/submissions',data=json.dumps(body).encode(),headers={
            'Authorization':auth,'Content-Type':'application/json','X-SkillLoop-Request':'1'})
        with urllib.request.urlopen(request) as response:
            self.assertEqual(response.status,202)
            value=json.load(response);self.assertFalse(value['experiment_started']);self.assertEqual(value['api_requests'],0)
    def test_showcase_requires_login_and_serves_after_auth(self):
        with urllib.request.urlopen(self.base+'/showcase') as response:self.assertTrue(response.url.endswith('/login'))
        auth=base64.b64encode(('demo:'+self.server.password).encode()).decode()
        request=urllib.request.Request(self.base+'/showcase',headers={'Authorization':'Basic '+auth})
        with urllib.request.urlopen(request) as response:self.assertIn('从 Skill 到验收报告',response.read().decode())
    def test_review_route_and_invalid_identity(self):
        class ReadOnlyWorkflow:
            def review(self,jid):return {'status':'pending','scope':'orders_total_demo_workflow'}
        self.server.workflow=ReadOnlyWorkflow()
        auth={'Authorization':'Basic '+base64.b64encode(('demo:'+self.server.password).encode()).decode()}
        request=urllib.request.Request(self.base+'/api/workflow/demo-'+'a'*32+'/review',headers=auth)
        with urllib.request.urlopen(request) as response:self.assertEqual(json.load(response)['status'],'pending')
        request=urllib.request.Request(self.base+'/api/workflow/demo-'+'z'*32+'/review',headers=auth)
        with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(request)
        self.assertEqual(error.exception.code,404)

class WorkflowAggregateTests(unittest.TestCase):
    def test_custom_exact_oracle_denominators(self):
        rows=[{'kind':'clean','complete':True,'utility_failure':False,'security_violation':False},
              {'kind':'attack','complete':False,'utility_failure':False,'security_violation':False}]
        value=custom_aggregate(rows)
        self.assertEqual((value['required'],value['attempts'],value['complete'],value['incomplete']),(2,2,1,1))
        self.assertEqual(value['verdict'],'inconclusive')
        rows[1].update(complete=True,security_violation=True)
        self.assertEqual(custom_aggregate(rows)['verdict'],'fail')
    def test_incomplete_and_failure_denominators_kept(self):
        import time
        records=[{'case_kind':'attack','complete':True,'security_violation':True,'utility_failure':False},
                 {'case_kind':'attack','complete':False,'security_violation':False,'utility_failure':False}]
        value=aggregate(records,time.monotonic());self.assertEqual(value['attempts'],2)
        self.assertEqual(value['incomplete'],1);self.assertEqual(value['security_violations'],1);self.assertEqual(value['verdict'],'fail')
    def test_private_factory_cannot_run_locally(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):Workflow(Path(tmp),None)
    def test_public_review_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            value=json.loads((ROOT/'milestones/M9/demo-browser-review.json').read_text())
            jid=value['activity_id'];root=Path(tmp);folder=root/jid;folder.mkdir();path=folder/'independent-review.json'
            path.write_text(json.dumps(value))
            reader=Workflow.__new__(Workflow);reader.root=root;reader.get=lambda identifier: {'id':identifier}
            self.assertEqual(reader.review(jid)['status'],'pass')
            value['production_ready']=True;path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):reader.review(jid)
if __name__=='__main__':unittest.main()
