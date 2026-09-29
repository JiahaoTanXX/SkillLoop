"""Append-only private failure history with explicit compatibility and bindings."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from skillloop.protocol import digest_jcs, validate_envelope


class FailureHistory:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        self.path = path
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS failures (digest TEXT PRIMARY KEY, compatibility TEXT NOT NULL, record TEXT NOT NULL)")
        os.chmod(path, 0o600)

    def add(self, *, compatibility: dict, case: dict, mutation: dict | None,
            result: dict, evidence_ref: str, gate_digest: str | None) -> str:
        for record in (case, result):
            validate_envelope(record)
        if case["kind"] != "CaseTemplate" or result["kind"] != "RunResultBody":
            raise ValueError("history_record_kind")
        body = result["body"]
        if body["case_digest"] != case["digest"] or not (body["security_violation"] or body["utility_status"] == "fail"):
            raise ValueError("history_requires_bound_confirmed_failure")
        if mutation is not None:
            validate_envelope(mutation)
        if case["body"]["mutation_digest"] != (mutation["digest"] if mutation else None):
            raise ValueError("history_mutation_binding")
        if set(compatibility) != {"family", "profile", "contract_digest", "objective_registry_digest", "oracle_digest", "privacy_domain"}:
            raise ValueError("history_compatibility_shape")
        entry = {"compatibility": compatibility, "case": case, "mutation": mutation,
                 "result_digest": result["digest"], "source_subject_digest": body["subject_digest"],
                 "evidence_ref": evidence_ref, "gate_digest": gate_digest}
        digest = digest_jcs(entry)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT OR IGNORE INTO failures VALUES (?, ?, ?)",
                       (digest, digest_jcs(compatibility), json.dumps(entry, ensure_ascii=False, sort_keys=True)))
        return digest

    def applicable(self, compatibility: dict) -> list[dict]:
        with closing(sqlite3.connect(self.path)) as db:
            rows = db.execute("SELECT digest, record FROM failures WHERE compatibility=? ORDER BY digest",
                              (digest_jcs(compatibility),)).fetchall()
        result = []
        for digest, text in rows:
            record = json.loads(text)
            if digest_jcs(record) != digest or record["compatibility"] != compatibility:
                raise ValueError("history_integrity")
            result.append({"digest": digest, **record})
        return result
