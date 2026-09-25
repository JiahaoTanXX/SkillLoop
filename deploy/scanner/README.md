# SkillSpector ARM64 M1 image

This image packages the pinned SkillSpector source for DGX Spark smoke tests. It is not a ready production scanner until its offline intelligence and coverage profile are approved.

| Input | Pinned identity |
| --- | --- |
| Base image | `public.ecr.aws/docker/library/python@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9` (`linux/arm64`, Python 3.12.14) |
| SkillSpector source commit | `dabf4759a189be0f0428a2f7a472b3d5bdad1fe6` (v2.11.2) |
| Source `uv.lock` SHA-256 | `5de3b0c121a34472026462c9fad368019accbe094ba4693198364c105e5ea93c` |
| Exported `scanner-deps-hashed.txt` SHA-256 | `1786cdbe3b2a9bd5de91e5493c5cb17278e14de9b5373cff8b57fdebac0432f0` |
| Built `skillspector-2.11.2-py3-none-any.whl` SHA-256 | `4e046af9b21218c650f463d22896e4b5cc3326178a3b13fbc3cb8c4031bac70a` |
| DGX local image ID | `sha256:905f66cb3253c884385232984a5535367b896fd5192abe0ee10239ec5fa2c093` |

Build context contains only the exported hashed dependency list, the pinned wheel, and this Dockerfile. Verify both input file hashes before building. On DGX, the dependency list was exported from the fixed `uv.lock`; the wheel was built from the fixed source commit with `python3 -m pip wheel --no-deps --index-url https://pypi.tuna.tsinghua.edu.cn/simple`. The Dockerfile uses a reachable domestic Python package mirror, verifies dependency wheel hashes, and installs the SkillSpector wheel without resolving extra dependencies.

```sh
sha256sum scanner-deps-hashed.txt skillspector-2.11.2-py3-none-any.whl
docker build --pull=false --network=host -t skillloop/skillspector:m1 .
docker image inspect skillloop/skillspector:m1 --format '{{.Id}} {{.Os}}/{{.Architecture}}'
```

Run with no network, a read-only root filesystem, and only the input Skill mounted read-only. Use a separate writable report directory and a temporary filesystem for runtime scratch space. The first M1 container smokes are recorded in [the platform report](../../docs/dgx-m1-access-report.zh-CN.md). The local image ID is a measured build result; a production deployment needs an immutable registry or transferred OCI archive identity, an approved offline intelligence source, and a full coverage check.

## M1 offline OSV candidate

`Dockerfile.offline` adds the official OSV-Scanner 2.6.0 Linux ARM64 binary and `offline_osv.py` to the same pinned SkillSpector wheel and dependency export. The official OSV PyPI and npm `all.zip` snapshots are **runtime inputs**, not repository files or Docker build context. Their byte counts and SHA-256 values, along with the engine binary, are pinned in `offline-osv-lock.json`. The snapshot date is 2026-09-24 UTC; refreshing either snapshot requires a new lock and acceptance run.

Download on a networked local machine from the [official OSV data dumps](https://google.github.io/osv.dev/data/) and the [official OSV-Scanner v2.6.0 release](https://github.com/google/osv-scanner/releases/tag/v2.6.0). Copy the two ZIP files and Linux ARM64 executable to the assigned DGX account, verify SHA-256 and byte counts against `offline-osv-lock.json`, then place the ZIP files at these exact container paths:

```text
/osv-data/osv-scalibr/PyPI/all.zip
/osv-data/osv-scalibr/npm/all.zip
```

The container receives `/osv-data` and the Skill input read-only, plus a private tmpfs for bounded scratch files. Build from the existing pinned wheel/dependency context plus `Dockerfile.offline`, `offline_osv.py`, `offline-osv-lock.json`, and the verified `osv-scanner-linux-arm64` binary. The entrypoint verifies the engine and both data archives before scanning. It replaces the upstream SC4 HTTP lookup with `osv-scanner scan source --offline` against only those local archives. Unpinned or unsupported coordinates, missing archives, scanner errors, timeouts, and output limits must produce a coverage gap or fail preflight. This candidate requires DGX container smoke tests and a portable OCI archive digest before M1 deployment readiness can pass.
