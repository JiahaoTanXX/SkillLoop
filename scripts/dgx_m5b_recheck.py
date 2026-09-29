"""Re-reduce saved raw M5b scans after a reducer fix; never rerun the model."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.dgx_m5b_scan import PROFILES, REDTEAM
from skillloop.discovery.finding_targets import map_redteam_finding
from skillloop.discovery.scanner import reduce_scan
from skillloop.families.fixtures import load_example_skill
from skillloop.protocol import digest_bytes


def run(output: Path) -> dict:
    index_path = output / "scan-index.json"
    previous = index_path.read_bytes()
    index = json.loads(previous)
    if set(index["subjects"]) != set(PROFILES):
        raise ValueError("scan_subject_set_changed")
    rows = {}
    for profile in PROFILES:
        old = index["subjects"][profile]
        raw = (output / profile / "report.json").read_bytes()
        skill = load_example_skill(profile, root=REDTEAM)
        if old["subject_digest"] != digest_bytes(skill) or old["qwen_chat_requests"] < 1:
            raise ValueError("scan_binding_or_qwen_coverage_missing:" + profile)
        report, findings, dispositions = reduce_scan(profile, raw, old["cli_exit_code"],
            subject_digest=digest_bytes(skill), require_llm=True, allow_risk_exit=True)
        mapped = [item for finding in findings if
                  (item := map_redteam_finding(profile, finding, skill)) is not None]
        rows[profile] = {**old, "coverage": report["body"]["status"],
            "scanner_report": report, "findings": findings,
            "dispositions": dispositions, "mapped_findings": mapped,
            "status": "ready_for_attack" if report["body"]["status"] == "complete"
            and mapped else "incomplete"}
    backup = output / "scan-index.before-recheck.json"
    if backup.exists():
        raise FileExistsError("recheck_backup_already_exists")
    backup.write_bytes(previous)
    os.chmod(backup, 0o600)
    for profile, row in rows.items():
        path = output / profile / "scan-reduced.json"
        path.write_text(json.dumps(row, ensure_ascii=False, indent=2) + "\n")
        os.chmod(path, 0o600)
    index["subjects"] = rows
    index["status"] = "ready_for_attack" if all(
        row["status"] == "ready_for_attack" for row in rows.values()) else "incomplete"
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n")
    os.chmod(index_path, 0o600)
    return index


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan-output", required=True, type=Path)
    args = parser.parse_args()
    result = run(args.scan_output.resolve())
    print(json.dumps({"status": result["status"], "subjects": {
        profile: {"status": row["status"], "qwen_chat_requests": row["qwen_chat_requests"],
                  "mapped_findings": len(row["mapped_findings"])}
        for profile, row in result["subjects"].items()}}, ensure_ascii=False))
