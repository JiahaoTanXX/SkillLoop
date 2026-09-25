"""Real SQLite M3 transaction tests using fixed M2 business fixtures."""

from __future__ import annotations

import tempfile
import unittest
import sqlite3
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from skillloop.families.fixtures import load_clean_fixture
from skillloop.families.registry import FamilyRegistry
from skillloop.protocol import ProtocolError, digest_bytes, digest_jcs, make_envelope
from skillloop.proxy.store import ProxyError, ProxyStore
from skillloop.proxy.server import ProxyServer
from skillloop.proxy.policy import AuthorizationError, compile_capability
from skillloop.proxy.wire import make_control, validate_control


def stamp(offset_seconds: int = 0) -> str:
    return (datetime.now(timezone.utc).replace(microsecond=0) + timedelta(seconds=offset_seconds)).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def fixture(profile_id: str = "orders_total") -> tuple[dict, dict, dict, dict, dict, dict[str, bytes]]:
    registry = FamilyRegistry()
    profile = registry.profile(profile_id)
    inputs, _expected = load_clean_fixture(profile_id, "a")
    contract = digest_jcs(profile)
    slots = [{"slot": name, "resource_class": "input", "allowed_access": ["read"],
              "tenant_id": "tenant-a"} for name in profile["input_bindings"]]
    slots += [{"slot": "output", "resource_class": "artifact", "allowed_access": ["read", "write"],
               "tenant_id": "tenant-a"},
              {"slot": "destination", "resource_class": "sink", "allowed_access": ["publish"],
               "tenant_id": "tenant-a"}]
    def action(tool: str, bindings: list[tuple[str, str, str]], *, check: str | None = None,
               transform: str | None = None, dest: str | None = None) -> dict:
        return {"tool": tool, "bindings": [{"parameter": p, "slot": s, "access": a} for p, s, a in bindings],
                "destination_slot": dest, "check_set_id": check, "transform_id": transform}
    check = f"{profile_id}-strict-v1"
    actions = [action("read_resource", [("resource_id", name, "read")]) for name in profile["input_bindings"]]
    actions += [action("build_artifact", [(f"input_bindings.{name}", name, "read")
                                             for name in profile["input_bindings"]] +
                       [("output_id", "output", "write")], transform=profile["operation"]),
                action("write_artifact", [("output_id", "output", "write")]),
                action("validate_artifact", [("output_id", "output", "read")], check=check),
                action("prepare_publication", [("output_id", "output", "read"),
                                                ("destination_id", "destination", "publish")],
                       check=check, dest="destination"),
                action("publish_artifact", [("output_id", "output", "read"),
                                            ("destination_id", "destination", "publish")],
                       check=check, dest="destination")]
    domain = make_envelope("AuthorizationDomain", {"domain_id": "approved-test-domain",
        "contract_digest": contract, "tenant_id": "tenant-a", "slots": slots,
        "approved_actions": actions, "max_tool_calls": 12, "prerequisites_profile": "strict-v2"})
    policy = make_envelope("Policy", {"contract_digest": contract, "domain_digest": domain["digest"],
        "allowed_actions": actions, "max_tool_calls": 12, "prerequisites_profile": "strict-v2"})
    resources = [{"resource_id": resource_id, "resource_class": "input", "access": "read",
                  "bytes_digest": digest_bytes(inputs[name]), "tenant_id": "tenant-a"}
                 for name, resource_id in profile["input_bindings"].items()]
    resources += [{"resource_id": "artifact:report", "resource_class": "artifact", "access": "read_write",
                   "bytes_digest": None, "tenant_id": "tenant-a"},
                  {"resource_id": "sink:report", "resource_class": "sink", "access": "publish",
                   "bytes_digest": None, "tenant_id": "tenant-a"}]
    slot_bindings = [{"slot": name, "resource_id": resource_id} for name, resource_id in profile["input_bindings"].items()]
    slot_bindings += [{"slot": "output", "resource_id": "artifact:report"},
                      {"slot": "destination", "resource_id": "sink:report"}]
    subject = digest_jcs({"profile_id": profile_id, "skill": "clean-a"})
    binding = make_envelope("TaskBinding", {"task_instance_id": "task-1", "run_id": "run-1",
        "subject_digest": subject, "domain_digest": domain["digest"], "tenant_id": "tenant-a",
        "resources": resources, "slot_bindings": slot_bindings})
    synthetic = digest_jcs("m3-local-fixture")
    run_request = make_envelope("RunRequest", {"subject_digest": subject,
        "case_digest": synthetic, "suite_digest": synthetic, "plan_digest": synthetic,
        "config_digest": synthetic, "authorization_domain_digest": domain["digest"],
        "initial_world_digest": synthetic, "repetition_index": 0})
    approval = make_envelope("ApprovalRecord", {"approval_id": "approval-1",
        "authorization_domain_digest": domain["digest"], "contract_digest": contract,
        "factory_rule_digest": synthetic, "config_digest": synthetic, "issuer": "administrator",
        "issued_at": stamp(-1), "expires_at": None, "trust_revision": 1, "state": "active"})
    raw = {resource_id: inputs[name] for name, resource_id in profile["input_bindings"].items()}
    return domain, policy, binding, run_request, approval, raw


class ProxyStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = ProxyStore(Path(self.temp.name) / "proxy.db", deployment_epoch="m3-test")
        self.domain, self.policy, self.binding, self.request, self.approval, self.raw = fixture()
        self.store.stage_approval(self.domain, self.approval)
        self.store.activate_approval(self.approval["digest"], 0, operation_id="activate-1",
                                     request_digest=digest_jcs("activate-1"))
        self.store.stage_task(domain=self.domain, policy=self.policy, binding=self.binding,
                              run_request=self.request, profile_id="orders_total", resources=self.raw,
                              approval_digest=self.approval["digest"], run_deadline=stamp(240),
                              campaign_id="campaign-1")
        self.store.start_run(self.request["digest"], self.binding["digest"],
                             operation_id="start-1", request_digest=digest_jcs("start-1"))
        self.counter = 0

    def call(self, tool: str, args: dict) -> dict:
        self.counter += 1
        call = make_envelope("ToolCall", {"call_id": f"call-{self.counter}", "run_id": "run-1",
            "task_instance_id": "task-1", "fencing_token": 1, "tool": tool, "args": args})
        self.store.stage_object(call, trusted_role="runtime")
        self.store.register_call_batch("run-1", 1, f"response-{self.counter}",
            [{"call_digest": call["digest"], "native_tool_call_id": f"native-{self.counter}",
              "batch_index": 0}])
        return self.store.execute_call(call["digest"], tool)

    def prepare(self) -> tuple[dict, dict, dict]:
        profile = FamilyRegistry().profile("orders_total")
        for name, resource_id in profile["input_bindings"].items():
            result = self.call("read_resource", {"resource_id": resource_id})
            self.assertEqual(result["body"]["outcome"], "ok", name)
            self.assertEqual(result["body"]["data"]["source_bytes_digest"], digest_bytes(self.raw[resource_id]))
        built = self.call("build_artifact", {"input_bindings": profile["input_bindings"],
            "output_id": "artifact:report", "transform_id": profile["operation"],
            "expected_version": 0, "idempotency_key": "build-1"})
        self.assertEqual(built["body"]["outcome"], "ok")
        validated = self.call("validate_artifact", {"output_id": "artifact:report",
            "artifact_digest": built["body"]["data"]["artifact_digest"],
            "check_set_id": "orders_total-strict-v1"})
        self.assertEqual(validated["body"]["outcome"], "ok")
        prepared = self.call("prepare_publication", {"output_id": "artifact:report",
            "artifact_digest": built["body"]["data"]["artifact_digest"],
            "destination_id": "sink:report", "validation_receipt_id": validated["body"]["data"]["validation_receipt_id"],
            "idempotency_key": "prepare-1"})
        self.assertEqual(prepared["body"]["outcome"], "ok")
        return built, validated, prepared

    def publish(self, built: dict, validated: dict, prepared: dict, key: str = "publish-1") -> dict:
        published = self.call("publish_artifact", {"output_id": "artifact:report",
            "artifact_digest": built["body"]["data"]["artifact_digest"],
            "destination_id": "sink:report",
            "validation_receipt_id": validated["body"]["data"]["validation_receipt_id"],
            "grant_ref": prepared["body"]["data"]["grant_ref"],
            "idempotency_key": key})
        return published

    def test_full_chain_publishes_exact_bytes_once(self) -> None:
        built, validated, prepared = self.prepare()
        published = self.publish(built, validated, prepared)
        self.assertEqual(published["body"]["outcome"], "ok")
        publication = self.store.inspect_publication("task-1")
        self.assertEqual(publication["artifact_digest"], built["body"]["data"]["artifact_digest"])
        self.assertEqual(digest_bytes(publication["content"]), publication["artifact_digest"])
        self.assertEqual(self.store.recover_tool("run-1", "publish_artifact", "publish-1")["state"], "committed")

    def test_revoke_before_publish_blocks_effect_and_recovery_shows_absence(self) -> None:
        built, validated, prepared = self.prepare()
        call = make_envelope("ToolCall", {"call_id": "call-publish-after-revoke", "run_id": "run-1",
            "task_instance_id": "task-1", "fencing_token": 1, "tool": "publish_artifact",
            "args": {"output_id": "artifact:report",
                     "artifact_digest": built["body"]["data"]["artifact_digest"],
                     "destination_id": "sink:report",
                     "validation_receipt_id": validated["body"]["data"]["validation_receipt_id"],
                     "grant_ref": prepared["body"]["data"]["grant_ref"],
                     "idempotency_key": "publish-after-revoke"}})
        self.store.stage_object(call, trusted_role="runtime")
        self.store.register_call_batch("run-1", 1, "response-publish-after-revoke",
            [{"call_digest": call["digest"], "native_tool_call_id": "native-publish-after-revoke",
              "batch_index": 0}])
        self.store.revoke_approval(self.approval["digest"], 1,
                                   operation_id="revoke-1", request_digest=digest_jcs("revoke-1"))
        result = self.store.execute_call(call["digest"], "publish_artifact")
        self.assertEqual(result["body"]["error_code"], "approval_required")
        self.assertIsNone(self.store.inspect_publication("task-1"))

    def test_publish_before_revoke_preserves_committed_publication(self) -> None:
        built, validated, prepared = self.prepare()
        result = self.publish(built, validated, prepared)
        self.assertEqual(result["body"]["outcome"], "ok")
        self.store.revoke_approval(self.approval["digest"], 1,
                                   operation_id="revoke-1", request_digest=digest_jcs("revoke-1"))
        self.assertIsNotNone(self.store.inspect_publication("task-1"))

    def test_same_bytes_write_advances_version_and_invalidates_receipt(self) -> None:
        profile = FamilyRegistry().profile("orders_total")
        for resource_id in profile["input_bindings"].values():
            self.call("read_resource", {"resource_id": resource_id})
        built = self.call("build_artifact", {"input_bindings": profile["input_bindings"],
            "output_id": "artifact:report", "transform_id": profile["operation"],
            "expected_version": 0, "idempotency_key": "build-1"})
        digest = built["body"]["data"]["artifact_digest"]
        old_receipt = self.call("validate_artifact", {"output_id": "artifact:report",
            "artifact_digest": digest, "check_set_id": "orders_total-strict-v1"})
        _inputs, expected = load_clean_fixture("orders_total", "a")
        written = self.call("write_artifact", {"output_id": "artifact:report", "expected_version": 1,
            "content_utf8": expected.decode("utf-8"), "idempotency_key": "write-same"})
        self.assertEqual(written["body"]["data"]["artifact_version"], 2)
        self.assertEqual(written["body"]["data"]["artifact_digest"], digest)
        invalid = self.call("prepare_publication", {"output_id": "artifact:report",
            "artifact_digest": digest, "destination_id": "sink:report",
            "validation_receipt_id": old_receipt["body"]["data"]["validation_receipt_id"],
            "idempotency_key": "prepare-old"})
        self.assertEqual(invalid["body"]["error_code"], "validation_failed")
        self.assertIsNone(self.store.inspect_publication("task-1"))

    def test_cancel_fences_even_a_completed_call_replay(self) -> None:
        profile = FamilyRegistry().profile("orders_total")
        resource_id = next(iter(profile["input_bindings"].values()))
        self.counter += 1
        call = make_envelope("ToolCall", {"call_id": "call-cancel", "run_id": "run-1",
            "task_instance_id": "task-1", "fencing_token": 1, "tool": "read_resource",
            "args": {"resource_id": resource_id}})
        self.store.stage_object(call, trusted_role="runtime")
        self.store.register_call_batch("run-1", 1, "response-cancel",
            [{"call_digest": call["digest"], "native_tool_call_id": "native-cancel", "batch_index": 0}])
        self.assertEqual(self.store.execute_call(call["digest"], "read_resource")["body"]["outcome"], "ok")
        self.store.cancel_run("run-1", 1, operation_id="cancel-1", request_digest=digest_jcs("cancel-1"))
        with self.assertRaisesRegex(ProxyError, "stale_fence"):
            self.store.execute_call(call["digest"], "read_resource")

    def test_unknown_arguments_and_cross_task_resource_rejected(self) -> None:
        with self.assertRaises(ProtocolError):
            make_envelope("ToolCall", {"call_id": "bad", "run_id": "run-1", "task_instance_id": "task-1",
                "fencing_token": 1, "tool": "read_resource",
                "args": {"resource_id": "input:customers", "unexpected": True}})
        result = self.call("read_resource", {"resource_id": "input:other-task"})
        self.assertEqual(result["body"]["error_code"], "denied")

    def test_control_wire_and_role_dispatch(self) -> None:
        server = object.__new__(ProxyServer)
        server.store = self.store
        request = make_control("ControlRequest", {"operation_id": "recover-1", "deadline": stamp(5),
            "method": "recover_operation", "params": {"run_id": "run-1", "tool": "build_artifact",
                                               "idempotency_key": "missing"}})
        result = server.dispatch(request, "controller")
        self.assertEqual(validate_control(result)["body"]["state"], "proven_not_started")
        status = server.dispatch(make_control("ControlRequest", {"operation_id": "get-start",
            "deadline": stamp(5), "method": "get_operation",
            "params": {"operation_ref": "start-1"}}), "controller")
        self.assertEqual(validate_control(status)["body"]["state"], "completed")
        self.assertEqual(status["body"]["result_kind"], "Lease")
        with self.assertRaisesRegex(ProxyError, "denied"):
            server.dispatch(request, "runtime")

    def test_batch_quota_is_all_or_none_and_skips_after_failure(self) -> None:
        def stage(index: int, resource_id: str) -> dict:
            call = make_envelope("ToolCall", {"call_id": f"batch-{index}", "run_id": "run-1",
                "task_instance_id": "task-1", "fencing_token": 1, "tool": "read_resource",
                "args": {"resource_id": resource_id}})
            self.store.stage_object(call, trusted_role="runtime")
            return {"call_digest": call["digest"], "native_tool_call_id": f"native-batch-{index}",
                    "batch_index": index}
        valid_id = next(iter(FamilyRegistry().profile("orders_total")["input_bindings"].values()))
        first = stage(0, "input:other-task")
        second = stage(1, valid_id)
        registered = self.store.register_call_batch("run-1", 1, "response-batch", [first, second])
        self.assertEqual(registered["consumed_calls"], 2)
        self.assertEqual(self.store.execute_call(first["call_digest"], "read_resource")["body"]["error_code"], "denied")
        self.assertEqual(self.store.execute_call(second["call_digest"], "read_resource")["body"]["error_code"],
                         "skipped_after_failure")
        many = [{**stage(i + 2, valid_id), "batch_index": i} for i in range(11)]
        with self.assertRaisesRegex(ProxyError, "budget_exhausted"):
            self.store.register_call_batch("run-1", 1, "response-over-budget", many)
        with sqlite3.connect(self.store.path) as db:
            self.assertEqual(db.execute("SELECT consumed_calls FROM runs WHERE run_id='run-1'").fetchone()[0], 2)
            self.assertEqual(db.execute("SELECT count(*) FROM call_registration").fetchone()[0], 2)

    def test_new_logical_call_same_key_consumes_quota_and_reuses_effect(self) -> None:
        profile = FamilyRegistry().profile("orders_total")
        for resource_id in profile["input_bindings"].values():
            self.call("read_resource", {"resource_id": resource_id})
        args = {"input_bindings": profile["input_bindings"], "output_id": "artifact:report",
                "transform_id": profile["operation"], "expected_version": 0, "idempotency_key": "build-shared"}
        first = self.call("build_artifact", args)
        second = self.call("build_artifact", args)
        self.assertEqual(first["body"]["outcome"], "ok")
        self.assertEqual(second["body"]["outcome"], "ok")
        self.assertNotEqual(first["body"]["call_id"], second["body"]["call_id"])
        self.assertEqual(first["body"]["data"], second["body"]["data"])
        with sqlite3.connect(self.store.path) as db:
            self.assertEqual(db.execute("SELECT version FROM resources WHERE resource_id='artifact:report'").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT consumed_calls FROM runs WHERE run_id='run-1'").fetchone()[0], 5)

    def test_duplicate_internal_call_id_with_different_args_rejected(self) -> None:
        ids = list(FamilyRegistry().profile("orders_total")["input_bindings"].values())
        def stage(resource_id: str) -> dict:
            call = make_envelope("ToolCall", {"call_id": "same-internal-id", "run_id": "run-1",
                "task_instance_id": "task-1", "fencing_token": 1, "tool": "read_resource",
                "args": {"resource_id": resource_id}})
            self.store.stage_object(call, trusted_role="runtime")
            return call
        first = stage(ids[0])
        self.store.register_call_batch("run-1", 1, "response-1",
            [{"call_digest": first["digest"], "native_tool_call_id": "native-1", "batch_index": 0}])
        second = stage(ids[1])
        with self.assertRaisesRegex(ProxyError, "version_conflict"):
            self.store.register_call_batch("run-1", 1, "response-2",
                [{"call_digest": second["digest"], "native_tool_call_id": "native-2", "batch_index": 0}])
        with sqlite3.connect(self.store.path) as db:
            self.assertEqual(db.execute("SELECT consumed_calls FROM runs WHERE run_id='run-1'").fetchone()[0], 1)

    def test_unregistered_call_cannot_execute(self) -> None:
        resource_id = next(iter(FamilyRegistry().profile("orders_total")["input_bindings"].values()))
        call = make_envelope("ToolCall", {"call_id": "unregistered", "run_id": "run-1",
            "task_instance_id": "task-1", "fencing_token": 1, "tool": "read_resource",
            "args": {"resource_id": resource_id}})
        self.store.stage_object(call, trusted_role="runtime")
        with self.assertRaisesRegex(ProxyError, "not_found"):
            self.store.execute_call(call["digest"], "read_resource")

    def test_exact_registration_replay_and_modified_metadata_rejected(self) -> None:
        resource_id = next(iter(FamilyRegistry().profile("orders_total")["input_bindings"].values()))
        call = make_envelope("ToolCall", {"call_id": "replay-id", "run_id": "run-1",
            "task_instance_id": "task-1", "fencing_token": 1, "tool": "read_resource",
            "args": {"resource_id": resource_id}})
        self.store.stage_object(call, trusted_role="runtime")
        item = {"call_digest": call["digest"], "native_tool_call_id": "native-replay", "batch_index": 0}
        first = self.store.register_call_batch("run-1", 1, "response-replay", [item])
        self.assertEqual(self.store.register_call_batch("run-1", 1, "response-replay", [item]), first)
        self.assertEqual(self.store.register_call_batch("run-1", 1, "retry-response", [item]), first)
        with self.assertRaisesRegex(ProxyError, "version_conflict"):
            self.store.register_call_batch("run-1", 1, "response-replay",
                [{**item, "native_tool_call_id": "forged-native"}])
        with sqlite3.connect(self.store.path) as db:
            self.assertEqual(db.execute("SELECT consumed_calls FROM runs WHERE run_id='run-1'").fetchone()[0], 1)

    def test_capability_rejects_tenant_expansion_and_empty_read(self) -> None:
        changed = deepcopy(self.binding)
        changed["body"]["resources"][0]["tenant_id"] = "tenant-b"
        changed = make_envelope("TaskBinding", changed["body"])
        with self.assertRaises(AuthorizationError):
            compile_capability(self.domain, changed, self.policy, "orders_total")
        limited_domain = deepcopy(self.domain)
        limited_domain["body"]["max_tool_calls"] = 11
        limited_domain = make_envelope("AuthorizationDomain", limited_domain["body"])
        limited_binding = deepcopy(self.binding)
        limited_binding["body"]["domain_digest"] = limited_domain["digest"]
        limited_binding = make_envelope("TaskBinding", limited_binding["body"])
        expanded = make_envelope("Policy", {**self.policy["body"],
                                             "domain_digest": limited_domain["digest"]})
        with self.assertRaisesRegex(AuthorizationError, "policy_expansion"):
            compile_capability(limited_domain, limited_binding, expanded, "orders_total")
        no_read = deepcopy(self.domain)
        no_read["body"]["slots"] = [slot for slot in no_read["body"]["slots"]
                                      if slot["resource_class"] not in ("input", "skill")]
        no_read["body"]["approved_actions"] = [action for action in no_read["body"]["approved_actions"]
                                                  if action["tool"] == "write_artifact"]
        no_read = make_envelope("AuthorizationDomain", no_read["body"])
        no_read_binding = deepcopy(self.binding)
        no_read_binding["body"]["domain_digest"] = no_read["digest"]
        no_read_binding["body"]["slot_bindings"] = [item for item in no_read_binding["body"]["slot_bindings"]
                                                      if item["slot"] in {"output", "destination"}]
        no_read_binding = make_envelope("TaskBinding", no_read_binding["body"])
        no_read_policy = make_envelope("Policy", {**self.policy["body"], "domain_digest": no_read["digest"],
                                                  "allowed_actions": no_read["body"]["approved_actions"]})
        with self.assertRaisesRegex(AuthorizationError, "empty_read_binding"):
            compile_capability(no_read, no_read_binding, no_read_policy, "orders_total")

    def test_crash_before_or_after_commit_recovers_authoritative_result(self) -> None:
        profile = FamilyRegistry().profile("orders_total")
        for resource_id in profile["input_bindings"].values():
            self.call("read_resource", {"resource_id": resource_id})
        args = {"input_bindings": profile["input_bindings"], "output_id": "artifact:report",
                "transform_id": profile["operation"], "expected_version": 0,
                "idempotency_key": "crash-build"}
        call = make_envelope("ToolCall", {"call_id": "crash-build-call", "run_id": "run-1",
            "task_instance_id": "task-1", "fencing_token": 1, "tool": "build_artifact", "args": args})
        self.store.stage_object(call, trusted_role="runtime")
        self.store.register_call_batch("run-1", 1, "crash-response", [{"call_digest": call["digest"],
            "native_tool_call_id": "native-crash", "batch_index": 0}])
        script = ("import os,sys; from pathlib import Path; from skillloop.proxy.store import ProxyStore; "
                  "s=ProxyStore(Path(sys.argv[1]),deployment_epoch='m3-test'); "
                  "s.fault_hook=lambda point: os._exit(71) if point==sys.argv[3] else None; "
                  "s.execute_call(sys.argv[2],'build_artifact')")
        first = subprocess.run([sys.executable, "-c", script, str(self.store.path), call["digest"],
                                "before_commit"], check=False, capture_output=True)
        self.assertEqual(first.returncode, 71, first.stderr.decode())
        self.assertEqual(self.store.recover_tool("run-1", "build_artifact", "crash-build")["state"],
                         "proven_not_started")
        with sqlite3.connect(self.store.path) as db:
            self.assertEqual(db.execute("SELECT version FROM resources WHERE resource_id='artifact:report'").fetchone()[0], 0)
        second = subprocess.run([sys.executable, "-c", script, str(self.store.path), call["digest"],
                                 "after_commit"], check=False, capture_output=True)
        self.assertEqual(second.returncode, 71, second.stderr.decode())
        recovered = self.store.recover_tool("run-1", "build_artifact", "crash-build")
        self.assertEqual(recovered["state"], "committed")
        replay = self.store.execute_call(call["digest"], "build_artifact")
        self.assertEqual(replay["digest"], recovered["tool_result_digest"])
        with sqlite3.connect(self.store.path) as db:
            self.assertEqual(db.execute("SELECT version FROM resources WHERE resource_id='artifact:report'").fetchone()[0], 1)

    def test_real_sqlite_publish_revoke_race(self) -> None:
        built, validated, prepared = self.prepare()
        args = {"output_id": "artifact:report", "artifact_digest": built["body"]["data"]["artifact_digest"],
                "destination_id": "sink:report", "validation_receipt_id": validated["body"]["data"]["validation_receipt_id"],
                "grant_ref": prepared["body"]["data"]["grant_ref"], "idempotency_key": "race-publish"}
        call = make_envelope("ToolCall", {"call_id": "race-call", "run_id": "run-1",
            "task_instance_id": "task-1", "fencing_token": 1, "tool": "publish_artifact", "args": args})
        self.store.stage_object(call, trusted_role="runtime")
        self.store.register_call_batch("run-1", 1, "race-response", [{"call_digest": call["digest"],
            "native_tool_call_id": "native-race", "batch_index": 0}])
        barrier = threading.Barrier(2)
        def publish() -> dict:
            barrier.wait()
            return ProxyStore(self.store.path, deployment_epoch="m3-test").execute_call(call["digest"], "publish_artifact")
        def revoke() -> dict:
            barrier.wait()
            return ProxyStore(self.store.path, deployment_epoch="m3-test").revoke_approval(
                self.approval["digest"], 1, operation_id="race-revoke",
                request_digest=digest_jcs("race-revoke"))
        with ThreadPoolExecutor(max_workers=2) as pool:
            pub_future, revoke_future = pool.submit(publish), pool.submit(revoke)
            published, revoked = pub_future.result(), revoke_future.result()
        self.assertEqual(revoked["state"], "revoked")
        publication = self.store.inspect_publication("task-1")
        self.assertEqual(publication is not None, published["body"]["outcome"] == "ok")
        if publication is None:
            self.assertEqual(published["body"]["error_code"], "approval_required")
        with sqlite3.connect(self.store.path) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM publications").fetchone()[0], int(publication is not None))
            self.assertEqual(db.execute("SELECT count(*) FROM outbox").fetchone()[0], int(publication is not None))
            self.assertEqual(db.execute("SELECT trust_revision FROM trust_state").fetchone()[0], 2)

    def test_publish_crash_keeps_publication_outbox_and_grant_atomic(self) -> None:
        built, validated, prepared = self.prepare()
        args = {"output_id": "artifact:report", "artifact_digest": built["body"]["data"]["artifact_digest"],
                "destination_id": "sink:report", "validation_receipt_id": validated["body"]["data"]["validation_receipt_id"],
                "grant_ref": prepared["body"]["data"]["grant_ref"], "idempotency_key": "crash-publish"}
        call = make_envelope("ToolCall", {"call_id": "crash-publish-call", "run_id": "run-1",
            "task_instance_id": "task-1", "fencing_token": 1, "tool": "publish_artifact", "args": args})
        self.store.stage_object(call, trusted_role="runtime")
        self.store.register_call_batch("run-1", 1, "crash-publish-response", [{"call_digest": call["digest"],
            "native_tool_call_id": "native-crash-publish", "batch_index": 0}])
        script = ("import os,sys; from pathlib import Path; from skillloop.proxy.store import ProxyStore; "
                  "s=ProxyStore(Path(sys.argv[1]),deployment_epoch='m3-test'); "
                  "s.fault_hook=lambda point: os._exit(73) if point==sys.argv[3] else None; "
                  "s.execute_call(sys.argv[2],'publish_artifact')")
        before = subprocess.run([sys.executable, "-c", script, str(self.store.path), call["digest"],
                                 "before_commit"], check=False, capture_output=True)
        self.assertEqual(before.returncode, 73, before.stderr.decode())
        self.assertEqual(self.store.recover_tool("run-1", "publish_artifact", "crash-publish")["state"],
                         "proven_not_started")
        with sqlite3.connect(self.store.path) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM publications").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT count(*) FROM outbox").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT consumed FROM grants WHERE grant_ref=?",
                                        (args["grant_ref"],)).fetchone()[0], 0)
        after = subprocess.run([sys.executable, "-c", script, str(self.store.path), call["digest"],
                                "after_commit"], check=False, capture_output=True)
        self.assertEqual(after.returncode, 73, after.stderr.decode())
        recovered = self.store.recover_tool("run-1", "publish_artifact", "crash-publish")
        self.assertEqual(recovered["state"], "committed")
        self.assertEqual(self.store.execute_call(call["digest"], "publish_artifact")["digest"],
                         recovered["tool_result_digest"])
        with sqlite3.connect(self.store.path) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM publications").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT count(*) FROM outbox").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT consumed FROM grants WHERE grant_ref=?",
                                        (args["grant_ref"],)).fetchone()[0], 1)

    def test_second_publication_for_same_task_is_rejected(self) -> None:
        built, validated, prepared = self.prepare()
        second_call = make_envelope("ToolCall", {"call_id": "publish-second-call", "run_id": "run-1",
            "task_instance_id": "task-1", "fencing_token": 1, "tool": "publish_artifact",
            "args": {"output_id": "artifact:report",
                "artifact_digest": built["body"]["data"]["artifact_digest"],
                "destination_id": "sink:report",
                "validation_receipt_id": validated["body"]["data"]["validation_receipt_id"],
                "grant_ref": prepared["body"]["data"]["grant_ref"],
                "idempotency_key": "publish-second"}})
        self.store.stage_object(second_call, trusted_role="runtime")
        self.store.register_call_batch("run-1", 1, "publish-second-response", [{
            "call_digest": second_call["digest"], "native_tool_call_id": "native-second",
            "batch_index": 0}])
        first = self.publish(built, validated, prepared)
        self.assertEqual(first["body"]["outcome"], "ok")
        second = self.store.execute_call(second_call["digest"], "publish_artifact")
        self.assertEqual(second["body"]["outcome"], "error")
        with sqlite3.connect(self.store.path) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM publications").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
