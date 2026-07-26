#!/usr/bin/env python3
"""Run one authorized focused replay after the bounded 26-to-51 fix."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import tarfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MAIN_RUN_ID = "multihyp_day6_focused_branch_capacity_remediation_v1"
SUB_RUN_IDS = tuple(
    f"multihyp_day6_focused_capacity_r{index}" for index in range(1, 5)
)
SCIENTIFIC_AUTHORIZATION_SHA256 = (
    "f092a4910667eded36a04d966128e2e9a11e7226711297a78dca11cf50e54fa3"
)
FAILED_FOCUSED_AUDIT_SHA256 = (
    "af36883f0540958ebd9650e1cb68de8bfcc4ed4fb32854b0b03a83c98631e5af"
)
MAXIMUM_STAGE_RECORD_COUNT = 51
SCAN_START = 155
SCAN_END = 205


def _load(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _archive_json(path: Path, suffix: str) -> dict[str, Any]:
    with tarfile.open(path, "r:gz") as archive:
        members = [
            member for member in archive.getmembers()
            if member.name.endswith(suffix)
        ]
        if len(members) != 1:
            raise RuntimeError(f"archive member identity mismatch: {suffix}")
        stream = archive.extractfile(members[0])
        if stream is None:
            raise RuntimeError(f"archive member unreadable: {suffix}")
        value = json.load(stream)
    if not isinstance(value, dict):
        raise RuntimeError(f"archive member is not an object: {suffix}")
    return value


def validate_failed_focused_archive(path: Path) -> dict[str, Any]:
    resolved = path.expanduser().resolve()
    if (
        not resolved.is_file()
        or sha256_file(resolved) != FAILED_FOCUSED_AUDIT_SHA256
    ):
        raise RuntimeError("failed focused audit identity mismatch")
    capability = _archive_json(
        resolved, "evidence/source_locks/fast_window_capability_gate.json"
    )
    failure = _archive_json(
        resolved, "evidence/run_1/run_failure_diagnosis.json"
    )
    manifest = _archive_json(
        resolved,
        "evidence/small_results/"
        "focused_formal_branch_stage_localization_manifest.json",
    )
    if (
        capability.get("requested_scan_start"),
        capability.get("requested_scan_end"),
        capability.get("requested_record_count"),
        capability.get("frozen_configure_capacity_limit"),
    ) != (SCAN_START, SCAN_END, MAXIMUM_STAGE_RECORD_COUNT, 26):
        raise RuntimeError("failed focused capacity evidence mismatch")
    if capability.get("requested_window_supported_by_frozen_binary") is not False:
        raise RuntimeError("failed focused rejection evidence missing")
    if manifest.get("execution_status") != (
        "STOPPED_FAIL_CLOSED_AFTER_RUN_1_CONFIGURATION_REJECTION"
    ):
        raise RuntimeError("failed focused execution status mismatch")
    if (
        failure.get("lidar_callback_count"),
        failure.get("imu_callback_count"),
        failure.get("observation_record_count"),
        failure.get("stage_record_count"),
    ) != (0, 0, 0, 0):
        raise RuntimeError("failed focused run unexpectedly produced evidence")
    if (
        manifest.get("fifth_replay_started") is not False
        or capability.get("fast_source_modified") is not False
        or capability.get("fast_binary_changed") is not False
    ):
        raise RuntimeError("failed focused immutability evidence mismatch")
    return {
        "failed_focused_audit_sha256": FAILED_FOCUSED_AUDIT_SHA256,
        "previous_failure_classification":
            "REQUESTED_51_RECORD_WINDOW_EXCEEDS_FROZEN_RUNTIME_CAPACITY_26",
        "previous_sensor_replay_count": 0,
    }


def validate_capacity_authorization(path: Path) -> dict[str, Any]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise RuntimeError("capacity remediation authorization missing")
    value = json.loads(resolved.read_text(encoding="utf-8"))
    required = {
        "schema_version":
            "focused_stage_hash_capacity_remediation_authorization_v1",
        "scientific_authorization_audit_sha256":
            SCIENTIFIC_AUTHORIZATION_SHA256,
        "failed_focused_audit_sha256": FAILED_FOCUSED_AUDIT_SHA256,
        "failure_classification":
            "REQUESTED_51_RECORD_WINDOW_EXCEEDS_FROZEN_RUNTIME_CAPACITY_26",
        "authorized_change":
            "EXPAND_BOUNDED_DIAGNOSTIC_RECORD_CAPACITY_FROM_26_TO_51",
        "formal_algorithm_change_authorized": False,
        "hash_contract_change_authorized": False,
        "snapshot_change_authorized": False,
        "thread_configuration_change_authorized": False,
        "replay_count_authorized": 4,
        "day7_authorized": False,
    }
    if not isinstance(value, dict) or any(
        value.get(key) != expected for key, expected in required.items()
    ):
        raise RuntimeError("capacity remediation authorization mismatch")
    return {
        **required,
        "capacity_remediation_authorization_sha256":
            sha256_file(resolved),
    }


CAPACITY_GATE_FLAGS = (
    "failed_focused_audit_identity_pass",
    "capacity_remediation_authorization_pass",
    "only_allowed_fast_files_changed",
    "maximum_capacity_constant_pass",
    "legacy_26_window_accepted_pass",
    "focused_51_window_accepted_pass",
    "window_52_rejected_pass",
    "collector_bounded_capacity_pass",
    "default_disabled_behavior_pass",
    "fast_capacity_gtest_direct_pass",
    "fast_build_pass",
    "fast_test_pass",
    "degen_targeted_test_pass",
    "degen_full_test_pass",
    "formal_fast_math_unchanged_pass",
    "snapshot_source_unchanged_pass",
    "hash_contract_unchanged_pass",
    "focused_stage_hash_capacity_remediation_pass",
    "focused_stage_155_205_replay_authorized",
)


def validate_capacity_gate(path: Path) -> dict[str, Any]:
    value = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    if not isinstance(value, dict) or any(
        value.get(flag) is not True for flag in CAPACITY_GATE_FLAGS
    ):
        raise RuntimeError("capacity remediation Gate is not open")
    if value.get("maximum_stage_record_count") != MAXIMUM_STAGE_RECORD_COUNT:
        raise RuntimeError("capacity remediation Gate maximum mismatch")
    return value


def validate_run_lock(
    path: Path,
    *,
    run_id: str,
    capacity_authorization_sha256: str,
    capacity_gate_sha256: str,
) -> dict[str, Any]:
    value = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("capacity remediation run lock is not an object")
    checks = {
        "main_run_id": MAIN_RUN_ID,
        "sub_run_ids": list(SUB_RUN_IDS),
        "scientific_authorization_audit_sha256":
            SCIENTIFIC_AUTHORIZATION_SHA256,
        "failed_focused_audit_sha256": FAILED_FOCUSED_AUDIT_SHA256,
        "capacity_remediation_authorization_sha256":
            capacity_authorization_sha256,
        "capacity_remediation_gate_sha256": capacity_gate_sha256,
        "maximum_stage_record_count": MAXIMUM_STAGE_RECORD_COUNT,
        "requested_scan_start": SCAN_START,
        "requested_scan_end": SCAN_END,
        "requested_stage_record_count": MAXIMUM_STAGE_RECORD_COUNT,
        "ikdtree_source_sha256":
            "2a17d431b11de0607b4f7505624d3ce77e39eef29b054b0440f67c099ccc810b",
        "coherent_snapshot_source_sha256":
            "2a17d431b11de0607b4f7505624d3ce77e39eef29b054b0440f67c099ccc810b",
        "offline_analysis_code_changed_after_runtime_lock": False,
    }
    if any(value.get(key) != expected for key, expected in checks.items()):
        raise RuntimeError("capacity remediation run lock mismatch")
    ports = value.get("ros_master_ports")
    if (
        not isinstance(ports, dict)
        or ports.get(run_id) != 20311 + SUB_RUN_IDS.index(run_id)
    ):
        raise RuntimeError("capacity remediation ROS master port mismatch")
    fast_root = Path.home() / "fastlio2_ws/src/FAST_LIO"
    live_files = {
        "capacity_header_sha256":
            fast_root / "include/experiment_a_stage_hash_audit.hpp",
        "capacity_source_sha256":
            fast_root / "src/experiment_a_stage_hash_audit.cpp",
        "capacity_test_sha256":
            fast_root / "test/test_experiment_a_stage_hash_audit.cpp",
        "ikdtree_header_sha256":
            fast_root / "include/ikd-Tree/ikd_Tree.h",
        "ikdtree_cpp_sha256":
            fast_root / "include/ikd-Tree/ikd_Tree.cpp",
        "laser_mapping_hook_sha256": fast_root / "src/laserMapping.cpp",
        "new_fast_binary_sha256":
            Path.home() / "fastlio2_ws/devel/lib/fast_lio/fastlio_mapping",
    }
    for field, live_path in live_files.items():
        if value.get(field) != sha256_file(live_path):
            raise RuntimeError(f"runtime lock live identity mismatch: {field}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sequence", required=True)
    parser.add_argument("--clip", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--run-lock", required=True, type=Path)
    parser.add_argument("--endpoint-contract", required=True, type=Path)
    parser.add_argument(
        "--scientific-authorization-audit", required=True, type=Path
    )
    parser.add_argument("--failed-focused-audit", required=True, type=Path)
    parser.add_argument("--capacity-authorization", required=True, type=Path)
    parser.add_argument("--capacity-gate", required=True, type=Path)
    parser.add_argument("--enable-readonly-tap", action="store_true")
    parser.add_argument("--enable-compact-export", action="store_true")
    parser.add_argument("--enable-in-call-audit", action="store_true")
    parser.add_argument("--enable-experiment-a-stage-hash", action="store_true")
    parser.add_argument("--enable-coherent-map-snapshot", action="store_true")
    parser.add_argument("--disable-runtime-detector", action="store_true")
    parser.add_argument("--use-frozen-tail-adjudication", action="store_true")
    args = parser.parse_args()
    if args.run_id not in SUB_RUN_IDS:
        raise RuntimeError("unauthorized capacity remediation run id")
    if args.output_dir.expanduser().resolve().name != args.run_id:
        raise RuntimeError("capacity remediation output identity mismatch")

    failed = validate_failed_focused_archive(args.failed_focused_audit)
    authorization = validate_capacity_authorization(
        args.capacity_authorization
    )
    validate_capacity_gate(args.capacity_gate)
    validate_run_lock(
        args.run_lock,
        run_id=args.run_id,
        capacity_authorization_sha256=authorization[
            "capacity_remediation_authorization_sha256"
        ],
        capacity_gate_sha256=sha256_file(args.capacity_gate.resolve()),
    )

    focused = _load(
        ROOT / "scripts/97_run_focused_branch_stage_localization.py",
        "focused_capacity_remediation_transport",
    )
    focused.MAIN_RUN_ID = MAIN_RUN_ID
    focused.SUB_RUN_IDS = SUB_RUN_IDS
    focused.AUTHORIZATION_SHA256 = SCIENTIFIC_AUTHORIZATION_SHA256
    prior_validate = focused.validate_authorization_archive

    def validate_all(path: Path) -> dict[str, Any]:
        scientific = prior_validate(path)
        return {
            **scientific,
            **failed,
            **authorization,
            "focused_stage_hash_capacity_remediation_pass": True,
            "focused_stage_155_205_replay_authorized": True,
            "maximum_stage_record_count": MAXIMUM_STAGE_RECORD_COUNT,
        }

    focused.validate_authorization_archive = validate_all
    forwarded = [sys.argv[0]]
    for name, value in (
        ("--sequence", args.sequence),
        ("--clip", str(args.clip)),
        ("--run-id", args.run_id),
        ("--output-dir", str(args.output_dir)),
        ("--run-lock", str(args.run_lock)),
        ("--endpoint-contract", str(args.endpoint_contract)),
        (
            "--authorization-audit",
            str(args.scientific_authorization_audit),
        ),
    ):
        forwarded.extend((name, value))
    forwarded.extend((
        "--enable-readonly-tap",
        "--enable-compact-export",
        "--enable-in-call-audit",
        "--enable-experiment-a-stage-hash",
        "--enable-coherent-map-snapshot",
        "--disable-runtime-detector",
        "--use-frozen-tail-adjudication",
    ))
    sys.argv = forwarded
    return int(focused.main())


if __name__ == "__main__":
    raise SystemExit(main())
