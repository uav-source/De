#!/usr/bin/env python3
"""Run one of exactly three authorized post-remediation Day 8 replays."""

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
from fastlio2_adapter.day8_focused_traversal_remediation import (
    DETAILED_TOKEN_SCAN_END,
    DETAILED_TOKEN_SCAN_START,
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


MAIN_RUN_ID = (
    "multihyp_day8_focused_traversal_materializer_remediation_v1"
)
RUN_IDS = (
    "multihyp_day8_focused_materializer_r2",
    "multihyp_day8_focused_materializer_r3",
    "multihyp_day8_focused_materializer_r4",
)
SOURCE_DAY8_SHA256 = (
    "d434af826eed0cc1a80d91e72f420cfcd4456768187c46cda9671629e30ff209"
)
AUTH_SCHEMA = "day8_overflow_materializer_remediation_authorization_v1"


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
    source_archive: Path, authorization: Path,
) -> dict[str, Any]:
    if _sha256(source_archive.resolve()) != SOURCE_DAY8_SHA256:
        raise RuntimeError("source Day 8 archive identity mismatch")
    value = json.loads(authorization.resolve().read_text(encoding="utf-8"))
    required = {
        "schema_version": AUTH_SCHEMA,
        "source_audit_sha256": SOURCE_DAY8_SHA256,
        "source_failure_classification":
            "OVERFLOW_SUMMARY_SCHEMA_METADATA_PARSED_AS_INTEGER",
        "source_run1_runtime_capture_pass": True,
        "source_run1_scan157_token_coverage_pass": True,
        "source_run1_shadow_accounting_pass": True,
        "source_run1_reuse_authorized": True,
        "source_run1_replay_authorized": False,
        "additional_real_replay_count_authorized": 3,
        "materializer_fix_authorized": True,
        "fast_source_change_authorized": False,
        "fast_build_authorized": False,
        "analysis_hotfix_after_runtime_lock_authorized": False,
        "day9_authorized": False,
        "stage3_start_authorized": False,
        "stage4_start_authorized": False,
        "fast_lio2_integration_authorized": False,
    }
    if any(value.get(key) != expected for key, expected in required.items()):
        raise RuntimeError("focused remediation authorization mismatch")
    return {
        "day8_authorized": True,
        "day8_scope":
            "OVERFLOW_MATERIALIZER_REMEDIATION_AND_R2_R4_ONLY",
        "source_day8_audit_sha256": SOURCE_DAY8_SHA256,
        "remediation_authorization_sha256": _sha256(authorization.resolve()),
        "day9_authorized": False,
    }


def validate_run_lock(path: Path, run_id: str) -> dict[str, Any]:
    value = json.loads(path.resolve().read_text(encoding="utf-8"))
    expected = {
        "main_run_id": MAIN_RUN_ID,
        "sub_run_ids": list(RUN_IDS),
        "source_day8_audit_sha256": SOURCE_DAY8_SHA256,
        "query_summary_window": [155, 165],
        "detailed_token_window": [156, 158],
        "run_count": 3,
        "fast_cpu_core": 22,
        "rosbag_cpu_core": 23,
        "playback_rate": 0.25,
    }
    if any(value.get(key) != expected for key, expected in expected.items()):
        raise RuntimeError("focused run-lock contract mismatch")
    if value["ros_master_ports"].get(run_id) != 20712 + RUN_IDS.index(run_id):
        raise RuntimeError("focused ROS master port mismatch")
    return value


def _focused_materialize(run_dir: Path, output: Path) -> dict[str, Any]:
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
    overflow_validation = parse_overflow_summary(overflow)
    rows, coverage = token_capture_coverage(
        queries, grouped,
        capture_failure_count=0,
        overflow_count=overflow_validation["overflow_count"],
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
    )
    write_comparison(
        output / "day8_shadow_voxel_query_comparison.csv", shadow
    )
    accounting = {
        "schema_version": "day8_shadow_accounting_summary_v1",
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
    if (
        not coverage["scan157_token_coverage_pass"]
        or coverage["token_capture_failure_count"] != 0
        or not accounting["shadow_state_accounting_pass"]
    ):
        raise RuntimeError("focused per-run token/shadow gate failed")
    return {
        "scan157_query_count": coverage["scan157_query_count"],
        "scan157_detailed_token_query_count":
            coverage["scan157_query_with_detailed_token_count"],
        "scan157_token_coverage_pass": True,
        "token_capture_failure_count": 0,
        "unclassified_token_count": 0,
        "shadow_accounting_failure_count": 0,
        "shadow_state_accounting_pass": True,
    }


def configure_focused_transport(base: Any) -> None:
    original = base.configure_day8_transport

    def configure(old: Any) -> None:
        original(old)
        prior_configure = old.configure_transport

        def configure_transport(
            transport_base: Any, transport: Any, *,
            run_id: str, repeat_id: int,
        ) -> None:
            prior_configure(
                transport_base, transport,
                run_id=run_id, repeat_id=repeat_id,
            )
            code = transport.execute.__code__
            if sum(value == 20500 for value in code.co_consts) != 1:
                raise RuntimeError("focused ROS port anchor mismatch")
            transport.execute.__code__ = code.replace(
                co_consts=tuple(
                    20701 if value == 20500 else value
                    for value in code.co_consts
                )
            )

        old.configure_transport = configure_transport
        prior_materialize = old.materialize

        def materialize(*args: Any, **kwargs: Any) -> dict[str, Any]:
            summary = prior_materialize(*args, **kwargs)
            output = Path(kwargs["output"]).resolve()
            run_dir = Path(kwargs["run_dir"]).resolve()
            summary.update(_focused_materialize(run_dir, output))
            summary.update({
                "schema_version":
                    "day8_focused_traversal_replay_run_summary_v1",
                "main_run_id": MAIN_RUN_ID,
                "detailed_token_scan_start": DETAILED_TOKEN_SCAN_START,
                "detailed_token_scan_end": DETAILED_TOKEN_SCAN_END,
            })
            summary["complete"] = bool(summary["complete"]) and all((
                summary.get("lidar_callback_count") == 491,
                summary.get("imu_callback_count") == 9953,
                summary.get("runtime_scan_count") == 490,
                summary.get("observation_record_count") == 487,
                summary.get("stage_hash_record_count") == 11,
                summary.get("tap_drop_count") == 0,
                summary.get("writer_error_count") == 0,
                summary.get("ground_truth_topic_count") == 0,
                summary["scan157_token_coverage_pass"],
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
        "day8_focused_base_runner",
    )
    base.MAIN_RUN_ID = MAIN_RUN_ID
    base.SUB_RUN_IDS = RUN_IDS
    base.DAY7_AUDIT_SHA256 = SOURCE_DAY8_SHA256
    base.DETAIL_START = DETAILED_TOKEN_SCAN_START
    base.DETAIL_END = DETAILED_TOKEN_SCAN_END
    base.validate_authorization = validate_authorization
    base.validate_run_lock = validate_run_lock
    range_query.DETAIL_START = DETAILED_TOKEN_SCAN_START
    range_query.DETAIL_END = DETAILED_TOKEN_SCAN_END
    configure_focused_transport(base)
    return int(base.main())


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
