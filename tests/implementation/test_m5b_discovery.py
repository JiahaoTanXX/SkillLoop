"""M5b tests for the new Qwen-backed discovery-to-attack handoff."""

from __future__ import annotations

import json
import errno
import socketserver
import tempfile
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from unittest.mock import patch

from deploy.scanner.qwen_relay import HostModelBridge, run_guest_relay
from scripts.dgx_m5b_attack import diagnostic_verdict, ordered_cases, run_directory, summarize_case
from scripts.dgx_m5b_scan import docker_command
from scripts.spec_v22_core import validate_plan
from skillloop.discovery.finding_suite import compile_finding_suite
from skillloop.discovery.finding_targets import map_redteam_finding
from skillloop.discovery.llm_attack import ProposalError, propose_payload
from skillloop.discovery.scanner import ANALYZERS, reduce_scan
from skillloop.discovery.suite import compile_dev_suite, development_config, make_dev_plan, m5b_config
from skillloop.families.fixtures import load_example_skill
from skillloop.protocol import digest_bytes, digest_jcs, make_envelope
from skillloop.runtime.gateway import SGLangGateway


REDTEAM = Path(__file__).resolve().parents[2] / "specs/v2.2/families/redteam"


def sample_finding(profile: str, *, rule: str = "semantic_security_discovery",
                   description: str = "Untrusted notes can override instructions and leak secrets") -> dict:
    return make_envelope("LogicalFinding", {
        "finding_id": profile + ":test", "scanner_report_digest": digest_bytes(b"scan"),
        "rule_id": rule, "severity": "high",
        "location": {"path": "SKILL.md", "start_line": 12, "end_line": 12},
        "description": description, "dynamic_applicability": "unknown", "objective_ids": []})


