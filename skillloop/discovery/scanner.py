"""Reduce pinned SkillSpector reports against an independent analyzer registry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from skillloop.families.registry import FAMILY_SPEC
from skillloop.protocol import ProtocolError, decode_json, digest_bytes, digest_jcs, make_envelope


ANALYZERS = Path(__file__).with_name("analyzers.json")


class CoverageError(ProtocolError):
    pass


def reduce_scan(profile_id: str, raw_report: bytes, exit_code: int,
                *, subject_digest: str, require_llm: bool = False,
                allow_risk_exit: bool = False) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    registry = json.loads(ANALYZERS.read_text())
    if profile_id not in registry["profiles"]:
        raise CoverageError("unknown_profile")
    raw_digest = digest_bytes(raw_report)
    raw = decode_json(raw_report)
    if type(raw) is not dict:
        raise CoverageError("raw_report_shape")
    coverage = raw.get("analysis_completeness") or {}
    metadata = raw.get("metadata") or {}
    entries = coverage.get("analyzer_statuses") or []
    if type(entries) is not list or any(type(entry) is not dict for entry in entries):
        raise CoverageError("analyzer_entries")
    by_id = {entry.get("analyzer_id"): entry for entry in entries}
    semantic = set(registry["explicitly_disabled_semantic_analyzers"])
    required = set(registry["required_static_analyzers"]) | (semantic if require_llm else set())
    optional = set() if require_llm else semantic
    identities_ok = len(by_id) == len(entries) and set(by_id) == required | optional
    risk = (raw.get("risk_assessment") or {}).get("score")
    risk_exit = (allow_risk_exit and exit_code == 1 and
                 type(risk) in (int, float) and risk > 50)
    complete = ((exit_code == 0 or risk_exit) and raw.get("execution_successful") is True and
                coverage.get("execution_successful") is True and
                coverage.get("is_complete") is True and coverage.get("status") == "complete" and
                metadata.get("skillspector_version") == registry["scanner_version"] and identities_ok)
    normalized: list[dict[str, Any]] = []
    for name in sorted(required):
        entry = by_id.get(name)
        if entry is None:
            complete = False
            normalized.append({"analyzer_id": name, "status": "unknown",
                               "reason": "missing_analyzer", "evidence_digest": None})
            continue
        status = entry.get("status")
        if status not in {"completed", "not_applicable"}:
            complete = False
        # Pinned 2.11.2 meta_analyzer.py returns an explicit non-applicability
        # event before making a model call when there are no findings to review.
        # The three semantic inspection nodes still must actually complete.
        meta_empty = (name == "meta_analyzer" and status == "not_applicable" and
            entry.get("reason_code") == "no_applicable_files" and
            all(type(entry.get(key)) is int and entry[key] == 0 for key in
                ("planned_work", "completed", "partial", "skipped", "failed", "unaccounted")) and
            type(raw.get("issues")) is list and not raw["issues"] and
            coverage.get("findings_before_filtering") == 0 and
            coverage.get("findings_after_filtering") == 0 and
            metadata.get("llm_requested") is True and metadata.get("llm_available") is True and
            metadata.get("meta_analysis_applied") is False)
        if require_llm and name in semantic and status != "completed" and not meta_empty:
            complete = False
        if any(entry.get(key, 0) for key in ("partial", "failed", "unaccounted")):
            complete = False
        if status == "not_applicable" and not entry.get("reason_code"):
            complete = False
        normalized.append({"analyzer_id": name,
                           "status": status if status in {"completed", "not_applicable", "failed"} else "unknown",
                           "reason": entry.get("reason_code") if status != "completed" else None,
                           "evidence_digest": digest_jcs(entry)})
    for name in optional:
        if by_id.get(name, {}).get("status") not in {"disabled", "not_applicable"}:
            complete = False
    if coverage.get("ledger_exceptions") or coverage.get("limitations") or coverage.get("entirely_uninspected_files"):
        complete = False
    profile_digest = digest_bytes((FAMILY_SPEC / "profiles" / f"{profile_id}.json").read_bytes())
    findings: list[dict[str, Any]] = []
    for issue in raw.get("issues", []):
        location = issue.get("location") or {}
        path = str(location.get("file") or "unknown")
        line = location.get("start_line") or 1
        is_manifest_path = issue.get("id") == "AS3" and path == "manifest.json"
        findings.append(make_envelope("LogicalFinding", {
            "finding_id": f"{profile_id}:{issue['finding_id']}",
            "scanner_report_digest": raw_digest, "rule_id": str(issue["id"]),
            "severity": str(issue.get("severity", "unknown")).lower(),
            "location": {"path": path, "start_line": line, "end_line": location.get("end_line") or line},
            "description": str(issue.get("finding") or issue.get("explanation") or
                               issue.get("pattern") or issue["id"]),
            "dynamic_applicability": "static_only" if is_manifest_path else "unknown",
            "objective_ids": [],
        }))
    report = make_envelope("ScannerReport", {"profile_digest": profile_digest,
        "scanner_version": registry["scanner_version"],
        "status": "complete" if complete else "incomplete",
        "upstream_exit_code": max(exit_code, 0),
        "raw_report_digest": raw_digest,
        "analyzers": normalized,
        "finding_digests": [item["digest"] for item in findings]})
    dispositions = [make_envelope("FindingDisposition", {
        "finding_digest": item["digest"], "verification": "unverified",
        "disposition": "open", "actor": "evaluator",
        "evidence_digests": [raw_digest], "expires_at": None,
        "scope_subject_digest": subject_digest}) for item in findings]
    return report, findings, dispositions
