"""Run the first blinded A/B/C comparison experiment.

A: one direct model answer
B: one structured single-model answer
C: the three-agent AI Research Lab OS pipeline

This script makes five paid API calls only when --execute is supplied.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from orchestrator import AgentValidationError, Orchestrator
from providers import OpenAIProvider

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASE_PATH = ROOT / "experiments" / "pilot_001_case.json"
DEFAULT_ARTIFACT_DIR = ROOT / "artifacts"


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
    def __init__(self, inner: Any, usage: UsageTotals) -> None:
        self._inner = inner
        self._usage = usage

    def create(self, **kwargs: Any) -> Any:
        response = self._inner.create(**kwargs)
        self._usage.add_response(response)
        return response


class TrackingClient:
    def __init__(self, inner: Any, usage: UsageTotals) -> None:
        self.responses = TrackingResponses(inner.responses, usage)


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
        default=6000,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.timeout_seconds <= 0:
        print("ERROR: --timeout-seconds must be positive", file=sys.stderr)
        return 2
    if args.max_output_tokens < 1:
        print("ERROR: --max-output-tokens must be at least 1", file=sys.stderr)
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

    try:
        direct = _run_single_answer(
            client=base_client,
            model=model,
            usage=UsageTotals(),
            instructions=(
                "固定資料だけを使って質問に直接答えてください。"
                "資料にない事実を追加せず、採用案、却下案、計算根拠、"
                "主要リスク、追加検証項目を日本語で簡潔に示してください。"
            ),
            input_text=shared_input,
            max_output_tokens=args.max_output_tokens,
        )
        structured = _run_single_answer(
            client=base_client,
            model=model,
            usage=UsageTotals(),
            instructions=(
                "固定資料だけを使って回答してください。次の順序で検討し、"
                "最終回答には各項目を明示してください："
                "1.制約と数値の抽出、2.各案の計算、3.採用案、4.最も強い反論、"
                "5.不確実性、6.追加検証。資料にない事実は追加しないでください。"
            ),
            input_text=shared_input,
            max_output_tokens=args.max_output_tokens,
        )
        os_result = _run_os_answer(
            client=base_client,
            model=model,
            case=case,
            timeout_seconds=args.timeout_seconds,
            max_output_tokens=args.max_output_tokens,
        )
    except AgentValidationError as exc:
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
        return 1
    except Exception as exc:
        print(
            f"ERROR: experiment failed with {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1

    systems = {
        "A": direct,
        "B": structured,
        "C": os_result,
    }
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    args.artifact_dir.mkdir(parents=True, exist_ok=True)
    result_path = args.artifact_dir / f"pilot_001_{timestamp}.json"
    blind_path = args.artifact_dir / f"pilot_001_{timestamp}_blind.txt"

    blind_labels = ["X", "Y", "Z"]
    system_keys = list(systems)
    secrets.SystemRandom().shuffle(system_keys)
    blind_mapping = dict(zip(blind_labels, system_keys, strict=True))

    record = {
        "experiment_id": case["experiment_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "case": case,
        "systems": systems,
        "blind_mapping": blind_mapping,
    }
    result_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    blind_path.write_text(
        _build_blind_document(case, systems, blind_mapping),
        encoding="utf-8",
    )

    print("\nCOMPLETE")
    for key in ("A", "B", "C"):
        item = systems[key]
        usage = item["usage"]
        print(
            f"{key}: calls={usage['model_calls']} "
            f"tokens={usage['total_tokens']} "
            f"time={item['wall_clock_seconds']:.2f}s"
        )
    print(f"Full result: {result_path}")
    print(f"Blind evaluation file: {blind_path}")
    print("Do not open the full result before scoring X, Y, and Z.")
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
    instructions: str,
    input_text: str,
    max_output_tokens: int,
) -> dict[str, Any]:
    tracked = TrackingClient(client, usage)
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
        raise RuntimeError(f"single-model response status was {status!r}")
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
) -> dict[str, Any]:
    usage = UsageTotals()
    tracked = TrackingClient(client, usage)
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
    return {
        "answer": result.final_answer,
        "run_id": result.run_id,
        "stages": [
            {
                "agent": stage.agent,
                "valid": stage.validation.valid,
                "elapsed_seconds": stage.elapsed_seconds,
            }
            for stage in result.stages
        ],
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
        "FIXED MATERIALS",
    ]
    for material in case["materials"]:
        lines.append(
            f"{material['material_id']} | {material['name']}"
        )
        lines.extend(f"- {fact}" for fact in material["facts"])
        lines.append("")
    lines.append("CONSTRAINTS")
    lines.extend(f"- {constraint}" for constraint in case["constraints"])
    lines.extend(
        [
            "",
            "SCORING",
            "各回答を0～5点で採点：正確性、根拠対応、推論、反証、"
            "不確実性、網羅性、実行可能性、明瞭さ。",
            "回答の長さや文体だけで優劣を決めない。",
            "",
        ]
    )
    for blind_label in ("X", "Y", "Z"):
        system_key = mapping[blind_label]
        lines.extend(
            [
                f"===== ANSWER {blind_label} =====",
                systems[system_key]["answer"],
                "",
                "SCORES:",
                "正確性 __/5 | 根拠対応 __/5 | 推論 __/5 | 反証 __/5",
                "不確実性 __/5 | 網羅性 __/5 | 実行可能性 __/5 | 明瞭さ __/5",
                "重大な誤り・良かった点：",
                "",
            ]
        )
    return "\n".join(lines)


def _as_int(value: Any) -> int:
    return int(value) if isinstance(value, (int, float)) else 0


if __name__ == "__main__":
    raise SystemExit(main())
