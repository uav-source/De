#!/usr/bin/env python3
"""Compare the three frozen Day 6 observations at semantic field level."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.day6_branch_divergence import (  # noqa: E402
    validate_source_lock,
    write_json,
)
from fastlio2_adapter.day6_semantic_observation import (  # noqa: E402
    SEMANTIC_FIELDS,
    classify_divergence_order,
    compare_semantic_pair,
    evidence_granularity_matrix,
    first_divergence_by_field,
    first_semantic_divergence,
    load_observation_records,
    previous_record_semantic_identity,
)


PAIR_DEFINITIONS = (
    ("r1-r2", 1, 2),
    ("r1-r3", 1, 3),
    ("r2-r3", 2, 3),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def csv_value(value: Any) -> Any:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, dict)):
        return json.dumps(
            value, allow_nan=False, separators=(",", ":"), sort_keys=True
        )
    if value is None:
        return ""
    return value


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    rows = list(rows)
    if not rows:
        raise ValueError(f"cannot write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(value) for key, value in row.items()})


def jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def first_for_fields(
    first: Mapping[str, Any],
    fields: tuple[str, ...],
) -> Any:
    values = [
        value
        for field in fields
        for value in [first.get(field)]
        if value is not None
    ]
    if not values:
        return None
    return min(values, key=lambda value: int(value["record_index"]))


def covariance_summary(record: Mapping[str, Any]) -> dict[str, float]:
    raw = np.asarray(
        record["prior_covariance_detector_order_raw"], dtype=np.float64
    )
    symmetric = np.asarray(
        record["prior_covariance_detector_order_symmetric"],
        dtype=np.float64,
    )
    return {
        "prior_covariance_raw_trace": float(np.trace(raw)),
        "prior_covariance_raw_frobenius_norm": float(np.linalg.norm(raw)),
        "prior_covariance_symmetric_trace": float(np.trace(symmetric)),
        "prior_covariance_symmetric_frobenius_norm": float(
            np.linalg.norm(symmetric)
        ),
        "prior_covariance_max_asymmetry": float(
            record["prior_covariance_max_asymmetry"]
        ),
    }


def window_row(
    *,
    run_index: int,
    record_index: int,
    record: Mapping[str, Any],
    detector: Mapping[str, Any],
) -> dict[str, Any]:
    position = np.asarray(record["prior_position_world"], dtype=np.float64)
    orientation = np.asarray(
        record["prior_orientation_world_from_imu_xyzw"],
        dtype=np.float64,
    )
    row = {
        "run": f"run_{run_index}",
        "record_index": record_index,
        "scan_index": int(record["scan_index"]),
        "timestamp_begin": float(record["timestamp_begin"]),
        "timestamp_end": float(record["timestamp_end"]),
        "prior_position_world": record["prior_position_world"],
        "prior_position_norm": float(np.linalg.norm(position)),
        "prior_orientation_world_from_imu_xyzw": (
            record["prior_orientation_world_from_imu_xyzw"]
        ),
        "prior_orientation_norm": float(np.linalg.norm(orientation)),
        **covariance_summary(record),
        "valid_correspondence_count": int(
            record["valid_correspondence_count"]
        ),
        "jacobian_row_count": len(record["detector_pose_jacobian_rows"]),
        "jacobian_column_count": 6,
        "formal_native_jacobian_checksum": int(
            record["formal_native_jacobian_checksum"]
        ),
        "detector_jacobian_checksum": int(
            record["detector_jacobian_checksum"]
        ),
        "innovation_length": len(record["formal_filter_innovation_h"]),
        "formal_innovation_checksum": int(
            record["formal_innovation_checksum"]
        ),
        "geometric_residual_checksum": int(
            record["geometric_residual_checksum"]
        ),
        "accepted_index_checksum": int(record["accepted_index_checksum"]),
        "formal_correspondence_checksum": int(
            record["formal_correspondence_checksum"]
        ),
        "map_size": "NOT_OBSERVED",
        "odi_trans": float(detector["odi_trans"]),
        "ais_trans": float(detector["ais_trans"]),
        "lambda_min_trans": float(detector["lambda_min_trans"]),
        "condition_number_trans": float(
            detector["condition_number_trans"]
        ),
        "primary_eigengap_ratio": float(
            detector["primary_eigengap_ratio"]
        ),
        "primary_direction_stable": bool(
            detector["primary_direction_stable"]
        ),
        "degeneracy_triggered": bool(detector["degeneracy_triggered"]),
        "actionable_direction": bool(detector["actionable_direction"]),
        "primary_weak_direction": detector["primary_weak_direction"],
    }
    return row


def environment_audit(input_root: Path, output_root: Path) -> dict[str, Any]:
    lock = json.loads(
        (input_root / "day6_identity/day6_run_lock_redacted.json").read_text(
            encoding="utf-8"
        )
    )
    rows = []
    for index in (1, 2, 3):
        run = input_root / f"run_{index}"
        environment = json.loads(
            (
                run
                / "evidence/detector_processing/environment_identity.json"
            ).read_text(encoding="utf-8")
        )
        handshake = json.loads(
            (run / "evidence/connection_handshake/summary.json").read_text(
                encoding="utf-8"
            )
        )
        drain = json.loads(
            (run / "evidence/drain/summary.json").read_text(encoding="utf-8")
        )
        record, _ = load_observation_records(
            run / "observation_records_v3.bin"
        )
        rows.append(
            {
                "run": f"run_{index}",
                "ros_master_port": handshake["ros_master_port"],
                "cpu_affinity": lock["cpu_affinity"],
                "OMP_NUM_THREADS": environment["environment_variables"].get(
                    "OMP_NUM_THREADS"
                ),
                "OPENBLAS_NUM_THREADS": environment[
                    "environment_variables"
                ].get("OPENBLAS_NUM_THREADS"),
                "MKL_NUM_THREADS": environment[
                    "environment_variables"
                ].get("MKL_NUM_THREADS"),
                "PYTHONHASHSEED": environment["environment_variables"].get(
                    "PYTHONHASHSEED"
                ),
                "fastlio2_binary_sha256": record[0][
                    "fastlio2_binary_sha256"
                ],
                "fastlio2_source_commit": record[0]["fastlio2_commit"],
                "launch_config_bundle_sha256": record[0][
                    "config_bundle_sha256"
                ],
                "rosbag_playback_rate": lock["playback_rate"],
                "pause_start_protocol": (
                    "HANDSHAKE_THEN_UNPAUSE_THEN_FROZEN_TAIL_ADJUDICATION"
                ),
                "handshake_start_monotonic_ns": handshake[
                    "handshake_start_monotonic_ns"
                ],
                "handshake_ready_monotonic_ns": handshake[
                    "handshake_ready_monotonic_ns"
                ],
                "unpause_call_start_monotonic_ns": handshake[
                    "unpause_call_start_monotonic_ns"
                ],
                "unpause_call_end_monotonic_ns": handshake[
                    "unpause_call_end_monotonic_ns"
                ],
                "lidar_callback_count": drain["actual_lidar_callback_count"],
                "imu_callback_count": drain["actual_imu_callback_count"],
                "scheduling_trace_available": False,
                "runtime_execution_order_trace_available": False,
            }
        )
    write_csv(output_root / "cross_run_environment_identity.csv", rows)
    comparable_fields = (
        "cpu_affinity",
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "PYTHONHASHSEED",
        "fastlio2_binary_sha256",
        "fastlio2_source_commit",
        "launch_config_bundle_sha256",
        "rosbag_playback_rate",
        "pause_start_protocol",
        "lidar_callback_count",
        "imu_callback_count",
    )
    configuration_identity = all(
        all(row[field] == rows[0][field] for row in rows[1:])
        for field in comparable_fields
    )
    summary = {
        "schema_version": "day6_cross_run_environment_identity_v1",
        "run_count": 3,
        "CONFIGURATION_IDENTITY": (
            "MATCHED_EXCEPT_INTENTIONALLY_DISTINCT_ROS_MASTER_PORT"
            if configuration_identity
            else "MISMATCHED"
        ),
        "SCHEDULING_IDENTITY": "NOT_PROVEN_NO_SCHEDULING_TRACE",
        "RUNTIME_EXECUTION_ORDER_IDENTITY": (
            "NOT_PROVEN_NO_EXECUTION_ORDER_TRACE"
        ),
        "ros_master_ports": [row["ros_master_port"] for row in rows],
        "configuration_identity_pass": configuration_identity,
        "scheduling_identity_claimed": False,
        "runtime_execution_order_identity_claimed": False,
    }
    write_json(
        output_root / "cross_run_environment_identity_summary.json",
        summary,
    )
    return summary


def main() -> int:
    args = parse_args()
    input_root = args.input_root.resolve()
    output = args.output_dir.resolve()
    if output.exists():
        raise SystemExit(f"ERROR: output already exists: {output}")
    lock = json.loads(
        (input_root / "day6_branch_root_cause_input_lock.json").read_text(
            encoding="utf-8"
        )
    )
    mismatches = validate_source_lock(ROOT, lock["analysis_source_sha256"])
    if mismatches:
        raise ValueError(f"analysis source lock mismatch: {mismatches}")
    output.mkdir(parents=True)
    divergence_output = output.parent / "divergence_onset"
    divergence_output.mkdir(parents=True, exist_ok=False)
    source_audit = output.parent / "source_audit"
    source_audit.mkdir(parents=True, exist_ok=True)

    records = {}
    direct = {}
    for index in (1, 2, 3):
        records[index], _ = load_observation_records(
            input_root / f"run_{index}/observation_records_v3.bin"
        )
        direct[index] = jsonl(
            input_root / f"run_{index}/direct_production_metrics_v1.jsonl"
        )
        if len(direct[index]) != 487:
            raise ValueError("direct output count mismatch")

    all_rows = []
    pair_summaries = {}
    field_rows = []
    for pair, left_index, right_index in PAIR_DEFINITIONS:
        rows = compare_semantic_pair(
            pair=pair,
            left=records[left_index],
            right=records[right_index],
        )
        all_rows.extend(rows)
        first = first_semantic_divergence(rows)
        by_field = first_divergence_by_field(rows)
        previous = previous_record_semantic_identity(rows)
        order = (
            classify_divergence_order(rows)
            if first is not None
            else "NOT_APPLICABLE_NO_DIVERGENCE"
        )
        mismatch_count = sum(
            not bool(row["semantic_equal"]) for row in rows
        )
        pair_summaries[pair] = {
            "semantic_mismatch_count": mismatch_count,
            "first_semantic_divergence": first,
            "first_divergence_by_field": by_field,
            "previous_record_semantic_identity": previous,
            "divergence_order_class": order,
        }
        for field in SEMANTIC_FIELDS + ("map_size",):
            value = by_field[field]
            field_rows.append(
                {
                    "pair": pair,
                    "field": field,
                    "first_divergence_record": (
                        value["record_index"] if value else ""
                    ),
                    "first_divergence_scan": (
                        value["scan_index"] if value else ""
                    ),
                    "observed": value is not None,
                }
            )

    write_csv(
        output / "semantic_observation_pairwise_comparison.csv",
        all_rows,
    )
    write_csv(output / "first_divergence_by_pair.csv", field_rows)
    write_json(
        output / "first_divergence_by_field.json",
        {
            pair: summary["first_divergence_by_field"]
            for pair, summary in pair_summaries.items()
        },
    )

    first = pair_summaries["r1-r3"]["first_semantic_divergence"]
    if first is None:
        raise ValueError("run 3 divergence was not localized")
    first_record = int(first["record_index"])
    first_scan = int(first["scan_index"])
    window_start = max(0, first_record - 12)
    window_end = min(486, first_record + 20)
    window_rows = []
    for index in (1, 2, 3):
        for record_index in range(window_start, window_end + 1):
            window_rows.append(
                window_row(
                    run_index=index,
                    record_index=record_index,
                    record=records[index][record_index],
                    detector=direct[index][record_index],
                )
            )
        write_json(
            divergence_output
            / f"first_divergence_record_run{index}.json",
            records[index][first_record],
        )
    write_csv(
        divergence_output / "divergence_onset_window.csv",
        window_rows,
    )
    write_json(
        divergence_output / "divergence_onset_window.json",
        {
            "schema_version": "day6_divergence_onset_window_v1",
            "first_divergence_record": first_record,
            "first_divergence_scan": first_scan,
            "window_start_record": window_start,
            "window_end_record": window_end,
            "rows": window_rows,
        },
    )

    granularity = evidence_granularity_matrix(records[1][0])
    write_csv(source_audit / "evidence_granularity_matrix.csv", granularity)
    granularity_summary = {
        "schema_version": "day6_evidence_granularity_summary_v1",
        "rows": granularity,
        "MAP_CONTENT_IDENTITY_STATUS": (
            "NOT_OBSERVABLE_WITH_CURRENT_EVIDENCE"
        ),
        "RAW_SENSOR_PAYLOAD_IDENTITY_STATUS": "NOT_PROVEN",
        "specific_correspondence_element_localized": False,
        "checksum_only_limitation_disclosed": True,
        "evidence_granularity_audit_pass": True,
    }
    write_json(
        source_audit / "evidence_granularity_summary.json",
        granularity_summary,
    )
    environment = environment_audit(input_root, source_audit)

    r13_first = pair_summaries["r1-r3"]["first_divergence_by_field"]
    summary = {
        "schema_version": "day6_semantic_pairwise_summary_v1",
        "semantic_contract": "SEMANTIC_OBSERVATION_V1",
        "semantic_identity_excludes_run_identity_and_self_checksums": True,
        "pairs": pair_summaries,
        "run1_run2_semantic_mismatch_count": pair_summaries["r1-r2"][
            "semantic_mismatch_count"
        ],
        "run1_run3_semantic_mismatch_count": pair_summaries["r1-r3"][
            "semantic_mismatch_count"
        ],
        "run2_run3_semantic_mismatch_count": pair_summaries["r2-r3"][
            "semantic_mismatch_count"
        ],
        "first_divergence_record": first_record,
        "first_divergence_scan": first_scan,
        "PREVIOUS_RECORD_SEMANTIC_IDENTITY_CONFIRMED": (
            pair_summaries["r1-r3"]["previous_record_semantic_identity"]
            == "CONFIRMED"
            and pair_summaries["r2-r3"][
                "previous_record_semantic_identity"
            ]
            == "CONFIRMED"
        ),
        "DIVERGENCE_ORDER_CLASS": pair_summaries["r1-r3"][
            "divergence_order_class"
        ],
        "first_timestamp_divergence": first_for_fields(
            r13_first, ("timestamp_begin", "timestamp_end")
        ),
        "first_prior_position_divergence": r13_first[
            "prior_position_world"
        ],
        "first_prior_orientation_divergence": r13_first[
            "prior_orientation_world_from_imu_xyzw"
        ],
        "first_prior_covariance_divergence": first_for_fields(
            r13_first,
            (
                "prior_covariance_detector_order_raw",
                "prior_covariance_detector_order_symmetric",
            ),
        ),
        "first_valid_count_divergence": r13_first[
            "valid_correspondence_count"
        ],
        "first_jacobian_divergence": r13_first[
            "detector_pose_jacobian_rows"
        ],
        "first_innovation_divergence": r13_first[
            "formal_filter_innovation_h"
        ],
        "first_geometric_residual_divergence": r13_first[
            "geometric_residual_checksum"
        ],
        "first_accepted_index_divergence": r13_first[
            "accepted_index_checksum"
        ],
        "first_correspondence_divergence": r13_first[
            "formal_correspondence_checksum"
        ],
        "first_map_size_divergence": r13_first["map_size"],
        "CORRESPONDENCE_DIVERGENCE_AT_ONSET_STATUS": (
            "SUPPORTED_AT_AGGREGATE_CHECKSUM_AND_FORMAL_ARRAY_LEVEL"
        ),
        "PRIOR_STATE_DIVERGENCE_AT_ONSET_STATUS": (
            "EQUAL_AT_ONSET_DIVERGED_ON_NEXT_RECORD"
        ),
        "window_start_record": window_start,
        "window_end_record": window_end,
        "pairwise_semantic_comparison_pass": True,
        "first_divergence_localization_pass": True,
        "environment_audit": environment,
    }
    write_json(output / "semantic_comparison_summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
