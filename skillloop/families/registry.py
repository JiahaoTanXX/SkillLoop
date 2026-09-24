"""Load only approved V2.2 profile bytes from the versioned registry."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from skillloop.protocol import ProtocolError, decode_json, digest_bytes

FAMILY_SPEC = Path(__file__).resolve().parents[2] / "specs" / "v2.2" / "families"
PROFILE_IDS = frozenset({"orders_total", "refunds_total", "markdown_index"})


class FamilyRegistry:
    def __init__(self, root: Path = FAMILY_SPEC):
        registry = decode_json((root / "registry.json").read_bytes())
        if registry.get("api_major") != 4 or registry.get("family_ids") != ["markdown-index", "table-report"]:
            raise ProtocolError("family_registry_version")
        profiles: dict[str, dict[str, Any]] = {}
        for record in registry["profiles"]:
            path = record["path"]
            if path not in {f"profiles/{name}.json" for name in PROFILE_IDS}:
                raise ProtocolError("unregistered_profile_path")
            raw = (root / path).read_bytes()
            if len(raw) != record["size_bytes"] or digest_bytes(raw) != record["bytes_digest"]:
                raise ProtocolError("profile_bytes_mismatch")
            profile = decode_json(raw)
            profile_id = profile["profile_id"]
            if profile_id in profiles or path != f"profiles/{profile_id}.json" or profile["api_major"] != 4:
                raise ProtocolError("profile_identity")
            profiles[profile_id] = profile
        if set(profiles) != PROFILE_IDS:
            raise ProtocolError("missing_profile")
        if profiles["orders_total"]["operation"] != profiles["refunds_total"]["operation"] != "group_sum_join":
            raise ProtocolError("table_operation_mismatch")
        if profiles["markdown_index"]["operation"] != "local_heading_link_index":
            raise ProtocolError("markdown_operation_mismatch")
        self._profiles = profiles
        self._build_schemas = decode_json((root / "tool-args.schema.json").read_bytes())["$defs"]
        if set(self._build_schemas) != PROFILE_IDS:
            raise ProtocolError("tool_schema_profiles")

    def profile(self, profile_id: str) -> dict[str, Any]:
        try:
            return deepcopy(self._profiles[profile_id])
        except KeyError as exc:
            raise ProtocolError("unknown_profile") from exc

    def validate_build_args(self, profile_id: str, args: dict[str, Any]) -> dict[str, Any]:
        self.profile(profile_id)
        errors = list(Draft202012Validator(self._build_schemas[profile_id]).iter_errors(args))
        if errors:
            raise ProtocolError("build_args_schema") from errors[0]
        return args
