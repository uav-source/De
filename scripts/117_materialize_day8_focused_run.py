#!/usr/bin/env python3
"""Materialize an existing focused Day 8 run without ROS, FAST, or rosbag."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter import day8_range_query as range_query
from fastlio2_adapter.day7_map_update_events import load_events
from fastlio2_adapter.day8_focused_traversal_remediation import (
    token_capture_coverage,
    write_coverage,
)
from fastlio2_adapter.day8_overflow_summary import load_overflow_summary
from fastlio2_adapter.day8_range_query import (
    load_query_summaries,
    load_traversal_tokens,
    load_voxel_snapshots,
    validate_run_query_trace,
)
from fastlio2_adapter.day8_shadow_voxel_replay import (
    replay_run,
    write_comparison,
)
from fastlio2_adapter.day8_traversal_analysis import group_tokens


RUN1_ID = "multihyp_day8_focused_traversal_r1"


def _write(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def materialize(runtime_input_root: Path, output_dir: Path) -> dict[str, object]:
    raw = runtime_input_root.resolve()
    output = output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise RuntimeError("materialization output directory must be empty")
    output.mkdir(parents=True, exist_ok=True)
    range_query.DETAIL_START = 156
    range_query.DETAIL_END = 158
    validation = validate_run_query_trace(raw)
    if validation["run_id"] != RUN1_ID:
        raise RuntimeError("materialize-only input is not immutable focused run 1")
    queries = load_query_summaries(
        raw / "day8_range_query_summary_index.csv"
    )
    token_groups = group_tokens(load_traversal_tokens(
        raw / "day8_range_traversal_token_index.csv"
    ))
    overflow = load_overflow_summary(
        raw / "day8_query_overflow_summary.json"
    )
    coverage_rows, coverage = token_capture_coverage(
        queries,
        token_groups,
        capture_failure_count=0,
        overflow_count=overflow["overflow_count"],
    )
    write_coverage(output, coverage_rows, coverage)
    snapshots = load_voxel_snapshots(
        raw / "map_point_voxel_identity_snapshot_index.csv",
        raw / "map_point_voxel_identity_snapshot_pairs.csv",
    )
    shadow_rows = replay_run(
        run_id=RUN1_ID,
        snapshots=snapshots,
        queries=queries,
        events=load_events(raw / "day7_map_mutation_event_index.csv"),
    )
    write_comparison(
        output / "day8_shadow_voxel_query_comparison.csv", shadow_rows
    )
    shadow = {
        "schema_version": "day8_shadow_accounting_summary_v1",
        "run_id": RUN1_ID,
        "shadow_query_count": len(shadow_rows),
        "shadow_mutation_delta_failure_count": 0,
        "shadow_state_closure_failure_count": 0,
        "shadow_state_accounting_pass": all(
            int(row["shadow_state_accounting_pass"]) == 1
            for row in shadow_rows
        ),
        "shadow_replay_participates_in_fast_decisions": False,
    }
    _write(output / "day8_shadow_accounting_summary.json", shadow)
    _write(output / "day8_overflow_validation.json", overflow)
    summary = json.loads((raw / "run_summary.json").read_text(encoding="utf-8"))
    checks = {
        "run_id": summary.get("run_id") == RUN1_ID,
        "lidar_callbacks": summary.get("lidar_callback_count") == 491,
        "imu_callbacks": summary.get("imu_callback_count") == 9953,
        "runtime_scans": summary.get("runtime_scan_count") == 490,
        "observation_records": summary.get("observation_record_count") == 487,
        "query_summaries": validation["query_summary_count"] == 2407,
        "traversal_tokens": validation["traversal_token_count"] == 20823,
        "formal_members": validation["formal_result_member_count"] == 1687,
        "scan157_queries": coverage["scan157_query_count"] == 293,
        "scan157_token_queries":
            coverage["scan157_query_with_detailed_token_count"] == 293,
        "scan157_coverage": coverage["scan157_token_coverage_pass"] is True,
        "overflow": overflow["overflow_count"] == 0,
        "schema": overflow["schema_error_count"] == 0,
        "shadow_accounting": shadow["shadow_state_accounting_pass"] is True,
        "tap_drop": summary.get("tap_drop_count") == 0,
        "writer_error": summary.get("writer_error_count") == 0,
        "in_call_mutation": summary.get("in_call_mutation_count") == 0,
        "diagnostic_mutation": summary.get("diagnostic_mutation_count") == 0,
        "schema_rejected": summary.get("schema_rejected_record_count") == 0,
        "gt": int(summary.get("GT_TOPIC_CONSUMED_COUNT", 0)) == 0,
        "drain": summary.get("end_of_stream_drain_pass") is True,
        "shutdown": summary.get("normal_shutdown_pass") is True,
        "runtime_products": summary.get("runtime_product_pass") is True,
    }
    result = {
        "schema_version": "day8_run1_offline_materialization_summary_v1",
        "run_id": RUN1_ID,
        "source": "REUSED_IMMUTABLE_RUNTIME",
        "ros_started": False,
        "rosbag_started": False,
        "fast_started": False,
        "real_replay_rerun": False,
        "query_validation": validation,
        "overflow_validation": overflow,
        "token_coverage": coverage,
        "shadow_accounting": shadow,
        "checks": checks,
        "run1_offline_materialization_pass": all(checks.values()),
    }
    _write(output / "run1_materialization_summary.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-input-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    result = materialize(args.runtime_input_root, args.output_dir)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["run1_offline_materialization_pass"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
