"""Offline regression tests for the first A/B/C pilot experiment."""

from __future__ import annotations

import json
import sys
import types
from types import SimpleNamespace

import pytest

import experiments.pilot_001_ab_compare as pilot
from experiments.pilot_001_ab_compare import (
    DEFAULT_CASE_PATH,
    SCORING_SECTIONS,
    TrackingClient,
    UsageTotals,
    _build_blind_document,
    _load_case,
    build_os_scoring_document,
    main,
)


def test_pilot_case_contains_reference_checks() -> None:
    case = _load_case(DEFAULT_CASE_PATH)

    assert case["experiment_id"] == "pilot-001"
    assert len(case["materials"]) == 3
    assert [item["evidence_id"] for item in case["materials"]] == [
        "E-001",
        "E-002",
        "E-003",
    ]
    assert [item["locator"] for item in case["materials"]] == [
        "input://pilot-001/E-001",
        "input://pilot-001/E-002",
        "input://pilot-001/E-003",
    ]
    assert any(
        "クラウドLLM＋人間確認だけ" in check
        for check in case["reference_checks"]
    )


def test_pilot_defaults_to_dry_run(capsys) -> None:
    exit_code = main([])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "DRY RUN: no API request was sent." in captured.out
    assert "Paid model calls: 5 total" in captured.out
    assert "Reasoning effort: low" in captured.out
    assert "Max output tokens per call: 8000" in captured.out
    assert "Execution order: C, A, B" in captured.out


def test_usage_totals_collect_response_usage() -> None:
    totals = UsageTotals()
    response = SimpleNamespace(
        usage=SimpleNamespace(
            input_tokens=100,
            output_tokens=40,
            total_tokens=140,
        )
    )

    totals.add_response(response)

    assert totals.as_dict() == {
        "input_tokens": 100,
        "output_tokens": 40,
        "total_tokens": 140,
        "model_calls": 1,
    }


def test_tracking_client_applies_reasoning_effort() -> None:
    calls: list[dict[str, object]] = []

    class FakeResponses:
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(usage=None)

    inner = SimpleNamespace(responses=FakeResponses())
    tracked = TrackingClient(
        inner,
        UsageTotals(),
        reasoning_effort="low",
    )

    tracked.responses.create(model="test-model")

    assert calls == [
        {
            "model": "test-model",
            "reasoning": {"effort": "low"},
        }
    ]


def test_tracking_client_reports_usage_to_both_totals() -> None:
    """Per-system and cumulative spend are tracked from the same call."""

    per_system = UsageTotals()
    cumulative = UsageTotals()

    class FakeResponses:
        def create(self, **kwargs):
            return SimpleNamespace(
                usage=SimpleNamespace(
                    input_tokens=30,
                    output_tokens=10,
                    total_tokens=40,
                )
            )

    tracked = TrackingClient(
        SimpleNamespace(responses=FakeResponses()),
        per_system,
        reasoning_effort="low",
        extra_usage=cumulative,
    )
    tracked.responses.create(model="test-model")
    tracked.responses.create(model="test-model")

    assert per_system.as_dict()["model_calls"] == 2
    assert per_system.as_dict()["total_tokens"] == 80
    assert cumulative.as_dict() == per_system.as_dict()


def test_blind_document_hides_system_names() -> None:
    case = _load_case(DEFAULT_CASE_PATH)
    systems = {
        "A": {"answer": "answer-a"},
        "B": {"answer": "answer-b"},
        "C": {"answer": "answer-c"},
    }
    document = _build_blind_document(
        case,
        systems,
        {"X": "C", "Y": "A", "Z": "B"},
    )

    assert "ANSWER X" in document
    assert "answer-c" in document
    assert "FIXED MATERIALS AND CONSTRAINTS" in document
    assert "A=direct" not in document
    assert "three-agent" not in document


