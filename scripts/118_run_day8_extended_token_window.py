#!/usr/bin/env python3
"""Run one of exactly four locked Day 8 extended-token replays."""

from __future__ import annotations

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
from fastlio2_adapter.day8_extended_token_window import (
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
from fastlio2_adapter.day8_traversal_analysis import group_tokens


SOURCE_AUDIT_SHA256 = (
    "09d627d5850964ff6df518c2fe141bf508367ed85dd81ed05baec54a4e060315"
)
AUTHORIZATION_SHA256 = (
    "e336beb7c865705a5e3c2bbd464316baf985739ed8a4d60dadf0ad31d7765d4d"
)
AUTHORIZATION_SCHEMA = "day8_extended_token_window_authorization_v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import %s" % path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def validate_authorization(
    source_archive: Path,
    authorization: Path,
) -> dict[str, Any]:
    if _sha256(source_archive.expanduser().resolve()) != SOURCE_AUDIT_SHA256:
        raise RuntimeError("source Day 8 audit identity mismatch")
    auth_path = authorization.expanduser().resolve()
    if _sha256(auth_path) != AUTHORIZATION_SHA256:
        raise RuntimeError("extended token authorization identity mismatch")
    value = json.loads(auth_path.read_text(encoding="utf-8"))
    required = {
        "schema_version": AUTHORIZATION_SCHEMA,
        "source_audit_sha256": SOURCE_AUDIT_SHA256,
        "source_four_run_matrix_complete": True,
        "source_shadow_accounting_pass": True,
        "source_first_divergent_query_scan": 162,
        "source_first_divergent_query_sequence": 1841,
        "source_detailed_token_status":
            "NOT_CAPTURED_OUTSIDE_TOKEN_WINDOW",
        "source_query_summary_window": [155, 165],
        "source_detailed_token_window": [156, 158],
        "authorized_query_summary_window": [155, 165],
        "authorized_detailed_token_window": [156, 163],
        "authorized_new_replay_count": 4,
        "previous_run_reuse_authorized": False,
        "fast_source_change_authorized": False,
        "fast_build_authorized": False,
        "null_token_semantic_remediation_authorized": True,
        "analysis_hotfix_after_runtime_lock_authorized": False,
        "day9_authorized": False,
        "stage3_start_authorized": False,
        "fast_lio2_integration_authorized": False,
        "DAY8_EXTENDED_TOKEN_AUTHORIZATION_PASS": True,
    }
    if any(value.get(key) != expected for key, expected in required.items()):
        raise RuntimeError("extended token authorization fields mismatch")
    return {
        "schema_version": "day8_extended_authorization_identity_v1",
        "source_audit_sha256": SOURCE_AUDIT_SHA256,
        "authorization_sha256": AUTHORIZATION_SHA256,
        "authorized_new_replay_count": 4,
        "previous_run_reuse_authorized": False,
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
        "detailed_token_window": [156, 163],
        "run_count": 4,
        "fast_cpu_core": 22,
        "rosbag_cpu_core": 23,
        "playback_rate": 0.25,
    }
    if any(value.get(key) != expected for key, expected in expected.items()):
        raise RuntimeError("extended token run-lock contract mismatch")
    if value.get("ros_master_ports") != ROS_MASTER_PORTS:
        raise RuntimeError("extended token ROS master port map mismatch")
    if value["ros_master_ports"].get(run_id) != ROS_MASTER_PORTS[run_id]:
        raise RuntimeError("extended token run port mismatch")
    return value


def _extended_materialize(output: Path) -> dict[str, Any]:
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
        "schema_version": "day8_extended_shadow_accounting_summary_v1",
        "run_id": queries[0]["run_id"],
        "shadow_query_count": len(shadow),
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
        coverage["scan157_token_coverage_pass"],
        coverage["scan162_token_coverage_pass"],
        coverage["token_capture_failure_count"] == 0,
        coverage["unclassified_token_count"] == 0,
        accounting["shadow_state_accounting_pass"],
    )):
        raise RuntimeError("extended per-run token/shadow gate failed")
    return {
        "token_semantics_version": "TOKEN_CAPTURE_SEMANTICS_V2",
        "scan157_query_count": coverage["scan157_query_count"],
        "scan157_query_with_detailed_token_count":
            coverage["scan157_query_with_detailed_token_count"],
        "scan157_token_coverage_pass": True,
        "scan162_query_count": coverage["scan162_query_count"],
        "scan162_query_with_detailed_token_count":
            coverage["scan162_query_with_detailed_token_count"],
        "scan162_token_coverage_pass": True,
        "token_capture_failure_count": 0,
        "unclassified_token_count": 0,
        "shadow_accounting_failure_count": 0,
        "shadow_state_accounting_pass": True,
    }


def configure_extended_transport(base: Any) -> None:
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
                raise RuntimeError("extended ROS port anchor mismatch")
            transport.execute.__code__ = code.replace(
                co_consts=tuple(
                    20800 if value == 20500 else value
                    for value in code.co_consts
                )
            )

        old.configure_transport = configure_transport
        prior_materialize = old.materialize

        def materialize(*args: Any, **kwargs: Any) -> dict[str, Any]:
            summary = prior_materialize(*args, **kwargs)
            output = Path(kwargs["output"]).resolve()
            summary.update(_extended_materialize(output))
            summary.update({
                "schema_version":
                    "day8_extended_token_replay_run_summary_v1",
                "main_run_id": MAIN_RUN_ID,
                "query_summary_scan_start": QUERY_SUMMARY_SCAN_START,
                "query_summary_scan_end": QUERY_SUMMARY_SCAN_END,
                "detailed_token_scan_start": DETAILED_TOKEN_SCAN_START,
                "detailed_token_scan_end": DETAILED_TOKEN_SCAN_END,
            })
            summary["complete"] = all((
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
                summary.get("coherent_snapshot_count") == 22,
                summary.get("incoherent_snapshot_count") == 0,
                summary.get("tap_drop_count") == 0,
                summary.get("writer_error_count") == 0,
                summary.get("ground_truth_topic_count") == 0,
                summary["scan157_token_coverage_pass"],
                summary["scan162_token_coverage_pass"],
                summary["shadow_state_accounting_pass"],
            ))
            (output / "run_summary.json").write_text(
                json.dumps(summary, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            return summary

        old.materialize = materialize

    base.configure_day8_transport = configure


def main() -> int:
    base = _load(
        ROOT / "scripts/108_run_day8_range_query_diagnostics.py",
        "day8_extended_base_runner",
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
    configure_extended_transport(base)
    return int(base.main())


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        print("ERROR: %s" % error, file=sys.stderr)
        raise SystemExit(1)
