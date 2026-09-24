import copy
import json
import unittest

from scripts import spec_v22_families as reference
from skillloop.families import (FamilyRegistry, build_artifact, build_value,
                                load_clean_fixture, load_example_skill,
                                parse_frontmatter, validate_artifact)
from skillloop.protocol import ProtocolError


class FamilyBuilderTests(unittest.TestCase):
    def fixture(self, profile_id, suffix):
        fixture = reference.load(f"fixtures/{profile_id}/clean-{suffix}/manifest.json")
        inputs = {slot: reference.check_record(record) for slot, record in fixture["inputs"].items()}
        expected = reference.check_record(fixture["expected"])
        return inputs, expected

    def test_registered_profiles_are_immutable_to_callers(self):
        registry = FamilyRegistry()
        profile = registry.profile("orders_total")
        profile["mapping"]["included_state"] = "cancelled"
        self.assertEqual(registry.profile("orders_total")["mapping"]["included_state"], "completed")
        with self.assertRaisesRegex(ProtocolError, "unknown_profile"):
            registry.profile("unknown")

    def test_profile_bound_tool_arguments(self):
        registry = FamilyRegistry()
        profile = registry.profile("refunds_total")
        args = {"input_bindings": profile["input_bindings"], "output_id": "artifact:report",
                "transform_id": profile["operation"], "expected_version": 0,
                "idempotency_key": "test-build"}
        self.assertEqual(registry.validate_build_args("refunds_total", args), args)
        for changed in (dict(args, transform_id="unregistered"), dict(args, unexpected=True),
                        dict(args, expected_version=1)):
            with self.assertRaisesRegex(ProtocolError, "build_args_schema"):
                registry.validate_build_args("refunds_total", changed)

    def test_six_literal_goldens_and_independent_oracle(self):
        for profile_id in ("orders_total", "refunds_total", "markdown_index"):
            for suffix in ("a", "b"):
                with self.subTest(profile_id=profile_id, suffix=suffix):
                    inputs, expected = self.fixture(profile_id, suffix)
                    actual = build_artifact(profile_id, inputs)
                    self.assertEqual(actual, expected)
                    self.assertEqual(validate_artifact(profile_id, inputs, actual)["size_bytes"], len(expected))
                    damaged = expected[:-2] + b"x\n"
                    with self.assertRaises(ProtocolError):
                        validate_artifact(profile_id, inputs, damaged)

    def test_registered_fixtures_and_three_skill_packages(self):
        for profile_id in ("orders_total", "refunds_total", "markdown_index"):
            skill = load_example_skill(profile_id)
            self.assertEqual(parse_frontmatter(skill)["profile_id"], profile_id)
            for suffix in ("a", "b"):
                self.assertEqual(load_clean_fixture(profile_id, suffix), self.fixture(profile_id, suffix))
        with self.assertRaises(ProtocolError):
            parse_frontmatter(load_example_skill("orders_total").replace(b"api_major: 4", b"api_major: 3"))

    def test_table_profiles_use_same_implementation_with_different_mapping(self):
        orders, _ = self.fixture("orders_total", "a")
        refunds, _ = self.fixture("refunds_total", "a")
        self.assertNotEqual(build_value("orders_total", orders), build_value("refunds_total", refunds))
        for profile_id, inputs in (("orders_total", orders), ("refunds_total", refunds)):
            self.assertEqual(build_value(profile_id, inputs), reference.reference(profile_id, inputs))

    def test_constructive_private_fixtures_as_independent_business_inputs(self):
        for profile_id in ("orders_total", "refunds_total", "markdown_index"):
            for first_byte in (3, 17, 59, 241):
                with self.subTest(profile_id=profile_id, first_byte=first_byte):
                    inputs, expected, _ = reference.private_fixture(profile_id, bytes([first_byte]) + bytes(31))
                    self.assertEqual(build_artifact(profile_id, inputs), expected)

    def test_csv_lexical_and_business_boundaries(self):
        inputs, _ = self.fixture("orders_total", "a")
        for raw in (b"order_id,customer_id,amount_cents,status\nr1,c1,1.0,completed\n",
                    b"order_id,customer_id,amount_cents,status\nr1,c1,01,completed\n",
                    b"order_id,customer_id,amount_cents,status\nr1,c1,1e0,completed\n",
                    b"order_id,customer_id,amount_cents,status\nr1,c1,1,completed\r\nr2,c1,2,completed\n",
                    b'order_id,customer_id,amount_cents,status\nr1,c1,"1"x,completed\n',
                    b"order_id,customer_id,amount_cents,status\nr1,unknown,1,completed\n"):
            changed = dict(inputs, records=raw)
            with self.subTest(raw=raw), self.assertRaises(ProtocolError):
                build_artifact("orders_total", changed)

    def test_table_hand_calculated_boundaries(self):
        inputs = {
            "directory": b"customer_id,customer_name\nz,Same\na,Same\n",
            "records": b"order_id,customer_id,amount_cents,status\nr1,z,0,completed\n",
            "notes": b"",
        }
        self.assertEqual(build_value("orders_total", inputs), {"customers": [
            {"customer_id": "a", "customer_name": "Same", "order_count": 0, "orders_total_cents": 0},
            {"customer_id": "z", "customer_name": "Same", "order_count": 1, "orders_total_cents": 0},
        ]})
        inputs["directory"] = b"customer_id,customer_name\n"
        inputs["records"] = b"order_id,customer_id,amount_cents,status\n"
        self.assertEqual(build_value("orders_total", inputs), {"customers": []})
        inputs["directory"] = ("customer_id,customer_name\na," + "A" * 64 + "\n").encode()
        inputs["records"] = ("order_id,customer_id,amount_cents,status\n" + "".join(
            f"r{i},a,1000000000,completed\n" for i in range(20))).encode()
        self.assertEqual(build_value("orders_total", inputs), {"customers": [{
            "customer_id": "a", "customer_name": "A" * 64,
            "order_count": 20, "orders_total_cents": 20_000_000_000,
        }]})
        with self.assertRaises(ProtocolError):
            build_artifact("orders_total", dict(inputs, records=inputs["records"] + b"r20,a,1,completed\n"))

    def test_markdown_fences_duplicates_and_unsupported_links(self):
        inputs, _ = self.fixture("markdown_index", "a")
        changed = dict(inputs, document=b"# A\n# A\n# A-2\n[x](#a-2)\n```text\n# Hidden\n```\n")
        self.assertEqual(build_value("markdown_index", changed), reference.reference("markdown_index", changed))
        for document in (b"# A\n[x](https://example.org)\n", b"# A\n[x](#missing)\n",
                         b"# A\n```\nnot closed\n", b"# A\n*unsupported*\n"):
            with self.subTest(document=document), self.assertRaises(ProtocolError):
                build_artifact("markdown_index", dict(inputs, document=document))

    def test_markdown_hundred_line_boundary(self):
        inputs, _ = self.fixture("markdown_index", "a")
        document = b"# A\n" + b"Text.\n" * 99
        self.assertEqual(build_value("markdown_index", dict(inputs, document=document)), {
            "headings": [{"anchor": "a", "level": 1, "line": 1, "text": "A"}], "links": [],
        })
        with self.assertRaises(ProtocolError):
            build_artifact("markdown_index", dict(inputs, document=document + b"Text.\n"))

    def test_named_slots_and_exact_output(self):
        inputs, expected = self.fixture("orders_total", "a")
        with self.assertRaisesRegex(ProtocolError, "input_binding_names"):
            build_artifact("orders_total", {"records": inputs["records"], "directory": inputs["directory"]})
        with self.assertRaises(ProtocolError):
            validate_artifact("orders_total", inputs, expected[:-1])


if __name__ == "__main__":
    unittest.main()
