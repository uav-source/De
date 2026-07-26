#!/usr/bin/env python3
"""Validate and extract immutable inputs for the Day 6 branch audit."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.day6_branch_divergence import (  # noqa: E402
    EXPECTED_ADAPTER_SHA256,
    EXPECTED_DEGEN_BRANCH,
    EXPECTED_DEGEN_HEAD,
    EXPECTED_DIRECT_SHA256,
    EXPECTED_FAST_BRANCH,
    EXPECTED_FAST_HEAD,
    EXPECTED_OBSERVATION_SHA256,
    authorization_lineage,
    sha256_file,
    validate_archive_identity,
    verify_internal_sha256s,
    write_json,
)
from fastlio2_adapter.day6_semantic_observation import (  # noqa: E402
    load_observation_records,
    validate_record_index_file,
)


ANALYSIS_SOURCE_PATHS = (
    "src/fastlio2_adapter/day6_branch_divergence.py",
    "src/fastlio2_adapter/day6_semantic_observation.py",
    "src/fastlio2_adapter/day6_eigenspace_stability.py",
    "src/fastlio2_adapter/day6_divergence_hypotheses.py",
    "scripts/80_extract_day6_branch_inputs.py",
    "scripts/81_compare_day6_semantic_observations.py",
    "scripts/82_analyze_day6_eigenspace_stability.py",
    "scripts/83_finalize_day6_branch_root_cause.py",
    "scripts/84_render_day6_branch_root_cause_plots.py",
)
ANALYSIS_TEST_PATHS = (
    "tests/test_day6_semantic_observation.py",
    "tests/test_day6_first_divergence.py",
    "tests/test_day6_divergence_order.py",
    "tests/test_day6_evidence_granularity.py",
    "tests/test_day6_eigenspace_reconstruction.py",
    "tests/test_day6_sign_invariant_angles.py",
    "tests/test_day6_weak_subspace_angles.py",
    "tests/test_day6_hypothesis_matrix.py",
    "tests/test_day6_branch_root_cause_gate.py",
)
FAST_SOURCE_PATHS = (
    "src/laserMapping.cpp",
    "include/common_lib.h",
    "include/ikd-Tree/ikd_Tree.h",
    "include/ikd-Tree/ikd_Tree.cpp",
    "include/IKFoM_toolkit/esekfom/esekfom.hpp",
)
IMMUTABLE_REPO_PATHS = (
    "src/degen_detector/odi_tracker.py",
    "configs/detector/odi_stage2a.yaml",
    "artifacts/current/detector_stage2a/locked/detector_lock.json",
    "src/fastlio2_adapter/detector_adapter.py",
    "src/fastlio2_adapter/runtime_detector_adapter_v3.py",
    "src/fastlio2_adapter/canonical_detector_output.py",
    "src/fastlio2_adapter/runtime_observation_v3.py",
    "src/fastlio2_adapter/frozen_observation.py",
    "schemas/harmful_bias/readonly_observation_v3.schema.json",
    "schemas/harmful_bias/readonly_detector_output_v3.schema.json",
    "docs/harmful_bias/strict_replay_route_closure.md",
    "manifests/harmful_bias/day6_fallback_functional_diagnostics_manifest.json",
    "README.md",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day6-audit", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def git_output(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip())
    return completed.stdout.strip()


def safe_extract(archive: Path, destination: Path) -> Path:
    with tarfile.open(archive, "r:gz") as handle:
        members = handle.getmembers()
        roots = {
            Path(member.name).parts[0]
            for member in members
            if member.name and Path(member.name).parts
        }
        if len(roots) != 1:
            raise ValueError("archive root is ambiguous")
        resolved = destination.resolve()
        for member in members:
            if member.issym() or member.islnk():
                raise ValueError("archive link is forbidden")
            try:
                (destination / member.name).resolve().relative_to(resolved)
            except ValueError as error:
                raise ValueError("unsafe archive member") from error
        handle.extractall(destination)
    return destination / next(iter(roots))


def copy_file(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise ValueError(f"required input missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def copy_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise ValueError(f"required directory missing: {source}")
    shutil.copytree(source, destination, dirs_exist_ok=True)


def tree_sha256(root: Path) -> str:
    rows = []
    for path in sorted(value for value in root.rglob("*") if value.is_file()):
        rows.append(
            f"{sha256_file(path)}  {path.relative_to(root).as_posix()}\n"
        )
    import hashlib

    return hashlib.sha256("".join(rows).encode("utf-8")).hexdigest()


def validate_scientific_invariants(
    audit_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    run_values = []
    for index in (1, 2, 3):
        observation_root = (
            audit_root / f"real_replay_observations/run_{index}"
        )
        detector_root = audit_root / f"detector_outputs/run_{index}"
        binary = observation_root / "observation_records_v3.bin"
        adapter = detector_root / "adapter_detector_outputs_v3.jsonl"
        direct = detector_root / "direct_production_metrics_v1.jsonl"
        records, integrity = load_observation_records(binary)
        index_value = validate_record_index_file(
            observation_root / "observation_record_index.csv"
        )
        lifecycle = json.loads(
            (observation_root / "observation_lifecycle_summary.json").read_text(
                encoding="utf-8"
            )
        )
        summary = json.loads(
            (observation_root / "run_summary.json").read_text(encoding="utf-8")
        )
        values = {
            "run_index": index,
            "observation_sha256": sha256_file(binary),
            "observation_size_bytes": binary.stat().st_size,
            "record_count": len(records),
            "record_index": index_value,
            "lifecycle_consistency_pass": lifecycle[
                "lifecycle_consistency_pass"
            ],
            "lidar_callback_count": summary["lidar_callback_count"],
            "imu_callback_count": summary["imu_callback_count"],
            "tap_drop_count": summary["tap_drop_count"],
            "in_call_mutation_count": summary["in_call_mutation_count"],
            "schema_rejected_count": summary["schema_rejected_record_count"],
            "gt_topic_consumed_count": summary["GT_TOPIC_CONSUMED_COUNT"],
            "adapter_sha256": sha256_file(adapter),
            "direct_sha256": sha256_file(direct),
            "binary_integrity": integrity,
        }
        expected = {
            "observation_sha256": EXPECTED_OBSERVATION_SHA256[index - 1],
            "record_count": 487,
            "lifecycle_consistency_pass": True,
            "lidar_callback_count": 491,
            "imu_callback_count": 9953,
            "tap_drop_count": 0,
            "in_call_mutation_count": 0,
            "schema_rejected_count": 0,
            "gt_topic_consumed_count": 0,
            "adapter_sha256": EXPECTED_ADAPTER_SHA256[index - 1],
            "direct_sha256": EXPECTED_DIRECT_SHA256[index - 1],
        }
        mismatches = [
            key for key, expected_value in expected.items()
            if values[key] != expected_value
        ]
        if mismatches:
            raise ValueError(
                f"run {index} scientific identity mismatch: {mismatches}"
            )
        run_values.append(values)
    gate = json.loads(
        (
            audit_root
            / "evidence/small_results/"
            "day6_fallback_functional_diagnostics_gate_summary.json"
        ).read_text(encoding="utf-8")
    )
    required = {
        "DAY6_FALLBACK_FUNCTIONAL_DIAGNOSTICS_PASS": True,
        "NEXT_PHASE_AUTHORIZED": False,
        "CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE": "NOT_PROVEN",
        "STAGE3_START_AUTHORIZED": False,
        "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
    }
    if any(gate.get(key) != value for key, value in required.items()):
        raise ValueError("Day 6 gate invariants changed")
    return run_values, {key: gate[key] for key in required}


def main() -> int:
    args = parse_args()
    archive = args.day6_audit.expanduser().resolve()
    output = args.output_dir.resolve()
    if output.exists():
        raise SystemExit(f"ERROR: output already exists: {output}")
    archive_identity = validate_archive_identity(archive)
    output.mkdir(parents=True)
    with tempfile.TemporaryDirectory(
        prefix="day6_branch_input_extract_"
    ) as temporary:
        audit_root = safe_extract(archive, Path(temporary))
        internal = verify_internal_sha256s(audit_root)
        runs, fixed_gates = validate_scientific_invariants(audit_root)

        for index in (1, 2, 3):
            source_observation = (
                audit_root / f"real_replay_observations/run_{index}"
            )
            source_detector = audit_root / f"detector_outputs/run_{index}"
            destination = output / f"run_{index}"
            for name in (
                "observation_records_v3.bin",
                "observation_records_v3.bin.sha256",
                "observation_record_index.csv",
                "observation_lifecycle_summary.json",
                "run_summary.json",
            ):
                copy_file(source_observation / name, destination / name)
            for name in (
                "adapter_detector_outputs_v3.jsonl",
                "adapter_detector_outputs_v3.jsonl.sha256",
                "direct_production_metrics_v1.jsonl",
                "direct_production_metrics_v1.jsonl.sha256",
            ):
                copy_file(
                    source_detector / name,
                    destination / name,
                )
            evidence_source = audit_root / f"evidence/run_{index}"
            for relative in (
                "connection_handshake/summary.json",
                "tail_clock/raw_summary.json",
                "tail_clock/adjudication_summary.json",
                "drain/summary.json",
                "runtime_products/summary.json",
                "in_call_immutability/summary.json",
                "binary_validation/summary.json",
                "detector_processing/detector_processing_summary.json",
                "detector_processing/environment_identity.json",
                "detector_processing/source_identity.json",
            ):
                copy_file(
                    evidence_source / relative,
                    destination / "evidence" / relative,
                )

        for name in (
            "day6_fallback_functional_diagnostics_manifest.json",
            "day6_fallback_functional_diagnostics_gate_summary.json",
            "day6_fallback_functional_diagnostics_report.md",
            "audit_scope_summary.json",
        ):
            copy_file(
                audit_root / "evidence/small_results" / name,
                output / "day6_identity" / name,
            )
        copy_file(
            audit_root / "evidence/run_lock/day6_run_lock_redacted.json",
            output / "day6_identity/day6_run_lock_redacted.json",
        )

        copy_file(
            audit_root / "repo/degen_base.bundle",
            output / "reproduction_base/degen_base.bundle",
        )
        for name in ("degen_overlay", "home_state", "detector_snapshot"):
            copy_tree(
                audit_root / "repo" / name,
                output / "reproduction_base" / name,
            )

    fast_root = Path.home() / "fastlio2_ws/src/FAST_LIO"
    if git_output(fast_root, "branch", "--show-current") != EXPECTED_FAST_BRANCH:
        raise ValueError("FAST branch changed")
    if git_output(fast_root, "rev-parse", "HEAD") != EXPECTED_FAST_HEAD:
        raise ValueError("FAST HEAD changed")
    if git_output(ROOT, "branch", "--show-current") != EXPECTED_DEGEN_BRANCH:
        raise ValueError("Degen branch changed")
    if git_output(ROOT, "rev-parse", "HEAD") != EXPECTED_DEGEN_HEAD:
        raise ValueError("Degen HEAD changed")

    fast_hashes = {}
    for relative in FAST_SOURCE_PATHS:
        source = fast_root / relative
        copy_file(
            source,
            output / "source_reference/fastlio2" / relative,
        )
        fast_hashes[relative] = sha256_file(source)
    immutable_hashes = {}
    for relative in IMMUTABLE_REPO_PATHS:
        source = ROOT / relative
        immutable_hashes[relative] = sha256_file(source)
        copy_file(
            source,
            output / "source_reference/degen" / relative,
        )

    analysis_hashes = {
        relative: sha256_file(ROOT / relative)
        for relative in ANALYSIS_SOURCE_PATHS + ANALYSIS_TEST_PATHS
    }
    lineage = authorization_lineage()
    write_json(output / "day6_audit_authorization_lineage.json", lineage)
    identity = {
        "schema_version": "day6_final_delivery_identity_gate_v1",
        "archive_identity": archive_identity,
        "internal_hash": internal,
        "run_identity": runs,
        "fixed_day6_gates": fixed_gates,
        "DAY6_FINAL_DELIVERY_AUDIT_IDENTITY_PASS": True,
        "DAY6_ROOT_CAUSE_OFFLINE_ANALYSIS_AUTHORIZED": True,
    }
    write_json(output / "day6_final_delivery_identity_gate.json", identity)
    lock = {
        "schema_version": "day6_branch_root_cause_input_lock_v1",
        "day6_audit_authorization_lineage": lineage,
        "day6_final_delivery_audit_sha256": archive_identity[
            "archive_sha256"
        ],
        "day6_internal_checked_file_count": internal["checked_file_count"],
        "day6_internal_hash_failure_count": 0,
        "degen_branch": EXPECTED_DEGEN_BRANCH,
        "degen_head": EXPECTED_DEGEN_HEAD,
        "fastlio2_branch": EXPECTED_FAST_BRANCH,
        "fastlio2_head": EXPECTED_FAST_HEAD,
        "fastlio2_source_sha256": fast_hashes,
        "fastlio2_source_tree_sha256": tree_sha256(
            output / "source_reference/fastlio2"
        ),
        "immutable_repo_source_sha256": immutable_hashes,
        "analysis_source_sha256": analysis_hashes,
        "run_identity": runs,
        "fixed_day6_gates": fixed_gates,
        "input_root_alias": "$DAY6_BRANCH_INPUT_ROOT",
        "day6_audit_alias": "$HOME_AUDITED/"
        "Degen-LIO-multihyp-D6-fallback-functional-diagnostics-audit.tar.gz",
        "analysis_scripts_locked_after_creation": True,
        "input_locked_after_creation": True,
        "roscore_run": False,
        "roslaunch_run": False,
        "rosbag_run": False,
        "fastlio2_run": False,
        "detector_reexecuted": False,
    }
    write_json(output / "day6_branch_root_cause_input_lock.json", lock)
    print(json.dumps(identity, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
