"""Installed command entry point with derived-repository conformance checks."""

from __future__ import annotations

import argparse
from pathlib import Path

import ai_native
from ai_native_platform.inheritance import Finding as InheritanceFinding
from ai_native_platform.inheritance import doctor as inheritance_doctor


def _inheritance_findings(args: argparse.Namespace) -> list[InheritanceFinding]:
    """Return inheritance findings, including deterministic root-resolution failures."""
    root = Path(args.root) if args.root else Path(args.manifest).parent
    try:
        resolved_root = root.resolve()
    except (OSError, RuntimeError) as exc:
        return [InheritanceFinding("inheritance.invalid", f"cannot resolve repository root: {exc}")]
    return inheritance_doctor(resolved_root)


def command_doctor(args: argparse.Namespace) -> int:
    """Run the base doctor plus inheritance validation for the target repository."""
    status = ai_native.command_doctor(args)
    findings = _inheritance_findings(args)
    if findings:
        detail = "; ".join(f"{finding.code}: {finding.message}" for finding in findings)
        print(f"FAIL Repository inheritance: {detail}")
        return 1
    print("PASS Repository inheritance: compliant or not opted in")
    return status


def main(argv: list[str] | None = None) -> int:
    """Run the public CLI with the inheritance-aware doctor command."""
    parser = ai_native.build_parser()
    args = parser.parse_args(argv)
    if args.command == "doctor":
        return command_doctor(args)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
