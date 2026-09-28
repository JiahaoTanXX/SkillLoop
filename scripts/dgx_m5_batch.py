"""Resume the frozen 45-run M5 development matrix and retain per-run evidence."""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.dgx_m5_development import run_one
from skillloop.discovery.scanner import reduce_scan
from skillloop.discovery.suite import compile_dev_suite, development_config, make_dev_plan
from skillloop.protocol import digest_bytes


ROOT = Path.home() / "skillloop/platform/m5"


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / "development-config.json").write_text(
        json.dumps(development_config(), indent=2) + "\n")
    for profile in ("orders_total", "refunds_total", "markdown_index"):
        compiled = compile_dev_suite(profile)
        plan = make_dev_plan(compiled, campaign_id="m5-development-1-" + profile)
        (ROOT / (profile + "-suite.json")).write_text(
            json.dumps(compiled["suite"], ensure_ascii=False, indent=2) + "\n")
        (ROOT / (profile + "-plan.json")).write_text(
            json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
        raw_path = ROOT / "scans" / ({"orders_total": "orders_total.json",
            "refunds_total": "refunds-total.json", "markdown_index": "markdown-index.json"}[profile])
        raw = raw_path.read_bytes()
        report, findings, dispositions = reduce_scan(profile, raw, 0,
                                                       subject_digest=compiled["skill_digest"])
        (ROOT / (profile + "-scan-reduced.json")).write_text(json.dumps({
            "report": report, "findings": findings, "dispositions": dispositions,
        }, ensure_ascii=False, indent=2) + "\n")
        if report["body"]["status"] != "complete":
            raise RuntimeError("scanner_coverage_incomplete:" + profile)
    jobs = []
    for profile in ("orders_total", "refunds_total", "markdown_index"):
        compiled = compile_dev_suite(profile)
        for case_id, case in compiled["cases"].items():
            for repetition in range(case["body"]["repetitions"]):
                output = ROOT / "runs" / (case_id.replace(".", "-") + "-" + str(repetition))
                if (output / "result.json").exists():
                    print(json.dumps({"case_id": case_id, "repetition": repetition,
                                      "status": "existing"}), flush=True)
                elif output.exists():
                    print(json.dumps({"case_id": case_id, "repetition": repetition,
                                      "status": "partial_output_requires_review"}), flush=True)
                else:
                    jobs.append((case_id, repetition, output))
    with ThreadPoolExecutor(max_workers=1) as pool:
        futures = {pool.submit(run_one, *job): job for job in jobs}
        for future in as_completed(futures):
            case_id, repetition, _output = futures[future]
            try:
                print(json.dumps(future.result()), flush=True)
            except Exception as exc:
                print(json.dumps({"case_id": case_id, "repetition": repetition,
                                  "error_type": type(exc).__name__, "status": "failed"}), flush=True)
    results = list((ROOT / "runs").glob("*/result.json"))
    print(json.dumps({"completed_result_files": len(results), "required": 45,
                      "result_index_digest": digest_bytes("\n".join(
                          sorted(str(path.relative_to(ROOT)) for path in results)).encode())}), flush=True)


if __name__ == "__main__":
    main()
