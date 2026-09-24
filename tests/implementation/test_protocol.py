import copy
import json
import unittest

from skillloop.protocol import (
    ProtocolError, SPEC, canonical_json_line, decode_json, digest_jcs,
    gate_verdict, make_envelope, parse_envelope, validate_envelope,
)


class ProtocolTests(unittest.TestCase):
    def test_all_reference_record_shapes(self):
        records = json.loads((SPEC / "core/valid-records.json").read_text())
        self.assertEqual({x["kind"] for x in records}, set(json.loads((SPEC / "protocol.schema.json").read_text())["$defs"]))
        for record in records:
            with self.subTest(kind=record["kind"]):
                self.assertEqual(validate_envelope(record), record)
                self.assertEqual(parse_envelope(canonical_json_line(record)), record)

    def test_all_hash_goldens(self):
        for golden in json.loads((SPEC / "core/hash-goldens.json").read_text()):
            with self.subTest(kind=golden["kind"]):
                self.assertEqual(digest_jcs(golden["projection"]), golden["digest"])

    def test_rejects_duplicate_key_bom_nonfinite_and_unsafe_integer(self):
        for raw in (b'{"a":1,"a":2}', b'\xef\xbb\xbf{}', b'{"a":NaN}',
                    b'{"a":Infinity}', b'{"a":9007199254740992}'):
            with self.subTest(raw=raw), self.assertRaises(ProtocolError):
                decode_json(raw)

    def test_integer_lexeme_and_unknown_field(self):
        value = json.loads((SPEC / "core/valid-records.json").read_text())[0]
        wrong = copy.deepcopy(value)
        wrong["api_major"] = 4.0
        with self.assertRaises(ProtocolError):
            validate_envelope(wrong)
        wrong = copy.deepcopy(value)
        wrong["unexpected"] = True
        with self.assertRaises(ProtocolError):
            validate_envelope(wrong)

    def test_digest_tampering_and_envelope_creation(self):
        value = json.loads((SPEC / "core/valid-records.json").read_text())[0]
        self.assertEqual(make_envelope(value["kind"], value["body"]), value)
        wrong = copy.deepcopy(value)
        wrong["body"]["objective_id"] = "changed"
        with self.assertRaisesRegex(ProtocolError, "digest_mismatch"):
            validate_envelope(wrong)

    def test_gate_precedence(self):
        self.assertEqual(gate_verdict(failure_reasons=["effect"], contract_approved=False,
                                      incomplete_reasons=["missing"]), "fail")
        self.assertEqual(gate_verdict(failure_reasons=[], contract_approved=False,
                                      incomplete_reasons=["missing"]), "needs_contract")
        self.assertEqual(gate_verdict(failure_reasons=[], contract_approved=True,
                                      incomplete_reasons=["missing"]), "inconclusive")
        self.assertEqual(gate_verdict(failure_reasons=[], contract_approved=True,
                                      incomplete_reasons=[]), "pass")


if __name__ == "__main__":
    unittest.main()
