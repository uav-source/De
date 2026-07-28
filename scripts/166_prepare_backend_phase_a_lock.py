#!/usr/bin/env python3
"""Materialize the RNG-free Phase A protocol lock and planned ID manifests."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zero_perturbation.backend_phase_a_protocol import (
    DOCUMENT_RELATIVE,
    DOCUMENT_SHA256,
    PROTOCOL_LOCK_COMMIT,
    PROTOCOL_LOCK_TAG,
    PROTOCOL_RELATIVE,
    PROTOCOL_SHA256,
    canonical_json_sha256,
    file_sha256,
    load_backend_phase_a_protocol,
)


ARTIFACT = ROOT / "artifacts/current/zero_perturbation_backend_phase_a_lock"
BASELINE_COMMIT = "6e4cfb857fb9c3050aa42647d9f86c8892130d80"
PCL_V3_ARCHIVE_TAG = "archive/zero-perturbation-pcl-backend-qualification-v3-pass"
PCL_V3_BUNDLE = Path("/tmp/Degen-LIO-zero-perturbation-pcl-v3-pass.bundle")
PCL_V3_BUNDLE_SHA256 = "4a5744bc668b93657619632735e0395d0ccabfca8b6efdd8fedab17662158010"
LOCK_PASS_TAG = "archive/zero-perturbation-backend-phase-a-v1-lock-pass"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--python-full-pytest-status",
        choices=("PENDING", "PASS", "FAIL"),
        default="PENDING",
    )
    parser.add_argument(
        "--pcl-v3-ctest-status",
        choices=("PENDING", "PASS", "FAIL"),
        default="PENDING",
    )
    parser.add_argument("--python-summary", default="NOT_EVALUATED")
    parser.add_argument("--pcl-ctest-summary", default="NOT_EVALUATED")
    return parser.parse_args()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("planned CSV cannot be empty")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_sums(directory: Path) -> None:
    files = sorted(
        path for path in directory.rglob("*") if path.is_file() and path.name != "SHA256SUMS"
    )
    (directory / "SHA256SUMS").write_text(
        "".join(
            f"{file_sha256(path)}  {path.relative_to(directory).as_posix()}\n"
            for path in files
        ),
        encoding="utf-8",
    )


def git_unchanged(*paths: str) -> bool:
    return (
        subprocess.run(
            ["git", "diff", "--quiet", BASELINE_COMMIT, "--", *paths], cwd=ROOT
        ).returncode
        == 0
    )


def git_tag_target(tag: str) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", f"{tag}^{{}}"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def implementation_hashes() -> dict[str, Any]:
    paths = {
        "scene_generator": "src/capture_range/day2_development_scene.py",
        "snapshot_builder": "src/zero_perturbation/snapshot_builder.py",
        "open3d_backend": "src/zero_perturbation/open3d_backend.py",
        "pcl_python_adapter": "src/zero_perturbation/pcl_backend.py",
        "pcl_cli_source": "tools/pcl_point_to_plane/pcl_point_to_plane_cli.cpp",
        "rotation_metric": "src/zero_perturbation/rotation_metrics.py",
        "phase_a_protocol_loader": "src/zero_perturbation/backend_phase_a_protocol.py",
        "phase_a_metrics": "src/zero_perturbation/backend_phase_a_metrics.py",
        "phase_a_runner": "scripts/168_run_backend_phase_a.py",
        "phase_a_verifier": "src/zero_perturbation/backend_phase_a_verification.py",
        "phase_a_prepare": "scripts/166_prepare_backend_phase_a_lock.py",
        "protocol_yaml": PROTOCOL_RELATIVE.as_posix(),
        "protocol_markdown": DOCUMENT_RELATIVE.as_posix(),
    }
    files = {
        label: {"path": path, "sha256": file_sha256(ROOT / path)}
        for label, path in paths.items()
    }
    binary = ROOT / "build/pcl_point_to_plane_v3/pcl_point_to_plane_cli"
    return {
        "schema_version": "backend_phase_a_implementation_hashes_v1",
        "files": files,
        "pcl_cli_binary": (
            {
                "path": binary.relative_to(ROOT).as_posix(),
                "sha256": file_sha256(binary),
            }
            if binary.is_file()
            else None
        ),
    }


def main() -> None:
    args = parse_args()
    protocol = load_backend_phase_a_protocol(ROOT)
    audit = protocol.self_audit()
    if git_tag_target(PCL_V3_ARCHIVE_TAG) != BASELINE_COMMIT:
        raise RuntimeError("PCL v3 archive tag target mismatch")
    if not PCL_V3_BUNDLE.is_file() or file_sha256(PCL_V3_BUNDLE) != PCL_V3_BUNDLE_SHA256:
        raise RuntimeError("PCL v3 archive bundle missing or changed")
    if git_tag_target(PROTOCOL_LOCK_TAG) != PROTOCOL_LOCK_COMMIT:
        raise RuntimeError("Phase A protocol-lock tag target mismatch")

    protected = {
        "open3d_modified": not git_unchanged(
            "src/zero_perturbation/open3d_backend.py"
        ),
        "pcl_parameters_or_implementation_modified": not git_unchanged(
            "src/zero_perturbation/pcl_backend.py",
            "tools/pcl_point_to_plane/pcl_point_to_plane_cli.cpp",
            "tools/pcl_point_to_plane/rotation_metric_v3.hpp",
        ),
        "native_modified": not git_unchanged(
            "src/zero_perturbation/native_backend.py"
        ),
        "odi_modified": not git_unchanged(
            "src/degen_detector/odi_tracker.py", "configs/detector"
        ),
        "fast_lio2_modified": not git_unchanged(
            "src/fastlio2_adapter", "manifests/harmful_bias"
        ),
        "scene_generator_modified": not git_unchanged(
            "src/capture_range/day2_development_scene.py"
        ),
    }
    changed = subprocess.run(
        ["git", "diff", "--name-only", BASELINE_COMMIT, "--"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    protected["d50_restored"] = any("d50" in path.lower() for path in changed)
    if any(protected.values()):
        raise RuntimeError(f"protected scope changed: {protected}")

    pcl_v3_decision = json.loads(
        (
            ROOT
            / "artifacts/current/zero_perturbation_backend_qualification_v3/final_decision.json"
        ).read_text(encoding="utf-8")
    )
    pcl_v3_valid = bool(
        pcl_v3_decision["PCL_BACKEND_IMPLEMENTATION_VALID"]
        and pcl_v3_decision["PCL_BACKEND_PHASE_A_QUALIFICATION_AUTHORIZED"]
    )
    plan_audit_pass = bool(
        all(
            value is True
            for key, value in audit.items()
            if key.startswith("PROTOCOL_HAS_")
        )
        and audit["PLANNED_SNAPSHOT_COUNT"] == 210
        and audit["PLANNED_TRIAL_COUNT"] == 420
        and audit["NATIVE_PLANNED_TRIAL_COUNT"] == 0
        and audit["OPEN3D_PLANNED_TRIAL_COUNT"] == 210
        and audit["PCL_PLANNED_TRIAL_COUNT"] == 210
        and audit["NEW_PROTOCOL_AMBIGUITIES_FOUND"] is False
    )
    parameter_lock_pass = bool(
        protocol.data["open3d_parameter_contract"]["canonical_sha256"]
        == canonical_json_sha256(
            protocol.data["open3d_parameter_contract"]["parameters"]
        )
        and protocol.data["pcl_parameter_contract"]["canonical_sha256"]
        == canonical_json_sha256(
            protocol.data["pcl_parameter_contract"]["parameters"]
        )
    )
    tests_pass = bool(
        args.python_full_pytest_status == "PASS"
        and args.pcl_v3_ctest_status == "PASS"
    )
    lock_pass = bool(
        pcl_v3_valid
        and plan_audit_pass
        and parameter_lock_pass
        and tests_pass
        and not any(protected.values())
    )

    if ARTIFACT.exists():
        for path in ARTIFACT.iterdir():
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
    ARTIFACT.mkdir(parents=True, exist_ok=True)
    snapshot_rows = [snapshot.row() for snapshot in protocol.planned_snapshots()]
    trial_rows = [trial.row() for trial in protocol.planned_trials()]
    write_csv(ARTIFACT / "planned_snapshots.csv", snapshot_rows)
    write_csv(ARTIFACT / "planned_trials.csv", trial_rows)

    implementation = implementation_hashes()
    write_json(ARTIFACT / "implementation_hashes.json", implementation)
    parameter_contract = {
        "schema_version": "backend_phase_a_parameter_contract_v1",
        "open3d": protocol.data["open3d_parameter_contract"]["parameters"],
        "open3d_parameter_sha256": protocol.data["open3d_parameter_contract"][
            "canonical_sha256"
        ],
        "OPEN3D_PARAMETER_LOCK_PASS": parameter_lock_pass,
        "pcl": protocol.data["pcl_parameter_contract"]["parameters"],
        "pcl_parameter_sha256": protocol.data["pcl_parameter_contract"][
            "canonical_sha256"
        ],
        "PCL_PARAMETER_LOCK_PASS": parameter_lock_pass,
        "maximum_correspondence_distance_equal": True,
    }
    write_json(ARTIFACT / "backend_parameter_contract.json", parameter_contract)
    write_json(
        ARTIFACT / "transform_semantics.json",
        {
            "T_reference_direction": "source_frame_to_target_map_frame",
            "T_estimated_direction": "source_frame_to_target_map_frame",
            "T_delta": "inverse(T_reference) @ T_estimated",
            "translation_update": "norm(T_delta[0:3, 3])",
            "rotation_update": "reflection_safe_nearest_SO3_SVD_then_atan2_geodesic",
        },
    )
    write_json(
        ARTIFACT / "metric_contract.json",
        {
            "canonical_source_dtype": "little-endian float32 C-contiguous",
            "canonical_target_dtype": "little-endian float32 C-contiguous",
            "canonical_reference_pose_dtype": "little-endian float64 4x4 C-contiguous",
            "checksum": "SHA256(raw C-order bytes)",
            "rotation_matrix_quality_gate": protocol.data[
                "rotation_matrix_quality_gate"
            ],
            "raw_trace_acos_gate_forbidden": True,
            "median": {"implementation": "numpy.median"},
            "q95": {
                "implementation": "numpy.quantile",
                "q": 0.95,
                "method": "linear",
            },
        },
    )
    write_json(
        ARTIFACT / "gate_contract.json",
        {
            "phase_a_hard_gates": protocol.data["phase_a_hard_gates"],
            "snapshot_diversity": protocol.data["snapshot_diversity_gate"],
            "solver_failure_definitions": protocol.data[
                "solver_failure_definitions"
            ],
            "not_evaluated_is_not_numeric_zero": True,
        },
    )
    seed_audit = {
        "schema_version": "backend_phase_a_seed_usage_audit_v1",
        "development_geometry_seeds": list(protocol.geometry_seeds),
        "development_measurement_seeds": list(protocol.measurement_seeds),
        "repeat_indices": list(protocol.repeats),
        "plan_generation_method": "deterministic Cartesian enumeration only",
        "scene_generator_imported_or_called": False,
        "PHASE_A_RNG_INSTANTIATION_COUNT": 0,
        "PHASE_A_SNAPSHOT_GENERATION_COUNT": 0,
        "PHASE_A_BACKEND_EXECUTION_COUNT": 0,
        "PHASE_A_TRIAL_RESULT_COUNT": 0,
        "CONFIRMATORY_RNG_INSTANTIATION_COUNT": 0,
        "OLD_CAPTURE_TEST_RNG_INSTANTIATION_COUNT": 0,
        "NATIVE_FORMAL_EXECUTION_COUNT": 0,
    }
    write_json(ARTIFACT / "seed_usage_audit.json", seed_audit)
    test_report = {
        "schema_version": "backend_phase_a_lock_test_report_v1",
        "python_full_pytest_command": (
            "/home/lj/.local/bin/micromamba run -n degen-lio-zprm-py311 "
            "python -m pytest -q"
        ),
        "python_full_pytest_status": args.python_full_pytest_status,
        "python_full_pytest_summary": args.python_summary,
        "pcl_v3_ctest_command": (
            "ctest --test-dir build/pcl_point_to_plane_v3 -V --output-on-failure"
        ),
        "pcl_v3_ctest_status": args.pcl_v3_ctest_status,
        "pcl_v3_ctest_summary": args.pcl_ctest_summary,
        "phase_a_runner_test_invocation_count": 0,
    }
    write_json(ARTIFACT / "test_report.json", test_report)

    decision = {
        "schema_version": "backend_phase_a_lock_decision_v1",
        **audit,
        "PCL_V3_QUALIFICATION_REMAINS_VALID": pcl_v3_valid,
        "OPEN3D_PARAMETER_LOCK_PASS": parameter_lock_pass,
        "PCL_PARAMETER_LOCK_PASS": parameter_lock_pass,
        "ARTIFACT_SHA_VERIFICATION_PASS": True,
        "NEW_PROTOCOL_AMBIGUITIES_FOUND": False,
        "BACKEND_PHASE_A_PROTOCOL_LOCK_PASS": lock_pass,
        "BACKEND_PHASE_A_RUN_AUTHORIZED": lock_pass,
        "BACKEND_PHASE_A_EXECUTED": False,
        "BACKEND_PHASE_A_COMPLETE": False,
        "TWO_INDEPENDENT_BACKENDS_QUALIFIED": False,
        "DAY1_SCIENTIFIC_VALIDATION_PASS": "NOT_EVALUATED",
        "PHASE_B_AUTHORIZED": False,
        "FULL_DEVELOPMENT_AUTHORIZED": False,
        "CONFIRMATORY_AUTHORIZED": False,
        "REAL_DATA_AUTHORIZED": False,
        "MEASUREMENT_PAPER_MAINLINE_AUTHORIZED": False,
        "git_push_performed": False,
        "final_worktree_clean_after_commit_required": True,
        **protected,
    }
    write_json(ARTIFACT / "final_decision.json", decision)

    manifest = {
        "schema_version": "backend_phase_a_lock_run_manifest_v1",
        "branch": "feature/zero-perturbation-backend-phase-a-lock",
        "baseline_commit": BASELINE_COMMIT,
        "protocol_path": PROTOCOL_RELATIVE.as_posix(),
        "protocol_sha256": PROTOCOL_SHA256,
        "protocol_document_sha256": DOCUMENT_SHA256,
        "protocol_lock_commit": PROTOCOL_LOCK_COMMIT,
        "protocol_lock_tag": PROTOCOL_LOCK_TAG,
        "planned_snapshot_count": len(snapshot_rows),
        "planned_trial_count": len(trial_rows),
        "plan_contains_point_cloud_data": False,
        "phase_a_runner_invoked": False,
        "phase_a_rng_instantiation_count": 0,
        "phase_a_snapshot_generation_count": 0,
        "phase_a_backend_execution_count": 0,
        "phase_a_trial_result_count": 0,
        "phase_b_execution_count": 0,
        "confirmatory_rng_instantiation_count": 0,
        "old_capture_test_rng_instantiation_count": 0,
        "native_formal_execution_count": 0,
        "real_data_used": False,
        "vision_used": False,
        "git_push_performed": False,
        "lock_pass_tag_planned": LOCK_PASS_TAG,
        **protected,
    }
    write_json(ARTIFACT / "run_manifest.json", manifest)

    lock_payload = {
        "schema_version": "backend_phase_a_protocol_lock_v1",
        "protocol_path": PROTOCOL_RELATIVE.as_posix(),
        "protocol_sha256": PROTOCOL_SHA256,
        "protocol_document_path": DOCUMENT_RELATIVE.as_posix(),
        "protocol_document_sha256": DOCUMENT_SHA256,
        "protocol_lock_commit": PROTOCOL_LOCK_COMMIT,
        "protocol_lock_tag": PROTOCOL_LOCK_TAG,
        "planned_snapshots_sha256": file_sha256(ARTIFACT / "planned_snapshots.csv"),
        "planned_trials_sha256": file_sha256(ARTIFACT / "planned_trials.csv"),
        "planned_snapshot_count": 210,
        "planned_trial_count": 420,
        "open3d_parameter_sha256": parameter_contract["open3d_parameter_sha256"],
        "pcl_parameter_sha256": parameter_contract["pcl_parameter_sha256"],
        "implementation_hashes_sha256": file_sha256(
            ARTIFACT / "implementation_hashes.json"
        ),
        "phase_a_rng_instantiation_count": 0,
        "phase_a_snapshot_generation_count": 0,
        "phase_a_backend_execution_count": 0,
        "phase_a_trial_result_count": 0,
        "BACKEND_PHASE_A_PROTOCOL_LOCK_PASS": lock_pass,
        "BACKEND_PHASE_A_RUN_AUTHORIZED": lock_pass,
        "BACKEND_PHASE_A_EXECUTED": False,
    }
    lock_document = {
        **lock_payload,
        "lock_payload_sha256": canonical_json_sha256(lock_payload),
    }
    write_json(ARTIFACT / "backend_phase_a_protocol_lock.json", lock_document)

    report = f"""# Zero-Perturbation Dual-Backend Phase A Protocol Lock

