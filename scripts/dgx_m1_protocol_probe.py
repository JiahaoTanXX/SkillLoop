"""Bounded OpenAI-compatible tool/parser checks for the local M1 SGLang service."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path


ECHO = {"type": "function", "function": {"name": "echo", "description": "Return the supplied text",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}},
                       "required": ["text"], "additionalProperties": False}}}


def request(endpoint: str, data: bytes, timeout: int) -> tuple[int, dict | None, float]:
    start = time.monotonic()
    req = urllib.request.Request(endpoint.rstrip("/") + "/v1/chat/completions", data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, json.loads(response.read()), time.monotonic() - start
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read())
        except (UnicodeError, json.JSONDecodeError):
            body = None
        return exc.code, body, time.monotonic() - start


def tool_case(endpoint: str, model: str, prompt: str, expected: list[str], timeout: int) -> dict:
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "tools": [ECHO], "tool_choice": "auto", "temperature": 1.0, "top_p": 0.95,
                       "max_tokens": 2048}).encode()
    try:
        status, response, latency = request(endpoint, body, timeout)
        if status != 200 or not isinstance(response, dict):
            return {"status": status, "error": "http_or_body", "latency_seconds": round(latency, 2)}
        choice = response["choices"][0]
        message = choice["message"]
        calls = message.get("tool_calls") or []
        args = [json.loads(call["function"]["arguments"]) for call in calls]
        names = [call["function"]["name"] for call in calls]
        values = [item.get("text") if isinstance(item, dict) else None for item in args]
        return {"status": status, "tool_calls": len(calls), "names": names,
                "expected_values_observed": sorted(values) == sorted(expected),
                "finish_reason": choice.get("finish_reason"),
                "separate_reasoning": "reasoning_content" in message,
                "usage": response.get("usage"), "latency_seconds": round(latency, 2)}
    except (urllib.error.URLError, TimeoutError, KeyError, TypeError, ValueError, IndexError) as exc:
        return {"error": type(exc).__name__ + ":" + str(exc)[:120]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default="http://127.0.0.1:30000")
    parser.add_argument("--model", required=True)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = {
        "single": tool_case(args.endpoint, args.model,
                            "Call the echo tool exactly once with text ALPHA. Do not answer in plain text.",
                            ["ALPHA"], args.timeout),
        "multi": tool_case(args.endpoint, args.model,
                           "In this one assistant turn, call the echo tool twice: first with text ALPHA, "
                           "then with text BETA. Do not answer in plain text.",
                           ["ALPHA", "BETA"], args.timeout),
    }
    try:
        status, body, elapsed = request(args.endpoint, b'{"model":', args.timeout)
        result["malformed_request"] = {"status": status, "structured_error": isinstance(body, dict),
                                       "latency_seconds": round(elapsed, 2)}
    except (urllib.error.URLError, TimeoutError) as exc:
        result["malformed_request"] = {"error": type(exc).__name__ + ":" + str(exc)[:120]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
