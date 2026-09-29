"""Run two private qwen3.8-flash refund task boundary probes on DGX."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from pathlib import Path


REPO = Path(os.environ["REFUNDS_API_REPO"])
ROOT = Path(os.environ["REFUNDS_API_ROOT"])
PRIVATE = Path.home() / "skillloop/api-private"
sys.path.insert(0, str(REPO))

import scripts.dgx_m6_calibrate as calibration
import scripts.dgx_m6_repair as m6
from scripts.dgx_m5_development import run_one
from skillloop.protocol import digest_bytes, digest_jcs


def main() -> None:
    output = ROOT / "c3"
    if output.exists():
        raise FileExistsError("refunds_api_boundary_calibration_exists")
    output.mkdir(parents=True, mode=0o700)

    api_config = json.loads((PRIVATE / "config.json").read_text())
    runtime_config = {
        **m6.CONFIG,
        "config_id": "m6-qwen-api-refunds-v1-boundary",
        "thinking": False,
        "provider": "qwen_api",
        "api_config_file": str(PRIVATE / "config.json"),
        "api_shared_budget_path": str(PRIVATE / "calibration-v1/cost.sqlite"),
        "api_purpose": "calibration",
        "agent_deadline_seconds": 210,
        "provider_timeout_seconds": 120,
        "proxy_deadline_seconds": 230,
        "worker_deadline_seconds": 240,
        "max_context_tokens": 16384,
        "max_output_tokens": 2048,
    }
    m6.CONFIG = runtime_config
    m6.VICTIM_BOUND = 240
    calibration.VICTIM_BOUND = 240
    compiled, inputs, plan = calibration.probe_suite(
        "refunds_total", m6.REDTEAM, campaign_id="m6-api-refunds-v1-boundary-original-c3")
    (output / "compiled.json").write_text(json.dumps(compiled, ensure_ascii=False, indent=2) + "\n")
    (output / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
    os.chmod(output / "compiled.json", 0o600)
    os.chmod(output / "plan.json", 0o600)

    rows = []
    for case_id in ("refunds_total.clean-a", "refunds_total.secret-leak"):
        started = time.monotonic()
        result = run_one(case_id, 0, output / case_id, compiled_suite=compiled,
            skill_root=m6.REDTEAM, campaign_id="m6-api-refunds-v1-boundary-original-c3",
            runtime_config=runtime_config, execution_plan=plan, inputs_override=inputs)
        trace = next((output / case_id / "evidence").glob("run-*.jsonl"))
        events = [json.loads(line) for line in trace.read_text().splitlines()]
        responses = [event["response"] for event in events if event.get("type") == "model_response"]
        usage = [response.get("_skillloop_private_transport_audit", {}) for response in responses]
        missing_reasoning = sum(str(row.get("reasoning_usage_status", "")).startswith("unknown_missing") for row in usage)
        reported_reasoning = [row["reasoning_tokens"] for row in usage if row.get("reasoning_usage_status") == "provider_reported_zero"]
        rows.append({
            "case": case_id,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "coverage_complete": result["coverage_complete"],
            "utility_status": result["utility_status"],
            "security_violation": result["security_violation"],
            "model_responses": len(responses),
            "reasoning_usage_missing_count": missing_reasoning,
            "reasoning_tokens_sum": sum(reported_reasoning) if missing_reasoning == 0 else None,
            "reasoning_tokens_status": "unknown_missing" if missing_reasoning else "reported",
            "known_usage_cost_micro_rmb": sum(row.get("known_usage_cost_micro_rmb", 0) for row in usage),
            "conservative_reserved_micro_rmb": sum(row.get("reserved_micro_rmb", 0) for row in usage),
            "settled_micro_rmb": sum(row.get("charged_micro_rmb", 0) or 0 for row in usage),
            "result_digest": result["result_digest"],
            "trace_digest": digest_bytes(trace.read_bytes()),
        })

    ledger = sqlite3.connect(PRIVATE / "calibration-v1/cost.sqlite")
    ledger_summary = ledger.execute(
        "select count(*),sum(charged_micro),sum(reserved_micro),group_concat(distinct state) from reservations"
    ).fetchone()
    ledger.close()
    record = {
        "kind": "RefundsM6ApiBoundaryCalibration",
        "campaign_id": "m6-api-refunds-v1-boundary-original-c3",
        "prior_setup_attempt_refs": [str(ROOT / "boundary-calibration-original-v1"), str(ROOT / "boundary-calibration-original-v2")],
        "profile": "refunds_total",
        "model": api_config["model"],
        "enable_thinking": False,
        "source_ref": str(REPO),
        "scope": "original_skill_business_boundary_probes_not_candidate_admission_or_regression",
        "rows": rows,
        "reasoning_usage": "unknown where the provider omitted raw reasoning_tokens; no missing values coerced to zero",
        "shared_cost_ledger_ref": str(PRIVATE / "calibration-v1/cost.sqlite"),
        "shared_cost_ledger_summary": {
            "reservation_count": ledger_summary[0],
            "charged_micro_rmb": ledger_summary[1],
            "reserved_micro_rmb": ledger_summary[2],
            "states": ledger_summary[3],
        },
        "formal_admission": "rejected_unless_all_gate_requirements_are_independently_satisfied",
        "candidate_regression_started": False,
        "production_ready": False,
    }
    (output / "calibration-status.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    os.chmod(output / "calibration-status.json", 0o600)
    print(json.dumps({"status": "boundary_calibration_finished", "rows": rows,
        "shared_cost_ledger_summary": record["shared_cost_ledger_summary"],
        "formal_admission": record["formal_admission"]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
