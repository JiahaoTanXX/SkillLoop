"""Apply exact UTF-8 proposals without trusting model claims or patch totals."""

from __future__ import annotations

import re
from copy import deepcopy

from scripts.spec_v22_core import canonical_policy, is_policy_subset, validate_skill_package
from skillloop.families.fixtures import parse_frontmatter
from skillloop.protocol import digest_bytes, digest_jcs, make_envelope, validate_envelope


def bundle(files: dict[str, str], policy: dict, obligation_digest: str,
           compiler_digest: str) -> dict:
    validate_skill_package(files)
    parse_frontmatter(files["SKILL.md"].encode())
    return make_envelope("CandidateBundle", {
        "skill_digest": digest_jcs([{"path": path, "bytes_digest": digest_bytes(text.encode())}
                                    for path, text in sorted(files.items())]),
        "policy_digest": canonical_policy(policy)["digest"],
        "obligation_digest": obligation_digest, "compiler_digest": compiler_digest})


def _edits(files: dict[str, str], edits: list[dict]) -> tuple[dict, int, list[str]]:
    validate_skill_package(files)
    before_identity = parse_frontmatter(files["SKILL.md"].encode())
    grouped: dict[str, list[dict]] = {}
    result = deepcopy(files)
    for edit in edits:
        path = edit["path"]
        if not re.fullmatch(r"SKILL\.md|references/[A-Za-z0-9_-]+\.md", path) or path not in files:
            raise ValueError("forbidden_patch_path")
        grouped.setdefault(path, []).append(edit)
    cost = 0
    for path, changes in grouped.items():
        raw = files[path].encode()
        limit = raw.index(b"\n---\n", 4) + 5 if path == "SKILL.md" else 0
        previous_end = -1
        previous_start = -1
        for edit in sorted(changes, key=lambda item: (item["start_byte"], item["end_byte"])):
            start, end = edit["start_byte"], edit["end_byte"]
            if (edit["parent_bytes_digest"] != digest_bytes(raw) or start < limit or
                    start < previous_end or start == previous_start or end < start or end > len(raw)):
                raise ValueError("patch_range_parent_or_frontmatter")
            raw[:start].decode("utf-8")
            raw[:end].decode("utf-8")
            replacement = edit["replacement_utf8"].encode("utf-8")
            if raw[start:end] == replacement:
                raise ValueError("edit_no_change")
            cost += end - start + len(replacement)
            previous_start, previous_end = start, end
        for edit in sorted(changes, key=lambda item: item["start_byte"], reverse=True):
            raw = raw[:edit["start_byte"]] + edit["replacement_utf8"].encode() + raw[edit["end_byte"]:]
        result[path] = raw.decode()
        if result[path] == files[path]:
            raise ValueError("text_no_change")
    validate_skill_package(result)
    if parse_frontmatter(result["SKILL.md"].encode()) != before_identity:
        raise ValueError("patch_identity_changed")
    return result, cost, sorted(grouped)


def apply_proposal(proposal: dict, file_set: dict, history: list[dict], parent_policy: dict) -> dict:
    """History is re-applied, never accepted as caller-provided quota accounting."""
    if validate_envelope(proposal)["kind"] != "PatchProposal":
        raise ValueError("patch_kind")
    if len(history) >= 2:
        raise ValueError("patch_round_budget")
    fixed = {key: file_set[key] for key in ("obligation_digest", "compiler_digest")}
    p = proposal["body"]
    parent = bundle(file_set["files"], parent_policy, **fixed)
    if p["parent_subject_digest"] != parent["digest"] or file_set["subject_digest"] != parent["digest"]:
        raise ValueError("patch_parent_subject")
    policy = parent_policy if p["policy_digest"] is None else file_set.get("policies", {}).get(p["policy_digest"])
    if policy is None or not is_policy_subset(policy, parent_policy):
        raise ValueError("policy_expansion_or_unresolved")
    before_policy, policy = canonical_policy(parent_policy), canonical_policy(policy)
    if p["repair_kind"] == "policy_only" and p["edits"]:
        raise ValueError("policy_only_has_file_edits")
    if p["repair_kind"] == "text_only" and p["policy_digest"] is not None:
        raise ValueError("text_only_has_policy")
    if p["repair_kind"] in {"text_only", "combined"} and not p["edits"]:
        raise ValueError("text_patch_missing")
    if p["repair_kind"] in {"policy_only", "combined"} and policy == before_policy:
        raise ValueError("policy_no_change")
    touched: set[str] = set()
    cumulative = 0
    previous_files = previous_policy = None
    for entry in history:
        if set(entry) != {"proposal", "before_files", "after_files", "before_policy", "after_policy", "changed_bytes", "changed_paths"}:
            raise ValueError("patch_history_shape")
        prior_files = entry["before_files"]
        prior_policy = entry["before_policy"]
        if previous_files is not None and (prior_files != previous_files or prior_policy != previous_policy):
            raise ValueError("patch_history_chain")
        original_bundle = bundle(prior_files, prior_policy, **fixed)
        checked = apply_proposal(entry["proposal"], {
            "files": prior_files, "subject_digest": original_bundle["digest"],
            "policies": {canonical_policy(entry["after_policy"])["digest"]: entry["after_policy"]},
            **fixed}, [], prior_policy)
        if (checked["files"] != entry["after_files"] or checked["policy"] != entry["after_policy"] or
                checked["history_entry"]["changed_bytes"] != entry["changed_bytes"] or
                checked["changed_paths"] != entry["changed_paths"]):
            raise ValueError("patch_history_cost_or_result")
        touched.update(entry["changed_paths"])
        cumulative += entry["changed_bytes"]
        previous_files, previous_policy = entry["after_files"], entry["after_policy"]
    if history and (previous_files != file_set["files"] or previous_policy != before_policy):
        raise ValueError("patch_history_current_parent")
    result, cost, paths = _edits(file_set["files"], p["edits"])
    touched.update(paths)
    cumulative += cost
    original = history[0]["before_files"] if history else file_set["files"]
    growth = sum(len(v.encode()) for v in result.values()) - sum(len(v.encode()) for v in original.values())
    if len(touched) > 3 or cumulative > 8192 or growth > 4096:
        raise ValueError("patch_cumulative_budget")
    candidate = bundle(result, policy, **fixed)
    if candidate["digest"] == parent["digest"]:
        raise ValueError("patch_no_change")
    return {"files": result, "policy": policy, "changed_paths": paths,
        "cumulative_changed_bytes": cumulative, "cumulative_net_growth_bytes": max(0, growth),
        "candidate_subject_digest": candidate["digest"], "candidate_bundle": candidate,
        "history_entry": deepcopy({"proposal": proposal, "before_files": file_set["files"],
            "after_files": result, "before_policy": before_policy, "after_policy": policy,
            "changed_bytes": cost, "changed_paths": paths})}
