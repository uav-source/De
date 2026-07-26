#!/usr/bin/env python3
"""Compare and finalize the Day 5 startup-sync V4 AUDIT_ONLY matrix."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.replay_endpoint_contract import (  # noqa: E402
    sequence_contract,
    validate_contract,
)
from fastlio2_adapter.runtime_equivalence import (  # noqa: E402
    compare_final_maps,
    compare_parameter_documents,
    compare_runtime_rows,
    load_json,
    load_runtime_frames,
    load_yaml,
)


RUN_ID = "multihyp_day5_startup_sync_v4"
SEQUENCES = ("avia_quick_shack", "avia_outdoor_run_100hz")
REPEATS = (1, 2, 3)
PAIRS = ((1, 2), (1, 3), (2, 3))
TOLERANCE = 1e-12


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({field for row in rows for field in row}) if rows else ["status"]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_dir(run_root: Path, sequence: str, repeat: int) -> Path:
    return run_root / "runs/baseline" / sequence / f"AUDIT_ONLY_R{repeat}"


def selected_signature(rows: list[dict[str, Any]], *, tail: bool = False) -> str:
    selected_rows = rows[-10:] if tail else rows[:10]
    selected = [
        {
            "scan_index": row["scan_index"],
            "measure_group_checksum": row["measure_group_checksum"],
            "timestamp_begin": row["timestamp_begin"],
            "timestamp_end": row["timestamp_end"],
            "lidar_point_count": row["lidar_point_count"],
            "imu_message_count": row["imu_message_count"],
        }
        for row in selected_rows
    ]
    return hashlib.sha256(
        json.dumps(selected, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def compare_sequence(
    run_root: Path,
    sequence: str,
    *,
    output_root: Path | None = None,
) -> dict[str, Any]:
    if sequence not in SEQUENCES:
        raise ValueError(f"unsupported sequence: {sequence}")
    output_root = output_root or run_root
    runs: dict[int, dict[str, Any]] = {}
    boundaries: list[dict[str, Any]] = []
    drains: list[dict[str, Any]] = []
    for repeat in REPEATS:
        directory = run_dir(run_root, sequence, repeat)
        state = load_json(directory / "single_run_state.json")
        if state.get("status") != "COMPLETED":
            raise RuntimeError(f"{sequence} R{repeat} is not complete")
        frames = load_runtime_frames(directory / "converted/runtime_frames.csv")
        metadata = dict(load_json(directory / "run_metadata.json"))
        drain = dict(load_json(directory / "end_of_stream_drain.json"))
        runs[repeat] = {
            "directory": directory,
            "frames": frames,
            "metadata": metadata,
            "drain": drain,
            "final_map": dict(load_json(directory / "final_map_summary.json")),
            "params": dict(load_yaml(directory / "rosparams.yaml")),
        }
        boundaries.append(
            {
                "sequence_id": sequence,
                "repeat_id": repeat,
                "scan_count": len(frames),
                "first_scan_index": frames[0]["scan_index"] if frames else None,
                "last_scan_index": frames[-1]["scan_index"] if frames else None,
                "first_measure_group_checksum": (
                    frames[0]["measure_group_checksum"] if frames else None
                ),
                "last_measure_group_checksum": (
                    frames[-1]["measure_group_checksum"] if frames else None
                ),
                "first_ten_signature_sha256": selected_signature(frames),
                "last_ten_signature_sha256": selected_signature(frames, tail=True),
            }
        )
        drains.append(
            {
                "sequence_id": sequence,
                "repeat_id": repeat,
                **drain,
            }
        )
    comparisons: list[dict[str, Any]] = []
    mismatch_rows: list[dict[str, Any]] = []
    first_divergences: list[dict[str, Any]] = []
    parameter_rows: list[dict[str, Any]] = []
    for left, right in PAIRS:
        comparison_id = f"baseline:{sequence}:AUDIT_ONLY_R{left}_vs_AUDIT_ONLY_R{right}"
        runtime_result, details = compare_runtime_rows(
            runs[left]["frames"],
            runs[right]["frames"],
            comparison_id=comparison_id,
        )
        map_result = compare_final_maps(
            runs[left]["final_map"], runs[right]["final_map"]
        )
        result = {
            **runtime_result,
            **map_result,
            "overall_equivalence_pass": bool(
                runtime_result["runtime_equivalence_pass"]
                and map_result["final_map_equivalence_pass"]
            ),
            "sequence_id": sequence,
            "left_run": f"AUDIT_ONLY_R{left}",
            "right_run": f"AUDIT_ONLY_R{right}",
        }
        comparisons.append(result)
        mismatch_rows.extend(details)
        first_divergences.append(
            {
                "sequence_id": sequence,
                "comparison_id": comparison_id,
                "first_divergence_scan_index": result[
                    "first_divergence_scan_index"
                ],
                "first_divergence_stage": result["first_divergence_stage"],
            }
        )
        parameter = compare_parameter_documents(
            runs[left]["params"], runs[right]["params"]
        )
        parameter_rows.append(
            {
                "sequence_id": sequence,
                "left_run": f"AUDIT_ONLY_R{left}",
                "right_run": f"AUDIT_ONLY_R{right}",
                **parameter,
            }
        )
    drain_fields = (
        "actual_lidar_callback_count",
        "actual_imu_callback_count",
        "final_processed_measure_group_count",
        "last_processed_lidar_begin_stamp_ns",
        "last_processed_lidar_end_stamp_ns",
        "unprocessed_lidar_tail_count",
        "remaining_imu_count",
    )
    drain_repeatable = all(
        len({row[field] for row in drains}) == 1 for field in drain_fields
    )
    first_ten_match = len(
        {row["first_ten_signature_sha256"] for row in boundaries}
    ) == 1
    last_ten_match = len(
        {row["last_ten_signature_sha256"] for row in boundaries}
    ) == 1
    scan_count_match = len({row["scan_count"] for row in boundaries}) == 1
    passed = (
        all(row["overall_equivalence_pass"] for row in comparisons)
        and all(row["parameter_diff_allowlist_pass"] for row in parameter_rows)
        and all(row["drain_pass"] for row in drains)
        and drain_repeatable
        and first_ten_match
        and last_ten_match
        and scan_count_match
    )
    prefix = "quick" if sequence == "avia_quick_shack" else "outdoor"
    write_csv(output_root / f"{prefix}_pairwise_equivalence.csv", comparisons)
    write_csv(output_root / f"{prefix}_mismatch_rows.csv", mismatch_rows[:50])
    write_csv(output_root / f"{prefix}_first_divergence.csv", first_divergences)
    write_csv(output_root / f"{prefix}_parameter_identity.csv", parameter_rows)
    write_csv(output_root / f"{prefix}_input_boundaries.csv", boundaries)
    result = {
        "sequence_id": sequence,
        "repeatability_pass": passed,
        "first_ten_match": first_ten_match,
        "last_ten_match": last_ten_match,
        "scan_count_match": scan_count_match,
        "drain_repeatable": drain_repeatable,
        "boundaries": boundaries,
        "drains": drains,
        "comparisons": comparisons,
        "first_divergences": first_divergences,
    }
    write_json(output_root / f"{prefix}_comparison_summary.json", result)
    return result


def _sum(rows: Iterable[Mapping[str, Any]], field: str) -> int:
    return sum(int(row.get(field, 0)) for row in rows)


def _max(rows: Iterable[Mapping[str, Any]], field: str) -> float:
    values = [float(row[field]) for row in rows if row.get(field) is not None]
    return max(values, default=0.0)


def _gt_topics(text: str) -> list[str]:
    tokens = ("ground_truth", "groundtruth", "mocap", "vicon", "truth", "/gt")
    return sorted(
        {
            line.split("* ", 1)[1].split(" ", 1)[0]
            for line in text.splitlines()
            if "* /" in line
            and any(token in line.lower() for token in tokens)
        }
    )


def finalize(
    run_root: Path, endpoint_path: Path, run_lock_path: Path
) -> dict[str, Any]:
    contract = json.loads(endpoint_path.read_text(encoding="utf-8"))
    validate_contract(contract)
    lock = json.loads(run_lock_path.read_text(encoding="utf-8"))
    quick = compare_sequence(run_root, "avia_quick_shack")
    outdoor = compare_sequence(run_root, "avia_outdoor_run_100hz")
    sequence_results = [quick, outdoor]
    comparisons = [
        row for sequence in sequence_results for row in sequence["comparisons"]
    ]
    boundaries = [
        row for sequence in sequence_results for row in sequence["boundaries"]
    ]
    drains = [row for sequence in sequence_results for row in sequence["drains"]]
    run_rows: list[dict[str, Any]] = []
    handshakes: list[dict[str, Any]] = []
    shutdowns: list[dict[str, Any]] = []
    products: list[dict[str, Any]] = []
    locks: list[dict[str, Any]] = []
    no_gt: list[dict[str, Any]] = []
    full_logs: list[dict[str, Any]] = []
    for sequence in SEQUENCES:
        endpoint = sequence_contract(contract, sequence)
        for repeat in REPEATS:
            directory = run_dir(run_root, sequence, repeat)
            metadata = dict(load_json(directory / "run_metadata.json"))
            run_rows.append(metadata)
            handshakes.append(
                {
                    "sequence_id": sequence,
                    "repeat_id": repeat,
                    **dict(load_json(directory / "connection_handshake_v4.json")),
                }
            )
            shutdowns.append(
                {
                    "sequence_id": sequence,
                    "repeat_id": repeat,
                    **dict(load_json(directory / "graceful_shutdown_v4.json")),
                }
            )
            products.append(
                {
                    "sequence_id": sequence,
                    "repeat_id": repeat,
                    **dict(load_json(directory / "runtime_product_validation_v4.json")),
                }
            )
            lock_row = dict(
                load_json(directory / "post_run_source_binary_clip_lock.json")
            )
            locks.append(
                {
                    "sequence_id": sequence,
                    "repeat_id": repeat,
                    "source_lock_pass": lock_row["source_lock_pass"],
                    "binary_lock_pass": lock_row["binary_lock_pass"],
                    "clip_lock_pass": lock_row["clip_lock_pass"],
                }
            )
            consumed = _gt_topics(
                (directory / "rosnode_info.txt").read_text(
                    encoding="utf-8", errors="replace"
                )
            )
            no_gt.append(
                {
                    "sequence_id": sequence,
                    "repeat_id": repeat,
                    "gt_topic_consumed_count": len(consumed),
                    "gt_topics": ";".join(consumed),
                    "no_gt_runtime_pass": not consumed,
                }
            )
            for relative in (
                "runtime_audit_v2.bin",
                "converted/runtime_frames.csv",
                "rosbag.log",
                "roslaunch.log",
                "roscore.log",
            ):
                path = directory / relative
                full_logs.append(
                    {
                        "run_id": RUN_ID,
                        "sequence_id": sequence,
                        "repeat_id": repeat,
                        "relative_path": path.relative_to(run_root).as_posix(),
                        "size_bytes": path.stat().st_size,
                        "sha256": file_sha256(path),
                        "included_in_audit_package": False,
                        "exclusion_reason": "LARGE_REAL_RUNTIME_LOG_NOT_SHARED",
                    }
                )
            assert int(drains[len(run_rows) - 1]["actual_lidar_callback_count"]) == int(
                endpoint["expected_lidar_message_count"]
            )
    heartbeat_history = run_root / "supervisor_heartbeat_history.csv"
    heartbeat_rows: list[dict[str, str]] = []
    if heartbeat_history.is_file():
        with heartbeat_history.open(encoding="utf-8", newline="") as stream:
            heartbeat_rows = list(csv.DictReader(stream))
    heartbeat_times = [
        int(row["last_heartbeat_monotonic_ns"]) for row in heartbeat_rows
    ]
    max_heartbeat_gap = max(
        (
            (right - left) / 1e9
            for left, right in zip(heartbeat_times, heartbeat_times[1:])
        ),
        default=0.0,
    )
    matrix_state = dict(load_json(run_root / "matrix_state.json"))
    interruption_count = int(matrix_state.get("runner_interruption_count", 0))
    supervisor_terminal = matrix_state.get("status")
    all_callbacks = all(
        row["actual_lidar_callback_count"] == row["expected_lidar_callback_count"]
        and row["actual_imu_callback_count"] == row["expected_imu_callback_count"]
        and row["actual_last_lidar_header_stamp_ns"]
        == row["expected_last_lidar_header_stamp_ns"]
        and row["actual_last_imu_header_stamp_ns"]
        == row["expected_last_imu_header_stamp_ns"]
        for row in drains
    )
    drain_pass = len(drains) == 6 and all(row["drain_pass"] for row in drains)
    source_pass = len(locks) == 6 and all(
        row["source_lock_pass"]
        and row["binary_lock_pass"]
        and row["clip_lock_pass"]
        for row in locks
    )
    shutdown_pass = len(shutdowns) == 6 and all(
        row["shutdown_completed"] for row in shutdowns
    )
    product_pass = len(products) == 6 and all(
        row["runtime_product_pass"] for row in products
    )
    handshake_pass = len(handshakes) == 6 and all(
        row["handshake_pass"] and row["unpause_success"] for row in handshakes
    )
    no_gt_pass = len(no_gt) == 6 and all(row["no_gt_runtime_pass"] for row in no_gt)
    no_nonfinite = all(
        int(load_json(run_dir(run_root, row["sequence_id"], row["repeat_id"]) / "run_summary.json").get("nonfinite_count", 0)) == 0
        and int(load_json(run_dir(run_root, row["sequence_id"], row["repeat_id"]) / "final_map_summary.json").get("nonfinite_count", 0)) == 0
        for row in run_rows
    )
    runner_persistence = (
        interruption_count == 0
        and supervisor_terminal in {"OUTDOOR_COMPARING", "COMPLETED"}
        and bool(heartbeat_rows)
    )
    implementation_pass = bool(lock.get("end_of_stream_audit_implementation_pass"))
    endpoint_pass = (
        hashlib.sha256(endpoint_path.read_bytes()).hexdigest()
        == lock["endpoint_contract_sha256"]
    )
    complete = len(run_rows) == 6
    baseline_pass = all(
        (
            endpoint_pass,
            implementation_pass,
            all_callbacks,
            drain_pass,
            runner_persistence,
            quick["repeatability_pass"],
            outdoor["repeatability_pass"],
            handshake_pass,
            shutdown_pass,
            product_pass,
            source_pass,
            no_gt_pass,
            no_nonfinite,
            complete,
        )
    )
    if not source_pass:
        failure = "SOURCE_LOCK_CHANGED"
    elif not endpoint_pass:
        failure = "ENDPOINT_CONTRACT_MISMATCH"
    elif not implementation_pass:
        failure = "DRAIN_SERVICE_IMPLEMENTATION_INVALID"
    elif not runner_persistence:
        failure = "RUNNER_SESSION_INTERRUPTED"
    elif not all_callbacks:
        incomplete_lidar = any(
            row["actual_lidar_callback_count"] < row["expected_lidar_callback_count"]
            for row in drains
        )
        incomplete_imu = any(
            row["actual_imu_callback_count"] < row["expected_imu_callback_count"]
            for row in drains
        )
        if incomplete_lidar:
            failure = "LIDAR_CALLBACK_COUNT_INCOMPLETE"
        elif incomplete_imu:
            failure = "IMU_CALLBACK_COUNT_INCOMPLETE"
        else:
            failure = "LAST_LIDAR_STAMP_MISMATCH"
    elif not drain_pass:
        failure = next(
            (
                row["failure_classification"]
                for row in drains
                if not row["drain_pass"]
            ),
            "END_OF_STREAM_DRAIN_TIMEOUT",
        )
    elif not shutdown_pass:
        failure = "RUNTIME_NODE_SHUTDOWN_INCOMPLETE"
    elif not product_pass:
        failure = "RUNTIME_PRODUCT_MISSING"
    elif not all(result["scan_count_match"] for result in sequence_results):
        failure = "INPUT_BOUNDARY_NONDETERMINISM_AFTER_DRAIN"
    elif _sum(comparisons, "prior_state_checksum_mismatch_count") or _sum(
        comparisons, "prior_covariance_checksum_mismatch_count"
    ):
        failure = "FASTLIO2_BASELINE_STATE_NONDETERMINISM"
    elif _sum(comparisons, "formal_native_jacobian_checksum_mismatch_count") or _sum(
        comparisons, "geometric_residual_checksum_mismatch_count"
    ):
        failure = "FASTLIO2_FORMAL_LINEARIZATION_NONDETERMINISM"
    elif _sum(comparisons, "posterior_state_checksum_mismatch_count") or _sum(
        comparisons, "posterior_covariance_checksum_mismatch_count"
    ):
        failure = "FASTLIO2_FILTER_UPDATE_NONDETERMINISM"
    elif _sum(comparisons, "map_size_after_update_mismatch_count") or any(
        not row["final_map_equivalence_pass"] for row in comparisons
    ):
        failure = "FINAL_MAP_DIGEST_OR_TRAVERSAL_NONDETERMINISM"
    else:
        failure = "NONE"
    gates = {
        "REPLAY_ENDPOINT_CONTRACT_PASS": endpoint_pass,
        "END_OF_STREAM_AUDIT_IMPLEMENTATION_PASS": implementation_pass,
        "ALL_CALLBACKS_RECEIVED_PASS": all_callbacks,
        "END_OF_STREAM_DRAIN_PASS": drain_pass,
        "RUNNER_PERSISTENCE_PASS": runner_persistence,
        "QUICK_BASELINE_REPEATABILITY_PASS": quick["repeatability_pass"],
        "OUTDOOR_BASELINE_REPEATABILITY_PASS": outdoor["repeatability_pass"],
        "BASELINE_REPEATABILITY_PASS": baseline_pass,
        "DAY5_STARTUP_SYNC_V4_PASS": baseline_pass,
        "DAY5_CAPTURE_EXPORT_REMEDIATION_AUTHORIZED": baseline_pass,
        "DAY5_RUNTIME_EQUIVALENCE_PASS": False,
        "OFF_ON_REPLAY_EQUIVALENCE_STATUS": "NOT_REEVALUATED_STARTUP_SYNC_ONLY",
        "DAY6_QUICK_DIAGNOSTICS_AUTHORIZED": False,
        "FAILURE_CLASSIFICATION": failure,
    }
    first_divergence = next(
        (
            row
            for row in comparisons
            if row.get("first_divergence_stage") not in (None, "NONE")
        ),
        None,
    )
    summary = {
        **gates,
        "run_id": RUN_ID,
        "planned_replay_count": 6,
        "executed_replay_count": len(run_rows),
        "successful_replay_count": sum(
            row["runtime_product_pass"] and row["end_of_stream_drain_pass"]
            for row in run_rows
        ),
        "supervisor_pid": matrix_state.get("supervisor_pid"),
        "supervisor_terminal_state": supervisor_terminal,
        "supervisor_heartbeat_count": len(heartbeat_rows),
        "supervisor_max_heartbeat_gap_sec": max_heartbeat_gap,
        "runner_interruption_count": interruption_count,
        "paired_scan_count": _sum(comparisons, "paired_scan_count"),
        "missing_scan_count": _sum(comparisons, "missing_scan_count"),
        "duplicate_scan_count": _sum(comparisons, "duplicate_scan_count"),
        "measure_group_mismatch_count": _sum(
            comparisons, "measure_group_checksum_mismatch_count"
        ),
        "prior_state_mismatch_count": _sum(
            comparisons, "prior_state_checksum_mismatch_count"
        ),
        "prior_covariance_mismatch_count": _sum(
            comparisons, "prior_covariance_checksum_mismatch_count"
        ),
        "jacobian_mismatch_count": _sum(
            comparisons, "formal_native_jacobian_checksum_mismatch_count"
        ),
        "residual_mismatch_count": _sum(
            comparisons, "geometric_residual_checksum_mismatch_count"
        ),
        "accepted_index_mismatch_count": _sum(
            comparisons, "accepted_index_checksum_mismatch_count"
        ),
        "correspondence_mismatch_count": _sum(
            comparisons, "formal_correspondence_checksum_mismatch_count"
        ),
        "posterior_state_mismatch_count": _sum(
            comparisons, "posterior_state_checksum_mismatch_count"
        ),
        "posterior_covariance_mismatch_count": _sum(
            comparisons, "posterior_covariance_checksum_mismatch_count"
        ),
        "map_size_mismatch_count": _sum(
            comparisons, "map_size_after_update_mismatch_count"
        ),
        "final_map_mismatch_count": sum(
            not row["final_map_equivalence_pass"] for row in comparisons
        ),
        "max_position_difference_m": _max(
            comparisons, "max_position_difference_m"
        ),
        "max_rotation_difference_rad": _max(
            comparisons, "max_rotation_geodesic_difference_rad"
        ),
        "max_covariance_difference": _max(
            comparisons, "max_covariance_absolute_difference"
        ),
        "first_divergence_scan": (
            first_divergence["first_divergence_scan_index"]
            if first_divergence
            else None
        ),
        "first_divergence_stage": (
            first_divergence["first_divergence_stage"]
            if first_divergence
            else "NONE"
        ),
        "drain_pass_count": sum(row["drain_pass"] for row in drains),
        "drain_timeout_count": sum(
            row["failure_classification"] == "END_OF_STREAM_DRAIN_TIMEOUT"
            for row in drains
        ),
        "callback_incomplete_count": sum(
            row["actual_lidar_callback_count"] != row["expected_lidar_callback_count"]
            or row["actual_imu_callback_count"] != row["expected_imu_callback_count"]
            for row in drains
        ),
        "shutdown_completed_count": sum(
            row["shutdown_completed"] for row in shutdowns
        ),
        "runtime_product_pass_count": sum(
            row["runtime_product_pass"] for row in products
        ),
        "quick": quick,
        "outdoor": outdoor,
        "per_run_callback_counts": [
            {
                "sequence_id": row["sequence_id"],
                "repeat_id": row["repeat_id"],
                "lidar": row["actual_lidar_callback_count"],
                "imu": row["actual_imu_callback_count"],
            }
            for row in drains
        ],
        "per_run_processed_measure_group_counts": [
            row["final_processed_measure_group_count"] for row in drains
        ],
        "per_run_unprocessed_lidar_tail_counts": [
            row["unprocessed_lidar_tail_count"] for row in drains
        ],
        "per_run_remaining_imu_counts": [
            row["remaining_imu_count"] for row in drains
        ],
    }
    write_csv(run_root / "single_run_inventory.csv", run_rows)
    write_csv(run_root / "connection_handshake_summary.csv", handshakes)
    write_csv(run_root / "end_of_stream_drain_summary.csv", drains)
    write_csv(
        run_root / "callback_endpoint_summary.csv",
        [
            {
                key: row[key]
                for key in row
                if "callback" in key
                or "header_stamp" in key
                or key in {"sequence_id", "repeat_id", "drain_pass"}
            }
            for row in drains
        ],
    )
    write_csv(run_root / "first_input_boundary_summary.csv", boundaries)
    write_csv(run_root / "last_input_boundary_summary.csv", boundaries)
    write_csv(run_root / "baseline_pairwise_equivalence.csv", comparisons)
    write_csv(
        run_root / "baseline_repeatability_summary.csv",
        [
            {
                "sequence_id": result["sequence_id"],
                "repeatability_pass": result["repeatability_pass"],
                "first_ten_match": result["first_ten_match"],
                "last_ten_match": result["last_ten_match"],
                "scan_count_match": result["scan_count_match"],
                "drain_repeatable": result["drain_repeatable"],
            }
            for result in sequence_results
        ],
    )
    write_csv(
        run_root / "first_divergence_summary.csv",
        [
            row
            for result in sequence_results
            for row in result["first_divergences"]
        ],
    )
    write_csv(run_root / "source_binary_clip_lock_audit.csv", locks)
    write_csv(run_root / "runtime_product_completeness.csv", products)
    write_csv(run_root / "no_gt_runtime_audit.csv", no_gt)
    write_csv(
        run_root / "gate_summary.csv",
        [{"gate": key, "value": value} for key, value in gates.items()],
    )
    write_csv(run_root / "full_log_index.csv", full_logs)
    write_json(
        run_root / "day5_startup_sync_v4_run_manifest.json",
        {"run_id": RUN_ID, "runs": run_rows},
    )
    write_json(run_root / "day5_startup_sync_v4_summary.json", summary)
    write_json(run_root / "day5_startup_sync_v4_gate_summary.json", gates)
    return summary


def copy_small_results(run_root: Path) -> None:
    destination = (
        ROOT
        / "artifacts/current/harmful_bias_multihyp_dev/day5_startup_sync_v4"
    )
    if destination.exists():
        raise RuntimeError(f"small result directory exists: {destination}")
    destination.mkdir(parents=True)
    names = (
        "replay_endpoint_contract_v1.json",
        "endpoint_contract_validation.json",
        "supervisor_final_state.json",
        "supervisor_heartbeat_summary.csv",
        "single_run_inventory.csv",
        "connection_handshake_summary.csv",
        "end_of_stream_drain_summary.csv",
        "callback_endpoint_summary.csv",
        "first_input_boundary_summary.csv",
        "last_input_boundary_summary.csv",
        "baseline_pairwise_equivalence.csv",
        "baseline_repeatability_summary.csv",
        "first_divergence_summary.csv",
        "source_binary_clip_lock_audit.csv",
        "runtime_product_completeness.csv",
        "no_gt_runtime_audit.csv",
        "gate_summary.csv",
        "day5_startup_sync_v4_run_manifest.json",
        "day5_startup_sync_v4_summary.json",
        "day5_startup_sync_v4_gate_summary.json",
        "full_log_index.csv",
    )
    for name in names:
        source = run_root / name
        if source.is_file():
            shutil.copy2(source, destination / name)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--endpoint-contract", required=True, type=Path)
    parser.add_argument("--run-lock", required=True, type=Path)
    parser.add_argument("--quick-gate", action="store_true")
    parser.add_argument("--copy-small-results", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_root = args.run_root.expanduser().resolve()
    if args.quick_gate:
        result = compare_sequence(run_root, "avia_quick_shack")
        print(json.dumps(result, sort_keys=True))
        return int(not result["repeatability_pass"])
    summary = finalize(
        run_root,
        args.endpoint_contract.expanduser().resolve(),
        args.run_lock.expanduser().resolve(),
    )
    if args.copy_small_results:
        copy_small_results(run_root)
    print(json.dumps(summary, sort_keys=True))
    return int(not summary["DAY5_STARTUP_SYNC_V4_PASS"])


if __name__ == "__main__":
    raise SystemExit(main())