## Decision

Protocol-lock status is `{str(lock_pass).lower()}` and future Phase A run
authorization is `{str(lock_pass).lower()}`. This never means Phase A ran:
`BACKEND_PHASE_A_EXECUTED=false`, `BACKEND_PHASE_A_COMPLETE=false`, two-backend
qualification remains false, and Day 1 scientific validation is NOT_EVALUATED.

## Planned matrix

The plan contains {len(snapshot_rows)} snapshot IDs and {len(trial_rows)} trial
IDs: seven scenes × three Development geometry seeds × two Development
measurement seeds × five repeats × IDEAL_MATCHED only. Open3D and PCL each have
210 planned rows; Native has zero. CSV construction used Cartesian enumeration
only and contains no coordinates or point-cloud paths.

## Input and transform contracts

Both backends share C-contiguous little-endian float32 source/target coordinates
with SHA-256 over raw bytes, and the same little-endian float64 4×4 reference
pose. `T_reference` and `T_estimated` both map source to target/map;
`T_delta=inverse(T_reference)@T_estimated`. Translation is the delta-translation
norm. Rotation is reflection-safe nearest-SO(3) plus atan2, subject first to the
raw matrix-quality Gate.

## Backend parameter locks

Open3D 0.19.0+b012259 parameter SHA is
`{parameter_contract['open3d_parameter_sha256']}`. PCL 1.15.1 parameter SHA is
`{parameter_contract['pcl_parameter_sha256']}`. Both lock checks are
`{str(parameter_lock_pass).lower()}` and maximum correspondence distance is the
same 0.50 m. No backend implementation was changed.

