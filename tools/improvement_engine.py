"""Evidence-driven, bounded self-improvement discovery."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import tomllib
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_native import validate_manifest  # noqa: E402
from validator.validate_standard import validate_standard  # noqa: E402

SECRET_PATTERN = re.compile(
    r"(?i)\b(token|secret|password|api[_-]?key)\b\s*[:=]\s*([^\s,;]+)"
)
PROFILES = ("library", "cli", "service", "agent-tool", "plugin", "full-platform")


@dataclass(frozen=True)
class ImprovementFinding:
    """One actionable repository-improvement finding."""

    code: str
    title: str
    body: str
    path: str | None
    severity: str
    fingerprint: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return asdict(self)


def sanitize(text: str) -> str:
    """Redact common secret assignments from untrusted signals."""
    return SECRET_PATTERN.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)


def fingerprint(code: str, title: str, path: str | None) -> str:
    """Return a stable identity for one root cause."""
    material = "\0".join((code, title, path or ""))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]


def make_finding(
    code: str,
    title: str,
    body: str,
    path: str | None = None,
    severity: str = "medium",
) -> ImprovementFinding:
    """Create a sanitized finding with a stable fingerprint."""
    clean_title = sanitize(title).strip()[:160]
    clean_body = sanitize(body).strip()[:4000]
    return ImprovementFinding(
        code=code,
        title=clean_title,
        body=clean_body,
        path=path,
        severity=severity,
        fingerprint=fingerprint(code, clean_title, path),
    )


def _release_alignment_findings(root: Path) -> list[ImprovementFinding]:
    """Detect version and release-document drift."""
    findings: list[ImprovementFinding] = []
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    package_version = str(pyproject["project"]["version"])
    standard = yaml.safe_load(
        (root / "standard/AI_NATIVE_PLATFORM.yaml").read_text(encoding="utf-8")
    )
    release_version = str(standard["standard"]["current_release"])
    template = yaml.safe_load(
        (root / "templates/AI_NATIVE_PLATFORM.yaml").read_text(encoding="utf-8")
    )
    template_ref = str(template["standard"]["ref"])
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")

    if package_version != release_version:
        findings.append(
            make_finding(
                "release.version_drift",
                "Align package and standard release versions",
                f"pyproject version {package_version} differs from "
                f"standard release {release_version}.",
                "pyproject.toml",
                "high",
            )
        )
    if template_ref != f"v{release_version}":
        findings.append(
            make_finding(
                "release.template_ref_drift",
                "Align starter manifest with the current release",
                f"Starter ref {template_ref!r} must equal v{release_version}.",
                "templates/AI_NATIVE_PLATFORM.yaml",
                "high",
            )
        )
    if f"## [{release_version}]" not in changelog:
        findings.append(
            make_finding(
                "release.changelog_missing",
                "Document the current release in the changelog",
                f"CHANGELOG.md has no section for {release_version}.",
                "CHANGELOG.md",
                "medium",
            )
        )
    return findings


def _fixture_findings(root: Path) -> list[ImprovementFinding]:
    """Validate every passing and failing profile fixture."""
    findings: list[ImprovementFinding] = []
    fixture_root = root / "fixtures"
    for profile in PROFILES:
        passing = fixture_root / "passing" / f"{profile}.yaml"
        failing = fixture_root / "failing" / f"{profile}.yaml"
        if not passing.is_file() or not failing.is_file():
            findings.append(
                make_finding(
                    "fixtures.profile_missing",
                    f"Add complete fixtures for {profile}",
                    "Each profile requires one passing and one focused failing fixture.",
                    f"fixtures/{profile}",
                    "high",
                )
            )
            continue
        _, passing_findings = validate_manifest(passing, fixture_root)
        _, failing_findings = validate_manifest(failing, fixture_root)
        if passing_findings:
            findings.append(
                make_finding(
                    "fixtures.passing_invalid",
                    f"Repair the passing {profile} fixture",
                    "\n".join(item.render() for item in passing_findings),
                    str(passing.relative_to(root)),
                    "high",
                )
            )
        if not failing_findings:
            findings.append(
                make_finding(
                    "fixtures.failing_passed",
                    f"Make the failing {profile} fixture exercise a real gap",
                    "The focused failing fixture unexpectedly passes.",
                    str(failing.relative_to(root)),
                    "medium",
                )
            )
    return findings


def _external_signal_findings(root: Path) -> list[ImprovementFinding]:
    """Ingest normalized CI, dependency, docs, schema, evaluation, and release signals."""
    path = root / ".ai-native" / "signals.json"
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(".ai-native/signals.json must contain a list")

    findings: list[ImprovementFinding] = []
    allowed_kinds = {"ci", "dependency", "documentation", "schema", "evaluation", "release"}
    for item in payload:
        if not isinstance(item, dict):
            continue
        if item.get("status") in {"resolved", "deferred", "obsolete"}:
            continue
        kind = str(item.get("kind", ""))
        if kind not in allowed_kinds:
            continue
        code = str(item.get("code") or f"signal.{kind}")
        findings.append(
            make_finding(
                code,
                str(item.get("title") or f"Resolve {kind} drift"),
                str(item.get("body") or "Repository evidence reports an unresolved gap."),
                str(item["path"]) if item.get("path") else None,
                str(item.get("severity") or "medium"),
            )
        )
    return findings


def _suppressed(root: Path) -> tuple[set[str], set[str]]:
    """Load active fingerprint and code suppressions."""
    path = root / ".ai-native" / "suppressions.yaml"
    if not path.is_file():
        return set(), set()
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = payload.get("suppressions", []) if isinstance(payload, dict) else []
    fingerprints: set[str] = set()
    codes: set[str] = set()
    today = date.today().isoformat()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        expires = entry.get("expires")
        if expires and str(expires) < today:
            continue
        if entry.get("fingerprint"):
            fingerprints.add(str(entry["fingerprint"]))
        if entry.get("code"):
            codes.add(str(entry["code"]))
    return fingerprints, codes


def discover(
    root: Path = ROOT,
    budget: int = 5,
    include_canonical: bool = True,
) -> list[ImprovementFinding]:
    """Return deduplicated, suppressed, budgeted improvement findings."""
    candidates: list[ImprovementFinding] = []
    if include_canonical:
        for item in validate_standard(root):
            candidates.append(
                make_finding(
                    f"canonical.{item.code}",
                    f"Repair canonical standard finding: {item.code}",
                    item.message,
                    item.path,
                    "high",
                )
            )
    candidates.extend(_release_alignment_findings(root))
    candidates.extend(_fixture_findings(root))
    candidates.extend(_external_signal_findings(root))

    unique = {item.fingerprint: item for item in candidates}
    fingerprints, codes = _suppressed(root)
    active = [
        item
        for item in unique.values()
        if item.fingerprint not in fingerprints and item.code not in codes
    ]
    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    active.sort(
        key=lambda item: (
            severity_rank.get(item.severity, 2),
            item.code,
            item.path or "",
            item.fingerprint,
        )
    )
    return active[: max(0, budget)]
