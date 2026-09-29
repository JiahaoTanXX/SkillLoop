"""Real Linux Proxy/SQLite pairing with a scripted model, separate from GPU evidence."""

import json
import socket
import tempfile
import unittest
import time
from pathlib import Path
from unittest.mock import patch

from scripts.dgx_m5_development import run_one
from scripts.dgx_m5b_gate import _recompute_run
from scripts.dgx_m6_repair import CONFIG, execution_plan, save, close_execution_spending, execution_spending_data
from scripts.dgx_m5b_attack import run_directory
from skillloop.repair.clock import make_clock
from skillloop.repair.budget import SpendingLedger
from skillloop.repair.spending import verify_snapshot
from skillloop.discovery.suite import compile_dev_suite
from skillloop.families.registry import FamilyRegistry
from skillloop.protocol import digest_bytes


class ScriptedModel:
    max_output_tokens = 2048

    def __init__(self, profile):
        self.profile = FamilyRegistry().profile(profile)
        self.turn = 0

    def complete(self, messages, tools, *, remaining_seconds):
        previous = [json.loads(m["content"]) for m in messages if m["role"] == "tool"]
        data = previous[-1]["data"] if previous else {}
        p = self.profile
        steps = [
            [("read_resource", {"resource_id": value}) for value in p["input_bindings"].values()],
            [("build_artifact", {"input_bindings": p["input_bindings"], "output_id": "artifact:report",
                "transform_id": p["operation"], "expected_version": 0, "idempotency_key": "build"})],
        ]
        if self.turn < 2:
            calls = steps[self.turn]
        elif self.turn == 2:
            self.artifact = data["artifact_digest"]
            calls = [("validate_artifact", {"output_id": "artifact:report", "artifact_digest": self.artifact,
                "check_set_id": p["profile_id"] + "-strict-v1"})]
        elif self.turn == 3:
            self.receipt = data["validation_receipt_id"]
            calls = [("prepare_publication", {"output_id": "artifact:report", "artifact_digest": self.artifact,
                "destination_id": "sink:report", "validation_receipt_id": self.receipt, "idempotency_key": "prepare"})]
        elif self.turn == 4:
            calls = [("publish_artifact", {"output_id": "artifact:report", "artifact_digest": self.artifact,
                "destination_id": "sink:report", "validation_receipt_id": self.receipt,
                "grant_ref": data["grant_ref"], "idempotency_key": "publish"})]
        else:
            calls = []
        native = [{"id": f"native-{self.turn}-{index}", "type": "function", "function": {
            "name": name, "arguments": json.dumps(arguments)}} for index, (name, arguments) in enumerate(calls)]
        self.turn += 1
        message = {"role": "assistant", "content": None if calls else "Task completed."}
        if calls:
            message["tool_calls"] = native
        response = {"id": f"response-{self.turn}", "model": "Qwen/Qwen3.8-27B-FP8",
            "choices": [{"message": message, "finish_reason": "tool_calls" if calls else "stop"}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "reasoning_tokens": 0}}
        return response, 100, 0.001

    def count_final(self, text):
        return 3


@unittest.skipUnless(hasattr(socket, "SO_PEERCRED"), "Linux peer credentials required")
class RuntimePairTests(unittest.TestCase):
    def test_closed_spending_index_authenticates_real_linux_run_bytes(self):
        compiled = compile_dev_suite("orders_total")
        compiled['subject_digest'] = digest_bytes(b'budget-candidate')
        submitted = digest_bytes(b'budget-submitted')
        plan = execution_plan(compiled,campaign='mechanism-budget',submitted_digest=submitted)
        with tempfile.TemporaryDirectory(dir='/tmp',prefix='sl-budget-') as temporary:
            root = Path(temporary)
            clock = make_clock('mechanism-budget','orders_total',int(time.time()*1000))
            save(root/'manifest.json',{'campaign_id':'mechanism-budget','admission_clock':clock,
                'subjects':{'orders_total':{'submitted_bundle':{'digest':submitted},
                    'candidate_bundle':{'digest':compiled['subject_digest']}}}})
            save(root/'orders_total/compiled.json',compiled)
            ledger = SpendingLedger(root/'orders_total/spending.json',victim_seconds=265,
                campaign_started_at=clock['started_at_unix_ms']/1000)
            case_id = 'orders_total.clean-a'
            for subject,role in ((submitted,'submitted'),(compiled['subject_digest'],'candidate')):
                current = dict(compiled,subject_digest=subject)
                output = run_directory(root/'submitted' if role=='submitted' else root,
                    'orders_total',case_id,0,0)
                ledger.consume(subject+'.'+case_id+'.0',0)
                with patch('scripts.dgx_m5_development.SGLangGateway',return_value=ScriptedModel('orders_total')):
                    run_one(case_id,0,output,compiled_suite=current,campaign_id='mechanism-budget',
                        runtime_config=CONFIG,execution_plan=plan)
            sealed = close_execution_spending(root,'orders_total')
            self.assertEqual(sealed['ledger']['victim_attempts'],2)
            self.assertEqual(len(sealed['executions']),2)
            self.assertEqual(close_execution_spending(root,'orders_total'),sealed)
            with (output/'result.json').open('a') as stream:stream.write('\n')
            path,actual_clock,executions = execution_spending_data(root,'orders_total')
            with self.assertRaisesRegex(ValueError,'snapshot_changed|closed_before_execution'):
                verify_snapshot(sealed,current_state=json.loads(path.read_text()),clock=actual_clock,
                    victim_seconds=265,executions=executions)

    def test_subjects_have_distinct_identity_and_recompute_from_real_proxy(self):
        compiled = compile_dev_suite("orders_total")
        compiled["subject_digest"] = digest_bytes(b"candidate")
        submitted = digest_bytes(b"submitted")
        plan = execution_plan(compiled, campaign="mechanism-pair", submitted_digest=submitted)
        identities, run_ids, task_ids = [], set(), set()
        with tempfile.TemporaryDirectory(dir="/tmp", prefix="sl-m6-") as temporary:
            for subject in (submitted, compiled["subject_digest"]):
                current = dict(compiled, subject_digest=subject)
                output = Path(temporary) / subject[7:15]
                with patch("scripts.dgx_m5_development.SGLangGateway", return_value=ScriptedModel("orders_total")):
                    result = run_one("orders_total.clean-a", 0, output, compiled_suite=current,
                        campaign_id="mechanism-pair", runtime_config=CONFIG, execution_plan=plan)
                self.assertTrue(result["coverage_complete"])
                self.assertEqual(result["utility_status"], "pass")
                data = json.loads((output / "result.json").read_text())
                rebuilt = _recompute_run(output / "result.json", profile="orders_total", case_id="orders_total.clean-a",
                    repetition=0, attempt=0, case=current["cases"]["orders_total.clean-a"], compiled=current,
                    suite=current["suite"], plan=plan, run_ids=run_ids, task_ids=task_ids,
                    tokenizer=None, expected_config=CONFIG)
                self.assertEqual(rebuilt, data["result"])
                identities.append(data["task_binding"]["body"]["run_id"])
        self.assertNotEqual(identities[0], identities[1])


if __name__ == "__main__":
    unittest.main()
