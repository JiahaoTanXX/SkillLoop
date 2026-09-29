"""Refresh a read-only, profile-scoped Markdown API M6 status record.

This script never accesses credentials, private raw responses, or remote hosts,
and never starts a model request or execution clock.
"""

from __future__ import annotations

import json
import hashlib
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "milestones" / "M6" / "markdown-api-v1"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def record_digest(body: dict) -> str:
    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def build_status() -> dict:
    progress_path = ROOT / "milestones" / "M6" / "progress.json"
    admission_path = ROOT / "milestones" / "M7" / "api-parallel-admission.json"
    readiness_path = ROOT / "milestones" / "M7" / "api-readiness.json"
    dgx_observation_path = OUT / "dgx-status-observation.json"
    calibration_path = OUT / "business-calibration-summary.json"
    calibration_classification_path = OUT / "business-calibration-classification.json"
    source_index_path = OUT / "source-index.json"
    progress = load(progress_path)
    admission = load(admission_path)
    readiness = load(readiness_path)
    dgx_observation = load(dgx_observation_path)
    source_index = load(source_index_path)
    calibration = load(calibration_path) if calibration_path.exists() else None
    calibration_classification = load(calibration_classification_path)
    profile_admission = admission["profiles"]["markdown_index"]
    retained = progress["other_profiles_attack_audit"]["retained_markdown"]
    current = progress["other_profiles_attack_audit"]["current_markdown"]

    if profile_admission["formal_admission"] != "rejected":
        raise ValueError("status_refresh_requires_explicit_admission_review")

    api_configuration = {
        "base_url": readiness["base_url"],
        "model": admission["model"],
        "enable_thinking": admission["enable_thinking"],
        "input_price_per_million_rmb": "0.8",
        "output_price_per_million_rmb": "2.7",
        "shared_limit_rmb": "10.00",
    }

    body = {
        "kind": "MarkdownApiM6ProfileStatus",
        "profile": "markdown_index",
        "api_model": admission["model"],
        "enable_thinking": admission["enable_thinking"],
        "api_configuration": api_configuration,
        "api_configuration_digest": record_digest(api_configuration),
        "transport_source_snapshot_digest": source_index["digest"],
        "observed_at_unix_ms": int(time.time() * 1000),
        "formal_admission": profile_admission["formal_admission"],
        "admission_reasons": profile_admission["reasons"],
        "conservative_full_capacity_forecast_micro_rmb": profile_admission[
            "conservative_token_forecast_micro_rmb"
        ],
        "shared_limit_micro_rmb": admission["shared_limit_micro_rmb"],
        "initial_two_probe_reservation_micro_rmb": admission[
            "calibration_charged_or_reserved_micro_rmb"
        ],
        "raw_reasoning_tokens": admission["raw_reasoning_tokens"],
        "genuine_business_calibration_attempted": calibration is not None,
        "business_fixture_expected_match": calibration_classification[
            "business_fixture_expected_match"
        ],
        "trusted_family_oracle_invoked": calibration_classification[
            "trusted_family_oracle_invoked"
        ],
        "full_runtime_or_tool_loop_exercised": calibration_classification[
            "full_runtime_or_tool_loop_exercised"
        ],
        "complete_profile_calibration": calibration_classification[
            "complete_profile_calibration"
        ],
        "m6_gate_evidence": calibration_classification["m6_gate_evidence"],
        "genuine_business_calibration_admitted": bool(
            calibration
            and calibration.get("response_saved")
            and calibration.get("output_json_valid")
            and calibration.get("oracle_match")
            and calibration.get("finish_reason") != "length"
            and calibration.get("reasoning_tokens") == 0
            and calibration.get("transport_error_class") is None
            and calibration_classification["complete_profile_calibration"]
        ),
        "business_calibration_summary_sha256": digest(calibration_path) if calibration else None,
        "business_calibration_classification_sha256": digest(calibration_classification_path),
        "shared_cost_ledger_snapshot": (
            {
                "ledger_ref": calibration["shared_cost_ledger_ref"],
                "reservation_records": calibration["shared_ledger_after_request"]["reservation_records"],
                "conservative_reserved_micro_rmb": calibration["shared_ledger_after_request"][
                    "conservative_reserved_micro_rmb"
                ],
                "latest_calibration_request_reserved_micro_rmb": calibration[
                    "request_conservative_reservation_micro_rmb"
                ],
                "scope": "shared_across_profiles_not_a_markdown_allowance",
            }
            if calibration
            else None
        ),
        "matrix_model_requests_started": profile_admission["model_runs_started"],
        "new_api_matrix_model_requests": admission["new_api_matrix_model_requests"],
        "legacy_activity": {
            "m6_n11m_activity": current["activity"],
            "m6_n11m_status": current["status"],
            "m6_b08_is_historical_only": True,
            "m6_b08_attack_cases": retained["attack_cases"],
            "m6_b08_required_attack_runs": retained["attack_required_runs"],
            "m6_b08_complete_attack_runs": retained["attack_complete"],
            "m6_b08_incomplete_attempts_preserved": (
                retained["attack_actual_attempts"] - retained["attack_complete"]
            ),
            "m6_b08_historical_attack_successes": retained["attack_successes"],
            "m6_b08_unresolved_high": progress["retained_campaign"]["unresolved_high"],
            "historical_scores_count_as_new_api_results": False,
        },
        "dgx_process_observation": {
            "observed_at_utc": dgx_observation["observed_at_utc"],
            "observed_processes": dgx_observation["observed_processes"],
            "skillloop_or_api_model_process_seen": dgx_observation[
                "skillloop_or_api_model_process_seen"
            ],
            "m6_n11m_directory_seen": dgx_observation["m6_n11m_directory_seen"],
            "markdown_calibration_worker_running": dgx_observation[
                "markdown_calibration_worker_running"
            ],
            "markdown_private_activity_mode": dgx_observation[
                "markdown_private_activity_mode"
            ],
            "calibration_summary_mode": dgx_observation["calibration_summary_mode"],
            "raw_response_files_in_shared_private_calibration_root": dgx_observation[
                "raw_response_files_in_shared_private_calibration_root"
            ],
            "observation_scope": dgx_observation["scope"],
        },
        "source_records": {
            "markdown_api_source_index_sha256": digest(source_index_path),
            "m6_progress_sha256": digest(progress_path),
            "api_parallel_admission_sha256": digest(admission_path),
            "api_readiness_sha256": digest(readiness_path),
            "dgx_status_observation_sha256": digest(dgx_observation_path),
            "api_readiness_status": readiness["status"],
        },
        "next_gate": "complete_profile_runtime_calibration_and_resolve_raw_reasoning_and_shared_budget_before_matrix_gate",
        "execution_started": False,
        "clock_reset": False,
        "budget_increased": False,
        "credentials_or_raw_model_evidence_copied": False,
    }
    return {**body, "digest": record_digest(body)}


def main() -> None:
    status = build_status()
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / "progress.json"
    target.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: status[k] for k in (
        "profile", "formal_admission", "admission_reasons",
        "business_fixture_expected_match", "trusted_family_oracle_invoked",
        "complete_profile_calibration", "genuine_business_calibration_admitted",
        "matrix_model_requests_started",
        "execution_started", "digest",
    )}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
