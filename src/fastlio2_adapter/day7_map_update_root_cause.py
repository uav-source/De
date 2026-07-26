"""Pairwise Day 7 map-update divergence localization and classification."""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Any, Iterable, Mapping

from .day7_map_point_identity import (
    load_snapshot_sets,
    symmetric_difference,
)
from .day7_map_update_events import load_call_summaries, load_events
from .day7_rebuild_logger_analysis import compare_logger_runs


ROOT_CAUSE_CLASSIFICATIONS = {
    "VOXEL_REPRESENTATIVE_SELECTION_DIVERGED",
    "REBUILD_LOGGER_ROUTING_DIVERGED",
    "REBUILD_LOGGER_APPLICATION_ORDER_DIVERGED",
    "REBUILD_LOGGER_APPLICATION_RESULT_DIVERGED",
    "DIRECT_TREE_INSERTION_OUTCOME_DIVERGED",
    "DELETE_OR_REINSERTION_INTERACTION_DIVERGED",
    "SAME_EVENT_TRACE_DIFFERENT_MAP_AFTER",
    "NO_MAP_UPDATE_DIVERGENCE_REPRODUCED",
    "EVIDENCE_GAP",
}

EVENT_FIELDS = (
    "candidate_point_sha256",
    "voxel_identity",
    "existing_representative_sha256",
    "selected_representative_sha256",
    "decision_context_member_count",
    "decision_context_ordered_checksum",
    "decision_context_multiset_checksum",
    "formal_outcome",
    "mutation_destination",
    "rebuild_active_at_decision",
    "rebuild_generation",
    "logical_point_count_delta_claimed",
    "logger_entry_sequence",
)


def _event_key(row: Mapping[str, Any]) -> tuple[int, int, int]:
    return (
        int(row["scan_index"]),
        int(row["call_index"]),
        int(row["batch_point_index"]),
    )


def _events_by_key(rows: Iterable[Mapping[str, Any]]) -> dict[
    tuple[int, int, int], Mapping[str, Any]
]:
    materialized = list(rows)
    result = {_event_key(row): row for row in materialized}
    if len(result) != len(materialized):
        raise ValueError("duplicate mutation event identity")
    return result


def classify_event_difference(
    left: Mapping[str, Any], right: Mapping[str, Any]
) -> str:
    if left["mutation_destination"] != right["mutation_destination"]:
        return "REBUILD_LOGGER_ROUTING_DIVERGED"
    if (
        left["selected_representative_sha256"]
        != right["selected_representative_sha256"]
        or left["existing_representative_sha256"]
        != right["existing_representative_sha256"]
    ):
        return "VOXEL_REPRESENTATIVE_SELECTION_DIVERGED"
    if left["formal_outcome"] != right["formal_outcome"]:
        outcomes = {
            str(left["formal_outcome"]),
            str(right["formal_outcome"]),
        }
        if any(
            "DELETE" in outcome or "REINSERT" in outcome
            for outcome in outcomes
        ):
            return "DELETE_OR_REINSERTION_INTERACTION_DIVERGED"
        if left["mutation_destination"] == right["mutation_destination"] == (
            "DIRECT_TREE"
        ):
            return "DIRECT_TREE_INSERTION_OUTCOME_DIVERGED"
        return "REBUILD_LOGGER_APPLICATION_RESULT_DIVERGED"
    if (
        left["decision_context_ordered_checksum"]
        != right["decision_context_ordered_checksum"]
    ):
        return "VOXEL_REPRESENTATIVE_SELECTION_DIVERGED"
    return "EVIDENCE_GAP"


