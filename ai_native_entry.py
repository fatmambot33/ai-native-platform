"""Installed command entry point with derived-repository conformance checks."""

from __future__ import annotations

import argparse
from pathlib import Path

import ai_native
from tools.inheritance import doctor as inheritance_doctor


def command_doctor(args: argparse.Namespace) -> int:
    """Run the base doctor plus inheritance validation for the target repository."""
    status = ai_native.command_doctor(args)
    root = Path(args.root) if args.root else Path(args.manifest).parent
    findings = inheritance_doctor(root.resolve())
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
