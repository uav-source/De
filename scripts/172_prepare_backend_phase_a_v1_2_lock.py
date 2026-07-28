#!/usr/bin/env python3
"""Publish the prospectively frozen Phase A v1.2 Stage-0 protocol lock."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_perturbation.backend_phase_a_protocol import (
    canonical_json_sha256,
    file_sha256,
    load_backend_phase_a_protocol,
)
from zero_perturbation.backend_phase_a_v1_2 import (
    PROTOCOL_LOCK_SCHEMA,
    V1_2_DOCUMENT_RELATIVE,
    V1_2_DOCUMENT_SHA256,
    V1_2_INVALIDATION_RELATIVE,
    V1_2_LOCK_RELATIVE,
    V1_2_PROTOCOL_LOCK_TAG,
    V1_2_PROTOCOL_RELATIVE,
    V1_2_PROTOCOL_SHA256,
    implementation_hashes,
    load_v1_2_protocol,
    planned_rows,
    scientific_contract_diff,
)


BASELINE = "29fdae5f665d342f833e7094cb47306e432dcaed"
ARTIFACT = ROOT / V1_2_LOCK_RELATIVE
PCL_CLI = Path("build/pcl_point_to_plane_v3/pcl_point_to_plane_cli")


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targeted-pytest-summary", required=True)
    parser.add_argument("--full-pytest-summary", required=True)
    parser.add_argument("--pcl-ctest-summary", required=True)
    return parser.parse_args()


def _json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("cannot write empty planned manifest")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _tag_target(tag: str) -> str:
    return subprocess.run(
        ["git", "rev-parse", f"{tag}^{{}}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _unchanged(*paths: str) -> bool:
    return subprocess.run(
        ["git", "diff", "--quiet", BASELINE, "--", *paths], cwd=ROOT
    ).returncode == 0


def _write_sums() -> None:
    files = sorted(
        path
        for path in ARTIFACT.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    )
    (ARTIFACT / "SHA256SUMS").write_text(
        "".join(
            f"{file_sha256(path)}  {path.relative_to(ARTIFACT).as_posix()}\n"
            for path in files
        ),
        encoding="utf-8",
    )


def main() -> int:
    args = _args()
    if ARTIFACT.exists():
        raise FileExistsError(f"refusing to overwrite lock artifact: {ARTIFACT}")
    protocol = load_v1_2_protocol(ROOT)
    base = load_backend_phase_a_protocol(ROOT)
    diff = scientific_contract_diff(ROOT)
    implementation = implementation_hashes(ROOT)
    snapshots, trials = planned_rows(ROOT)
    invalidation = json.loads(
        (ROOT / V1_2_INVALIDATION_RELATIVE / "formal_attempt_inventory.json").read_text(
            encoding="utf-8"
        )
    )
    protected = {
        "open3d_modified": not _unchanged("src/zero_perturbation/open3d_backend.py"),
        "pcl_modified": not _unchanged(
            "src/zero_perturbation/pcl_backend.py",
            "tools/pcl_point_to_plane/pcl_point_to_plane_cli.cpp",
            "tools/pcl_point_to_plane/rotation_metric_v3.hpp",
        ),
        "scene_modified": not _unchanged("src/capture_range/day2_development_scene.py"),
        "seed_modified": not _unchanged("configs/zero_perturbation/seed_schedule_v1.json"),
        "native_modified": not _unchanged("src/zero_perturbation/native_backend.py"),
        "odi_modified": not _unchanged("src/degen_detector/odi_tracker.py", "configs/detector"),
        "fast_lio2_modified": not _unchanged("src/fastlio2_adapter", "manifests/harmful_bias"),
    }
    changed = subprocess.run(
        ["git", "diff", "--name-only", BASELINE, "--"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    protected["d50_restored"] = any("d50" in path.lower() for path in changed)
    seed_continuation = bool(
        invalidation.get("V1_1_FORMAL_BACKEND_EXECUTION_COUNT") == 0
        and invalidation.get("V1_1_FORMAL_SCIENTIFIC_RESULT_EXPOSURE_COUNT") == 0
    )
    zero_diff_names = (
        "scientific_parameter_difference_count",
        "scene_difference_count",
        "seed_difference_count",
        "repeat_difference_count",
        "condition_difference_count",
        "backend_parameter_difference_count",
        "metric_difference_count",
        "threshold_difference_count",
        "quantile_method_difference_count",
        "planned_snapshot_difference_count",
        "planned_trial_difference_count",
    )
    lock_pass = bool(
        all(diff[name] == 0 for name in zero_diff_names)
        and diff["provenance_implementation_difference_count"] > 0
        and diff["execution_staging_difference_count"] > 0
        and seed_continuation
        and len(snapshots) == 210
        and len(trials) == 420
        and not any(protected.values())
        and "passed" in args.targeted_pytest_summary
        and "passed" in args.full_pytest_summary
        and "100% tests passed" in args.pcl_ctest_summary
        and (ROOT / PCL_CLI).is_file()
    )
    if not lock_pass:
        raise RuntimeError("v1.2 protocol-lock prerequisites did not pass")
    ARTIFACT.mkdir(parents=True)
    _csv(ARTIFACT / "planned_snapshots.csv", snapshots)
    _csv(ARTIFACT / "planned_trials.csv", trials)
    _json(ARTIFACT / "phase_a_v1_1_to_v1_2_diff.json", diff)
    _json(
        ARTIFACT / "provenance_contract.json",
        {
            "schema_version": "backend_phase_a_v1_2_provenance_contract_v1",
            "canonical_target_contract": protocol["canonical_target_contract"],
            "source_parent_index_contract": protocol["source_parent_index_contract"],
            "source_generation_contract": protocol["source_generation_contract"],
            "V1_1_BYTEWISE_ROUNDTRIP_ASSERTION_INVALID": True,
        },
    )
    _json(
        ARTIFACT / "quantization_contract.json",
        {
            "schema_version": "backend_phase_a_v1_2_quantization_contract_v1",
            **protocol["quantization_closure_contract"],
        },
    )
    _json(
        ARTIFACT / "backend_parameter_contract.json",
        {
            "schema_version": "backend_phase_a_v1_2_backend_parameter_contract_v1",
            "open3d": base.data["open3d_parameter_contract"],
            "pcl": base.data["pcl_parameter_contract"],
            "backend_parameter_difference_count": 0,
        },
    )
    _json(
        ARTIFACT / "metric_contract.json",
        {
            "schema_version": "backend_phase_a_v1_2_metric_contract_v1",
            "transform_semantics": base.data["transform_semantics"],
            "rotation_quality": base.data["rotation_matrix_quality_gate"],
            "solver_failures": base.data["solver_failure_definitions"],
            "gates": base.data["phase_a_hard_gates"],
            "quantiles": base.data["quantile_contract"],
            "snapshot_diversity": base.data["snapshot_diversity_gate"],
            "metric_difference_count": 0,
            "threshold_difference_count": 0,
        },
    )
    _json(ARTIFACT / "implementation_hashes.json", implementation)
    seed_audit = {
        "schema_version": "backend_phase_a_v1_2_seed_continuation_audit_v1",
        "FORMAL_SEED_SET_CHANGED": False,
        "V1_1_FORMAL_SEED_ACCESS_STATUS": invalidation[
            "V1_1_FORMAL_SEED_ACCESS_STATUS"
        ],
        "V1_1_FORMAL_BACKEND_EXECUTION_COUNT": invalidation[
            "V1_1_FORMAL_BACKEND_EXECUTION_COUNT"
        ],
        "V1_1_FORMAL_SCIENTIFIC_RESULT_EXPOSURE_COUNT": invalidation[
            "V1_1_FORMAL_SCIENTIFIC_RESULT_EXPOSURE_COUNT"
        ],
        "OPEN3D_OR_PCL_POSE_ERROR_OBSERVED": False,
        "CORRECTION_BASIS": "general_floating_point_quantization_non_commutativity",
        "CORRECTION_DEPENDS_ON_SCENE_RESULT": False,
        "SCENE_SEED_METRIC_OR_GATE_CHANGED": False,
        "SEED_CONTINUATION_AFTER_PRE_BACKEND_ABORT_JUSTIFIED": seed_continuation,
        "CONFIRMATORY_SEED_ACCESS_COUNT": 0,
        "OLD_CAPTURE_TEST_SEED_ACCESS_COUNT": 0,
    }
    _json(ARTIFACT / "seed_continuation_audit.json", seed_audit)
    pcl_binary = {
        "path": PCL_CLI.as_posix(),
        "sha256": file_sha256(ROOT / PCL_CLI),
    }
    lock_payload = {
        "schema_version": PROTOCOL_LOCK_SCHEMA,
        "protocol_path": V1_2_PROTOCOL_RELATIVE.as_posix(),
        "protocol_sha256": V1_2_PROTOCOL_SHA256,
        "protocol_document_path": V1_2_DOCUMENT_RELATIVE.as_posix(),
        "protocol_document_sha256": V1_2_DOCUMENT_SHA256,
        "scientific_base_protocol_sha256": base.source_sha256,
        "protocol_lock_tag": V1_2_PROTOCOL_LOCK_TAG,
        "protocol_lock_commit": _tag_target(V1_2_PROTOCOL_LOCK_TAG),
        "planned_snapshots_path": (V1_2_LOCK_RELATIVE / "planned_snapshots.csv").as_posix(),
        "planned_snapshots_sha256": file_sha256(ARTIFACT / "planned_snapshots.csv"),
        "planned_trials_path": (V1_2_LOCK_RELATIVE / "planned_trials.csv").as_posix(),
        "planned_trials_sha256": file_sha256(ARTIFACT / "planned_trials.csv"),
        "planned_snapshot_count": 210,
        "planned_trial_count": 420,
        "implementation": implementation,
        "implementation_sha256": implementation["implementation_sha256"],
        "pcl_cli_binary": pcl_binary,
        "SEED_CONTINUATION_AFTER_PRE_BACKEND_ABORT_JUSTIFIED": seed_continuation,
        "PHASE_A_V1_2_PROTOCOL_LOCK_PASS": lock_pass,
        "stage0_snapshot_build_authorized": lock_pass,
        "stage1_backend_run_authorized": False,
    }
    _json(
        ARTIFACT / "backend_phase_a_v1_2_protocol_lock.json",
        {**lock_payload, "lock_payload_sha256": canonical_json_sha256(lock_payload)},
    )
    _json(
        ARTIFACT / "run_manifest.json",
        {
            "schema_version": "backend_phase_a_v1_2_lock_run_manifest_v1",
            "baseline_commit": BASELINE,
            "protocol_lock_commit": lock_payload["protocol_lock_commit"],
            "protocol_sha256": V1_2_PROTOCOL_SHA256,
            "implementation_sha256": implementation["implementation_sha256"],
            "targeted_pytest_summary": args.targeted_pytest_summary,
            "full_pytest_summary": args.full_pytest_summary,
            "pcl_v3_ctest_summary": args.pcl_ctest_summary,
            "FORMAL_STAGE0_SNAPSHOT_BUILD_COUNT": 0,
            "FORMAL_BACKEND_EXECUTION_COUNT": 0,
            "FORMAL_TRIAL_RESULT_COUNT": 0,
            "git_push_performed": False,
            **protected,
        },
    )
    _json(
        ARTIFACT / "final_decision.json",
        {
            "schema_version": "backend_phase_a_v1_2_lock_decision_v1",
            "PHASE_A_V1_2_PROTOCOL_LOCK_PASS": lock_pass,
            "SEED_CONTINUATION_AFTER_PRE_BACKEND_ABORT_JUSTIFIED": seed_continuation,
            "STAGE0_SNAPSHOT_BUILD_AUTHORIZED": lock_pass,
            "PHASE_A_STAGE1_BACKEND_RUN_AUTHORIZED": False,
            "PHASE_A_STAGE1_BACKEND_EXECUTED": False,
            "BACKEND_PHASE_A_COMPLETE": False,
            "TWO_INDEPENDENT_BACKENDS_QUALIFIED": False,
            "DAY1_SCIENTIFIC_VALIDATION_PASS": "NOT_EVALUATED",
            "PHASE_B_AUTHORIZED": False,
            "FULL_DEVELOPMENT_AUTHORIZED": False,
            "CONFIRMATORY_AUTHORIZED": False,
            "REAL_DATA_AUTHORIZED": False,
            "MEASUREMENT_PAPER_MAINLINE_AUTHORIZED": False,
        },
    )
    _write_sums()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
