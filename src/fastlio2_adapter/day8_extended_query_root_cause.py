"""Identity-aligned Day 8 extended query comparison and root-cause gate."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from .day8_extended_traversal_analysis import (
    detailed_traversal_difference,
    first_path_explanation,
    missing_expected_point_analysis,
)
from .day8_token_comparison_v2 import (
    EVIDENCE_GAP,
    compare_token_sequences,
)


CLASSIFICATIONS = {
    "QUERY_INPUT_DIVERGED",
    "SHADOW_LOGICAL_VOXEL_MEMBERSHIP_DIVERGED",
    "DELETION_FLAG_VISIBILITY_DIVERGED",
    "REBUILD_SUBTREE_VISIBILITY_DIVERGED",
    "TREE_TRAVERSAL_PRUNING_DIVERGED",
    "FULL_COVER_SUBTREE_FLATTEN_RESULT_DIVERGED",
    "FORMAL_RANGE_SEARCH_RESULT_INCOMPLETE_WITH_MATCHED_LOGICAL_MEMBERSHIP",
    "TREE_SHAPE_DIFFERED_BUT_RESULT_COMPLETE",
    "SAME_CAPTURED_QUERY_TRACE_DIFFERENT_RESULT",
    "NO_RANGE_SEARCH_DIVERGENCE_REPRODUCED",
    "EVIDENCE_GAP",
}
EXPLANATORY_CLASSIFICATIONS = {
    "DELETION_FLAG_VISIBILITY_DIVERGED",
    "REBUILD_SUBTREE_VISIBILITY_DIVERGED",
    "TREE_TRAVERSAL_PRUNING_DIVERGED",
    "FULL_COVER_SUBTREE_FLATTEN_RESULT_DIVERGED",
}


def extended_query_identity(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        int(row["scan_index"]),
        int(row["map_mutation_call_index"]),
        str(row["batch_id"]),
        int(row["batch_point_index"]),
        str(row["candidate_point_sha256"]),
        str(row["voxel_identity"]),
        int(row["query_box_checksum"]),
    )


def _members(row: Mapping[str, Any], prefix: str) -> tuple[str, ...]:
    direct = row.get(prefix)
    if isinstance(direct, (list, tuple)):
        return tuple(sorted(str(item) for item in direct))
    return tuple(sorted(filter(
        None, str(row.get(prefix + "_hashes", "")).split(";")
    )))


def classify_extended_query_difference(
    *,
    left_query: Mapping[str, Any],
    right_query: Mapping[str, Any],
    left_shadow: Mapping[str, Any],
    right_shadow: Mapping[str, Any],
    left_status: str,
    right_status: str,
    left_tokens: Sequence[Mapping[str, Any]],
    right_tokens: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    token = compare_token_sequences(
        left_status, right_status, left_tokens, right_tokens
    )
    left_shadow_members = _members(left_shadow, "shadow_member")
    right_shadow_members = _members(right_shadow, "shadow_member")
    left_formal = _members(left_shadow, "formal_result")
    right_formal = _members(right_shadow, "formal_result")
    if extended_query_identity(left_query) != extended_query_identity(right_query):
        classification = "QUERY_INPUT_DIVERGED"
        reason = "strict query identity differs"
    elif left_shadow_members != right_shadow_members:
        classification = "SHADOW_LOGICAL_VOXEL_MEMBERSHIP_DIVERGED"
        reason = "matched query input has different logical members"
    elif token["token_comparison_status"] != "APPLICABLE":
        classification = EVIDENCE_GAP
        reason = "detailed traversal evidence is not comparable"
    elif left_formal == right_formal:
        if token["token_sequence_equal"]:
            classification = "NO_RANGE_SEARCH_DIVERGENCE_REPRODUCED"
            reason = "query, shadow members, formal result, and trace match"
        else:
            classification = "TREE_SHAPE_DIFFERED_BUT_RESULT_COMPLETE"
            reason = "captured traversal differs but formal result is complete"
    elif token["token_sequence_equal"]:
        classification = "SAME_CAPTURED_QUERY_TRACE_DIFFERENT_RESULT"
        reason = "captured trace matches but formal result differs"
    else:
        missing = sorted(set(left_formal) ^ set(right_formal))
        witness = (
            missing_expected_point_analysis(
                missing[0], left_tokens, right_tokens
            )
            if missing else None
        )
        traversal = detailed_traversal_difference(
            left_run_id=str(left_query.get("run_id", "left")),
            right_run_id=str(right_query.get("run_id", "right")),
            query_identity=json.dumps(
                extended_query_identity(left_query), separators=(",", ":")
            ),
            left_status=left_status,
            right_status=right_status,
            left_tokens=left_tokens,
            right_tokens=right_tokens,
        )
        path = first_path_explanation(traversal)
        if witness and (
            witness["point_deleted_difference"]
            or witness["tree_deleted_difference"]
        ):
            classification = "DELETION_FLAG_VISIBILITY_DIVERGED"
            reason = "expected member is visited with different deleted visibility"
        elif path["rebuild_context_diverged"]:
            classification = "REBUILD_SUBTREE_VISIBILITY_DIVERGED"
            reason = "first captured path difference is rebuild visibility"
        elif path["full_cover_flatten_diverged"]:
            classification = "FULL_COVER_SUBTREE_FLATTEN_RESULT_DIVERGED"
            reason = "full-cover flatten result count differs"
        elif (
            path["query_relation_diverged"]
            or path["child_considered_or_visited_diverged"]
            or int(left_query.get("no_intersection_prune_count", 0))
            != int(right_query.get("no_intersection_prune_count", 0))
        ):
            classification = "TREE_TRAVERSAL_PRUNING_DIVERGED"
            reason = "first captured path differs in relation, child, or prune"
        else:
            classification = (
                "FORMAL_RANGE_SEARCH_RESULT_INCOMPLETE_"
                "WITH_MATCHED_LOGICAL_MEMBERSHIP"
            )
            reason = "formal result differs with matched logical members"
    if classification not in CLASSIFICATIONS:
        raise ValueError("classification outside fixed taxonomy")
    return {
        "classification": classification,
        "reason": reason,
        "token_semantics_version": token["token_semantics_version"],
        "root_cause_classification":
            token.get("root_cause_classification"),
        "left_token_capture_status": left_status,
        "right_token_capture_status": right_status,
        "token_comparison_status": token["token_comparison_status"],
        "token_sequence_equal": token["token_sequence_equal"],
        "capture_gate_pass": token["capture_gate_pass"],
        "formal_ikdtree_bug_proven": False,
        "data_race_proven": False,
        "day9_authorized": False,
    }


def compare_extended_query_runs(
    *,
    left_run_id: str,
    right_run_id: str,
    left_queries: Sequence[Mapping[str, Any]],
    right_queries: Sequence[Mapping[str, Any]],
    left_shadow_rows: Sequence[Mapping[str, Any]],
    right_shadow_rows: Sequence[Mapping[str, Any]],
    left_tokens_by_query: Mapping[int, Sequence[Mapping[str, Any]]],
    right_tokens_by_query: Mapping[int, Sequence[Mapping[str, Any]]],
    left_status_by_query: Mapping[int, str],
    right_status_by_query: Mapping[int, str],
) -> dict[str, Any]:
    left_shadow = {
        int(row["query_sequence"]): row for row in left_shadow_rows
    }
    right_shadow = {
        int(row["query_sequence"]): row for row in right_shadow_rows
    }
    rows: list[dict[str, Any]] = []
    first: dict[str, Any] | None = None
    prior_equal = True
    for index in range(max(len(left_queries), len(right_queries))):
        left = left_queries[index] if index < len(left_queries) else None
        right = right_queries[index] if index < len(right_queries) else None
        if left is None or right is None:
            classification = {
                "classification": EVIDENCE_GAP,
                "reason": "query count differs",
                "token_semantics_version": "TOKEN_CAPTURE_SEMANTICS_V2",
                "root_cause_classification": "EVIDENCE_GAP_QUERY_COUNT",
                "left_token_capture_status": "CAPTURE_FAILED",
                "right_token_capture_status": "CAPTURE_FAILED",
                "token_comparison_status": "NOT_APPLICABLE",
                "token_sequence_equal": None,
                "capture_gate_pass": False,
            }
            equal = False
            left_sequence = right_sequence = None
        else:
            left_sequence = int(left["query_sequence"])
            right_sequence = int(right["query_sequence"])
            classification = classify_extended_query_difference(
                left_query=left,
                right_query=right,
                left_shadow=left_shadow[left_sequence],
                right_shadow=right_shadow[right_sequence],
                left_status=left_status_by_query[left_sequence],
                right_status=right_status_by_query[right_sequence],
                left_tokens=left_tokens_by_query.get(left_sequence, ()),
                right_tokens=right_tokens_by_query.get(right_sequence, ()),
            )
            equal = (
                extended_query_identity(left) == extended_query_identity(right)
                and _members(left_shadow[left_sequence], "shadow_member")
                == _members(right_shadow[right_sequence], "shadow_member")
                and _members(left_shadow[left_sequence], "formal_result")
                == _members(right_shadow[right_sequence], "formal_result")
            )
        row = {
            "left_run_id": left_run_id,
            "right_run_id": right_run_id,
            "aligned_query_index": index,
            "left_query_sequence": left_sequence,
            "right_query_sequence": right_sequence,
            "query_equal": int(equal),
            **classification,
        }
        rows.append(row)
        if first is None and not equal:
            left_tokens = (
                left_tokens_by_query.get(left_sequence, ())
                if left_sequence is not None else ()
            )
            right_tokens = (
                right_tokens_by_query.get(right_sequence, ())
                if right_sequence is not None else ()
            )
            traversal = detailed_traversal_difference(
                left_run_id=left_run_id,
                right_run_id=right_run_id,
                query_identity=json.dumps(
                    extended_query_identity(left), separators=(",", ":")
                ) if left is not None else "null",
                left_status=classification["left_token_capture_status"],
                right_status=classification["right_token_capture_status"],
                left_tokens=left_tokens,
                right_tokens=right_tokens,
            )
            first = {
                **row,
                "left_query": dict(left) if left is not None else None,
                "right_query": dict(right) if right is not None else None,
                "previous_query_equal": prior_equal,
                "previous_query_index": index - 1 if index else None,
                "root_cause": classification,
                "traversal_difference": traversal,
            }
        prior_equal = equal
    if first is None:
        first = {
            "left_run_id": left_run_id,
            "right_run_id": right_run_id,
            "aligned_query_index": None,
            "classification": "NO_RANGE_SEARCH_DIVERGENCE_REPRODUCED",
            "root_cause": {
                "classification": "NO_RANGE_SEARCH_DIVERGENCE_REPRODUCED",
                "reason": "all aligned formal query results match",
                "formal_ikdtree_bug_proven": False,
                "day9_authorized": False,
            },
            "previous_query_equal": True,
        }
    canonical = json.dumps(
        rows, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        "schema_version": "pairwise_day8_extended_query_comparison_v2",
        "left_run_id": left_run_id,
        "right_run_id": right_run_id,
        "aligned_query_count": min(len(left_queries), len(right_queries)),
        "comparison_checksum": hashlib.sha256(canonical).hexdigest(),
        "rows": rows,
        "first_divergence": first,
    }


__all__ = [
    "CLASSIFICATIONS",
    "EXPLANATORY_CLASSIFICATIONS",
    "classify_extended_query_difference",
    "compare_extended_query_runs",
    "extended_query_identity",
]
