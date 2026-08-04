"""Sequential MVP orchestrator for Researcher, Skeptic, and Synthesizer."""

from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Callable, Mapping

from providers.base import AgentName, AgentProvider
from validation import ValidationReport, validate_agent_output

from .models import (
    AgentExecutionError,
    AgentValidationError,
    OrchestrationResult,
    StageResult,
)
from .run_context import RunContext, new_run_id

Validator = Callable[..., ValidationReport]


class Orchestrator:
    """Run the bounded three-agent MVP pipeline.

    The implementation deliberately avoids retries and autonomous loops. A
    provider failure or invalid payload stops the run before downstream agents
    receive untrusted data.
    """

    def __init__(
        self,
        provider: AgentProvider,
        *,
        max_calls: int = 3,
        validator: Validator = validate_agent_output,
    ) -> None:
        if max_calls < 1:
            raise ValueError("max_calls must be at least 1")
        self._provider = provider
        self._max_calls = max_calls
        self._validator = validator

    def run(
        self,
        question: str,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> OrchestrationResult:
        """Execute Researcher -> Skeptic -> Synthesizer exactly once."""

        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("question must not be empty")

        run_context = RunContext(
            run_id=new_run_id(),
            question=normalized_question,
            max_calls=self._max_calls,
        )
        shared_context = dict(context or {})
        stages: list[StageResult] = []

        researcher = self._execute(
            run_context,
            "researcher",
            {
                "question": normalized_question,
                "context": shared_context,
            },
        )
        stages.append(researcher)

        skeptic = self._execute(
            run_context,
            "skeptic",
            {
                "original_question": normalized_question,
                "researcher_payload": researcher.payload,
                "context": shared_context,
            },
            researcher_payload=researcher.payload,
        )
        stages.append(skeptic)

        synthesizer = self._execute(
            run_context,
            "synthesizer",
            {
                "original_question": normalized_question,
                "researcher_payload": researcher.payload,
                "skeptic_payload": skeptic.payload,
                "context": shared_context,
            },
            researcher_payload=researcher.payload,
            skeptic_payload=skeptic.payload,
        )
        stages.append(synthesizer)

        completed_at = datetime.now(timezone.utc)
        run_context.record(
            "run_completed",
            calls=run_context.call_count,
            stages=len(stages),
        )
        return OrchestrationResult(
            run_id=run_context.run_id,
            question=normalized_question,
            started_at=run_context.started_at,
            completed_at=completed_at,
            stages=tuple(stages),
            events=tuple(run_context.events),
        )

    def _execute(
        self,
        run_context: RunContext,
        agent: AgentName,
        request: Mapping[str, Any],
        *,
        researcher_payload: Mapping[str, Any] | None = None,
        skeptic_payload: Mapping[str, Any] | None = None,
    ) -> StageResult:
        run_context.reserve_call(agent)
        started = perf_counter()
        run_context.record("agent_started", agent=agent)

        try:
            raw_payload = self._provider.run_agent(
                agent,
                request,
                run_id=run_context.run_id,
            )
            payload = dict(raw_payload)
        except Exception as exc:  # provider boundary
            run_context.record(
                "agent_execution_failed",
                agent=agent,
                error=type(exc).__name__,
            )
            raise AgentExecutionError(agent, str(exc)) from exc

        self._verify_envelope_identity(run_context, agent, payload)

        report = self._validator(
            payload,
            agent=agent,
            researcher_payload=researcher_payload,
            skeptic_payload=skeptic_payload,
        )
        elapsed = perf_counter() - started

        if not report.valid:
            run_context.record(
                "agent_validation_failed",
                agent=agent,
                elapsed_seconds=elapsed,
            )
            raise AgentValidationError(agent, report)

        run_context.record(
            "agent_completed",
            agent=agent,
            elapsed_seconds=elapsed,
        )
        return StageResult(
            agent=agent,
            payload=payload,
            validation=report,
            elapsed_seconds=elapsed,
        )

    @staticmethod
    def _verify_envelope_identity(
        run_context: RunContext,
        agent: AgentName,
        payload: Mapping[str, Any],
    ) -> None:
        """Reject an envelope that does not match the request that produced it.

        The run identifier and the agent name are assigned by the orchestrator,
        never by the provider or the model. Checking them here keeps a provider
        from substituting another role's payload or attaching a run identifier
        this orchestrator never issued. Both checks run before schema
        validation so a mismatched payload never selects its own contract.
        """

        returned_run_id = payload.get("run_id")
        if returned_run_id != run_context.run_id:
            run_context.record(
                "agent_identity_rejected",
                agent=agent,
                reason="run_id_mismatch",
            )
            raise AgentExecutionError(
                agent,
                f"provider returned run_id {returned_run_id!r}, "
                f"expected {run_context.run_id!r}",
            )

        returned_agent = payload.get("agent")
        if returned_agent != agent:
            run_context.record(
                "agent_identity_rejected",
                agent=agent,
                reason="agent_mismatch",
            )
            raise AgentExecutionError(
                agent,
                f"provider returned agent {returned_agent!r}, "
                f"expected {agent!r}",
            )
