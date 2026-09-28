"""Run one frozen M5 development case on the isolated DGX loopback stack."""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skillloop.discovery.evaluator import evaluate_run
from skillloop.discovery.mutation import compile_mutation
from skillloop.discovery.suite import compile_dev_suite, development_config, make_dev_plan
from skillloop.families import load_clean_fixture, load_example_skill
from skillloop.protocol import digest_bytes, digest_jcs
from skillloop.proxy.server import ProxyServer
from skillloop.proxy.store import ProxyStore
from skillloop.runtime.adapter import AgentAdapter
from skillloop.runtime.client import ProxyClient
from skillloop.runtime.gateway import ExactDockerTokenizer, SGLangGateway
from tests.implementation.test_proxy_store import fixture, stamp


def run_one(case_id: str, repetition: int, output: Path, attempt_index: int = 0) -> dict:
    profile_id = case_id.split(".")[0]
    compiled = compile_dev_suite(profile_id)
    case = compiled["cases"][case_id]
    if repetition < 0 or repetition >= case["body"]["repetitions"] or attempt_index not in (0, 1):
        raise ValueError("repetition_out_of_range")
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    plan = make_dev_plan(compiled, campaign_id="m5-development-1-" + profile_id)
    config = development_config()
    suffix = "b" if case_id.endswith("clean-b") else "a"
    inputs, expected = load_clean_fixture(profile_id, suffix)
    skill_bytes = load_example_skill(profile_id)
    tokenizer = ExactDockerTokenizer()
    mutation_spec = compiled["mutations"].get(case_id)
    mutation = (compile_mutation(mutation_spec, source_bytes=inputs["notes"],
                                 profile_id=profile_id, count_tokens=tokenizer.count_text)
                if mutation_spec else None)
    domain, policy, binding, request, approval, raw = fixture(
        profile_id, suffix=suffix, subject_digest=digest_bytes(skill_bytes),
        case_digest=case["digest"], suite_digest=compiled["suite"]["digest"],
        plan_digest=plan["digest"], repetition_index=repetition,
        config_digest=plan["body"]["config_digest"],
        initial_world_digest=digest_jcs({"profile_id": profile_id,
            "inputs": {slot: digest_bytes(value) for slot, value in inputs.items()},
            "expected_digest": digest_bytes(expected)}),
        run_id=f"run-m5-{case_id}-{repetition}-attempt-{attempt_index}",
        task_instance_id=f"task-m5-{case_id}-{repetition}-attempt-{attempt_index}")
    store = ProxyStore(output / "authority.db", deployment_epoch="m5-development-1")
    store.stage_approval(domain, approval)
    store.activate_approval(approval["digest"], 0, operation_id="activate-m5",
                            request_digest=digest_jcs("activate-m5"))
    store.stage_task(domain=domain, policy=policy, binding=binding, run_request=request,
                     profile_id=profile_id, resources=raw, approval_digest=approval["digest"],
                     run_deadline=stamp(360), campaign_id="m5-development-1")
    store.start_run(request["digest"], binding["digest"], operation_id="start-m5",
                    request_digest=digest_jcs("start-m5"))
    server = ProxyServer(store, output / "sockets", controller_uid=os.getuid(),
                         runtime_uid=os.getuid(), socket_mode=0o600)
    with server:
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            result = AgentAdapter(proxy=ProxyClient(output / "sockets"),
                gateway=SGLangGateway("http://127.0.0.1:30000", tokenizer),
                private_root=output / "evidence").run(
                profile_id=profile_id, skill_bytes=skill_bytes, run_request=request,
                task_binding=binding, fence=1, trust_revision=1,
                deployment_epoch="m5-development-1", deadline_seconds=300,
                rendered_mutation=mutation, attempt_index=attempt_index)
        finally:
            server.stop()
            worker.join(timeout=2)
    capture = {"case": case, "config": config, "run_request": request, "task_binding": binding,
        "mutation": mutation_spec, "observation": result["observation"],
        "runtime_evidence_index": result["evidence_index"],
        "runtime_incomplete_reasons": result["incomplete_reasons"],
        "trace_filename": Path(result["trace_path"]).name}
    (output / "runtime-capture.json").write_text(json.dumps(capture, ensure_ascii=False, indent=2) + "\n")
    os.chmod(output / "runtime-capture.json", 0o600)
    evaluated, events, summary, evaluation_evidence = evaluate_run(case=case, objectives=compiled["objectives"],
        adapter_result=result, store=store, expected=expected, notes=inputs["notes"], mutation_spec=mutation_spec)
    private = {"case": case, "suite_digest": compiled["suite"]["digest"],
        "plan_digest": plan["digest"], "config": config,
        "run_request": request, "task_binding": binding, "mutation": mutation_spec,
        "rendered_digest": mutation.rendered_digest if mutation else None,
        "observation": result["observation"], "evidence_index": evaluation_evidence,
        "runtime_evidence_index": result["evidence_index"],
        "runtime_incomplete_reasons": result["incomplete_reasons"],
        "result": evaluated, "trusted_events": events, "summary": summary,
        "rounds": result["rounds"]}
    (output / "result.json").write_text(json.dumps(private, ensure_ascii=False, indent=2) + "\n")
    os.chmod(output / "result.json", 0o600)
    return {"case_id": case_id, "repetition": repetition,
        "coverage_complete": evaluated["body"]["coverage_complete"],
        "utility_status": evaluated["body"]["utility_status"],
        "security_violation": evaluated["body"]["security_violation"],
        "exposure_status": evaluated["body"]["exposure_status"],
        "objective_outcomes": [{key: row[key] for key in ("objective_id", "attempt", "effect")}
                               for row in evaluated["body"]["objective_outcomes"]],
        "incomplete_reasons": evaluated["body"]["incomplete_reasons"],
        "rounds": result["rounds"], "result_digest": evaluated["digest"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--repetition", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--attempt-index", type=int, default=0)
    args = parser.parse_args()
    print(json.dumps(run_one(args.case, args.repetition, args.output,
                             args.attempt_index), ensure_ascii=False))


if __name__ == "__main__":
    main()
