"""Cross-reference and safety validation beyond JSON Schema."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping

_ERROR = "error"
_WARNING = "warning"

_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "openai_api_key",
        re.compile(r"\bsk-(?!ant-)[A-Za-z0-9_-]{20,}\b"),
    ),
    (
        "anthropic_api_key",
        re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    ),
    (
        "github_token",
        re.compile(
            r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|"
            r"github_pat_[A-Za-z0-9_]{20,})\b"
        ),
    ),
    (
        "aws_access_key",
        re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    ),
    (
        "private_key",
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
        ),
    ),
    (
        "generic_secret_assignment",
        re.compile(
            r"(?i)\b(?:api[_ -]?key|access[_ -]?token|secret|password)\b"
            r"\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{12,}"
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class SemanticIssue:
    severity: str
    code: str
    path: str
    message: str


@dataclass(frozen=True, slots=True)
class SemanticValidationResult:
    valid: bool
    issues: tuple[SemanticIssue, ...]


class SemanticValidator:
    """Validate IDs, cross-agent references, labels, timing, and secrets."""

    def validate(
        self,
        payload: Mapping[str, Any],
        *,
        researcher_payload: Mapping[str, Any] | None = None,
        skeptic_payload: Mapping[str, Any] | None = None,
    ) -> SemanticValidationResult:
        issues: list[SemanticIssue] = []
        self._validate_timing(payload, issues)
        self._scan_secrets(payload, issues)

        agent = payload.get("agent")
        if agent == "researcher":
            self._validate_researcher(payload, issues)
        elif agent == "skeptic":
            self._validate_skeptic(payload, researcher_payload, issues)
        elif agent == "synthesizer":
            self._validate_synthesizer(
                payload,
                researcher_payload,
                skeptic_payload,
                issues,
            )
        else:
            self._add(
                issues,
                _ERROR,
                "unknown_agent",
                "$.agent",
                f"Unknown agent: {agent!r}",
            )

        issues.sort(
            key=lambda issue: (
                issue.severity != _ERROR,
                issue.path,
                issue.code,
            )
        )
        return SemanticValidationResult(
            valid=not any(issue.severity == _ERROR for issue in issues),
            issues=tuple(issues),
        )

    def _validate_researcher(
        self,
        payload: Mapping[str, Any],
        issues: list[SemanticIssue],
    ) -> None:
        output = _output(payload)
        claims = _objects(output.get("claims"))
        evidence = _objects(output.get("evidence"))

        claim_map = self._unique_index(
            claims,
            "claim_id",
            "$.output.claims",
            issues,
        )
        evidence_map = self._unique_index(
            evidence,
            "evidence_id",
            "$.output.evidence",
            issues,
        )

        for index, claim in enumerate(claims):
            claim_id = claim.get("claim_id")
            path = f"$.output.claims[{index}]"
            for evidence_id in _strings(claim.get("evidence_ids")):
                if evidence_id not in evidence_map:
                    self._add(
                        issues,
                        _ERROR,
                        "dangling_evidence_reference",
                        f"{path}.evidence_ids",
                        (
                            f"Claim {claim_id} references missing evidence "
                            f"{evidence_id}"
                        ),
                    )
                elif claim_id not in _strings(
                    evidence_map[evidence_id].get("supports_claim_ids")
                ):
                    self._add(
                        issues,
                        _WARNING,
                        "asymmetric_claim_evidence_link",
                        f"{path}.evidence_ids",
                        (
                            f"Evidence {evidence_id} does not list {claim_id} "
                            "in supports_claim_ids"
                        ),
                    )

            if (
                claim.get("verification_status") == "supported"
                and not claim.get("evidence_ids")
            ):
                self._add(
                    issues,
                    _ERROR,
                    "supported_without_evidence",
                    path,
                    f"Claim {claim_id} is supported but has no evidence",
                )

        for index, item in enumerate(evidence):
            evidence_id = item.get("evidence_id")
            path = f"$.output.evidence[{index}]"
            for claim_id in _strings(item.get("supports_claim_ids")):
                if claim_id not in claim_map:
                    self._add(
                        issues,
                        _ERROR,
                        "dangling_claim_reference",
                        f"{path}.supports_claim_ids",
                        (
                            f"Evidence {evidence_id} references missing "
                            f"claim {claim_id}"
                        ),
                    )
                elif evidence_id not in _strings(
                    claim_map[claim_id].get("evidence_ids")
                ):
                    self._add(
                        issues,
                        _WARNING,
                        "asymmetric_evidence_claim_link",
                        f"{path}.supports_claim_ids",
                        (
                            f"Claim {claim_id} does not list evidence "
                            f"{evidence_id}"
                        ),
                    )

            if item.get("source_type") == "model_memory":
                supported_fact_ids = [
                    claim_id
                    for claim_id in _strings(item.get("supports_claim_ids"))
                    if claim_map.get(claim_id, {}).get("type") == "fact"
                ]
                if supported_fact_ids:
                    self._add(
                        issues,
                        _WARNING,
                        "model_memory_fact",
                        path,
                        (
                            "Model memory is not verified evidence for fact "
                            "claims: " + ", ".join(supported_fact_ids)
                        ),
                    )

        for index, conflict in enumerate(
            _objects(output.get("conflicts"))
        ):
            for claim_id in _strings(conflict.get("claim_ids")):
                if claim_id not in claim_map:
                    self._add(
                        issues,
                        _ERROR,
                        "dangling_conflict_claim",
                        f"$.output.conflicts[{index}].claim_ids",
                        f"Conflict references missing claim {claim_id}",
                    )

    def _validate_skeptic(
        self,
        payload: Mapping[str, Any],
        researcher_payload: Mapping[str, Any] | None,
        issues: list[SemanticIssue],
    ) -> None:
        output = _output(payload)
        self._unique_index(
            _objects(output.get("issues")),
            "issue_id",
            "$.output.issues",
            issues,
        )

        if researcher_payload is None:
            if self._skeptic_has_external_refs(output):
                self._add(
                    issues,
                    _WARNING,
                    "researcher_context_missing",
                    "$",
                    (
                        "Researcher payload was not supplied; cross-agent "
                        "references were not checked"
                    ),
                )
            return

        researcher = _output(researcher_payload)
        claim_map = {
            item.get("claim_id"): item
            for item in _objects(researcher.get("claims"))
        }
        evidence_ids = {
            item.get("evidence_id")
            for item in _objects(researcher.get("evidence"))
        }

        for index, item in enumerate(_objects(output.get("issues"))):
            for claim_id in _strings(item.get("target_claim_ids")):
                if claim_id not in claim_map:
                    self._add(
                        issues,
                        _ERROR,
                        "unknown_target_claim",
                        f"$.output.issues[{index}].target_claim_ids",
                        (
                            "Issue references missing researcher claim "
                            f"{claim_id}"
                        ),
                    )

        for index, item in enumerate(
            _objects(output.get("counterarguments"))
        ):
            for evidence_id in _strings(
                item.get("supporting_evidence_ids")
            ):
                if evidence_id not in evidence_ids:
                    self._add(
                        issues,
                        _ERROR,
                        "unknown_supporting_evidence",
                        (
                            "$.output.counterarguments"
                            f"[{index}].supporting_evidence_ids"
                        ),
                        (
                            "Counterargument references missing evidence "
                            f"{evidence_id}"
                        ),
                    )

        for index, item in enumerate(
            _objects(output.get("confidence_adjustments"))
        ):
            claim_id = item.get("claim_id")
            claim = claim_map.get(claim_id)
            if claim is None:
                self._add(
                    issues,
                    _ERROR,
                    "unknown_adjusted_claim",
                    (
                        "$.output.confidence_adjustments"
                        f"[{index}].claim_id"
                    ),
                    (
                        "Confidence adjustment references missing claim "
                        f"{claim_id}"
                    ),
                )
                continue

            original = item.get("original")
            researcher_confidence = claim.get("confidence")
            if isinstance(original, (int, float)) and isinstance(
                researcher_confidence,
                (int, float),
            ):
                if abs(
                    float(original) - float(researcher_confidence)
                ) > 1e-9:
                    self._add(
                        issues,
                        _WARNING,
                        "original_confidence_mismatch",
                        (
                            "$.output.confidence_adjustments"
                            f"[{index}].original"
                        ),
                        (
                            f"Original confidence {original} does not match "
                            f"researcher value {researcher_confidence}"
                        ),
                    )

    def _validate_synthesizer(
        self,
        payload: Mapping[str, Any],
        researcher_payload: Mapping[str, Any] | None,
        skeptic_payload: Mapping[str, Any] | None,
        issues: list[SemanticIssue],
    ) -> None:
        output = _output(payload)
        conclusion = output.get("conclusion")
        if isinstance(conclusion, Mapping):
            confidence = conclusion.get("confidence")
            label = conclusion.get("confidence_label")
            if isinstance(confidence, (int, float)):
                expected = confidence_label(float(confidence))
                if label != expected:
                    self._add(
                        issues,
                        _ERROR,
                        "confidence_label_mismatch",
                        "$.output.conclusion.confidence_label",
                        (
                            f"Confidence {confidence} requires label "
                            f"{expected!r}, not {label!r}"
                        ),
                    )

        researcher = (
            _output(researcher_payload)
            if researcher_payload is not None
            else {}
        )
        skeptic = (
            _output(skeptic_payload)
            if skeptic_payload is not None
            else {}
        )
        claim_map = {
            item.get("claim_id"): item
            for item in _objects(researcher.get("claims"))
        }
        evidence_map = {
            item.get("evidence_id"): item
            for item in _objects(researcher.get("evidence"))
        }
        issue_ids = {
            item.get("issue_id")
            for item in _objects(skeptic.get("issues"))
        }

        if researcher_payload is None and (
            output.get("supported_findings") or output.get("citations")
        ):
            self._add(
                issues,
                _WARNING,
                "researcher_context_missing",
                "$",
                (
                    "Researcher payload was not supplied; claim and evidence "
                    "references were not checked"
                ),
            )
        else:
            for index, finding in enumerate(
                _objects(output.get("supported_findings"))
            ):
                claim_id = finding.get("claim_id")
                if claim_id not in claim_map:
                    self._add(
                        issues,
                        _ERROR,
                        "unknown_supported_claim",
                        (
                            "$.output.supported_findings"
                            f"[{index}].claim_id"
                        ),
                        (
                            "Supported finding references missing claim "
                            f"{claim_id}"
                        ),
                    )
                for evidence_id in _strings(finding.get("evidence_ids")):
                    if evidence_id not in evidence_map:
                        self._add(
                            issues,
                            _ERROR,
                            "unknown_finding_evidence",
                            (
                                "$.output.supported_findings"
                                f"[{index}].evidence_ids"
                            ),
                            (
                                "Supported finding references missing evidence "
                                f"{evidence_id}"
                            ),
                        )

            for index, citation in enumerate(
                _objects(output.get("citations"))
            ):
                evidence_id = citation.get("evidence_id")
                evidence = evidence_map.get(evidence_id)
                if evidence is None:
                    self._add(
                        issues,
                        _ERROR,
                        "unknown_citation_evidence",
                        f"$.output.citations[{index}].evidence_id",
                        (
                            "Citation references missing evidence "
                            f"{evidence_id}"
                        ),
                    )
                elif citation.get("locator") != evidence.get("locator"):
                    self._add(
                        issues,
                        _WARNING,
                        "citation_locator_mismatch",
                        f"$.output.citations[{index}].locator",
                        (
                            "Citation locator differs from researcher "
                            f"evidence {evidence_id}"
                        ),
                    )

        if skeptic_payload is None and output.get(
            "important_counterpoints"
        ):
            self._add(
                issues,
                _WARNING,
                "skeptic_context_missing",
                "$",
                (
                    "Skeptic payload was not supplied; issue references "
                    "were not checked"
                ),
            )
        else:
            for index, counterpoint in enumerate(
                _objects(output.get("important_counterpoints"))
            ):
                issue_id = counterpoint.get("issue_id")
                if issue_id not in issue_ids:
                    self._add(
                        issues,
                        _ERROR,
                        "unknown_counterpoint_issue",
                        (
                            "$.output.important_counterpoints"
                            f"[{index}].issue_id"
                        ),
                        (
                            "Counterpoint references missing skeptic issue "
                            f"{issue_id}"
                        ),
                    )

        priorities = [
            item.get("priority")
            for item in _objects(output.get("recommended_actions"))
            if isinstance(item.get("priority"), int)
        ]
        if len(priorities) != len(set(priorities)):
            self._add(
                issues,
                _ERROR,
                "duplicate_action_priority",
                "$.output.recommended_actions",
                "Recommended action priorities must be unique",
            )
        elif priorities and sorted(priorities) != list(
            range(1, len(priorities) + 1)
        ):
            self._add(
                issues,
                _WARNING,
                "non_contiguous_action_priority",
                "$.output.recommended_actions",
                (
                    "Recommended action priorities should be contiguous "
                    "starting at 1"
                ),
            )

    def _validate_timing(
        self,
        payload: Mapping[str, Any],
        issues: list[SemanticIssue],
    ) -> None:
        started = _parse_datetime(payload.get("started_at"))
        completed = _parse_datetime(payload.get("completed_at"))
        status = payload.get("status")
        if (
            status in {"completed", "completed_with_warnings"}
            and payload.get("completed_at") is None
        ):
            self._add(
                issues,
                _ERROR,
                "missing_completion_time",
                "$.completed_at",
                f"Status {status!r} requires completed_at",
            )
        if (
            started is not None
            and completed is not None
            and completed < started
        ):
            self._add(
                issues,
                _ERROR,
                "invalid_time_order",
                "$.completed_at",
                "completed_at must not be earlier than started_at",
            )

    def _scan_secrets(
        self,
        payload: Mapping[str, Any],
        issues: list[SemanticIssue],
    ) -> None:
        seen: set[tuple[str, str]] = set()
        for path, text in _walk_strings(payload):
            for code, pattern in _SECRET_PATTERNS:
                if pattern.search(text) and (path, code) not in seen:
                    seen.add((path, code))
                    self._add(
                        issues,
                        _ERROR,
                        "secret_detected",
                        path,
                        (
                            f"Potential {code.replace('_', ' ')} detected; "
                            "redact before storage"
                        ),
                    )

    def _unique_index(
        self,
        items: list[Mapping[str, Any]],
        key: str,
        base_path: str,
        issues: list[SemanticIssue],
    ) -> dict[Any, Mapping[str, Any]]:
        result: dict[Any, Mapping[str, Any]] = {}
        for index, item in enumerate(items):
            value = item.get(key)
            if value in result:
                self._add(
                    issues,
                    _ERROR,
                    "duplicate_id",
                    f"{base_path}[{index}].{key}",
                    f"Duplicate identifier: {value}",
                )
            else:
                result[value] = item
        return result

    @staticmethod
    def _skeptic_has_external_refs(output: Mapping[str, Any]) -> bool:
        return any(
            item.get("target_claim_ids")
            for item in _objects(output.get("issues"))
        ) or any(
            item.get("supporting_evidence_ids")
            for item in _objects(output.get("counterarguments"))
        ) or bool(output.get("confidence_adjustments"))

    @staticmethod
    def _add(
        issues: list[SemanticIssue],
        severity: str,
        code: str,
        path: str,
        message: str,
    ) -> None:
        issues.append(
            SemanticIssue(
                severity=severity,
                code=code,
                path=path,
                message=message,
            )
        )


def confidence_label(value: float) -> str:
    """Map a confidence value to the protocol's label bands."""

    if not 0 <= value <= 1:
        raise ValueError("confidence must be between 0 and 1")
    if value < 0.20:
        return "very_low"
    if value < 0.40:
        return "low"
    if value < 0.60:
        return "medium"
    if value < 0.80:
        return "high"
    return "very_high"


def _output(
    payload: Mapping[str, Any] | None,
) -> Mapping[str, Any]:
    if payload is None:
        return {}
    output = payload.get("output")
    return output if isinstance(output, Mapping) else payload


def _objects(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _walk_strings(
    value: Any,
    path: str = "$",
) -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk_strings(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_strings(child, f"{path}[{index}]")


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