def synthesizer_output() -> dict:
    return {
        "direct_answer": "クラウドLLMと人間確認の組み合わせを採用する。",
        "conclusion": {
            "text": "採用できる。",
            "confidence": 0.7,
            "confidence_label": "high",
            "conditions": ["レビュー体制が維持されること"],
        },
        "supported_findings": [
            {
                "claim_id": "C-001",
                "text": "1日8時間の上限を満たすのはクラウド構成だけである。",
                "evidence_ids": ["E-002"],
                "confidence": 0.8,
            }
        ],
        "important_counterpoints": [
            {
                "issue_id": "I-001",
                "text": "外部送信によるデータ保護上の懸念が残る。",
                "impact_on_conclusion": "運用条件次第で結論が覆りうる。",
            }
        ],
        "unresolved_uncertainties": ["実測のレビュー時間が未検証である。"],
        "assumptions": ["1件あたりのレビュー時間は資料の値どおりとする。"],
        "recommended_actions": [
            {
                "priority": 2,
                "action": "レビュー時間を実測する。",
                "purpose": "容量前提を検証する。",
                "success_signal": "2週間分の実測値が揃う。",
            },
            {
                "priority": 1,
                "action": "データ保護要件を確認する。",
                "purpose": "外部送信の可否を判断する。",
                "success_signal": "法務の書面回答を得る。",
            },
        ],
        "citations": [
            {"evidence_id": "E-002", "locator": "input://pilot-001/E-002"}
        ],
        "plain_language_answer": "クラウド構成が唯一条件を満たします。",
    }


def test_os_scoring_document_contains_all_rubric_sections() -> None:
    document = build_os_scoring_document(synthesizer_output())

    for section in SCORING_SECTIONS:
        assert section in document

    # The rubric scores counterpoints, uncertainties, actions, and citations.
    # Grading plain_language_answer alone would discard all four.
    assert "外部送信によるデータ保護上の懸念" in document
    assert "実測のレビュー時間が未検証" in document
    assert "1件あたりのレビュー時間" in document
    assert "データ保護要件を確認する" in document
    assert "レビュー時間を実測する" in document
    assert "E-002" in document
    assert "input://pilot-001/E-002" in document


def test_os_scoring_document_orders_actions_by_priority() -> None:
    document = build_os_scoring_document(synthesizer_output())

    first = document.index("データ保護要件を確認する")
    second = document.index("レビュー時間を実測する")

    assert first < second


def test_os_scoring_document_keeps_sections_in_order() -> None:
    document = build_os_scoring_document(synthesizer_output())

    positions = [document.index(section) for section in SCORING_SECTIONS]

    assert positions == sorted(positions)


def test_missing_synthesizer_fields_do_not_drop_sections() -> None:
    document = build_os_scoring_document({"direct_answer": "結論のみ"})

    for section in SCORING_SECTIONS:
        assert section in document


def test_all_systems_share_the_same_heading_contract() -> None:
    """A and B are told to emit the sections C is rendered into."""

    instruction = pilot._SHARED_FORMAT_INSTRUCTION
    document = build_os_scoring_document(synthesizer_output())

    for section in SCORING_SECTIONS:
        assert section in instruction
        assert section in document


def test_blind_document_redacts_run_ids_and_internal_payloads() -> None:
    case = _load_case(DEFAULT_CASE_PATH)
    systems = {
        "A": {"answer": "1. 結論\nA案。"},
        "B": {"answer": "1. 結論\nB案。"},
        "C": {
            "answer": "1. 結論\n実行ID RUN-20260804T000000000000Z-abcd1234 の結果。",
            "run_id": "RUN-20260804T000000000000Z-abcd1234",
            "plain_language_answer": "内部要約",
            "stages": [{"agent": "researcher", "payload": {"secret": "内部データ"}}],
            "events": [{"event": "agent_completed", "agent": "skeptic"}],
        },
    }
    document = _build_blind_document(
        case,
        systems,
        {"X": "C", "Y": "A", "Z": "B"},
    )

    assert "RUN-20260804T000000000000Z-abcd1234" not in document
    assert "[run-id redacted]" in document
    for leak in ("researcher", "skeptic", "synthesizer", "内部データ", "内部要約"):
        assert leak not in document
    for label in ("システムA", "システムB", "システムC"):
        assert label not in document


