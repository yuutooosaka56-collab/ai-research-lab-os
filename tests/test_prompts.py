"""Regression tests for agent prompt contracts."""

from prompts.synthesizer import build_synthesizer_prompt


def test_synthesizer_prompt_defines_confidence_boundary() -> None:
    prompt = build_synthesizer_prompt({"question": "test"})

    assert "0.40 <= confidence < 0.60: medium" in prompt.instructions
    assert "0.60 <= confidence < 0.80: high" in prompt.instructions
    assert "0.60 must be high" in prompt.instructions
    assert '"confidence": 0.60' in prompt.input
    assert '"confidence_label": "high"' in prompt.input
