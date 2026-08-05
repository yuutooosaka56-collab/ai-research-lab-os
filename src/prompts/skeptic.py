"""Skeptic prompt construction."""

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
  "overall_assessment": "non-empty string",
  "issues": [
    {
      "issue_id": "I-001",
      "severity": "critical|major|moderate|minor|none",
      "category": "string",
      "target_claim_ids": ["C-001"],
      "description": "string",
      "why_it_matters": "string",
      "recommended_correction": "string"
    }
  ],
  "counterarguments": [
    {
      "id": "CA-001",
      "argument": "string",
      "strength": "strong|moderate|weak",
      "supporting_evidence_ids": ["E-001"]
    }
  ],
  "alternative_hypotheses": [
    {
      "id": "H-001",
      "hypothesis": "string",
      "what_would_support_it": "string",
      "what_would_falsify_it": "string"
    }
  ],
  "confidence_adjustments": [
    {
      "claim_id": "C-001",
      "original": 0.0,
      "recommended": 0.0,
      "reason": "string"
    }
  ],
  "additional_research_required": false,
  "priority_followups": ["string"],
  "surviving_strengths": ["string"]
}
"""


def build_skeptic_prompt(request: Mapping[str, Any]) -> PromptBundle:
    """Build the critical-review prompt for one researcher result."""

    role_instructions = """
Role: Skeptic.
Audit the Researcher output for unsupported claims, weak evidence, hidden
assumptions, causal errors, stale information, conflicts of interest, and
alternative explanations. Do not oppose claims merely to create disagreement.
Only reference Claim IDs and Evidence IDs that exist in the supplied Researcher
payload. If a counterargument has no supplied evidence, use an empty evidence
array and describe it as a possibility rather than an established fact.

Objection eligibility test.
Every entry in `issues`, `counterarguments`, and `alternative_hypotheses` must
satisfy all four checks below. If an objection fails any one of them, do not
output it at all.
1. Constraint-compatible: it holds without relaxing, changing, or ignoring any
   hard constraint.
2. Grounded: the supplied materials support it.
3. Decision-relevant: it explains a specific causal chain or calculation that
   would change the conclusion under the fixed conditions.
4. Sound: its arithmetic and its logic hold.

Prohibited objections:
- Any objection that assumes additional people, additional shifts, overtime,
  outsourcing, a longer working day, automatic approval, or full automation
  that the supplied materials do not state.
- Any objection that parallelization, batching, asynchronous processing, or
  pipelining could make an option feasible when it does not reduce the total
  human working time that option requires. Reordering work does not change that
  total, so it cannot resolve a staffing or working-hour constraint.
- Vague possibility statements such as "this might be improvable" that change
  no constrained quantity.
Leaving an array empty is better than filling it with objections that fail this
test. Report genuine agreement through `surviving_strengths` instead.
""".strip()
    return PromptBundle(
        instructions=(
            f"{COMMON_INSTRUCTIONS}\n\n"
            f"{HARD_CONSTRAINT_INSTRUCTIONS}\n\n"
            f"{role_instructions}"
        ),
        input=build_input(
            role="skeptic",
            request=request,
            output_contract=_OUTPUT_CONTRACT,
        ),
    )
