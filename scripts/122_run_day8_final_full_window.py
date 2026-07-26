#!/usr/bin/env python3
"""Run one of exactly four locked final full-window Day 8 replays."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter import day8_range_query as range_query
from fastlio2_adapter.day7_map_update_events import load_events
from fastlio2_adapter.day8_final_full_window_analysis import (
    DETAILED_TOKEN_SCAN_END,
    DETAILED_TOKEN_SCAN_START,
    MAIN_RUN_ID,
    QUERY_SUMMARY_SCAN_END,
    QUERY_SUMMARY_SCAN_START,
    ROS_MASTER_PORTS,
    RUN_IDS,
    token_capture_coverage,
    write_coverage,
)
from fastlio2_adapter.day8_overflow_summary import parse_overflow_summary
from fastlio2_adapter.day8_range_query import (
    load_query_summaries,
    load_traversal_tokens,
    load_voxel_snapshots,
)
from fastlio2_adapter.day8_shadow_voxel_replay import (
    replay_run,
    write_comparison,
)
from fastlio2_adapter.day8_token_semantics_v3 import (
    TOKEN_CAPTURE_SEMANTICS_VERSION,
)
from fastlio2_adapter.day8_traversal_analysis import group_tokens


SOURCE_AUDIT_SHA256 = (
    "491d5341227c22077742a89d77c84b4250e71729dd5cd79b3f35394ca1de0272"
)
AUTHORIZATION_SHA256 = (
    "f5cc7069e356005c32c3d28e21b27f1ea6dedf574b29f9a155e1856ea000f835"
)
AUTHORIZATION_SCHEMA = "day8_final_full_window_authorization_v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def validate_authorization(
    source_archive: Path,
    authorization: Path,
) -> dict[str, Any]:
    source = source_archive.expanduser().resolve()
    auth_path = authorization.expanduser().resolve()
    if not source.is_file() or _sha256(source) != SOURCE_AUDIT_SHA256:
        raise RuntimeError("source Day 8 audit identity mismatch")
    if not auth_path.is_file() or _sha256(auth_path) != AUTHORIZATION_SHA256:
        raise RuntimeError("final full-window authorization identity mismatch")
    value = json.loads(auth_path.read_text(encoding="utf-8"))
    required = {
        "schema_version": AUTHORIZATION_SCHEMA,
        "source_audit_sha256": SOURCE_AUDIT_SHA256,
        "source_four_replay_runs_complete": True,
        "source_shadow_accounting_pass": True,
        "source_strict_identity_result_divergence_reproduced": False,
        "source_query_completeness_violation_observed": False,
        "source_null_token_semantics_fully_propagated": False,
        "source_audit_package_scope_pass": False,
        "authorized_query_summary_window": [155, 165],
        "authorized_detailed_token_window": [155, 165],
        "authorized_new_replay_count": 4,
        "fifth_replay_authorized": False,
        "previous_run_reuse_authorized": False,
        "fast_source_change_authorized": False,
        "fast_build_authorized": False,
        "strict_identity_alignment_remediation_authorized": True,
        "null_token_contract_remediation_authorized": True,
        "plot_contract_remediation_authorized": True,
        "analysis_hotfix_after_runtime_lock_authorized": False,
        "close_random_replay_route_if_not_reproduced": True,
        "day9_authorized": False,
        "stage3_start_authorized": False,
        "fast_lio2_integration_authorized": False,
    }
    mismatches = {
        key: {"expected": expected, "actual": value.get(key)}
        for key, expected in required.items()
        if value.get(key) != expected
    }
    if mismatches:
        raise RuntimeError(f"final authorization fields mismatch: {mismatches}")
    return {
        "schema_version": "day8_final_authorization_identity_v1",
        "source_audit_sha256": SOURCE_AUDIT_SHA256,
        "authorization_sha256": AUTHORIZATION_SHA256,
        "authorized_new_replay_count": 4,
        "fifth_replay_authorized": False,
        "previous_run_reuse_authorized": False,
        "DAY8_FINAL_FULL_WINDOW_AUTHORIZATION_PASS": True,
        "day9_authorized": False,
    }


def validate_run_lock(path: Path, run_id: str) -> dict[str, Any]:
    value = json.loads(path.resolve().read_text(encoding="utf-8"))
    expected = {
        "main_run_id": MAIN_RUN_ID,
        "sub_run_ids": list(RUN_IDS),
        "source_audit_sha256": SOURCE_AUDIT_SHA256,
        "authorization_sha256": AUTHORIZATION_SHA256,
        "query_summary_window": [155, 165],
        "detailed_token_window": [155, 165],
        "run_count": 4,
        "fast_cpu_core": 22,
        "rosbag_cpu_core": 23,
        "playback_rate": 0.25,
    }
    mismatches = {
        key: {"expected": expected_value, "actual": value.get(key)}
        for key, expected_value in expected.items()
        if value.get(key) != expected_value
    }
    if mismatches:
        raise RuntimeError(f"final run-lock contract mismatch: {mismatches}")
    if value.get("ros_master_ports") != ROS_MASTER_PORTS:
        raise RuntimeError("final ROS master port map mismatch")
    if value["ros_master_ports"].get(run_id) != ROS_MASTER_PORTS[run_id]:
        raise RuntimeError("final ROS master port mismatch")
    return value


def _final_materialize(output: Path) -> dict[str, Any]:
    queries = load_query_summaries(
        output / "day8_range_query_summary_index.csv"
    )
    grouped = group_tokens(load_traversal_tokens(
        output / "day8_range_traversal_token_index.csv"
    ))
    overflow = json.loads(
        (output / "day8_query_overflow_summary.json").read_text(
            encoding="utf-8"
        )
    )
    parsed = parse_overflow_summary(overflow)
    rows, coverage = token_capture_coverage(
        queries,
        grouped,
        capture_failure_count=0,
        overflow_count=parsed["overflow_count"],
    )
    write_coverage(output, rows, coverage)
    snapshots = load_voxel_snapshots(
        output / "map_point_voxel_identity_snapshot_index.csv",
        output / "map_point_voxel_identity_snapshot_pairs.csv",
    )
    shadow = replay_run(
        run_id=str(queries[0]["run_id"]),
        snapshots=snapshots,
        queries=queries,
        events=load_events(output / "day7_map_mutation_event_index.csv"),
        tolerate_accounting_failure=False,
    )
    write_comparison(
        output / "day8_shadow_voxel_query_comparison.csv",
        shadow,
    )
    accounting = {
        "schema_version": "day8_final_shadow_accounting_summary_v1",
        "run_id": queries[0]["run_id"],
        "shadow_query_count": len(shadow),
        "shadow_member_total": sum(
            int(row["shadow_member_count"]) for row in shadow
        ),
        "formal_member_total": sum(
            int(row["formal_result_count"]) for row in shadow
        ),
        "shadow_accounting_failure_count": sum(
            int(row["shadow_state_accounting_pass"]) != 1 for row in shadow
        ),
        "shadow_mutation_delta_failure_count": 0,
        "shadow_state_closure_failure_count": 0,
        "shadow_state_accounting_pass": all(
            int(row["shadow_state_accounting_pass"]) == 1 for row in shadow
        ),
        "shadow_replay_participates_in_fast_decisions": False,
    }
    (output / "day8_shadow_accounting_summary.json").write_text(
        json.dumps(accounting, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not all((
        coverage["FULL_WINDOW_QUERY_SUMMARY_COVERAGE_PASS"],
        coverage["FULL_WINDOW_DETAILED_TOKEN_COVERAGE_PASS"],
        coverage["token_capture_failure_count"] == 0,
        coverage["unclassified_token_count"] == 0,
        accounting["shadow_state_accounting_pass"],
    )):
        raise RuntimeError("final per-run token/shadow gate failed")
    return {
        "token_semantics_version": TOKEN_CAPTURE_SEMANTICS_VERSION,
        "full_window_per_scan_token_coverage": coverage["per_scan"],
        "full_window_query_summary_coverage_pass": True,
        "full_window_detailed_token_coverage_pass": True,
        "token_capture_failure_count": 0,
        "unclassified_token_count": 0,
        "shadow_accounting_failure_count": 0,
        "shadow_state_accounting_pass": True,
    }


def _run_complete(summary: Mapping[str, Any]) -> bool:
    gt_count = summary.get(
        "ground_truth_topic_count",
        summary.get("GT_TOPIC_CONSUMED_COUNT"),
    )
    per_scan = summary.get("full_window_per_scan_token_coverage", {})
    return all((
        summary.get("wrapper_exit_code") == 0,
        summary.get("wrapper_pipeline_clean_exit_pass") is True,
        summary.get("adjudicated_tail_handoff_pass") is True,
        summary.get("runtime_product_pass") is True,
        summary.get("end_of_stream_drain_pass") is True,
        summary.get("normal_shutdown_pass") is True,
        summary.get("lidar_callback_count") == 491,
        summary.get("imu_callback_count") == 9953,
        summary.get("runtime_scan_count") == 490,
        summary.get("observation_record_count") == 487,
        summary.get("stage_hash_record_count") == 11,
        summary.get("stage_hash_first_scan") == 155,
        summary.get("stage_hash_last_scan") == 165,
        summary.get("coherent_snapshot_count") == 22,
        summary.get("incoherent_snapshot_count") == 0,
        summary.get("cross_scan_continuity_violation_count") == 0,
        summary.get("tap_drop_count") == 0,
        summary.get("writer_error_count") == 0,
        summary.get("in_call_mutation_count") == 0,
        summary.get("diagnostic_mutation_count") == 0,
        summary.get("schema_rejected_record_count") == 0,
        gt_count == 0,
        summary.get("full_window_query_summary_coverage_pass") is True,
        summary.get("full_window_detailed_token_coverage_pass") is True,
        len(per_scan) == 11,
        all(
            value.get("query_count", 0) > 0
            and value.get("token_coverage_pass") is True
            for value in per_scan.values()
        ),
        summary.get("shadow_state_accounting_pass") is True,
    ))


def configure_final_transport(base: Any) -> None:
    original = base.configure_day8_transport

    def configure(old: Any) -> None:
        original(old)
        prior_configure = old.configure_transport

        def configure_transport(
            transport_base: Any,
            transport: Any,
            *,
            run_id: str,
            repeat_id: int,
        ) -> None:
            prior_configure(
                transport_base,
                transport,
                run_id=run_id,
                repeat_id=repeat_id,
            )
            code = transport.execute.__code__
            if sum(value == 20500 for value in code.co_consts) != 1:
                raise RuntimeError("final ROS port anchor mismatch")
            transport.execute.__code__ = code.replace(
                co_consts=tuple(
                    20900 if value == 20500 else value
                    for value in code.co_consts
                )
            )

        old.configure_transport = configure_transport
        prior_materialize = old.materialize

        def materialize(*args: Any, **kwargs: Any) -> dict[str, Any]:
            summary = prior_materialize(*args, **kwargs)
            output = Path(kwargs["output"]).resolve()
            summary.update(_final_materialize(output))
            summary.update({
                "schema_version": "day8_final_full_window_run_summary_v1",
                "main_run_id": MAIN_RUN_ID,
                "query_summary_scan_start": QUERY_SUMMARY_SCAN_START,
                "query_summary_scan_end": QUERY_SUMMARY_SCAN_END,
                "detailed_token_scan_start": DETAILED_TOKEN_SCAN_START,
                "detailed_token_scan_end": DETAILED_TOKEN_SCAN_END,
                "ground_truth_topic_count": summary.get(
                    "ground_truth_topic_count",
                    summary.get("GT_TOPIC_CONSUMED_COUNT"),
                ),
            })
            # Wrapper fields are added after this inner materializer returns.
            summary["complete"] = bool(summary.get("complete")) and all((
                summary["full_window_query_summary_coverage_pass"],
                summary["full_window_detailed_token_coverage_pass"],
                summary["shadow_state_accounting_pass"],
                summary["ground_truth_topic_count"] == 0,
            ))
            (output / "run_summary.json").write_text(
                json.dumps(summary, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            return summary

        old.materialize = materialize

    base.configure_day8_transport = configure


def _write_final_per_run_gate(output: Path, summary: Mapping[str, Any]) -> None:
    complete = _run_complete(summary)
    gate = {
        "schema_version": "day8_final_full_window_per_run_gate_v1",
        "run_id": summary["run_id"],
        "real_replay_completed": True,
        "all_gates_pass": complete,
        "FULL_WINDOW_QUERY_SUMMARY_COVERAGE_PASS": summary[
            "full_window_query_summary_coverage_pass"
        ],
        "FULL_WINDOW_DETAILED_TOKEN_COVERAGE_PASS": summary[
            "full_window_detailed_token_coverage_pass"
        ],
        "SHADOW_STATE_ACCOUNTING_PASS": summary[
            "shadow_state_accounting_pass"
        ],
        "wrapper_exit_code": summary.get("wrapper_exit_code"),
        "lidar_callback_count": summary.get("lidar_callback_count"),
        "imu_callback_count": summary.get("imu_callback_count"),
        "observation_record_count": summary.get("observation_record_count"),
        "query_summary_count": summary.get("range_query_summary_count"),
        "traversal_token_count": summary.get(
            "detailed_traversal_token_count"
        ),
        "per_scan": summary["full_window_per_scan_token_coverage"],
    }
    (output / "day8_final_per_run_gate.json").write_text(
        json.dumps(gate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if not complete:
        raise RuntimeError("final per-run completeness gate failed")


def main() -> int:
    context_parser = argparse.ArgumentParser(add_help=False)
    context_parser.add_argument("--run-id", required=True)
    context_parser.add_argument("--output-dir", required=True, type=Path)
    context, _ = context_parser.parse_known_args()
    base = _load(
        ROOT / "scripts/108_run_day8_range_query_diagnostics.py",
        "day8_final_base_runner",
    )
    base.MAIN_RUN_ID = MAIN_RUN_ID
    base.SUB_RUN_IDS = RUN_IDS
    base.DAY7_AUDIT_SHA256 = SOURCE_AUDIT_SHA256
    base.AMENDMENT_SHA256 = AUTHORIZATION_SHA256
    base.SCAN_START = QUERY_SUMMARY_SCAN_START
    base.SCAN_END = QUERY_SUMMARY_SCAN_END
    base.DETAIL_START = DETAILED_TOKEN_SCAN_START
    base.DETAIL_END = DETAILED_TOKEN_SCAN_END
    base.validate_authorization = validate_authorization
    base.validate_run_lock = validate_run_lock
    range_query.SCAN_START = QUERY_SUMMARY_SCAN_START
    range_query.SCAN_END = QUERY_SUMMARY_SCAN_END
    range_query.DETAIL_START = DETAILED_TOKEN_SCAN_START
    range_query.DETAIL_END = DETAILED_TOKEN_SCAN_END
    configure_final_transport(base)
    result = int(base.main())
    if result == 0:
        output = context.output_dir.expanduser().resolve()
        summary_path = output / "run_summary.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        summary["ground_truth_topic_count"] = summary.get(
            "ground_truth_topic_count",
            summary.get("GT_TOPIC_CONSUMED_COUNT"),
        )
        summary["complete"] = _run_complete(summary)
        summary_path.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _write_final_per_run_gate(output, summary)
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
