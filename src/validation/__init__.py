"""Validation API for AI Research Lab OS agent outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .schema_validator import (
    SchemaIssue,
    SchemaValidationResult,
    SchemaValidator,
)
from .semantic_validator import (
    SemanticIssue,
    SemanticValidationResult,
    SemanticValidator,
    confidence_label,
)


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Combined structural and semantic validation result."""

    schema: SchemaValidationResult
    semantic: SemanticValidationResult | None

    @property
    def valid(self) -> bool:
        return (
            self.schema.valid
            and self.semantic is not None
            and self.semantic.valid
        )


def validate_agent_output(
    payload: Mapping[str, Any],
    *,
    agent: str | None = None,
    researcher_payload: Mapping[str, Any] | None = None,
    skeptic_payload: Mapping[str, Any] | None = None,
    schema_validator: SchemaValidator | None = None,
    semantic_validator: SemanticValidator | None = None,
) -> ValidationReport:
    """Run schema validation first, then semantic validation if safe.

    ``agent`` names the role the caller requested. Supplying it selects the
    schema from the caller's expectation instead of the payload's self-declared
    ``agent`` field, so a payload cannot choose which contract it is judged
    against. Each agent schema also pins ``agent`` with ``const``, so a
    mismatched self-declaration is rejected during schema validation.
    """

    schema_result = (
        schema_validator or SchemaValidator()
    ).validate(payload, agent=agent)
    if not schema_result.valid:
        return ValidationReport(
            schema=schema_result,
            semantic=None,
        )

    semantic_result = (
        semantic_validator or SemanticValidator()
    ).validate(
        payload,
        researcher_payload=researcher_payload,
        skeptic_payload=skeptic_payload,
    )
    return ValidationReport(
        schema=schema_result,
        semantic=semantic_result,
    )


__all__ = [
    "SchemaIssue",
    "SchemaValidationResult",
    "SchemaValidator",
    "SemanticIssue",
    "SemanticValidationResult",
    "SemanticValidator",
    "ValidationReport",
    "confidence_label",
    "validate_agent_output",
]
