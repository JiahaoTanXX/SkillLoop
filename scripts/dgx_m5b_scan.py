"""Run LLM-enabled SkillSpector against three isolated vulnerable Skills.

The scanner retains Docker --network none. A mounted Unix socket connects its
loopback OpenAI-compatible client to the host's loopback-only SGLang service.
No report is accepted as LLM-covered without completed semantic analyzers
and at least one observed chat-completions request through that bridge.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deploy.scanner.qwen_relay import HostModelBridge
from skillloop.discovery.finding_targets import map_redteam_finding
from skillloop.discovery.scanner import reduce_scan
from skillloop.families.fixtures import load_example_skill
from skillloop.protocol import digest_bytes


REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "deploy/scanner"
REDTEAM = REPO / "specs/v2.2/families/redteam"
PROFILES = ("orders_total", "refunds_total", "markdown_index")
MODEL = "Qwen/Qwen3.8-27B-FP8"


def model_preflight(model_url: str) -> list[str]:
    if model_url != "http://127.0.0.1:30000":
        raise ValueError("only_pinned_loopback_model_endpoint_supported")
    with urllib.request.urlopen(model_url + "/v1/models", timeout=10) as response:
        payload = json.load(response)
    ids = [item.get("id") for item in payload.get("data", []) if isinstance(item, dict)]
    if MODEL not in ids and "/model" not in ids:
        raise RuntimeError("qwen_model_identity_not_confirmed")
    return ids


def docker_command(*, image: str, osv_data: Path, bridge_dir: Path,
                   skill_dir: Path, report_dir: Path) -> list[str]:
    return ["docker", "run", "--rm", "--network", "none", "--read-only",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--user", f"{os.getuid()}:{os.getgid()}", "--pids-limit", "256",
            "--memory", "2g", "--cpus", "2", "--tmpfs", "/tmp:rw,nosuid,size=256m",
            "--mount", f"type=bind,src={CONFIG},dst=/scan-config,readonly",
            "--mount", f"type=bind,src={skill_dir},dst=/subject,readonly",
            "--mount", f"type=bind,src={osv_data},dst=/osv-data,readonly",
            "--mount", f"type=bind,src={bridge_dir},dst=/model-bridge,readonly",
            "--mount", f"type=bind,src={report_dir},dst=/report",
            "--env", "HOME=/tmp", "--env", "XDG_CACHE_HOME=/tmp/cache",
            "--env", "LANGCHAIN_TRACING_V2=false", "--env", "HTTP_PROXY=",
            "--env", "HTTPS_PROXY=", "--env", "ALL_PROXY=",
            "--env", "NO_PROXY=127.0.0.1,localhost",
            "--env", "SKILLSPECTOR_PROVIDER=openai",
            "--env", "SKILLSPECTOR_MAX_LLM_CONCURRENCY=1",
            "--env", "SKILLSPECTOR_MAX_WORKFLOW_SECONDS=900",
            "--env", f"SKILLSPECTOR_MODEL={MODEL}",
            "--env", "SKILLSPECTOR_MODEL_REGISTRY=/scan-config/qwen-model-registry.yaml",
            "--env", "OPENAI_BASE_URL=http://127.0.0.1:31000/v1",
            "--env", "OPENAI_API_KEY=local-scanner-only",
            "--entrypoint", "python", image, "/scan-config/qwen_scan_guest.py"]


def run(*, image: str, osv_data: Path, output: Path,
        model_url: str = "http://127.0.0.1:30000") -> dict:
    model_ids = model_preflight(model_url)
    if output.exists():
        raise FileExistsError("campaign_output_already_exists:" + str(output))
    output.mkdir(parents=True, mode=0o700)
    result = {"campaign_kind": "m5b-vulnerable-skill-llm-scan",
              "model": MODEL, "model_endpoint": model_url,
              "model_ids": model_ids, "scanner_image": image, "subjects": {}}
    with tempfile.TemporaryDirectory(prefix="skillloop-m5b-bridge-") as temporary:
        bridge_dir = Path(temporary)
        os.chmod(bridge_dir, 0o700)
        with HostModelBridge(bridge_dir / "qwen.sock") as bridge:
            for profile in PROFILES:
                skill_dir = REDTEAM / "skills" / profile.replace("_", "-")
                report_dir = output / profile
                report_dir.mkdir(mode=0o700)
                skill = load_example_skill(profile, root=REDTEAM)
                before = bridge.chat_requests
                command = docker_command(image=image, osv_data=osv_data,
                    bridge_dir=bridge_dir, skill_dir=skill_dir, report_dir=report_dir)
                try:
                    completed = subprocess.run(command, capture_output=True,
                                               timeout=1200, check=False)
                    exit_code = completed.returncode
                    (report_dir / "scanner-stdout.log").write_bytes(completed.stdout)
                    (report_dir / "scanner-stderr.log").write_bytes(completed.stderr)
                except subprocess.TimeoutExpired as exc:
                    exit_code = 124
                    (report_dir / "scanner-stdout.log").write_bytes(exc.stdout or b"")
                    (report_dir / "scanner-stderr.log").write_bytes(exc.stderr or b"")
                calls = bridge.chat_requests - before
                raw_path = report_dir / "report.json"
                row = {"subject_digest": digest_bytes(skill), "cli_exit_code": exit_code,
                       "qwen_chat_requests": calls, "raw_report_present": raw_path.is_file()}
                if raw_path.is_file():
                    try:
                        report, findings, dispositions = reduce_scan(profile,
                            raw_path.read_bytes(), exit_code, subject_digest=digest_bytes(skill),
                            require_llm=True, allow_risk_exit=True)
                        mapped = [item for finding in findings if
                                  (item := map_redteam_finding(profile, finding, skill)) is not None]
                        row.update({"coverage": report["body"]["status"],
                            "scanner_report": report, "findings": findings,
                            "dispositions": dispositions, "mapped_findings": mapped,
                            "status": "ready_for_attack" if report["body"]["status"] == "complete"
                            and calls > 0 and mapped else "incomplete"})
                    except (ValueError, KeyError, TypeError) as error:
                        row.update({"status": "incomplete", "parse_error": type(error).__name__})
                else:
                    row["status"] = "incomplete"
                result["subjects"][profile] = row
                (report_dir / "scan-reduced.json").write_text(
                    json.dumps(row, ensure_ascii=False, indent=2) + "\n")
                os.chmod(report_dir / "scan-reduced.json", 0o600)
    result["status"] = "ready_for_attack" if all(
        row["status"] == "ready_for_attack" for row in result["subjects"].values()) else "incomplete"
    (output / "scan-index.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    os.chmod(output / "scan-index.json", 0o600)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True, help="Pinned SkillSpector offline image ref")
    parser.add_argument("--osv-data", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = run(image=args.image, osv_data=args.osv_data.resolve(), output=args.output.resolve())
    print(json.dumps({"status": result["status"], "subjects": {
        profile: {"status": row["status"], "qwen_chat_requests": row["qwen_chat_requests"],
                  "findings": len(row.get("findings", [])),
                  "mapped_findings": len(row.get("mapped_findings", []))}
        for profile, row in result["subjects"].items()}}, ensure_ascii=False))
    if result["status"] != "ready_for_attack":
        raise SystemExit(4)


if __name__ == "__main__":
    main()
