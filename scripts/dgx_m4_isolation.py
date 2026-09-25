"""DGX-only positive/negative peer UID and model-mount isolation probe."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skillloop.proxy.server import ProxyServer
from skillloop.proxy.store import ProxyStore


CLIENT_CODE = """
import json,socket,sys
s=socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET)
s.settimeout(5)
s.connect('/socket/'+sys.argv[1])
s.send(b'{}')
print(json.dumps(json.loads(s.recv(4096))))
"""


def probe(root: Path) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    store = ProxyStore(root / "isolation.db", deployment_epoch="m4-isolation")
    sockets = root / "sockets"
    server = ProxyServer(store, sockets, controller_uid=os.getuid(),
                         runtime_uid=21002, socket_mode=0o666)
    with server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            def client(uid: int, name: str) -> dict:
                run = subprocess.run(["docker", "run", "--rm", "--network", "none",
                    "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                    "--user", str(uid), "-v", f"{sockets}:/socket:rw",
                    "public.ecr.aws/docker/library/python:3.12-slim",
                    "python", "-c", CLIENT_CODE, name], capture_output=True,
                    text=True, timeout=30, check=True)
                return json.loads(run.stdout)
            runtime_tool = client(21002, "tool.sock")
            generator_tool = client(21006, "tool.sock")
            runtime_control = client(21002, "control.sock")
        finally:
            server.stop()
            thread.join(timeout=2)
    model = json.loads(subprocess.run(["docker", "inspect", "skillloop-m4-sglang"],
                                      capture_output=True, text=True, timeout=10, check=True).stdout)[0]
    mounts = model["Mounts"]
    published = model["NetworkSettings"]["Ports"]["30000/tcp"]
    result = {"runtime_tool_authenticated": runtime_tool == {"ok": False, "error_code": "invalid_args"},
              "generator_tool_denied": generator_tool == {"ok": False, "error_code": "denied"},
              "runtime_control_denied": runtime_control == {"ok": False, "error_code": "denied"},
              "model_mounts_only_readonly_weights": len(mounts) == 1 and mounts[0]["Destination"] == "/model"
                  and not mounts[0]["RW"],
              "model_published_loopback_only": all(item["HostIp"] == "127.0.0.1" for item in published),
              "model_offline_loading": all(name in model["Config"]["Env"] for name in
                   ("HF_HUB_OFFLINE=1", "TRANSFORMERS_OFFLINE=1"))}
    (root / "isolation.json").write_text(json.dumps(result, indent=2) + "\n")
    if not all(result.values()):
        raise RuntimeError("isolation_gate_failed")
    return result


if __name__ == "__main__":
    print(json.dumps(probe(Path.home() / "skillloop/platform/m4/isolation")))
