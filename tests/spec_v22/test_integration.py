"""Cross-module specification contracts, using the published family fixtures."""
import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import spec_v22_core as core
import spec_v22_families as families


def record(kind, body):
    return core.reseal({"api_major": 4, "kind": kind, "body": body})


def digest_file(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


class IntegrationSpec(unittest.TestCase):
    def test_unknown_required_security_observation_cannot_pass(self):
        world = core.load("core/gate-world.json")
        objective = next(item for item in world["objectives"] if item["body"]["prohibited"])
        event = copy.deepcopy(world["events"][0])
        definition = objective["body"]
        event["body"].update(event_id="integration-unknown-effect", sequence=999,
                             event_type="effect", objective_id=definition["objective_id"],
                             channel=definition["allowed_channels"][0], outcome="unknown",
                             recipient_scope="public",
                             observer_role=definition["observer_role"],
                             predicate_version=str(definition["version"]))
        event = core.reseal(event)
        world["events"].append(event)
        world["evidence"]["body"]["event_digests"].append(event["digest"])
        world["evidence"] = core.reseal(world["evidence"])
        result = core.evaluate_run(world["observation"], world["objectives"],
                                   world["events"], world["evidence"])
        self.assertFalse(result["body"]["coverage_complete"])
        self.assertFalse(result["body"]["security_violation"])

    def test_all_published_dev_cases_use_core_case_contract(self):
        suite = families.load("dev-suite.json")
        templates = {}
        # Clean identities must be established before attacks bind their controls.
        cases = sorted(suite["cases"], key=lambda item: item["kind"] != "clean")
        for case in cases:
            fixture_path = families.SPEC / case["fixture"]
            expected_path = fixture_path.parent / "expected.json"
            mutation_digest = (core.canonical_digest(case["mutation"])
                               if case["mutation"] is not None else None)
            body = {"case_id": case["case_id"], "case_kind": case["kind"],
                    "split": case["split"], "fixture_digest": digest_file(fixture_path),
                    "business_projection_digest": digest_file(expected_path),
                    "mutation_digest": mutation_digest,
                    "clean_pair_digest": (templates[case["clean_pair_id"]]["digest"]
                                          if case["clean_pair_id"] else None),
                    "objective_ids": case["objective_ids"],
                    "repetitions": case["repetitions"]}
            template = record("CaseTemplate", body)
            core.validate_record(template)
            templates[case["case_id"]] = template
        self.assertEqual(len(templates), 15)
        for profile_id in ("orders_total", "refunds_total", "markdown_index"):
            applicable = [case for case in cases if case["profile_id"] == profile_id]
            self.assertEqual(sum(case["repetitions"] for case in applicable), 15)
            self.assertEqual(sum(case["kind"] == "attack" for case in applicable), 3)

    def test_both_families_share_named_tool_binding_contract(self):
        for profile_id in ("orders_total", "refunds_total", "markdown_index"):
            profile = families.profile(profile_id)
            call = record("ToolCall", {
                "call_id": "integration-call", "run_id": "integration-run",
                "task_instance_id": "integration-task", "fencing_token": 1,
                "tool": "build_artifact",
                "args": {"input_bindings": profile["input_bindings"],
                         "output_id": "artifact:report", "transform_id": profile["operation"],
                         "expected_version": 0, "idempotency_key": "integration-key"}})
            core.validate_record(call)
            bad = copy.deepcopy(call)
            bad["body"]["args"]["input_bindings"] = list(profile["input_bindings"].values())
            with self.assertRaises(ValueError):
                core.validate_record(core.reseal(bad))

    def test_confirmed_user_choices_match_registered_families(self):
        decisions = json.loads((ROOT / "specs/v2.2/user-decisions.json").read_text())
        registry = families.load("registry.json")
        self.assertEqual(set(decisions["first_release"]["task_families"]), set(registry["family_ids"]))
        self.assertTrue(decisions["first_release"]["cross_family_required"])
        self.assertFalse(decisions["model"]["backend_fixed_by_user"])
        self.assertEqual(decisions["model"]["required_repository"], "Qwen/Qwen3.8-27B-FP8")
        self.assertFalse(decisions["model"]["actual_deployment_verified"])
        self.assertEqual(decisions["workflow"], {"developer_count": 1, "calendar_schedule": False})


if __name__ == "__main__":
    unittest.main()
