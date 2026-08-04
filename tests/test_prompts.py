"""Regression tests for agent prompt contracts."""

from prompts.researcher import build_researcher_prompt
from prompts.synthesizer import build_synthesizer_prompt


def test_researcher_prompt_defines_strict_evidence_ids() -> None:
    prompt = build_researcher_prompt(
        {
            "question": "test",
            "context": {
                "materials": [
                    {
                        "evidence_id": "E-001",
                        "locator": "input://test/E-001",
                    }
                ]
            },
        }
    )

    assert "Evidence IDs: E-001, E-002" in prompt.instructions
    assert "`E-M001` is invalid" in prompt.instructions
    assert "reuse it" in prompt.instructions
    assert '"evidence_id": "E-001"' in prompt.input


def test_synthesizer_prompt_defines_confidence_boundary() -> None:
    prompt = build_synthesizer_prompt({"question": "test"})

    assert "0.40 <= confidence < 0.60: medium" in prompt.instructions
    assert "0.60 <= confidence < 0.80: high" in prompt.instructions
    assert "0.60 must be high" in prompt.instructions
    assert '"confidence": 0.60' in prompt.input
    assert '"confidence_label": "high"' in prompt.input
