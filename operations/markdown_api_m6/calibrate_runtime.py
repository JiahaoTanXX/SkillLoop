"""Run private clean/attack boundary probes through the trusted M6 tool loop."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from scripts.dgx_m5_development import run_one
import scripts.dgx_m6_calibrate as calibration
import scripts.dgx_m6_repair as m6
from operations.markdown_api_m6.qwen_runtime import runtime_executor
from skillloop.protocol import digest_bytes


def main() -> int:
    private = Path(os.environ["SKILLLOOP_M6_API_PRIVATE"]).resolve()
    candidate_root = Path(os.environ["SKILLLOOP_MARKDOWN_CANDIDATE"]).resolve()
    activity_id = os.environ.get(
        "SKILLLOOP_M6_RUNTIME_CALIBRATION_ID", "runtime-calibration-001")
    if not activity_id.startswith("runtime-calibration-") or "/" in activity_id:
        raise ValueError("invalid_runtime_calibration_id")
    output = private / activity_id
    output.mkdir(mode=0o700, parents=True, exist_ok=False)

    runtime_config = {
        **m6.CONFIG,
        "config_id": "m6-qwen-api-markdown-v1-boundary",
        "thinking": False,
        "provider": "qwen_api_experimental",
        "agent_deadline_seconds": 235,
        "provider_timeout_seconds": 120,
        "max_context_tokens": 16384,
        "max_output_tokens": 2048,
    }
    m6.CONFIG = runtime_config
    m6.VICTIM_BOUND = 265
    calibration.VICTIM_BOUND = 265
    campaign = "m6-api-markdown-v1-" + activity_id
    compiled, inputs, plan = calibration.probe_suite(
        "markdown_index", candidate_root, campaign_id=campaign
    )
    for name, value in (("compiled.json", compiled), ("plan.json", plan)):
        target = output / name
        target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        os.chmod(target, 0o600)

    rows = []
    # Keep this external API calibration strictly on the benign clean fixture.
    # The private secret-leak fixture is not exported by this runner.
    for case_id in ("markdown_index.clean-a",):
        started = time.monotonic()
        result = run_one(
            case_id, 0, output / case_id,
            compiled_suite=compiled,
            skill_root=candidate_root,
            campaign_id=campaign,
            runtime_config=runtime_config,
            execution_plan=plan,
            inputs_override=inputs,
            runtime_executor=runtime_executor,
            tokenizer_container=os.environ.get(
                "SKILLLOOP_TOKENIZER_CONTAINER", "skillloop-refunds-api-tokenizer"),
            deployment_epoch="m6-markdown-api-v1-" + activity_id,
        )
        run_dir = output / case_id
        trace = next((run_dir / "evidence").glob("run-*.jsonl"))
        events = [json.loads(line) for line in trace.read_text().splitlines()]
        responses = [e["response"] for e in events if e.get("type") == "model_response"]
        reasoning = []
        for response in responses:
            usage = response.get("usage") or {}
            count = usage.get("reasoning_tokens")
            if count is None:
                count = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
            reasoning.append(count)
        rows.append({
            "case": case_id,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "coverage_complete": result["coverage_complete"],
            "utility_status": result["utility_status"],
            "security_violation": result["security_violation"],
            "incomplete_reasons": result["incomplete_reasons"],
            "model_responses": len(responses),
            "reasoning_tokens": sum(reasoning) if all(type(v) is int for v in reasoning) else None,
            "reasoning_usage_missing": sum(v is None for v in reasoning),
            "reasoning_usage_nonzero": sum(type(v) is int and v != 0 for v in reasoning),
            "result_digest": result["result_digest"],
            "trace_digest": digest_bytes(trace.read_bytes()),
            "input_sizes": {slot: len(data) for slot, data in inputs.items()},
            "raw_trace_stays_private": True,
        })

    summary = {
        "kind": "MarkdownApiRuntimeBoundaryCalibration",
        "profile": "markdown_index",
        "campaign_id": campaign,
        "scope": "one_benign_clean_boundary_attempt_not_matrix_or_gate",
        "rows": rows,
        "shared_budget_scope": "m6-markdown-refunds-api-v1",
        "reasoning_missing_is_unknown": True,
        "m6_gate_evidence": False,
        "candidate_score": None,
    }
    path = output / "calibration-summary.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    os.chmod(path, 0o600)
    print(json.dumps({
        "kind": summary["kind"], "campaign_id": campaign,
        "scope": summary["scope"], "rows": rows,
        "m6_gate_evidence": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
