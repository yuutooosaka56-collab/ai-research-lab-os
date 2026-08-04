"""Synthesizer prompt construction."""

from __future__ import annotations

from typing import Any, Mapping

from .common import COMMON_INSTRUCTIONS, PromptBundle, build_input

_OUTPUT_CONTRACT = """
{
  "direct_answer": "non-empty string",
  "conclusion": {
    "text": "string",
    "confidence": 0.60,
    "confidence_label": "high",
    "conditions": ["string"]
  },
  "supported_findings": [
    {
      "claim_id": "C-001",
      "text": "string",
      "evidence_ids": ["E-001"],
      "confidence": 0.0
    }
  ],
  "important_counterpoints": [
    {
      "issue_id": "I-001",
      "text": "string",
      "impact_on_conclusion": "string"
    }
  ],
  "unresolved_uncertainties": ["string"],
  "assumptions": ["string"],
  "recommended_actions": [
    {
      "priority": 1,
      "action": "string",
      "purpose": "string",
      "success_signal": "string"
    }
  ],
  "citations": [
    {"evidence_id": "E-001", "locator": "string"}
  ],
  "plain_language_answer": "non-empty string"
}
"""


def build_synthesizer_prompt(request: Mapping[str, Any]) -> PromptBundle:
    """Build the evidence-weighted synthesis prompt."""

    role_instructions = """
Role: Synthesizer.
Answer the original question by integrating the supplied Researcher and Skeptic
outputs. Weight evidence quality rather than agent agreement. Reflect every
critical or major issue that materially changes the answer, preserve unresolved
uncertainty, and do not introduce new factual claims that lack a Researcher
Claim ID and Evidence ID. Citation locators must exactly match the corresponding
Researcher evidence. Recommended-action priorities must start at 1 and be unique.
Use these exact confidence-label bands for conclusion.confidence:
- 0.00 <= confidence < 0.20: very_low
- 0.20 <= confidence < 0.40: low
- 0.40 <= confidence < 0.60: medium
- 0.60 <= confidence < 0.80: high
- 0.80 <= confidence <= 1.00: very_high
Boundary values belong to the higher band; for example, 0.60 must be high.
""".strip()
    return PromptBundle(
        instructions=f"{COMMON_INSTRUCTIONS}\n\n{role_instructions}",
        input=build_input(
            role="synthesizer",
            request=request,
            output_contract=_OUTPUT_CONTRACT,
        ),
    )
