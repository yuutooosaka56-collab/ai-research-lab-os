"""Synthesizer prompt construction."""

from __future__ import annotations

from typing import Any, Mapping

from .common import (
    COMMON_INSTRUCTIONS,
    HARD_CONSTRAINT_INSTRUCTIONS,
    PromptBundle,
    build_input,
)

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

Skeptic adoption gate.
Skeptic output is a set of candidates, not a set of decisions. Do not adopt a
Skeptic item automatically. Before an issue, counterargument, or alternative
hypothesis may enter `important_counterpoints`, `unresolved_uncertainties`, or
`recommended_actions`, confirm all four checks:
1. Hard constraints: it does not require relaxing, changing, or ignoring any
   hard constraint.
2. Grounding: the supplied materials support it.
3. Materiality: it changes the conclusion under the fixed conditions.
4. Soundness: its arithmetic and its logic hold.
If even one check fails, exclude the item from `important_counterpoints`,
`unresolved_uncertainties`, and `recommended_actions`. Dropping an ineligible
objection is correct behaviour, not an omission, and does not by itself lower
`conclusion.confidence`.
An objection that depends on adding people, adding shifts, or overtime fails
check 1. An objection that parallelization or batching makes an option feasible,
when it does not reduce the total human working time required, fails check 3.
Both must be excluded.
""".strip()
    return PromptBundle(
        instructions=(
            f"{COMMON_INSTRUCTIONS}\n\n"
            f"{HARD_CONSTRAINT_INSTRUCTIONS}\n\n"
            f"{role_instructions}"
        ),
        input=build_input(
            role="synthesizer",
            request=request,
            output_contract=_OUTPUT_CONTRACT,
        ),
    )
