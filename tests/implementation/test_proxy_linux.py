"""Linux-only AF_UNIX and SO_PEERCRED mechanism checks for M3."""

from __future__ import annotations

import json
import os
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path

from skillloop.families.registry import FamilyRegistry
from skillloop.protocol import canonical_json_line, digest_jcs, make_envelope
from skillloop.proxy.server import MAX_MESSAGE_BYTES, ProxyServer
from skillloop.proxy.store import ProxyStore
from skillloop.proxy.wire import make_control
from tests.implementation.test_proxy_store import fixture, stamp


@unittest.skipUnless(hasattr(socket, "SO_PEERCRED") and hasattr(socket, "SOCK_SEQPACKET"),
                     "Linux SO_PEERCRED required")
class LinuxProxyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.store = ProxyStore(root / "authority.db", deployment_epoch="m3-linux-test")
        domain, policy, binding, request, approval, raw = fixture()
        self.store.stage_approval(domain, approval)
        self.store.activate_approval(approval["digest"], 0, operation_id="activate-linux",
                                     request_digest=digest_jcs("activate-linux"))
        self.store.stage_task(domain=domain, policy=policy, binding=binding, run_request=request,
            profile_id="orders_total", resources=raw, approval_digest=approval["digest"],
            run_deadline=stamp(240), campaign_id="campaign-linux")
        self.store.start_run(request["digest"], binding["digest"], operation_id="start-linux",
                             request_digest=digest_jcs("start-linux"))
        self.directory = root / "socket"

    def _serve(self, controller_uid: int, runtime_uid: int) -> tuple[ProxyServer, threading.Thread]:
        server = ProxyServer(self.store, self.directory, controller_uid=controller_uid,
                             runtime_uid=runtime_uid, socket_mode=0o600)
        server.__enter__()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(lambda: (server.stop(), thread.join(timeout=2), server.__exit__(None, None, None)))
        return server, thread

    def _request(self, socket_name: str, method: str, params: dict) -> dict:
        message = make_control("ControlRequest", {"operation_id": f"rpc-{time.time_ns()}",
            "deadline": stamp(5), "method": method, "params": params})
        with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as client:
            client.settimeout(5)
            client.connect(str(self.directory / socket_name))
            client.send(canonical_json_line(message))
            return json.loads(client.recv(MAX_MESSAGE_BYTES))

    def test_uid_and_socket_method_boundaries(self) -> None:
        self._serve(controller_uid=os.getuid(), runtime_uid=os.getuid() + 1)
        recovery = self._request("control.sock", "recover_operation", {
            "run_id": "run-1", "tool": "build_artifact", "idempotency_key": "missing"})
        self.assertTrue(recovery["ok"])
        self.assertEqual(recovery["result"]["body"]["state"], "proven_not_started")
        denied_uid = self._request("tool.sock", "recover_operation", {
            "run_id": "run-1", "tool": "build_artifact", "idempotency_key": "missing"})
        self.assertEqual(denied_uid, {"ok": False, "error_code": "denied"})
        denied_method = self._request("control.sock", "register_call_batch", {
            "run_id": "run-1", "fence": 1, "response_id": "wrong-role", "calls": []})
        self.assertEqual(denied_method, {"ok": False, "error_code": "denied"})

    def test_runtime_registered_tool_call_over_seqpacket(self) -> None:
        self._serve(controller_uid=os.getuid() + 1, runtime_uid=os.getuid())
        resource_id = next(iter(FamilyRegistry().profile("orders_total")["input_bindings"].values()))
        call = make_envelope("ToolCall", {"call_id": "linux-read", "run_id": "run-1",
            "task_instance_id": "task-1", "fencing_token": 1, "tool": "read_resource",
            "args": {"resource_id": resource_id}})
        with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as client:
            client.settimeout(5)
            client.connect(str(self.directory / "ingress.sock"))
            client.send(canonical_json_line(call))
            ingress = json.loads(client.recv(MAX_MESSAGE_BYTES))
        self.assertEqual(ingress, {"ok": True, "call_digest": call["digest"]})
        registered = self._request("tool.sock", "register_call_batch", {"run_id": "run-1",
            "fence": 1, "response_id": "linux-response", "calls": [{"call_digest": call["digest"],
            "native_tool_call_id": "native-linux", "batch_index": 0}]})
        self.assertTrue(registered["ok"])
        result = self._request("tool.sock", "read_resource", {"call_digest": call["digest"]})
        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["body"]["outcome"], "ok")
        self.assertEqual(result["result"]["body"]["call_id"], "linux-read")
        denied_controller = self._request("control.sock", "recover_operation", {
            "run_id": "run-1", "tool": "read_resource", "idempotency_key": "missing"})
        self.assertEqual(denied_controller, {"ok": False, "error_code": "denied"})

    def test_oversized_packet_rejected_before_json_parse(self) -> None:
        self._serve(controller_uid=os.getuid(), runtime_uid=os.getuid() + 1)
        with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as client:
            client.settimeout(5)
            client.connect(str(self.directory / "control.sock"))
            try:
                client.send(b"x" * (MAX_MESSAGE_BYTES + 1))
            except OSError as error:
                # Linux may cap AF_UNIX packets below the application cap.
                self.assertEqual(error.errno, 90)
                return
            result = json.loads(client.recv(4096))
        self.assertEqual(result, {"ok": False, "error_code": "invalid_args"})
