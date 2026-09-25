"""Linux AF_UNIX SOCK_SEQPACKET boundary with kernel peer UID authorization."""

from __future__ import annotations

import os
import selectors
import socket
import struct
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from skillloop.protocol import ProtocolError, canonical_json_line

from .store import ProxyError, ProxyStore
from .wire import make_control, parse_control


MAX_MESSAGE_BYTES = 262_144
MAX_REQUEST_SECONDS = 10


def _deadline(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("deadline_timezone")
    return parsed.astimezone(timezone.utc)


class ProxyServer:
    """Two sockets: controller operations and registered runtime tool calls."""

    def __init__(self, store: ProxyStore, directory: Path, *,
                 controller_uid: int = 21001, runtime_uid: int = 21002,
                 socket_mode: int = 0o660, controller_gid: int | None = None,
                 runtime_gid: int | None = None):
        if not hasattr(socket, "SO_PEERCRED") or not hasattr(socket, "SOCK_SEQPACKET"):
            raise RuntimeError("linux_peercred_seqpacket_required")
        self.store = store
        self.directory = Path(directory)
        self.controller_uid = controller_uid
        self.runtime_uid = runtime_uid
        self.socket_mode = socket_mode
        self.controller_gid = controller_gid
        self.runtime_gid = runtime_gid
        self._selector = selectors.DefaultSelector()
        self._sockets: list[socket.socket] = []
        self._stop = threading.Event()
        self._active = {"controller": 0, "runtime": 0}
        self._lock = threading.Lock()

    def __enter__(self) -> "ProxyServer":
        self.directory.mkdir(parents=True, exist_ok=True)
        for role, name, gid in (("controller", "control.sock", self.controller_gid),
                                ("runtime", "tool.sock", self.runtime_gid)):
            path = self.directory / name
            if path.exists():
                raise RuntimeError("socket_path_exists")
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
            listener.bind(str(path))
            listener.listen(16)
            os.chmod(path, self.socket_mode)
            if gid is not None:
                os.chown(path, -1, gid)
            self._selector.register(listener, selectors.EVENT_READ, role)
            self._sockets.append(listener)
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        for listener in self._sockets:
            self._selector.unregister(listener)
            listener.close()
        self._selector.close()
        for name in ("control.sock", "tool.sock"):
            (self.directory / name).unlink(missing_ok=True)

    def serve_forever(self) -> None:
        while not self._stop.is_set():
            for key, _mask in self._selector.select(timeout=0.2):
                connection, _address = key.fileobj.accept()
                with self._lock:
                    if self._active[key.data] >= 16:
                        connection.close()
                        continue
                    self._active[key.data] += 1
                threading.Thread(target=self._handle, args=(connection, key.data), daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def _handle(self, connection: socket.socket, socket_role: str) -> None:
        try:
            connection.settimeout(MAX_REQUEST_SECONDS)
            raw_peer = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
            _pid, uid, _gid = struct.unpack("3i", raw_peer)
            expected = self.controller_uid if socket_role == "controller" else self.runtime_uid
            # Consume one bounded packet before replying. Closing a SEQPACKET socket
            # with unread input can turn the explicit denial into ECONNRESET.
            raw, _ancillary, flags, _address = connection.recvmsg(MAX_MESSAGE_BYTES + 1)
            if uid != expected:
                self._send(connection, {"ok": False, "error_code": "denied"})
                return
            if not raw or len(raw) > MAX_MESSAGE_BYTES or flags & socket.MSG_TRUNC:
                self._send(connection, {"ok": False, "error_code": "invalid_args"})
                return
            try:
                request = parse_control(raw)
                result = self.dispatch(request, socket_role)
                self._send(connection, {"ok": True, "result": result})
            except (ProxyError, ProtocolError, KeyError, TypeError, ValueError) as error:
                code = error.code if isinstance(error, ProxyError) else "invalid_args"
                self._send(connection, {"ok": False, "error_code": code})
        except (OSError, TimeoutError):
            pass
        finally:
            connection.close()
            with self._lock:
                self._active[socket_role] -= 1

    @staticmethod
    def _send(connection: socket.socket, value: dict[str, Any]) -> None:
        raw = canonical_json_line(value)
        if len(raw) > MAX_MESSAGE_BYTES:
            raw = canonical_json_line({"ok": False, "error_code": "runtime_error"})
        connection.sendall(raw)

    def dispatch(self, request: dict[str, Any], role: str) -> dict[str, Any]:
        """Role is supplied only after SO_PEERCRED verification in _handle."""
        if request["kind"] != "ControlRequest":
            raise ProxyError("invalid_args")
        body = request["body"]
        remaining = _deadline(body["deadline"]) - datetime.now(timezone.utc)
        if remaining <= timedelta(0):
            raise ProxyError("expired")
        if remaining > timedelta(seconds=MAX_REQUEST_SECONDS):
            raise ProxyError("invalid_args")
        method, params = body["method"], body["params"]
        controller = {"activate_approval", "revoke_approval", "start_run",
                      "cancel_run", "recover_operation", "get_operation"}
        runtime = {"register_call_batch", "read_resource", "build_artifact", "write_artifact",
                   "validate_artifact", "prepare_publication", "publish_artifact", "get_operation"}
        if method not in (controller if role == "controller" else runtime if role == "runtime" else set()):
            raise ProxyError("denied")
        opid = body["operation_id"]
        digest = request["digest"]
        if method == "activate_approval":
            result = self.store.activate_approval(params["approval_digest"], params["expected_trust_revision"],
                operation_id=opid, request_digest=digest)
            return make_control("ApprovalResult", {"operation_id": opid, "approval_ref": result["approval_digest"],
                "effective_trust_revision": result["trust_revision"], "state": result["state"],
                "committed_at": result["committed_at"], "expires_at": result["expires_at"]})
        if method == "revoke_approval":
            result = self.store.revoke_approval(params["approval_digest"], params["expected_trust_revision"],
                operation_id=opid, request_digest=digest)
            return make_control("ApprovalResult", {"operation_id": opid, "approval_ref": result["approval_digest"],
                "effective_trust_revision": result["trust_revision"], "state": result["state"],
                "committed_at": result["committed_at"], "expires_at": result["expires_at"]})
        if method == "start_run":
            return self.store.start_run(params["run_request_digest"], params["task_binding_digest"],
                operation_id=opid, request_digest=digest)
        if method == "cancel_run":
            result = self.store.cancel_run(params["run_id"], params["expected_fence"],
                operation_id=opid, request_digest=digest)
            return make_control("CancellationResult", {"campaign_public_ref": result["campaign_id"],
                "run_id": result["run_id"], "effective_fence": result["fence"],
                "committed_at": result["committed_at"]})
        if method == "recover_operation":
            result = self.store.recover_tool(params["run_id"], params["tool"], params["idempotency_key"])
            return make_control("RecoveryResult", result)
        if method == "register_call_batch":
            result = self.store.register_call_batch(params["run_id"], params["fence"],
                                                    params["response_id"], params["calls"])
            return make_control("RegistrationResult", result)
        if method in TOOL_NAMES:
            return self.store.execute_call(params["call_digest"], method)
        if method == "get_operation":
            return make_control("OperationStatus", self.store.get_operation(params["operation_ref"], role))
        raise ProxyError("denied")


TOOL_NAMES = frozenset({"read_resource", "build_artifact", "write_artifact",
                        "validate_artifact", "prepare_publication", "publish_artifact"})
