"""OpenAI Responses API adapter for the bounded MVP pipeline."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Mapping

from prompts import build_agent_prompt

from .base import AgentName


class OpenAIProviderConfigurationError(RuntimeError):
    """Raised when the provider cannot be configured safely."""


class OpenAIProviderResponseError(RuntimeError):
    """Raised when the API response cannot become a validated agent payload."""


class OpenAIProvider:
    """Generate role output with the OpenAI Responses API.

    The model generates only the role-specific ``output`` object. Trusted run
    metadata is attached locally so the model cannot choose the run identifier,
    timestamps, provider name, or model metadata.

    A client may be injected for tests. When no client is supplied, the official
    ``openai`` package is imported lazily and configured with SDK retries disabled
    so orchestration limits remain explicit.
    """

    def __init__(
        self,
        *,
        model: str,
        client: Any | None = None,
        api_key: str | None = None,
        timeout_seconds: float = 120.0,
        max_output_tokens: int = 4_000,
    ) -> None:
        normalized_model = model.strip()
        if not normalized_model:
            raise OpenAIProviderConfigurationError("model must not be empty")
        if timeout_seconds <= 0:
            raise OpenAIProviderConfigurationError(
                "timeout_seconds must be positive"
            )
        if max_output_tokens < 1:
            raise OpenAIProviderConfigurationError(
                "max_output_tokens must be at least 1"
            )

        self._model = normalized_model
        self._max_output_tokens = max_output_tokens
        self._client = (
            client
            if client is not None
            else self._build_client(
                api_key=api_key,
                timeout_seconds=timeout_seconds,
            )
        )

    @classmethod
    def from_env(
        cls,
        *,
        timeout_seconds: float = 120.0,
        max_output_tokens: int = 4_000,
    ) -> "OpenAIProvider":
        """Create a provider from explicit environment variables.

        ``OPENAI_MODEL`` is required rather than silently selecting a model that
        may change price, capability, or availability over time.
        """

        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        model = os.environ.get("OPENAI_MODEL", "").strip()
        if not api_key:
            raise OpenAIProviderConfigurationError(
                "OPENAI_API_KEY is not set"
            )
        if not model:
            raise OpenAIProviderConfigurationError(
                "OPENAI_MODEL is not set"
            )
        return cls(
            model=model,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            max_output_tokens=max_output_tokens,
        )

    @property
    def provider_name(self) -> str:
        return "openai"

    def run_agent(
        self,
        agent: AgentName,
        request: Mapping[str, Any],
        *,
        run_id: str,
    ) -> Mapping[str, Any]:
        """Execute one role and return a complete local run envelope."""

        prompt = build_agent_prompt(agent, request)
        started_at = datetime.now(timezone.utc)

        try:
            response = self._client.responses.create(
                model=self._model,
                instructions=prompt.instructions,
                input=prompt.input,
                text={"format": {"type": "json_object"}},
                max_output_tokens=self._max_output_tokens,
            )
        except Exception as exc:
            raise OpenAIProviderResponseError(
                f"OpenAI request failed with {type(exc).__name__}"
            ) from exc

        status = getattr(response, "status", None)
        if status != "completed":
            raise OpenAIProviderResponseError(
                f"OpenAI response status was {status!r}, expected 'completed'"
            )

        output_text = getattr(response, "output_text", None)
        if not isinstance(output_text, str) or not output_text.strip():
            raise OpenAIProviderResponseError(
                "OpenAI response did not contain output_text"
            )

        try:
            output = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise OpenAIProviderResponseError(
                "OpenAI output_text was not valid JSON"
            ) from exc
        if not isinstance(output, dict):
            raise OpenAIProviderResponseError(
                "OpenAI output must be a JSON object"
            )

        completed_at = datetime.now(timezone.utc)
        model_version = str(
            getattr(response, "model", None) or self._model
        )
        return {
            "protocol_version": "0.1",
            "run_id": run_id,
            "agent": agent,
            "status": "completed",
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "model": {
                "provider": "openai",
                "name": self._model,
                "version": model_version,
            },
            "input_digest": _digest(request),
            "warnings": [],
            "errors": [],
            "output": output,
        }

    @staticmethod
    def _build_client(
        *,
        api_key: str | None,
        timeout_seconds: float,
    ) -> Any:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise OpenAIProviderConfigurationError(
                "Install the OpenAI extra with: pip install -e '.[openai]'"
            ) from exc

        kwargs: dict[str, Any] = {
            "timeout": timeout_seconds,
            "max_retries": 0,
        }
        if api_key is not None:
            kwargs["api_key"] = api_key
        return OpenAI(**kwargs)


def _digest(request: Mapping[str, Any]) -> str:
    serialized = json.dumps(
        request,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(serialized).hexdigest()
