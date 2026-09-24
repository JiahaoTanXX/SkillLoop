"""M2 independent reference oracle adapter.

The separate V2.2 reference implementation is used only to cross-check the
builder until the trusted oracle service and isolation arrive in M3/M4.
"""

from __future__ import annotations

from typing import Any

from scripts import spec_v22_families as reference

from skillloop.protocol import ProtocolError


def validate_artifact(profile_id: str, inputs: dict[str, bytes], stored_bytes: bytes) -> dict[str, Any]:
    try:
        return reference.validate_output(profile_id, inputs, stored_bytes)
    except ValueError as exc:
        raise ProtocolError(str(exc)) from exc
