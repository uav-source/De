"""Explicit capture semantics for bounded Day 8 traversal-token evidence."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence


CAPTURED_NONEMPTY = "CAPTURED_NONEMPTY"
CAPTURED_EMPTY_FORMAL_QUERY = "CAPTURED_EMPTY_FORMAL_QUERY"
NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW = "NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW"
NOT_CAPTURED_TRACE_DISABLED = "NOT_CAPTURED_TRACE_DISABLED"
CAPTURE_FAILED = "CAPTURE_FAILED"
OVERFLOWED = "OVERFLOWED"

CAPTURE_STATUSES = {
    CAPTURED_NONEMPTY,
    CAPTURED_EMPTY_FORMAL_QUERY,
    NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW,
    NOT_CAPTURED_TRACE_DISABLED,
    CAPTURE_FAILED,
    OVERFLOWED,
}
NOT_CAPTURED_STATUSES = {
    NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW,
    NOT_CAPTURED_TRACE_DISABLED,
}
FATAL_CAPTURE_STATUSES = {CAPTURE_FAILED, OVERFLOWED}


def resolve_token_capture_status(
    query: Mapping[str, Any],
    tokens: Sequence[Mapping[str, Any]],
    *,
    trace_enabled: bool,
    detailed_scan_start: int,
    detailed_scan_end: int,
    capture_failed: bool = False,
    overflowed: bool = False,
) -> str:
    """Resolve one formal query without treating missing evidence as empty."""
    scan = int(query["scan_index"])
    if overflowed:
        return OVERFLOWED
    if capture_failed:
        return CAPTURE_FAILED
    if not trace_enabled:
        return NOT_CAPTURED_TRACE_DISABLED
    if not detailed_scan_start <= scan <= detailed_scan_end:
        return NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW
    if tokens:
        return CAPTURED_NONEMPTY
    if int(query.get("visited_node_count", -1)) == 0:
        return CAPTURED_EMPTY_FORMAL_QUERY
    return CAPTURE_FAILED


def compare_token_capture(
    left_status: str,
    right_status: str,
    *,
    token_sequence_equal: bool | None,
) -> dict[str, Any]:
    """Return comparison applicability separately from sequence equality."""
    if left_status not in CAPTURE_STATUSES or right_status not in CAPTURE_STATUSES:
        raise ValueError("unknown token capture status")
    fatal = left_status in FATAL_CAPTURE_STATUSES or right_status in FATAL_CAPTURE_STATUSES
    not_captured = (
        left_status in NOT_CAPTURED_STATUSES
        or right_status in NOT_CAPTURED_STATUSES
    )
    comparable = (
        left_status == right_status == CAPTURED_NONEMPTY
        or left_status == right_status == CAPTURED_EMPTY_FORMAL_QUERY
    )
    return {
        "left_token_capture_status": left_status,
        "right_token_capture_status": right_status,
        "token_comparison_status":
            "APPLICABLE" if comparable else "NOT_APPLICABLE",
        "token_sequence_equal":
            bool(token_sequence_equal) if comparable else None,
        "root_cause_classification": (
            "EVIDENCE_GAP_DETAILED_TRACE_NOT_CAPTURED"
            if not_captured else
            "EVIDENCE_GAP" if not comparable else None
        ),
        "capture_gate_pass": not fatal,
    }


def status_counts(statuses: Sequence[str]) -> dict[str, int]:
    counts = Counter(statuses)
    return {status: counts.get(status, 0) for status in sorted(CAPTURE_STATUSES)}
