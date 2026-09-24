"""Verify that the client records a bounded SGLang request timeout."""

from __future__ import annotations

import argparse
import json
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default="http://127.0.0.1:30000")
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=0.001)
    args = parser.parse_args()
    body = json.dumps({"model": args.model,
                       "messages": [{"role": "user", "content": "Write a long explanation of sorting."}],
                       "max_tokens": 1024}).encode()
    request = urllib.request.Request(args.endpoint.rstrip("/") + "/v1/chat/completions",
                                     data=body, headers={"Content-Type": "application/json"})
    start = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=args.timeout_seconds) as response:
            response.read()
            outcome = {"kind": "response", "status": response.status}
    except (socket.timeout, TimeoutError) as exc:
        outcome = {"kind": "timeout", "exception_type": type(exc).__name__}
    except urllib.error.URLError as exc:
        outcome = {"kind": "transport_error", "exception_type": type(exc.reason).__name__}
    outcome["latency_seconds"] = round(time.monotonic() - start, 4)
    outcome["configured_timeout_seconds"] = args.timeout_seconds
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(outcome, indent=2) + "\n")
    print(json.dumps(outcome))


if __name__ == "__main__":
    main()
