"""Initialize and audit the shared M6 campaign cap before any API request."""

from __future__ import annotations

import json
import os
import sqlite3
import stat
from pathlib import Path

from skillloop.protection.api_budget import ScopedAPIBudget
from skillloop.protocol import digest_jcs


PRIVATE = Path.home() / "skillloop/api-private"
ACTIVITY = Path.home() / "skillloop/m6-api-refunds-v1"
LEDGER = PRIVATE / "calibration-v1/cost.sqlite"
SCOPE = "m6-markdown-refunds-api-v1"
CAP_RMB = "50.00"
LEGACY_CAP_RMB = "10.00"


def main() -> None:
    config = json.loads((PRIVATE / "config.json").read_text())
    if stat.S_IMODE(LEDGER.stat().st_mode) != 0o600:
        raise ValueError("shared_ledger_permissions")
    budget = ScopedAPIBudget(LEDGER, input_rate=config["input_price_per_million_rmb"],
        output_rate=config["output_price_per_million_rmb"], limit_rmb=CAP_RMB,
        legacy_limit_rmb=LEGACY_CAP_RMB, scope_id=SCOPE)
    db = sqlite3.connect(LEDGER)
    event = db.execute("SELECT scope,limit_micro,baseline_micro,event_id,created_at FROM campaign_caps WHERE scope=?",
        (SCOPE,)).fetchone()
    reservations = db.execute("SELECT COUNT(*),COALESCE(SUM(reserved_micro),0),COALESCE(SUM(charged_micro),0) FROM reservations").fetchone()
    states = db.execute("SELECT state,COUNT(*) FROM reservations GROUP BY state ORDER BY state").fetchall()
    binding = db.execute("SELECT value FROM metadata WHERE key='binding'").fetchone()[0]
    db.close()
    report = {
        "kind": "JointM6ApiBudgetInitialization",
        "ledger_ref": str(LEDGER),
        "ledger_mode": "0600",
        "scope_id": event[0],
        "joint_cap_micro_rmb": event[1],
        "joint_cap_rmb": "50.00",
        "legacy_cap_rmb": LEGACY_CAP_RMB,
        "campaign_event_id": event[3],
        "campaign_created_at": event[4],
        "baseline_ledger_usage_micro_rmb": event[2],
        "reservations_digest_binding_unchanged": binding == digest_jcs({
            "input_rate": config["input_price_per_million_rmb"],
            "output_rate": config["output_price_per_million_rmb"],
            "limit_rmb": LEGACY_CAP_RMB}),
        "reservation_count": reservations[0],
        "reservation_ceiling_micro_rmb": reservations[1],
        "ledger_accounted_usage_micro_rmb": reservations[2],
        "reservation_states": states,
        "remaining_joint_headroom_micro_rmb": event[1] - reservations[2],
        "api_requests_made": 0,
    }
    if not report["reservations_digest_binding_unchanged"]:
        raise ValueError("legacy_budget_binding_changed")
    target = ACTIVITY / "joint-budget-initialization.json"
    if target.exists():
        old = json.loads(target.read_text())
        if old.get("campaign_event_id") != event[3]:
            raise ValueError("joint_budget_event_changed")
    else:
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        os.chmod(target, 0o600)
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
