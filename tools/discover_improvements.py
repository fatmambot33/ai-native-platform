"""Emit structured canonical standard findings for issue automation."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from validator.validate_standard import validate_standard  # noqa: E402


def main() -> int:
    """Print structured findings without failing the discovery workflow."""
    print(json.dumps([asdict(finding) for finding in validate_standard()], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
