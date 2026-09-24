"""Reproducible contract gate for the first implementation milestones.

This does not certify runtime identity, Linux isolation, or model behavior.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    reference = subprocess.run([sys.executable, "scripts/verify_specs_v22.py"],
                               cwd=ROOT, capture_output=True, text=True, check=True)
    reference_report = json.loads(reference.stdout)
    implementation = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests/implementation", "-v"],
        cwd=ROOT, capture_output=True, text=True, check=True)
    acceptance = json.loads((ROOT / "specs/v2.2/operations/acceptance.json").read_text())
    tests = acceptance["tests"]
    review_ids = {review for case in tests for review in case["review_ids"]}
    expected = {f"R{number:02d}" for number in range(1, 43)}
    if review_ids != expected or len({case["id"] for case in tests}) != len(tests):
        raise ValueError("acceptance_matrix_incomplete")
    if any(not case["reference_test_ids"] or not case["evidence_path"] or not case["command"] for case in tests):
        raise ValueError("acceptance_matrix_missing_test_or_evidence")
    if reference_report["status"] != "pass":
        raise ValueError("reference_specification_failed")
    print(json.dumps({
        "api_major": 4,
        "status": "pass",
        "scope": "M0_wire_and_reference_contracts_plus_M2_offline_business_only",
        "reference_unit_tests": reference_report["unit_tests"],
        "implementation_unit_tests": implementation.stderr.count(" ... ok"),
        "review_requirements_mapped": len(review_ids),
        "families": 2,
        "profiles": 3,
        "literal_goldens": 6,
        "runtime_identity_verified": False,
        "dgx_model_verified": False,
        "scanner_deployment_verified": False,
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
