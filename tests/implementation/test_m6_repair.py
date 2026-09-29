from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts import spec_v22_core as reference
from scripts.dgx_m6_repair import append_history, execution_plan, retry_eligible, repair_obligations, scan_passed
from skillloop.discovery.suite import compile_dev_suite
from skillloop.discovery.scanner import ANALYZERS, reduce_scan
from skillloop.protocol import digest_bytes, digest_jcs, make_envelope
from skillloop.repair.applicator import apply_proposal, bundle
from skillloop.repair.budget import SpendingLedger, forecast, freeze, protected_reservations, revise, eliminate_protected_slots
from skillloop.repair.history import FailureHistory


class ApplicatorTests(unittest.TestCase):
    def setUp(self):
        self.files = reference.load("core/patch-files.json")
        self.policy = reference.load("core/policy-example.json")
        self.proposal = reference.load("core/patch-example.json")

    def apply(self, proposal=None, files=None, history=None, policy=None):
        return apply_proposal(proposal or self.proposal, files or self.files,
                              history or [], policy or self.policy)

    def changed(self, **fields):
        value = copy.deepcopy(self.proposal)
        value["body"].update(fields)
        return make_envelope("PatchProposal", value["body"])

    def test_matches_independent_reference_application(self):
        self.assertEqual(self.apply(), reference.apply_patch(self.proposal, self.files, [], self.policy))

    def test_wrong_subject_and_file_digest_rejected(self):
        with self.assertRaisesRegex(ValueError, "patch_parent_subject"):
            self.apply(self.changed(parent_subject_digest=digest_bytes(b"wrong")))
        edits = copy.deepcopy(self.proposal["body"]["edits"])
        edits[0]["parent_bytes_digest"] = digest_bytes(b"wrong")
        with self.assertRaisesRegex(ValueError, "patch_range_parent"):
            self.apply(self.changed(edits=edits))

    def test_frontmatter_and_forbidden_paths_rejected(self):
        for path in ("code.py", "oracle.py", "Gate.md", "requirements.txt", "../SKILL.md", "tests/test.py"):
            edits = copy.deepcopy(self.proposal["body"]["edits"])
            edits[0]["path"] = path
            with self.assertRaises(ValueError):
                self.apply(self.changed(edits=edits))
        edits = copy.deepcopy(self.proposal["body"]["edits"])
        edits[0].update(start_byte=4, end_byte=8)
        with self.assertRaisesRegex(ValueError, "frontmatter"):
            self.apply(self.changed(edits=edits))

    def test_overlap_and_split_utf8_rejected(self):
        edits = copy.deepcopy(self.proposal["body"]["edits"])
        with self.assertRaises(ValueError):
            self.apply(self.changed(edits=edits + edits))
        edits[0]["start_byte"] += 1
        with self.assertRaises(UnicodeError):
            self.apply(self.changed(edits=edits))

    def test_identical_text_and_policy_reordering_rejected(self):
        edits = copy.deepcopy(self.proposal["body"]["edits"])
        edit = edits[0]
        edit["replacement_utf8"] = self.files["files"]["SKILL.md"].encode()[edit["start_byte"]:edit["end_byte"]].decode()
        with self.assertRaisesRegex(ValueError, "no_change"):
            self.apply(self.changed(edits=edits))
        policy = copy.deepcopy(self.policy)
        policy["body"]["allowed_actions"].reverse()
        policy = make_envelope("Policy", policy["body"])
        files = copy.deepcopy(self.files)
        files["policies"][policy["digest"]] = policy
        with self.assertRaisesRegex(ValueError, "policy_no_change"):
            self.apply(self.changed(repair_kind="policy_only", edits=[], policy_digest=policy["digest"]), files)

    def test_expansion_rejected_and_tightening_allowed(self):
        for calls, expected in ((12, "reject"), (4, "pass")):
            body = copy.deepcopy(self.policy["body"])
            body["max_tool_calls"] = calls
            if expected == "reject":
                action = copy.deepcopy(body["allowed_actions"][0])
                action["bindings"][0]["slot"] = "another_source"
                body["allowed_actions"].append(action)
            policy = make_envelope("Policy", body)
            files = copy.deepcopy(self.files)
            files["policies"][policy["digest"]] = policy
            proposal = self.changed(repair_kind="policy_only", edits=[], policy_digest=policy["digest"])
            if expected == "reject":
                with self.assertRaisesRegex(ValueError, "expansion"):
                    self.apply(proposal, files)
            else:
                self.assertEqual(self.apply(proposal, files)["changed_paths"], [])

    def test_history_cost_tampering_and_third_round_rejected(self):
        first = self.apply()
        fixed = {key: self.files[key] for key in ("obligation_digest", "compiler_digest")}
        current = {"files": first["files"], "subject_digest": first["candidate_subject_digest"], "policies": {}, **fixed}
        raw = current["files"]["SKILL.md"].encode()
        start = raw.index(b"\n---\n", 4) + 5
        second = make_envelope("PatchProposal", {"parent_subject_digest": current["subject_digest"],
            "repair_kind": "text_only", "policy_digest": None, "edits": [{"path": "SKILL.md",
                "parent_bytes_digest": digest_bytes(raw), "start_byte": start, "end_byte": len(raw),
                "replacement_utf8": "Complete the original task.\n"}]})
        history = [first["history_entry"]]
        result = self.apply(second, current, history)
        self.assertGreater(result["cumulative_changed_bytes"], first["cumulative_changed_bytes"])
        tampered = copy.deepcopy(history)
        tampered[0]["changed_bytes"] = 0
        with self.assertRaisesRegex(ValueError, "cost_or_result"):
            self.apply(second, current, tampered)
        with self.assertRaisesRegex(ValueError, "round_budget"):
            self.apply(second, current, history + [result["history_entry"]])

    def test_cross_round_file_union_rejected(self):
        files = copy.deepcopy(self.files)
        files["files"].update({"references/a.md": "a\n", "references/b.md": "b\n", "references/c.md": "c\n"})
        fixed = {key: files[key] for key in ("obligation_digest", "compiler_digest")}
        files["subject_digest"] = bundle(files["files"], self.policy, **fixed)["digest"]
        edits = [{"path": path, "parent_bytes_digest": digest_bytes(files["files"][path].encode()),
                  "start_byte": 0, "end_byte": 1, "replacement_utf8": "x"} for path in
                 ("references/a.md", "references/b.md", "references/c.md")]
        first = self.apply(self.changed(parent_subject_digest=files["subject_digest"], edits=edits), files)
        current = {**files, "files": first["files"], "subject_digest": first["candidate_subject_digest"]}
        with self.assertRaisesRegex(ValueError, "cumulative_budget"):
            self.apply(self.changed(parent_subject_digest=current["subject_digest"]), current, [first["history_entry"]])

    def test_add_then_remove_still_consumes_byte_quota(self):
        files = copy.deepcopy(self.files)
        raw = files["files"]["SKILL.md"].encode()
        start = raw.index(b"\n---\n", 4) + 5
        files["files"]["SKILL.md"] = raw[:start].decode() + "a" * 3500 + "\n"
        fixed = {key: files[key] for key in ("obligation_digest", "compiler_digest")}
        files["subject_digest"] = bundle(files["files"], self.policy, **fixed)["digest"]
        def replacement(current, text):
            data = current["files"]["SKILL.md"].encode()
            return self.changed(parent_subject_digest=current["subject_digest"], edits=[{
                "path": "SKILL.md", "parent_bytes_digest": digest_bytes(data), "start_byte": start,
                "end_byte": len(data), "replacement_utf8": text}])
        first = self.apply(replacement(files, "b" * 3500 + "\n"), files)
        current = {**files, "files": first["files"], "subject_digest": first["candidate_subject_digest"]}
        with self.assertRaisesRegex(ValueError, "cumulative_budget"):
            self.apply(replacement(current, "a" * 3500 + "\n"), current, [first["history_entry"]])

    def test_duplicate_frontmatter_and_repair_kind_mismatch_rejected(self):
        files = copy.deepcopy(self.files)
        files["files"]["SKILL.md"] = files["files"]["SKILL.md"].replace("name: synthetic-skill\n", "name: synthetic-skill\nname: another\n")
        with self.assertRaisesRegex(ValueError, "frontmatter"):
            self.apply(files=files)
        with self.assertRaisesRegex(ValueError, "policy_only_has_file_edits"):
            self.apply(self.changed(repair_kind="policy_only"))
        with self.assertRaisesRegex(ValueError, "text_patch_missing"):
            self.apply(self.changed(edits=[]))


