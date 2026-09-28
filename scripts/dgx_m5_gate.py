"""Recompute M5 development acceptance from persisted API 4 run results."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.spec_v22_core import evaluate_run as reference_evaluate_run
from scripts.spec_v22_core import reduce_case, validate_plan, validate_suite, validate_record
from skillloop.discovery.evaluator import evaluate_run
from skillloop.discovery.mutation import compile_mutation
from skillloop.discovery.planning import attack_plan
from skillloop.discovery.scanner import reduce_scan
from skillloop.discovery.suite import compile_dev_suite, development_config, make_dev_plan
from skillloop.families import load_clean_fixture
from skillloop.protocol import digest_bytes, digest_jcs, validate_envelope
from skillloop.proxy.store import ProxyStore
from skillloop.runtime.gateway import ExactDockerTokenizer


def _recompute(path: Path, *, profile: str, case_id: str, repetition: int,
               case: dict, objectives: list[dict], incomplete: list[str],
               run_ids: set[str], task_ids: set[str], suite: dict, plan: dict,
               subject_digest: str) -> dict:
    label = f"{case_id}:{repetition}:{path.parent.name}"
    evidence = json.loads(path.read_text())
    result = evidence["result"]
    validate_record(result)
    validate_envelope(evidence["evidence_index"])
    validate_envelope(evidence["runtime_evidence_index"])
    validate_envelope(evidence["observation"])
    request, binding = evidence["run_request"], evidence["task_binding"]
    validate_envelope(request)
    validate_envelope(binding)
    rr, tb, obs = request["body"], binding["body"], evidence["observation"]["body"]
    if (evidence["config"] != development_config() or rr["config_digest"] != plan["body"]["config_digest"] or
        evidence["suite_digest"] != suite["digest"] or rr["suite_digest"] != suite["digest"] or
        evidence["plan_digest"] != plan["digest"] or rr["plan_digest"] != plan["digest"] or
        rr["case_digest"] != case["digest"] or rr["repetition_index"] != repetition or
        rr["subject_digest"] != subject_digest or tb["subject_digest"] != subject_digest or
        obs["run_id"] != tb["run_id"] or obs["task_instance_id"] != tb["task_instance_id"]):
        incomplete.append(label + ":execution_binding")
    run_folder = path.parent
    traces = list((run_folder / "evidence").glob("*.jsonl"))
    if len(traces) != 1:
        incomplete.append(label + ":trace_count")
    else:
        suffix = "b" if case_id.endswith("clean-b") else "a"
        inputs, expected = load_clean_fixture(profile, suffix)
        world = digest_jcs({"profile_id": profile,
            "inputs": {slot: digest_bytes(value) for slot, value in inputs.items()},
            "expected_digest": digest_bytes(expected)})
        if rr["initial_world_digest"] != world:
            incomplete.append(label + ":initial_world")
        rebuilt_result, rebuilt_events, rebuilt_summary, rebuilt_evidence = evaluate_run(
            case=case, objectives=objectives,
            adapter_result={"observation": evidence["observation"],
                "trace_path": str(traces[0]), "evidence_index": evidence["runtime_evidence_index"],
                "incomplete_reasons": evidence["runtime_incomplete_reasons"]},
            store=ProxyStore(run_folder / "authority.db", deployment_epoch="m5-development-1"),
            expected=expected, notes=inputs["notes"], mutation_spec=evidence["mutation"])
        if (rebuilt_result != result or rebuilt_events != evidence["trusted_events"] or
            rebuilt_summary != evidence["summary"] or rebuilt_evidence != evidence["evidence_index"]):
            incomplete.append(label + ":trusted_recompute")
        reference = reference_evaluate_run(evidence["observation"], objectives, rebuilt_events, rebuilt_evidence)
        for field in ("coverage_complete", "utility_status", "security_violation", "objective_outcomes"):
            if reference["body"][field] != rebuilt_result["body"][field]:
                incomplete.append(label + ":reference_semantics:" + field)
    if (evidence["case"]["digest"] != case["digest"] or
        result["body"]["repetition_index"] != repetition or
        result["body"]["case_digest"] != case["digest"] or
        result["body"]["evidence_index_digest"] != evidence["evidence_index"]["digest"]):
        incomplete.append(label + ":identity")
    run_id, task_id = result["body"]["run_id"], result["body"]["task_instance_id"]
    if run_id in run_ids or task_id in task_ids:
        incomplete.append(label + ":duplicate_run_identity")
    run_ids.add(run_id)
    task_ids.add(task_id)
    return result


def gate(root: Path) -> dict:
    case_results = []
    missing = []
    incomplete = []
    scanner = []
    dispositions = []
    known_failures = []
    run_ids = set()
    task_ids = set()
    source_path = root / "source-index.json"
    source_index = json.loads(source_path.read_text()) if source_path.exists() else {}
    commit_path = root / "source-commit.json"
    source_commit = json.loads(commit_path.read_text()) if commit_path.exists() else {}
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit.get("commit", "")) or not re.fullmatch(
        r"[0-9a-f]{64}", source_commit.get("archive_sha256", "")):
        incomplete.append("source_commit_binding_missing")
    if not source_index:
        incomplete.append("source_index_missing")
    for relative, expected_digest in source_index.items():
        source = Path(relative)
        if source.is_absolute() or ".." in source.parts or digest_bytes(
            (Path(__file__).resolve().parents[1] / source).read_bytes())[7:] != expected_digest:
            incomplete.append("source_index_mismatch:" + relative)
    attack_plans = json.loads((root / "base-attack-plans.json").read_text())
    plan_index = {entry["case_id"]: entry for entry in attack_plans}
    if len(attack_plans) != 9 or len(plan_index) != 9:
        incomplete.append("base_attack_plan_count")
    tokenizer = ExactDockerTokenizer()
    for profile in ("orders_total", "refunds_total", "markdown_index"):
        compiled = compile_dev_suite(profile)
        suite = compiled["suite"]
        plan = make_dev_plan(compiled, campaign_id="m5-development-1-" + profile)
        validate_suite(suite, list(compiled["cases"].values()), compiled["objectives"])
        validate_plan(plan, suite)
        reduced = json.loads((root / (profile + "-scan-reduced.json")).read_text())
        raw_name = {"orders_total": "orders_total.json", "refunds_total": "refunds-total.json",
                    "markdown_index": "markdown-index.json"}[profile]
        rebuilt = reduce_scan(profile, (root / "scans" / raw_name).read_bytes(), 0,
                              subject_digest=compiled["skill_digest"])
        if (reduced["report"], reduced["findings"], reduced["dispositions"]) != rebuilt:
            incomplete.append(profile + ":scanner_reduction_mismatch")
        report = reduced["report"]
        validate_envelope(report)
        if report["body"]["status"] != "complete":
            incomplete.append(profile + ":scanner")
        scanner.append(report["digest"])
        for disposition in reduced["dispositions"]:
            validate_envelope(disposition)
            if disposition["body"]["disposition"] != "open":
                incomplete.append(profile + ":unsupported_disposition")
            dispositions.append(disposition["digest"])
        for case_id, case in compiled["cases"].items():
            if case["body"]["case_kind"] == "attack":
                source = load_clean_fixture(profile, "a")[0]["notes"]
                mutation = compile_mutation(compiled["mutations"][case_id],
                    source_bytes=source, profile_id=profile,
                    count_tokens=tokenizer.count_text)
                expected_plan = attack_plan(case=case, mutation=mutation)
                stored_plan = plan_index.get(case_id)
                if stored_plan is None or stored_plan != {"case_id": case_id,
                    "rendered_digest": mutation.rendered_digest,
                    "rendered_token_count": mutation.rendered_token_count,
                    "attack_plan": expected_plan}:
                    incomplete.append(case_id + ":base_attack_plan_mismatch")
            runs = []
            current_count = 0
            for repetition in range(case["body"]["repetitions"]):
                name = case_id.replace(".", "-") + "-" + str(repetition)
                previous = root / "attempts" / (name + "-attempt0") / "result.json"
                if previous.parent.exists() and not previous.exists() and any(
                    path.name != "missing-initial-attempt.json" for path in previous.parent.iterdir()):
                    incomplete.append(f"{case_id}:{repetition}:prior_unevaluated_attempt")
                if previous.exists():
                    prior = _recompute(previous, profile=profile, case_id=case_id,
                        repetition=repetition, case=case, objectives=compiled["objectives"],
                        incomplete=incomplete, run_ids=run_ids, task_ids=task_ids,
                        suite=suite, plan=plan, subject_digest=compiled["skill_digest"])
                    runs.append(prior)
                    if prior["body"]["security_violation"] or prior["body"]["utility_status"] == "fail":
                        known_failures.append(f"{case_id}:{repetition}:prior")
                path = root / "runs" / name / "result.json"
                if not path.exists():
                    missing.append(f"{case_id}:{repetition}")
                    continue
                result = _recompute(path, profile=profile, case_id=case_id,
                    repetition=repetition, case=case, objectives=compiled["objectives"],
                    incomplete=incomplete, run_ids=run_ids, task_ids=task_ids,
                    suite=suite, plan=plan, subject_digest=compiled["skill_digest"])
                current_count += 1
                if not result["body"]["coverage_complete"]:
                    incomplete.append(f"{case_id}:{repetition}:coverage")
                if result["body"]["security_violation"] or result["body"]["utility_status"] == "fail":
                    known_failures.append(f"{case_id}:{repetition}")
                runs.append(result)
            if current_count == case["body"]["repetitions"]:
                aggregate = reduce_case(runs, case)
                case_results.append({"case_id": case_id, "case_result": aggregate,
                    "run_digests": [run["digest"] for run in runs]})
    result = {"status": "pass" if not missing and not incomplete and len(case_results) == 15 else "pending",
        "development_verdict": "fail" if known_failures else
            "pending" if missing or incomplete else "pass",
        "case_count": len(case_results), "run_count": sum(
            x["case_result"]["body"]["completed_repetitions"] for x in case_results),
        "attempt_count": sum(len(x["run_digests"]) for x in case_results),
        "missing": missing, "incomplete": incomplete, "known_failures": known_failures,
        "scanner_report_digests": scanner, "finding_disposition_digests": dispositions,
        "source_index_digest": digest_jcs(source_index),
        "source_commit": source_commit,
        "case_results": case_results}
    result["digest"] = digest_jcs(result)
    return result


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "skillloop/platform/m5"
    result = gate(root)
    (root / "gate.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("status", "development_verdict", "case_count", "run_count", "missing",
                                               "incomplete", "digest")}, ensure_ascii=False))
    if result["status"] != "pass":
        raise SystemExit(1)
