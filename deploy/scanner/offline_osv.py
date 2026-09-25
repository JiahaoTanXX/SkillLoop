"""Bounded, air-gapped OSV provider for the pinned SkillSpector SC4 analyzer.

The upstream 2.11.2 scanner queries api.osv.dev.  This adapter uses the
official OSV-Scanner 2.6.0 binary and the pinned PyPI/npm data dumps instead.
Its limitations flow into SkillSpector's existing inspection ledger.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from skillspector.inspection_ledger import LedgerReason
from skillspector.nodes.analyzers import osv_client
from skillspector.nodes.analyzers import static_patterns_supply_chain as supply_chain


DATA_ROOT = Path(os.environ.get("SKILLLOOP_OSV_DATA_ROOT", "/osv-data"))
OSV_BINARY = Path(os.environ.get("SKILLLOOP_OSV_BINARY", "/usr/local/bin/osv-scanner"))
LOCK_PATH = Path(__file__).with_name("offline-osv-lock.json")
PYPI_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,255}\Z")
NPM_NAME = re.compile(r"(?:@[A-Za-z0-9._-]+/)?[A-Za-z0-9._-]{1,256}\Z")
VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+!~-]{0,127}\Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_inputs() -> None:
    """Fail before scanning if any offline intelligence or engine byte changed."""
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    for item in lock["files"]:
        path = OSV_BINARY if item["name"] == "osv-scanner" else DATA_ROOT / item["path"]
        if not path.is_file() or path.stat().st_size != item["bytes"]:
            raise RuntimeError(f"offline OSV input unavailable: {item['name']}")
        if _sha256(path) != item["sha256"]:
            raise RuntimeError(f"offline OSV input digest mismatch: {item['name']}")


def _limit(reason: LedgerReason, **kwargs: object) -> osv_client.OsvQueryLimitation:
    return osv_client.OsvQueryLimitation(reason=reason, **kwargs)


def _coordinate_key(name: str, version: str, ecosystem: str) -> tuple[str, str]:
    normalized = name.lower() if ecosystem == "npm" else name.lower().replace("_", "-")
    return (normalized, version)


def _write_lockfile(path: Path, ecosystem: str, packages: list[tuple[str, str]]) -> None:
    if ecosystem == "PyPI":
        path.write_text("".join(f"{name}=={version}\n" for name, version in packages), encoding="utf-8")
    else:
        entries = {"": {"name": "skillloop-osv-query", "version": "0.0.0"}}
        entries.update({f"node_modules/{name}": {"version": version} for name, version in packages})
        path.write_text(
            json.dumps({"name": "skillloop-osv-query", "version": "0.0.0", "lockfileVersion": 3,
                        "packages": entries}, separators=(",", ":")), encoding="utf-8"
        )


def query_batch(
    packages: list[tuple[str, str | None]], ecosystem: str, *,
    timeout_seconds: float | None = None, budget: osv_client.OsvQueryBudget | None = None,
) -> osv_client.QueryBatchResults:
    """Return findings aligned to inputs; never present omitted work as complete."""
    active = budget or osv_client.OsvQueryBudget.create(timeout_seconds)
    limitations: list[osv_client.OsvQueryLimitation] = []
    retained = packages[:max(0, active.max_packages - active.packages_seen)]
    if len(retained) != len(packages):
        limitations.append(_limit(LedgerReason.OUTPUT_LIMIT, observed_records=len(packages),
                                  limit_records=active.max_packages - active.packages_seen))
    active.packages_seen += len(retained)
    values: list[list[osv_client.VulnResult]] = [[] for _ in retained]
    if not retained:
        return osv_client.QueryBatchResults(values, limitations=tuple(limitations))
    if ecosystem not in ("PyPI", "npm"):
        limitations.append(_limit(LedgerReason.OPAQUE_CONTENT, error_class="UnsupportedEcosystem"))
        osv_client._last_query_ok = False
        return osv_client.QueryBatchResults(values, limitations=tuple(limitations))

    valid: list[tuple[int, str, str]] = []
    name_pattern = PYPI_NAME if ecosystem == "PyPI" else NPM_NAME
    for index, (name, version) in enumerate(retained):
        if not isinstance(name, str) or not isinstance(version, str) or not name_pattern.fullmatch(name) or not VERSION.fullmatch(version):
            limitations.append(_limit(LedgerReason.OPAQUE_CONTENT, error_class="UnpinnedOrInvalidCoordinate"))
            continue
        valid.append((index, name, version))
    if not valid:
        osv_client._last_query_ok = False
        return osv_client.QueryBatchResults(values, limitations=tuple(limitations))

    if active.batches_sent >= active.max_batches or len(valid) > active.max_queries_per_batch:
        limitations.append(_limit(LedgerReason.OUTPUT_LIMIT, observed_records=len(valid),
                                  limit_records=active.max_queries_per_batch))
        osv_client._last_query_ok = False
        return osv_client.QueryBatchResults(values, limitations=tuple(limitations))
    remaining = active.remaining_seconds()
    if remaining <= 0:
        limitations.append(_limit(LedgerReason.RUNTIME_LIMIT, limit_seconds=active.limit_seconds))
        osv_client._last_query_ok = False
        return osv_client.QueryBatchResults(values, limitations=tuple(limitations))

    active.batches_sent += 1
    try:
        with tempfile.TemporaryDirectory(prefix="skillloop-osv-") as temporary:
            work = Path(temporary)
            lockfile = work / ("requirements.txt" if ecosystem == "PyPI" else "package-lock.json")
            output = work / "osv-result.json"
            _write_lockfile(lockfile, ecosystem, [(name, version) for _, name, version in valid])
            process = subprocess.run(
                [str(OSV_BINARY), "scan", "source", "--offline", "--lockfile", str(lockfile),
                 "--format", "json", "--all-packages", "--verbosity", "error",
                 "--output-file", str(output)],
                cwd=work, env={**os.environ, "OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY": str(DATA_ROOT)},
                capture_output=True, timeout=remaining, check=False,
            )
            if process.returncode not in (0, 1) or not output.is_file():
                raise RuntimeError("OfflineScannerFailed")
            if output.stat().st_size > active.max_response_bytes - active.response_bytes:
                limitations.append(_limit(LedgerReason.OUTPUT_LIMIT,
                                          observed_bytes=output.stat().st_size,
                                          limit_bytes=active.max_response_bytes - active.response_bytes))
                raise RuntimeError("OfflineScannerOutputLimit")
            active.response_bytes += output.stat().st_size
            payload = json.loads(output.read_text(encoding="utf-8"))
    except subprocess.TimeoutExpired:
        limitations.append(_limit(LedgerReason.RUNTIME_LIMIT, limit_seconds=active.limit_seconds,
                                  error_class="OfflineScannerTimeout"))
        osv_client._last_query_ok = False
        return osv_client.QueryBatchResults(values, limitations=tuple(limitations))
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        if not limitations:
            limitations.append(_limit(LedgerReason.ANALYZER_RUNTIME_ERROR,
                                      error_class=type(error).__name__))
        osv_client._last_query_ok = False
        return osv_client.QueryBatchResults(values, limitations=tuple(limitations))

    keyed: dict[tuple[str, str], list[osv_client.VulnResult]] = {}
    for result in payload.get("results", []):
        for item in result.get("packages", []):
            coordinate = item.get("package", {})
            name, version = coordinate.get("name"), coordinate.get("version")
            if not isinstance(name, str) or not isinstance(version, str):
                limitations.append(_limit(LedgerReason.OPAQUE_CONTENT, error_class="InvalidScannerPackage"))
                continue
            raw = item.get("vulnerabilities", [])
            if not isinstance(raw, list):
                limitations.append(_limit(LedgerReason.OPAQUE_CONTENT, error_class="InvalidScannerVulnerabilities"))
                continue
            if len(raw) > osv_client.MAX_OSV_VULNS_PER_PACKAGE:
                limitations.append(_limit(LedgerReason.OUTPUT_LIMIT, observed_records=len(raw),
                                          limit_records=osv_client.MAX_OSV_VULNS_PER_PACKAGE))
            if any(not isinstance(v, dict) for v in raw):
                limitations.append(_limit(LedgerReason.OPAQUE_CONTENT, error_class="InvalidScannerAdvisory"))
            keyed[_coordinate_key(name, version, ecosystem)] = [
                osv_client._parse_vuln(v) for v in raw[:osv_client.MAX_OSV_VULNS_PER_PACKAGE] if isinstance(v, dict)
            ]
    for index, name, version in valid:
        key = _coordinate_key(name, version, ecosystem)
        if key not in keyed:
            limitations.append(_limit(LedgerReason.ANALYZER_RUNTIME_ERROR,
                                      error_class="MissingScannerPackage"))
        else:
            available = max(0, active.max_results - active.results_retained)
            if len(keyed[key]) > available:
                limitations.append(_limit(LedgerReason.OUTPUT_LIMIT,
                                          observed_records=active.results_retained + len(keyed[key]),
                                          limit_records=active.max_results))
            values[index] = keyed[key][:available]
            active.results_retained += len(values[index])
    osv_client._last_query_ok = not limitations
    return osv_client.QueryBatchResults(values, limitations=tuple(limitations[:osv_client.MAX_OSV_LIMITATIONS]))


def main() -> None:
    try:
        verify_inputs()
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print(f"offline OSV preflight failed: {error}", file=sys.stderr)
        raise SystemExit(78) from error
    osv_client.query_batch = query_batch
    supply_chain.query_batch = query_batch
    supply_chain.was_osv_reachable = lambda: osv_client._last_query_ok
    # The upstream static fallback has no version-complete database.  Keep it
    # only for degraded scans, whose ledger carries the offline lookup failure.
    original_fallback = supply_chain._sc4_from_fallback
    supply_chain._sc4_from_fallback = lambda *args, **kwargs: (
        [] if osv_client._last_query_ok else original_fallback(*args, **kwargs)
    )
    from skillspector.cli import app
    app()


if __name__ == "__main__":
    main()