def classify_pair_components(
    *,
    map_diverged: bool,
    left_event: Mapping[str, Any] | None,
    right_event: Mapping[str, Any] | None,
    logger: Mapping[str, Any],
) -> str:
    """Classify one pair without inferring a data race or algorithm bug."""

    if not map_diverged:
        return "NO_MAP_UPDATE_DIVERGENCE_REPRODUCED"
    if (left_event is None) != (right_event is None):
        return "EVIDENCE_GAP"
    if left_event is not None and right_event is not None:
        return classify_event_difference(left_event, right_event)
    if not bool(logger.get("append_multiset_equal", True)):
        return "EVIDENCE_GAP"
    if not bool(logger.get("apply_order_equal", True)):
        return "REBUILD_LOGGER_APPLICATION_ORDER_DIVERGED"
    if not bool(logger.get("apply_result_equal", True)):
        return "REBUILD_LOGGER_APPLICATION_RESULT_DIVERGED"
    return "SAME_EVENT_TRACE_DIFFERENT_MAP_AFTER"


def evaluate_day7_gate(
    gate_fields: Mapping[str, bool],
    pair_results: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    required = (
        "day7_authorization_identity_pass",
        "day7_source_path_resolution_pass",
        "day7_outcome_taxonomy_pass",
        "fast_build_pass",
        "fast_test_pass",
        "degen_targeted_test_pass",
        "degen_full_test_pass",
        "formal_fast_logic_unchanged_pass",
        "diagnostic_readonly_scope_pass",
        "day7_synthetic_trace_validation_pass",
        "four_replay_runs_complete_pass",
        "map_mutation_event_capture_pass",
        "rebuild_logger_trace_pass",
        "rebuild_commit_trace_pass",
        "map_point_identity_snapshot_pass",
        "event_trace_overflow_pass",
        "event_trace_schema_pass",
        "map_delta_accounting_pass",
        "map_point_symmetric_difference_pass",
        "six_pair_event_comparison_pass",
        "previous_event_identity_check_complete",
        "offline_analysis_lock_pass",
        "diff_scope_pass",
        "audit_package_scope_pass",
    )
    missing_or_false = [
        name for name in required if gate_fields.get(name) is not True
    ]
    pairs = list(pair_results)
    reproduced = any(
        row.get("map_insertion_divergence_reproduced") is True
        for row in pairs
    )
    evidence_gap = any(
        row.get("root_cause_classification") == "EVIDENCE_GAP"
        for row in pairs
    )
    localized_pairs = [
        row for row in pairs
        if row.get("map_insertion_divergence_reproduced") is True
        and row.get("root_cause_classification") not in {
            "EVIDENCE_GAP",
            "SAME_EVENT_TRACE_DIFFERENT_MAP_AFTER",
        }
        and row.get("event_explains_symmetric_difference") is True
        and row.get("previous_event_identity_equal") in {True, None}
    ]
    first_event_localized = reproduced and bool(localized_pairs)
    map_after_explained = (
        reproduced
        and not evidence_gap
        and all(
            row.get("event_explains_symmetric_difference") is True
            for row in pairs
            if row.get("map_insertion_divergence_reproduced") is True
        )
    )
    execution_pass = not missing_or_false
    root_cause_pass = (
        execution_pass
        and first_event_localized
        and map_after_explained
        and all(
            row.get("root_cause_classification")
            not in {"EVIDENCE_GAP", "SAME_EVENT_TRACE_DIFFERENT_MAP_AFTER"}
            for row in pairs
            if row.get("map_insertion_divergence_reproduced") is True
        )
    )
    classifications = sorted({
        str(row["root_cause_classification"])
        for row in pairs
        if row.get("map_insertion_divergence_reproduced") is True
    })
    return {
        "required_gate_count": len(required),
        "failed_required_gates": missing_or_false,
        "day7_execution_pass": execution_pass,
        "first_divergent_map_mutation_event_localized":
            first_event_localized,
        "map_after_delta_explained_pass": map_after_explained,
        "map_update_root_cause_localized": root_cause_pass,
        "day7_map_update_rebuild_root_cause_pass": root_cause_pass,
        "multiple_map_update_divergence_modes": len(classifications) > 1,
        "root_cause_classifications": classifications,
        "data_race_proven": False,
        "formal_ikdtree_bug_proven": False,
        "day8_recommended": root_cause_pass,
        "day8_authorized": False,
        "stage3_start_authorized": False,
        "fast_lio2_integration_authorized": False,
    }


def compare_run_pair(
    left_dir: Path,
    right_dir: Path,
    *,
    pair_name: str | None = None,
) -> dict[str, Any]:
    left_events = load_events(
        left_dir / "day7_map_mutation_event_index.csv"
    )
    right_events = load_events(
        right_dir / "day7_map_mutation_event_index.csv"
    )
    left_map = load_snapshot_sets(
        left_dir / "map_point_identity_snapshot_hashes.csv"
    )
    right_map = load_snapshot_sets(
        right_dir / "map_point_identity_snapshot_hashes.csv"
    )
    first_scan = None
    only_left: list[str] = []
    only_right: list[str] = []
    for scan in range(150, 171):
        before = (scan, "MAP_BEFORE")
        after = (scan, "MAP_AFTER")
        if before not in left_map or before not in right_map:
            raise ValueError("missing map-before identity snapshot")
        if after not in left_map or after not in right_map:
            raise ValueError("missing map-after identity snapshot")
        if left_map[before] == right_map[before] and (
            left_map[after] != right_map[after]
        ):
            first_scan = scan
            only_left, only_right = symmetric_difference(
                left_map[after], right_map[after]
            )
            break

    left_by_key = {_event_key(row): row for row in left_events}
    right_by_key = {_event_key(row): row for row in right_events}
    all_keys = sorted(set(left_by_key) | set(right_by_key))
    mismatch_key = None
    left_event: Mapping[str, Any] | None = None
    right_event: Mapping[str, Any] | None = None
    for key in all_keys:
        if first_scan is not None and key[0] > first_scan:
            break
        a = left_by_key.get(key)
        b = right_by_key.get(key)
        if a is None or b is None or any(
            a[field] != b[field] for field in EVENT_FIELDS
        ):
            mismatch_key = key
            left_event = a
            right_event = b
            break

    logger = compare_logger_runs(left_dir, right_dir)
    insertion_batch_equal = None
    if mismatch_key is not None:
        left_calls = {
            (int(row["scan_index"]), int(row["call_index"])): row
            for row in load_call_summaries(
                left_dir / "day7_map_mutation_call_summaries.csv"
            )
        }
        right_calls = {
            (int(row["scan_index"]), int(row["call_index"])): row
            for row in load_call_summaries(
                right_dir / "day7_map_mutation_call_summaries.csv"
            )
        }
        call_key = mismatch_key[:2]
        left_call = left_calls.get(call_key)
        right_call = right_calls.get(call_key)
        insertion_batch_equal = (
            left_call is not None
            and right_call is not None
            and left_call["input_point_count"]
            == right_call["input_point_count"]
            and left_call.get("input_ordered_checksum")
            == right_call.get("input_ordered_checksum")
            and left_call.get("input_multiset_checksum")
            == right_call.get("input_multiset_checksum")
        )
    classification = classify_pair_components(
        map_diverged=first_scan is not None,
        left_event=left_event,
        right_event=right_event,
        logger=logger,
    )

    related = set()
    if first_scan is not None:
        for row in itertools.chain(left_events, right_events):
            if int(row["scan_index"]) != first_scan:
                continue
            related.update(
                value for value in (
                    row["candidate_point_sha256"],
                    row["existing_representative_sha256"],
                    row["selected_representative_sha256"],
                ) if value
            )
        for row in itertools.chain(
            _load_logger_for_backlink(left_dir),
            _load_logger_for_backlink(right_dir),
        ):
            if row["point_sha256"]:
                related.add(row["point_sha256"])
    unexplained = sorted((set(only_left) | set(only_right)) - related)
    previous_key = None
    previous_identity_equal = None
    if mismatch_key is not None:
        preceding = [key for key in all_keys if key < mismatch_key]
        previous_key = preceding[-1] if preceding else None
        if previous_key is not None:
            previous_left = left_by_key.get(previous_key)
            previous_right = right_by_key.get(previous_key)
            previous_identity_equal = (
                previous_left is not None
                and previous_right is not None
                and all(
                    previous_left[field] == previous_right[field]
                    for field in EVENT_FIELDS
                )
            )
    return {
        "run_pair": pair_name or f"{left_dir.name}-{right_dir.name}",
        "map_insertion_divergence_reproduced": first_scan is not None,
        "scan_index": first_scan,
        "call_index": mismatch_key[1] if mismatch_key else None,
        "batch_point_index": mismatch_key[2] if mismatch_key else None,
        "batch_kind": left_event.get("batch_kind") if left_event else None,
        "candidate_point_sha256":
            left_event.get("candidate_point_sha256") if left_event else None,
        "run_a_candidate_point_sha256":
            left_event.get("candidate_point_sha256") if left_event else None,
        "run_b_candidate_point_sha256":
            right_event.get("candidate_point_sha256") if right_event else None,
        "candidate_identity_equal": (
            left_event.get("candidate_point_sha256")
            == right_event.get("candidate_point_sha256")
        ) if left_event and right_event else None,
        "voxel_identity":
            left_event.get("voxel_identity") if left_event else None,
        "run_a_outcome":
            left_event.get("formal_outcome") if left_event else None,
        "run_b_outcome":
            right_event.get("formal_outcome") if right_event else None,
        "run_a_destination":
            left_event.get("mutation_destination") if left_event else None,
        "run_b_destination":
            right_event.get("mutation_destination") if right_event else None,
        "run_a_existing_representative":
            left_event.get("existing_representative_sha256")
            if left_event else None,
        "run_b_existing_representative":
            right_event.get("existing_representative_sha256")
            if right_event else None,
        "run_a_selected_representative":
            left_event.get("selected_representative_sha256")
            if left_event else None,
        "run_b_selected_representative":
            right_event.get("selected_representative_sha256")
            if right_event else None,
        "decision_context_equal":
            (
                left_event.get("decision_context_ordered_checksum")
                == right_event.get("decision_context_ordered_checksum")
            ) if left_event and right_event else None,
        "map_before_point_set_equal": first_scan is not None,
        "insertion_batch_equal": insertion_batch_equal,
        "rebuild_active_equal":
            (
                left_event.get("rebuild_active_at_decision")
                == right_event.get("rebuild_active_at_decision")
            ) if left_event and right_event else None,
        "rebuild_generation_equal":
            (
                left_event.get("rebuild_generation")
                == right_event.get("rebuild_generation")
            ) if left_event and right_event else None,
        "map_after_only_run_a": only_left,
        "map_after_only_run_b": only_right,
        "event_explains_symmetric_difference": not unexplained,
        "unexplained_map_point_identities": unexplained,
        "previous_event_key": previous_key,
        "previous_event_identity_equal": previous_identity_equal,
        "logger_trace_equal": logger["logger_trace_equal"],
        "logger_append_multiset_equal": logger["append_multiset_equal"],
        "logger_append_order_equal": logger["append_order_equal"],
        "logger_apply_order_equal": logger["apply_order_equal"],
        "logger_apply_result_equal": logger["apply_result_equal"],
        "logger_first_mismatch_index": logger["first_mismatch_index"],
        "root_cause_classification": classification,
        "data_race_proven": False,
        "formal_ikdtree_bug_proven": False,
    }


def _load_logger_for_backlink(run_dir: Path) -> list[dict[str, str]]:
    import csv

    with (
        run_dir / "day7_rebuild_logger_event_index.csv"
    ).open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))
