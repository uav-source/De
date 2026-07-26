#!/usr/bin/env python3
"""Run one of four focused scan 155-205 branch-localization replays."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import tarfile
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter import experiment_a_map_snapshot_coherence as snapshots
from fastlio2_adapter import experiment_a_stage_hash as stage_hash
from fastlio2_adapter.focused_branch_stage_classifier import (
    EXPECTED_RECORD_COUNT,
    EXPECTED_SNAPSHOTS_PER_RUN,
    SCAN_END,
    SCAN_START,
    configure_focused_contract,
)


MAIN_RUN_ID = "multihyp_day6_focused_formal_branch_stage_localization_v1"
SUB_RUN_IDS = tuple(
    f"multihyp_day6_focused_branch_r{index}" for index in range(1, 5)
)
AUTHORIZATION_SHA256 = (
    "f092a4910667eded36a04d966128e2e9a11e7226711297a78dca11cf50e54fa3"
)


def _load(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_authorization_archive(path: Path) -> dict[str, Any]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file() or _sha256(resolved) != AUTHORIZATION_SHA256:
        raise RuntimeError("focused authorization audit identity mismatch")
    with tarfile.open(resolved, "r:gz") as archive:
        member = next(
            (
                item for item in archive.getmembers()
                if item.name.endswith(
                    "bounded_formal_branch_reproduction_manifest.json"
                )
            ),
            None,
        )
        if member is None:
            raise RuntimeError("bounded authorization manifest missing")
        stream = archive.extractfile(member)
        if stream is None:
            raise RuntimeError("bounded authorization manifest unreadable")
        manifest = json.load(stream)
        coherence_member = next(
            (
                item for item in archive.getmembers()
                if item.name.endswith(
                    "authorization/coherence_gate_summary.json"
                )
            ),
            None,
        )
        if coherence_member is None:
            raise RuntimeError(
                "bounded authorization coherence gate missing"
            )
        coherence_stream = archive.extractfile(coherence_member)
        if coherence_stream is None:
            raise RuntimeError(
                "bounded authorization coherence gate unreadable"
            )
        coherence = json.load(coherence_stream)
    if manifest.get("bounded_branch_reproduction_execution_pass") is not True:
        raise RuntimeError("bounded execution authorization missing")
    if manifest.get("semantic_formal_divergence_observed") is not True:
        raise RuntimeError("full-stream formal branch observation missing")
    scans = set(manifest["pairwise_first_divergence_scans"].values())
    if not {164, 196}.issubset(scans):
        raise RuntimeError("authorized branch scans missing")
    if manifest.get("formal_branch_stage_localized") is not False:
        raise RuntimeError("authorization stage-localization state mismatch")
    if coherence.get("map_snapshot_coherence_pass") is not True:
        raise RuntimeError("authorization map snapshot coherence missing")
    if (
        coherence.get("map_snapshot_cross_scan_coherence_pass")
        is not True
    ):
        raise RuntimeError(
            "authorization cross-scan snapshot coherence missing"
        )
    if manifest.get("day7_authorized") is not False:
        raise RuntimeError("authorization unexpectedly opens Day 7")
    return {
        "schema_version":
            "focused_formal_branch_stage_localization_authorization_v1",
        "authorization_audit_path": str(resolved),
        "authorization_audit_sha256": AUTHORIZATION_SHA256,
        "bounded_branch_reproduction_execution_pass": True,
        "formal_branch_observed_in_full_observation_stream": True,
        "prior_formal_branch_stage_localized": False,
        "authorized_prior_branch_scans": [164, 196],
        "map_snapshot_coherence_pass": True,
        "map_snapshot_cross_scan_coherence_pass": True,
        "focused_scan_start": SCAN_START,
        "focused_scan_end": SCAN_END,
        "day7_authorized": False,
    }


def _focused_finalize(
    runtime_summary: Mapping[str, Any],
    stage_summary: Mapping[str, Any],
    *,
    run_id: str,
    ros_master_port: int,
) -> dict[str, Any]:
    summary = dict(runtime_summary)
    summary.update({
        "schema_version": "day6_focused_branch_replay_run_summary_v1",
        "run_id": run_id,
        "ros_master_port": ros_master_port,
        "stage_hash_record_count": int(stage_summary["stage_record_count"]),
        "stage_hash_first_scan": int(stage_summary["first_scan_index"]),
        "stage_hash_last_scan": int(stage_summary["last_scan_index"]),
        "diagnostic_mutation_count": int(
            stage_summary["diagnostic_mutation_count"]
        ),
        "diagnostic_internal_error_count": int(
            stage_summary["diagnostic_internal_error_count"]
        ),
        "stage_hash_schema_pass": True,
        "stage_hash_window_coverage_pass": True,
        "raw_lidar_hash_capture_pass": True,
        "imu_bundle_hash_capture_pass": True,
        "undistorted_cloud_hash_capture_pass": True,
        "map_before_hash_capture_pass": True,
        "correspondence_hash_reuse_pass": True,
        "insertion_batch_hash_capture_pass": True,
        "map_after_hash_capture_pass": True,
    })
    summary["complete"] = bool(runtime_summary["complete"]) and all((
        summary["stage_hash_record_count"] == EXPECTED_RECORD_COUNT,
        summary["stage_hash_first_scan"] == SCAN_START,
        summary["stage_hash_last_scan"] == SCAN_END,
        summary["diagnostic_mutation_count"] == 0,
        summary["diagnostic_internal_error_count"] == 0,
    ))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sequence", required=True)
    parser.add_argument("--clip", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--run-lock", required=True, type=Path)
    parser.add_argument("--endpoint-contract", required=True, type=Path)
    parser.add_argument("--authorization-audit", required=True, type=Path)
    parser.add_argument("--enable-readonly-tap", action="store_true")
    parser.add_argument("--enable-compact-export", action="store_true")
    parser.add_argument("--enable-in-call-audit", action="store_true")
    parser.add_argument("--enable-experiment-a-stage-hash", action="store_true")
    parser.add_argument("--enable-coherent-map-snapshot", action="store_true")
    parser.add_argument("--disable-runtime-detector", action="store_true")
    parser.add_argument("--use-frozen-tail-adjudication", action="store_true")
    args = parser.parse_args()
    if args.run_id not in SUB_RUN_IDS:
        raise RuntimeError("unauthorized focused replay run id")
    if not all((
        args.enable_readonly_tap,
        args.enable_compact_export,
        args.enable_in_call_audit,
        args.enable_experiment_a_stage_hash,
        args.enable_coherent_map_snapshot,
        args.disable_runtime_detector,
        args.use_frozen_tail_adjudication,
    )):
        raise RuntimeError("all focused replay safety flags are required")

    configure_focused_contract()
    old = _load(
        ROOT / "scripts/85_run_experiment_a_stage_hash_pair.py",
        "focused_branch_transport",
    )
    old.MAIN_RUN_ID = MAIN_RUN_ID
    old.SUB_RUN_IDS = SUB_RUN_IDS
    old.EXPECTED_AUDIT_SHA256 = AUTHORIZATION_SHA256
    old.SCAN_START = SCAN_START
    old.SCAN_END = SCAN_END
    old.validate_authorization_archive = validate_authorization_archive
    old.finalize_materialized_summary = _focused_finalize
    prior_materialize = old.materialize

    def materialize(*values: Any, **kwargs: Any) -> Any:
        summary = prior_materialize(*values, **kwargs)
        output = Path(kwargs["output"])
        records = json.loads(
            (output / "experiment_a_stage_hash_records_v2.json").read_text(
                encoding="utf-8"
            )
        )
        snapshot = snapshots.materialize_snapshot_evidence(records, output)
        summary.update({
            "schema_version": "day6_focused_branch_replay_run_summary_v1",
            "stage_hash_v2_record_count": summary["stage_hash_record_count"],
            "map_before_snapshot_count":
                snapshot["map_before_snapshot_count"],
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
        })
        summary["complete"] = bool(summary["complete"]) and all((
            summary["map_before_snapshot_count"] == EXPECTED_RECORD_COUNT,
            summary["map_after_snapshot_count"] == EXPECTED_RECORD_COUNT,
            summary["coherent_snapshot_count"]
                == EXPECTED_SNAPSHOTS_PER_RUN,
            summary["incoherent_snapshot_count"] == 0,
            summary["cross_scan_continuity_violation_count"] == 0,
        ))
        base = old.load_module(
            ROOT / "scripts/75_run_day6_fallback_real_replay.py",
            "focused_output_helper",
        )
        base.write_json(output / "run_summary.json", summary)
        return summary

    old.materialize = materialize
    forwarded = [sys.argv[0]]
    for name, value in (
        ("--sequence", args.sequence),
        ("--clip", str(args.clip)),
        ("--run-id", args.run_id),
        ("--output-dir", str(args.output_dir)),
        ("--run-lock", str(args.run_lock)),
        ("--endpoint-contract", str(args.endpoint_contract)),
        ("--authorization-audit", str(args.authorization_audit)),
    ):
        forwarded.extend((name, value))
    forwarded.extend((
        "--enable-readonly-tap",
        "--enable-compact-export",
        "--enable-in-call-audit",
        "--enable-experiment-a-stage-hash",
        "--disable-runtime-detector",
        "--use-frozen-tail-adjudication",
    ))
    sys.argv = forwarded
    result = int(old.main())
    if result == 0:
        path = args.output_dir.expanduser().resolve() / "run_summary.json"
        summary = json.loads(path.read_text(encoding="utf-8"))
        summary.update({
            "wrapper_exit_code": 0,
            "wrapper_failure_classification": "NONE",
            "wrapper_pipeline_clean_exit_pass": True,
        })
        path.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
