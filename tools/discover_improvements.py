"""Print bounded evidence-driven improvement findings."""

from __future__ import annotations

import argparse
import json
import os

from improvement_engine import discover


def main() -> int:
    """Print structured findings without failing the discovery workflow."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--budget",
        type=int,
        default=int(os.environ.get("AI_NATIVE_ISSUE_BUDGET", "5")),
    )
    args = parser.parse_args()
    print(
        json.dumps(
            [finding.as_dict() for finding in discover(budget=args.budget)],
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
