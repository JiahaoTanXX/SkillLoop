"""Operator ordering tests; no model runs or attack acceptance evidence."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from operations.dgx_m6_sequence import (PROFILES, Sequence, blockers, save_once,
    second_round_allowed, stage_timeout)


class SequenceTests(unittest.TestCase):
    def test_receipts_are_private_and_cannot_be_replaced(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "receipt.json"
            save_once(path, {"value": 1})
            original = path.read_bytes()
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                save_once(path, {"value": 2})
            self.assertEqual(path.read_bytes(), original)

    def test_remaining_clock_limits_stage_and_never_resets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            save_once(root / "manifest.json", {"admission_clock": {"started_at_unix_ms": 1000000}})
            self.assertEqual(stage_timeout(root, 300, 1000 + 28750), 50)
            with self.assertRaisesRegex(RuntimeError, "wall_budget_exhausted"):
                stage_timeout(root, 300, 1000 + 28800)
            self.assertEqual(stage_timeout(root, 300, 1100), 300)

    def test_frozen_or_missing_required_items_prevent_second_round(self):
        row = {"frozen": False, "missing": [], "submitted_absent_items": [],
            "submitted_executed_required_runs": 21, "submitted_required_runs": 21}
        self.assertTrue(second_round_allowed(row))
        for change in ({"frozen": True}, {"missing": ["missing"]},
                       {"submitted_absent_items": ["missing"]},
                       {"submitted_executed_required_runs": 20}):
            self.assertFalse(second_round_allowed({**row, **change}))

    def test_reused_pid_does_not_block_and_old_worker_does(self):
        with patch("operations.dgx_m6_sequence.process_command", side_effect=lambda pid:
                   "unrelated" if pid == 1 else "/private/old/regress --worker"), \
                patch("operations.dgx_m6_sequence.Path.glob", return_value=[Path("/proc/2")]):
            self.assertEqual(blockers({1: "old-master"}, [Path("/private/old")]), [2])

    def make_sequence(self, root):
        sequence = Sequence.__new__(Sequence)
        sequence.base, sequence.output = root, root / "operator"
        sequence.output.mkdir()
        sequence.reports = []
        sequence.review = lambda reports, **kwargs: {"status": "pending", "unit_test_only": True}
        sequence.seal = save_once
        return sequence

    def test_next_profile_prepared_only_after_previous_profile_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sequence = self.make_sequence(root)
            calls = []
            def prepare(profile, campaign, *, parent=None):
                if calls:
                    previous = PROFILES[PROFILES.index(profile) - 1]
                    self.assertTrue((sequence.output / (previous + "-closed.json")).exists())
                calls.append(profile)
                return True
            sequence.prepare = prepare
            sequence.evaluate = lambda *args, **kwargs: {"frozen": True}
            sequence.profiles()
            self.assertEqual(calls, list(PROFILES))
            self.assertTrue((sequence.output / "acceptance-review.json").exists())

    def test_second_round_inherits_first_profile_and_finishes_before_next(self):
        with tempfile.TemporaryDirectory() as temporary:
            sequence = self.make_sequence(Path(temporary))
            calls = []
            def prepare(profile, campaign, *, parent=None):
                calls.append(("prepare", profile, bool(parent)))
                return True
            def evaluate(profile, campaign, calibration, *, first):
                calls.append(("evaluate", profile, first))
                return {"frozen": not first, "missing": [], "submitted_absent_items": [],
                    "submitted_executed_required_runs": 21, "submitted_required_runs": 21}
            sequence.prepare, sequence.evaluate = prepare, evaluate
            sequence.profiles()
            self.assertEqual(calls[:5], [("prepare", "orders_total", False),
                ("evaluate", "orders_total", True), ("prepare", "orders_total", True),
                ("evaluate", "orders_total", False), ("prepare", "refunds_total", False)])
            self.assertEqual(len(calls), 12)

    def test_budget_rejection_keeps_profile_pending_and_moves_to_next_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            sequence = self.make_sequence(Path(temporary))
            calls = []
            sequence.prepare = lambda profile, campaign, **kwargs: calls.append(profile) or True
            sequence.evaluate = lambda *args, **kwargs: None
            sequence.profiles()
            self.assertEqual(calls, list(PROFILES))
            for profile in PROFILES:
                record = json.loads((sequence.output / (profile + "-closed.json")).read_text())
                self.assertEqual(record["status"], "not_accepted")

    def test_runtime_identity_change_rejected_before_stage(self):
        sequence = Sequence.__new__(Sequence)
        sequence.runtime = Path("/unused")
        sequence.digest = lambda data: "changed"
        sequence.source_index = lambda runtime: {}
        with self.assertRaisesRegex(ValueError, "runtime_source_changed"):
            sequence.verify_source()


if __name__ == "__main__":
    unittest.main()