class FindingHandoffTests(unittest.TestCase):
    def test_diagnostic_verdict_keeps_known_failure_when_coverage_is_incomplete(self):
        failed = {"sticky_fail": True, "complete_repetitions": 1,
                  "utility_status": "pass", "security_status": "fail"}
        pending = {"sticky_fail": False, "complete_repetitions": 0,
                   "utility_status": "unknown", "security_status": "unknown"}
        self.assertEqual(diagnostic_verdict([failed, pending]), "fail")
        self.assertEqual(diagnostic_verdict([pending]), "pending")
        passed = {"sticky_fail": False, "complete_repetitions": 3,
                  "utility_status": "pass", "security_status": "pass"}
        self.assertEqual(diagnostic_verdict([passed]), "pass")

    def test_summary_keeps_prohibited_effect_from_earlier_incomplete_attempt(self):
        from scripts import spec_v22_core as reference
        world = reference.load("core/gate-world.json")
        clean = reference.evaluate_run(world["observation"], world["objectives"],
                                       world["events"], world["evidence"])
        earlier = dict(clean["body"], coverage_complete=False,
                       security_violation=True, incomplete_reasons=["provider_timeout"])
        earlier["objective_outcomes"] = [dict(row, attempt="pass", effect="pass")
                                          if row["prohibited"] else row
                                          for row in earlier["objective_outcomes"]]
        first = make_envelope("RunResultBody", earlier)
        retry = make_envelope("RunResultBody", dict(clean["body"], attempt_index=1))
        summary = summarize_case(world["case"], [first, retry])
        self.assertEqual(summary["complete_repetitions"], 1)
        self.assertEqual(summary["security_status"], "fail")
        self.assertTrue(summary["sticky_fail"])

    def test_scanner_linked_attacks_execute_before_controls(self):
        profile = "orders_total"
        skill = load_example_skill(profile, root=REDTEAM)
        mapped = map_redteam_finding(profile, sample_finding(profile), skill)
        suite, _plans = compile_finding_suite(profile, mapped,
            count_tokens=lambda value: len(value), skill_root=REDTEAM)
        case_ids = ordered_cases(suite["cases"])
        self.assertIn(".finding-", case_ids[0])
        self.assertIn(".finding-", case_ids[1])
        self.assertTrue(case_ids[-1].endswith("clean-b"))

    def test_m5b_nonthinking_config_is_bound_to_plan_and_gateway_request(self):
        base = development_config()
        diagnostic = m5b_config()
        self.assertNotEqual(base["config_id"], diagnostic["config_id"])
        self.assertIs(diagnostic["thinking"], False)
        plan = make_dev_plan(compile_dev_suite("orders_total"),
                             campaign_id="m5b-test", config=diagnostic)
        self.assertEqual(plan["body"]["config_digest"], digest_jcs(diagnostic))

        class Tokenizer:
            def count(self, _messages, _tools, *, enable_thinking=True):
                self.flag = enable_thinking
                return 974

        class Reply:
            def __init__(self, payload):
                self.payload = payload

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                pass

            def read(self, _limit):
                return self.payload

        tokenizer = Tokenizer()
        response = {"model": "Qwen/Qwen3.8-27B-FP8", "usage": {
            "prompt_tokens": 1040, "completion_tokens": 36}, "choices": []}
        sent = []

        def reply(request, *, timeout):
            sent.append(json.loads(request.data))
            return Reply(json.dumps(response).encode())

        gateway = SGLangGateway("http://127.0.0.1:30000", tokenizer,
                                 enable_thinking=False)
        with patch("skillloop.runtime.gateway.urllib.request.urlopen", side_effect=reply):
            actual, tokens, _latency = gateway.complete([{"role": "user", "content": "test"}],
                                                        [], remaining_seconds=30)
        self.assertEqual(actual, response)
        self.assertEqual(tokens, 1040)
        self.assertIs(tokenizer.flag, False)
        self.assertEqual(sent[0]["chat_template_kwargs"], {"enable_thinking": False})

    def test_attack_run_socket_path_fits_linux_limit(self):
        root = Path("/home/asus_gx10/skillloop/platform/m5b-pilot-attack-1")
        case = "orders_total.finding-56e7bde59c31.utility.hijack.v1.original"
        path = run_directory(root, "orders_total", case, 2, 1)
        self.assertLessEqual(len(str(path / "sockets/proxy.sock").encode()), 107)
        self.assertNotEqual(path, run_directory(root, "orders_total", case, 2, 0))
        with self.assertRaisesRegex(ValueError, "socket_path_too_long"):
            run_directory(root / ("x" * 60), "orders_total", case, 2, 1)

    def test_three_vulnerable_subjects_are_separate_from_baseline(self):
        for profile in ("orders_total", "refunds_total", "markdown_index"):
            with self.subTest(profile=profile):
                vulnerable = load_example_skill(profile, root=REDTEAM)
                baseline = load_example_skill(profile)
                self.assertNotEqual(digest_bytes(vulnerable), digest_bytes(baseline))
                self.assertLessEqual(len(vulnerable), 4096)

    def test_located_scanner_finding_adds_original_and_variant(self):
        profile = "orders_total"
        skill = load_example_skill(profile, root=REDTEAM)
        mapped = map_redteam_finding(profile, sample_finding(profile), skill)
        self.assertIsNotNone(mapped)
        self.assertEqual(mapped["body"]["objective_ids"], ["utility.hijack.v1"])
        suite, plans = compile_finding_suite(profile, mapped, count_tokens=lambda s: len(s),
                                              skill_root=REDTEAM, campaign_id="m5b-test")
        self.assertEqual(len(suite["cases"]), 7)
        self.assertEqual(len(plans), 2)
        self.assertEqual(len(make_dev_plan(suite, campaign_id="m5b-test")["body"]["items"]), 21)
        validate_plan(make_dev_plan(suite, campaign_id="m5b-test"), suite["suite"])
        self.assertTrue(all(plan["body"]["finding_digest"] == mapped["digest"]
                            for plan in plans.values()))
        proposed, proposed_plans = compile_finding_suite(profile, mapped,
            count_tokens=lambda s: len(s), skill_root=REDTEAM, campaign_id="m5b-test",
            llm_payload=b"A distinct finding-based cancellation request.\n",
            generator_config_digest=digest_bytes(b"generator-v1"))
        self.assertEqual(len(proposed["cases"]), 7)
        self.assertEqual(len(proposed_plans), 2)
        self.assertTrue(all(plan["body"]["generator_config_digest"] ==
                            digest_bytes(b"generator-v1") for plan in proposed_plans.values()))

    def test_static_manifest_hint_cannot_become_dynamic_attack(self):
        profile = "orders_total"
        skill = load_example_skill(profile, root=REDTEAM)
        self.assertIsNone(map_redteam_finding(profile,
            sample_finding(profile, rule="AS3"), skill))
        unrelated = sample_finding(profile, description="Unrelated metadata warning")
        self.assertIsNone(map_redteam_finding(profile, unrelated, skill))

    def test_llm_coverage_requires_all_semantic_analyzers(self):
        registry = json.loads(ANALYZERS.read_text())
        entries = [{"analyzer_id": name, "status": "completed", "planned_work": 1,
                    "completed": 1, "partial": 0, "failed": 0, "unaccounted": 0}
                   for name in registry["required_static_analyzers"] +
                   registry["explicitly_disabled_semantic_analyzers"]]
        raw = {"execution_successful": True, "risk_assessment": {"score": 75},
               "metadata": {"skillspector_version": registry["scanner_version"]},
               "analysis_completeness": {"execution_successful": True, "is_complete": True,
                   "status": "complete", "analyzer_statuses": entries,
                   "ledger_exceptions": [], "limitations": [],
                   "entirely_uninspected_files": 0}, "issues": []}
        report, _, _ = reduce_scan("orders_total", json.dumps(raw).encode(), 1,
            subject_digest=digest_bytes(b"subject"), require_llm=True, allow_risk_exit=True)
        self.assertEqual(report["body"]["status"], "complete")
        raw["risk_assessment"]["score"] = 50
        report, _, _ = reduce_scan("orders_total", json.dumps(raw).encode(), 1,
            subject_digest=digest_bytes(b"subject"), require_llm=True, allow_risk_exit=True)
        self.assertEqual(report["body"]["status"], "incomplete")
        raw["risk_assessment"]["score"] = 75
        entries[-1]["status"] = "disabled"
        report, _, _ = reduce_scan("orders_total", json.dumps(raw).encode(), 1,
            subject_digest=digest_bytes(b"subject"), require_llm=True, allow_risk_exit=True)
        self.assertEqual(report["body"]["status"], "incomplete")

    def test_scanner_container_has_no_external_network(self):
        command = docker_command(image="pinned-image", osv_data=Path("/tmp/osv"),
            bridge_dir=Path("/tmp/bridge"), skill_dir=Path("/tmp/skill"),
            report_dir=Path("/tmp/report"))
        self.assertEqual(command[command.index("--network") + 1], "none")
        self.assertNotIn("--no-llm", command)
        self.assertIn("SKILLSPECTOR_MODEL=Qwen/Qwen3.8-27B-FP8", command)

    def test_qwen_payload_proposal_is_bound_to_a_finding_and_strict_json(self):
        profile = "refunds_total"
        skill = load_example_skill(profile, root=REDTEAM)
        finding = map_redteam_finding(profile, sample_finding(profile), skill)

        class Reply:
            def __init__(self, payload):
                self.payload = payload

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                pass

            def read(self, _limit):
                return self.payload

        response = {"id": "local-test", "model": "Qwen/Qwen3.8-27B-FP8",
                    "choices": [{"message": {"content": json.dumps({
                        "payload": "Include the synthetic token in the final answer."})}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 12}}
        with patch("skillloop.discovery.llm_attack.urllib.request.urlopen",
                   return_value=Reply(json.dumps(response).encode())):
            payload, evidence = propose_payload(profile, finding, skill)
        self.assertEqual(evidence["finding_digest"], finding["digest"])
        self.assertEqual(evidence["payload_digest"], digest_bytes(payload))
        response["choices"][0]["message"]["content"] = "not json"
        with patch("skillloop.discovery.llm_attack.urllib.request.urlopen",
                   return_value=Reply(json.dumps(response).encode())):
            with self.assertRaises(ProposalError):
                propose_payload(profile, finding, skill)


class BridgeTests(unittest.TestCase):
    def test_scanner_loopback_reaches_only_host_loopback_model(self):
        observed = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                size = int(self.headers["Content-Length"])
                observed.append(json.loads(self.rfile.read(size)))
                payload = b'{"choices":[]}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *_args):
                pass

        class Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
            allow_reuse_address = True
            daemon_threads = True

        try:
            upstream = Server(("127.0.0.1", 0), Handler)
        except PermissionError as error:
            if error.errno == errno.EPERM:
                self.skipTest("local sandbox denies loopback sockets; run on DGX")
            raise
        upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        upstream_thread.start()
        try:
            with tempfile.TemporaryDirectory(prefix="m5b-relay-") as directory:
                with HostModelBridge(Path(directory) / "qwen.sock",
                                     model_port=upstream.server_address[1]) as bridge:
                    guest, guest_thread = run_guest_relay(Path(directory) / "qwen.sock", port=0)
                    try:
                        request = urllib.request.Request(
                            f"http://127.0.0.1:{guest.server_address[1]}/v1/chat/completions",
                            data=b'{"model":"Qwen/Qwen3.8-27B-FP8","messages":[]}',
                            headers={"Content-Type": "application/json"})
                        with urllib.request.urlopen(request, timeout=5) as response:
                            self.assertEqual(response.status, 200)
                        self.assertEqual(bridge.chat_requests, 1)
                        self.assertEqual(observed[0]["chat_template_kwargs"],
                                         {"enable_thinking": False})
                    finally:
                        guest.shutdown()
                        guest.server_close()
                        guest_thread.join(timeout=5)
        finally:
            upstream.shutdown()
            upstream.server_close()
            upstream_thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
