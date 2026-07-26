#!/usr/bin/env python3
"""Run one authorized Day 8 Quick Shack range-query diagnostic replay."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter import experiment_a_map_snapshot_coherence as snapshots
from fastlio2_adapter import experiment_a_stage_hash as stage_hash
from fastlio2_adapter import focused_branch_stage_classifier as classifier
from fastlio2_adapter import day7_map_update_events as day7_events
from fastlio2_adapter.day7_map_point_identity import (
    load_snapshot_sets, validate_snapshot_binary,
)
from fastlio2_adapter.day7_rebuild_logger_analysis import load_logger_events
from fastlio2_adapter.day8_range_query import validate_run_query_trace


MAIN_RUN_ID = "multihyp_day8_ikdtree_range_search_context_v1"
SUB_RUN_IDS = tuple(
    f"multihyp_day8_range_query_r{index}" for index in range(1, 5)
)
DAY7_AUDIT_SHA256 = (
    "22f2229c4928bba7e340fc623afec1f50fbe13ae8a3519eb6789e329c446911e"
)
AMENDMENT_SHA256 = (
    "697d7e069d29f055450d12748f9307806b0af3c9ee425d8c002cf44902a70019"
)
SCAN_START = 155
SCAN_END = 165
DETAIL_START = 160
DETAIL_END = 163
EXPECTED_RECORD_COUNT = 11
EXPECTED_SNAPSHOT_COUNT = 22
DAY7_SCAN_START = 150
DAY7_SCAN_END = 170
# Day 7 mutation events retain their fixed 150--170 support window, while
# the shared coherent snapshot exporter intentionally remains on the Day 8
# 155--165 diagnostic window (11 scans x MAP_BEFORE/MAP_AFTER).
DAY7_EXPECTED_SNAPSHOT_COUNT = EXPECTED_SNAPSHOT_COUNT
DAY7_STATUS_SERVICE = "/harmful_bias/day7_map_update_status"
DAY8_STATUS_SERVICE = "/harmful_bias/day8_range_query_status"

DAY7_RUNTIME_FILES = (
    "day7_map_mutation_events_v1.bin",
    "day7_map_mutation_events_v1.bin.sha256",
    "day7_map_mutation_event_index.csv",
    "day7_map_mutation_event_summary.json",
    "day7_map_mutation_call_summaries.json",
    "day7_map_mutation_call_summaries.csv",
    "day7_rebuild_logger_events_v1.bin",
    "day7_rebuild_logger_events_v1.bin.sha256",
    "day7_rebuild_logger_event_index.csv",
    "day7_rebuild_commit_summaries.json",
    "day7_rebuild_commit_summaries.csv",
    "map_point_identity_snapshots_v1.bin",
    "map_point_identity_snapshots_v1.bin.sha256",
    "map_point_identity_snapshot_index.csv",
    "map_point_identity_snapshot_hashes.csv",
    "day7_diagnostic_immutability_summary.json",
)
DAY8_RUNTIME_FILES = (
    "day8_range_query_summaries_v1.bin",
    "day8_range_query_summaries_v1.bin.sha256",
    "day8_range_query_summary_index.csv",
    "day8_range_traversal_tokens_v1.bin",
    "day8_range_traversal_tokens_v1.bin.sha256",
    "day8_range_traversal_token_index.csv",
    "map_point_voxel_identity_snapshots_v2.bin",
    "map_point_voxel_identity_snapshots_v2.bin.sha256",
    "map_point_voxel_identity_snapshot_index.csv",
    "map_point_voxel_identity_snapshot_pairs.csv",
    "day8_query_trace_summary.json",
    "day8_query_overflow_summary.json",
    "day8_diagnostic_immutability_summary.json",
)


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
    source_audit: Path, amendment: Path,
) -> dict[str, Any]:
    source = source_audit.expanduser().resolve()
    amendment_path = amendment.expanduser().resolve()
    if not source.is_file() or _sha256(source) != DAY7_AUDIT_SHA256:
        raise RuntimeError("Day 7 source audit identity mismatch")
    if (
        not amendment_path.is_file()
        or _sha256(amendment_path) != AMENDMENT_SHA256
    ):
        raise RuntimeError("Day 8 amendment identity mismatch")
    value = json.loads(amendment_path.read_text(encoding="utf-8"))
    required = {
        "source_day7_audit_sha256": DAY7_AUDIT_SHA256,
        "source_day7_internal_hash_failure_count": 0,
        "day8_authorization_amendment_pass": True,
        "day8_authorized": True,
        "day8_scope":
            "IKDTREE_RANGE_SEARCH_AND_VOXEL_REPRESENTATIVE_CONTEXT_DIAGNOSTICS",
        "map_update_root_cause_localized": True,
        "localized_scan_index": 161,
        "localized_call_index": 1,
        "localized_batch_point_index": 200,
        "root_cause_classification":
            "VOXEL_REPRESENTATIVE_SELECTION_DIVERGED",
        "formal_ikdtree_bug_proven": False,
        "data_race_proven": False,
        "stage3_start_authorized": False,
        "stage4_start_authorized": False,
        "fast_lio2_integration_authorized": False,
        "patent2_authorized": False,
        "day9_authorized": False,
    }
    if any(value.get(key) != expected for key, expected in required.items()):
        raise RuntimeError("Day 8 authorization fields mismatch")
    return {
        "schema_version": "day8_authorization_identity_v1",
        "source_day7_audit_sha256": DAY7_AUDIT_SHA256,
        "day8_authorization_amendment_sha256": AMENDMENT_SHA256,
        "day8_authorized": True,
        "day8_scope": required["day8_scope"],
        "stage3_start_authorized": False,
        "stage4_start_authorized": False,
        "day9_authorized": False,
    }


def validate_run_lock(path: Path, run_id: str) -> dict[str, Any]:
    value = json.loads(path.resolve().read_text(encoding="utf-8"))
    expected = {
        "main_run_id": MAIN_RUN_ID,
        "sub_run_ids": list(SUB_RUN_IDS),
        "source_day7_audit_sha256": DAY7_AUDIT_SHA256,
        "day8_authorization_amendment_sha256": AMENDMENT_SHA256,
        "scan_start": SCAN_START, "scan_end": SCAN_END,
        "detailed_trace_scan_start": DETAIL_START,
        "detailed_trace_scan_end": DETAIL_END, "run_count": 4,
    }
    if any(value.get(key) != item for key, item in expected.items()):
        raise RuntimeError("Day 8 run-lock contract mismatch")
    ports = value.get("ros_master_ports", {})
    if ports.get(run_id) != 20511 + SUB_RUN_IDS.index(run_id):
        raise RuntimeError("Day 8 ROS master port mismatch")
    if value.get("fast_cpu_core") != 22 or value.get("rosbag_cpu_core") != 23:
        raise RuntimeError("Day 8 CPU affinity mismatch")
    if float(value.get("playback_rate", 0)) != 0.25:
        raise RuntimeError("Day 8 playback rate mismatch")
    return value


def _validate_day7_trace(run_dir: Path) -> dict[str, Any]:
    day7_events.EXPECTED_SCAN_START = DAY7_SCAN_START
    day7_events.EXPECTED_SCAN_END = DAY7_SCAN_END
    mutation = day7_events.validate_fixed_binary(
        run_dir / "day7_map_mutation_events_v1.bin",
        day7_events.MUTATION_MAGIC,
    )
    logger = day7_events.validate_fixed_binary(
        run_dir / "day7_rebuild_logger_events_v1.bin",
        day7_events.LOGGER_MAGIC,
    )
    events = day7_events.load_events(
        run_dir / "day7_map_mutation_event_index.csv"
    )
    logger_rows = load_logger_events(
        run_dir / "day7_rebuild_logger_event_index.csv"
    )
    snapshot_sets = load_snapshot_sets(
        run_dir / "map_point_identity_snapshot_hashes.csv"
    )
    snapshot_binary = validate_snapshot_binary(
        run_dir / "map_point_identity_snapshots_v1.bin",
        run_dir / "map_point_identity_snapshot_index.csv",
        run_dir / "map_point_identity_snapshot_hashes.csv",
    )
    status = json.loads(
        (run_dir / "day7_map_mutation_event_summary.json").read_text(
            encoding="utf-8"
        )
    )
    delta = day7_events.materialize_delta_accounting(run_dir)
    if (
        mutation["record_count"] != len(events)
        or logger["record_count"] != len(logger_rows)
        or len(snapshot_sets) != DAY7_EXPECTED_SNAPSHOT_COUNT
        or snapshot_binary["record_count"] != DAY7_EXPECTED_SNAPSHOT_COUNT
        or status.get("event_overflow_count") != 0
        or status.get("unclassified_event_count") != 0
        or status.get("scan_start") != DAY7_SCAN_START
        or status.get("scan_end") != DAY7_SCAN_END
    ):
        raise RuntimeError("Day 7 support trace gate failed")
    return {
        "event_count": len(events),
        "logger_event_count": len(logger_rows),
        "snapshot_count": len(snapshot_sets),
        "event_overflow_count": 0,
        "unclassified_event_count": 0,
        "map_delta_accounting_failure_count": delta["failure_count"],
    }


def configure_day8_transport(old: Any) -> None:
    prior_configure = old.configure_transport

    def configure_transport(
        base: Any, transport: Any, *, run_id: str, repeat_id: int,
    ) -> None:
        prior_configure(base, transport, run_id=run_id, repeat_id=repeat_id)
        # The frozen V5 transport embeds 20200 as a function constant instead
        # of reading the run lock.  Replace only that port-base constant so
        # the actual roscore/ROS_MASTER_URI, not merely the materialized
        # summary, obeys the Day 8 fixed 20511--20514 contract.
        execute_code = transport.execute.__code__
        replacements = sum(
            value == 20200 for value in execute_code.co_consts
        )
        if replacements != 1:
            raise RuntimeError(
                "frozen V5 ROS master port base anchor mismatch"
            )
        transport.execute.__code__ = execute_code.replace(
            co_consts=tuple(
                20500 if value == 20200 else value
                for value in execute_code.co_consts
            )
        )
        prior_run_command = transport.run_command

        def run_command(
            command: Sequence[str], *, environment: Mapping[str, str],
            output: Path | None = None, check: bool = True,
        ) -> Any:
            result = prior_run_command(
                command, environment=environment, output=output, check=check
            )
            values = list(command)
            if values[:3] == [
                "rosparam", "set",
                "/harmful_bias/end_of_stream_audit_enabled",
            ]:
                for key, value in (
                    ("/harmful_bias/day7_map_update_audit_enabled", "true"),
                    (
                        "/harmful_bias/day7_scan_start",
                        str(DAY7_SCAN_START),
                    ),
                    (
                        "/harmful_bias/day7_scan_end",
                        str(DAY7_SCAN_END),
                    ),
                    ("/harmful_bias/day8_range_query_audit_enabled", "true"),
                    ("/harmful_bias/day8_scan_start", str(SCAN_START)),
                    ("/harmful_bias/day8_scan_end", str(SCAN_END)),
                    (
                        "/harmful_bias/day8_detailed_trace_scan_start",
                        str(DETAIL_START),
                    ),
                    (
                        "/harmful_bias/day8_detailed_trace_scan_end",
                        str(DETAIL_END),
                    ),
                ):
                    prior_run_command(
                        ["rosparam", "set", key, value],
                        environment=environment,
                    )
            return result

        transport.run_command = run_command
        prior_shutdown = transport.graceful_shutdown

        def graceful_shutdown(
            roslaunch: Any, *, environment: Mapping[str, str],
            run_dir: Path,
        ) -> dict[str, Any]:
            for service, prefix in (
                (DAY7_STATUS_SERVICE, "day7_map_update"),
                (DAY8_STATUS_SERVICE, "day8_range_query"),
            ):
                poll = transport.bounded_trigger_call(
                    service, environment=environment, timeout_sec=15.0
                )
                transport.atomic_json(
                    run_dir / f"{prefix}_service_evidence.json",
                    dict(poll.evidence),
                )
                if (
                    poll.snapshot is None
                    or poll.evidence.get("service_success") is not True
                ):
                    raise transport.RunFailure(
                        "RUNTIME_PRODUCT_MISSING",
                        f"{prefix} status service failed",
                    )
                transport.atomic_json(
                    run_dir / f"{prefix}_status.json",
                    dict(poll.snapshot),
                )
            return prior_shutdown(
                roslaunch, environment=environment, run_dir=run_dir
            )

        transport.graceful_shutdown = graceful_shutdown

    old.configure_transport = configure_transport
    prior_materialize = old.materialize

    def materialize(*args: Any, **kwargs: Any) -> dict[str, Any]:
        summary = prior_materialize(*args, **kwargs)
        output = Path(kwargs["output"]).resolve()
        run_dir = Path(kwargs["run_dir"]).resolve()
        for name in (*DAY7_RUNTIME_FILES, *DAY8_RUNTIME_FILES):
            source = run_dir / name
            if not source.is_file():
                raise RuntimeError(f"Day 8 runtime product missing: {name}")
            shutil.copy2(source, output / name)
        for prefix in ("day7_map_update", "day8_range_query"):
            shutil.copy2(
                run_dir / f"{prefix}_status.json",
                output / f"{prefix}_pre_shutdown_status.json",
            )
        day7 = _validate_day7_trace(output)
        day8 = validate_run_query_trace(output)
        summary.update({
            "schema_version": "day8_range_query_replay_run_summary_v1",
            "day7_map_update_audit_enabled": True,
            "day7_support_scan_start": DAY7_SCAN_START,
            "day7_support_scan_end": DAY7_SCAN_END,
            "day7_support_snapshot_count": day7["snapshot_count"],
            "day8_range_query_audit_enabled": True,
            "day8_scan_start": SCAN_START,
            "day8_scan_end": SCAN_END,
            "day8_stage_record_count": EXPECTED_RECORD_COUNT,
            "day8_snapshot_count": EXPECTED_SNAPSHOT_COUNT,
            "map_mutation_event_count": day7["event_count"],
            "day7_event_overflow_count": day7["event_overflow_count"],
            "day7_unclassified_event_count":
                day7["unclassified_event_count"],
            "day7_map_delta_accounting_failure_count":
                day7["map_delta_accounting_failure_count"],
            "range_query_summary_count": day8["query_summary_count"],
            "detailed_traversal_token_count":
                day8["traversal_token_count"],
            "formal_result_member_count":
                day8["formal_result_member_count"],
            "point_voxel_snapshot_count":
                day8["point_voxel_snapshot_count"],
            "day8_query_schema_error_count":
                day8["query_schema_error_count"],
            "day8_query_trace_validation_pass": True,
            "instrumentation_timing_perturbation_present": True,
        })
        summary["complete"] = bool(summary["complete"]) and all((
            summary["stage_hash_record_count"] == EXPECTED_RECORD_COUNT,
            day7["snapshot_count"] == DAY7_EXPECTED_SNAPSHOT_COUNT,
            day7["event_overflow_count"] == 0,
            day7["unclassified_event_count"] == 0,
            day8["query_summary_count"] > 0,
            day8["traversal_token_count"] > 0,
            day8["point_voxel_snapshot_count"] == EXPECTED_SNAPSHOT_COUNT,
            not any(day8["overflow"].values()),
        ))
        (output / "run_summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return summary

    old.materialize = materialize


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sequence", required=True)
    parser.add_argument("--clip", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--run-lock", required=True, type=Path)
    parser.add_argument("--endpoint-contract", required=True, type=Path)
    parser.add_argument("--authorization-audit", required=True, type=Path)
    parser.add_argument("--authorization-amendment", required=True, type=Path)
    parser.add_argument("--enable-readonly-tap", action="store_true")
    parser.add_argument("--enable-compact-export", action="store_true")
    parser.add_argument("--enable-in-call-audit", action="store_true")
    parser.add_argument("--enable-experiment-a-stage-hash", action="store_true")
    parser.add_argument("--enable-coherent-map-snapshot", action="store_true")
    parser.add_argument("--enable-day7-map-update-audit", action="store_true")
    parser.add_argument("--enable-day8-range-query-audit", action="store_true")
    parser.add_argument("--disable-runtime-detector", action="store_true")
    parser.add_argument("--use-frozen-tail-adjudication", action="store_true")
    args = parser.parse_args()
    if args.run_id not in SUB_RUN_IDS:
        raise RuntimeError("unauthorized Day 8 run id")
    if not all((
        args.enable_readonly_tap, args.enable_compact_export,
        args.enable_in_call_audit, args.enable_experiment_a_stage_hash,
        args.enable_coherent_map_snapshot, args.enable_day7_map_update_audit,
        args.enable_day8_range_query_audit, args.disable_runtime_detector,
        args.use_frozen_tail_adjudication,
    )):
        raise RuntimeError("all Day 8 safety flags are required")
    validate_run_lock(args.run_lock, args.run_id)
    authorization = validate_authorization(
        args.authorization_audit, args.authorization_amendment
    )
    classifier.SCAN_START = SCAN_START
    classifier.SCAN_END = SCAN_END
    classifier.EXPECTED_RECORD_COUNT = EXPECTED_RECORD_COUNT
    classifier.EXPECTED_SNAPSHOTS_PER_RUN = EXPECTED_SNAPSHOT_COUNT
    stage_hash.SCAN_START = SCAN_START
    stage_hash.SCAN_END = SCAN_END
    stage_hash.EXPECTED_RECORD_COUNT = EXPECTED_RECORD_COUNT
    snapshots.SCAN_START = SCAN_START
    snapshots.SCAN_END = SCAN_END
    snapshots.EXPECTED_RECORD_COUNT = EXPECTED_RECORD_COUNT
    snapshots.EXPECTED_SNAPSHOTS_PER_RUN = EXPECTED_SNAPSHOT_COUNT
    snapshots.EXPECTED_TOTAL_SNAPSHOTS = 2 * EXPECTED_SNAPSHOT_COUNT
    day7_events.EXPECTED_SCAN_START = DAY7_SCAN_START
    day7_events.EXPECTED_SCAN_END = DAY7_SCAN_END

    focused = _load(
        ROOT / "scripts/97_run_focused_branch_stage_localization.py",
        "day8_focused_transport",
    )
    focused.MAIN_RUN_ID = MAIN_RUN_ID
    focused.SUB_RUN_IDS = SUB_RUN_IDS
    focused.AUTHORIZATION_SHA256 = DAY7_AUDIT_SHA256
    focused.SCAN_START = SCAN_START
    focused.SCAN_END = SCAN_END
    focused.EXPECTED_RECORD_COUNT = EXPECTED_RECORD_COUNT
    focused.EXPECTED_SNAPSHOTS_PER_RUN = EXPECTED_SNAPSHOT_COUNT
    focused.validate_authorization_archive = lambda _path: dict(authorization)
    prior_load = focused._load

    def patched_load(path: Path, name: str) -> Any:
        module = prior_load(path, name)
        if path.name == "85_run_experiment_a_stage_hash_pair.py":
            configure_day8_transport(module)
        return module

    focused._load = patched_load
    forwarded = [sys.argv[0]]
    for name, value in (
        ("--sequence", args.sequence), ("--clip", str(args.clip)),
        ("--run-id", args.run_id), ("--output-dir", str(args.output_dir)),
        ("--run-lock", str(args.run_lock)),
        ("--endpoint-contract", str(args.endpoint_contract)),
        ("--authorization-audit", str(args.authorization_audit)),
    ):
        forwarded.extend((name, value))
    forwarded.extend((
        "--enable-readonly-tap", "--enable-compact-export",
        "--enable-in-call-audit", "--enable-experiment-a-stage-hash",
        "--enable-coherent-map-snapshot", "--disable-runtime-detector",
        "--use-frozen-tail-adjudication",
    ))
    sys.argv = forwarded
    return int(focused.main())


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
