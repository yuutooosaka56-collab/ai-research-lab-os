"""Regression tests for agent prompt contracts.

These tests never call a model provider. They assert only on the strings that
``build_*_prompt`` returns, so the whole module runs offline.
"""

import pytest

from prompts.researcher import build_researcher_prompt
from prompts.skeptic import build_skeptic_prompt
from prompts.synthesizer import build_synthesizer_prompt

# Mirrors the pilot-001 fixed conditions: one operator, eight hours per day,
# and two options whose human workload exceeds that ceiling.
_FIXED_CONDITION_REQUEST = {
    "question": "どの構成を採用すべきか",
    "context": {
        "materials": [
            {
                "evidence_id": "E-001",
                "locator": "input://pilot-001/E-001",
                "facts": ["人間の平均確認時間は1件70秒"],
            },
            {
                "evidence_id": "E-003",
                "locator": "input://pilot-001/E-003",
                "facts": ["平均処理時間は1件90秒"],
            },
        ],
        "constraints": [
            "処理件数は1日500件",
            "担当者は1人",
            "担当者の作業可能時間は1日8時間",
            "完全自動送信は禁止し、人間が最終承認する",
        ],
    },
}

_BUILDERS = (
    build_researcher_prompt,
    build_skeptic_prompt,
    build_synthesizer_prompt,
)


def _flat(text: str) -> str:
    """Collapse wrapped prompt text so assertions survive re-wrapping."""

    return " ".join(text.split())


def test_researcher_prompt_defines_strict_evidence_ids() -> None:
    prompt = build_researcher_prompt(
        {
            "question": "test",
            "context": {
                "materials": [
                    {
                        "evidence_id": "E-001",
                        "locator": "input://test/E-001",
                    }
                ]
            },
        }
    )

    assert "Evidence IDs: E-001, E-002" in prompt.instructions
    assert "`E-M001` is invalid" in prompt.instructions
    assert "reuse it" in prompt.instructions
    assert '"evidence_id": "E-001"' in prompt.input


def test_synthesizer_prompt_defines_confidence_boundary() -> None:
    prompt = build_synthesizer_prompt({"question": "test"})

    assert "0.40 <= confidence < 0.60: medium" in prompt.instructions
    assert "0.60 <= confidence < 0.80: high" in prompt.instructions
    assert "0.60 must be high" in prompt.instructions
    assert '"confidence": 0.60' in prompt.input
    assert '"confidence_label": "high"' in prompt.input


@pytest.mark.parametrize("builder", _BUILDERS)
def test_every_role_treats_constraints_as_hard_constraints(builder) -> None:
    """Requirements 1 and 2: constraints are fixed, not soft assumptions."""

    instructions = _flat(builder(_FIXED_CONDITION_REQUEST).instructions)

    assert "Hard constraints:" in instructions
    assert (
        "Every entry in `context.constraints` is a hard constraint."
        in instructions
    )
    assert (
        "They are not uncertain assumptions, not hypotheses, and not open "
        "questions." in instructions
    )
    assert (
        "Never relax, reinterpret, widen, or ignore a hard constraint"
        in instructions
    )
    assert (
        "Never list a hard constraint as an assumption to be tested or as an "
        "unresolved uncertainty." in instructions
    )
    assert (
        "An option that becomes viable only if a hard constraint changes is "
        "out of scope." in instructions
    )
    assert (
        "Only a contradiction between supplied materials, or between a "
        "supplied material and a constraint, may justify questioning a "
        "constraint itself." in instructions
    )


@pytest.mark.parametrize("builder", _BUILDERS)
def test_scheduling_changes_do_not_relieve_a_capacity_ceiling(builder) -> None:
    """Requirement 4: reordering work does not reduce human working time."""

    instructions = _flat(builder(_FIXED_CONDITION_REQUEST).instructions)

    assert "one operator working eight hours per day" in instructions
    assert (
        "Scheduling changes such as parallelization, batching, asynchronous "
        "execution, pipelining, or queueing reorder work; they do not reduce "
        "the total human working time an option requires, so they cannot turn "
        "an over-capacity option into a feasible one." in instructions
    )


@pytest.mark.parametrize("builder", _BUILDERS)
def test_staffing_workarounds_are_constraint_changes(builder) -> None:
    """Requirement 5: more people, shifts, overtime, auto-approval are out."""

    instructions = _flat(builder(_FIXED_CONDITION_REQUEST).instructions)

    assert (
        "Adding people, adding shifts, working overtime, outsourcing, "
        "extending the working day, and replacing a mandatory human approval "
        "step with automatic approval or full automation are all changes to "
        "hard constraints. Never present them as options available within the "
        "fixed conditions." in instructions
    )


