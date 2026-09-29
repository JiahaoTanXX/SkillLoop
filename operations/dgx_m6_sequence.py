"""Run private M6 profile campaigns sequentially after retained jobs drain.

The runtime checkout is immutable and separate from this operator program.
This program never starts M7 or grants production eligibility.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


PROFILES = ("orders_total", "refunds_total", "markdown_index")
EXPECTED_SOURCE = "sha256:af90fcfb855095c624f72c5ab17f5a9c27c856eed67f65d30cc938b367e106b7"
M5_DIGEST = "sha256:33bb8d78a32e7b5346896574f086c97bc86edfc566c9bef2a462215fe5d99bf6"


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def save_once(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("x") as stream:
        os.chmod(path, 0o600)
        json.dump(data, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def process_command(pid: int) -> str | None:
    path = Path("/proc") / str(pid)
    try:
        if "(zombie)" in (path / "status").read_text():
            return None
        return (path / "cmdline").read_bytes().replace(b"\0", b" ").decode()
    except FileNotFoundError:
        return None


def blockers(jobs: dict[int, str], evidence: list[Path]) -> list[int]:
    active = []
    for pid, expected in jobs.items():
        command = process_command(pid)
        if command and expected in command:
            active.append(pid)
    for path in Path("/proc").glob("[0-9]*"):
        pid = int(path.name)
        if pid == os.getpid():
            continue
        command = process_command(pid)
        if command and any(str(root) in command for root in evidence):
            active.append(pid)
    return sorted(set(active))


def stage_timeout(root: Path | None, bound: int, now: float) -> float:
    if root is None or not (root / "manifest.json").is_file():
        return bound
    manifest = load(root / "manifest.json")
    clock = manifest["admission_clock"]
    remaining = 28800 - (now - clock["started_at_unix_ms"] / 1000)
    if remaining <= 0:
        raise RuntimeError("profile_wall_budget_exhausted")
    return min(bound, remaining)


def second_round_allowed(row: dict) -> bool:
    return (not row["frozen"] and not row["missing"] and
            not row["submitted_absent_items"] and
            row["submitted_executed_required_runs"] == row["submitted_required_runs"])


class Sequence:
    def __init__(self, *, base: Path, runtime: Path, python: Path, output: Path):
        self.base, self.runtime, self.python, self.output = base, runtime, python, output
        sys.path.insert(0, str(runtime))
        from scripts.dgx_m6_repair import source_index
        from skillloop.protocol import digest_jcs
        from skillloop.repair.acceptance import review
        self.source_index, self.digest, self.review = source_index, digest_jcs, review
        self.reports = []

    def verify_source(self) -> None:
        if self.digest(self.source_index(self.runtime)) != EXPECTED_SOURCE:
            raise ValueError("runtime_source_changed")

    def seal(self, path: Path, data: dict) -> None:
        save_once(path, {**data, "digest": self.digest(data)})

    def run(self, label: str, script: str, arguments: list[str], bound: int,
            *, clock_root: Path | None = None) -> None:
        self.verify_source()
        timeout = stage_timeout(clock_root, bound, time.time())
        log = self.output / (label + ".log")
        self.seal(self.output / (label + "-start.json"), {
            "stage": script, "bound_seconds": bound, "effective_timeout_seconds": timeout,
            "started_at_unix_ms": int(time.time() * 1000), "runtime_source_digest": EXPECTED_SOURCE})
        print(json.dumps({"stage": label, "status": "started"}), flush=True)
        with log.open("xb") as stream:
            os.chmod(log, 0o600)
            process = subprocess.Popen([str(self.python), str(self.runtime / "scripts" / script),
                *arguments], cwd=self.runtime, stdout=stream, stderr=stream, start_new_session=True)
            try:
                code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                # Only the owned stage process group; the shared inference service is separate.
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                code = 124
        self.seal(self.output / (label + "-finish.json"), {
            "stage": script, "exit_code": code, "finished_at_unix_ms": int(time.time() * 1000),
            "log_ref": str(log), "raw_output_private": True})
        if code:
            raise RuntimeError("stage_failed:" + label)

    def prepare(self, profile: str, root: Path, *, parent: Path | None = None) -> bool:
        arguments = ["prepare", "--output", str(root), "--profile", profile,
            "--baseline", str(self.base / "m5b-a30"), "--scan-index",
            str(self.base / "platform/m5b-pilot-scan-2/scan-index.json")]
        if parent:
            arguments += ["--parent-output", str(parent), "--parent-source", str(self.runtime)]
        else:
            arguments += ["--reuse-proposals", str(self.base / "m6-b01"),
                "--history-root", str(self.base / "m5b-nonthinking-1"),
                "--retained-development", str(self.base / "m6-b06"),
                "--retained-development", str(self.base / "m6-b08")]
        self.run(root.name + "-prepare", "dgx_m6_repair.py", arguments,
            570 if parent else 180, clock_root=parent)
        manifest = load(root / "manifest.json")
        if set(manifest["subjects"]) != {profile} or not manifest.get("admission_clock"):
            raise ValueError("single_profile_clock_missing")
        return manifest["subjects"][profile]["status"] == "applied"

    def evaluate(self, profile: str, root: Path, calibration: Path, *, first: bool) -> dict | None:
        self.run(root.name + "-scan", "dgx_m6_repair.py", ["rescan", "--output", str(root),
            "--profile", profile, "--image", "skillloop/skillspector-offline:m1", "--osv-data",
            str(self.base / "platform/offline-osv")], 300, clock_root=root)
        if first:
            self.run(root.name + "-calibrate", "dgx_m6_calibrate.py", ["calibrate",
                "--campaign", str(root), "--output", str(calibration)], 800, clock_root=root)
            if not load(calibration / "calibration.json")["ready"]:
                return None
        self.run(root.name + "-admit", "dgx_m6_admit.py", ["--campaign", str(root),
            "--calibration", str(calibration), "--profile", profile], 60, clock_root=root)
        if load(root / profile / "budget-admission.json")["admission"] != "ready":
            return None
        if first:
            self.run(root.name + "-submitted", "dgx_m6_repair.py", ["regress", "--output",
                str(root), "--profile", profile, "--subject-role", "submitted"], 28800, clock_root=root)
        self.run(root.name + "-candidate", "dgx_m6_repair.py", ["regress", "--output",
            str(root), "--profile", profile], 28800, clock_root=root)
        self.run(root.name + "-gate", "dgx_m6_gate.py", ["--output", str(root),
            "--baseline", str(self.base / "m5b-a30"), "--scan-index",
            str(self.base / "platform/m5b-pilot-scan-2/scan-index.json"),
            "--runtime-source", str(self.runtime)], 150, clock_root=root)
        report = load(root / "m6-gate.json")
        # Validation of the complete report chain is separate from the operator's decisions.
        self.review([*self.reports, report], m5_gate_digest=M5_DIGEST)
        self.reports.append(report)
        self.seal(self.output / (root.name + "-gate-receipt.json"), {
            "independent_gate_digest": report["digest"], "profile": profile,
            "runtime_source_digest": EXPECTED_SOURCE})
        return report["subjects"][profile]

    def profiles(self) -> None:
        for profile, suffix in zip(PROFILES, ("o", "r", "m")):
            first = self.base / ("m6-n11" + suffix)
            second = self.base / ("m6-n12" + suffix)
            calibration = self.base / ("m6-c11" + suffix)
            row = None
            if self.prepare(profile, first):
                row = self.evaluate(profile, first, calibration, first=True)
                if row is not None and second_round_allowed(row) and self.prepare(profile, second, parent=first):
                    row = self.evaluate(profile, second, calibration, first=False)
            self.seal(self.output / (profile + "-closed.json"), {
                "profile": profile, "status": "frozen" if row and row["frozen"] else "not_accepted",
                "first_ref": str(first), "second_ref": str(second) if second.exists() else None,
                "closed_at_unix_ms": int(time.time() * 1000), "production_ready": False})
            result = self.review(self.reports, m5_gate_digest=M5_DIGEST)
            save_once(self.output / (profile + "-review.json"), result)
            print(json.dumps({"profile": profile, "status": "closed", "m6_acceptance": result["status"]}), flush=True)
        save_once(self.output / "acceptance-review.json", self.review(self.reports, m5_gate_digest=M5_DIGEST))

    def wait_and_run(self) -> None:
        self.verify_source()
        jobs = {389706: str(self.base / "m6-v7-resume1.py"),
                578458: str(self.base / "m6-v9-finalize2.py")}
        retired = [self.base / name for name in ("m6-b08", "m6-b09o", "m6-b09r", "m6-b09m")]
        while blockers(jobs, retired):
            time.sleep(30)
        previous = load(self.base / "m6-final-acceptance-review.json")
        if previous.get("digest") != self.digest({k: v for k, v in previous.items() if k != "digest"}):
            raise ValueError("retained_acceptance_review_digest")
        if previous["status"] != "pending" or previous["m7_entry_ready"] is not False:
            raise ValueError("retained_campaign_requires_manual_acceptance_review")
        self.seal(self.output / "retained-campaign-review.json", {
            "prior_acceptance_review_digest": previous["digest"], "status": "not_accepted",
            "evidence_retained": True, "old_timestamps_preserved": True,
            "new_scores_will_not_reuse_old_runs": True})
        rejection = self.base / "m6-b08/configuration-rejection.json"
        if not rejection.exists():
            self.seal(rejection, {"status": "not_accepted", "evidence_retained": True,
                "reason_codes": ["retained_acceptance_pending", "per_profile_admission_clock_absent",
                                 "closed_actual_spending_snapshot_absent"],
                "acceptance_review_digest": previous["digest"], "production_ready": False})
        self.profiles()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    with (args.base / "m6-sequence.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        args.output.mkdir(mode=0o700, exist_ok=False)
        sequence = Sequence(base=args.base, runtime=args.runtime, python=args.python, output=args.output)
        sequence.seal(args.output / "started.json", {"kind": "M6SequentialOperatorRun",
            "pid": os.getpid(), "runtime_source_digest": EXPECTED_SOURCE,
            "started_at_unix_ms": int(time.time() * 1000), "protected_evaluation": "not_started",
            "production_ready": False})
        try:
            sequence.wait_and_run()
        except Exception as error:
            sequence.seal(args.output / "operator-failure.json", {
                "status": "not_accepted", "error_type": type(error).__name__,
                "raw_details_private": True, "protected_evaluation": "not_started",
                "production_ready": False})
            raise


if __name__ == "__main__":
    main()
