"""Mutable execution state for one orchestration run."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from providers.base import AgentName

from .models import CallBudgetExceeded


def new_run_id(now: datetime | None = None) -> str:
    """Create a sortable run identifier without external state."""

    current = now or datetime.now(timezone.utc)
    stamp = current.strftime("%Y%m%dT%H%M%S%fZ")
    return f"RUN-{stamp}-{uuid4().hex[:8]}"


@dataclass(slots=True)
class RunContext:
    """Track bounded execution state and lightweight audit events."""

    run_id: str
    question: str
    max_calls: int = 3
    started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    call_count: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)

    def reserve_call(self, agent: AgentName) -> None:
        """Reserve one provider call or fail before exceeding the limit."""

        if self.call_count >= self.max_calls:
            raise CallBudgetExceeded(
                f"Provider call limit {self.max_calls} reached before {agent}"
            )
        self.call_count += 1
        self.record("provider_call_reserved", agent=agent, call=self.call_count)

    def record(self, event: str, **details: Any) -> None:
        """Append a timestamped, JSON-serializable audit event."""

        self.events.append(
            {
                "at": datetime.now(timezone.utc).isoformat(),
                "event": event,
                **details,
            }
        )
