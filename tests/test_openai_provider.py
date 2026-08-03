from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from orchestrator import Orchestrator
from prompts import build_agent_prompt
from providers import (
    MockProvider,
    OpenAIProvider,
    OpenAIProviderConfigurationError,
    OpenAIProviderResponseError,
)
from validation import validate_agent_output


@dataclass
class FakeResponse:
    output_text: str
    status: str = "completed"
    model: str = "test-model-version"


class FakeResponsesResource:
    def __init__(
        self,
        response: FakeResponse | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


class QueuedResponsesResource:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.remaining = list(responses)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(kwargs)
        assert self.remaining, "No queued fake response remains"
        return self.remaining.pop(0)


class FakeClient:
    def __init__(self, responses: Any) -> None:
        self.responses = responses


def researcher_output(question: str = "検証用の質問") -> dict[str, Any]:
    request = {"question": question, "context": {}}
    payload = MockProvider().run_agent(
        "researcher",
        request,
        run_id="RUN-SOURCE-001",
    )
    return dict(payload["output"])


def queued_role_responses(question: str) -> list[FakeResponse]:
    mock = MockProvider()
    researcher_request = {"question": question, "context": {}}
    researcher = mock.run_agent(
        "researcher",
        researcher_request,
        run_id="RUN-SOURCE-002",
    )
    skeptic_request = {
        "original_question": question,
        "researcher_payload": researcher,
        "context": {},
    }
    skeptic = mock.run_agent(
        "skeptic",
        skeptic_request,
        run_id="RUN-SOURCE-002",
    )
    synthesizer_request = {
        "original_question": question,
        "researcher_payload": researcher,
        "skeptic_payload": skeptic,
        "context": {},
    }
    synthesizer = mock.run_agent(
        "synthesizer",
        synthesizer_request,
        run_id="RUN-SOURCE-002",
    )
    return [
        FakeResponse(json.dumps(payload["output"], ensure_ascii=False))
        for payload in (researcher, skeptic, synthesizer)
    ]


def test_provider_uses_responses_api_and_returns_valid_envelope() -> None:
    output = researcher_output()
    resource = FakeResponsesResource(
        FakeResponse(output_text=json.dumps(output, ensure_ascii=False))
    )
    provider = OpenAIProvider(
        model="test-model",
        client=FakeClient(resource),
        max_output_tokens=1234,
    )
    request = {"question": "検証用の質問", "context": {}}

    payload = provider.run_agent(
        "researcher",
        request,
        run_id="RUN-OPENAI-001",
    )

    assert provider.provider_name == "openai"
    assert payload["run_id"] == "RUN-OPENAI-001"
    assert payload["agent"] == "researcher"
    assert payload["model"] == {
        "provider": "openai",
        "name": "test-model",
        "version": "test-model-version",
    }
    assert payload["output"] == output
    assert validate_agent_output(payload).valid

    assert len(resource.calls) == 1
    call = resource.calls[0]
    assert call["model"] == "test-model"
    assert call["max_output_tokens"] == 1234
    assert call["text"] == {"format": {"type": "json_object"}}
    assert "Return exactly one JSON object" in call["instructions"]
    assert "UNTRUSTED REQUEST DATA" in call["input"]
    assert "検証用の質問" in call["input"]


def test_openai_provider_completes_orchestrator_with_mocked_http() -> None:
    question = "OpenAI接続経路は一周するか"
    resource = QueuedResponsesResource(queued_role_responses(question))
    provider = OpenAIProvider(
        model="test-model",
        client=FakeClient(resource),
    )

    result = Orchestrator(provider).run(question)

    assert [stage.agent for stage in result.stages] == [
        "researcher",
        "skeptic",
        "synthesizer",
    ]
    assert all(stage.validation.valid for stage in result.stages)
    assert "Mock環境で最後まで動作" in result.final_answer
    assert len(resource.calls) == 3
    assert "ROLE: researcher" in resource.calls[0]["input"]
    assert "ROLE: skeptic" in resource.calls[1]["input"]
    assert "ROLE: synthesizer" in resource.calls[2]["input"]


def test_provider_rejects_non_completed_response() -> None:
    resource = FakeResponsesResource(
        FakeResponse(output_text="{}", status="incomplete")
    )
    provider = OpenAIProvider(
        model="test-model",
        client=FakeClient(resource),
    )

    with pytest.raises(
        OpenAIProviderResponseError,
        match="expected 'completed'",
    ):
        provider.run_agent(
            "researcher",
            {"question": "x"},
            run_id="RUN-OPENAI-002",
        )


def test_provider_rejects_invalid_json() -> None:
    resource = FakeResponsesResource(FakeResponse(output_text="not-json"))
    provider = OpenAIProvider(
        model="test-model",
        client=FakeClient(resource),
    )

    with pytest.raises(
        OpenAIProviderResponseError,
        match="not valid JSON",
    ):
        provider.run_agent(
            "researcher",
            {"question": "x"},
            run_id="RUN-OPENAI-003",
        )


def test_provider_rejects_non_object_json() -> None:
    resource = FakeResponsesResource(FakeResponse(output_text="[]"))
    provider = OpenAIProvider(
        model="test-model",
        client=FakeClient(resource),
    )

    with pytest.raises(
        OpenAIProviderResponseError,
        match="must be a JSON object",
    ):
        provider.run_agent(
            "researcher",
            {"question": "x"},
            run_id="RUN-OPENAI-004",
        )


def test_request_errors_are_wrapped_without_echoing_message() -> None:
    resource = FakeResponsesResource(
        error=RuntimeError("secret request content")
    )
    provider = OpenAIProvider(
        model="test-model",
        client=FakeClient(resource),
    )

    with pytest.raises(OpenAIProviderResponseError) as exc_info:
        provider.run_agent(
            "researcher",
            {"question": "x"},
            run_id="RUN-OPENAI-005",
        )

    assert "RuntimeError" in str(exc_info.value)
    assert "secret request content" not in str(exc_info.value)


def test_from_env_requires_explicit_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-sent")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    with pytest.raises(
        OpenAIProviderConfigurationError,
        match="OPENAI_MODEL",
    ):
        OpenAIProvider.from_env()


def test_prompt_router_builds_all_roles() -> None:
    for agent in ("researcher", "skeptic", "synthesizer"):
        prompt = build_agent_prompt(agent, {"payload": "data"})
        assert "Return exactly one JSON object" in prompt.instructions
        assert f"ROLE: {agent}" in prompt.input
        assert '"payload": "data"' in prompt.input
