"""Check the pinned model's requested sampling fields and seed behavior on loopback."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path


def call(endpoint: str, model: str) -> dict:
    payload = {"model": model, "messages": [{"role": "user", "content": "Reply with OK."}],
               "temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.0,
               "presence_penalty": 0.0, "seed": 12345, "max_tokens": 128}
    req = urllib.request.Request(endpoint.rstrip("/") + "/v1/chat/completions",
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            body = json.loads(response.read())
            message = body["choices"][0]["message"]
            return {"status": response.status, "usage": body.get("usage"),
                    "finish_reason": body["choices"][0].get("finish_reason"),
                    "reasoning_separate": "reasoning_content" in message,
                    "content": message.get("content"), "reasoning": message.get("reasoning_content"),
                    "latency_seconds": round(time.monotonic() - start, 2)}
    except urllib.error.HTTPError as exc:
        return {"status": exc.code, "error": exc.read().decode("utf-8", errors="replace")[:180]}
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, ValueError) as exc:
        return {"error": type(exc).__name__ + ":" + str(exc)[:120]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default="http://127.0.0.1:30000")
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    first = call(args.endpoint, args.model)
    second = call(args.endpoint, args.model)
    result = {"first": {k: v for k, v in first.items() if k not in ("content", "reasoning")},
              "second": {k: v for k, v in second.items() if k not in ("content", "reasoning")},
              "same_seed_same_output": first.get("content") == second.get("content")
              and first.get("reasoning") == second.get("reasoning")
              if first.get("status") == second.get("status") == 200 else None}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
