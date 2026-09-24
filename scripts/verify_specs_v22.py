"""Run the V2.2 reference checks; never attest a deployed agent or model."""
from __future__ import annotations

import hashlib
import ast
import importlib
import json
import re
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "specs/v2.2"
EXPECTED_REVIEW_HASH = "b2517d55c8a95ce6fe19fb8dc3dfaa1a17d9c8a6ff69b9434a278f863736ea77"


def read_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {path}: {key}")
            result[key] = value
        return result
    return json.loads(path.read_text(), object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def verify_documents():
    review = ROOT / "reviews/v2.1-2026-09-23/REVIEW.zh-CN.md"
    assert hashlib.sha256(review.read_bytes()).hexdigest() == EXPECTED_REVIEW_HASH
    prd_path = ROOT / "SkillLoop-PRD-v2.2.zh-CN.md"
    prd = prd_path.read_text()
    wanted = [f"R{i:02}" for i in range(1, 43)]
    assert re.findall(r"^\| (R\d\d) \|", prd, re.M) == wanted
    resolution = read_json(SPEC / "review-resolution.json")
    assert [x["review_id"] for x in resolution["items"]] == wanted
    assert resolution["review_sha256"] == EXPECTED_REVIEW_HASH
    known_tests = set(test_ids())
    acceptance = read_json(SPEC / "operations/acceptance.json")
    accepted_by_id = {row["id"]: row for row in acceptance["tests"]}
    assert set(accepted_by_id) == {"ACCEPT-" + rid for rid in wanted}
    for row in acceptance["tests"]:
        assert row["runtime_status"] == "pending" and row["command_kind"] == "planned_not_implemented"
        assert row["positive_case"]["steps"] and row["negative_case"]["expected_result"]
        assert row["reference_test_ids"] and set(row["reference_test_ids"]) <= known_tests
    for row in resolution["items"]:
        assert row["decision_status"] == "decided"
        assert row["structural_expression"] == "specified_and_checked"
        assert row["counterexample_verification"] == "listed_reference_assertions_passed"
        assert row["verification_evidence"][0]["test_ids"] == accepted_by_id["ACCEPT-" + row["review_id"]]["reference_test_ids"]
        assert row["runtime_acceptance"] == "pending" and not row["runtime_evidence"]
        for value in row["specification_paths"]:
            assert (ROOT / value).is_file(), value
    clauses = re.findall(r"\*\*(SL22-[A-Z]+-\d+)\*\*", prd)
    index = read_json(SPEC / "requirements-index.json")
    assert len(clauses) == len(set(clauses))
    assert clauses == [x["requirement_id"] for x in index["requirements"]]
    for row in index["requirements"]:
        assert row["reference_test_ids"] and set(row["reference_test_ids"]) <= known_tests
        assert set(row["runtime_acceptance_ids"]) <= set(accepted_by_id)
    migration = read_json(SPEC / "probe-migration.json")
    assert [row["probe_id"] for row in migration["items"]] == [f"P{i:02}" for i in range(1,16)]
    assert all(row["test_id"] in known_tests for row in migration["items"])
    assert "SkillLoop-PRD-v2.2.zh-CN.md" in (ROOT / "PRD.md").read_text()
    assert len((ROOT / "PRD.md").read_text().splitlines()) <= 15, "PRD.md is an entry pointer"
    assert not re.search(r"四人分工|4\s*人分工|三天计划|3\s*天计划|Sprint-3D", prd)
    markdowns = [prd_path, ROOT / "PRD.md", ROOT / "Readme.md", *SPEC.rglob("*.md")]
    links = 0
    for path in markdowns:
        data = path.read_text()
        assert len(re.findall(r"^```", data, re.M)) % 2 == 0, f"unclosed fence: {path}"
        for target in re.findall(r"(?<!!)\[[^\]]*\]\(([^)]+)\)", data):
            target = target.strip("<>").split("#", 1)[0]
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            candidate = (path.parent / target).resolve()
            if candidate == SPEC / "verification-report.json":
                continue  # this command writes it after all checks pass
            assert candidate.exists(), f"missing link: {path}: {target}"
            links += 1
    json_files = list(SPEC.rglob("*.json"))
    for path in json_files:
        read_json(path)
    return {"review_items": len(wanted), "normative_clause_ids": len(clauses), "migrated_counterexamples": 15,
            "relative_links": links, "json_files_checked": len(json_files),
            "review_source_preserved": True}


def verification_inputs():
    """Make a saved report auditable against exact specification/test bytes."""
    paths = [ROOT / "SkillLoop-PRD-v2.2.zh-CN.md", ROOT / "PRD.md", ROOT / "Readme.md",
             *SPEC.rglob("*"), *ROOT.glob("scripts/*v22*.py"),
             *ROOT.glob("tests/spec_v22/*.py")]
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(set(paths)) if path.is_file()
            and path.name != "verification-report.json" and "__pycache__" not in path.parts}


def test_ids():
    result = []
    for path in sorted(ROOT.glob("tests/spec_v22/test_*.py")):
        for cls in ast.parse(path.read_text()).body:
            if isinstance(cls, ast.ClassDef):
                result.extend(f"{path.stem}.{cls.name}.{node.name}" for node in cls.body
                              if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"))
    return sorted(result)


def main():
    component_results = {}
    for name in ("core", "families", "operations"):
        module = importlib.import_module(f"spec_v22_{name}")
        result = module.verify()
        assert isinstance(result, dict), name
        if "status" in result:
            assert result["status"] == "pass", result
        component_results[name] = result
    tests = subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests/spec_v22", "-v"],
        cwd=ROOT, capture_output=True, text=True, check=False)
    if tests.returncode:
        sys.stderr.write(tests.stdout + tests.stderr)
        raise SystemExit(tests.returncode)
    match = re.search(r"Ran (\d+) tests?", tests.stderr)
    assert match, "unittest produced no test count"
    documents = verify_documents()
    report = {"document_version": "2.2", "api_major": 4, "status": "pass",
              "scope": "listed_executable_specification_assertions_only",
              "components": component_results, "unit_tests": int(match.group(1)),
              "test_ids": test_ids(), "input_sha256": verification_inputs(),
              "documents": documents,
              "runtime_security_verified": False, "dgx_model_verified": False,
              "offline_scanner_deployment_verified": False,
              "github_integration_verified": False, "repair_value_demonstrated": False}
    (SPEC / "verification-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
