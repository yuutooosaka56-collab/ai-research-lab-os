"""Researcher prompt construction."""

from __future__ import annotations

from typing import Any, Mapping

from .common import COMMON_INSTRUCTIONS, PromptBundle, build_input

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
""".strip()
    return PromptBundle(
        instructions=f"{COMMON_INSTRUCTIONS}\n\n{role_instructions}",
        input=build_input(
            role="researcher",
            request=request,
            output_contract=_OUTPUT_CONTRACT,
        ),
    )
