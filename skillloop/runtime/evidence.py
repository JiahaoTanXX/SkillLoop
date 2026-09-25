"""Private content-addressed trace with an explicit 4 MiB completeness limit."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from skillloop.protocol import canonical_json_line, digest_bytes, digest_jcs, make_envelope


MAX_TRACE_BYTES = 4 * 1024 * 1024


class TraceLimit(RuntimeError):
    pass


class PrivateTrace:
    def __init__(self, root: Path, run_id: str):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        self.contexts = self.root / "contexts"
        self.contexts.mkdir(exist_ok=True, mode=0o700)
        self.path = self.root / ("run-" + digest_jcs(run_id).removeprefix("sha256:") + ".jsonl")
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        self.file = os.fdopen(fd, "wb")
        self.size = 0
        self.context_bytes = 0
        self.event_digests: list[str] = []

    def context(self, messages: list[dict[str, Any]]) -> str:
        raw = canonical_json_line(messages)
        digest = digest_bytes(raw)
        target = self.contexts / digest.removeprefix("sha256:")
        if not target.exists():
            if self.size + self.context_bytes + len(raw) > MAX_TRACE_BYTES:
                raise TraceLimit("trace_limit")
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as output:
                output.write(raw)
                output.flush()
                os.fsync(output.fileno())
            self.context_bytes += len(raw)
        return digest

    def append(self, event: dict[str, Any]) -> str:
        raw = canonical_json_line(event)
        if self.size + self.context_bytes + len(raw) > MAX_TRACE_BYTES:
            raise TraceLimit("trace_limit")
        self.file.write(raw)
        self.file.flush()
        os.fsync(self.file.fileno())
        self.size += len(raw)
        digest = digest_bytes(raw)
        self.event_digests.append(digest)
        return digest

    def finish(self, *, run_id: str, task_instance_id: str, subject_digest: str,
               trust_revision: int, complete: bool) -> dict[str, Any]:
        self.file.close()
        raw = self.path.read_bytes()
        return make_envelope("EvidenceIndex", {"run_id": run_id,
            "task_instance_id": task_instance_id, "subject_digest": subject_digest,
            "event_digests": self.event_digests, "trace_digest": digest_bytes(raw),
            "complete": complete, "issuer": "trusted-collector",
            "trust_revision": trust_revision})
