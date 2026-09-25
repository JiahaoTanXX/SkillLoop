"""Authenticated local Proxy transport; Runtime never opens the SQLite file."""

from __future__ import annotations

import socket
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from skillloop.protocol import canonical_json_line, decode_json, validate_envelope
from skillloop.proxy.wire import make_control, validate_control


class ProxyRPCError(RuntimeError):
    pass


class ProxyClient:
    def __init__(self, socket_dir: Path, *, timeout_seconds: float = 10):
        self.socket_dir = Path(socket_dir)
        self.timeout_seconds = timeout_seconds

    def _send(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        with socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET) as connection:
            connection.settimeout(self.timeout_seconds)
            connection.connect(str(self.socket_dir / name))
            connection.sendall(canonical_json_line(payload))
            raw = connection.recv(262_145)
        if not raw:
            raise ProxyRPCError("empty_proxy_response")
        value = decode_json(raw)
        if type(value) is not dict or value.get("ok") is not True:
            raise ProxyRPCError(str(value.get("error_code", "invalid_proxy_response")))
        return value

    def import_call(self, call: dict[str, Any]) -> str:
        validate_envelope(call)
        if call["kind"] != "ToolCall":
            raise ProxyRPCError("not_tool_call")
        reply = self._send("ingress.sock", call)
        if reply.get("call_digest") != call["digest"]:
            raise ProxyRPCError("call_identity_mismatch")
        return call["digest"]

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        deadline = datetime.now(timezone.utc) + timedelta(seconds=9)
        request = make_control("ControlRequest", {
            "operation_id": "runtime-" + uuid.uuid4().hex,
            "deadline": deadline.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "method": method, "params": params,
        })
        result = self._send("tool.sock", request).get("result")
        if type(result) is not dict:
            raise ProxyRPCError("invalid_proxy_result")
        if result.get("kind") == "ToolResult":
            validate_envelope(result)
        else:
            validate_control(result)
        return result
