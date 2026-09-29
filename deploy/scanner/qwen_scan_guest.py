"""Run pinned offline SkillSpector with its LLM analyzers via local Qwen."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from qwen_relay import run_guest_relay


def main() -> int:
    required = {
        "SKILLSPECTOR_PROVIDER": "openai",
        "SKILLSPECTOR_MODEL": "Qwen/Qwen3.8-27B-FP8",
        "OPENAI_BASE_URL": "http://127.0.0.1:31000/v1",
    }
    for key, value in required.items():
        if os.environ.get(key) != value:
            raise RuntimeError("scanner_model_configuration_mismatch:" + key)
    server, thread = run_guest_relay(Path("/model-bridge/qwen.sock"))
    try:
        command = [sys.executable, "/opt/skillloop-scanner/offline_osv.py", "scan",
                   "/subject/SKILL.md", "--format", "json", "--output", "/report/report.json"]
        # Deliberately omit --no-llm. A report with disabled/incomplete semantic
        # analyzers is rejected by the host-side coverage reducer.
        return subprocess.run(command, check=False, timeout=1200).returncode
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
