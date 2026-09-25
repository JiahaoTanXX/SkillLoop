"""M4 terminal semantics and evidence limits independent of GPU availability."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from skillloop.runtime.adapter import AgentAdapter
from skillloop.runtime.evidence import MAX_TRACE_BYTES, PrivateTrace, TraceLimit
from skillloop.runtime.gateway import GatewayError
from tests.implementation.test_proxy_store import fixture


class FinalOnlyGateway:
    max_output_tokens = 2048

    def complete(self, _messages, _tools, *, remaining_seconds):
        return ({"id": "response-final", "model": "Qwen/Qwen3.8-27B-FP8",
                 "choices": [{"message": {"role": "assistant", "content": "Finished without an artifact."},
                              "finish_reason": "stop"}],
                 "usage": {"prompt_tokens": 100, "completion_tokens": 8}}, 100, 0.01)

    def count_final(self, text):
        return 8


class TimeoutGateway:
    def complete(self, _messages, _tools, *, remaining_seconds):
        raise GatewayError("provider_timeout")


class UnusedProxy:
    def import_call(self, _call):
        raise AssertionError("unexpected tool call")

    def request(self, _method, _params):
        raise AssertionError("unexpected tool call")


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        _domain, _policy, self.binding, self.request, _approval, _raw = fixture()

    def run_adapter(self, gateway):
        adapter = AgentAdapter(proxy=UnusedProxy(), gateway=gateway,
                               private_root=Path(self.temp.name) / "evidence")
        return adapter.run(profile_id="orders_total", skill_bytes=b"Use the registered tools.",
                           run_request=self.request, task_binding=self.binding,
                           fence=1, trust_revision=1, deployment_epoch="test")

    def test_final_text_without_publication_is_business_failure(self):
        result = self.run_adapter(FinalOnlyGateway())
        self.assertFalse(result["published"])
        self.assertEqual(result["terminal_reason"], "agent_stopped")
        self.assertEqual(result["infra_status"], "ok")
        self.assertTrue(result["evidence_index"]["body"]["complete"])
        self.assertEqual(result["final_text"], "Finished without an artifact.")

    def test_provider_timeout_marks_evidence_incomplete(self):
        result = self.run_adapter(TimeoutGateway())
        self.assertFalse(result["published"])
        self.assertEqual(result["terminal_reason"], "infra_timeout")
        self.assertEqual(result["infra_status"], "timeout")
        self.assertFalse(result["evidence_index"]["body"]["complete"])
        self.assertIn("provider_timeout", result["incomplete_reasons"])

    def test_trace_limit_raises_instead_of_silent_truncation(self):
        trace = PrivateTrace(Path(self.temp.name) / "limit", "large-run")
        with self.assertRaises(TraceLimit):
            trace.append({"content": "A" * MAX_TRACE_BYTES})
        self.assertEqual(trace.size, 0)
        trace.file.close()


if __name__ == "__main__":
    unittest.main()
