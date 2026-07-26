"""Day 8 pairwise range-query alignment and bounded root-cause taxonomy."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from .day8_range_query import query_identity
from .day8_traversal_analysis import (
    first_token_difference,
    missing_point_witness,
    traversal_signature,
)


CLASSIFICATIONS = {
    "QUERY_INPUT_DIVERGED",
    "SHADOW_LOGICAL_VOXEL_MEMBERSHIP_DIVERGED",
    "DELETION_FLAG_VISIBILITY_DIVERGED",
    "REBUILD_SUBTREE_VISIBILITY_DIVERGED",
    "TREE_TRAVERSAL_PRUNING_DIVERGED",
    "FORMAL_RANGE_SEARCH_RESULT_INCOMPLETE_WITH_MATCHED_LOGICAL_MEMBERSHIP",
    "TREE_SHAPE_DIFFERED_BUT_RESULT_COMPLETE",
    "SAME_QUERY_TRACE_DIFFERENT_RESULT",
    "SAME_CAPTURED_QUERY_TRACE_DIFFERENT_RESULT",
    "FULL_COVER_SUBTREE_FLATTEN_RESULT_DIVERGED",
    "NO_RANGE_SEARCH_DIVERGENCE_REPRODUCED",
    "EVIDENCE_GAP",
}


def _members(row: Mapping[str, Any], prefix: str) -> tuple[str, ...]:
    direct = row.get(prefix)
    if isinstance(direct, (tuple, list)):
        return tuple(sorted(str(value) for value in direct))
    text = str(row.get(prefix + "_hashes", ""))
    return tuple(sorted(value for value in text.split(";") if value))


def classify_query_difference(
    *,
    left_query: Mapping[str, Any],
    right_query: Mapping[str, Any],
    left_shadow: Mapping[str, Any],
    right_shadow: Mapping[str, Any],
    left_tokens: Sequence[Mapping[str, Any]],
    right_tokens: Sequence[Mapping[str, Any]],
    evidence_complete: bool = True,
    left_token_capture_status: str | None = None,
    right_token_capture_status: str | None = None,
) -> dict[str, Any]:
    capture_gap = False
    capture_subclassification: str | None = None
    if left_token_capture_status is not None or right_token_capture_status is not None:
        from .day8_token_capture_status import compare_token_capture

        if left_token_capture_status is None or right_token_capture_status is None:
            raise ValueError("both token capture statuses are required")
        capture = compare_token_capture(
            left_token_capture_status,
            right_token_capture_status,
            token_sequence_equal=None,
        )
        capture_gap = capture["token_comparison_status"] != "APPLICABLE"
        capture_subclassification = capture["root_cause_classification"]
    if capture_gap:
        classification = "EVIDENCE_GAP"
        reason = "detailed traversal tokens were not captured for both queries"
    elif not evidence_complete:
        classification = "EVIDENCE_GAP"
        reason = "required query, shadow, or traversal evidence is incomplete"
    elif any(
        left_query.get(field) != right_query.get(field)
        for field in (
            "candidate_point_sha256", "voxel_identity",
            "query_box_checksum",
        )
    ):
        classification = "QUERY_INPUT_DIVERGED"
        reason = "candidate, formal voxel, or query box differs"
    else:
        left_shadow_members = _members(left_shadow, "shadow_member")
        right_shadow_members = _members(right_shadow, "shadow_member")
        left_formal = _members(left_shadow, "formal_result")
        right_formal = _members(right_shadow, "formal_result")
        traversal_equal = (
            traversal_signature(left_tokens)
            == traversal_signature(right_tokens)
        )
        formal_equal = left_formal == right_formal
        shadow_equal = left_shadow_members == right_shadow_members
        completeness = (
            not set(left_shadow_members).symmetric_difference(left_formal)
            and not set(right_shadow_members).symmetric_difference(right_formal)
        )
        if not shadow_equal:
            classification = "SHADOW_LOGICAL_VOXEL_MEMBERSHIP_DIVERGED"
            reason = "query input matches but pre-query logical members differ"
        elif formal_equal and not traversal_equal:
            classification = "TREE_SHAPE_DIFFERED_BUT_RESULT_COMPLETE"
            reason = "traversal differs while formal result is unchanged"
        elif formal_equal:
            classification = "NO_RANGE_SEARCH_DIVERGENCE_REPRODUCED"
            reason = "query input, logical members, and formal result match"
        elif traversal_equal:
            classification = (
                "SAME_CAPTURED_QUERY_TRACE_DIFFERENT_RESULT"
                if left_token_capture_status is not None
                else "SAME_QUERY_TRACE_DIFFERENT_RESULT"
            )
            reason = "recorded query and traversal match but formal result differs"
        else:
            differing_points = sorted(set(left_formal) ^ set(right_formal))
            witnesses = [
                missing_point_witness(point, left_tokens)
                for point in differing_points
            ] + [
                missing_point_witness(point, right_tokens)
                for point in differing_points
            ]
            if any(
                item["point_deleted_when_visited"]
                or item["tree_deleted_when_visited"]
                for item in witnesses
            ):
                classification = "DELETION_FLAG_VISIBILITY_DIVERGED"
                reason = "a separating point is visited with a deleted flag"
            elif (
                int(left_query.get("rebuild_subtree_observed_count", 0))
                != int(right_query.get("rebuild_subtree_observed_count", 0))
                or int(left_query.get("rebuild_active", 0))
                != int(right_query.get("rebuild_active", 0))
            ):
                classification = "REBUILD_SUBTREE_VISIBILITY_DIVERGED"
                reason = "matched logical members have different rebuild visibility"
            elif (
                int(left_query.get("full_cover_subtree_count", 0))
                != int(right_query.get("full_cover_subtree_count", 0))
                or any(
                    a.get("query_relation") == "FULL_COVER"
                    and b.get("query_relation") == "FULL_COVER"
                    and int(a.get("subtree_flatten_result_count", 0))
                    != int(b.get("subtree_flatten_result_count", 0))
                    for a, b in zip(left_tokens, right_tokens)
                )
            ):
                classification = (
                    "FULL_COVER_SUBTREE_FLATTEN_RESULT_DIVERGED"
                )
                reason = "full-cover subtree visibility or flatten result differs"
            elif any(
                left_query.get(field) != right_query.get(field)
                for field in (
                    "no_intersection_prune_count",
                    "full_cover_subtree_count",
                    "partial_intersection_node_count",
                )
            ):
                classification = "TREE_TRAVERSAL_PRUNING_DIVERGED"
                reason = "matched logical members have different pruning path"
            elif not completeness:
                classification = (
                    "FORMAL_RANGE_SEARCH_RESULT_INCOMPLETE_"
                    "WITH_MATCHED_LOGICAL_MEMBERSHIP"
                )
                reason = "formal result omits/adds members relative to matched shadow"
            else:
                classification = "EVIDENCE_GAP"
                reason = "formal separation is not explained by bounded evidence"
    return {
        "classification": classification,
        "reason": reason,
        "root_cause_subclassification": capture_subclassification,
        "classification_schema_pass": classification in CLASSIFICATIONS,
        "bug_proven": False,
        "day9_authorized": False,
        "query_completeness_violation_is_diagnostic_not_bug_proof": True,
    }


def compare_query_runs(
    *,
    left_run_id: str,
    right_run_id: str,
    left_queries: Sequence[Mapping[str, Any]],
    right_queries: Sequence[Mapping[str, Any]],
    left_shadow_rows: Sequence[Mapping[str, Any]],
    right_shadow_rows: Sequence[Mapping[str, Any]],
    left_tokens_by_query: Mapping[int, Sequence[Mapping[str, Any]]],
    right_tokens_by_query: Mapping[int, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    left_shadow = {
        int(row["query_sequence"]): row for row in left_shadow_rows
    }
    right_shadow = {
        int(row["query_sequence"]): row for row in right_shadow_rows
    }
    count = max(len(left_queries), len(right_queries))
    first: dict[str, Any] | None = None
    previous_equal = True
    comparison_rows: list[dict[str, Any]] = []
    for index in range(count):
        left = left_queries[index] if index < len(left_queries) else None
        right = right_queries[index] if index < len(right_queries) else None
        if left is None or right is None:
            equal = False
            classification = {
                "classification": "EVIDENCE_GAP",
                "reason": "query count differs",
                "classification_schema_pass": True,
                "bug_proven": False,
                "day9_authorized": False,
            }
        else:
            left_sequence = int(left["query_sequence"])
            right_sequence = int(right["query_sequence"])
            left_s = left_shadow.get(left_sequence)
            right_s = right_shadow.get(right_sequence)
            evidence_complete = (
                left_s is not None
                and right_s is not None
                and int(left_s.get("shadow_state_accounting_pass", 0)) == 1
                and int(right_s.get("shadow_state_accounting_pass", 0)) == 1
            )
            classification = classify_query_difference(
                left_query=left,
                right_query=right,
                left_shadow=left_s or {},
                right_shadow=right_s or {},
                left_tokens=left_tokens_by_query.get(left_sequence, ()),
                right_tokens=right_tokens_by_query.get(right_sequence, ()),
                evidence_complete=evidence_complete,
            )
            equal = (
                query_identity(left) == query_identity(right)
                and _members(left_s or {}, "shadow_member")
                == _members(right_s or {}, "shadow_member")
                and _members(left_s or {}, "formal_result")
                == _members(right_s or {}, "formal_result")
            )
        row = {
            "left_run_id": left_run_id,
            "right_run_id": right_run_id,
            "aligned_query_index": index,
            "left_query_sequence":
                int(left["query_sequence"]) if left is not None else "",
            "right_query_sequence":
                int(right["query_sequence"]) if right is not None else "",
            "query_equal": int(equal),
            "classification": classification["classification"],
        }
        comparison_rows.append(row)
        if first is None and not equal:
            first = {
                **row,
                "left_query": dict(left) if left is not None else None,
                "right_query": dict(right) if right is not None else None,
                "previous_query_equal": previous_equal,
                "previous_query_index": index - 1 if index > 0 else None,
                "root_cause": classification,
                "traversal_difference": (
                    first_token_difference(
                        left_tokens_by_query.get(
                            int(left["query_sequence"]), ()
                        ) if left is not None else (),
                        right_tokens_by_query.get(
                            int(right["query_sequence"]), ()
                        ) if right is not None else (),
                    )
                ),
            }
        previous_equal = equal
    if first is None:
        first = {
            "left_run_id": left_run_id,
            "right_run_id": right_run_id,
            "first_divergent_query": None,
            "previous_query_equal": True,
            "root_cause": {
                "classification": "NO_RANGE_SEARCH_DIVERGENCE_REPRODUCED",
                "reason": "all aligned formal query results match",
                "bug_proven": False,
                "day9_authorized": False,
            },
        }
    canonical = json.dumps(
        comparison_rows, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        "schema_version": "pairwise_day8_range_query_comparison_v1",
        "left_run_id": left_run_id,
        "right_run_id": right_run_id,
        "aligned_query_count": min(len(left_queries), len(right_queries)),
        "comparison_checksum": hashlib.sha256(canonical).hexdigest(),
        "rows": comparison_rows,
        "first_divergence": first,
    }


def evaluate_day8_gate(
    run_validations: Sequence[Mapping[str, Any]],
    pairwise: Sequence[Mapping[str, Any]],
    *,
    synthetic_pass: bool,
    static_logic_unchanged: bool,
) -> dict[str, Any]:
    checks = {
        "four_complete_runs": (
            len(run_validations) == 4
            and all(
                item.get("day8_query_trace_validation_pass") is True
                for item in run_validations
            )
        ),
        "six_pairwise_comparisons": len(pairwise) == 6,
        "synthetic_fixture_pass": synthetic_pass,
        "formal_range_search_logic_unchanged_pass": static_logic_unchanged,
        "no_overflow_or_schema_error": all(
            not any(int(value) for value in item.get("overflow", {}).values())
            and int(item.get("query_schema_error_count", 0)) == 0
            for item in run_validations
        ),
    }
    return {
        "schema_version": "day8_final_gate_v1",
        **checks,
        "day8_execution_pass": all(checks.values()),
        "range_query_context_diagnostics_only": True,
        "shadow_replay_participates_in_fast_decisions": False,
        "bug_proven": False,
        "day9_authorized": False,
    }
