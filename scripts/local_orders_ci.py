"""Offline orders CI/CD: durable trigger registry, decision and sanitized receipt."""
import argparse
import datetime
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from skillloop.ci.decision import decide
from skillloop.ci.registry import LocalRegistry
from skillloop.protocol import digest_bytes, digest_jcs

SOURCES = ['skillloop/ci/decision.py', 'skillloop/ci/registry.py',
           'demo/server.py', 'demo/workflow.py', 'demo/profiles.py', 'demo/submissions.py', 'demo/public-report.json',
           'scripts/dgx_demo_review.py',
           'tests/implementation/test_m8_demo.py', 'scripts/local_orders_ci.py']
SOURCES += [str(p.relative_to(ROOT)) for p in sorted((ROOT/'demo/web').iterdir()) if p.is_file()]


def source_index():
    return {name: digest_bytes((ROOT / name).read_bytes()) for name in SOURCES}


def workflow():
    with tempfile.TemporaryDirectory(prefix='orders-local-ci-') as tmp:
        registry = LocalRegistry(Path(tmp) / 'registry.sqlite')
        head = digest_bytes((ROOT / 'demo/public-report.json').read_bytes())
        first = registry.trigger('orders_total', head, 'demo-v1')
        duplicate = registry.trigger('orders_total', head, 'demo-v1')
        decision = decide(submitted_verdict='fail', candidate_verdict='pass',
                          m7_accepted=False, source_kind='immutable_snapshot')
        receipt = registry.complete('orders_total', head, 'demo-v1', first['generation'], first['campaign'], decision)
        second = registry.trigger('orders_total', head, 'demo-v2', 'configuration')
        stale_rejected = False
        try:
            registry.complete('orders_total', head, 'demo-v1', first['generation'], first['campaign'], decision)
        except ValueError as error:
            if str(error) != 'stale_generation': raise
            stale_rejected = True
        renewed = registry.trigger('orders_total', head, 'demo-v2', 'renewal', receipt)
        restarted = LocalRegistry(Path(tmp) / 'registry.sqlite')
        restart_dedup = restarted.trigger('orders_total', head, 'demo-v2', 'renewal', receipt)
        checks = {'trigger_deduplicated': duplicate['deduplicated'],
                  'configuration_advances_generation': second['generation'] == 2,
                  'stale_completion_rejected': stale_rejected,
                  'verified_renewal_advances_generation': renewed['generation'] == 3,
                  'restart_preserves_deduplication': restart_dedup['deduplicated'],
                  'submitted_failure_preserved': decision['exit_code'] == 1,
                  'm7_candidate_held': decision['candidate_decision'] == 'inconclusive',
                  'no_external_publication': not decision['github_check_published'] and not decision['publishable']}
        if not all(checks.values()): raise ValueError('local_workflow_failed')
        return checks, decision


def run(output):
    if output.exists(): raise ValueError('receipt_already_exists')
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests/implementation'), pattern='test_m8_demo.py')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful() or result.testsRun == 0: raise ValueError('local_ci_tests_failed')
    checks, decision = workflow()
    body = {'kind': 'OrdersLocalCIReceipt', 'scope': 'orders_total_local_ci_cd',
            'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'tests': {'run': result.testsRun, 'failures': len(result.failures),
                      'errors': len(result.errors), 'skipped': len(result.skipped)},
            'checks': checks, 'decision': decision, 'sources': source_index(),
            'github_integration_required': False, 'm7_accepted': False, 'production_ready': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as file:
        json.dump({**body, 'digest': digest_jcs(body)}, file, ensure_ascii=False, indent=2)
    print(json.dumps({'local_workflow': 'pass', 'tests': result.testsRun, 'submitted_exit_code': decision['exit_code']}))


def review(receipt, output):
    if output.exists(): raise ValueError('review_already_exists')
    data = json.loads(receipt.read_text()); claimed = data.pop('digest')
    if digest_jcs(data) != claimed or data['sources'] != source_index(): raise ValueError('receipt_or_source_changed')
    if data['scope'] != 'orders_total_local_ci_cd' or data['m7_accepted'] or data['production_ready']:
        raise ValueError('acceptance_scope')
    tests = data['tests']
    if tests['run'] <= 0 or any(tests[k] for k in ('failures', 'errors', 'skipped')): raise ValueError('test_denominator')
    checks, decision = workflow()
    if checks != data['checks'] or decision != data['decision']: raise ValueError('independent_reconstruction')
    review = {'kind': 'OrdersLocalCIAcceptanceReview', 'status': 'pass',
              'scope': data['scope'], 'receipt_digest': claimed, 'tests': tests,
              'workflow_reconstructed': True, 'github_integration_required': False,
              'm7_accepted': False, 'production_ready': False,
              'limitations': ['local_ci_cd_only', 'no_model_evaluation_in_this_receipt', 'm7_qualification_pending']}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as file:
        json.dump({**review, 'digest': digest_jcs(review)}, file, ensure_ascii=False, indent=2)
    print(json.dumps({'review': 'pass', 'scope': review['scope'], 'tests': tests['run']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--review', type=Path)
    args = parser.parse_args()
    if args.review: review(args.review, args.output)
    else: run(args.output)
