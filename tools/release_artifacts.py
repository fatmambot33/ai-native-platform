"""Generate deterministic checksums, SPDX SBOM, and provenance inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import tomli as tomllib


def sha256(path: Path) -> str:
    """Return a file SHA-256 digest."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_metadata(root: Path, dist: Path) -> dict[str, Path]:
    """Create deterministic release metadata for files in *dist*."""
    files = sorted(
        path
        for path in dist.iterdir()
        if path.is_file()
        and path.name not in {"SHA256SUMS", "sbom.spdx.json", "provenance.json"}
    )
    if not files:
        raise ValueError(f"No release artifacts found in {dist}")

    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]
    version = str(project["version"])
    name = str(project["name"])
    checksums = {path.name: sha256(path) for path in files}

    checksum_path = dist / "SHA256SUMS"
    checksum_path.write_text(
        "".join(f"{digest}  {filename}\n" for filename, digest in checksums.items()),
        encoding="utf-8",
    )

    namespace_seed = hashlib.sha256(f"{name}:{version}".encode()).hexdigest()
    sbom: dict[str, Any] = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"{name}-{version}",
        "documentNamespace": (
            f"https://github.com/fatmambot33/ai-native-platform/"
            f"spdx/{version}/{namespace_seed}"
        ),
        "creationInfo": {
            "created": "1970-01-01T00:00:00Z",
            "creators": ["Tool: ai-native-platform-release-metadata"],
        },
        "packages": [
            {
                "name": name,
                "SPDXID": "SPDXRef-Package",
                "versionInfo": version,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": True,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": str(project.get("license", "NOASSERTION")),
            }
        ],
        "files": [
            {
                "fileName": filename,
                "SPDXID": f"SPDXRef-File-{index}",
                "checksums": [{"algorithm": "SHA256", "checksumValue": digest}],
                "licenseConcluded": "NOASSERTION",
            }
            for index, (filename, digest) in enumerate(checksums.items(), start=1)
        ],
        "relationships": [
            {
                "spdxElementId": "SPDXRef-Package",
                "relationshipType": "CONTAINS",
                "relatedSpdxElement": f"SPDXRef-File-{index}",
            }
            for index in range(1, len(checksums) + 1)
        ],
    }
    sbom_path = dist / "sbom.spdx.json"
    sbom_path.write_text(json.dumps(sbom, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    provenance = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [
            {"name": filename, "digest": {"sha256": digest}}
            for filename, digest in checksums.items()
        ],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": (
                    "https://github.com/fatmambot33/ai-native-platform/"
                    "blob/v0.1.0/.github/workflows/release.yml"
                ),
                "externalParameters": {"version": version},
                "internalParameters": {},
                "resolvedDependencies": [],
            },
            "runDetails": {
                "builder": {
                    "id": "https://github.com/fatmambot33/ai-native-platform/actions"
                },
                "metadata": {
                    "invocationId": "local-dry-run",
                    "startedOn": datetime.now(timezone.utc).isoformat(),
                },
            },
        },
    }
    provenance_path = dist / "provenance.json"
    provenance_path.write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "checksums": checksum_path,
        "sbom": sbom_path,
        "provenance": provenance_path,
    }


def main() -> int:
    """Generate release metadata."""
    parser = argparse.ArgumentParser()
    parser.add_argument("dist", nargs="?", default="dist")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    outputs = build_metadata(Path(args.root).resolve(), Path(args.dist).resolve())
    for label, path in outputs.items():
        print(f"{label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
