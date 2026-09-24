"""Local-only M1 model feasibility probe. Not a production Runtime or Proxy.

Run against a loopback SGLang OpenAI-compatible endpoint. Raw model output and
fixture bytes remain on DGX; stdout contains only a compact result summary.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skillloop.families import FamilyRegistry, build_artifact, load_clean_fixture, load_example_skill, validate_artifact
from skillloop.protocol import ProtocolError, decode_json, digest_bytes


def _tool(name: str, properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "function", "function": {"name": name, "description": name.replace("_", " "),
            "parameters": {"type": "object", "properties": properties,
                           "required": list(properties), "additionalProperties": False}}}


TOOLS = [
    _tool("read_resource", {"resource_id": {"type": "string"}}),
    _tool("build_artifact", {"input_bindings": {"type": "object"}, "output_id": {"type": "string"},
                             "transform_id": {"type": "string"}, "expected_version": {"type": "integer"},
                             "idempotency_key": {"type": "string"}}),
    _tool("write_artifact", {"output_id": {"type": "string"}, "content": {"type": "string"}}),
    _tool("validate_artifact", {"output_id": {"type": "string"}}),
    _tool("prepare_publication", {"output_id": {"type": "string"}}),
    _tool("publish_artifact", {"output_id": {"type": "string"}}),
]


def _request(endpoint: str, model: str, messages: list[dict[str, Any]], timeout: int) -> tuple[dict[str, Any], float]:
    body = json.dumps({"model": model, "messages": messages, "tools": TOOLS, "tool_choice": "auto",
                       "temperature": 1.0, "top_p": 0.95, "max_tokens": 2048},
                      ensure_ascii=False).encode()
    start = time.monotonic()
    request = urllib.request.Request(endpoint.rstrip("/") + "/v1/chat/completions", data=body,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        parsed = decode_json(response.read())
    return parsed, time.monotonic() - start


class MockTools:
    def __init__(self, profile_id: str, suffix: str, reject_once: bool):
        self.profile_id = profile_id
        self.profile = FamilyRegistry().profile(profile_id)
        if suffix == "max":
            if self.profile["family_id"] == "table-report":
                mapping = self.profile["mapping"]
                directory = ",".join(mapping["directory_header"]) + "\na," + "A" * 64 + "\n"
                records = ",".join(mapping["records_header"]) + "\n" + "".join(
                    f"r{i},a,1000000000,{mapping['included_state']}\n" for i in range(20))
                self.inputs = {"directory": directory.encode(), "records": records.encode(), "notes": b"N" * 1024}
            else:
                self.inputs = {"document": b"# A\n" + b"Text.\n" * 99, "notes": b"N" * 1024}
            self.expected = build_artifact(profile_id, self.inputs)
            validate_artifact(profile_id, self.inputs, self.expected)
        else:
            self.inputs, self.expected = load_clean_fixture(profile_id, suffix)
        self.resources = {resource_id: self.inputs[slot]
                          for slot, resource_id in self.profile["input_bindings"].items()}
        self.read_slots: set[str] = set()
        self.built: bytes | None = None
        self.stored: bytes | None = None
        self.validated = False
        self.prepared = False
        self.published = False
        self.reject_once = reject_once
        self.rejections = 0

    def call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        try:
            if name == "read_resource":
                if set(args) != {"resource_id"} or args["resource_id"] not in self.resources:
                    raise ProtocolError("unregistered_resource")
                resource_id = args["resource_id"]
                self.read_slots.add(resource_id)
                return {"content": self.resources[resource_id].decode("utf-8")}
            if name == "build_artifact":
                FamilyRegistry().validate_build_args(self.profile_id, args)
                if args["input_bindings"] != self.profile["input_bindings"]:
                    raise ProtocolError("unregistered_binding")
                if self.read_slots != set(self.resources):
                    raise ProtocolError("read_required")
                if self.reject_once:
                    self.reject_once = False
                    raise ProtocolError("temporary_mock_rejection_retry")
                self.built = build_artifact(self.profile_id, self.inputs)
                return {"content": self.built.decode("utf-8"), "digest": digest_bytes(self.built)}
            if set(args) != ({"output_id", "content"} if name == "write_artifact" else {"output_id"}):
                raise ProtocolError("tool_arguments")
            if args["output_id"] != "artifact:report":
                raise ProtocolError("unregistered_artifact")
            if name == "write_artifact":
                raw = args["content"].encode("utf-8")
                if self.built is None or raw != self.built:
                    raise ProtocolError("unexpected_artifact_bytes")
                self.stored = raw
                return {"digest": digest_bytes(raw)}
            if name == "validate_artifact":
                if self.stored is None:
                    raise ProtocolError("missing_artifact")
                validate_artifact(self.profile_id, self.inputs, self.stored)
                self.validated = True
                return {"validated": True}
            if name == "prepare_publication":
                if not self.validated:
                    raise ProtocolError("validation_required")
                self.prepared = True
                return {"prepared": True}
            if name == "publish_artifact":
                if not self.prepared:
                    raise ProtocolError("prepare_required")
                self.published = True
                return {"published": True}
            raise ProtocolError("unknown_tool")
        except (ProtocolError, KeyError, TypeError, ValueError) as exc:
            self.rejections += 1
            return {"error": str(exc)}


def run_case(endpoint: str, model: str, profile_id: str, suffix: str,
             reject_once: bool, timeout: int) -> dict[str, Any]:
    mock = MockTools(profile_id, suffix, reject_once)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": "You are an agent operating only the registered mock tools. Follow the Skill. "
         "Do not invent resource IDs or operations. Recover from tool errors when possible."},
        {"role": "user", "content": load_example_skill(profile_id).decode("utf-8") + "\n\n" +
         "For this task, input bindings are " + json.dumps(mock.profile["input_bindings"], sort_keys=True) +
         ". Build with output_id artifact:report, transform_id " + mock.profile["operation"] +
         ", expected_version 0 and any nonempty idempotency_key. Write the exact build content; then validate, "
         "prepare, and publish. Read every named input before building."},
    ]
    usage: dict[str, int] = {}
    calls: list[str] = []
    latency = 0.0
    error: str | None = None
    for _ in range(16):
        try:
            response, elapsed = _request(endpoint, model, messages, timeout)
            latency += elapsed
            for key, value in response.get("usage", {}).items():
                if type(value) is int:
                    usage[key] = usage.get(key, 0) + value
            message = response["choices"][0]["message"]
            tool_calls = message.get("tool_calls") or []
            messages.append({"role": "assistant", "content": message.get("content"),
                             **({"tool_calls": tool_calls} if tool_calls else {})})
            if not tool_calls:
                break
            for call in tool_calls:
                name = call["function"]["name"]
                calls.append(name)
                try:
                    args = decode_json(call["function"]["arguments"].encode("utf-8"))
                    if type(args) is not dict:
                        raise ProtocolError("tool_args_not_object")
                    result = mock.call(name, args)
                except (ProtocolError, KeyError, TypeError, ValueError) as exc:
                    mock.rejections += 1
                    result = {"error": str(exc)}
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result)})
            if mock.published:
                break
        except (urllib.error.URLError, TimeoutError, KeyError, IndexError, ProtocolError) as exc:
            error = type(exc).__name__ + ":" + str(exc)[:120]
            break
    return {"profile_id": profile_id, "fixture": suffix, "reject_once": reject_once,
            "published": mock.published, "correct_bytes": mock.stored == mock.expected,
            "calls": calls, "rejections": mock.rejections, "usage": usage,
            "latency_seconds": round(latency, 2), "error": error}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default="http://127.0.0.1:30000")
    parser.add_argument("--model", required=True)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    results = [run_case(args.endpoint, args.model, profile, "a", False, args.timeout)
               for profile in ("orders_total", "refunds_total", "markdown_index")]
    results.append(run_case(args.endpoint, args.model, "orders_total", "b", True, args.timeout))
    results.extend(run_case(args.endpoint, args.model, profile, "max", False, args.timeout)
                   for profile in ("orders_total", "refunds_total", "markdown_index"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"cases": len(results), "published_correct": sum(
        case["published"] and case["correct_bytes"] for case in results),
        "profile_results": [{"profile_id": case["profile_id"], "published": case["published"],
                             "correct_bytes": case["correct_bytes"], "error": case["error"]} for case in results]},
        ensure_ascii=False))


if __name__ == "__main__":
    main()
