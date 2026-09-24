"""Read-only counterexamples against the V2.1 executable specification.

Run with the dependencies in specs/v2.1/requirements-verify.txt.
These probes demonstrate specification-check gaps, not deployed exploits.
"""
import copy
import importlib.util
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("reviewed_spec", ROOT / "scripts/verify_specs_v21.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
records = m.load("examples/valid-records.json")
schema = m.load("protocol.schema.json")
validator = Draft202012Validator(schema, format_checker=FormatChecker())
results = []


def example(kind):
    return copy.deepcopy(next(x for x in records if x["kind"] == kind))


def check(label, record, observed=None):
    results.append(dict(probe=label, schema_accepts=validator.is_valid(record),
                        semantic_errors=m.semantic_errors(record), observed=observed))


r = example("RunResult")
r.update(case_kind="attack", exposure_status="delivery_failed")
check("P01_delivery_failure_is_complete_and_safe", r, m.reduce_case([r], 1))

r = example("RunResult")
r.update(case_kind="attack", policy_decisions=["unknown"])
check("P02_unknown_policy_is_complete_and_safe", r, m.reduce_case([r], 1))

r = example("RunResult")
r.update(case_kind="attack", objective_results=[dict(objective_id="prohibited-leak", level="effect", success=True)])
check("P03_effect_true_and_safe_true_coexist", r, m.reduce_case([r], 1))

r = example("RunResult")
r.update(utility_success=False, agent_outcome="failure", evidence_complete=False)
g = copy.deepcopy(next(t["input"] for t in m.load("examples/gate-cases.json") if t["expected_verdict"] == "pass"))
g["cases"][0].update(complete=False, utility_pass=False)
check("P04_known_utility_failure_with_missing_evidence_is_not_fail", g, m.gate(g, m.load("gate-spec.json")))

r = example("ScannerReport")
r.update(status="complete", completed_or_justified_analyzers=[], upstream_exit_code=2, raw_report_digest=None)
check("P05_complete_scanner_with_no_completed_analyzers", r)

r = example("ExecutionPlan")
r["subject_digests"].append("sha256:" + "f" * 64)
r.update(reserved_rollouts=1, reserved_execution_ms=1)
r["plan_digest"] = m.digest({k: v for k, v in r.items() if k != "plan_digest"})
check("P06_eighteen_required_pairs_reserve_one_run", r)

r = copy.deepcopy(next(x for x in records if x["kind"] == "CIResult" and x["submitted_decision"]["verdict"] == "pass"))
r["submitted_decision"]["incomplete_items"] = ["missing_required_case"]
check("P07_nested_gate_result_semantics_not_checked", r,
      dict(nested_errors=m.semantic_errors(r["submitted_decision"])))

r = copy.deepcopy(next(x for x in records if x["kind"] == "CIResult" and x["submitted_decision"]["verdict"] == "pass"))
r["coverage"].update(required_cases=9, completed_cases=0)
check("P08_pass_report_with_zero_completed_cases", r)

r = example("Policy")
r["body"]["allowed_actions"][0]["resource_bindings"] = []
r["policy_digest"] = m.body_digest(r["body"])
check("P09_read_action_without_resource_binding", r)

r = example("Policy")
old_digest = r["policy_digest"]
old_body = copy.deepcopy(r["body"])
r["body"]["allowed_actions"].reverse()
r["policy_digest"] = m.body_digest(r["body"])
check("P10_same_action_set_different_subject_component", r,
      dict(digest_changed=old_digest != r["policy_digest"],
           subset_both_directions=m.is_subset(r["body"], old_body) and m.is_subset(old_body, r["body"])))

r = example("CaseTemplate")
r.update(case_kind="attack", payload_digest=None, clean_pair_id=None, objective_ids=[])
check("P11_attack_case_without_payload_or_objective", r)

r = example("TaskInstance")
r["resources"].append(copy.deepcopy(r["resources"][0]))
r["resources"][-1]["bytes_digest"] = "sha256:" + "f" * 64
check("P12_duplicate_resource_identity_conflicting_bytes", r)

raw = b'customer_id,name\nc1,Al"ice\n'
try:
    output = m.orders_reference(raw, b"order_id,customer_id,amount_cents\n")
    results.append(dict(probe="P13_unquoted_double_quote_csv_accepted", accepted=True,
                        output=json.loads(output)))
except Exception as exc:
    results.append(dict(probe="P13_unquoted_double_quote_csv_accepted", accepted=False, error=str(exc)))

r = example("RunResult")
r.update(utility_success=None, agent_outcome="indeterminate")
check("P14_unknown_utility_reduced_to_complete_false_utility", r, m.reduce_case([r], 1))

r = example("PatchCandidate")
r.update(repair_kind="policy_only", file_patch_digest=None, policy_patch_digest="sha256:" + "f" * 64,
         changed_paths=["tools/executor.py"], cumulative_added_bytes=10, cumulative_changed_bytes=20)
check("P15_policy_only_candidate_claims_code_edit", r)

print(json.dumps(results, ensure_ascii=False, indent=2))
