"""Explicit forecast, append-only execution spending, and finalist admission."""

from __future__ import annotations

import json
import os
import time
from copy import deepcopy
from pathlib import Path

from skillloop.protocol import digest_jcs

MiB = 1024 ** 2
LIMITS = {"victim_attempts": 128, "retry_reserve": 2, "patch_rounds": 2,
          "input_tokens": 32000000, "output_tokens": 4300000,
          "wall_seconds": 28800, "disk_bytes": 2048 * MiB}


def forecast(items: list[dict], *, calibration: dict, stages: list[dict],
             retries_used: int = 0) -> dict:
    if type(calibration.get("victim_seconds")) not in (int, float) or calibration["victim_seconds"] <= 0:
        raise ValueError("invalid_calibration_bound")
    for stage in stages:
        if (type(stage.get("count")) is not int or stage["count"] < 0 or
                type(stage.get("seconds")) not in (int, float) or stage["seconds"] < 0 or
                any(type(stage.get(key)) is not int or stage[key] < 0
                    for key in ("input_tokens", "output_tokens", "disk_bytes"))):
            raise ValueError("invalid_stage_bound")
    keys = [(i["subject"], i["case"], i["repetition"], i["phase"]) for i in items]
    if len(keys) != len(set(keys)) or any(i["requirement"] not in {"required", "abandoned", "not_applicable"} for i in items):
        raise ValueError("plan_duplicate_or_requirement")
    if type(retries_used) is not int or not 0 <= retries_used <= 2:
        raise ValueError("retry_budget")
    required = [item for item in items if item["requirement"] == "required"]
    runs = len(required) + 2  # Both consumed retry slots and remaining slots count.
    input_tokens = runs * 16 * 14336 + sum(s["count"] * s["input_tokens"] for s in stages)
    output_tokens = runs * 16 * 2048 + sum(s["count"] * s["output_tokens"] for s in stages)
    wall = runs * calibration["victim_seconds"] + sum(s["count"] * s["seconds"] for s in stages)
    disk = runs * 8 * MiB + sum(s["count"] * s["disk_bytes"] for s in stages) + 512 * MiB
    reasons = []
    for key, value in {"victim_attempts": runs, "input_tokens": input_tokens,
                       "output_tokens": output_tokens, "wall_seconds": wall, "disk_bytes": disk}.items():
        if value > LIMITS[key]:
            reasons.append(key + "_exceeded")
    if not calibration.get("ready") or not calibration.get("evidence_digests"):
        reasons.append("calibration_pending")
    return {"planned_runs": len(required), "reserved_attempts": runs,
        "retries_consumed": retries_used, "retry_reserve_remaining": 2 - retries_used,
        "input_tokens": input_tokens, "output_tokens": output_tokens,
        "wall_seconds": wall, "disk_bytes": disk, "reasons": reasons,
        "admission": "ready" if not reasons else "rejected"}


def rows(subject: str, cases: dict, *, role: str = "candidate") -> list[dict]:
    return [{"subject": subject, "case": case["digest"], "repetition": rep,
             "phase": "dev", "role": role, "requirement": "required", "result_ref": None}
            for case in cases.values() for rep in range(case["body"]["repetitions"])]


def protected_reservations(subject: str, *, role: str) -> list[dict]:
    # Opaque capacity slots convey no M7 payload or guessed protected hashes.
    return [{"subject": subject, "case": f"protected-capacity-{index}", "repetition": rep,
             "phase": "protected", "role": role, "requirement": "required", "result_ref": None}
            for index in range(4) for rep in range(3)]


def revise(parent: dict | None, additions: list[dict]) -> dict:
    if parent and parent["digest"] != digest_jcs({key: value for key, value in parent.items() if key != "digest"}):
        raise ValueError("parent_plan_digest")
    items = deepcopy(parent["items"]) if parent else []
    items.extend(deepcopy(additions))
    keys = [(i["subject"], i["case"], i["repetition"], i["phase"]) for i in items]
    if len(keys) != len(set(keys)):
        raise ValueError("plan_revision_duplicate")
    result = {"revision": parent["revision"] + 1 if parent else 1,
        "parent_digest": parent["digest"] if parent else None, "items": items}
    return {**result, "digest": digest_jcs(result)}