class PlanHistoryTests(unittest.TestCase):
    def test_stage_token_bounds_cover_all_warmup_model_rounds(self):
        from scripts.dgx_m6_repair import stage_bounds
        bounds = {stage["name"]: stage for stage in stage_bounds()}
        self.assertEqual(bounds["warmup"]["input_tokens"], 16 * 14336)
        self.assertEqual(bounds["warmup"]["output_tokens"], 16 * 2048)
        self.assertEqual(bounds["patcher"]["input_tokens"] + bounds["patcher"]["output_tokens"], 16384)
    def test_maximum_probe_uses_registered_canary_and_oracle(self):
        from scripts.dgx_m6_calibrate import maximum_inputs, probe_suite
        from skillloop.discovery.evaluator import synthetic_canary
        from skillloop.families.builders import build_artifact
        from skillloop.families.oracle import validate_artifact
        from skillloop.families.registry import FAMILY_SPEC
        for profile in ("orders_total", "refunds_total", "markdown_index"):
            inputs = maximum_inputs(profile)
            self.assertEqual(len(inputs["notes"]), 1024)
            self.assertTrue(synthetic_canary(inputs["notes"]))
            expected = build_artifact(profile, inputs)
            validate_artifact(profile, inputs, expected)
            compiled, _, plan = probe_suite(profile, FAMILY_SPEC)
            reference.validate_plan(plan, compiled["suite"])
            self.assertEqual(plan["body"]["reserved_rollouts"], 2)
        self.assertEqual(len(maximum_inputs("markdown_index")["document"]), 4096)

    def test_second_candidate_plan_retains_every_first_candidate_item(self):
        first = compile_dev_suite("markdown_index")
        first["subject_digest"] = digest_bytes(b"first")
        plan = execution_plan(first, campaign="shared-campaign")
        second = copy.deepcopy(first)
        second["subject_digest"] = digest_bytes(b"second")
        revised = execution_plan(second, campaign="shared-campaign", parent=plan)
        self.assertEqual(revised["body"]["items"][:15], plan["body"]["items"])
        self.assertEqual(revised["body"]["reserved_rollouts"], 30)
        self.assertEqual(revised["body"]["parent_plan_digest"], plan["digest"])
        case_id = next(iter(second["cases"]))
        retry = execution_plan(second, campaign="shared-campaign", parent=revised, retry=(case_id, 0))
        self.assertEqual(retry["body"]["items"][:15], plan["body"]["items"])

    def test_paired_submitted_and_candidate_rows_share_one_campaign_budget(self):
        compiled = compile_dev_suite("refunds_total")
        compiled["subject_digest"] = digest_bytes(b"candidate")
        submitted = digest_bytes(b"submitted")
        plan = execution_plan(compiled, campaign="paired", submitted_digest=submitted)
        self.assertEqual(plan["body"]["reserved_rollouts"], 30)
        self.assertEqual({i["subject_role"] for i in plan["body"]["items"]}, {"submitted", "candidate"})
        revised = dict(compiled, subject_digest=submitted)
        next_plan = execution_plan(revised, campaign="paired", parent=plan,
            retry=(next(iter(compiled["cases"])), 0))
        self.assertEqual(sum(i["attempts_reserved"] for i in next_plan["body"]["items"]), 31)
        self.assertTrue(all(i["attempts_reserved"] == 1 for i in next_plan["body"]["items"] if i["subject_role"] == "candidate"))

    def test_eliminated_capacity_slots_are_retained_and_delivered_slots_are_immutable(self):
        parent = revise(None, protected_reservations("first", role="finalist"))
        revised = eliminate_protected_slots(parent, "first", protected_reservations("second", role="finalist"))
        self.assertEqual(len(revised["items"]), 24)
        self.assertTrue(all(i["requirement"] == "abandoned" for i in revised["items"][:12]))
        self.assertEqual(revised["parent_digest"], parent["digest"])
        parent["items"][0]["result_ref"] = "actual-delivery"
        parent["digest"] = digest_jcs({k: v for k, v in parent.items() if k != "digest"})
        with self.assertRaisesRegex(ValueError, "search_closed"):
            eliminate_protected_slots(parent, "first", [])

    def test_generation_retries_are_counted_within_bounded_repair_rounds(self):
        arguments = dict(subject="s", development_verdict="pass", missing=[], unresolved_high=[],
            budget={"admission": "ready"}, evidence_digest=digest_bytes(b"gate"))
        self.assertEqual(freeze(**arguments, proposal_attempts=2, applied_candidates=1,
            evaluable_candidates=1, repair_rounds=1)["status"], "frozen")
        self.assertEqual(freeze(**arguments, proposal_attempts=4, applied_candidates=2,
            evaluable_candidates=2, repair_rounds=2)["status"], "frozen")
        self.assertEqual(freeze(**arguments, proposal_attempts=5, applied_candidates=2,
            evaluable_candidates=2, repair_rounds=2)["status"], "not_frozen")
    def test_zero_finding_meta_is_inapplicable_without_skipping_semantic_inspection(self):
        registry = json.loads(ANALYZERS.read_text())
        entries = [{"analyzer_id": name, "status": "completed", "planned_work": 1,
                    "completed": 1, "partial": 0, "skipped": 0, "failed": 0, "unaccounted": 0}
                   for name in registry["required_static_analyzers"] + registry["explicitly_disabled_semantic_analyzers"]]
        meta = next(e for e in entries if e["analyzer_id"] == "meta_analyzer")
        meta.update(status="not_applicable", reason_code="no_applicable_files", planned_work=0, completed=0)
        raw = {"execution_successful": True, "issues": [],
            "metadata": {"skillspector_version": "2.11.2", "llm_requested": True,
                         "llm_available": True, "meta_analysis_applied": False},
            "analysis_completeness": {"execution_successful": True, "is_complete": True, "status": "complete",
                "analyzer_statuses": entries, "findings_before_filtering": 0, "findings_after_filtering": 0}}
        def status():
            return reduce_scan("orders_total", json.dumps(raw).encode(), 0,
                               subject_digest=digest_bytes(b"candidate"), require_llm=True)[0]["body"]["status"]
        self.assertEqual(status(), "complete")
        raw["analysis_completeness"]["findings_before_filtering"] = 1
        self.assertEqual(status(), "incomplete")
        raw["analysis_completeness"]["findings_before_filtering"] = 0
        meta["planned_work"] = 1
        self.assertEqual(status(), "incomplete")
        meta["planned_work"] = 0
        semantic = next(e for e in entries if e["analyzer_id"] == "semantic_security_discovery")
        semantic.update(status="not_applicable", reason_code="no_applicable_files", planned_work=0, completed=0)
        self.assertEqual(status(), "incomplete")

    def test_scan_status_uses_api_report_status(self):
        report = {"body": {"status": "complete"}}
        self.assertTrue(scan_passed(report, 4, []))
        self.assertFalse(scan_passed(report, 0, []))
        self.assertFalse(scan_passed(report, 4, ["high"]))
        self.assertFalse(scan_passed({"body": {"status": "partial"}}, 4, []))

    def test_obligations_are_formal_domain_bound_objects(self):
        for profile in ("orders_total", "refunds_total", "markdown_index"):
            obligations = repair_obligations(profile)
            self.assertEqual(obligations["kind"], "RepairObligations")
            self.assertEqual({r["obligation"] for r in obligations["body"]["requirements"]},
                             {"require_validation", "restrict_resources", "restrict_destination"})

    def test_history_exact_digest_dedup_keeps_evidence_bindings(self):
        compiled = compile_dev_suite("orders_total")
        case = next(c for c in compiled["cases"].values() if c["body"]["case_kind"] == "attack")
        mutation = compiled["mutations"][case["body"]["case_id"]]
        records = [{"digest": digest_bytes(f"history-{i}".encode()), "case": case, "mutation": mutation} for i in range(2)]
        augmented, bindings = append_history(compiled, records)
        self.assertEqual(len(augmented["cases"]), 5)
        self.assertEqual(len(bindings), 2)
        self.assertEqual({b["equivalence"] for b in bindings}, {"exact_case_digest"})

    def test_history_opaque_alias_dedup_preserves_all_other_case_fields(self):
        compiled = compile_dev_suite("orders_total")
        case = next(c for c in compiled["cases"].values() if c["body"]["case_kind"] == "attack")
        alias = make_envelope("CaseTemplate", {**case["body"], "case_id": "orders_total.history-alias"})
        mutation = compiled["mutations"][case["body"]["case_id"]]
        record = {"digest": digest_bytes(b"history-alias"), "case": alias, "mutation": mutation}
        augmented, bindings = append_history(compiled, [record])
        self.assertEqual(len(augmented["cases"]), len(compiled["cases"]))
        self.assertEqual(bindings[0]["equivalence"], "same_case_body_except_opaque_id")
        self.assertEqual(bindings[0]["source_case_digest"], alias["digest"])
        different = make_envelope("CaseTemplate", {**alias["body"], "objective_ids": ["security.unvalidated-publication.v1"]})
        augmented, _ = append_history(compiled, [{**record, "case": different}])
        self.assertEqual(len(augmented["cases"]), len(compiled["cases"]) + 1)

    def test_append_only_revisions(self):
        item = {"subject": "s", "case": "c", "repetition": 0, "phase": "dev", "requirement": "required"}
        first = revise(None, [item])
        second = revise(first, [{**item, "subject": "s2"}])
        self.assertEqual(second["items"][0], item)
        self.assertEqual(second["parent_digest"], first["digest"])
        with self.assertRaises(ValueError):
            revise(second, [item])

    def test_uncalibrated_and_history_over_capacity_rejected(self):
        def items(n):
            return [{"subject": "s", "case": str(i), "repetition": 0, "phase": "dev", "requirement": "required"} for i in range(n)]
        calibration = {"ready": True, "victim_seconds": 180, "evidence_digests": [digest_bytes(b"e") ]}
        self.assertEqual(forecast(items(126), calibration=calibration, stages=[])["admission"], "ready")
        self.assertIn("victim_attempts_exceeded", forecast(items(127), calibration=calibration, stages=[])["reasons"])
        self.assertIn("calibration_pending", forecast(items(15), calibration={**calibration, "ready": False}, stages=[])["reasons"])

    def test_representative_plan_forecasts_include_stages_and_retry_reserve(self):
        from scripts.spec_v22_operations import expand_plan
        calibration = {"ready": True, "victim_seconds": 180, "evidence_digests": [digest_bytes(b"measured") ]}
        stage = {"count": 1, "seconds": 120, "input_tokens": 10, "output_tokens": 20, "disk_bytes": 4096}
        for counts, expected in (({}, 56), ({"findings": 1}, 68),
                                 ({"abandoned": 1, "active": 1}, 98),
                                 ({"history": 11}, 122), ({"history": 13}, 134)):
            entries = expand_plan(**counts)
            items = [{"subject": e["subject"], "case": e["case"], "repetition": e["repetition"],
                      "phase": e["phase"], "requirement": "required"} for e in entries]
            budget = forecast(items, calibration=calibration, stages=[stage])
            self.assertEqual(budget["reserved_attempts"], expected)
            self.assertEqual(budget["wall_seconds"], expected * 180 + 120)
            self.assertEqual(budget["admission"], "ready" if expected <= 128 else "rejected")

    def test_finalist_requires_protected_capacity_and_dev_pass(self):
        arguments = {"subject": "s", "missing": [], "unresolved_high": [], "proposal_attempts": 1,
            "applied_candidates": 1, "evaluable_candidates": 1, "evidence_digest": digest_bytes(b"gate")}
        self.assertEqual(freeze(**arguments, development_verdict="pass", budget={"admission": "ready"})["status"], "frozen")
        self.assertEqual(freeze(**arguments, development_verdict="fail", budget={"admission": "ready"})["status"], "not_frozen")
        self.assertEqual(freeze(**arguments, development_verdict="pass", budget={"admission": "rejected"})["status"], "not_frozen")
        self.assertEqual(len(protected_reservations("s", role="finalist")), 12)

    def test_spending_survives_restart_and_duplicate_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "spend.json"
            ledger = SpendingLedger(path)
            ledger.consume("case.0", 0)
            ledger = SpendingLedger(path)
            self.assertEqual(ledger.read()["victim_attempts"], 1)
            with self.assertRaises(ValueError):
                ledger.consume("case.0", 0)
            ledger.consume("case.0", 1)
            ledger.consume("case.1", 1)
            with self.assertRaises(ValueError):
                ledger.consume("case.2", 1)

    def test_execution_plan_only_adds_two_qualified_retries(self):
        compiled = compile_dev_suite("orders_total")
        compiled["subject_digest"] = digest_bytes(b"candidate")
        plan = execution_plan(compiled, campaign="m6-test")
        case_id = next(iter(compiled["cases"]))
        for rep in (0, 1):
            parent = plan
            plan = execution_plan(compiled, campaign="m6-test", parent=plan, retry=(case_id, rep))
            self.assertEqual(plan["body"]["parent_plan_digest"], parent["digest"])
        self.assertEqual(plan["body"]["reserved_rollouts"], 17)
        with self.assertRaises(ValueError):
            execution_plan(compiled, campaign="m6-test", parent=plan, retry=(case_id, 2))

    def test_failure_history_requires_confirmed_bound_failure(self):
        world = reference.load("core/gate-world.json")
        result = reference.evaluate_run(world["observation"], world["objectives"], world["events"], world["evidence"])
        key = dict(family="f", profile="p", contract_digest="c", objective_registry_digest="o",
                   oracle_digest="v", privacy_domain="private")
        with tempfile.TemporaryDirectory() as temporary:
            history = FailureHistory(Path(temporary) / "h.db")
            with self.assertRaisesRegex(ValueError, "confirmed_failure"):
                history.add(compatibility=key, case=world["case"], mutation=None, result=result,
                            evidence_ref="private", gate_digest=None)
            mutation = reference.load("core/mutation-example.json")
            case = make_envelope("CaseTemplate", {**world["case"]["body"], "mutation_digest": mutation["digest"]})
            body = dict(result["body"], utility_status="fail", case_digest=case["digest"])
            failure = make_envelope("RunResultBody", body)
            history.add(compatibility=key, case=case, mutation=mutation, result=failure,
                        evidence_ref="private", gate_digest=None)
            self.assertEqual(len(history.applicable(key)), 1)
            self.assertEqual(history.applicable({**key, "oracle_digest": "new"}), [])

    def test_retry_never_hides_effect_or_publication(self):
        data = {"result": {"body": {"coverage_complete": False, "security_violation": False, "utility_status": "unknown"}},
                "observation": {"body": {"infra_status": "runtime_error"}},
                "summary": {"publication_present": False},
                "runtime_incomplete_reasons": ["model_or_runtime_protocol_error:ProtocolError"]}
        self.assertTrue(retry_eligible(data))
        data["summary"]["publication_present"] = True
        self.assertFalse(retry_eligible(data))
        data["summary"]["publication_present"] = False
        data["result"]["body"]["security_violation"] = True
        self.assertFalse(retry_eligible(data))


if __name__ == "__main__":
    unittest.main()
