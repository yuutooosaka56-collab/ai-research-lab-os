from __future__ import annotations

from typing import Any, Mapping

import pytest

from orchestrator import (
    AgentExecutionError,
    AgentValidationError,
    CallBudgetExceeded,
    Orchestrator,
)
from providers import AgentName, MockProvider


def test_mock_pipeline_completes_all_three_stages() -> None:
    provider = MockProvider()
    result = Orchestrator(provider).run(
        "AI研究室OSの最小ルートは動作するか"
    )

    assert provider.calls == ["researcher", "skeptic", "synthesizer"]
    assert [stage.agent for stage in result.stages] == provider.calls
    assert all(stage.validation.valid for stage in result.stages)
    assert all(
        stage.payload["run_id"] == result.run_id
        for stage in result.stages
    )
    assert "Mock環境で最後まで動作" in result.final_answer
    assert result.completed_at >= result.started_at


def test_payload_for_returns_each_validated_stage() -> None:
    result = Orchestrator(MockProvider()).run("検証用の質問")

    assert result.payload_for("researcher")["agent"] == "researcher"
    assert result.payload_for("skeptic")["agent"] == "skeptic"
    assert result.payload_for("synthesizer")["agent"] == "synthesizer"


class InvalidResearcherProvider(MockProvider):
    def run_agent(
        self,
        agent: AgentName,
        request: Mapping[str, Any],
        *,
        run_id: str,
    ) -> Mapping[str, Any]:
        payload = dict(
            super().run_agent(agent, request, run_id=run_id)
        )
        if agent == "researcher":
            output = dict(payload["output"])
            output.pop("claims")
            payload["output"] = output
        return payload


def test_invalid_stage_stops_before_downstream_agents() -> None:
    provider = InvalidResearcherProvider()

    with pytest.raises(AgentValidationError) as exc_info:
        Orchestrator(provider).run("不正出力の停止試験")

    assert exc_info.value.agent == "researcher"
    assert not exc_info.value.report.valid
    assert provider.calls == ["researcher"]


def test_call_budget_stops_before_excess_provider_call() -> None:
    provider = MockProvider()

    with pytest.raises(CallBudgetExceeded):
        Orchestrator(provider, max_calls=2).run("呼び出し上限の試験")

    assert provider.calls == ["researcher", "skeptic"]


def test_empty_question_is_rejected_without_provider_call() -> None:
    provider = MockProvider()

    with pytest.raises(ValueError, match="question must not be empty"):
        Orchestrator(provider).run("   ")

    assert provider.calls == []


class ForgedRunIdProvider(MockProvider):
    """Return a run identifier the orchestrator never issued."""

    def run_agent(
        self,
        agent: AgentName,
        request: Mapping[str, Any],
        *,
        run_id: str,
    ) -> Mapping[str, Any]:
        payload = dict(
            super().run_agent(agent, request, run_id=run_id)
        )
        payload["run_id"] = "RUN-FORGED-0000"
        return payload


def test_forged_run_id_stops_before_schema_validation() -> None:
    provider = ForgedRunIdProvider()

    with pytest.raises(AgentExecutionError, match="run_id"):
        Orchestrator(provider).run("run_id偽装の停止試験")

    assert provider.calls == ["researcher"]


class SwappedAgentProvider(MockProvider):
    """Answer a researcher request with a valid skeptic envelope."""

    def run_agent(
        self,
        agent: AgentName,
        request: Mapping[str, Any],
        *,
        run_id: str,
    ) -> Mapping[str, Any]:
        if agent == "researcher":
            self.calls.append(agent)
            researcher = MockProvider().run_agent(
                "researcher",
                request,
                run_id=run_id,
            )
            return MockProvider().run_agent(
                "skeptic",
                {
                    "original_question": "swap",
                    "researcher_payload": researcher,
                },
                run_id=run_id,
            )
        return super().run_agent(agent, request, run_id=run_id)


def test_swapped_agent_payload_stops_before_schema_validation() -> None:
    provider = SwappedAgentProvider()

    with pytest.raises(AgentExecutionError) as exc_info:
        Orchestrator(provider).run("agent入れ替えの停止試験")

    assert exc_info.value.agent == "researcher"
    assert "expected 'researcher'" in str(exc_info.value)
    assert provider.calls == ["researcher"]


def test_result_exposes_audit_events() -> None:
    result = Orchestrator(MockProvider()).run("監査イベントの保存試験")

    names = [event["event"] for event in result.events]

    assert names.count("provider_call_reserved") == 3
    assert names.count("agent_completed") == 3
    assert names[-1] == "run_completed"
    assert all("at" in event for event in result.events)