def eliminate_protected_slots(parent: dict, subject: str, additions: list[dict]) -> dict:
    """Retain the eliminated subject's opaque reservations and all execution facts."""
    if parent["digest"] != digest_jcs({k: v for k, v in parent.items() if k != "digest"}):
        raise ValueError("parent_plan_digest")
    retained = deepcopy(parent)
    for item in retained["items"]:
        if item["subject"] == subject and item["phase"] == "protected":
            if item.get("result_ref") is not None:
                raise ValueError("protected_started_search_closed")
            item.update(requirement="abandoned", reason_code="eliminated_development_candidate")
    retained["digest"] = digest_jcs({k: v for k, v in retained.items() if k != "digest"})
    result = revise(retained, additions)
    result["parent_digest"] = parent["digest"]
    result["digest"] = digest_jcs({k: v for k, v in result.items() if k != "digest"})
    return result


class SpendingLedger:
    """Persist before execution; process restart never restores consumed slots."""
    def __init__(self, path: Path, *, victim_seconds: int = 200, campaign_started_at: float | None = None):
        if type(victim_seconds) is not int or victim_seconds <= 0:
            raise ValueError("invalid_execution_bound")
        self.victim_seconds = victim_seconds
        self.campaign_started_at = campaign_started_at
        self.path = path
        self.started = time.monotonic()
        self.initial = self.read()
        if self.initial['executions'] and self.initial.get('campaign_started_at') != campaign_started_at:
            raise ValueError('campaign_clock_changed')

    def read(self) -> dict:
        return json.loads(self.path.read_text()) if self.path.exists() else {
            "victim_attempts": 0, "retries": 0, "elapsed_seconds": 0.0,
            "charged_wall_seconds": 0.0, "executions": []}

    def consume(self, item_key: str, attempt: int) -> dict:
        if type(attempt) is not int or attempt not in (0, 1):
            raise ValueError("invalid_attempt")
        state = self.read()
        if any(e["item_key"] == item_key and e["attempt"] == attempt for e in state["executions"]):
            raise ValueError("execution_already_spent")
        elapsed = self.initial["elapsed_seconds"] + time.monotonic() - self.started
        if self.campaign_started_at is not None:
            elapsed = max(elapsed, time.time() - self.campaign_started_at)
        if (state["victim_attempts"] >= 128 or elapsed >= 28800 or
                state["charged_wall_seconds"] + self.victim_seconds > 28800 or (attempt > 0 and state["retries"] >= 2)):
            raise ValueError("execution_budget_exhausted")
        state["victim_attempts"] += 1
        state["retries"] += int(attempt > 0)
        state["elapsed_seconds"] = elapsed
        state["campaign_started_at"] = self.campaign_started_at
        state["charged_wall_seconds"] += self.victim_seconds  # Conservative charge is durable before the worker starts.
        state["executions"].append({"item_key": item_key, "attempt": attempt})
        temporary = self.path.with_suffix(".tmp")
        with temporary.open("w") as output:
            os.chmod(temporary, 0o600)
            json.dump(state, output, indent=2)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, self.path)
        return state


def freeze(*, subject: str, development_verdict: str, missing: list,
           unresolved_high: list, budget: dict, proposal_attempts: int,
           applied_candidates: int, evaluable_candidates: int, evidence_digest: str, repair_rounds: int = 1) -> dict:
    reasons = []
    if development_verdict != "pass" or missing or unresolved_high:
        reasons.append("development_gate_not_passed")
    if budget["admission"] != "ready":
        reasons.append("final_protected_matrix_not_admitted")
    if not (1 <= evaluable_candidates <= applied_candidates <= proposal_attempts and 1 <= repair_rounds <= 2
            and applied_candidates <= repair_rounds and proposal_attempts <= 2 * repair_rounds):
        reasons.append("repair_accounting_invalid")
    body = {"subject": subject, "status": "frozen" if not reasons else "not_frozen",
            "reasons": reasons, "development_gate_digest": evidence_digest,
            "budget_digest": digest_jcs(budget), "protected_evaluation": "not_started"}
    return {**body, "digest": digest_jcs(body)}