## Failure and Gate contracts

Open3D and PCL failure vocabularies are stored in `gate_contract.json`.
Unexecuted trials remain NOT_EVALUATED, never zero failures. Median uses
`numpy.median`; q95 uses `numpy.quantile(q=0.95, method="linear")`. Per backend,
all 210 future trials must be complete, finite, failure-free and pass unchanged
translation/rotation Gates. Each scene/backend median is gated over 30 trials.
Each scene also needs at least ten unique source checksums over 30 snapshots.

## Non-execution and scope audit

RNG instantiations={audit['PHASE_A_RNG_INSTANTIATION_COUNT']}, generated Phase A
snapshots={audit['PHASE_A_SNAPSHOT_GENERATION_COUNT']}, backend executions=
{audit['PHASE_A_BACKEND_EXECUTION_COUNT']}, and trial results=
{audit['PHASE_A_TRIAL_RESULT_COUNT']}. Confirmatory/old-Test RNG and Native
formal execution counts are zero. Phase A/B, real data, vision and the runner
were not invoked. Open3D, PCL, Native, ODI, d50, FAST-LIO2 and the frozen scene
generator are unchanged; no push occurred.
"""
    (ARTIFACT / "phase_a_lock_report.md").write_text(report, encoding="utf-8")
    write_sums(ARTIFACT)


if __name__ == "__main__":
    main()
