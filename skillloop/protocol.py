"""Strict API 4 wire parsing, schema validation, and content identity.

Digest verification establishes byte-level object identity. Callers must still
authenticate the producer and resolve references from an authoritative store.
"""

from __future__ import annotations

import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

import rfc8785
from jsonschema import Draft202012Validator, FormatChecker, validators

from . import API_MAJOR

SPEC = Path(__file__).resolve().parents[1] / "specs" / "v2.2"
SAFE_INTEGER = 2**53 - 1


class ProtocolError(ValueError):
    """A wire object does not satisfy the API 4 contract."""


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise ProtocolError("duplicate_json_key")
        result[key] = value
    return result


def _integer(token: str) -> int:
    value = int(token)
    if abs(value) > SAFE_INTEGER:
        raise ProtocolError("unsafe_integer")
    return value


def _decimal(token: str) -> float:
    value = float(token)
    if not math.isfinite(value):
        raise ProtocolError("non_finite_number")
    return value


def _constant(_: str) -> None:
    raise ProtocolError("non_finite_number")


def decode_json(raw: bytes) -> Any:
    if not isinstance(raw, bytes) or raw.startswith(b"\xef\xbb\xbf"):
        raise ProtocolError("invalid_utf8_or_bom")
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_int=_integer,
            parse_float=_decimal,
            parse_constant=_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("invalid_json") from exc


def digest_bytes(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def digest_jcs(value: Any) -> str:
    try:
        return digest_bytes(rfc8785.dumps(value))
    except (TypeError, ValueError) as exc:
        raise ProtocolError("not_jcs_serializable") from exc


def canonical_json_line(value: Any) -> bytes:
    try:
        return rfc8785.dumps(value) + b"\n"
    except (TypeError, ValueError) as exc:
        raise ProtocolError("not_jcs_serializable") from exc


@lru_cache(maxsize=1)
def _schema() -> dict[str, Any]:
    return decode_json((SPEC / "protocol.schema.json").read_bytes())


_type_checker = Draft202012Validator.TYPE_CHECKER.redefine(
    "integer", lambda _checker, value: type(value) is int
).redefine(
    "number", lambda _checker, value: type(value) in (int, float) and math.isfinite(value)
)
_validator_class = validators.extend(Draft202012Validator, type_checker=_type_checker)


@lru_cache(maxsize=64)
def _validator(kind: str) -> Draft202012Validator:
    schema = _schema()
    if kind not in schema["$defs"]:
        raise ProtocolError("unknown_kind")
    selected = {"$ref": "#/$defs/" + kind, "$defs": schema["$defs"]}
    return _validator_class(selected, format_checker=FormatChecker())


def validate_envelope(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or not isinstance(value.get("kind"), str):
        raise ProtocolError("invalid_envelope")
    if type(value.get("api_major")) is not int:
        raise ProtocolError("api_major_integer_lexeme")
    errors = sorted(_validator(value["kind"]).iter_errors(value), key=lambda e: list(map(str, e.path)))
    if errors:
        error = errors[0]
        raise ProtocolError("schema:" + "/".join(map(str, error.path))) from error
    if value["api_major"] != API_MAJOR:
        raise ProtocolError("unsupported_api_major")
    expected = digest_jcs({"api_major": API_MAJOR, "kind": value["kind"], "body": value["body"]})
    if value["digest"] != expected:
        raise ProtocolError("digest_mismatch")
    return value


def parse_envelope(raw: bytes) -> dict[str, Any]:
    return validate_envelope(decode_json(raw))


def make_envelope(kind: str, body: dict[str, Any]) -> dict[str, Any]:
    projection = {"api_major": API_MAJOR, "kind": kind, "body": body}
    return validate_envelope({**projection, "digest": digest_jcs(projection)})


def gate_verdict(*, failure_reasons: list[str], contract_approved: bool,
                 incomplete_reasons: list[str]) -> str:
    """The fixed precedence; full Gate still requires authoritative manifests."""
    if failure_reasons:
        return "fail"
    if not contract_approved:
        return "needs_contract"
    if incomplete_reasons:
        return "inconclusive"
    return "pass"
