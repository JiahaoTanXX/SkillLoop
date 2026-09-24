"""Verify immutable M2 fixtures and the three registered example Skills."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from skillloop.protocol import ProtocolError, decode_json, digest_bytes

from .registry import FAMILY_SPEC, PROFILE_IDS

_FRONTMATTER_LINE = re.compile(r"([a-z_]+): ([^\n]+)\Z")
_FRONTMATTER_KEYS = {"name", "description", "api_major", "family_id", "profile_id"}


def parse_frontmatter(raw: bytes) -> dict[str, str]:
    if type(raw) is not bytes or len(raw) > 4096:
        raise ProtocolError("skill_byte_limit")
    try:
        text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise ProtocolError("skill_utf8") from exc
    if (text.startswith("\ufeff") or "\r" in text or not text.startswith("---\n")
            or not text.endswith("\n") or unicodedata.normalize("NFC", text) != text):
        raise ProtocolError("skill_encoding")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ProtocolError("frontmatter_missing_end")
    fields: dict[str, str] = {}
    for line in text[4:end].split("\n"):
        match = _FRONTMATTER_LINE.fullmatch(line)
        if match is None or match.group(1) in fields:
            raise ProtocolError("frontmatter_syntax_or_duplicate")
        fields[match.group(1)] = match.group(2)
    if set(fields) != _FRONTMATTER_KEYS or fields["api_major"] != "4":
        raise ProtocolError("frontmatter_identity")
    return fields


def _registered_bytes(root: Path, record: dict) -> bytes:
    path = record["path"]
    if not isinstance(path, str) or Path(path).is_absolute() or ".." in Path(path).parts:
        raise ProtocolError("fixture_path")
    full = root / path
    raw = full.read_bytes()
    if len(raw) != record["size_bytes"] or digest_bytes(raw) != record["bytes_digest"]:
        raise ProtocolError("fixture_bytes_mismatch")
    return raw


def load_clean_fixture(profile_id: str, suffix: str, root: Path = FAMILY_SPEC) -> tuple[dict[str, bytes], bytes]:
    if profile_id not in PROFILE_IDS or suffix not in {"a", "b"}:
        raise ProtocolError("unknown_fixture")
    manifest = decode_json((root / "fixtures" / profile_id / f"clean-{suffix}" / "manifest.json").read_bytes())
    if manifest["profile_id"] != profile_id:
        raise ProtocolError("fixture_profile")
    return ({slot: _registered_bytes(root, record) for slot, record in manifest["inputs"].items()},
            _registered_bytes(root, manifest["expected"]))


def load_example_skill(profile_id: str, root: Path = FAMILY_SPEC) -> bytes:
    if profile_id not in PROFILE_IDS:
        raise ProtocolError("unknown_profile")
    skill_id = profile_id.replace("_", "-")
    manifest = decode_json((root / "skills" / skill_id / "manifest.json").read_bytes())
    if (manifest["skill_id"] != skill_id or manifest["entrypoint"] != "SKILL.md"
            or manifest["dependencies"] or manifest["reference_files"] or len(manifest["files"]) != 1):
        raise ProtocolError("skill_package")
    raw = _registered_bytes(root, manifest["files"][0])
    fields = parse_frontmatter(raw)
    if fields["name"] != skill_id or fields["profile_id"] != profile_id or fields["family_id"] != manifest["family_id"]:
        raise ProtocolError("skill_identity")
    return raw
