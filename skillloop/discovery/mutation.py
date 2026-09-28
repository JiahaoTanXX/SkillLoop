"""Validate a bounded notes-slot mutation before any model delivery."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Callable

from skillloop.families.registry import FamilyRegistry
from skillloop.protocol import ProtocolError, digest_bytes, make_envelope, validate_envelope


class MutationError(ProtocolError):
    pass


@dataclass(frozen=True)
class RenderedMutation:
    spec: dict
    source_digest: str
    payload_digest: str
    rendered_digest: str
    rendered_utf8: str
    rendered_token_count: int


def _text(raw: bytes, max_bytes: int, label: str) -> str:
    if type(raw) is not bytes or len(raw) > max_bytes or raw.startswith(b"\xef\xbb\xbf"):
        raise MutationError(label + "_byte_limit")
    try:
        value = raw.decode("utf-8")
    except UnicodeError as exc:
        raise MutationError(label + "_utf8") from exc
    if unicodedata.normalize("NFC", value) != value or any(
        unicodedata.category(c).startswith("C") and c not in "\r\n" for c in value
    ):
        raise MutationError(label + "_text_form")
    return value


def compile_mutation(spec: dict, *, source_bytes: bytes, profile_id: str,
                     count_tokens: Callable[[str], int],
                     registry: FamilyRegistry | None = None) -> RenderedMutation:
    validate_envelope(spec)
    if spec["kind"] != "MutationSpec":
        raise MutationError("mutation_kind")
    profile = (registry or FamilyRegistry()).profile(profile_id)
    body = spec["body"]
    limits = profile["limits"]
    if body["slot_id"] != "notes" or "notes" not in profile["input_bindings"]:
        raise MutationError("unapproved_slot")
    _text(source_bytes, limits["notes_source_bytes"], "source")
    if body["source_bytes_digest"] != digest_bytes(source_bytes):
        raise MutationError("source_digest_mismatch")
    payload = body["payload_utf8"].encode("utf-8")
    _text(payload, limits["payload_bytes"], "payload")
    if body["payload_bytes_digest"] != digest_bytes(payload):
        raise MutationError("payload_digest_mismatch")
    rendered = source_bytes + payload if body["mode"] == "append" else payload
    if body["max_rendered_bytes"] != limits["notes_rendered_bytes"]:
        raise MutationError("rendered_limit_not_profile")
    value = _text(rendered, body["max_rendered_bytes"], "rendered")
    tokens = count_tokens(value)
    if type(tokens) is not int or tokens < 0 or tokens > limits["rendered_token_budget"]:
        raise MutationError("rendered_token_limit")
    return RenderedMutation(spec, digest_bytes(source_bytes), digest_bytes(payload),
                            digest_bytes(rendered), value, tokens)


def make_dev_mutation(*, profile_id: str, source_bytes: bytes, payload_bytes: bytes,
                      mode: str = "append") -> dict:
    profile = FamilyRegistry().profile(profile_id)
    _text(payload_bytes, profile["limits"]["payload_bytes"], "payload")
    return make_envelope("MutationSpec", {"slot_id": "notes", "mode": mode,
        "payload_utf8": payload_bytes.decode("utf-8"),
        "payload_bytes_digest": digest_bytes(payload_bytes),
        "delivery": "every_read_same_rendered_bytes", "exposure_requirement": "optional",
        "max_rendered_bytes": profile["limits"]["notes_rendered_bytes"],
        "source_bytes_digest": digest_bytes(source_bytes)})


def require_distinct_variant(original: RenderedMutation, variant: RenderedMutation) -> None:
    if (original.payload_digest == variant.payload_digest or
        original.rendered_digest == variant.rendered_digest or
        original.spec["body"]["slot_id"] != variant.spec["body"]["slot_id"]):
        raise MutationError("replayed_payload_not_variant")
