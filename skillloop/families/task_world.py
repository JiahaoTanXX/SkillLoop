"""Trusted task bindings for fixed and factory-produced business worlds."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from skillloop.families.fixtures import load_clean_fixture
from skillloop.families.registry import FamilyRegistry
from skillloop.protocol import digest_bytes, digest_jcs, make_envelope


def stamp(offset_seconds: int = 0) -> str:
    return (datetime.now(timezone.utc).replace(microsecond=0) + timedelta(seconds=offset_seconds)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def fixture(profile_id: str = "orders_total", *, suffix: str = "a",
            subject_digest: str | None = None, case_digest: str | None = None,
            suite_digest: str | None = None, plan_digest: str | None = None,
            repetition_index: int = 0, run_id: str = "run-1",
            task_instance_id: str = "task-1", config_digest: str | None = None,
            initial_world_digest: str | None = None,
            inputs_override: dict[str, bytes] | None = None) -> tuple[dict, dict, dict, dict, dict, dict[str, bytes]]:
    registry = FamilyRegistry()
    profile = registry.profile(profile_id)
    inputs, _expected = load_clean_fixture(profile_id, suffix)
    if inputs_override is not None:
        from skillloop.families.oracle import validate_artifact
        from skillloop.families.builders import build_artifact
        inputs = dict(inputs_override)
        validate_artifact(profile_id, inputs, build_artifact(profile_id, inputs))
    contract = digest_jcs(profile)
    slots = [{"slot": name, "resource_class": "input", "allowed_access": ["read"],
              "tenant_id": "tenant-a"} for name in profile["input_bindings"]]
    slots += [{"slot": "output", "resource_class": "artifact", "allowed_access": ["read", "write"],
               "tenant_id": "tenant-a"},
              {"slot": "destination", "resource_class": "sink", "allowed_access": ["publish"],
               "tenant_id": "tenant-a"}]
    def action(tool: str, bindings: list[tuple[str, str, str]], *, check: str | None = None,
               transform: str | None = None, dest: str | None = None) -> dict:
        return {"tool": tool, "bindings": [{"parameter": p, "slot": s, "access": a} for p, s, a in bindings],
                "destination_slot": dest, "check_set_id": check, "transform_id": transform}
    check = f"{profile_id}-strict-v1"
    actions = [action("read_resource", [("resource_id", name, "read")]) for name in profile["input_bindings"]]
    actions += [action("build_artifact", [(f"input_bindings.{name}", name, "read")
                                             for name in profile["input_bindings"]] +
                       [("output_id", "output", "write")], transform=profile["operation"]),
                action("write_artifact", [("output_id", "output", "write")]),
                action("validate_artifact", [("output_id", "output", "read")], check=check),
                action("prepare_publication", [("output_id", "output", "read"),
                                                ("destination_id", "destination", "publish")],
                       check=check, dest="destination"),
                action("publish_artifact", [("output_id", "output", "read"),
                                            ("destination_id", "destination", "publish")],
                       check=check, dest="destination")]
    domain = make_envelope("AuthorizationDomain", {"domain_id": "approved-test-domain",
        "contract_digest": contract, "tenant_id": "tenant-a", "slots": slots,
        "approved_actions": actions, "max_tool_calls": 12, "prerequisites_profile": "strict-v2"})
    policy = make_envelope("Policy", {"contract_digest": contract, "domain_digest": domain["digest"],
        "allowed_actions": actions, "max_tool_calls": 12, "prerequisites_profile": "strict-v2"})
    resources = [{"resource_id": resource_id, "resource_class": "input", "access": "read",
                  "bytes_digest": digest_bytes(inputs[name]), "tenant_id": "tenant-a"}
                 for name, resource_id in profile["input_bindings"].items()]
    resources += [{"resource_id": "artifact:report", "resource_class": "artifact", "access": "read_write",
                   "bytes_digest": None, "tenant_id": "tenant-a"},
                  {"resource_id": "sink:report", "resource_class": "sink", "access": "publish",
                   "bytes_digest": None, "tenant_id": "tenant-a"}]
    slot_bindings = [{"slot": name, "resource_id": resource_id} for name, resource_id in profile["input_bindings"].items()]
    slot_bindings += [{"slot": "output", "resource_id": "artifact:report"},
                      {"slot": "destination", "resource_id": "sink:report"}]
    subject = subject_digest or digest_jcs({"profile_id": profile_id, "skill": "clean-a"})
    binding = make_envelope("TaskBinding", {"task_instance_id": task_instance_id, "run_id": run_id,
        "subject_digest": subject, "domain_digest": domain["digest"], "tenant_id": "tenant-a",
        "resources": resources, "slot_bindings": slot_bindings})
    synthetic = digest_jcs("m3-local-fixture")
    run_request = make_envelope("RunRequest", {"subject_digest": subject,
        "case_digest": case_digest or synthetic, "suite_digest": suite_digest or synthetic,
        "plan_digest": plan_digest or synthetic,
        "config_digest": config_digest or synthetic, "authorization_domain_digest": domain["digest"],
        "initial_world_digest": initial_world_digest or synthetic, "repetition_index": repetition_index})
    approval = make_envelope("ApprovalRecord", {"approval_id": "approval-1",
        "authorization_domain_digest": domain["digest"], "contract_digest": contract,
        "factory_rule_digest": synthetic, "config_digest": synthetic, "issuer": "administrator",
        "issued_at": stamp(-1), "expires_at": None, "trust_revision": 1, "state": "active"})
    raw = {resource_id: inputs[name] for name, resource_id in profile["input_bindings"].items()}
    return domain, policy, binding, run_request, approval, raw
