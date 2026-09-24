"""Verify a DGX model snapshot against a pinned upstream file manifest.

Manifest is collected from the official Hugging Face tree API at a fixed SHA.
LFS content uses SHA-256; ordinary Git files use the Git blob SHA-1 object ID.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def file_hash(path: Path, algorithm: str, size: int) -> str:
    digest = hashlib.new(algorithm)
    if algorithm == "sha1":
        digest.update(f"blob {size}\0".encode())
    with path.open("rb") as source:
        while chunk := source.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    root = args.model_dir.resolve()
    results = []
    for name, expected in manifest["files"].items():
        path = root / name
        if path.resolve().is_relative_to(root) is False or not path.is_file():
            results.append({"path": name, "status": "missing_or_unsafe_path"})
            continue
        size = path.stat().st_size
        if size != expected["size"]:
            results.append({"path": name, "status": "size_mismatch"})
            continue
        algorithm = "sha256" if "lfs_sha256" in expected else "sha1"
        want = expected.get("lfs_sha256", expected.get("git_oid"))
        actual = file_hash(path, algorithm, size)
        results.append({"path": name, "status": "match" if actual == want else "digest_mismatch"})
    failures = [record for record in results if record["status"] != "match"]
    report = {"revision": manifest["revision"], "checked_files": len(results),
              "matched_files": len(results) - len(failures), "failures": failures}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
