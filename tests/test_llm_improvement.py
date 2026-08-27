"""Tests for the optional, cost-controlled LLM improvement layer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.llm_improvement import analyze_optional, collect_evidence, validate_ai_payload


def test_collect_evidence_is_bounded_and_redacts_secret_assignments(tmp_path: Path) -> None:
    """Only bounded sanitized repository text is exposed to the model."""
    (tmp_path / "README.md").write_text(
        "api_key=super-secret\n" + "useful evidence " * 20,
        encoding="utf-8",
    )
    (tmp_path / "ignored.txt").write_text("not selected", encoding="utf-8")

    evidence = collect_evidence(tmp_path, [], max_chars=80, per_file_chars=80)
    serialized = json.dumps(evidence)

    assert "super-secret" not in serialized
    assert "[REDACTED]" in serialized
    assert sum(len(item["content"]) for item in evidence["files"]) <= 80
    assert [item["path"] for item in evidence["files"]] == ["README.md"]


def test_optional_ai_disabled_or_missing_key_never_calls_model(tmp_path: Path) -> None:
    """Free deterministic discovery remains usable without an API call or credential."""
    baseline = [
        {
            "code": "ci.failure",
            "title": "Fix CI",
            "body": "Evidence",
            "path": None,
            "severity": "high",
            "fingerprint": "abc",
        }
    ]

    def unexpected_request(*_: Any) -> dict[str, Any]:
        raise AssertionError("model requester must not run")

    disabled, disabled_status = analyze_optional(
        tmp_path,
        baseline,
        enabled=False,
        api_key=None,
        requester=unexpected_request,
    )
    missing_key, missing_key_status = analyze_optional(
        tmp_path,
        baseline,
        enabled=True,
        api_key=None,
        requester=unexpected_request,
    )

    assert disabled == baseline
    assert missing_key == baseline
    assert "disabled" in disabled_status
    assert "OPENAI_API_KEY" in missing_key_status


def test_validate_ai_payload_requires_grounded_high_confidence_evidence(tmp_path: Path) -> None:
    """Model proposals survive only when grounded in supplied repository evidence."""
    source = tmp_path / "tools" / "example.py"
    source.parent.mkdir()
    source.write_text("def example():\n    return True\n", encoding="utf-8")
    payload = {
        "findings": [
            {
                "code": "ai.duplicate_validation",
                "title": "Consolidate duplicate validation",
                "body": "Two paths implement the same policy.",
                "path": "tools/example.py",
                "severity": "medium",
                "confidence": 0.91,
                "evidence_paths": ["tools/example.py"],
            },
            {
                "code": "ai.low_confidence",
                "title": "Ignore weak guess",
                "body": "Not sufficiently supported.",
                "path": "tools/example.py",
                "severity": "low",
                "confidence": 0.40,
                "evidence_paths": ["tools/example.py"],
            },
            {
                "code": "ai.invented_file",
                "title": "Reject invented evidence",
                "body": "This path was not supplied.",
                "path": "missing.py",
                "severity": "high",
                "confidence": 0.99,
                "evidence_paths": ["missing.py"],
            },
        ]
    }

    findings = validate_ai_payload(
        payload,
        root=tmp_path,
        evidence_paths={"tools/example.py"},
        budget=5,
        min_confidence=0.80,
    )

    assert len(findings) == 1
    assert findings[0]["code"] == "ai.duplicate_validation"
    assert findings[0]["source"] == "llm"
    assert findings[0]["confidence"] == 0.91
    assert "tools/example.py" in findings[0]["body"]


def test_optional_ai_uses_one_request_and_remaining_issue_budget(tmp_path: Path) -> None:
    """One bounded model call can fill only the unused deterministic issue budget."""
    (tmp_path / "README.md").write_text("repository evidence", encoding="utf-8")
    baseline = [
        {
            "code": "release.drift",
            "title": "Fix release drift",
            "body": "Evidence",
            "path": None,
            "severity": "high",
            "fingerprint": "deterministic",
        }
    ]
    calls: list[tuple[str, int, int]] = []

    def requester(
        evidence: dict[str, Any],
        model: str,
        max_findings: int,
        max_output_tokens: int,
    ) -> dict[str, Any]:
        assert evidence["files"][0]["path"] == "README.md"
        calls.append((model, max_findings, max_output_tokens))
        return {
            "findings": [
                {
                    "code": "ai.readme_gap",
                    "title": "Clarify repository guidance",
                    "body": "The evidence leaves an important workflow implicit.",
                    "path": "README.md",
                    "severity": "medium",
                    "confidence": 0.95,
                    "evidence_paths": ["README.md"],
                }
            ]
        }

    findings, status = analyze_optional(
        tmp_path,
        baseline,
        enabled=True,
        api_key="test-key",
        model="test-model",
        budget=2,
        max_output_tokens=123,
        requester=requester,
    )

    assert calls == [("test-model", 1, 123)]
    assert [finding["source"] for finding in findings if "source" in finding] == ["llm"]
    assert len(findings) == 2
    assert "accepted 1" in status
