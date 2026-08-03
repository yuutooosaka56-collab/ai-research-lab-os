"""Provider-neutral prompt builders for MVP agents."""

from __future__ import annotations

from typing import Any, Mapping

from providers.base import AgentName

from .common import PromptBundle
from .researcher import build_researcher_prompt
from .skeptic import build_skeptic_prompt
from .synthesizer import build_synthesizer_prompt


def build_agent_prompt(
    agent: AgentName,
    request: Mapping[str, Any],
) -> PromptBundle:
    """Dispatch one structured request to its role-specific prompt builder."""

    if agent == "researcher":
        return build_researcher_prompt(request)
    if agent == "skeptic":
        return build_skeptic_prompt(request)
    if agent == "synthesizer":
        return build_synthesizer_prompt(request)
    raise ValueError(f"Unsupported agent: {agent}")


__all__ = [
    "PromptBundle",
    "build_agent_prompt",
    "build_researcher_prompt",
    "build_skeptic_prompt",
    "build_synthesizer_prompt",
]
