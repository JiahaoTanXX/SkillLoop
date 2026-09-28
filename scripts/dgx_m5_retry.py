"""Use the second reserved attempt only for missing or incomplete M5 runs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.dgx_m5_development import run_one
from skillloop.discovery.suite import compile_dev_suite


def main() -> None:
    root = Path.home() / "skillloop/platform/m5"
    attempts = root / "attempts"
    attempts.mkdir(exist_ok=True)
    for profile in ("orders_total", "refunds_total", "markdown_index"):
        for case_id, case in compile_dev_suite(profile)["cases"].items():
            for repetition in range(case["body"]["repetitions"]):
                name = case_id.replace(".", "-") + "-" + str(repetition)
                current = root / "runs" / name
                previous = attempts / (name + "-attempt0")
                if previous.exists():
                    continue
                if current.exists() and (current / "result.json").exists():
                    result = json.loads((current / "result.json").read_text())["result"]
                    if result["body"]["coverage_complete"]:
                        continue
                if current.exists():
                    current.rename(previous)
                else:
                    previous.mkdir()
                    (previous / "missing-initial-attempt.json").write_text(json.dumps({
                        "case_id": case_id, "repetition": repetition,
                        "status": "initial_output_missing"}) + "\n")
                try:
                    print(json.dumps(run_one(case_id, repetition, current, attempt_index=1)), flush=True)
                except Exception as exc:
                    print(json.dumps({"case_id": case_id, "repetition": repetition,
                                      "status": "retry_failed", "error_type": type(exc).__name__}), flush=True)


if __name__ == "__main__":
    main()
