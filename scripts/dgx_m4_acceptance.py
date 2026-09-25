"""DGX-only M4 fixed normal chain; raw evidence stays in the assigned node."""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skillloop.families import load_clean_fixture, load_example_skill
from skillloop.protocol import digest_bytes, digest_jcs
from skillloop.proxy.server import ProxyServer
from skillloop.proxy.store import ProxyStore
from skillloop.runtime.adapter import AgentAdapter
from skillloop.runtime.client import ProxyClient
from skillloop.runtime.gateway import ExactDockerTokenizer, SGLangGateway
from tests.implementation.test_proxy_store import fixture, stamp


def run_one(profile_id: str, output: Path, instruction_suffix: str = "",
            attempt_index: int = 0) -> dict:
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    domain, policy, binding, request, approval, raw = fixture(profile_id)
    store = ProxyStore(output / "authority.db", deployment_epoch="m4-acceptance")
    store.stage_approval(domain, approval)
    store.activate_approval(approval["digest"], 0, operation_id="activate-m4",
                            request_digest=digest_jcs("activate-m4"))
    store.stage_task(domain=domain, policy=policy, binding=binding, run_request=request,
                     profile_id=profile_id, resources=raw, approval_digest=approval["digest"],
                     run_deadline=stamp(240), campaign_id="m4-acceptance")
    store.start_run(request["digest"], binding["digest"], operation_id="start-m4",
                    request_digest=digest_jcs("start-m4"))
    server = ProxyServer(store, output / "sockets", controller_uid=os.getuid(),
                         runtime_uid=os.getuid(), socket_mode=0o600)
    with server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            adapter = AgentAdapter(proxy=ProxyClient(output / "sockets"),
                gateway=SGLangGateway("http://127.0.0.1:30000", ExactDockerTokenizer()),
                private_root=output / "evidence")
            result = adapter.run(profile_id=profile_id, skill_bytes=load_example_skill(profile_id),
                run_request=request, task_binding=binding, fence=1, trust_revision=1,
                deployment_epoch="m4-acceptance", deadline_seconds=180,
                instruction_suffix=instruction_suffix, attempt_index=attempt_index)
        finally:
            server.stop()
            thread.join(timeout=2)
    publication = store.inspect_publication(binding["body"]["task_instance_id"])
    _inputs, expected = load_clean_fixture(profile_id, "a")
    published_correct = publication is not None and publication["content"] == expected
    manifest = {"profile_id": profile_id, "published": result["published"],
        "published_correct": published_correct, "terminal_reason": result["terminal_reason"],
        "infra_status": result["infra_status"], "incomplete_reasons": result["incomplete_reasons"],
        "rounds": result["rounds"], "usage": result["usage"],
        "evidence_index": result["evidence_index"], "observation": result["observation"],
        "publication_digest": publication["artifact_digest"] if publication else None,
        "trace_file": Path(result["trace_path"]).name,
        "trace_bytes_digest": digest_bytes(Path(result["trace_path"]).read_bytes())}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return {key: manifest[key] for key in ("profile_id", "published", "published_correct",
                                            "terminal_reason", "infra_status", "incomplete_reasons",
                                            "rounds", "usage", "trace_bytes_digest")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("orders_total", "refunds_total", "markdown_index"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--instruction-suffix", default="")
    parser.add_argument("--attempt-index", type=int, default=0)
    args = parser.parse_args()
    result = run_one(args.profile, args.output, args.instruction_suffix, args.attempt_index)
    print(json.dumps(result, ensure_ascii=False))
    if not result["published_correct"] or result["incomplete_reasons"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
