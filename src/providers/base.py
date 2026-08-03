"""Provider abstraction for agent execution."""

from __future__ import annotations

from typing import Any, Literal, Mapping, Protocol, runtime_checkable

AgentName = Literal["researcher", "skeptic", "synthesizer"]


@runtime_checkable
class AgentProvider(Protocol):
    """Minimal interface implemented by model providers.

    Providers receive an agent name, a structured request, and the current
    run identifier. They must return a complete agent run envelope matching
    the corresponding JSON Schema.
    """

    @property
    def provider_name(self) -> str:
        """Human-readable provider identifier used in logs."""

    def run_agent(
        self,
        agent: AgentName,
        request: Mapping[str, Any],
        *,
        run_id: str,
    ) -> Mapping[str, Any]:
        """Execute one agent and return its complete run envelope."""
