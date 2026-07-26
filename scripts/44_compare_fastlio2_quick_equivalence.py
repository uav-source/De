#!/usr/bin/env python3
"""Compare staged Day 5 remediation runs without ambiguous pass fields."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.runtime_equivalence import (
    CHECKSUM_FIELDS,
    HARD_MEAN_OVERHEAD_PERCENT,
    HARD_Q95_OVERHEAD_PERCENT,
    RUNTIME_WARMUP_VALID_SCAN_COUNT,
    TARGET_MEAN_OVERHEAD_PERCENT,
    TARGET_Q95_OVERHEAD_PERCENT,
    combine_equivalence_results,
    compare_final_maps,
    compare_parameter_documents,
    compare_runtime_rows,
    load_json,
    load_runtime_frames,
    load_yaml,
)


SEQUENCES = ("avia_quick_shack", "avia_outdoor_run_100hz")
PHASE_LAYOUT = {
    "baseline": {
        "labels": ("AUDIT_ONLY_R1", "AUDIT_ONLY_R2", "AUDIT_ONLY_R3"),
        "pairs": (
            ("AUDIT_ONLY_R1", "AUDIT_ONLY_R2"),
            ("AUDIT_ONLY_R1", "AUDIT_ONLY_R3"),
            ("AUDIT_ONLY_R2", "AUDIT_ONLY_R3"),
        ),
        "primary": (),
        "table": "baseline_repeatability.csv",
        "gate": "BASELINE_REPEATABILITY_PASS",
    },
    "capture": {
        "labels": (
            "AUDIT_ONLY_R1",
            "CAPTURE_ONLY_R1",
            "CAPTURE_ONLY_R2",
            "AUDIT_ONLY_R2",
        ),
        "pairs": (
            ("AUDIT_ONLY_R1", "CAPTURE_ONLY_R1"),
            ("AUDIT_ONLY_R2", "CAPTURE_ONLY_R2"),
            ("AUDIT_ONLY_R1", "AUDIT_ONLY_R2"),
            ("CAPTURE_ONLY_R1", "CAPTURE_ONLY_R2"),
        ),
        "primary": (
            ("AUDIT_ONLY_R1", "CAPTURE_ONLY_R1"),
            ("AUDIT_ONLY_R2", "CAPTURE_ONLY_R2"),
        ),
        "table": "capture_only_equivalence.csv",
        "gate": "CAPTURE_ONLY_EQUIVALENCE_PASS",
    },
    "export": {
        "labels": (
            "AUDIT_ONLY_R1",
            "COMPACT_EXPORT_R1",
            "COMPACT_EXPORT_R2",
            "AUDIT_ONLY_R2",
        ),
        "pairs": (
            ("AUDIT_ONLY_R1", "COMPACT_EXPORT_R1"),
            ("AUDIT_ONLY_R2", "COMPACT_EXPORT_R2"),
            ("AUDIT_ONLY_R1", "AUDIT_ONLY_R2"),
            ("COMPACT_EXPORT_R1", "COMPACT_EXPORT_R2"),
        ),
        "primary": (
            ("AUDIT_ONLY_R1", "COMPACT_EXPORT_R1"),
            ("AUDIT_ONLY_R2", "COMPACT_EXPORT_R2"),
        ),
        "table": "compact_export_equivalence.csv",
        "gate": "COMPACT_EXPORT_EQUIVALENCE_PASS",
    },
}
GT_TOPIC_TOKENS = ("ground_truth", "groundtruth", "mocap", "vicon", "truth", "/gt")
FORBIDDEN_FIELD_TOKENS = (
    "pose_gt", "axis_gt", "oracle_axis", "ground_truth", "future_frame",
    "holdout_label", "harmful_label", "imu_conflict", "candidate_offsets",
)


def compare_phase(
    phase_root: Path, phase: str, output_root: Path
) -> dict[str, Any]:
    layout = PHASE_LAYOUT[phase]
    output_root.mkdir(parents=True, exist_ok=True)
    runs: dict[tuple[str, str], dict[str, Any]] = {}
    inventory: list[dict[str, Any]] = []
    for sequence in SEQUENCES:
        for label in layout["labels"]:
            directory = phase_root / sequence / label
            metadata = dict(load_json(directory / "run_metadata.json"))
            frames = load_runtime_frames(directory / "converted/runtime_frames.csv")
            tap = dict(load_json(directory / "tap_export_summary.json"))
            final_map = dict(load_json(directory / "final_map_summary.json"))
            params = dict(load_yaml(directory / "rosparams.yaml"))
            conversion = dict(
                load_json(directory / "converted/binary_conversion_summary.json")
            )
            run_summary = dict(load_json(directory / "run_summary.json"))
            detector_path = directory / "detector/detector_runtime_summary.json"
            detector = dict(load_json(detector_path)) if detector_path.exists() else None
            run = {
                "directory": directory,
                "metadata": metadata,
                "frames": frames,
                "tap": tap,
                "final_map": final_map,
                "params": params,
                "conversion": conversion,
                "run_summary": run_summary,
                "detector": detector,
            }
            runs[(sequence, label)] = run
            inventory.append(
                {
                    "phase": phase,
                    "sequence_id": sequence,
                    "run_label": label,
                    "runtime_mode": metadata["runtime_mode"],
                    "repeat_id": metadata["repeat_id"],
                    "bag_sha256": metadata["bag_sha256"],
                    "binary_sha256": metadata["fastlio2_binary_sha256_before"],
                    "runtime_audit_row_count": len(frames),
                    "observation_record_count": metadata["observation_record_count"],
                    "rosbag_exit_code": metadata["rosbag_exit_code"],
                    "roslaunch_exit_code": metadata["roslaunch_exit_code"],
                }
            )

    comparisons: list[dict[str, Any]] = []
    mismatch_rows: list[dict[str, Any]] = []
    first_divergence: list[dict[str, Any]] = []
    parameter_rows: list[dict[str, Any]] = []
    for sequence in SEQUENCES:
        for left_label, right_label in layout["pairs"]:
            comparison_id = f"{phase}:{sequence}:{left_label}_vs_{right_label}"
            runtime_result, details = compare_runtime_rows(
                runs[(sequence, left_label)]["frames"],
                runs[(sequence, right_label)]["frames"],
                comparison_id=comparison_id,
            )
            map_result = compare_final_maps(
                runs[(sequence, left_label)]["final_map"],
                runs[(sequence, right_label)]["final_map"],
            )
            result = combine_equivalence_results(runtime_result, map_result)
            result.update(
                {
                    "phase": phase,
                    "sequence_id": sequence,
                    "left_run": left_label,
                    "right_run": right_label,
                }
            )
            comparisons.append(result)
            mismatch_rows.extend(details)
            first_divergence.append(
                {
                    "phase": phase,
                    "comparison_id": comparison_id,
                    "sequence_id": sequence,
                    "first_divergence_scan_index": result[
                        "first_divergence_scan_index"
                    ],
                    "first_divergence_stage": result["first_divergence_stage"],
                }
            )
            parameter = compare_parameter_documents(
                runs[(sequence, left_label)]["params"],
                runs[(sequence, right_label)]["params"],
            )
            parameter_rows.append(
                {
                    "phase": phase,
                    "sequence_id": sequence,
                    "left_run": left_label,
                    "right_run": right_label,
                    "differing_parameter_count": parameter[
                        "differing_parameter_count"
                    ],
                    "non_allowlisted_parameter_difference_count": parameter[
                        "non_allowlisted_parameter_difference_count"
                    ],
                    "non_allowlisted_parameters": ";".join(
                        parameter["non_allowlisted_parameters"]
                    ),
                    "parameter_diff_allowlist_pass": parameter[
                        "parameter_diff_allowlist_pass"
                    ],
                }
            )

    completeness: list[dict[str, Any]] = []
    binary_rows: list[dict[str, Any]] = []
    detector_rows: list[dict[str, Any]] = []
    no_gt_rows: list[dict[str, Any]] = []
    forbidden_field_count = 0
    for (sequence, label), run in runs.items():
        frames = run["frames"]
        first_valid = sum(
            bool(row["first_valid_linearization_found"]) for row in frames
        )
        capture_count = int(run["tap"]["capture_record_count"])
        binary_count = int(run["conversion"]["observation_record_count"])
        detector = run["detector"]
        detector_count = int(detector["detector_output_count"]) if detector else 0
        schema_rejected = int(detector["schema_rejected_record_count"]) if detector else 0
        completeness.append(
            {
                "phase": phase,
                "sequence_id": sequence,
                "run_label": label,
                "first_valid_linearization_count": first_valid,
                "capture_record_count": capture_count,
                "binary_record_count": binary_count,
                "schema_rejected_record_count": schema_rejected,
                "detector_output_count": detector_count,
                "detector_output_missing_count": (
                    int(detector["detector_output_missing_count"]) if detector else 0
                ),
                "tap_drop_count": int(run["tap"]["tap_drop_count"]),
                "writer_error_count": int(run["tap"]["writer_error_count"])
                + int(run["run_summary"]["writer_error_count"]),
                "tap_call_mutation_count": sum(
                    bool(row["tap_call_mutation_detected"]) for row in frames
                ),
                "export_call_mutation_count": sum(
                    bool(row["export_call_mutation_detected"]) for row in frames
                ),
            }
        )
        conversion = run["conversion"]
        binary_rows.append(
            {
                "phase": phase,
                "sequence_id": sequence,
                "run_label": label,
                "binary_file_integrity_pass": conversion[
                    "binary_file_integrity_pass"
                ],
                "binary_checksum_failure_count": conversion[
                    "binary_checksum_failure_count"
                ],
                "truncated_record_count": conversion["truncated_record_count"],
                "runtime_record_count": conversion["runtime_record_count"],
                "observation_record_count": conversion[
                    "observation_record_count"
                ],
            }
        )
        if detector:
            detector_rows.append(
                {"phase": phase, "sequence_id": sequence, "run_label": label, **detector}
            )
        subscriptions = _subscription_topics(
            (run["directory"] / "rosnode_info.txt").read_text(
                encoding="utf-8", errors="replace"
            )
        )
        consumed = [
            topic
            for topic in subscriptions
            if any(token in topic.lower() for token in GT_TOPIC_TOKENS)
        ]
        no_gt_rows.append(
            {
                "phase": phase,
                "sequence_id": sequence,
                "run_label": label,
                "gt_topic_consumed_count": len(consumed),
                "gt_topics": ";".join(consumed),
                "no_gt_runtime_pass": not consumed,
            }
        )
        for path in (
            run["directory"] / "converted/observation_records_v3.jsonl",
            run["directory"] / "detector/detector_outputs_pass1.jsonl",
        ):
            if path.exists():
                for line in path.read_text(encoding="utf-8").splitlines():
                    forbidden_field_count += _forbidden_key_count(json.loads(line))

    overhead = _phase_overhead(runs, layout["primary"], phase)
    phase_gate = all(row["overall_equivalence_pass"] for row in comparisons)
    tap_immutable = all(row["tap_call_mutation_count"] == 0 for row in completeness)
    export_immutable = all(
        row["export_call_mutation_count"] == 0 for row in completeness
    )
    if phase == "capture":
        phase_gate = phase_gate and all(
            (
                row["capture_record_count"] == row["first_valid_linearization_count"]
                if row["run_label"].startswith("CAPTURE_ONLY")
                else row["capture_record_count"] == 0
            )
            and row["tap_drop_count"] == 0
            and row["writer_error_count"] == 0
            for row in completeness
        ) and tap_immutable and export_immutable
    if phase == "export":
        phase_gate = phase_gate and all(
            row["binary_file_integrity_pass"] for row in binary_rows
        ) and all(
            (
                row["capture_record_count"] == row["first_valid_linearization_count"]
                and row["binary_record_count"] == row["first_valid_linearization_count"]
                and row["schema_rejected_record_count"] == 0
                and row["detector_output_count"] == row["binary_record_count"]
                and row["detector_output_missing_count"] == 0
                if row["run_label"].startswith("COMPACT_EXPORT")
                else row["capture_record_count"] == 0
                and row["binary_record_count"] == 0
            )
            and row["tap_drop_count"] == 0
            and row["writer_error_count"] == 0
            for row in completeness
        ) and tap_immutable and export_immutable and all(
            row["detector_repeat_checksum_mismatch_count"] == 0
            for row in detector_rows
        )

    summary = {
        "phase": phase,
        "phase_executed": True,
        "replay_count": len(inventory),
        "successful_replay_count": sum(
            row["rosbag_exit_code"] == 0
            and row["roslaunch_exit_code"] in (0, 130)
            for row in inventory
        ),
        layout["gate"]: phase_gate,
        "TAP_IN_CALL_IMMUTABILITY_PASS": tap_immutable,
        "EXPORT_CALL_IMMUTABILITY_PASS": export_immutable,
        "PARAMETER_DIFF_ALLOWLIST_PASS": all(
            row["parameter_diff_allowlist_pass"] for row in parameter_rows
        ),
        "BINARY_FILE_INTEGRITY_PASS": all(
            row["binary_file_integrity_pass"] for row in binary_rows
        ),
        "OBSERVATION_SCHEMA_ACCEPTANCE_PASS": all(
            row["schema_rejected_record_count"] == 0 for row in completeness
        ),
        "DETECTOR_OUTPUT_COMPLETENESS_PASS": all(
            row["detector_output_missing_count"] == 0 for row in completeness
        ),
        "NO_GT_RUNTIME_PASS": all(row["no_gt_runtime_pass"] for row in no_gt_rows)
        and forbidden_field_count == 0,
        "forbidden_field_count": forbidden_field_count,
        "inventory": inventory,
        "comparisons": comparisons,
        "completeness": completeness,
        "binary_integrity": binary_rows,
        "overhead": overhead,
        "detector": detector_rows,
    }
    _write_csv(output_root / layout["table"], comparisons)
    _write_csv(output_root / f"first_divergence_{phase}.csv", first_divergence)
    _write_csv(output_root / f"parameter_diff_audit_{phase}.csv", parameter_rows)
    _write_csv(output_root / f"record_completeness_{phase}.csv", completeness)
    _write_csv(output_root / f"binary_integrity_{phase}.csv", binary_rows)
    _write_csv(output_root / f"runtime_overhead_{phase}.csv", overhead)
    _write_csv(output_root / f"no_gt_runtime_audit_{phase}.csv", no_gt_rows)
    _write_csv(output_root / f"detector_runtime_{phase}.csv", detector_rows)
    _write_csv(output_root / f"mismatch_rows_{phase}.csv", mismatch_rows)
    _write_json(output_root / f"{phase}_phase_summary.json", summary)
    return summary


def aggregate_results(output_root: Path) -> dict[str, Any]:
    phase_summaries: dict[str, dict[str, Any] | None] = {}
    for phase in PHASE_LAYOUT:
        path = output_root / f"{phase}_phase_summary.json"
        phase_summaries[phase] = dict(load_json(path)) if path.exists() else None
    baseline = phase_summaries["baseline"]
    capture = phase_summaries["capture"]
    export = phase_summaries["export"]
    all_executed = [value for value in phase_summaries.values() if value]
    inventories = [row for phase in all_executed for row in phase["inventory"]]
    comparisons = [row for phase in all_executed for row in phase["comparisons"]]
    completeness = [row for phase in all_executed for row in phase["completeness"]]
    binary_rows = [row for phase in all_executed for row in phase["binary_integrity"]]
    overhead = [row for phase in all_executed for row in phase["overhead"]]
    detector_rows = [row for phase in all_executed for row in phase["detector"]]

    source_path = output_root / "post_run_lock_verification.json"
    source = dict(load_json(source_path)) if source_path.exists() else {}
    binaries = {
        value
        for row in inventories
        for value in (row["binary_sha256"],)
    }
    checksum_totals = {
        field: sum(int(row[f"{field}_mismatch_count"]) for row in comparisons)
        for field in CHECKSUM_FIELDS
    }
    exact = lambda name: all(  # noqa: E731
        int(row.get(f"{name}_mismatch_count", 0)) == 0 for row in comparisons
    )
    overall_pairs = all(
        bool(row["overall_equivalence_pass"]) for row in comparisons
    ) if comparisons else False
    baseline_pass = bool(baseline and baseline["BASELINE_REPEATABILITY_PASS"])
    capture_pass = bool(capture and capture["CAPTURE_ONLY_EQUIVALENCE_PASS"])
    export_pass = bool(export and export["COMPACT_EXPORT_EQUIVALENCE_PASS"])
    runtime_hard = bool(overhead) and all(
        row["runtime_hard_gate"] for row in overhead
    )
    runtime_target = bool(overhead) and all(
        row["runtime_target_gate"] for row in overhead
    )
    replay_count = sum(int(phase["replay_count"]) for phase in all_executed)
    successful_replays = sum(
        int(phase["successful_replay_count"]) for phase in all_executed
    )
    no_drop_parts = {
        "TAP_BUFFER_NO_DROP_PASS": all(
            int(row["tap_drop_count"]) == 0 for row in completeness
        ) if completeness else False,
        "WRITER_NO_ERROR_PASS": all(
            int(row["writer_error_count"]) == 0 for row in completeness
        ) if completeness else False,
        "BINARY_FILE_INTEGRITY_PASS": all(
            bool(row["binary_file_integrity_pass"]) for row in binary_rows
        ) if binary_rows else False,
        "OBSERVATION_SCHEMA_ACCEPTANCE_PASS": bool(export) and all(
            int(row["schema_rejected_record_count"]) == 0
            for row in export["completeness"]
        ),
        "DETECTOR_OUTPUT_COMPLETENESS_PASS": bool(export) and all(
            int(row["detector_output_missing_count"]) == 0
            for row in export["completeness"]
        ),
    }
    no_drop = all(no_drop_parts.values())
    gates: dict[str, Any] = {
        "DAY5_SOURCE_LOCK_PASS": bool(source.get("all_locked_hashes_match", False)),
        "BAG_HASH_PASS": bool(inventories) and all(
            row["bag_sha256"]
            in {
                "05a56e75898f952766f136d1e5db64a35d202e990e3b1052558369d8384d7ffe",
                "13bde5d88ce054d88904873e924e2619153efdf5b63df7f3bbab4f16eb72a253",
            }
            for row in inventories
        ),
        "SAME_BINARY_PASS": len(binaries) == 1 and bool(binaries),
        "PARAMETER_DIFF_ALLOWLIST_PASS": bool(all_executed) and all(
            phase["PARAMETER_DIFF_ALLOWLIST_PASS"] for phase in all_executed
        ),
        "BASELINE_REPEATABILITY_PASS": baseline_pass,
        "TAP_IN_CALL_IMMUTABILITY_PASS": bool(capture and export)
        and capture["TAP_IN_CALL_IMMUTABILITY_PASS"]
        and export["TAP_IN_CALL_IMMUTABILITY_PASS"],
        "EXPORT_CALL_IMMUTABILITY_PASS": bool(capture and export)
        and capture["EXPORT_CALL_IMMUTABILITY_PASS"]
        and export["EXPORT_CALL_IMMUTABILITY_PASS"],
        "CAPTURE_ONLY_EQUIVALENCE_PASS": capture_pass,
        "COMPACT_EXPORT_EQUIVALENCE_PASS": export_pass,
        "MEASURE_GROUP_EQUIVALENCE_PASS": checksum_totals[
            "measure_group_checksum"
        ] == 0 and overall_pairs,
        "POSE_EQUIVALENCE_PASS": checksum_totals["prior_state_checksum"] == 0
        and checksum_totals["posterior_state_checksum"] == 0
        and all(row["max_position_difference_m"] <= 1e-12 for row in comparisons)
        and all(
            row["max_rotation_geodesic_difference_rad"] <= 1e-12
            for row in comparisons
        ),
        "COVARIANCE_EQUIVALENCE_PASS": checksum_totals[
            "prior_covariance_checksum"
        ] == 0
        and checksum_totals["posterior_covariance_checksum"] == 0
        and all(
            row["max_covariance_absolute_difference"] <= 1e-12
            for row in comparisons
        ),
        "FORMAL_JACOBIAN_CHECKSUM_EQUIVALENCE_PASS": checksum_totals[
            "formal_native_jacobian_checksum"
        ] == 0
        and checksum_totals["detector_jacobian_checksum"] == 0,
        "FORMAL_RESIDUAL_CHECKSUM_EQUIVALENCE_PASS": checksum_totals[
            "formal_innovation_checksum"
        ] == 0
        and checksum_totals["geometric_residual_checksum"] == 0,
        "ACCEPTED_INDEX_CHECKSUM_EQUIVALENCE_PASS": checksum_totals[
            "accepted_index_checksum"
        ] == 0,
        "CORRESPONDENCE_EQUIVALENCE_PASS": checksum_totals[
            "formal_correspondence_checksum"
        ] == 0,
        "MAP_SIZE_EQUIVALENCE_PASS": exact("map_size_after_update"),
        "FINAL_MAP_CHECKSUM_EQUIVALENCE_PASS": bool(comparisons) and all(
            row["final_map_equivalence_pass"] for row in comparisons
        ),
        **no_drop_parts,
        "DETECTOR_REPEATABILITY_PASS": bool(detector_rows) and all(
            row["detector_repeat_checksum_mismatch_count"] == 0
            for row in detector_rows
        ),
        "NO_DROP_PASS": no_drop,
        "NO_NONFINITE_PASS": bool(all_executed) and all(
            int(row.get("nonfinite_count", 0)) == 0 for row in detector_rows
        ) and all(
            int(run.get("final_map", {}).get("nonfinite_count", 0)) == 0
            for run in []
        ),
        "NO_GT_RUNTIME_PASS": bool(all_executed) and all(
            phase["NO_GT_RUNTIME_PASS"] for phase in all_executed
        ),
        "RUNTIME_HARD_GATE_PASS": runtime_hard,
        "RUNTIME_TARGET_PASS": runtime_target,
        "DAY5_DIFF_SCOPE_PASS": bool(source.get("day5_diff_scope_pass", False)),
    }
    required = [name for name in gates if name != "RUNTIME_TARGET_PASS"]
    remediation_pass = (
        replay_count == 22
        and successful_replays == 22
        and all(gates[name] for name in required)
    )
    gates["DAY5_REMEDIATION_PASS"] = remediation_pass
    gates["DAY5_RUNTIME_EQUIVALENCE_PASS"] = remediation_pass
    gates["OFF_ON_REPLAY_EQUIVALENCE_STATUS"] = (
        "PASS" if remediation_pass else "FAIL"
    )
    gates["DAY6_QUICK_DIAGNOSTICS_AUTHORIZED"] = remediation_pass
    if not baseline_pass:
        failure = "BASELINE_RUNTIME_NONDETERMINISM"
    elif not capture_pass:
        failure = "TAP_CAPTURE_SIDE_EFFECT_OR_SCHEDULING"
    elif not export_pass:
        failure = "EXPORT_SIDE_EFFECT_OR_SCHEDULING"
    elif not runtime_hard:
        failure = "RUNTIME_OVERHEAD_HARD_GATE"
    else:
        failure = "NONE"
    gates["FAILURE_CLASSIFICATION"] = failure
    gates["HARMFUL_BIAS_DETECTABILITY_STATUS"] = (
        "NOT_EVALUATED_DAY5_REMEDIATION"
    )

    _combine_csvs(output_root, "first_divergence_*.csv", "first_divergence_summary.csv")
    _combine_csvs(output_root, "parameter_diff_audit_*.csv", "parameter_diff_audit.csv")
    _combine_csvs(output_root, "record_completeness_*.csv", "record_completeness.csv")
    _combine_csvs(output_root, "binary_integrity_*.csv", "binary_integrity_summary.csv")
    _combine_csvs(output_root, "runtime_overhead_*.csv", "runtime_overhead_summary.csv")
    _combine_csvs(output_root, "no_gt_runtime_audit_*.csv", "no_gt_runtime_audit.csv")
    _combine_csvs(output_root, "detector_runtime_*.csv", "detector_runtime_summary.csv")
    _write_csv(
        output_root / "gate_summary.csv",
        [{"gate": name, "value": value} for name, value in gates.items()],
    )
    summary = {
        "run_id": "multihyp_day5_remediation_v1",
        "phase_execution_status": {
            name: value is not None for name, value in phase_summaries.items()
        },
        "phase_replay_counts": {
            name: int(value["replay_count"]) if value else 0
            for name, value in phase_summaries.items()
        },
        "planned_replay_count": 22,
        "successful_replay_count": successful_replays,
        "paired_scan_count": sum(
            int(row["paired_scan_count"]) for row in comparisons
        ),
        "missing_scan_count": sum(
            int(row["missing_scan_count"]) for row in comparisons
        ),
        "duplicate_scan_count": sum(
            int(row["duplicate_scan_count"]) for row in comparisons
        ),
        "max_position_difference_m": max(
            (float(row["max_position_difference_m"]) for row in comparisons),
            default=None,
        ),
        "max_rotation_difference_rad": max(
            (
                float(row["max_rotation_geodesic_difference_rad"])
                for row in comparisons
            ),
            default=None,
        ),
        "max_covariance_difference": max(
            (
                float(row["max_covariance_absolute_difference"])
                for row in comparisons
            ),
            default=None,
        ),
        "checksum_mismatch_counts": checksum_totals,
        "tap_call_mutation_count": sum(
            int(row["tap_call_mutation_count"]) for row in completeness
        ),
        "export_call_mutation_count": sum(
            int(row["export_call_mutation_count"]) for row in completeness
        ),
        "tap_drop_count": sum(int(row["tap_drop_count"]) for row in completeness),
        "writer_error_count": sum(
            int(row["writer_error_count"]) for row in completeness
        ),
        "binary_checksum_failure_count": sum(
            int(row["binary_checksum_failure_count"]) for row in binary_rows
        ),
        "schema_rejected_count": sum(
            int(row["schema_rejected_record_count"]) for row in completeness
        ),
        "detector_output_missing_count": sum(
            int(row["detector_output_missing_count"]) for row in completeness
        ),
        "first_divergences": [
            {
                "comparison_id": row["comparison_id"],
                "scan_index": row["first_divergence_scan_index"],
                "stage": row["first_divergence_stage"],
            }
            for row in comparisons
        ],
        "per_sequence_runtime": overhead,
        **gates,
    }
    _write_json(output_root / "day5_remediation_summary.json", summary)
    _write_json(output_root / "day5_remediation_gate_summary.json", gates)
    _write_json(
        output_root / "day5_remediation_run_manifest.json",
        {
            "run_id": "multihyp_day5_remediation_v1",
            "planned_replay_count": 22,
            "successful_replay_count": successful_replays,
            "runs": inventories,
        },
    )
    return summary


def _phase_overhead(
    runs: dict[tuple[str, str], dict[str, Any]],
    primary_pairs: tuple[tuple[str, str], ...],
    phase: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sequence in SEQUENCES:
        relative: list[float] = []
        capture: list[float] = []
        writer: list[float] = []
        for baseline_label, active_label in primary_pairs:
            baseline = {
                int(row["scan_index"]): row
                for row in runs[(sequence, baseline_label)]["frames"]
            }
            active = {
                int(row["scan_index"]): row
                for row in runs[(sequence, active_label)]["frames"]
            }
            valid = [
                index
                for index in sorted(set(baseline) & set(active))
                if baseline[index]["update_invoked"]
                and active[index]["update_invoked"]
            ][RUNTIME_WARMUP_VALID_SCAN_COUNT:]
            for index in valid:
                baseline_ns = int(baseline[index]["scan_total_runtime_ns"])
                active_ns = int(active[index]["scan_total_runtime_ns"])
                relative.append((active_ns / baseline_ns - 1.0) * 100.0)
                capture.append(float(active[index]["tap_capture_ns"]))
                writer.append(float(active[index]["binary_writer_ns"]))
        if not relative:
            continue
        mean = float(np.mean(relative))
        q95 = float(np.quantile(relative, 0.95))
        rows.append(
            {
                "phase": phase,
                "sequence_id": sequence,
                "measured_scan_count": len(relative),
                "mean_overhead_percent": mean,
                "median_overhead_percent": float(np.median(relative)),
                "q95_overhead_percent": q95,
                "max_overhead_percent": float(np.max(relative)),
                "tap_capture_mean_ns": float(np.mean(capture)),
                "tap_capture_q95_ns": float(np.quantile(capture, 0.95)),
                "binary_writer_mean_ns": float(np.mean(writer)),
                "binary_writer_q95_ns": float(np.quantile(writer, 0.95)),
                "runtime_hard_gate": mean <= HARD_MEAN_OVERHEAD_PERCENT
                and q95 <= HARD_Q95_OVERHEAD_PERCENT,
                "runtime_target_gate": mean <= TARGET_MEAN_OVERHEAD_PERCENT
                and q95 <= TARGET_Q95_OVERHEAD_PERCENT,
            }
        )
    return rows


def _subscription_topics(text: str) -> list[str]:
    topics: list[str] = []
    in_subscriptions = False
    for line in text.splitlines():
        if line.startswith("Subscriptions:"):
            in_subscriptions = True
            continue
        if in_subscriptions and line and not line.startswith(" "):
            break
        if in_subscriptions and "* /" in line:
            topics.append(line.split("* ", 1)[1].split(" ", 1)[0])
    return topics


def _forbidden_key_count(value: Any) -> int:
    if isinstance(value, dict):
        return sum(
            int(any(token in str(key).lower() for token in FORBIDDEN_FIELD_TOKENS))
            + _forbidden_key_count(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return sum(_forbidden_key_count(child) for child in value)
    return 0


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(rows[0]) if rows else ("status",)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        if rows:
            writer.writerows(rows)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _combine_csvs(output_root: Path, pattern: str, output_name: str) -> None:
    rows: list[dict[str, Any]] = []
    for path in sorted(output_root.glob(pattern)):
        if path.name == output_name:
            continue
        with path.open(newline="", encoding="utf-8") as handle:
            rows.extend(dict(row) for row in csv.DictReader(handle))
    _write_csv(output_root / output_name, rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=tuple(PHASE_LAYOUT))
    parser.add_argument("--phase-root", type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--aggregate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.aggregate:
        summary = aggregate_results(args.output_root)
        print(json.dumps(summary, sort_keys=True))
        return int(not summary["DAY5_REMEDIATION_PASS"])
    if args.phase is None or args.phase_root is None:
        raise SystemExit("--phase and --phase-root are required unless --aggregate")
    summary = compare_phase(args.phase_root, args.phase, args.output_root)
    print(json.dumps(summary, sort_keys=True))
    return int(not summary[PHASE_LAYOUT[args.phase]["gate"]])


if __name__ == "__main__":
    raise SystemExit(main())
