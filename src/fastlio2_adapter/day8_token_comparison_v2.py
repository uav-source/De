"""Strict TOKEN_CAPTURE_SEMANTICS_V2 comparison and propagation helpers."""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping, Optional, Sequence

from .day8_token_capture_status import (
    CAPTURED_EMPTY_FORMAL_QUERY,
    CAPTURED_NONEMPTY,
    CAPTURE_STATUSES,
    CAPTURE_FAILED,
    FATAL_CAPTURE_STATUSES,
    NOT_CAPTURED_STATUSES,
    OVERFLOWED,
)
from .day8_traversal_analysis import TOKEN_FIELDS


SEMANTICS_VERSION = "TOKEN_CAPTURE_SEMANTICS_V2"
APPLICABLE = "APPLICABLE"
NOT_APPLICABLE = "NOT_APPLICABLE"
EVIDENCE_GAP = "EVIDENCE_GAP"
EVIDENCE_GAP_NOT_CAPTURED = (
    "EVIDENCE_GAP_DETAILED_TRACE_NOT_CAPTURED"
)


def _canonical_tokens(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {field: row.get(field) for field in TOKEN_FIELDS}
        for row in rows
    ]


def compare_token_sequences(
    left_status: str,
    right_status: str,
    left_tokens: Sequence[Mapping[str, Any]],
    right_tokens: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Compare tokens without ever treating absent capture as an empty trace."""
    if left_status not in CAPTURE_STATUSES:
        raise ValueError("unknown left token capture status")
    if right_status not in CAPTURE_STATUSES:
        raise ValueError("unknown right token capture status")
    fatal = (
        left_status in FATAL_CAPTURE_STATUSES
        or right_status in FATAL_CAPTURE_STATUSES
    )
    not_captured = (
        left_status in NOT_CAPTURED_STATUSES
        or right_status in NOT_CAPTURED_STATUSES
    )
    comparable = (
        left_status == right_status == CAPTURED_NONEMPTY
        or left_status == right_status == CAPTURED_EMPTY_FORMAL_QUERY
    )
    if comparable:
        equal: Optional[bool] = (
            _canonical_tokens(left_tokens) == _canonical_tokens(right_tokens)
        )
        comparison_status = APPLICABLE
        classification: Optional[str] = None
        root_classification: Optional[str] = None
    elif not_captured:
        equal = None
        comparison_status = NOT_APPLICABLE
        classification = EVIDENCE_GAP
        root_classification = EVIDENCE_GAP_NOT_CAPTURED
    else:
        equal = None
        comparison_status = NOT_APPLICABLE
        classification = EVIDENCE_GAP
        root_classification = (
            "EVIDENCE_GAP_TOKEN_CAPTURE_FAILED_OR_OVERFLOWED"
            if fatal
            else "EVIDENCE_GAP_INCOMPARABLE_CAPTURE_STATES"
        )
    value = {
        "token_semantics_version": SEMANTICS_VERSION,
        "left_token_capture_status": left_status,
        "right_token_capture_status": right_status,
        "token_comparison_status": comparison_status,
        "token_sequence_equal": equal,
        "classification": classification,
        "root_cause_classification": root_classification,
        "capture_gate_pass": not fatal,
    }
    validate_comparison_record(value)
    return value


def validate_comparison_record(value: Mapping[str, Any]) -> None:
    """Reject every known null-token semantic regression."""
    left = value.get("left_token_capture_status")
    right = value.get("right_token_capture_status")
    if left not in CAPTURE_STATUSES or right not in CAPTURE_STATUSES:
        raise ValueError("token comparison has an unknown capture status")
    status = value.get("token_comparison_status")
    equal = value.get("token_sequence_equal")
    comparable = (
        left == right == CAPTURED_NONEMPTY
        or left == right == CAPTURED_EMPTY_FORMAL_QUERY
    )
    not_captured = (
        left in NOT_CAPTURED_STATUSES or right in NOT_CAPTURED_STATUSES
    )
    if comparable:
        if status != APPLICABLE or not isinstance(equal, bool):
            raise ValueError("captured token comparison is not applicable")
    else:
        if status != NOT_APPLICABLE or equal is not None:
            raise ValueError("non-comparable tokens must use JSON null")
    if not_captured:
        if value.get("root_cause_classification") != EVIDENCE_GAP_NOT_CAPTURED:
            raise ValueError("NOT_CAPTURED evidence gap classification missing")
        if value.get("classification") != EVIDENCE_GAP:
            raise ValueError("NOT_CAPTURED final classification must be EVIDENCE_GAP")
    if (
        left in FATAL_CAPTURE_STATUSES or right in FATAL_CAPTURE_STATUSES
    ) and value.get("capture_gate_pass") is not False:
        raise ValueError("fatal token capture state did not fail the gate")


def iter_token_comparison_records(value: Any) -> Iterable[Mapping[str, Any]]:
    """Yield nested records carrying the complete V2 comparison contract."""
    if isinstance(value, Mapping):
        required = {
            "left_token_capture_status",
            "right_token_capture_status",
            "token_comparison_status",
            "token_sequence_equal",
        }
        if required.issubset(value):
            yield value
        for item in value.values():
            yield from iter_token_comparison_records(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from iter_token_comparison_records(item)


def audit_null_token_semantics(documents: Mapping[str, Any]) -> dict[str, Any]:
    """Validate every nested output layer supplied by the caller."""
    counts: dict[str, int] = {}
    failures: list[dict[str, str]] = []
    for name, document in documents.items():
        records = list(iter_token_comparison_records(document))
        counts[name] = len(records)
        for index, record in enumerate(records):
            try:
                validate_comparison_record(record)
            except ValueError as error:
                failures.append({
                    "document": name,
                    "record_index": str(index),
                    "error": str(error),
                })
    return {
        "schema_version": "day8_null_token_semantics_audit_v2",
        "token_semantics_version": SEMANTICS_VERSION,
        "document_record_counts": counts,
        "failure_count": len(failures),
        "failures": failures,
        "NULL_TOKEN_SEMANTICS_FULLY_PROPAGATED_PASS": not failures,
    }


def json_null_roundtrip_pass() -> bool:
    value = compare_token_sequences(
        "NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW",
        "NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW",
        (),
        (),
    )
    return json.loads(json.dumps(value))["token_sequence_equal"] is None


__all__ = [
    "APPLICABLE",
    "EVIDENCE_GAP",
    "EVIDENCE_GAP_NOT_CAPTURED",
    "NOT_APPLICABLE",
    "SEMANTICS_VERSION",
    "audit_null_token_semantics",
    "compare_token_sequences",
    "json_null_roundtrip_pass",
    "validate_comparison_record",
]