def _artifact_names(directory) -> list[str]:
    return sorted(path.name for path in directory.iterdir())


@pytest.fixture
def fake_openai(monkeypatch) -> None:
    """Let main() reach its execution path without an OpenAI dependency."""

    module = types.ModuleType("openai")
    module.OpenAI = lambda **kwargs: SimpleNamespace(responses=SimpleNamespace())
    monkeypatch.setitem(sys.modules, "openai", module)
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")


def _fake_system_result(answer: str) -> dict:
    return {
        "answer": answer,
        "wall_clock_seconds": 1.0,
        "usage": {
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
            "model_calls": 1,
        },
    }


def test_completed_run_writes_checkpoint_result_and_blind_file(
    monkeypatch,
    tmp_path,
    fake_openai,
) -> None:
    captured: list[str] = []

    def fake_os(**kwargs):
        return _fake_system_result("1. 結論\nC案。")

    def fake_single(**kwargs):
        captured.append(kwargs["instructions"])
        return _fake_system_result("1. 結論\n単体案。")

    monkeypatch.setattr(pilot, "_run_os_answer", fake_os)
    monkeypatch.setattr(pilot, "_run_single_answer", fake_single)

    exit_code = main(["--execute", "--artifact-dir", str(tmp_path)])

    assert exit_code == 0
    names = _artifact_names(tmp_path)
    assert any(name.endswith("_partial.json") for name in names)
    assert any(name.endswith("_blind.txt") for name in names)

    result_name = next(
        name
        for name in names
        if name.endswith(".json") and not name.endswith("_partial.json")
    )
    record = json.loads((tmp_path / result_name).read_text(encoding="utf-8"))
    assert record["complete"] is True
    assert record["completed_systems"] == ["A", "B", "C"]
    assert set(record["blind_mapping"]) == {"X", "Y", "Z"}
    assert set(record["blind_mapping"].values()) == {"A", "B", "C"}

    # Both single-model systems must be told to use the shared headings.
    assert len(captured) == 2
    for instruction in captured:
        for section in SCORING_SECTIONS:
            assert section in instruction


def test_failure_saves_partial_artifact_and_no_blind_file(
    monkeypatch,
    tmp_path,
    fake_openai,
) -> None:
    def fake_os(**kwargs):
        return _fake_system_result("1. 結論\nC案。")

    calls: list[str] = []

    def fake_single(**kwargs):
        calls.append("call")
        if len(calls) == 2:
            raise RuntimeError("simulated provider failure")
        return _fake_system_result("1. 結論\n単体案。")

    monkeypatch.setattr(pilot, "_run_os_answer", fake_os)
    monkeypatch.setattr(pilot, "_run_single_answer", fake_single)

    exit_code = main(["--execute", "--artifact-dir", str(tmp_path)])

    assert exit_code == 1
    names = _artifact_names(tmp_path)
    assert not any(name.endswith("_blind.txt") for name in names)

    partial_name = next(name for name in names if name.endswith("_partial.json"))
    record = json.loads((tmp_path / partial_name).read_text(encoding="utf-8"))

    assert record["complete"] is False
    assert record["completed_systems"] == ["A", "C"]
    assert "blind_mapping" not in record
    assert record["failure"]["system"] == "B"
    assert record["failure"]["exception_type"] == "RuntimeError"
    assert record["experiment_id"] == "pilot-001"
    assert record["model"] == "test-model"
    assert record["settings"]["reasoning_effort"] == "low"
    assert record["cumulative_usage"]["model_calls"] >= 0
    assert record["systems"]["C"]["answer"].startswith("1. 結論")