@pytest.mark.parametrize("builder", _BUILDERS)
def test_fixed_conditions_reach_the_prompt_input(builder) -> None:
    """The constraints the rules refer to are actually serialized."""

    prompt_input = builder(_FIXED_CONDITION_REQUEST).input

    assert "担当者は1人" in prompt_input
    assert "担当者の作業可能時間は1日8時間" in prompt_input
    assert "完全自動送信は禁止し、人間が最終承認する" in prompt_input


def test_researcher_keeps_hard_constraints_out_of_assumptions() -> None:
    instructions = _flat(
        build_researcher_prompt(_FIXED_CONDITION_REQUEST).instructions
    )

    assert (
        "Test every option against the hard constraints before assigning "
        "confidence" in instructions
    )
    assert (
        "The `assumptions` array is for uncertain premises only. Never place a "
        "hard constraint there." in instructions
    )


def test_skeptic_prompt_requires_objection_eligibility() -> None:
    """Requirement 3: ineligible objections are suppressed, not softened."""

    instructions = _flat(
        build_skeptic_prompt(_FIXED_CONDITION_REQUEST).instructions
    )

    assert "Objection eligibility test." in instructions
    assert (
        "must satisfy all four checks below. If an objection fails any one of "
        "them, do not output it at all." in instructions
    )
    assert (
        "1. Constraint-compatible: it holds without relaxing, changing, or "
        "ignoring any hard constraint." in instructions
    )
    assert "2. Grounded: the supplied materials support it." in instructions
    assert (
        "3. Decision-relevant: it explains a specific causal chain or "
        "calculation that would change the conclusion under the fixed "
        "conditions." in instructions
    )
    assert "4. Sound: its arithmetic and its logic hold." in instructions
    assert (
        "Leaving an array empty is better than filling it with objections that "
        "fail this test." in instructions
    )


def test_skeptic_prompt_forbids_capacity_workaround_objections() -> None:
    instructions = _flat(
        build_skeptic_prompt(_FIXED_CONDITION_REQUEST).instructions
    )

    assert "Prohibited objections:" in instructions
    assert (
        "Any objection that assumes additional people, additional shifts, "
        "overtime, outsourcing, a longer working day, automatic approval, or "
        "full automation that the supplied materials do not state."
        in instructions
    )
    assert (
        "Any objection that parallelization, batching, asynchronous "
        "processing, or pipelining could make an option feasible when it does "
        "not reduce the total human working time that option requires."
        in instructions
    )
    assert (
        "Reordering work does not change that total, so it cannot resolve a "
        "staffing or working-hour constraint." in instructions
    )
    assert (
        'Vague possibility statements such as "this might be improvable" that '
        "change no constrained quantity." in instructions
    )


def test_synthesizer_prompt_defines_the_skeptic_adoption_gate() -> None:
    """Requirements 6 and 7: no automatic adoption, four checks, hard drop."""

    instructions = _flat(
        build_synthesizer_prompt(_FIXED_CONDITION_REQUEST).instructions
    )

    assert "Skeptic adoption gate." in instructions
    assert (
        "Skeptic output is a set of candidates, not a set of decisions. Do not "
        "adopt a Skeptic item automatically." in instructions
    )
    assert (
        "Before an issue, counterargument, or alternative hypothesis may enter "
        "`important_counterpoints`, `unresolved_uncertainties`, or "
        "`recommended_actions`, confirm all four checks:" in instructions
    )
    assert (
        "1. Hard constraints: it does not require relaxing, changing, or "
        "ignoring any hard constraint." in instructions
    )
    assert "2. Grounding: the supplied materials support it." in instructions
    assert (
        "3. Materiality: it changes the conclusion under the fixed conditions."
        in instructions
    )
    assert "4. Soundness: its arithmetic and its logic hold." in instructions
    assert (
        "If even one check fails, exclude the item from "
        "`important_counterpoints`, `unresolved_uncertainties`, and "
        "`recommended_actions`." in instructions
    )
    assert (
        "Dropping an ineligible objection is correct behaviour, not an "
        "omission" in instructions
    )


def test_synthesizer_gate_names_the_pilot_001_failure_modes() -> None:
    """The two objections pilot-001 wrongly adopted are named explicitly."""

    instructions = _flat(
        build_synthesizer_prompt(_FIXED_CONDITION_REQUEST).instructions
    )

    assert (
        "An objection that depends on adding people, adding shifts, or "
        "overtime fails check 1." in instructions
    )
    assert (
        "An objection that parallelization or batching makes an option "
        "feasible, when it does not reduce the total human working time "
        "required, fails check 3." in instructions
    )
    assert "Both must be excluded." in instructions
