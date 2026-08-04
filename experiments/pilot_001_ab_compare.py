"""Run the first blinded A/B/C comparison experiment.

A: one direct model answer
B: one structured single-model answer
C: the three-agent AI Research Lab OS pipeline

This script makes five paid API calls only when --execute is supplied.
All systems use the same reasoning effort and output-token limit.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping

from orchestrator import AgentValidationError, Orchestrator
from providers import OpenAIProvider
from validation import ValidationReport

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASE_PATH = ROOT / "experiments" / "pilot_001_case.json"
DEFAULT_ARTIFACT_DIR = ROOT / "artifacts"

SYSTEM_KEYS = ("A", "B", "C")
BLIND_LABELS = ("X", "Y", "Z")

# Every system is graded on the same six sections. A and B are instructed to
# produce them; C is rendered into them from the synthesizer output.
SCORING_SECTIONS = (
    "1. 結論",
    "2. 計算根拠と支持された判断",
    "3. 反論・主要リスク",
    "4. 不確実性と前提",
    "5. 推奨アクション",
    "6. 根拠参照",
)

_SHARED_FORMAT_INSTRUCTION = (
    "回答は次の6つの見出しを、この順序で、この表記のまま使って構成してください。\n"
    + "\n".join(SCORING_SECTIONS)
    + "\n「6. 根拠参照」では、使用した固定資料を evidence_id（E-001 など）で参照してください。"
)

_MISSING = "(記載なし)"

_RUN_ID_PATTERN = re.compile(r"RUN-[A-Za-z0-9._:-]+")


@dataclass
class UsageTotals:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    calls: int = 0

    def add_response(self, response: Any) -> None:
        self.calls += 1
        usage = getattr(response, "usage", None)
        if usage is None:
            return
        self.input_tokens += _as_int(getattr(usage, "input_tokens", 0))
        self.output_tokens += _as_int(getattr(usage, "output_tokens", 0))
        self.total_tokens += _as_int(getattr(usage, "total_tokens", 0))

    def as_dict(self) -> dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "model_calls": self.calls,
        }


class TrackingResponses:
    def __init__(
        self,
        inner: Any,
        usage: UsageTotals,
        *,
        reasoning_effort: str,
        extra_usage: UsageTotals | None = None,
    ) -> None:
        self._inner = inner
        self._usage = usage
        self._reasoning_effort = reasoning_effort
        self._extra_usage = extra_usage

    def create(self, **kwargs: Any) -> Any:
        kwargs.setdefault(
            "reasoning",
            {"effort": self._reasoning_effort},
        )
        response = self._inner.create(**kwargs)
        self._usage.add_response(response)
        if self._extra_usage is not None:
            self._extra_usage.add_response(response)
        return response


class TrackingClient:
    def __init__(
        self,
        inner: Any,
        usage: UsageTotals,
        *,
        reasoning_effort: str,
        extra_usage: UsageTotals | None = None,
    ) -> None:
        self.responses = TrackingResponses(
            inner.responses,
            usage,
            reasoning_effort=reasoning_effort,
            extra_usage=extra_usage,
        )


def build_os_scoring_document(output: Mapping[str, Any]) -> str:
    """Render one synthesizer output as a complete scoring document.

    Grading system C on ``plain_language_answer`` alone would discard the
    counterpoints, uncertainties, assumptions, actions, and citations that the
    rubric actually scores, and would leave C with a visibly different shape
    from A and B. This renders the synthesizer fields into the same six
    sections A and B are asked to produce.
    """

    lines: list[str] = []

    lines.append(SCORING_SECTIONS[0])
    lines.append(_text(output.get("direct_answer")) or _MISSING)
    lines.append("")

    lines.append(SCORING_SECTIONS[1])
    findings = _objects(output.get("supported_findings"))
    if findings:
        for item in findings:
            references = ", ".join(_strings(item.get("evidence_ids")))
            suffix = f"（根拠: {references}）" if references else ""
            lines.append(f"- {_text(item.get('text'))}{suffix}")
    else:
        lines.append(_MISSING)
    lines.append("")

    lines.append(SCORING_SECTIONS[2])
    counterpoints = _objects(output.get("important_counterpoints"))
    if counterpoints:
        for item in counterpoints:
            impact = _text(item.get("impact_on_conclusion"))
            suffix = f"（結論への影響: {impact}）" if impact else ""
            lines.append(f"- {_text(item.get('text'))}{suffix}")
    else:
        lines.append(_MISSING)
    lines.append("")

    lines.append(SCORING_SECTIONS[3])
    uncertainties = _strings(output.get("unresolved_uncertainties"))
    assumptions = _strings(output.get("assumptions"))
    if uncertainties or assumptions:
        for item in uncertainties:
            lines.append(f"- 不確実性: {item}")
        for item in assumptions:
            lines.append(f"- 前提: {item}")
    else:
        lines.append(_MISSING)
    lines.append("")

    lines.append(SCORING_SECTIONS[4])
    actions = _objects(output.get("recommended_actions"))
    if actions:
        ordered = sorted(
            actions,
            key=lambda item: (
                item.get("priority")
                if isinstance(item.get("priority"), int)
                else 10**6
            ),
        )
        for item in ordered:
            priority = item.get("priority")
            label = f"優先度{priority}" if isinstance(priority, int) else "優先度不明"
            lines.append(
                f"- {label}: {_text(item.get('action'))}"
                f" / 目的: {_text(item.get('purpose'))}"
                f" / 成功指標: {_text(item.get('success_signal'))}"
            )
    else:
        lines.append(_MISSING)
    lines.append("")

    lines.append(SCORING_SECTIONS[5])
    citations = _objects(output.get("citations"))
    if citations:
        for item in citations:
            lines.append(
                f"- {_text(item.get('evidence_id'))}: {_text(item.get('locator'))}"
            )
    else:
        lines.append(_MISSING)

    return "\n".join(lines).strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run pilot-001 as a blinded A/B/C comparison."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Send five paid API requests. Without this flag, only preview the plan.",
    )
    parser.add_argument(
        "--case",
        type=Path,
        default=DEFAULT_CASE_PATH,
        help="Path to the fixed experiment case JSON.",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=DEFAULT_ARTIFACT_DIR,
        help="Directory for full and blinded experiment results.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=180.0,
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=8000,
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=("low", "medium", "high"),
        default="low",
        help="Use the same reasoning effort for A, B, and C.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.max_output_tokens < 1:
        print("ERROR: --max-output-tokens must be at least 1", file=sys.stderr)
        return 2
    if args.timeout_seconds <= 0:
        print("ERROR: --timeout-seconds must be positive", file=sys.stderr)
        return 2

    try:
        case = _load_case(args.case)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: could not load case: {exc}", file=sys.stderr)
        return 2

    model = os.environ.get("OPENAI_MODEL", "").strip()
    api_key_set = bool(os.environ.get("OPENAI_API_KEY", "").strip())

    print(f"Experiment: {case['experiment_id']} - {case['title']}")
    print(f"Model: {model or '<not set>'}")
    print("Systems: A=direct, B=structured single model, C=three-agent OS")
    print("Paid model calls: 5 total (1 + 1 + 3)")
    print(f"Reasoning effort: {args.reasoning_effort}")
    print(f"Max output tokens per call: {args.max_output_tokens}")
    print("Execution order: C, A, B")

    if not args.execute:
        print("DRY RUN: no API request was sent.")
        print("Run again with --execute after checking the case and billing.")
        return 0

    if not model:
        print("ERROR: OPENAI_MODEL is not set", file=sys.stderr)
        return 1
    if not api_key_set:
        print("ERROR: OPENAI_API_KEY is not set", file=sys.stderr)
        return 1

    try:
        from openai import OpenAI
    except ImportError:
        print("ERROR: install the OpenAI extra first", file=sys.stderr)
        return 1

    base_client = OpenAI(
        timeout=args.timeout_seconds,
        max_retries=0,
    )
    shared_input = _shared_input(case)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    args.artifact_dir.mkdir(parents=True, exist_ok=True)
    partial_path = args.artifact_dir / f"pilot_001_{timestamp}_partial.json"
    result_path = args.artifact_dir / f"pilot_001_{timestamp}.json"
    blind_path = args.artifact_dir / f"pilot_001_{timestamp}_blind.txt"

    settings = {
        "reasoning_effort": args.reasoning_effort,
        "max_output_tokens": args.max_output_tokens,
        "timeout_seconds": args.timeout_seconds,
        "execution_order": ["C", "A", "B"],
    }
    systems: dict[str, dict[str, Any]] = {}
    cumulative_usage = UsageTotals()
    current_system: str | None = None

    def checkpoint(failure: dict[str, Any] | None = None) -> None:
        _write_json(
            partial_path,
            _checkpoint_record(
                case=case,
                model=model,
                settings=settings,
                systems=systems,
                cumulative_usage=cumulative_usage,
                failure=failure,
            ),
        )

    try:
        current_system = "C"
        print("\nRunning C: three-agent OS (3 calls)...")
        systems["C"] = _run_os_answer(
            client=base_client,
            model=model,
            case=case,
            timeout_seconds=args.timeout_seconds,
            max_output_tokens=args.max_output_tokens,
            reasoning_effort=args.reasoning_effort,
            cumulative_usage=cumulative_usage,
        )
        checkpoint()

        current_system = "A"
        print("Running A: direct single model (1 call)...")
        systems["A"] = _run_single_answer(
            client=base_client,
            model=model,
            usage=UsageTotals(),
            reasoning_effort=args.reasoning_effort,
            instructions=(
                "固定資料だけを使って質問に答えてください。"
                "資料にない事実は追加しないでください。\n"
                + _SHARED_FORMAT_INSTRUCTION
            ),
            input_text=shared_input,
            max_output_tokens=args.max_output_tokens,
            cumulative_usage=cumulative_usage,
        )
        checkpoint()

        current_system = "B"
        print("Running B: structured single model (1 call)...")
        systems["B"] = _run_single_answer(
            client=base_client,
            model=model,
            usage=UsageTotals(),
            reasoning_effort=args.reasoning_effort,
            instructions=(
                "固定資料だけを使って回答してください。次の順序で検討してください："
                "1.制約と数値の抽出、2.各案の計算、3.採用案、4.最も強い反論、"
                "5.不確実性、6.追加検証。"
                "資料にない事実は追加しないでください。\n"
                + _SHARED_FORMAT_INSTRUCTION
            ),
            input_text=shared_input,
            max_output_tokens=args.max_output_tokens,
            cumulative_usage=cumulative_usage,
        )
        checkpoint()
    except AgentValidationError as exc:
        checkpoint(_failure_record(current_system, exc))
        print(f"ERROR: {exc.agent} failed validation", file=sys.stderr)
        for issue in exc.report.schema.issues:
            print(f"SCHEMA {issue.path}: {issue.message}", file=sys.stderr)
        if exc.report.semantic is not None:
            for issue in exc.report.semantic.issues:
                print(
                    f"SEMANTIC {issue.severity} {issue.code} "
                    f"{issue.path}: {issue.message}",
                    file=sys.stderr,
                )
        print(f"Partial result saved: {partial_path}", file=sys.stderr)
        return 1
    except Exception as exc:
        checkpoint(_failure_record(current_system, exc))
        print(
            f"ERROR: experiment failed with {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        print(f"Partial result saved: {partial_path}", file=sys.stderr)
        return 1

    # Only a fully completed run gets a blind mapping and a blind file.
    system_keys = list(SYSTEM_KEYS)
    secrets.SystemRandom().shuffle(system_keys)
    blind_mapping = dict(zip(BLIND_LABELS, system_keys, strict=True))

    record = _checkpoint_record(
        case=case,
        model=model,
        settings=settings,
        systems=systems,
        cumulative_usage=cumulative_usage,
    )
    record["case"] = case
    record["blind_mapping"] = blind_mapping
    _write_json(result_path, record)
    blind_path.write_text(
        _build_blind_document(case, systems, blind_mapping),
        encoding="utf-8",
    )

    print("\nCOMPLETE")
    for key in SYSTEM_KEYS:
        item = systems[key]
        usage = item["usage"]
        print(
            f"{key}: calls={usage['model_calls']} "
            f"tokens={usage['total_tokens']} "
            f"time={item['wall_clock_seconds']:.2f}s"
        )
    print(
        f"Cumulative: calls={cumulative_usage.calls} "
        f"tokens={cumulative_usage.total_tokens}"
    )
    print(f"Full result: {result_path}")
    print(f"Checkpoint: {partial_path}")
    print(f"Blind evaluation file: {blind_path}")
    print(
        "Do not open the full result or the checkpoint "
        "before scoring X, Y, and Z."
    )
    return 0


def _load_case(path: Path) -> dict[str, Any]:
    case = json.loads(path.read_text(encoding="utf-8"))
    required = {"experiment_id", "title", "question", "materials", "constraints"}
    missing = sorted(required - set(case))
    if missing:
        raise ValueError("missing fields: " + ", ".join(missing))
    return case


def _shared_input(case: dict[str, Any]) -> str:
    data = {
        "question": case["question"],
        "materials": case["materials"],
        "constraints": case["constraints"],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def _run_single_answer(
    *,
    client: Any,
    model: str,
    usage: UsageTotals,
    reasoning_effort: str,
    instructions: str,
    input_text: str,
    max_output_tokens: int,
    cumulative_usage: UsageTotals | None = None,
) -> dict[str, Any]:
    tracked = TrackingClient(
        client,
        usage,
        reasoning_effort=reasoning_effort,
        extra_usage=cumulative_usage,
    )
    started = perf_counter()
    response = tracked.responses.create(
        model=model,
        instructions=instructions,
        input=input_text,
        max_output_tokens=max_output_tokens,
    )
    elapsed = perf_counter() - started
    status = getattr(response, "status", None)
    output_text = getattr(response, "output_text", None)
    if status != "completed":
        reason = _incomplete_reason(response)
        detail = f", reason={reason!r}" if reason else ""
        raise RuntimeError(
            f"single-model response status was {status!r}{detail}"
        )
    if not isinstance(output_text, str) or not output_text.strip():
        raise RuntimeError("single-model response contained no output_text")
    return {
        "answer": output_text.strip(),
        "wall_clock_seconds": elapsed,
        "usage": usage.as_dict(),
    }


def _run_os_answer(
    *,
    client: Any,
    model: str,
    case: dict[str, Any],
    timeout_seconds: float,
    max_output_tokens: int,
    reasoning_effort: str,
    cumulative_usage: UsageTotals | None = None,
) -> dict[str, Any]:
    usage = UsageTotals()
    tracked = TrackingClient(
        client,
        usage,
        reasoning_effort=reasoning_effort,
        extra_usage=cumulative_usage,
    )
    provider = OpenAIProvider(
        model=model,
        client=tracked,
        timeout_seconds=timeout_seconds,
        max_output_tokens=max_output_tokens,
    )
    context = {
        "materials": case["materials"],
        "constraints": case["constraints"],
        "evidence_rule": "Use only the supplied fixed materials.",
    }
    started = perf_counter()
    result = Orchestrator(provider).run(case["question"], context=context)
    elapsed = perf_counter() - started

    synthesizer_output = result.payload_for("synthesizer").get("output")
    if not isinstance(synthesizer_output, Mapping):
        raise RuntimeError("synthesizer payload did not contain an output object")

    return {
        "answer": build_os_scoring_document(synthesizer_output),
        "plain_language_answer": result.final_answer,
        "run_id": result.run_id,
        "stages": [
            {
                "agent": stage.agent,
                "payload": stage.payload,
                "validation": _validation_to_dict(stage.validation),
                "valid": stage.validation.valid,
                "elapsed_seconds": stage.elapsed_seconds,
            }
            for stage in result.stages
        ],
        "events": list(result.events),
        "wall_clock_seconds": elapsed,
        "usage": usage.as_dict(),
    }


def _build_blind_document(
    case: dict[str, Any],
    systems: dict[str, dict[str, Any]],
    mapping: dict[str, str],
) -> str:
    lines = [
        "PILOT-001 BLIND EVALUATION",
        "",
        "QUESTION",
        case["question"],
        "",
        "FIXED MATERIALS AND CONSTRAINTS",
        json.dumps(
            {
                "materials": case["materials"],
                "constraints": case["constraints"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        "",
        "SCORING",
        "各回答を0～5点で採点：正確性、根拠対応、推論、反証、"
        "不確実性、網羅性、実行可能性、明瞭さ。",
        "回答の長さや文体だけで優劣を決めない。",
        "",
    ]
    for blind_label in BLIND_LABELS:
        system_key = mapping[blind_label]
        # Only the formatted answer is exposed. Stage payloads, run ids, agent
        # names, and the system key never reach the scorer.
        lines.extend(
            [
                f"===== ANSWER {blind_label} =====",
                _redact_run_ids(_text(systems[system_key].get("answer"))),
                "",
                "SCORES:",
                "正確性 __/5 | 根拠対応 __/5 | 推論 __/5 | 反証 __/5",
                "不確実性 __/5 | 網羅性 __/5 | 実行可能性 __/5 | 明瞭さ __/5",
                "重大な誤り・良かった点：",
                "",
            ]
        )
    return "\n".join(lines)


def _incomplete_reason(response: Any) -> str | None:
    details = getattr(response, "incomplete_details", None)
    reason = getattr(details, "reason", None)
    return reason if isinstance(reason, str) and reason else None


def _as_int(value: Any) -> int:
    return int(value) if isinstance(value, (int, float)) else 0


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _objects(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _redact_run_ids(text: str) -> str:
    """Remove run identifiers, which carry no scoring value but reveal system C."""

    return _RUN_ID_PATTERN.sub("[run-id redacted]", text)


def _validation_to_dict(report: ValidationReport) -> dict[str, Any]:
    """Serialize a validation report for the experiment record."""

    return {
        "valid": report.valid,
        "schema_valid": report.schema.valid,
        "schema_issues": [
            {
                "path": issue.path,
                "message": issue.message,
                "validator": issue.validator,
            }
            for issue in report.schema.issues
        ],
        "semantic_issues": [
            {
                "severity": issue.severity,
                "code": issue.code,
                "path": issue.path,
                "message": issue.message,
            }
            for issue in (
                report.semantic.issues if report.semantic is not None else ()
            )
        ],
    }


def _write_json(path: Path, data: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def _checkpoint_record(
    *,
    case: dict[str, Any],
    model: str,
    settings: dict[str, Any],
    systems: dict[str, dict[str, Any]],
    cumulative_usage: UsageTotals,
    failure: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the record written after each system and on failure.

    A run that dies partway through has still been paid for, so the completed
    systems, the cumulative token spend, and the failure detail are persisted
    instead of discarded.
    """

    return {
        "experiment_id": case["experiment_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "settings": settings,
        "completed_systems": [key for key in SYSTEM_KEYS if key in systems],
        "systems": systems,
        "cumulative_usage": cumulative_usage.as_dict(),
        "failure": failure,
        "complete": failure is None and len(systems) == len(SYSTEM_KEYS),
    }


def _failure_record(
    system: str | None,
    exc: BaseException,
) -> dict[str, Any]:
    """Describe a failure without copying provider error text into the artifact."""

    record: dict[str, Any] = {
        "system": system,
        "exception_type": type(exc).__name__,
        "agent": getattr(exc, "agent", None),
        "validation": None,
    }
    if isinstance(exc, AgentValidationError):
        record["validation"] = _validation_to_dict(exc.report)
    return record


if __name__ == "__main__":
    raise SystemExit(main())
