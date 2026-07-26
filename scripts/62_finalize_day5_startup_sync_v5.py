#!/usr/bin/env python3
"""Compare and finalize the final Day 5 startup-sync V5 matrix."""

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


RUN_ID = "multihyp_day5_startup_sync_v5"
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
    handoffs: list[dict[str, Any]] = []
    for repeat in REPEATS:
        directory = run_dir(run_root, sequence, repeat)
        state = load_json(directory / "single_run_state.json")
        if state.get("status") != "COMPLETED":
            raise RuntimeError(f"{sequence} R{repeat} is not complete")
        frames = load_runtime_frames(directory / "converted/runtime_frames.csv")
        metadata = dict(load_json(directory / "run_metadata.json"))
        drain = dict(load_json(directory / "end_of_stream_drain.json"))
        handoff = dict(load_json(directory / "tail_clock_handoff.json"))
        runs[repeat] = {
            "directory": directory,
            "frames": frames,
            "metadata": metadata,
            "drain": drain,
            "handoff": handoff,
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
        handoffs.append(
            {
                "sequence_id": sequence,
                "repeat_id": repeat,
                **handoff,
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
    tail_fields = (
        "tail_clock_step_ns",
        "last_bag_clock_ns",
        "tail_first_clock_ns",
    )
    tail_repeatable = all(
        len({row[field] for row in handoffs}) == 1 for field in tail_fields
    )
    tail_pass = all(
        row["handoff_pass"]
        and row["tail_first_clock_ns"]
        == row["last_bag_clock_ns"] + row["tail_clock_step_ns"]
        and row["clock_publisher_overlap_count"] == 0
        and row["clock_duplicate_count"] == 0
        and row["clock_backward_count"] == 0
        for row in handoffs
    )
    passed = (
        all(row["overall_equivalence_pass"] for row in comparisons)
        and all(row["parameter_diff_allowlist_pass"] for row in parameter_rows)
        and all(row["drain_pass"] for row in drains)
        and drain_repeatable
        and first_ten_match
        and last_ten_match
        and scan_count_match
        and tail_repeatable
        and tail_pass
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
        "tail_clock_repeatable": tail_repeatable,
        "tail_clock_pass": tail_pass,
        "boundaries": boundaries,
        "drains": drains,
        "handoffs": handoffs,
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


def read_json_if_present(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"JSON document must be an object: {path}")
    return dict(value)


def heartbeat_evidence(run_root: Path) -> tuple[list[dict[str, str]], float]:
    history = run_root / "supervisor_heartbeat_history.csv"
    rows: list[dict[str, str]] = []
    if history.is_file():
        with history.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
    times = [
        int(row["last_heartbeat_monotonic_ns"])
        for row in rows
        if row.get("last_heartbeat_monotonic_ns")
    ]
    max_gap = max(
        (
            (right - left) / 1e9
            for left, right in zip(times, times[1:])
        ),
        default=0.0,
    )
    return rows, max_gap


def tail_clock_rows(
    handoffs: Iterable[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    summary_rows: list[dict[str, Any]] = []
    monotonic_rows: list[dict[str, Any]] = []
    transition_rows: list[dict[str, Any]] = []
    for raw in handoffs:
        row = dict(raw)
        exact_first = (
            row.get("tail_first_clock_ns") is not None
            and row.get("last_bag_clock_ns") is not None
            and row.get("tail_clock_step_ns") is not None
            and int(row["tail_first_clock_ns"])
            == int(row["last_bag_clock_ns"]) + int(row["tail_clock_step_ns"])
        )
        summary_rows.append(
            {
                "sequence_id": row.get("sequence_id"),
                "repeat_id": row.get("repeat_id"),
                "start_success": row.get("start_success", False),
                "stop_success": row.get("stop_success", False),
                "handoff_pass": row.get("handoff_pass", False),
                "last_bag_clock_ns": row.get("last_bag_clock_ns"),
                "tail_first_clock_ns": row.get("tail_first_clock_ns"),
                "tail_clock_step_ns": row.get("tail_clock_step_ns"),
                "tail_publish_count": row.get("tail_publish_count", 0),
                "tail_final_clock_ns": row.get("tail_final_clock_ns"),
                "first_tail_exact_pass": exact_first,
                "failure_reason": row.get("failure_reason", ""),
            }
        )
        monotonic_rows.append(
            {
                "sequence_id": row.get("sequence_id"),
                "repeat_id": row.get("repeat_id"),
                "first_tail_exact_pass": exact_first,
                "clock_duplicate_count": row.get("clock_duplicate_count", 0),
                "clock_backward_count": row.get("clock_backward_count", 0),
                "monotonic_pass": bool(
                    exact_first
                    and int(row.get("clock_duplicate_count", 0)) == 0
                    and int(row.get("clock_backward_count", 0)) == 0
                ),
            }
        )
        transition_rows.append(
            {
                "sequence_id": row.get("sequence_id"),
                "repeat_id": row.get("repeat_id"),
                "bag_player_exit_monotonic_ns": row.get(
                    "bag_player_exit_monotonic_ns"
                ),
                "bag_clock_publisher_disappear_start_ns": row.get(
                    "bag_clock_publisher_disappear_start_ns"
                ),
                "bag_clock_publisher_disappear_ready_ns": row.get(
                    "bag_clock_publisher_disappear_ready_ns"
                ),
                "tail_start_request_monotonic_ns": row.get(
                    "tail_start_request_monotonic_ns"
                ),
                "tail_start_response_monotonic_ns": row.get(
                    "tail_start_response_monotonic_ns"
                ),
                "clock_publishers_before_handoff": json.dumps(
                    row.get("clock_publishers_before_handoff", []),
                    separators=(",", ":"),
                ),
                "clock_publishers_during_handoff": json.dumps(
                    row.get("clock_publishers_during_handoff", []),
                    separators=(",", ":"),
                ),
                "clock_publishers_after_handoff": json.dumps(
                    row.get("clock_publishers_after_handoff", []),
                    separators=(",", ":"),
                ),
                "clock_publisher_overlap_count": row.get(
                    "clock_publisher_overlap_count", 0
                ),
                "no_overlap_pass": int(
                    row.get("clock_publisher_overlap_count", 0)
                )
                == 0,
            }
        )
    return summary_rows, monotonic_rows, transition_rows


def drain_timeout_rows(
    drains: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "sequence_id": row.get("sequence_id"),
            "repeat_id": row.get("repeat_id"),
            "service_call_timeout_sec": row.get("service_call_timeout_sec"),
            "service_call_timeout_count": row.get(
                "service_call_timeout_count", 0
            ),
            "max_consecutive_service_timeouts": row.get(
                "max_consecutive_service_timeouts", 0
            ),
            "drain_pass": row.get("drain_pass", False),
            "failure_classification": row.get(
                "failure_classification", ""
            ),
        }
        for row in drains
    ]


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
    tail_handoffs: list[dict[str, Any]] = []
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
                    **dict(load_json(directory / "connection_handshake_v5.json")),
                }
            )
            shutdowns.append(
                {
                    "sequence_id": sequence,
                    "repeat_id": repeat,
                    **dict(load_json(directory / "graceful_shutdown_v5.json")),
                }
            )
            products.append(
                {
                    "sequence_id": sequence,
                    "repeat_id": repeat,
                    **dict(load_json(directory / "runtime_product_validation_v5.json")),
                }
            )
            tail_handoffs.append(
                {
                    "sequence_id": sequence,
                    "repeat_id": repeat,
                    **dict(load_json(directory / "tail_clock_handoff.json")),
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
    heartbeat_rows, max_heartbeat_gap = heartbeat_evidence(run_root)
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
        and supervisor_terminal
        in {"OUTDOOR_COMPARING", "COMPLETED", "FAILED"}
        and bool(heartbeat_rows)
    )
    fast_unchanged = bool(lock.get("fastlio2_unchanged_pass"))
    tail_protocol_test_pass = bool(lock.get("tail_clock_protocol_test_pass"))
    tail_handoff_pass = len(tail_handoffs) == 6 and all(
        row["handoff_pass"] for row in tail_handoffs
    )
    tail_no_overlap = len(tail_handoffs) == 6 and all(
        int(row["clock_publisher_overlap_count"]) == 0
        for row in tail_handoffs
    )
    tail_monotonic = len(tail_handoffs) == 6 and all(
        int(row["clock_duplicate_count"]) == 0
        and int(row["clock_backward_count"]) == 0
        and int(row["tail_first_clock_ns"])
        == int(row["last_bag_clock_ns"]) + int(row["tail_clock_step_ns"])
        for row in tail_handoffs
    )
    tail_main_loop_progress = len(drains) == 6 and all(
        int(row["main_loop_heartbeat_end"])
        > int(row["main_loop_heartbeat_start"])
        for row in drains
    )
    drain_wall_timeout_pass = bool(
        lock.get("drain_service_wall_timeout_implementation_pass")
    ) and len(drains) == 6 and all(
        int(row.get("service_call_timeout_count", 0)) == 0
        for row in drains
    )
    endpoint_pass = (
        hashlib.sha256(endpoint_path.read_bytes()).hexdigest()
        == lock["endpoint_contract_sha256"]
    )
    complete = len(run_rows) == 6
    baseline_pass = all(
        (
            endpoint_pass,
            fast_unchanged,
            tail_protocol_test_pass,
            tail_handoff_pass,
            tail_no_overlap,
            tail_monotonic,
            tail_main_loop_progress,
            drain_wall_timeout_pass,
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
        failure = "SOURCE_LOCK_CHANGED"
    elif not fast_unchanged:
        failure = "SOURCE_LOCK_CHANGED"
    elif not tail_handoff_pass:
        failure = next(
            (
                row.get("failure_reason")
                for row in tail_handoffs
                if not row.get("handoff_pass")
            ),
            "TAIL_CLOCK_START_FAILURE",
        )
    elif not tail_no_overlap:
        failure = "TAIL_CLOCK_PUBLISHER_OVERLAP"
    elif not tail_monotonic:
        failure = "TAIL_CLOCK_DUPLICATE_TIME"
    elif not tail_main_loop_progress:
        failure = "TAIL_CLOCK_MAIN_LOOP_NOT_PROGRESSING"
    elif not drain_wall_timeout_pass:
        failure = "DRAIN_SERVICE_CALL_TIMEOUT"
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
            failure = "LIDAR_CALLBACK_COUNT_INCOMPLETE"
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
        failure = "NORMAL_SHUTDOWN_FAILURE"
    elif not product_pass:
        failure = "RUNTIME_PRODUCT_MISSING"
    elif not all(result["scan_count_match"] for result in sequence_results):
        failure = "INPUT_BOUNDARY_NONDETERMINISM"
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
        failure = "FINAL_MAP_NONDETERMINISM"
    else:
        failure = "NONE"
    gates = {
        "REPLAY_ENDPOINT_CONTRACT_PASS": endpoint_pass,
        "FAST_LIO2_UNCHANGED_PASS": fast_unchanged,
        "TAIL_CLOCK_PROTOCOL_TEST_PASS": tail_protocol_test_pass,
        "TAIL_CLOCK_HANDOFF_PASS": tail_handoff_pass,
        "TAIL_CLOCK_NO_OVERLAP_PASS": tail_no_overlap,
        "TAIL_CLOCK_MONOTONIC_PASS": tail_monotonic,
        "TAIL_CLOCK_MAIN_LOOP_PROGRESS_PASS": tail_main_loop_progress,
        "DRAIN_SERVICE_WALL_TIMEOUT_PASS": drain_wall_timeout_pass,
        "ALL_CALLBACKS_RECEIVED_PASS": all_callbacks,
        "END_OF_STREAM_DRAIN_PASS": drain_pass,
        "RUNNER_PERSISTENCE_PASS": runner_persistence,
        "NORMAL_SHUTDOWN_PASS": shutdown_pass,
        "RUNTIME_PRODUCT_COMPLETENESS_PASS": product_pass,
        "QUICK_BASELINE_REPEATABILITY_PASS": quick["repeatability_pass"],
        "OUTDOOR_BASELINE_REPEATABILITY_PASS": outdoor["repeatability_pass"],
        "BASELINE_REPEATABILITY_PASS": baseline_pass,
        "DAY5_STARTUP_SYNC_V5_PASS": baseline_pass,
        "DAY5_CAPTURE_EXPORT_REMEDIATION_AUTHORIZED": baseline_pass,
        "DAY5_RUNTIME_EQUIVALENCE_PASS": False,
        "OFF_ON_REPLAY_EQUIVALENCE_STATUS": "NOT_REEVALUATED_STARTUP_SYNC_ONLY",
        "DAY6_QUICK_DIAGNOSTICS_AUTHORIZED": False,
        "FAILURE_CLASSIFICATION": failure,
        "STRICT_CROSS_PROCESS_REPLAY_ROUTE_STATUS": (
            "PROVEN" if baseline_pass else "ABANDONED_AFTER_V5"
        ),
        "STRICT_REPLAY_FURTHER_REMEDIATION_AUTHORIZED": False,
        "CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE": (
            "PROVEN" if baseline_pass else "NOT_PROVEN"
        ),
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
        "per_run_last_bag_clock_ns": [
            row["last_bag_clock_ns"] for row in tail_handoffs
        ],
        "per_run_tail_first_clock_ns": [
            row["tail_first_clock_ns"] for row in tail_handoffs
        ],
        "per_run_tail_publish_count": [
            row["tail_publish_count"] for row in tail_handoffs
        ],
        "per_run_tail_final_clock_ns": [
            row["tail_final_clock_ns"] for row in tail_handoffs
        ],
        "clock_publisher_overlap_count": _sum(
            tail_handoffs, "clock_publisher_overlap_count"
        ),
        "clock_duplicate_count": _sum(
            tail_handoffs, "clock_duplicate_count"
        ),
        "clock_backward_count": _sum(
            tail_handoffs, "clock_backward_count"
        ),
        "service_call_timeout_sec": lock["service_call_timeout_sec"],
        "service_call_timeout_count": _sum(
            drains, "service_call_timeout_count"
        ),
        "max_consecutive_service_timeouts": max(
            (
                int(row.get("max_consecutive_service_timeouts", 0))
                for row in drains
            ),
            default=0,
        ),
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
        "per_run_main_loop_heartbeat_growth": [
            {
                "sequence_id": row["sequence_id"],
                "repeat_id": row["repeat_id"],
                "start": row["main_loop_heartbeat_start"],
                "end": row["main_loop_heartbeat_end"],
                "growth": int(row["main_loop_heartbeat_end"])
                - int(row["main_loop_heartbeat_start"]),
            }
            for row in drains
        ],
        "outdoor_executed": True,
        "roscore_run": True,
        "roslaunch_run": True,
        "rosbag_run": True,
        "real_data_used": True,
        "engineering_quick_replay_run": True,
        "capture_only_run": False,
        "compact_export_run": False,
        "detector_called": False,
        "odi_computed": False,
        "scientific_experiment_run": False,
        "development_run": False,
        "holdout_run": False,
        "future_test_run": False,
        "detector_modified": False,
        "threshold_modified": False,
        "day5_commit_created": False,
        "push_performed": False,
        "RECOMMENDED_FALLBACK_EVIDENCE_ROUTE": (
            "IN_CALL_IMMUTABILITY+FROZEN_OBSERVATION_RECORD+"
            "OFFLINE_PRODUCTION_DETECTOR_DETERMINISM+"
            "REAL_REPLAY_FUNCTIONAL_STATISTICAL_TOLERANCE"
        ),
    }
    write_csv(run_root / "single_run_inventory.csv", run_rows)
    write_csv(run_root / "connection_handshake_summary.csv", handshakes)
    tail_summary, monotonic_rows, transition_rows = tail_clock_rows(
        tail_handoffs
    )
    write_csv(run_root / "tail_clock_handoff_summary.csv", tail_summary)
    write_csv(
        run_root / "tail_clock_monotonicity_audit.csv", monotonic_rows
    )
    write_csv(
        run_root / "clock_publisher_transition_audit.csv", transition_rows
    )
    write_csv(
        run_root / "drain_service_timeout_summary.csv",
        drain_timeout_rows(drains),
    )
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
        run_root / "day5_startup_sync_v5_run_manifest.json",
        {"run_id": RUN_ID, "runs": run_rows},
    )
    write_json(run_root / "day5_startup_sync_v5_summary.json", summary)
    write_json(run_root / "day5_startup_sync_v5_gate_summary.json", gates)
    return summary


def finalize_partial(
    run_root: Path, endpoint_path: Path, run_lock_path: Path
) -> dict[str, Any]:
    """Persist fail-closed V5 evidence when the matrix stops before completion."""

    contract = json.loads(endpoint_path.read_text(encoding="utf-8"))
    validate_contract(contract)
    lock = json.loads(run_lock_path.read_text(encoding="utf-8"))
    complete_identities = []
    existing_identities = []
    for sequence in SEQUENCES:
        for repeat in REPEATS:
            directory = run_dir(run_root, sequence, repeat)
            if directory.is_dir():
                existing_identities.append((sequence, repeat, directory))
                state = read_json_if_present(directory / "single_run_state.json")
                if state.get("status") == "COMPLETED":
                    complete_identities.append((sequence, repeat, directory))
    if len(complete_identities) == 6:
        return finalize(run_root, endpoint_path, run_lock_path)

    run_rows: list[dict[str, Any]] = []
    handshakes: list[dict[str, Any]] = []
    shutdowns: list[dict[str, Any]] = []
    products: list[dict[str, Any]] = []
    drains: list[dict[str, Any]] = []
    handoffs: list[dict[str, Any]] = []
    locks: list[dict[str, Any]] = []
    no_gt: list[dict[str, Any]] = []
    full_logs: list[dict[str, Any]] = []
    failure_candidates: list[str] = []
    for sequence, repeat, directory in existing_identities:
        identity = {"sequence_id": sequence, "repeat_id": repeat}
        state = read_json_if_present(directory / "single_run_state.json")
        metadata = read_json_if_present(directory / "run_metadata.json")
        failure = read_json_if_present(directory / "single_run_failure.json")
        run_rows.append(
            {
                **identity,
                "runtime_mode": "AUDIT_ONLY",
                "status": state.get("status", "UNKNOWN"),
                "failure_classification": failure.get(
                    "failure_classification",
                    state.get("failure_classification", "NONE"),
                ),
                **metadata,
            }
        )
        candidate = str(
            failure.get(
                "failure_classification",
                state.get("failure_classification", "NONE"),
            )
        )
        if candidate != "NONE":
            failure_candidates.append(candidate)
        named_documents = (
            (
                "connection_handshake_v5.json",
                handshakes,
            ),
            ("graceful_shutdown_v5.json", shutdowns),
            ("runtime_product_validation_v5.json", products),
            ("end_of_stream_drain.json", drains),
            ("tail_clock_handoff.json", handoffs),
            ("post_run_source_binary_clip_lock.json", locks),
        )
        for filename, destination in named_documents:
            value = read_json_if_present(directory / filename)
            if value:
                destination.append({**identity, **value})
        node_info = directory / "rosnode_info.txt"
        if node_info.is_file():
            consumed = _gt_topics(
                node_info.read_text(encoding="utf-8", errors="replace")
            )
            no_gt.append(
                {
                    **identity,
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
            if path.is_file():
                full_logs.append(
                    {
                        "run_id": RUN_ID,
                        **identity,
                        "relative_path": path.relative_to(run_root).as_posix(),
                        "size_bytes": path.stat().st_size,
                        "sha256": file_sha256(path),
                        "included_in_audit_package": False,
                        "exclusion_reason": "LARGE_REAL_RUNTIME_LOG_NOT_SHARED",
                    }
                )

    quick: dict[str, Any] | None = None
    outdoor: dict[str, Any] | None = None
    completed = {(sequence, repeat) for sequence, repeat, _ in complete_identities}
    if all(("avia_quick_shack", repeat) in completed for repeat in REPEATS):
        try:
            quick = compare_sequence(run_root, "avia_quick_shack")
        except Exception:
            quick = None
    if all(
        ("avia_outdoor_run_100hz", repeat) in completed
        for repeat in REPEATS
    ):
        try:
            outdoor = compare_sequence(
                run_root, "avia_outdoor_run_100hz"
            )
        except Exception:
            outdoor = None
    sequence_results = [
        result for result in (quick, outdoor) if result is not None
    ]
    comparisons = [
        row for result in sequence_results for row in result["comparisons"]
    ]
    boundaries = [
        row for result in sequence_results for row in result["boundaries"]
    ]
    matrix_state = read_json_if_present(run_root / "matrix_state.json")
    heartbeat_rows, max_heartbeat_gap = heartbeat_evidence(run_root)
    interruption_count = int(
        matrix_state.get("runner_interruption_count", 0)
    )
    matrix_failure = str(
        matrix_state.get("failure_classification", "NONE")
    )
    if matrix_failure != "NONE":
        failure = matrix_failure
    elif failure_candidates:
        failure = failure_candidates[0]
    elif existing_identities:
        failure = "RUNTIME_PRODUCT_MISSING"
    else:
        failure = "RUNNER_SESSION_INTERRUPTED"

    endpoint_pass = (
        file_sha256(endpoint_path) == lock.get("endpoint_contract_sha256")
    )
    fast_unchanged = bool(lock.get("fastlio2_unchanged_pass", False))
    tail_protocol_pass = bool(
        lock.get("tail_clock_protocol_test_pass", False)
    )
    all_six_handoffs = len(handoffs) == 6
    all_six_drains = len(drains) == 6
    all_six_handshakes = len(handshakes) == 6
    all_six_shutdowns = len(shutdowns) == 6
    all_six_products = len(products) == 6
    all_six_locks = len(locks) == 6
    tail_handoff_pass = all_six_handoffs and all(
        bool(row.get("handoff_pass")) for row in handoffs
    )
    tail_no_overlap = all_six_handoffs and all(
        int(row.get("clock_publisher_overlap_count", 0)) == 0
        for row in handoffs
    )
    tail_monotonic = all_six_handoffs and all(
        row.get("tail_first_clock_ns") is not None
        and int(row["tail_first_clock_ns"])
        == int(row["last_bag_clock_ns"])
        + int(row["tail_clock_step_ns"])
        and int(row.get("clock_duplicate_count", 0)) == 0
        and int(row.get("clock_backward_count", 0)) == 0
        for row in handoffs
    )
    main_loop_progress = all_six_drains and all(
        row.get("main_loop_heartbeat_start") is not None
        and row.get("main_loop_heartbeat_end") is not None
        and int(row["main_loop_heartbeat_end"])
        > int(row["main_loop_heartbeat_start"])
        for row in drains
    )
    drain_wall_timeout = (
        all_six_drains
        and bool(
            lock.get(
                "drain_service_wall_timeout_implementation_pass", False
            )
        )
        and all(
            int(row.get("service_call_timeout_count", 0)) == 0
            for row in drains
        )
    )
    callbacks_pass = all_six_drains and all(
        row.get("actual_lidar_callback_count")
        == row.get("expected_lidar_callback_count")
        and row.get("actual_imu_callback_count")
        == row.get("expected_imu_callback_count")
        and row.get("actual_last_lidar_header_stamp_ns")
        == row.get("expected_last_lidar_header_stamp_ns")
        and row.get("actual_last_imu_header_stamp_ns")
        == row.get("expected_last_imu_header_stamp_ns")
        for row in drains
    )
    drain_pass = all_six_drains and all(
        bool(row.get("drain_pass")) for row in drains
    )
    handshake_pass = all_six_handshakes and all(
        bool(row.get("handshake_pass"))
        and bool(row.get("unpause_success"))
        for row in handshakes
    )
    shutdown_pass = all_six_shutdowns and all(
        bool(row.get("shutdown_completed")) for row in shutdowns
    )
    product_pass = all_six_products and all(
        bool(row.get("runtime_product_pass")) for row in products
    )
    source_pass = all_six_locks and all(
        bool(row.get("source_lock_pass"))
        and bool(row.get("binary_lock_pass"))
        and bool(row.get("clip_lock_pass"))
        for row in locks
    )
    runner_persistence = bool(
        len(complete_identities) == 6
        and interruption_count == 0
        and heartbeat_rows
    )
    formal_replay_started = bool(existing_identities)
    quick_pass = bool(quick and quick["repeatability_pass"])
    outdoor_pass = bool(outdoor and outdoor["repeatability_pass"])
    gates = {
        "REPLAY_ENDPOINT_CONTRACT_PASS": endpoint_pass,
        "FAST_LIO2_UNCHANGED_PASS": fast_unchanged,
        "TAIL_CLOCK_PROTOCOL_TEST_PASS": tail_protocol_pass,
        "TAIL_CLOCK_HANDOFF_PASS": tail_handoff_pass,
        "TAIL_CLOCK_NO_OVERLAP_PASS": tail_no_overlap,
        "TAIL_CLOCK_MONOTONIC_PASS": tail_monotonic,
        "TAIL_CLOCK_MAIN_LOOP_PROGRESS_PASS": main_loop_progress,
        "DRAIN_SERVICE_WALL_TIMEOUT_PASS": drain_wall_timeout,
        "ALL_CALLBACKS_RECEIVED_PASS": callbacks_pass,
        "END_OF_STREAM_DRAIN_PASS": drain_pass,
        "RUNNER_PERSISTENCE_PASS": runner_persistence,
        "NORMAL_SHUTDOWN_PASS": shutdown_pass,
        "RUNTIME_PRODUCT_COMPLETENESS_PASS": product_pass,
        "QUICK_BASELINE_REPEATABILITY_PASS": quick_pass,
        "OUTDOOR_BASELINE_REPEATABILITY_PASS": outdoor_pass,
        "BASELINE_REPEATABILITY_PASS": False,
        "DAY5_STARTUP_SYNC_V5_PASS": False,
        "DAY5_CAPTURE_EXPORT_REMEDIATION_AUTHORIZED": False,
        "DAY5_RUNTIME_EQUIVALENCE_PASS": False,
        "OFF_ON_REPLAY_EQUIVALENCE_STATUS": (
            "NOT_REEVALUATED_STARTUP_SYNC_ONLY"
        ),
        "DAY6_QUICK_DIAGNOSTICS_AUTHORIZED": False,
        "FAILURE_CLASSIFICATION": failure,
        "STRICT_CROSS_PROCESS_REPLAY_ROUTE_STATUS": (
            "ABANDONED_AFTER_V5"
            if formal_replay_started
            else "NOT_STARTED"
        ),
        "STRICT_REPLAY_FURTHER_REMEDIATION_AUTHORIZED": False,
        "CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE": "NOT_PROVEN",
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
        "executed_replay_count": len(existing_identities),
        "successful_replay_count": len(complete_identities),
        "supervisor_pid": matrix_state.get("supervisor_pid"),
        "supervisor_terminal_state": matrix_state.get(
            "status", "NOT_STARTED"
        ),
        "supervisor_heartbeat_count": len(heartbeat_rows),
        "supervisor_max_heartbeat_gap_sec": max_heartbeat_gap,
        "runner_interruption_count": interruption_count,
        "per_run_last_bag_clock_ns": [
            row.get("last_bag_clock_ns") for row in handoffs
        ],
        "per_run_tail_first_clock_ns": [
            row.get("tail_first_clock_ns") for row in handoffs
        ],
        "per_run_tail_publish_count": [
            row.get("tail_publish_count", 0) for row in handoffs
        ],
        "per_run_tail_final_clock_ns": [
            row.get("tail_final_clock_ns") for row in handoffs
        ],
        "clock_publisher_overlap_count": _sum(
            handoffs, "clock_publisher_overlap_count"
        ),
        "clock_duplicate_count": _sum(
            handoffs, "clock_duplicate_count"
        ),
        "clock_backward_count": _sum(
            handoffs, "clock_backward_count"
        ),
        "service_call_timeout_sec": lock.get(
            "service_call_timeout_sec", 2.0
        ),
        "service_call_timeout_count": _sum(
            drains, "service_call_timeout_count"
        ),
        "max_consecutive_service_timeouts": max(
            (
                int(row.get("max_consecutive_service_timeouts", 0))
                for row in drains
            ),
            default=0,
        ),
        "per_run_callback_counts": [
            {
                "sequence_id": row["sequence_id"],
                "repeat_id": row["repeat_id"],
                "lidar": row.get("actual_lidar_callback_count"),
                "imu": row.get("actual_imu_callback_count"),
            }
            for row in drains
        ],
        "per_run_processed_measure_group_counts": [
            row.get("final_processed_measure_group_count")
            for row in drains
        ],
        "per_run_unprocessed_lidar_tail_counts": [
            row.get("unprocessed_lidar_tail_count") for row in drains
        ],
        "per_run_remaining_imu_counts": [
            row.get("remaining_imu_count") for row in drains
        ],
        "per_run_main_loop_heartbeat_growth": [
            {
                "sequence_id": row["sequence_id"],
                "repeat_id": row["repeat_id"],
                "start": row.get("main_loop_heartbeat_start"),
                "end": row.get("main_loop_heartbeat_end"),
                "growth": (
                    int(row["main_loop_heartbeat_end"])
                    - int(row["main_loop_heartbeat_start"])
                    if row.get("main_loop_heartbeat_start") is not None
                    and row.get("main_loop_heartbeat_end") is not None
                    else None
                ),
            }
            for row in drains
        ],
        "paired_scan_count": _sum(comparisons, "paired_scan_count"),
        "missing_scan_count": _sum(comparisons, "missing_scan_count"),
        "duplicate_scan_count": _sum(
            comparisons, "duplicate_scan_count"
        ),
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
            comparisons,
            "formal_native_jacobian_checksum_mismatch_count",
        ),
        "residual_mismatch_count": _sum(
            comparisons, "geometric_residual_checksum_mismatch_count"
        ),
        "accepted_index_mismatch_count": _sum(
            comparisons, "accepted_index_checksum_mismatch_count"
        ),
        "correspondence_mismatch_count": _sum(
            comparisons,
            "formal_correspondence_checksum_mismatch_count",
        ),
        "posterior_state_mismatch_count": _sum(
            comparisons, "posterior_state_checksum_mismatch_count"
        ),
        "posterior_covariance_mismatch_count": _sum(
            comparisons,
            "posterior_covariance_checksum_mismatch_count",
        ),
        "map_size_mismatch_count": _sum(
            comparisons, "map_size_after_update_mismatch_count"
        ),
        "final_map_mismatch_count": sum(
            not row.get("final_map_equivalence_pass", False)
            for row in comparisons
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
            first_divergence.get("first_divergence_scan_index")
            if first_divergence
            else None
        ),
        "first_divergence_stage": (
            first_divergence.get("first_divergence_stage")
            if first_divergence
            else "NONE"
        ),
        "drain_pass_count": sum(
            bool(row.get("drain_pass")) for row in drains
        ),
        "shutdown_completed_count": sum(
            bool(row.get("shutdown_completed")) for row in shutdowns
        ),
        "runtime_product_pass_count": sum(
            bool(row.get("runtime_product_pass")) for row in products
        ),
        "quick": quick,
        "outdoor": outdoor,
        "outdoor_executed": any(
            sequence == "avia_outdoor_run_100hz"
            for sequence, _repeat, _directory in existing_identities
        ),
        "roscore_run": formal_replay_started,
        "roslaunch_run": formal_replay_started,
        "rosbag_run": formal_replay_started,
        "real_data_used": formal_replay_started,
        "engineering_quick_replay_run": formal_replay_started,
        "capture_only_run": False,
        "compact_export_run": False,
        "detector_called": False,
        "odi_computed": False,
        "scientific_experiment_run": False,
        "development_run": False,
        "holdout_run": False,
        "future_test_run": False,
        "detector_modified": False,
        "threshold_modified": False,
        "day5_commit_created": False,
        "push_performed": False,
        "RECOMMENDED_FALLBACK_EVIDENCE_ROUTE": (
            "IN_CALL_IMMUTABILITY+FROZEN_OBSERVATION_RECORD+"
            "OFFLINE_PRODUCTION_DETECTOR_DETERMINISM+"
            "REAL_REPLAY_FUNCTIONAL_STATISTICAL_TOLERANCE"
        ),
    }

    tail_summary, monotonic_rows, transition_rows = tail_clock_rows(
        handoffs
    )
    write_csv(run_root / "tail_clock_handoff_summary.csv", tail_summary)
    write_csv(
        run_root / "tail_clock_monotonicity_audit.csv", monotonic_rows
    )
    write_csv(
        run_root / "clock_publisher_transition_audit.csv", transition_rows
    )
    write_csv(
        run_root / "drain_service_timeout_summary.csv",
        drain_timeout_rows(drains),
    )
    write_csv(run_root / "end_of_stream_drain_summary.csv", drains)
    write_csv(
        run_root / "callback_endpoint_summary.csv",
        [
            {
                key: value
                for key, value in row.items()
                if "callback" in key
                or "header_stamp" in key
                or key in {"sequence_id", "repeat_id", "drain_pass"}
            }
            for row in drains
        ],
    )
    write_csv(run_root / "single_run_inventory.csv", run_rows)
    write_csv(run_root / "connection_handshake_summary.csv", handshakes)
    write_csv(run_root / "runtime_product_completeness.csv", products)
    write_csv(run_root / "source_binary_clip_lock_audit.csv", locks)
    write_csv(run_root / "no_gt_runtime_audit.csv", no_gt)
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
                "tail_clock_repeatable": result["tail_clock_repeatable"],
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
    write_csv(
        run_root / "gate_summary.csv",
        [{"gate": key, "value": value} for key, value in gates.items()],
    )
    write_csv(run_root / "full_log_index.csv", full_logs)
    if not (run_root / "supervisor_summary.csv").is_file():
        write_csv(
            run_root / "supervisor_summary.csv",
            [
                {
                    "supervisor_pid": matrix_state.get("supervisor_pid"),
                    "heartbeat_count": len(heartbeat_rows),
                    "max_heartbeat_gap_sec": max_heartbeat_gap,
                    "runner_interruption_count": interruption_count,
                    "terminal_state": matrix_state.get(
                        "status", "NOT_STARTED"
                    ),
                    "failure_classification": failure,
                }
            ],
        )
    write_json(
        run_root / "day5_startup_sync_v5_run_manifest.json",
        {"run_id": RUN_ID, "runs": run_rows},
    )
    write_json(run_root / "day5_startup_sync_v5_summary.json", summary)
    write_json(run_root / "day5_startup_sync_v5_gate_summary.json", gates)
    return summary


def copy_small_results(run_root: Path) -> None:
    destination = (
        ROOT
        / "artifacts/current/harmful_bias_multihyp_dev/day5_startup_sync_v5"
    )
    if destination.exists():
        raise RuntimeError(f"small result directory exists: {destination}")
    destination.mkdir(parents=True)
    names = (
        "replay_endpoint_contract_v1.json",
        "endpoint_contract_validation.json",
        "supervisor_final_state.json",
        "supervisor_summary.csv",
        "single_run_inventory.csv",
        "connection_handshake_summary.csv",
        "tail_clock_handoff_summary.csv",
        "tail_clock_monotonicity_audit.csv",
        "clock_publisher_transition_audit.csv",
        "drain_service_timeout_summary.csv",
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
        "day5_startup_sync_v5_run_manifest.json",
        "day5_startup_sync_v5_summary.json",
        "day5_startup_sync_v5_gate_summary.json",
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
    parser.add_argument("--partial", action="store_true")
    parser.add_argument("--copy-small-results", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_root = args.run_root.expanduser().resolve()
    if args.quick_gate:
        if args.partial:
            raise SystemExit("ERROR: --quick-gate and --partial are exclusive")
        result = compare_sequence(run_root, "avia_quick_shack")
        print(json.dumps(result, sort_keys=True))
        return int(not result["repeatability_pass"])
    endpoint = args.endpoint_contract.expanduser().resolve()
    run_lock = args.run_lock.expanduser().resolve()
    summary = (
        finalize_partial(run_root, endpoint, run_lock)
        if args.partial
        else finalize(run_root, endpoint, run_lock)
    )
    if args.copy_small_results:
        copy_small_results(run_root)
    print(json.dumps(summary, sort_keys=True))
    return int(not summary["DAY5_STARTUP_SYNC_V5_PASS"])


if __name__ == "__main__":
    raise SystemExit(main())
