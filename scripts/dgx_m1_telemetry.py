"""Collect compact M1 resource samples on the assigned DGX node.

This probe reads local host/container counters only. It contains no credentials,
model prompts, or fixture contents. The output is JSON Lines for later summary.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def _run(*args: str) -> str | None:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=5, check=True)
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def sample(log_path: Path, container: str) -> dict[str, object]:
    memory = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, _, value = line.partition(":")
        if key in ("MemTotal", "MemAvailable"):
            memory[key.lower() + "_kib"] = int(value.strip().split()[0])
    gpu = _run("nvidia-smi", "--query-gpu=utilization.gpu,power.draw", "--format=csv,noheader,nounits")
    docker = _run("docker", "stats", "--no-stream", "--format", "{{json .}}", container)
    try:
        docker_stats = json.loads(docker) if docker else None
    except json.JSONDecodeError:
        docker_stats = None
    return {
        "utc": datetime.now(timezone.utc).isoformat(),
        **memory,
        "gpu_utilization_power_csv": gpu,
        "docker_stats": docker_stats,
        "server_log_bytes": log_path.stat().st_size if log_path.exists() else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--server-log", required=True, type=Path)
    parser.add_argument("--container", default="skillloop-m1-sglang")
    parser.add_argument("--interval", type=int, default=10)
    parser.add_argument("--duration", type=int, default=3600)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + args.duration
    with args.output.open("a", encoding="utf-8") as output:
        while time.monotonic() < deadline:
            output.write(json.dumps(sample(args.server_log, args.container), ensure_ascii=False) + "\n")
            output.flush()
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
