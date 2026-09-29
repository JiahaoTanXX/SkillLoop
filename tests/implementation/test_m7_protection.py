"""Run on DGX only: private factory material must stay in its private temp directory."""
import os,tempfile,unittest
from pathlib import Path
from skillloop.protection.authority import ProtectionAuthority
from skillloop.protection.suite import compile_private,protected_plan
from skillloop.discovery.evaluator import synthetic_canary
from skillloop.protocol import digest_jcs
from scripts.spec_v22_families import generate_private_suite,validate_private_suite
from scripts.dgx_m6_repair import CONFIG

@unittest.skipUnless(os.environ.get('SKILLLOOP_PRIVATE_TESTS')=='DGX','private material only on DGX')
class ProtectionTests(unittest.TestCase):
    def test_lowercase_canary_full_bytes(self):
        bundle=generate_private_suite('orders_total',os.urandom(32))
        self.assertEqual(synthetic_canary(bundle['inputs']['notes']),bundle['synthetic_secret'])
    def test_factory_and_plan(self):
        from skillloop.runtime.gateway import ExactDockerTokenizer
        b=generate_private_suite('orders_total',os.urandom(32));v=validate_private_suite(b)
        t=ExactDockerTokenizer()
        from skillloop.discovery.suite import compile_dev_suite
        try:c=compile_private(b,t,compile_dev_suite("orders_total"))
        finally:t.close()
        subjects={r:{'subject_digest':digest_jcs(r)} for r in ('submitted','finalist')}
        p=protected_plan(c,subjects,'test-protected',CONFIG)
        self.assertEqual(sum(i['phase']=='protected' for i in p['body']['items']),24)
        self.assertEqual(len(p['body']['items']),54)
        with self.assertRaises(ValueError):validate_private_suite(b,[v['epoch_id']])
        with self.assertRaises(ValueError):validate_private_suite(b,used_business_projections=[v['business_projection_digest']])
        with self.assertRaises(ValueError):validate_private_suite(b,used_payload_digests=v['payload_digests'])
    def test_durable_delivery_and_cas(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=ProtectionAuthority(Path(tmp));v={'epoch_id':'epoch-one','business_projection_digest':'projection-one','payload_digests':['payload-one']}
            a.create_epoch(campaign='c',finalist='s',validation=v,factory_digest='factory')
            key=a.reserve('d','c','epoch-one','s','case',0)
            a.transition(key,'reserved','delivered');a.transition(key,'delivered','unknown')
            recovered=ProtectionAuthority(Path(tmp))
            with self.assertRaises(ValueError):recovered.reserve('d','c','epoch-one','s','case',0)
            with self.assertRaises(ValueError):recovered.transition(key,'reserved','delivered')
            self.assertEqual(recovered.state(key)[0],'unknown')
    def test_private_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.chmod(tmp,0o755)
            with self.assertRaises(ValueError):ProtectionAuthority(Path(tmp))
if __name__=='__main__':unittest.main()
