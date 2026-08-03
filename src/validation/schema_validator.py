"""JSON parsing and Draft 2020-12 schema validation for agent outputs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

_AGENT_SCHEMA_FILES = {
    "researcher": "researcher.schema.json",
    "skeptic": "skeptic.schema.json",
    "synthesizer": "synthesizer.schema.json",
}


@dataclass(frozen=True, slots=True)
class SchemaIssue:
    """One machine-readable schema validation issue."""

    path: str
    message: str
    validator: str | None = None


@dataclass(frozen=True, slots=True)
class SchemaValidationResult:
    """Result returned by :class:`SchemaValidator`."""

    valid: bool
    issues: tuple[SchemaIssue, ...]
    payload: Mapping[str, Any] | None = None


class SchemaValidator:
    """Load local schemas and validate one agent run envelope.

    Relative ``$ref`` values are resolved through an in-memory registry. No
    network access is performed while validating untrusted model output.
    """

    def __init__(self, schema_dir: str | Path | None = None) -> None:
        self.schema_dir = (
            Path(schema_dir)
            if schema_dir is not None
            else Path(__file__).resolve().parents[1] / "schemas"
        )
        self._schemas = self._load_schemas()
        self._registry = self._build_registry()
        self._validators = {
            agent: Draft202012Validator(
                self._schemas[file_name],
                registry=self._registry,
                format_checker=FormatChecker(),
            )
            for agent, file_name in _AGENT_SCHEMA_FILES.items()
        }

    def _load_schemas(self) -> dict[str, dict[str, Any]]:
        required = {"common.schema.json", *_AGENT_SCHEMA_FILES.values()}
        schemas: dict[str, dict[str, Any]] = {}
        for file_name in sorted(required):
            path = self.schema_dir / file_name
            try:
                with path.open("r", encoding="utf-8") as handle:
                    schema = json.load(handle)
            except FileNotFoundError as exc:
                raise RuntimeError(f"Schema file not found: {path}") from exc
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Schema file is not valid JSON: {path}: {exc}") from exc

            Draft202012Validator.check_schema(schema)
            schemas[file_name] = schema
        return schemas

    def _build_registry(self) -> Registry:
        resources: list[tuple[str, Resource]] = []
        for file_name, schema in self._schemas.items():
            schema_id = schema.get("$id")
            if not isinstance(schema_id, str) or not schema_id:
                raise RuntimeError(f"Schema {file_name} must define a non-empty $id")
            resources.append((schema_id, Resource.from_contents(schema)))
        return Registry().with_resources(resources)

    def parse_and_validate(
        self,
        raw: str | bytes | bytearray,
        *,
        agent: str | None = None,
    ) -> SchemaValidationResult:
        """Parse JSON and validate it, returning parse errors in the same format."""

        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            return SchemaValidationResult(
                valid=False,
                issues=(
                    SchemaIssue(
                        path="$",
                        message=f"Invalid JSON: {exc}",
                        validator="json",
                    ),
                ),
                payload=None,
            )
        return self.validate(payload, agent=agent)

    def validate(
        self,
        payload: Any,
        *,
        agent: str | None = None,
    ) -> SchemaValidationResult:
        """Validate a decoded payload against the selected agent schema."""

        if not isinstance(payload, Mapping):
            return SchemaValidationResult(
                valid=False,
                issues=(
                    SchemaIssue(
                        path="$",
                        message="Top-level JSON value must be an object",
                        validator="type",
                    ),
                ),
                payload=None,
            )

        selected_agent = agent or payload.get("agent")
        if selected_agent not in self._validators:
            allowed = ", ".join(sorted(self._validators))
            return SchemaValidationResult(
                valid=False,
                issues=(
                    SchemaIssue(
                        path="$.agent",
                        message=(
                            f"Unknown agent {selected_agent!r}; "
                            f"expected one of: {allowed}"
                        ),
                        validator="enum",
                    ),
                ),
                payload=payload,
            )

        errors = sorted(
            self._validators[selected_agent].iter_errors(payload),
            key=lambda error: (
                tuple(str(part) for part in error.absolute_path),
                error.message,
            ),
        )
        issues = tuple(
            SchemaIssue(
                path=_format_json_path(error.absolute_path),
                message=error.message,
                validator=(
                    str(error.validator) if error.validator is not None else None
                ),
            )
            for error in errors
        )
        return SchemaValidationResult(
            valid=not issues,
            issues=issues,
            payload=payload,
        )


def _format_json_path(parts: Any) -> str:
    path = "$"
    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            escaped = str(part).replace("~", "~0").replace("/", "~1")
            path += f"/{escaped}"
    return path
