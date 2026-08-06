"""Compatibility entry point for AI-native platform validation."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_native import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main(["validate", *sys.argv[1:]]))
