from __future__ import annotations

from typing import Any, Mapping

import pytest

from lab_smoke import SmokeTestError, main, run_researcher_smoke
from providers import AgentName, MockProvider, OpenAIProvider


def test_smoke_calls_only_researcher_once() -> None:
    provider = MockProvider()

    result = run_researcher_smoke(
        provider,
        "Researcherスモークテスト",
        run_id="RUN-SMOKE-001",
    )

    assert result.valid
    assert result.run_id == "RUN-SMOKE-001"
    assert result.payload["agent"] == "researcher"
    assert provider.calls == ["researcher"]
    assert result.summary


class WrongRunIdProvider(MockProvider):
    def run_agent(
        self,
        agent: AgentName,
        request: Mapping[str, Any],
        *,
        run_id: str,
    ) -> Mapping[str, Any]:
        payload = dict(super().run_agent(agent, request, run_id=run_id))
        payload["run_id"] = "RUN-WRONG"
        return payload


def test_smoke_rejects_provider_run_id_mismatch() -> None:
    provider = WrongRunIdProvider()

    with pytest.raises(SmokeTestError, match="unexpected run_id"):
        run_researcher_smoke(
            provider,
            "Run ID検査",
            run_id="RUN-SMOKE-002",
        )

    assert provider.calls == ["researcher"]


def test_smoke_rejects_empty_question_before_provider_call() -> None:
    provider = MockProvider()

    with pytest.raises(ValueError, match="question must not be empty"):
        run_researcher_smoke(provider, "   ")

    assert provider.calls == []


def test_cli_dry_run_never_builds_openai_provider(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_if_called(**_: Any) -> OpenAIProvider:
        raise AssertionError("from_env must not run during dry-run")

    monkeypatch.setattr(OpenAIProvider, "from_env", fail_if_called)
    monkeypatch.setenv("OPENAI_MODEL", "preview-model")

    exit_code = main(["料金ゼロの確認"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "no API request was sent" in captured.out
    assert "1 Researcher, 0 Skeptic, 0 Synthesizer" in captured.out
    assert "preview-model" in captured.out


def test_cli_execute_uses_one_provider_call(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    provider = MockProvider()
    captured_settings: dict[str, Any] = {}

    def fake_from_env(**kwargs: Any) -> MockProvider:
        captured_settings.update(kwargs)
        return provider

    monkeypatch.setattr(OpenAIProvider, "from_env", fake_from_env)

    exit_code = main(
        [
            "--execute",
            "--max-output-tokens",
            "777",
            "--timeout-seconds",
            "45",
            "実行回数の確認",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert provider.calls == ["researcher"]
    assert captured_settings == {
        "timeout_seconds": 45.0,
        "max_output_tokens": 777,
    }
    assert "Validation: PASS" in captured.out


def test_cli_rejects_invalid_limits_without_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called(**_: Any) -> OpenAIProvider:
        raise AssertionError("from_env must not run for invalid arguments")

    monkeypatch.setattr(OpenAIProvider, "from_env", fail_if_called)

    assert main(["--execute", "--max-output-tokens", "0"]) == 2
    assert main(["--execute", "--timeout-seconds", "0"]) == 2
