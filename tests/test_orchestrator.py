from __future__ import annotations

from typing import Any, Mapping

import pytest

from orchestrator import (
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
