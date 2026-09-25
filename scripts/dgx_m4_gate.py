"""Reduce private M4 traces to a non-content acceptance manifest on DGX."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skillloop.protocol import digest_bytes, validate_envelope


ROOT = Path.home() / "skillloop/platform/m4"
SUCCESS = {"orders-total-second": "orders_total", "refunds-total-first": "refunds_total",
           "markdown-index-second": "markdown_index", "orders-total-deny-recover": "orders_total"}
EARLY_PREFLIGHT = {"orders-total-second", "refunds-total-first"}


def inspect_case(name: str, profile_id: str) -> dict:
    root = ROOT / name
    manifest = json.loads((root / "manifest.json").read_text())
    evidence = validate_envelope(manifest["evidence_index"])
    observation = validate_envelope(manifest["observation"])
    assert manifest["profile_id"] == profile_id
    assert manifest["published"] and manifest["published_correct"]
    assert manifest["terminal_reason"] == "completed" and manifest["infra_status"] == "ok"
    assert not manifest["incomplete_reasons"] and evidence["body"]["complete"]
    assert observation["body"]["evidence_complete"]
    trace = root / "evidence" / manifest.get("trace_file", "run-1.jsonl")
    raw = trace.read_bytes()
    assert digest_bytes(raw) == evidence["body"]["trace_digest"] == manifest["trace_bytes_digest"]
    events = [json.loads(line) for line in raw.splitlines()]
    assert [digest_bytes(line + b"\n") for line in raw.splitlines()] == evidence["body"]["event_digests"]
    model = [event for event in events if event["type"] == "model_response"]
    tools = [event for event in events if event["type"] == "tool_result"]
    registered = {item for event in events if event["type"] == "batch_registered"
                  for item in event["registration"]["body"]["registered_call_digests"]}
    assert all(event["call_digest"] in registered for event in tools)
    assert all(event["native_tool_call_id"] and event["internal_call_id"] and event["args_digest"] for event in tools)
    assert len(tools) <= 12 and len(model) <= 16
    expected_offset = 66 if name in EARLY_PREFLIGHT else 0
    for event in model:
        usage = event["response"]["usage"]
        assert usage["prompt_tokens"] - event["preflight_prompt_tokens"] == expected_offset
        assert usage["prompt_tokens"] + 2048 <= 16384
        assert usage["completion_tokens"] <= 2048
        context = root / "evidence/contexts" / event["context_digest"].removeprefix("sha256:")
        assert digest_bytes(context.read_bytes()) == event["context_digest"]
    context_bytes = sum(item.stat().st_size for item in (root / "evidence/contexts").iterdir())
    assert len(raw) + context_bytes <= 4 * 1024 * 1024
    assert events[-1]["type"] == "terminal" and events[-1]["published"]
    assert isinstance(events[-1].get("final_text"), str) and events[-1]["final_text"]
    if name == "orders-total-deny-recover":
        assert any(event["result"]["body"].get("error_code") == "denied" for event in tools)
        assert any(event["result"]["body"]["tool"] == "publish_artifact" and
                   event["result"]["body"]["outcome"] == "ok" for event in tools)
    return {"profile_id": profile_id, "model_rounds": len(model), "tool_calls": len(tools),
            "max_prompt_tokens": max(event["response"]["usage"]["prompt_tokens"] for event in model),
            "max_completion_tokens": max(event["response"]["usage"]["completion_tokens"] for event in model),
            "trace_digest": digest_bytes(raw), "trace_bytes": len(raw),
            "denied_calls": sum(event["result"]["body"].get("error_code") == "denied" for event in tools),
            "preflight_offset_calibrated": expected_offset}


def main() -> None:
    successes = {name: inspect_case(name, profile) for name, profile in SUCCESS.items()}
    failure_root = ROOT / "markdown-index-first"
    failure = json.loads((failure_root / "manifest.json").read_text())
    assert not failure["published"] and failure["infra_status"] == "timeout"
    assert "provider_timeout" in failure["incomplete_reasons"]
    assert not failure["evidence_index"]["body"]["complete"]
    isolation = json.loads((ROOT / "isolation/isolation.json").read_text())
    assert all(isolation.values())
    inspect = json.loads(subprocess.run(["docker", "inspect", "skillloop-m4-sglang"],
        capture_output=True, text=True, timeout=10, check=True).stdout)[0]
    assert inspect["State"]["Running"] and not inspect["State"]["OOMKilled"]
    memory = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}",
        "skillloop-m4-sglang"], capture_output=True, text=True, timeout=10, check=True).stdout.strip()
    gate = {"gate": "M4_REAL_RUNTIME_PASS", "successes": successes,
            "preserved_incomplete_attempt": {"profile_id": "markdown_index",
                "infra_status": "timeout", "reason": "provider_timeout",
                "trace_digest": failure["trace_bytes_digest"]},
            "isolation_digest": digest_bytes((ROOT / "isolation/isolation.json").read_bytes()),
            "model_container_oom_killed": False, "model_container_memory_usage": memory}
    target = ROOT / "gate.json"
    target.write_text(json.dumps(gate, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"gate": gate["gate"], "case_names": list(successes),
                      "max_prompt_tokens": max(case["max_prompt_tokens"] for case in successes.values()),
                      "max_completion_tokens": max(case["max_completion_tokens"] for case in successes.values()),
                      "gate_digest": digest_bytes(target.read_bytes())}, ensure_ascii=False))


if __name__ == "__main__":
    main()
