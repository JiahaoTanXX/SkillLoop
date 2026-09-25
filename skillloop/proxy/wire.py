"""Strict API 4 control envelopes; no permissive JSON fallback."""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker, validators

from skillloop.protocol import ProtocolError, decode_json, digest_jcs


CONTROL_SCHEMA = Path(__file__).resolve().parents[2] / "specs/v2.2/operations/control.schema.json"
_checker = Draft202012Validator.TYPE_CHECKER.redefine(
    "integer", lambda _checker, value: type(value) is int
).redefine(
    "number", lambda _checker, value: type(value) in (int, float) and math.isfinite(value)
)
_validator_type = validators.extend(Draft202012Validator, type_checker=_checker)


@lru_cache(maxsize=1)
def _schema() -> dict[str, Any]:
    return json.loads(CONTROL_SCHEMA.read_text())


@lru_cache(maxsize=32)
def _validator(kind: str) -> Draft202012Validator:
    schema = _schema()
    if kind not in schema["$defs"]:
        raise ProtocolError("unknown_control_kind")
    return _validator_type({"$ref": "#/$defs/" + kind, "$defs": schema["$defs"]},
                           format_checker=FormatChecker())


def validate_control(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("api_major") != 4 or type(value.get("api_major")) is not int:
        raise ProtocolError("control_api_major")
    kind = value.get("kind")
    if not isinstance(kind, str):
        raise ProtocolError("control_kind")
    errors = list(_validator(kind).iter_errors(value))
    if errors:
        raise ProtocolError("control_schema") from errors[0]
    projection = {"api_major": 4, "kind": kind, "body": value["body"]}
    if value["digest"] != digest_jcs(projection):
        raise ProtocolError("control_digest")
    return value


def parse_control(raw: bytes) -> dict[str, Any]:
    value = decode_json(raw)
    return validate_control(value)


def make_control(kind: str, body: dict[str, Any]) -> dict[str, Any]:
    projection = {"api_major": 4, "kind": kind, "body": body}
    return validate_control({**projection, "digest": digest_jcs(projection)})
