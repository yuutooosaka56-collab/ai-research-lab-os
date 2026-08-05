"""Researcher prompt construction."""

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
  "question_restated": "non-empty string",
  "scope": {"included": ["string"], "excluded": ["string"]},
  "subquestions": [
    {
      "id": "Q-001",
      "question": "string",
      "importance": "critical|high|medium|low",
      "reason": "string"
    }
  ],
  "assumptions": [
    {"id": "A-001", "text": "string", "risk_if_false": "string"}
  ],
  "claims": [
    {
      "claim_id": "C-001",
      "text": "string",
      "type": "fact|inference|hypothesis|proposal|unknown",
      "confidence": 0.0,
      "evidence_ids": ["E-001"],
      "assumptions": ["string"],
      "limitations": ["string"],
      "verification_status": "supported|partially_supported|contradicted|unverified|not_applicable"
    }
  ],
  "evidence": [
    {
      "evidence_id": "E-001",
      "title": "string",
      "source_type": "primary|secondary|tertiary|user_supplied|model_memory|unknown",
      "locator": "URL, DOI, file identifier, input://..., or model://memory",
      "published_at": null,
      "retrieved_at": null,
      "supports_claim_ids": ["C-001"],
      "reliability": 0.0,
      "notes": "string"
    }
  ],
  "conflicts": [
    {
      "description": "string",
      "claim_ids": ["C-001", "C-002"],
      "possible_explanations": ["string"]
    }
  ],
  "unknowns": [
    {
      "question": "string",
      "importance": "critical|high|medium|low",
      "how_to_resolve": "string"
    }
  ],
  "research_summary": "string"
}
"""


def build_researcher_prompt(request: Mapping[str, Any]) -> PromptBundle:
    """Build the bounded research prompt for one request."""

    role_instructions = """
Role: Researcher.
Decompose the question, expose assumptions, and organize claims and evidence.
Do not decide the final answer. Do not select only convenient evidence.
When no external retrieval result is supplied, do not pretend that web research
occurred. Internal knowledge must be marked `model_memory` and unverified unless
it is only used as a hypothesis or proposal.

Identifier rules are strict:
- Subquestion IDs: Q-001, Q-002, ...
- Assumption IDs: A-001, A-002, ...
- Claim IDs: C-001, C-002, ...
- Evidence IDs: E-001, E-002, ...
- Every identifier is one prefix letter, one hyphen, and exactly three digits.
- Never embed another source prefix inside an evidence ID. `E-M001` is invalid.
- If a supplied material already has an `evidence_id` such as `E-001`, reuse it
  exactly in both the evidence array and all claim evidence_ids references.
- If a source has another identifier such as `M-001`, preserve that identifier
  in title, locator, or notes; do not copy it into evidence_id.
- User-supplied fixed materials must use source_type `user_supplied` and must not
  be relabeled as model_memory.

Hard-constraint handling for this role:
- Test every option against the hard constraints before assigning confidence,
  and show the arithmetic you used.
- The `assumptions` array is for uncertain premises only. Never place a hard
  constraint there.
- When an option fails a hard constraint, record that failure as a claim with
  its calculation. Do not soften it into an unknown or a limitation.
""".strip()
    return PromptBundle(
        instructions=(
            f"{COMMON_INSTRUCTIONS}\n\n"
            f"{HARD_CONSTRAINT_INSTRUCTIONS}\n\n"
            f"{role_instructions}"
        ),
        input=build_input(
            role="researcher",
            request=request,
            output_contract=_OUTPUT_CONTRACT,
        ),
    )
