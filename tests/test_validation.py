from __future__ import annotations

from copy import deepcopy

import pytest

from validation import (
    SchemaValidator,
    SemanticValidator,
    confidence_label,
    validate_agent_output,
)


def envelope(agent: str, output: dict) -> dict:
    return {
        "protocol_version": "0.1",
        "run_id": "RUN-20260803-0001",
        "agent": agent,
        "status": "completed",
        "started_at": "2026-08-03T22:00:00+09:00",
        "completed_at": "2026-08-03T22:00:05+09:00",
        "model": {
            "provider": "test",
            "name": "mock-model",
            "version": "1",
        },
        "input_digest": "sha256:test",
        "warnings": [],
        "errors": [],
        "output": output,
    }


@pytest.fixture
def researcher_payload() -> dict:
    return envelope(
        "researcher",
        {
            "question_restated": "検証対象の問い",
            "scope": {
                "included": ["対象範囲"],
                "excluded": [],
            },
            "subquestions": [],
            "assumptions": [],
            "claims": [
                {
                    "claim_id": "C-001",
                    "text": "検証可能な事実",
                    "type": "fact",
                    "confidence": 0.8,
                    "evidence_ids": ["E-001"],
                    "assumptions": [],
                    "limitations": [],
                    "verification_status": "supported",
                }
            ],
            "evidence": [
                {
                    "evidence_id": "E-001",
                    "title": "一次資料",
                    "source_type": "primary",
                    "locator": "https://example.test/source",
                    "supports_claim_ids": ["C-001"],
                    "reliability": 0.9,
                    "notes": "テスト用資料",
                }
            ],
            "conflicts": [],
            "unknowns": [],
            "research_summary": "調査結果の要約",
        },
    )


@pytest.fixture
def skeptic_payload() -> dict:
    return envelope(
        "skeptic",
        {
            "overall_assessment": "主要主張は概ね支持される",
            "issues": [
                {
                    "issue_id": "I-001",
                    "severity": "minor",
                    "category": "scope_limit",
                    "target_claim_ids": ["C-001"],
                    "description": "適用範囲が限定される",
                    "why_it_matters": "一般化に影響する",
                    "recommended_correction": "条件を明示する",
                }
            ],
            "counterarguments": [
                {
                    "id": "CA-001",
                    "argument": "別条件では結論が変わる可能性がある",
                    "strength": "weak",
                    "supporting_evidence_ids": ["E-001"],
                }
            ],
            "alternative_hypotheses": [],
            "confidence_adjustments": [
                {
                    "claim_id": "C-001",
                    "original": 0.8,
                    "recommended": 0.7,
                    "reason": "適用範囲が限定されるため",
                }
            ],
            "additional_research_required": False,
            "priority_followups": [],
            "surviving_strengths": ["一次資料がある"],
        },
    )


@pytest.fixture
def synthesizer_payload() -> dict:
    return envelope(
        "synthesizer",
        {
            "direct_answer": "条件付きで支持される",
            "conclusion": {
                "text": "主要結論は条件付きで支持される",
                "confidence": 0.7,
                "confidence_label": "high",
                "conditions": ["対象条件内であること"],
            },
            "supported_findings": [
                {
                    "claim_id": "C-001",
                    "text": "検証可能な事実",
                    "evidence_ids": ["E-001"],
                    "confidence": 0.7,
                }
            ],
            "important_counterpoints": [
                {
                    "issue_id": "I-001",
                    "text": "適用範囲に限界がある",
                    "impact_on_conclusion": "結論を条件付きにする",
                }
            ],
            "unresolved_uncertainties": [],
            "assumptions": [],
            "recommended_actions": [
                {
                    "priority": 1,
                    "action": "追加条件を確認する",
                    "purpose": "適用可能性を判断する",
                    "success_signal": "対象条件が明確になる",
                }
            ],
            "citations": [
                {
                    "evidence_id": "E-001",
                    "locator": "https://example.test/source",
                }
            ],
            "plain_language_answer": (
                "条件が同じなら、今のところ支持できます。"
            ),
        },
    )


