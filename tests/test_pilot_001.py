"""Offline regression tests for the first A/B/C pilot experiment."""

from __future__ import annotations

from types import SimpleNamespace

from experiments.pilot_001_ab_compare import (
    DEFAULT_CASE_PATH,
    UsageTotals,
    _build_blind_document,
    _load_case,
    main,
)


def test_pilot_case_contains_reference_checks() -> None:
    case = _load_case(DEFAULT_CASE_PATH)

    assert case["experiment_id"] == "pilot-001"
    assert len(case["materials"]) == 3
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
    assert "A=direct" not in document
    assert "three-agent" not in document
