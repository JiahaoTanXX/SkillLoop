"""Executable *specification* for V2.2 operations; no database, OCI or model claim."""
from __future__ import annotations
import copy
import hashlib
import json
import math
from pathlib import Path
import jsonschema
import rfc8785
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
OPS = ROOT / "specs/v2.2/operations"
MiB = 1024 * 1024


class Rejected(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise Rejected(reason)


def load(name):
    return json.loads((OPS / name).read_text())


def transition(state, event):
    matches = [r for r in load("lifecycle.json")["run_transitions"]
               if state in r["from"] and r["event"] == event]
    require(len(matches) == 1, "invalid_transition")
    return copy.deepcopy(matches[0])


def retry_eligible(*, phase, prior_retries, campaign_retries, delivery,
                   known_failure, side_effect_state):
    if known_failure or prior_retries >= 1 or campaign_retries >= 2:
        return False
    if side_effect_state != "absent":
        return False
    return phase == "dev" or (phase == "protected" and delivery == "not_delivered")


class CampaignRegistry:
    """Persistent-key semantics in memory; job IDs deliberately not accepted."""
    def __init__(self):
        self.by_key = {}

    def issue(self, project, head, config, reason="source", prior_attestation=None, generation=1):
        require(reason in {"source", "renewal"}, "invalid_reason")
        require((reason == "renewal") == (prior_attestation is not None), "renewal_identity")
        require(type(generation) is int and generation > 0, "invalid_generation")
        key = (project, head, config, reason, prior_attestation, generation)
        if key not in self.by_key:
            self.by_key[key] = f"campaign-{len(self.by_key) + 1}"
        return self.by_key[key]


class ProtectionLedger:
    def __init__(self):
        self.epochs = {}
        self.executions = {}

    def create_epoch(self, campaign, finalist, epoch, approved_factory,
                     requested_factory, checks):
        require(approved_factory == requested_factory, "factory_needs_approval")
        needed = {"schema", "truth", "coverage", "delivery", "dev_dedup", "leak_check"}
        require(set(checks) == needed and all(checks.values()), "protected_suite_unavailable")
        if campaign in self.epochs:
            require(self.epochs[campaign] == (finalist, epoch), "frozen_finalist_or_epoch")
            return epoch
        require(epoch not in [e[1] for e in self.epochs.values()], "epoch_reuse")
        self.epochs[campaign] = (finalist, epoch)
        return epoch

    def reserve(self, deployment, campaign, epoch, subject, case, repetition):
        require(campaign in self.epochs and self.epochs[campaign][1] == epoch, "wrong_epoch")
        require(type(repetition) is int and 0 <= repetition < 3, "bad_repetition")
        key = (deployment, campaign, epoch, subject, case, repetition)
        old = self.executions.get(key)
        require(old not in {"delivered", "unknown", "complete"}, "no_protected_reexecution")
        self.executions[key] = "reserved"
        return key

    def record(self, key, delivery):
        require(key in self.executions, "not_reserved")
        allowed = {"reserved": {"not_delivered", "delivered", "unknown"},
                   "not_delivered": {"reserved"}, "delivered": {"complete", "unknown"},
                   "unknown": set(), "complete": set()}
        require(delivery in allowed[self.executions[key]], "invalid_delivery_transition")
        self.executions[key] = delivery


def public_projection(entity, role="patcher"):
    require(role in {"patcher", "generator", "report"}, "bad_role")
    # Allowlist; no payload hashes, suite digests, objective IDs or private paths.
    allowed = {"opaque_ref", "aggregate_status", "campaign_public_ref"}
    return {k: v for k, v in entity.items() if k in allowed}


class ProxyModel:
    """Serialized transaction reference only, NOT a concurrency implementation.

    write/receipt are internal state-model helpers after authorization/oracle
    success, never proposed RPC handlers. OS identity and actual call dispatch
    require the separate runtime acceptance tests.
    """
    def __init__(self):
        self.approved = True
        self.trust_revision = 1
        self.fence = 1
        self.active = True
        self.run_deadline = 900
        self.approval_expiry = 700
        self.version = 0
        self.artifact = b""
        self.receipts = {}
        self.grants = {}
        self.idempotency = {}
        self.publication = None
        self.events = []
        self.calls = {}
        self.native_ids = set()
        self.tool_budget = 12
        self.used_tools = 0

    def authenticate(self, role, fence):
        require(role == "runtime", "forbidden_role")
        require(self.active and fence == self.fence, "stale_fence")

    def new_action(self, now):
        require(self.approved and now < self.approval_expiry and now < self.run_deadline,
                "approval_or_run_expired")

    def revoke(self):
        self.approved = False
        self.trust_revision += 1
        self.events.append("effective_revocation_committed")

    def cancel(self):
        self.active = False
        self.fence += 1
        self.events.append("cancellation_committed")

    def register_batch(self, calls, role="runtime", fence=1):
        self.authenticate(role, fence)
        ids = [c["call_id"] for c in calls]
        native = [(c["response_id"], c["native_id"]) for c in calls]
        require(len(ids) == len(set(ids)), "duplicate_internal_id")
        require(len(native) == len(set(native)), "duplicate_native_id")
        fresh = []
        for c in calls:
            if c["call_id"] in self.calls:
                require(self.calls[c["call_id"]] == c, "call_parameter_conflict")
            else:
                require((c["response_id"], c["native_id"]) not in self.native_ids, "duplicate_native_id")
                fresh.append(c)
        require(self.used_tools + len(fresh) <= self.tool_budget, "whole_batch_over_budget")
        for c in fresh:
            self.calls[c["call_id"]] = copy.deepcopy(c)
            self.native_ids.add((c["response_id"], c["native_id"]))
        self.used_tools += len(fresh)
        return len(fresh)

    def write(self, body, expected_version, now=0):
        self.new_action(now)
        require(expected_version == self.version, "stale_artifact")
        self.artifact = body
        self.version += 1
        return self.version

    def receipt(self, now=0):
        self.new_action(now)
        require(self.version > 0, "no_artifact")
        # Caller represents a trusted oracle pass; real oracle belongs to family plugin.
        ref = f"receipt-{len(self.receipts) + 1}"
        self.receipts[ref] = {"version": self.version, "issued_at": now,
                              "expires_at": min(now + 300, self.run_deadline, self.approval_expiry),
                              "trust_revision": self.trust_revision}
        return ref

    def prepare(self, key, receipt, destination="mock", now=0, role="runtime", fence=1):
        self.authenticate(role, fence)
        params = (receipt, destination)
        ident = ("prepare", key)
        if ident in self.idempotency:
            old_params, result = self.idempotency[ident]
            require(old_params == params, "idempotency_conflict")
            return copy.deepcopy(result)
        self.new_action(now)
        r = self.receipts[receipt]
        require(r["version"] == self.version and r["trust_revision"] == self.trust_revision,
                "stale_receipt")
        require(now < r["expires_at"], "receipt_expired")
        result = {"grant_id": f"grant-{len(self.grants) + 1}", "version": self.version,
                  "issued_at": now, "expires_at": min(now + 600, r["expires_at"],
                                                       self.run_deadline, self.approval_expiry),
                  "trust_revision": self.trust_revision, "destination": destination}
        self.grants[result["grant_id"]] = copy.deepcopy(result)
        self.idempotency[ident] = (params, copy.deepcopy(result))
        return result

    def publish(self, key, grant, now=0, role="runtime", fence=1):
        self.authenticate(role, fence)
        ident = ("publish", key)
        if ident in self.idempotency:
            old, result = self.idempotency[ident]
            require(old == grant, "idempotency_conflict")
            return result
        self.new_action(now)
        g = self.grants[grant]
        require(now < g["expires_at"], "grant_expired")
        require(g["version"] == self.version and g["trust_revision"] == self.trust_revision,
                "stale_grant")
        require(self.publication is None, "publication_already_exists")
        self.publication = {"bytes": self.artifact, "version": self.version, "grant": grant}
        self.events.append("publication_committed")
        self.idempotency[ident] = (grant, self.publication)
        return self.publication

    def recover(self, operation, key, role="controller"):
        require(role == "controller", "forbidden_recovery")
        return self.idempotency.get((operation, key))


def finding_decision(severity, verification, disposition, *, complete_policy_proof=False,
                     dynamic_regression_pass=False, admin_evidence=False, prohibited_effect=False):
    require(severity in {"low", "medium", "high", "critical", "unknown"}, "severity")
    require(verification in {"unverified", "confirmed", "not_reproduced", "not_applicable", "inconclusive"}, "verification")
    require(disposition in {"open", "repaired", "mitigated_by_policy", "false_positive",
                            "manual_action_required"}, "disposition")
    if prohibited_effect:
        return "block"
    if disposition == "repaired":
        require(verification == "confirmed" and dynamic_regression_pass, "unproved_repair")
        return "closed_repaired"
    if disposition == "mitigated_by_policy":
        require(complete_policy_proof, "finite_refusals_are_not_policy_proof")
        return "closed_preventive_not_repair_count"
    if disposition == "false_positive":
        require(admin_evidence, "false_positive_needs_evidence")
        return "closed_with_expiring_review"
    if verification == "confirmed" or severity in {"high", "critical", "unknown"}:
        return "block"
    return "warning"


def history_requirement(*, compatibility, retirement_reason=None, admin_evidence=False):
    if retirement_reason is not None:
        require(retirement_reason in {"equivalent_merge", "not_applicable", "project_retired"},
                "invalid_retirement_reason")
        require(admin_evidence, "retirement_needs_evidence")
        return "retired_with_audit"
    require(compatibility in {"same", "migrated", "unknown"}, "compatibility")
    return "block" if compatibility == "unknown" else "required"


def expand_plan(*, finalists=1, abandoned=0, active=0, findings=0, history=0, retries=0):
    for value in (finalists, abandoned, active, findings, history, retries):
        require(type(value) is int and value >= 0, "invalid_plan_count")
    require(finalists <= 1 and abandoned <= 1 and active <= 1 and retries <= 2, "profile_limit")
    current = ["submitted"] + (["finalist"] if finalists else []) + (["active"] if active else [])
    items = []
    for subject in current + (["abandoned"] if abandoned else []):
        for phase, count in [("dev", 5), ("protected", 0 if subject == "abandoned" else 4)]:
            for case in range(count):
                for rep in range(3):
                    items.append({"subject": subject, "case": f"{phase}-{case}", "repetition": rep,
                                  "phase": phase, "attempt": 0})
        if subject != "abandoned":
            for case in range(findings * 2 + history):
                for rep in range(3):
                    items.append({"subject": subject, "case": f"additional-{case}", "repetition": rep,
                                  "phase": "dev", "attempt": 0})
    # Retry examples are extra attempts, never replacement of a failed/unknown run.
    for retry in range(retries):
        item = copy.deepcopy(items[retry])
        item["attempt"] = 1
        items.append(item)
    return items


def budget(items, *, calibration_ready=False, victim_timeout_seconds=180):
    limits = load("runtime-profile.json")["budget"]
    n = len(items)
    retries_used = sum(i["attempt"] > 0 for i in items)
    reserve = max(0, 2 - retries_used)
    # Admission always retains unused retry reserve; all stages are included.
    victim_attempts = n + reserve
    stages = limits["stages"]
    auxiliary_input = sum(s["count"] * s["input_tokens"] for s in stages)
    auxiliary_output = sum(s["count"] * s["output_tokens"] for s in stages)
    input_tokens = victim_attempts * 16 * 14336 + auxiliary_input
    output_tokens = victim_attempts * 16 * 2048 + auxiliary_output
    wall_seconds = victim_attempts * victim_timeout_seconds + sum(s["count"] * s["seconds"] for s in stages)
    disk_bytes = victim_attempts * 4 * MiB + sum(s["count"] * s["disk_mib"] * MiB for s in stages) + 512 * MiB
    fits = (victim_attempts <= limits["victim_attempts"] and input_tokens <= limits["input_tokens"]
            and output_tokens <= limits["output_tokens"] and wall_seconds <= limits["wall_seconds"]
            and disk_bytes <= limits["campaign_disk_bytes"])
    return {"planned_attempts": n, "retry_reserve": reserve, "reserved_victim_attempts": victim_attempts,
            "input_tokens": input_tokens, "output_tokens": output_tokens, "wall_seconds": wall_seconds,
            "disk_bytes": disk_bytes, "fits_configured_bounds": fits,
            "admission": "ready" if fits and calibration_ready else ("calibration_required" if fits else "rejected")}


def github_conclusion(verdict):
    return {"pass": "success", "fail": "failure", "needs_contract": "action_required",
            "inconclusive": "failure"}[verdict]


def storage_admission(free_bytes, reserved_bytes, request_bytes, queued, *, database_ok=True):
    if not database_ok:
        return "database_unavailable"
    if queued >= 16:
        return "busy"
    return "ready" if free_bytes - reserved_bytes - request_bytes >= 2 * 1024 ** 3 else "insufficient_storage"


def restore_epoch(old_epoch, new_epoch):
    require(old_epoch != new_epoch, "restore_requires_new_deployment_epoch")
    return {"deployment_epoch": new_epoch, "grants_valid": False, "leases_valid": False,
            "attestations_valid": False}


def nearest_rank_p95(values):
    if not values:
        return None
    require(all(type(x) in {int, float} and math.isfinite(x) and x >= 0 for x in values), "bad_latency")
    return sorted(values)[math.ceil(.95 * len(values)) - 1]


def performance_ratio(candidate, active):
    if len(candidate) < 20 or len(active) < 20:
        return None
    base = nearest_rank_p95(active)
    return None if base == 0 else nearest_rank_p95(candidate) / base


def validate_control_record(record, *, peer_uid=None, now=None):
    """Reference dispatch checks; peer_uid must come from the OS, never JSON."""
    jsonschema.Draft202012Validator(load("control.schema.json"),
                                    format_checker=jsonschema.FormatChecker()).validate(record)
    projection = {key: value for key, value in record.items() if key != "digest"}
    require(record["digest"] == "sha256:" + hashlib.sha256(rfc8785.dumps(projection)).hexdigest(),
            "control_digest_mismatch")
    body = record["body"]
    if record["kind"] == "ControlRequest":
        role = next((r for r in load("rpc.json")["roles"] if r["uid"] == peer_uid), None)
        require(role is not None and body["method"] in role["methods"], "control_permission_denied")
        require(now is not None, "trusted_clock_required")
        require(datetime.fromisoformat(body["deadline"].replace("Z", "+00:00")) > now,
                "control_deadline_exceeded")
    if record["kind"] == "ControlResponse":
        success = body["status"] in {"ok", "accepted"}
        require(success == (body["result_kind"] is not None and body["result_digest"] is not None
                            and body["error_code"] is None), "control_response_conflict")
        if body["status"] == "accepted":
            require(body["result_kind"] == "OperationTicket", "async_requires_ticket")
        if not success:
            require(body["result_kind"] is None and body["result_digest"] is None
                    and body["error_code"] is not None, "control_error_requires_code")
    if record["kind"] == "HardenResult":
        require((body["candidate_subject_digest"] is None) == (body["patch_application_digest"] is None),
                "harden_candidate_application_binding")
    return record


def verify():
    schema = load("operations.schema.json")
    jsonschema.Draft202012Validator.check_schema(schema)
    checked = []
    for path in sorted(OPS.glob("*.json")):
        if path.name.endswith(".schema.json"):
            continue
        jsonschema.Draft202012Validator(schema).validate(load(path.name))
        checked.append("OPS-SCHEMA-" + path.stem)
    for sample in load("budget-plans.json")["plans"]:
        observed = budget(expand_plan(**sample["parameters"]))
        require(observed == sample["expected"], "budget_goldens_mismatch:" + sample["id"])
        checked.append("OPS-BUDGET-" + sample["id"])
    acceptance = load("acceptance.json")["tests"]
    require(len({x["id"] for x in acceptance}) == len(acceptance), "duplicate_acceptance_id")
    require(all(x["runtime_status"] == "pending" for x in acceptance), "unexecuted_runtime_claim")
    control = load("control.schema.json")
    jsonschema.Draft202012Validator.check_schema(control)
    core = json.loads((OPS.parent / "protocol.schema.json").read_text())
    kinds = set(core["$defs"]) | set(control["$defs"])
    require(all(row["stdout_schema"] in kinds for row in load("cli.json")["commands"]), "cli_missing_output_schema")
    methods = load("control-methods.json")["methods"]
    require({row["method"] for row in methods} == {method for role in load("rpc.json")["roles"] for method in role["methods"]}, "control_method_registry_incomplete")
    require(all(row["result_kind"] in kinds and row["allowed_roles"] for row in methods), "control_method_contract_missing")
    checked.append("OPS-CONTROL-all_methods_and_CLI_outputs_typed")
    return {"status": "pass", "checks": checked, "counts": {"schema_documents": len([p for p in OPS.glob('*.json') if not p.name.endswith('.schema.json')]),
            "budget_examples": len(load("budget-plans.json")["plans"]), "runtime_acceptance_cases": len(acceptance)},
            "runtime_acceptance": "pending"}


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