def test_schema_accepts_valid_researcher(
    researcher_payload: dict,
) -> None:
    result = SchemaValidator().validate(researcher_payload)
    assert result.valid, result.issues


def test_schema_reports_invalid_json() -> None:
    result = SchemaValidator().parse_and_validate('{"agent":')
    assert not result.valid
    assert result.issues[0].validator == "json"


def test_schema_rejects_fact_without_evidence(
    researcher_payload: dict,
) -> None:
    payload = deepcopy(researcher_payload)
    payload["output"]["claims"][0]["evidence_ids"] = []
    result = SchemaValidator().validate(payload)
    assert not result.valid
    assert any(
        issue.validator == "minItems"
        for issue in result.issues
    )


def test_self_declared_agent_cannot_choose_its_own_schema(
    skeptic_payload: dict,
) -> None:
    """A skeptic envelope must fail when the caller expected a researcher.

    Without an explicit ``agent`` the validator falls back to the payload's own
    ``agent`` field, so the payload would select the contract it satisfies.
    """

    unpinned = validate_agent_output(skeptic_payload)
    assert unpinned.valid

    pinned = validate_agent_output(skeptic_payload, agent="researcher")
    assert not pinned.valid
    assert pinned.semantic is None
    assert any(
        issue.validator == "const" and issue.path == "$/agent"
        for issue in pinned.schema.issues
    )


def test_expected_agent_accepts_the_matching_payload(
    researcher_payload: dict,
) -> None:
    report = validate_agent_output(researcher_payload, agent="researcher")
    assert report.valid, report.schema.issues


def test_semantic_rejects_dangling_evidence(
    researcher_payload: dict,
) -> None:
    payload = deepcopy(researcher_payload)
    payload["output"]["claims"][0]["evidence_ids"] = [
        "E-999"
    ]
    result = SemanticValidator().validate(payload)
    assert not result.valid
    assert any(
        issue.code == "dangling_evidence_reference"
        for issue in result.issues
    )


def test_semantic_detects_secret(
    researcher_payload: dict,
) -> None:
    payload = deepcopy(researcher_payload)
    payload["output"]["research_summary"] = (
        "api_key=sk-abcdefghijklmnopqrstuvwxyz123456"
    )
    result = SemanticValidator().validate(payload)
    assert not result.valid
    assert any(
        issue.code == "secret_detected"
        for issue in result.issues
    )


def test_skeptic_cross_references_researcher(
    researcher_payload: dict,
    skeptic_payload: dict,
) -> None:
    payload = deepcopy(skeptic_payload)
    payload["output"]["issues"][0]["target_claim_ids"] = [
        "C-999"
    ]
    result = SemanticValidator().validate(
        payload,
        researcher_payload=researcher_payload,
    )
    assert not result.valid
    assert any(
        issue.code == "unknown_target_claim"
        for issue in result.issues
    )


def test_synthesizer_validates_context_and_label(
    researcher_payload: dict,
    skeptic_payload: dict,
    synthesizer_payload: dict,
) -> None:
    report = validate_agent_output(
        synthesizer_payload,
        researcher_payload=researcher_payload,
        skeptic_payload=skeptic_payload,
    )
    assert report.valid

    payload = deepcopy(synthesizer_payload)
    payload["output"]["conclusion"][
        "confidence_label"
    ] = "medium"
    result = SemanticValidator().validate(
        payload,
        researcher_payload=researcher_payload,
        skeptic_payload=skeptic_payload,
    )
    assert not result.valid
    assert any(
        issue.code == "confidence_label_mismatch"
        for issue in result.issues
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.0, "very_low"),
        (0.2, "low"),
        (0.4, "medium"),
        (0.6, "high"),
        (0.8, "very_high"),
        (1.0, "very_high"),
    ],
)
def test_confidence_label_boundaries(
    value: float,
    expected: str,
) -> None:
    assert confidence_label(value) == expected
