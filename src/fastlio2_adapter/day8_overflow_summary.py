"""Metadata-safe parser for the frozen Day 8 overflow summary schema."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = "day8_query_overflow_summary_v1"
OVERFLOW_FIELDS = (
    "query_summary_overflow",
    "traversal_token_overflow",
    "formal_result_member_overflow",
    "point_voxel_pair_overflow",
)
SCHEMA_ERROR_FIELD = "schema_error_count"
REQUIRED_FIELDS = (
    "schema_version",
    *OVERFLOW_FIELDS,
    SCHEMA_ERROR_FIELD,
)


class OverflowSummaryValidationError(ValueError):
    """Structured failure for a malformed frozen overflow summary."""

    def __init__(
        self, code: str, message: str, *, field: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.field = field

    def as_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.code,
            "field": self.field,
            "message": str(self),
        }


def _count(value: Mapping[str, Any], field: str) -> int:
    if field not in value:
        raise OverflowSummaryValidationError(
            "MISSING_REQUIRED_FIELD",
            f"required overflow summary field is missing: {field}",
            field=field,
        )
    item = value[field]
    if isinstance(item, bool) or not isinstance(item, int):
        raise OverflowSummaryValidationError(
            "INVALID_COUNT_TYPE",
            f"overflow summary count must be an integer: {field}",
            field=field,
        )
    if item < 0:
        raise OverflowSummaryValidationError(
            "NEGATIVE_COUNT",
            f"overflow summary count must be nonnegative: {field}",
            field=field,
        )
    return item


def parse_overflow_summary(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate frozen fields and ignore unknown metadata during aggregation."""
    if not isinstance(value, Mapping):
        raise OverflowSummaryValidationError(
            "SUMMARY_NOT_OBJECT",
            "overflow summary must be a JSON object",
        )
    if "schema_version" not in value:
        raise OverflowSummaryValidationError(
            "MISSING_REQUIRED_FIELD",
            "required overflow summary field is missing: schema_version",
            field="schema_version",
        )
    if value["schema_version"] != SCHEMA_VERSION:
        raise OverflowSummaryValidationError(
            "SCHEMA_VERSION_MISMATCH",
            "overflow summary schema version mismatch",
            field="schema_version",
        )
    counts = {field: _count(value, field) for field in OVERFLOW_FIELDS}
    schema_error_count = _count(value, SCHEMA_ERROR_FIELD)
    return {
        "schema_version": SCHEMA_VERSION,
        **counts,
        "schema_error_count": schema_error_count,
        "overflow_count": sum(counts.values()),
        "overflow_pass": not any(counts.values()),
        "schema_pass": schema_error_count == 0,
        "unknown_metadata_field_count": len(set(value) - set(REQUIRED_FIELDS)),
    }


def load_overflow_summary(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    return parse_overflow_summary(value)
