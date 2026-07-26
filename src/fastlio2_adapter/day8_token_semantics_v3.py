"""Fully propagated null-token semantics for Day 8 final outputs."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .day8_token_capture_status import (
    CAPTURED_EMPTY_FORMAL_QUERY,
    CAPTURED_NONEMPTY,
    CAPTURE_FAILED,
    CAPTURE_STATUSES,
    FATAL_CAPTURE_STATUSES,
    NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW,
    NOT_CAPTURED_STATUSES,
    NOT_CAPTURED_TRACE_DISABLED,
    OVERFLOWED,
)
from .day8_traversal_analysis import TOKEN_FIELDS


TOKEN_CAPTURE_SEMANTICS_VERSION = "day8_token_capture_semantics_v3"
APPLICABLE = "APPLICABLE"
NOT_APPLICABLE = "NOT_APPLICABLE"
EVIDENCE_GAP = "EVIDENCE_GAP"
EVIDENCE_GAP_NOT_CAPTURED = "EVIDENCE_GAP_DETAILED_TRACE_NOT_CAPTURED"


def _canonical_tokens(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [{field: row.get(field) for field in TOKEN_FIELDS} for row in rows]


def compare_token_sequences(
    left_status: str,
    right_status: str,
    left_tokens: Sequence[Mapping[str, Any]],
    right_tokens: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if left_status not in CAPTURE_STATUSES or right_status not in CAPTURE_STATUSES:
        raise ValueError("unknown token capture status")
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
        equal: bool | None = (
            _canonical_tokens(left_tokens) == _canonical_tokens(right_tokens)
        )
        comparison_status = APPLICABLE
        classification = None
        root = None
    else:
        equal = None
        comparison_status = NOT_APPLICABLE
        classification = EVIDENCE_GAP
        root = (
            EVIDENCE_GAP_NOT_CAPTURED
            if not_captured else
            "EVIDENCE_GAP_TOKEN_CAPTURE_FAILED_OR_OVERFLOWED"
            if fatal else
            "EVIDENCE_GAP_INCOMPARABLE_CAPTURE_STATES"
        )
    value = {
        "token_semantics_version": TOKEN_CAPTURE_SEMANTICS_VERSION,
        "left_token_capture_status": left_status,
        "right_token_capture_status": right_status,
        "token_comparison_status": comparison_status,
        "token_sequence_equal": equal,
        "classification": classification,
        "root_cause_classification": root,
        "capture_gate_pass": not fatal,
    }
    validate_token_comparison_record(value)
    return value


def validate_token_comparison_record(value: Mapping[str, Any]) -> None:
    left = value.get("left_token_capture_status")
    right = value.get("right_token_capture_status")
    if left not in CAPTURE_STATUSES or right not in CAPTURE_STATUSES:
        raise ValueError("unknown capture status in token comparison")
    comparable = (
        left == right == CAPTURED_NONEMPTY
        or left == right == CAPTURED_EMPTY_FORMAL_QUERY
    )
    status = value.get("token_comparison_status")
    equal = value.get("token_sequence_equal")
    if comparable:
        if status != APPLICABLE or not isinstance(equal, bool):
            raise ValueError("captured token comparison must be applicable")
    elif status != NOT_APPLICABLE or equal is not None:
        raise ValueError("non-comparable token sequence must be JSON null")
    if left in NOT_CAPTURED_STATUSES or right in NOT_CAPTURED_STATUSES:
        if value.get("classification") != EVIDENCE_GAP:
            raise ValueError("NOT_CAPTURED final classification must be EVIDENCE_GAP")
        if value.get("root_cause_classification") != EVIDENCE_GAP_NOT_CAPTURED:
            raise ValueError("NOT_CAPTURED root classification mismatch")
    if (
        left in FATAL_CAPTURE_STATUSES or right in FATAL_CAPTURE_STATUSES
    ) and value.get("capture_gate_pass") is not False:
        raise ValueError("fatal capture status did not fail gate")


def iter_token_records(value: Any) -> Iterable[Mapping[str, Any]]:
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
            yield from iter_token_records(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from iter_token_records(item)


def _csv_bool_or_null(value: str) -> bool | None:
    normalized = value.strip().lower()
    if normalized == "":
        return None
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False
    raise ValueError("CSV token_sequence_equal is not boolean-or-null")


def validate_csv(path: Path) -> tuple[int, list[str]]:
    failures: list[str] = []
    count = 0
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        fields = set(reader.fieldnames or ())
        required = {
            "left_token_capture_status",
            "right_token_capture_status",
            "token_comparison_status",
            "token_sequence_equal",
        }
        if not required.issubset(fields):
            return 0, []
        for index, raw in enumerate(reader):
            count += 1
            row: dict[str, Any] = dict(raw)
            try:
                row["token_sequence_equal"] = _csv_bool_or_null(
                    raw["token_sequence_equal"]
                )
                if "capture_gate_pass" in row:
                    row["capture_gate_pass"] = (
                        str(row["capture_gate_pass"]).lower() in {"true", "1"}
                    )
                validate_token_comparison_record(row)
            except ValueError as error:
                failures.append(f"{path.name}:{index}:{error}")
    return count, failures


def audit_output_paths(paths: Sequence[Path]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    failures: list[str] = []
    for path in paths:
        if path.suffix.lower() == ".json":
            document = json.loads(path.read_text(encoding="utf-8"))
            records = list(iter_token_records(document))
            counts[str(path)] = len(records)
            for index, record in enumerate(records):
                try:
                    validate_token_comparison_record(record)
                except ValueError as error:
                    failures.append(f"{path.name}:{index}:{error}")
        elif path.suffix.lower() == ".csv":
            count, csv_failures = validate_csv(path)
            counts[str(path)] = count
            failures.extend(csv_failures)
    return {
        "schema_version": "day8_token_semantics_recursive_audit_v3",
        "token_semantics_version": TOKEN_CAPTURE_SEMANTICS_VERSION,
        "document_record_counts": counts,
        "failure_count": len(failures),
        "failures": failures,
        "NULL_TOKEN_SEMANTICS_FULLY_PROPAGATED_PASS": not failures,
    }


def json_csv_null_roundtrip_pass() -> bool:
    value = compare_token_sequences(
        NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW,
        NOT_CAPTURED_TRACE_DISABLED,
        (),
        (),
    )
    encoded = json.loads(json.dumps(value))
    return encoded["token_sequence_equal"] is None


__all__ = [
    "APPLICABLE",
    "CAPTURED_EMPTY_FORMAL_QUERY",
    "CAPTURED_NONEMPTY",
    "CAPTURE_FAILED",
    "EVIDENCE_GAP",
    "EVIDENCE_GAP_NOT_CAPTURED",
    "NOT_APPLICABLE",
    "NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW",
    "NOT_CAPTURED_TRACE_DISABLED",
    "OVERFLOWED",
    "TOKEN_CAPTURE_SEMANTICS_VERSION",
    "audit_output_paths",
    "compare_token_sequences",
    "iter_token_records",
    "json_csv_null_roundtrip_pass",
    "validate_csv",
    "validate_token_comparison_record",
]
