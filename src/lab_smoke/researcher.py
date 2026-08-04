"""One-call Researcher smoke test with an explicit paid-execution guard."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from orchestrator import new_run_id
from providers import AgentProvider, OpenAIProvider
from validation import ValidationReport, validate_agent_output

DEFAULT_QUESTION = (
    "AI研究室OSのResearcher接続が正常に動作するか確認してください。"
)


class SmokeTestError(RuntimeError):
    """Raised when a one-call smoke test cannot be completed safely."""


@dataclass(frozen=True, slots=True)
class ResearcherSmokeResult:
    """Result of exactly one Researcher provider call."""

    run_id: str
    payload: Mapping[str, Any]
    validation: ValidationReport

    @property
    def valid(self) -> bool:
        return self.validation.valid

    @property
    def summary(self) -> str:
        output = self.payload.get("output")
        if not isinstance(output, Mapping):
            return ""
        value = output.get("research_summary")
        return value if isinstance(value, str) else ""

    @property
    def model_label(self) -> str:
        model = self.payload.get("model")
        if not isinstance(model, Mapping):
            return "unknown"
        name = str(model.get("name") or "unknown")
        version = str(model.get("version") or name)
        return name if version == name else f"{name} ({version})"


def run_researcher_smoke(
    provider: AgentProvider,
    question: str,
    *,
    context: Mapping[str, Any] | None = None,
    run_id: str | None = None,
) -> ResearcherSmokeResult:
    """Call only Researcher once and validate the returned run envelope."""

    normalized_question = question.strip()
    if not normalized_question:
        raise ValueError("question must not be empty")

    expected_run_id = run_id or new_run_id()
    request = {
        "question": normalized_question,
        "context": dict(context or {}),
        "constraints": {
            "mode": "researcher_smoke_test",
            "max_agent_calls": 1,
        },
    }

    try:
        raw_payload = provider.run_agent(
            "researcher",
            request,
            run_id=expected_run_id,
        )
        payload = dict(raw_payload)
    except Exception as exc:
        raise SmokeTestError(
            f"Researcher request failed with {type(exc).__name__}"
        ) from exc

    if payload.get("run_id") != expected_run_id:
        raise SmokeTestError("Provider returned an unexpected run_id")
    if payload.get("agent") != "researcher":
        raise SmokeTestError("Provider returned an unexpected agent")

    report = validate_agent_output(payload, agent="researcher")
    return ResearcherSmokeResult(
        run_id=expected_run_id,
        payload=payload,
        validation=report,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-research-smoke",
        description=(
            "Preview or execute exactly one paid OpenAI Researcher request. "
            "Skeptic and Synthesizer are never called by this command."
        ),
    )
    parser.add_argument(
        "question",
        nargs="?",
        default=DEFAULT_QUESTION,
        help="Question sent to the Researcher role.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually send one API request. Without this flag no request is sent.",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=1200,
        help="Maximum output tokens for the single Researcher response.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=60.0,
        help="Request timeout in seconds.",
    )
    parser.add_argument(
        "--show-json",
        action="store_true",
        help="Print the validated run envelope after a successful request.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.max_output_tokens < 1:
        print("ERROR: --max-output-tokens must be at least 1", file=sys.stderr)
        return 2
    if args.timeout_seconds <= 0:
        print("ERROR: --timeout-seconds must be positive", file=sys.stderr)
        return 2
    if not args.question.strip():
        print("ERROR: question must not be empty", file=sys.stderr)
        return 2

    model = os.environ.get("OPENAI_MODEL", "").strip() or "<not set>"
    if not args.execute:
        print("DRY RUN: no API request was sent.")
        print(f"Model: {model}")
        print("Agent calls: 1 Researcher, 0 Skeptic, 0 Synthesizer")
        print(f"Max output tokens: {args.max_output_tokens}")
        print(f"Question: {args.question.strip()}")
        print("Run again with --execute to send exactly one paid request.")
        return 0

    print("Executing exactly one Researcher API request...")
    try:
        provider = OpenAIProvider.from_env(
            timeout_seconds=args.timeout_seconds,
            max_output_tokens=args.max_output_tokens,
        )
        result = run_researcher_smoke(provider, args.question)
    except (ValueError, SmokeTestError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Run ID: {result.run_id}")
    print(f"Model: {result.model_label}")
    print(f"Validation: {'PASS' if result.valid else 'FAIL'}")

    if result.summary:
        print("Research summary:")
        print(result.summary)

    _print_validation_issues(result.validation)
    if not result.valid:
        return 2

    if args.show_json:
        print(json.dumps(result.payload, ensure_ascii=False, indent=2))
    return 0


def _print_validation_issues(report: ValidationReport) -> None:
    for issue in report.schema.issues:
        print(
            f"SCHEMA ERROR {issue.path}: {issue.message}",
            file=sys.stderr,
        )
    if report.semantic is None:
        return
    for issue in report.semantic.issues:
        stream = sys.stderr if issue.severity == "error" else sys.stdout
        print(
            f"SEMANTIC {issue.severity.upper()} "
            f"{issue.code} {issue.path}: {issue.message}",
            file=stream,
        )


if __name__ == "__main__":
    raise SystemExit(main())
