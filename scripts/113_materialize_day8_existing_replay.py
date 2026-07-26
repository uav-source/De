#!/usr/bin/env python3
"""Materialize a completed Day 8 replay without starting ROS or rosbag."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter import experiment_a_map_snapshot_coherence as snapshots


RUN_IDS = tuple(f"multihyp_day8_range_query_r{i}" for i in range(1, 5))


def _load_runner() -> Any:
    path = ROOT / "scripts/108_run_day8_range_query_diagnostics.py"
    spec = importlib.util.spec_from_file_location("day8_existing_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load Day 8 runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--original-runner-exit-code", required=True, type=int)
    args = parser.parse_args()
    run_dir = args.run_dir.expanduser().resolve()
    summary_path = run_dir / "run_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    run_id = str(summary.get("run_id", ""))
    if run_id not in RUN_IDS:
        raise RuntimeError("unauthorized existing Day 8 run id")
    if not all((
        summary.get("complete") is True,
        summary.get("runtime_product_pass") is True,
        summary.get("normal_shutdown_pass") is True,
        summary.get("lidar_callback_count") == 491,
        summary.get("imu_callback_count") == 9953,
        summary.get("runtime_scan_count") == 490,
        summary.get("observation_record_count") == 487,
    )):
        raise RuntimeError("existing scientific replay is incomplete")

    runner = _load_runner()
    day7 = runner._validate_day7_trace(run_dir)
    day8 = runner.validate_run_query_trace(run_dir)
    snapshots.SCAN_START = runner.SCAN_START
    snapshots.SCAN_END = runner.SCAN_END
    snapshots.EXPECTED_RECORD_COUNT = runner.EXPECTED_RECORD_COUNT
    snapshots.EXPECTED_SNAPSHOTS_PER_RUN = runner.EXPECTED_SNAPSHOT_COUNT
    snapshots.EXPECTED_TOTAL_SNAPSHOTS = 2 * runner.EXPECTED_SNAPSHOT_COUNT
    records = json.loads(
        (run_dir / "experiment_a_stage_hash_records_v2.json").read_text(
            encoding="utf-8"
        )
    )
    snapshot = snapshots.materialize_snapshot_evidence(records, run_dir)
    if not all((
        snapshot["map_snapshot_coherence_pass"],
        snapshot["map_snapshot_cross_scan_coherence_pass"],
        snapshot["coherent_snapshot_count"] == runner.EXPECTED_SNAPSHOT_COUNT,
        snapshot["incoherent_snapshot_count"] == 0,
        snapshot["cross_scan_continuity_violation_count"] == 0,
        day7["event_overflow_count"] == 0,
        day7["unclassified_event_count"] == 0,
        day8["query_summary_count"] > 0,
        day8["traversal_token_count"] > 0,
        not any(day8["overflow"].values()),
    )):
        raise RuntimeError("existing Day 8 product gate failed")

    summary.update({
        "schema_version": "day8_range_query_replay_run_summary_v1",
        "stage_hash_v2_record_count": summary["stage_hash_record_count"],
        "map_before_snapshot_count": snapshot["map_before_snapshot_count"],
        "map_after_snapshot_count": snapshot["map_after_snapshot_count"],
        "coherent_snapshot_count": snapshot["coherent_snapshot_count"],
        "incoherent_snapshot_count": snapshot["incoherent_snapshot_count"],
        "cross_scan_continuity_violation_count":
            snapshot["cross_scan_continuity_violation_count"],
        "map_snapshot_coherence_pass":
            snapshot["map_snapshot_coherence_pass"],
        "map_snapshot_cross_scan_coherence_pass":
            snapshot["map_snapshot_cross_scan_coherence_pass"],
        "snapshot_lock_wait_statistics": snapshot["lock_wait_ns"],
        "snapshot_copy_cost_statistics": snapshot["locked_copy_ns"],
        "day7_map_update_audit_enabled": True,
        "day7_support_scan_start": runner.DAY7_SCAN_START,
        "day7_support_scan_end": runner.DAY7_SCAN_END,
        "day7_support_snapshot_count": day7["snapshot_count"],
        "day7_event_overflow_count": day7["event_overflow_count"],
        "day7_unclassified_event_count": day7["unclassified_event_count"],
        "day7_map_delta_accounting_failure_count":
            day7["map_delta_accounting_failure_count"],
        "map_mutation_event_count": day7["event_count"],
        "day8_range_query_audit_enabled": True,
        "day8_scan_start": runner.SCAN_START,
        "day8_scan_end": runner.SCAN_END,
        "day8_stage_record_count": runner.EXPECTED_RECORD_COUNT,
        "day8_snapshot_count": runner.EXPECTED_SNAPSHOT_COUNT,
        "range_query_summary_count": day8["query_summary_count"],
        "detailed_traversal_token_count":
            day8["traversal_token_count"],
        "formal_result_member_count": day8["formal_result_member_count"],
        "point_voxel_snapshot_count": day8["point_voxel_snapshot_count"],
        "day8_query_schema_error_count":
            day8["query_schema_error_count"],
        "day8_query_trace_validation_pass": True,
        "instrumentation_timing_perturbation_present": True,
        "original_day8_runner_exit_code":
            args.original_runner_exit_code,
        "existing_replay_materialization_exit_code": 0,
        "existing_replay_materialization_pass": True,
        "replay_rerun": False,
        "wrapper_exit_code": 0,
        "wrapper_failure_classification": "NONE",
        "wrapper_pipeline_clean_exit_pass": True,
    })
    summary["complete"] = True
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    evidence = {
        "schema_version":
            "day8_existing_replay_materialization_evidence_v1",
        "run_id": run_id,
        "original_day8_runner_exit_code":
            args.original_runner_exit_code,
        "existing_replay_materialization_exit_code": 0,
        "scientific_replay_complete_before_materialization": True,
        "ros_started_by_materialization": False,
        "rosbag_started_by_materialization": False,
        "replay_rerun": False,
        "day7_map_delta_accounting_failure_count":
            day7["map_delta_accounting_failure_count"],
        "per_run_gate_pass": True,
    }
    (run_dir / "day8_existing_replay_materialization_evidence.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
