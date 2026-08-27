"""Optionally enrich deterministic self-improvement findings with LLM analysis."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from llm_improvement import (
    DEFAULT_MAX_INPUT_CHARS,
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_MODEL,
    analyze_optional,
    enabled_from_env,
)

ROOT = Path(__file__).resolve().parents[1]


def _env_int(name: str, default: int) -> int:
    """Read a positive integer environment setting with a safe default."""
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


def _env_float(name: str, default: float) -> float:
    """Read a bounded float environment setting with a safe default."""
    try:
        value = float(os.environ.get(name, str(default)))
    except ValueError:
        return default
    return value if 0 <= value <= 1 else default


def main() -> int:
    """Write deterministic findings plus any validated optional LLM findings."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("findings.json"))
    parser.add_argument("--output", type=Path, default=Path("combined-findings.json"))
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("deterministic findings input must contain a list")

    budget = _env_int("AI_NATIVE_ISSUE_BUDGET", 5)
    findings, status = analyze_optional(
        ROOT,
        payload,
        enabled=enabled_from_env(),
        api_key=os.environ.get("OPENAI_API_KEY"),
        model=os.environ.get("AI_NATIVE_LLM_MODEL", DEFAULT_MODEL),
        budget=budget,
        min_confidence=_env_float("AI_NATIVE_LLM_MIN_CONFIDENCE", DEFAULT_MIN_CONFIDENCE),
        max_input_chars=_env_int("AI_NATIVE_LLM_MAX_INPUT_CHARS", DEFAULT_MAX_INPUT_CHARS),
        max_output_tokens=_env_int(
            "AI_NATIVE_LLM_MAX_OUTPUT_TOKENS", DEFAULT_MAX_OUTPUT_TOKENS
        ),
    )
    args.output.write_text(
        json.dumps(findings, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"AI analysis {status}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
