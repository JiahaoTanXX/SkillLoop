"""Compile the nine fixed attack plans with the exact deployed tokenizer."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skillloop.discovery.mutation import compile_mutation
from skillloop.discovery.planning import attack_plan
from skillloop.discovery.suite import compile_dev_suite
from skillloop.families import load_clean_fixture
from skillloop.protocol import digest_jcs
from skillloop.runtime.gateway import ExactDockerTokenizer


def main() -> None:
    tokenizer = ExactDockerTokenizer()
    root = Path.home() / "skillloop/platform/m5"
    plans = []
    for profile in ("orders_total", "refunds_total", "markdown_index"):
        compiled = compile_dev_suite(profile)
        source = load_clean_fixture(profile, "a")[0]["notes"]
        for case_id, spec in compiled["mutations"].items():
            mutation = compile_mutation(spec, source_bytes=source,
                                        profile_id=profile, count_tokens=tokenizer.count_text)
            plans.append({"case_id": case_id, "rendered_digest": mutation.rendered_digest,
                "rendered_token_count": mutation.rendered_token_count,
                "attack_plan": attack_plan(case=compiled["cases"][case_id], mutation=mutation)})
    (root / "base-attack-plans.json").write_text(json.dumps(plans, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"plan_count": len(plans), "plan_index_digest": digest_jcs(plans)}))


if __name__ == "__main__":
    main()
