"""Durable DGX M5 batch, bounded retry, and trusted gate with one active owner."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path.home() / "skillloop/platform/m5"
REPO = Path(__file__).resolve().parents[1]


def state(stage: str, status: str, code: int | None = None) -> None:
    record = {"stage": stage, "status": status, "exit_code": code,
              "updated_at": datetime.now(timezone.utc).isoformat()}
    temporary = ROOT / "pipeline-state.tmp"
    temporary.write_text(json.dumps(record, indent=2) + "\n")
    temporary.replace(ROOT / "pipeline-state.json")
    print(json.dumps(record), flush=True)


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / "pipeline.lock").open("a") as lock:
        os.chmod(lock.name, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        sources = sorted({path for folder in ("skillloop", "tests/implementation", "specs/v2.2/families")
                          for path in (REPO / folder).rglob("*")
                          if path.is_file() and "__pycache__" not in path.parts and
                          path.suffix in {".py", ".json", ".sql", ".md", ".txt", ".csv"}} |
                         set((REPO / "scripts").glob("dgx_m5_*.py")) |
                         {REPO / "scripts/spec_v22_core.py", REPO / "specs/v2.2/protocol.schema.json",
                          REPO / "specs/v2.2/operations/runtime-profile.json"})
        source_index = {str(path.relative_to(REPO)): hashlib.sha256(path.read_bytes()).hexdigest()
                        for path in sources}
        (ROOT / "source-index.json").write_text(json.dumps(source_index, sort_keys=True, indent=2) + "\n")
        print(json.dumps({"source_file_count": len(source_index), "source_index_digest": hashlib.sha256(
            json.dumps(source_index, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}), flush=True)
        steps = [("mechanism-tests", ["-m", "unittest", "discover", "-s", "tests/implementation", "-q"]),
                 ("attack-plans", ["scripts/dgx_m5_plans.py"]),
                 ("development-batch", ["scripts/dgx_m5_batch.py"]),
                 ("reserved-retry", ["scripts/dgx_m5_retry.py"]),
                 ("trusted-gate", ["scripts/dgx_m5_gate.py", str(ROOT)])]
        for stage, command in steps:
            state(stage, "running")
            completed = subprocess.run([sys.executable, *command], cwd=REPO, check=False)
            state(stage, "passed" if completed.returncode == 0 else "failed", completed.returncode)
            if completed.returncode != 0:
                raise SystemExit(completed.returncode)
        state("complete", "passed", 0)


if __name__ == "__main__":
    main()
