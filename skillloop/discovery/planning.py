"""Bind base and finding driven attack plans to independently checked mutations."""

from __future__ import annotations

from typing import Any
import json
from pathlib import Path

from skillloop.families import load_clean_fixture
from skillloop.protocol import ProtocolError, digest_jcs, make_envelope, validate_envelope

from .mutation import RenderedMutation, compile_mutation, make_dev_mutation, require_distinct_variant
from .suite import compile_dev_suite


VARIANTS = Path(__file__).with_name("variants.json")


def attack_plan(*, case: dict[str, Any], mutation: RenderedMutation,
                finding: dict[str, Any] | None = None,
                variant_of: dict[str, Any] | None = None,
                original_mutation: RenderedMutation | None = None,
                generator_config_digest: str | None = None) -> dict[str, Any]:
    validate_envelope(case)
    if case["kind"] != "CaseTemplate" or case["body"]["case_kind"] != "attack":
        raise ProtocolError("attack_case_required")
    body = case["body"]
    if body["mutation_digest"] != mutation.spec["digest"]:
        raise ProtocolError("plan_mutation_mismatch")
    if finding is not None:
        validate_envelope(finding)
        if finding["kind"] != "LogicalFinding" or finding["body"]["dynamic_applicability"] != "applicable":
            raise ProtocolError("finding_not_dynamic")
        if not set(body["objective_ids"]) <= set(finding["body"]["objective_ids"]):
            raise ProtocolError("finding_objective_mismatch")
    if variant_of is not None:
        validate_envelope(variant_of)
        if finding is None or original_mutation is None:
            raise ProtocolError("variant_original_required")
        require_distinct_variant(original_mutation, mutation)
        if (variant_of["kind"] != "CaseTemplate" or
            variant_of["body"]["business_projection_digest"] != body["business_projection_digest"] or
            variant_of["body"]["clean_pair_digest"] != body["clean_pair_digest"]):
            raise ProtocolError("variant_projection_mismatch")
    return make_envelope("AttackPlan", {
        "finding_digest": finding["digest"] if finding else None,
        "objective_ids": body["objective_ids"], "case_template_digest": case["digest"],
        "mutation_digest": mutation.spec["digest"], "allowed_slot_ids": ["notes"],
        "clean_pair_digest": body["clean_pair_digest"],
        "generator_config_digest": generator_config_digest or digest_jcs(json.loads(VARIANTS.read_text())),
        "variant_of_case_digest": variant_of["digest"] if variant_of else None})


def generate_finding_attacks(*, profile_id: str, finding: dict[str, Any], count_tokens) -> list[dict]:
    """Expand only an approved dynamic finding into original and distinct tactics."""
    validate_envelope(finding)
    if finding["kind"] != "LogicalFinding" or finding["body"]["dynamic_applicability"] != "applicable":
        raise ProtocolError("finding_not_dynamic")
    objective_ids = finding["body"]["objective_ids"]
    variants = json.loads(VARIANTS.read_text())["variants"]
    if not objective_ids or len(set(objective_ids)) != len(objective_ids) or any(
        objective not in variants for objective in objective_ids):
        raise ProtocolError("finding_objective_not_registered")
    compiled = compile_dev_suite(profile_id)
    source = load_clean_fixture(profile_id, "a")[0]["notes"]
    result = []
    for objective_id in objective_ids:
        base = next(case for case in compiled["cases"].values()
                    if case["body"]["objective_ids"] == [objective_id])
        base_spec = compiled["mutations"][base["body"]["case_id"]]
        original = compile_mutation(base_spec, source_bytes=source,
                                    profile_id=profile_id, count_tokens=count_tokens)
        variant_spec = make_dev_mutation(profile_id=profile_id, source_bytes=source,
                                         payload_bytes=variants[objective_id].encode("utf-8"))
        variant = compile_mutation(variant_spec, source_bytes=source,
                                   profile_id=profile_id, count_tokens=count_tokens)
        identity = f"{profile_id}.finding-{finding['digest'][7:19]}.{objective_id}"
        original_case = make_envelope("CaseTemplate", dict(base["body"], case_id=identity + ".original"))
        variant_case = make_envelope("CaseTemplate", dict(base["body"], case_id=identity + ".variant",
                                                         mutation_digest=variant_spec["digest"]))
        result.append({"objective_id": objective_id,
            "original": {"case": original_case, "rendered": original,
                "plan": attack_plan(case=original_case, mutation=original, finding=finding)},
            "variant": {"case": variant_case, "rendered": variant,
                "plan": attack_plan(case=variant_case, mutation=variant, finding=finding,
                                     variant_of=original_case, original_mutation=original)}})
    return result
