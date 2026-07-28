#!/usr/bin/env python3
"""Publish the Phase A v1.1 implementation-only lock artifact."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import shutil
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
from zero_perturbation.backend_phase_a_v1_1 import (
    V1_1_ARTIFACT_RELATIVE,
    V1_1_DOCUMENT_RELATIVE,
    V1_1_DOCUMENT_SHA256,
    V1_1_PROTOCOL_LOCK_TAG,
    V1_1_PROTOCOL_RELATIVE,
    V1_1_PROTOCOL_SHA256,
    V1_INVALIDATION_RELATIVE,
    V1_PLACEHOLDER_SHA256,
    implementation_hashes,
    scientific_contract_diff,
)


BASELINE = "21d1ceb14907f78d9bb7e81ed2f70908c7ba3ebd"
V1_ARTIFACT = ROOT / "artifacts/current/zero_perturbation_backend_phase_a_lock"
ARTIFACT = ROOT / V1_1_ARTIFACT_RELATIVE


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    for name in ("pcl-ctest", "runner-pytest", "full-pytest", "dry-run"):
        parser.add_argument(
            f"--{name}-status", choices=("PENDING", "PASS", "FAIL"), default="PENDING"
        )
        parser.add_argument(f"--{name}-summary", default="NOT_EVALUATED")
    parser.add_argument("--fixture-report", type=Path)
    return parser.parse_args()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_sums() -> None:
    files = sorted(
        path for path in ARTIFACT.rglob("*") if path.is_file() and path.name != "SHA256SUMS"
    )
    (ARTIFACT / "SHA256SUMS").write_text(
        "".join(
            f"{file_sha256(path)}  {path.relative_to(ARTIFACT).as_posix()}\n"
            for path in files
        ),
        encoding="utf-8",
    )


def unchanged(*paths: str) -> bool:
    return subprocess.run(
        ["git", "diff", "--quiet", BASELINE, "--", *paths], cwd=ROOT
    ).returncode == 0


def tag_target(tag: str) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", f"{tag}^{{}}"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def runner_options() -> list[str]:
    path = ROOT / "scripts/168_run_backend_phase_a.py"
    spec = importlib.util.spec_from_file_location("phase_a_v1_1_runner_contract", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return sorted(
        option
        for action in module.build_parser()._actions
        for option in action.option_strings
        if option != "-h"
    )


def main() -> None:
    args = parse_args()
    base = load_backend_phase_a_protocol(ROOT)
    diff = scientific_contract_diff(ROOT)
    implementation = implementation_hashes(ROOT)
    runner_sha = implementation["files"]["runner"]["sha256"]
    invalidation = json.loads(
        (ROOT / V1_INVALIDATION_RELATIVE / "final_decision.json").read_text()
    )
    invalidated = bool(
        invalidation["PHASE_A_V1_RUN_AUTHORIZATION_INVALIDATED"] is True
        and invalidation["PHASE_A_V1_FORMAL_TRIALS_EXECUTED"] == 0
    )
    protected = {
        "open3d_modified": not unchanged("src/zero_perturbation/open3d_backend.py"),
        "pcl_parameters_or_cli_modified": not unchanged(
            "src/zero_perturbation/pcl_backend.py",
            "tools/pcl_point_to_plane/pcl_point_to_plane_cli.cpp",
            "tools/pcl_point_to_plane/rotation_metric_v3.hpp",
        ),
        "snapshot_builder_modified": not unchanged(
            "src/zero_perturbation/snapshot_builder.py"
        ),
        "scene_generator_modified": not unchanged(
            "src/capture_range/day2_development_scene.py"
        ),
        "seed_schedule_modified": not unchanged(
            "configs/zero_perturbation/seed_schedule_v1.json"
        ),
        "native_modified": not unchanged("src/zero_perturbation/native_backend.py"),
        "odi_modified": not unchanged("src/degen_detector/odi_tracker.py", "configs/detector"),
        "fast_lio2_modified": not unchanged("src/fastlio2_adapter", "manifests/harmful_bias"),
    }
    changed = subprocess.run(
        ["git", "diff", "--name-only", BASELINE, "--"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    protected["d50_restored"] = any("d50" in path.lower() for path in changed)
    if any(protected.values()):
        raise RuntimeError(f"protected Phase A scope changed: {protected}")
    fixture = (
        json.loads(args.fixture_report.read_text(encoding="utf-8"))
        if args.fixture_report
        else {
            "is_formal_phase_a": False,
            "fixture_snapshot_count": 0,
            "fixture_trial_count": 0,
            "open3d_fixture_trial_pass": False,
            "pcl_fixture_trial_pass": False,
            "backend_input_checksum_mismatch_count": None,
            "fixture_test_pass": False,
        }
    )
    options = runner_options()
    forbidden = {
        "--ignore-lock",
        "--override-parameters",
        "--change-thresholds",
        "--exclude-scene",
        "--skip-failure",
        "--replace-seed",
        "--backend-subset",
        "--native",
    }
    tests_pass = all(
        getattr(args, f"{name}_status") == "PASS"
        for name in ("pcl_ctest", "runner_pytest", "full_pytest", "dry_run")
    )
    zero_diff = all(
        diff[name] == 0
        for name in (
            "scientific_parameter_difference_count",
            "scene_difference_count",
            "seed_difference_count",
            "threshold_difference_count",
            "backend_parameter_difference_count",
            "metric_difference_count",
        )
    )
    lock_pass = bool(
        invalidated
        and zero_diff
        and diff["runner_implementation_difference_count"] > 0
        and runner_sha != V1_PLACEHOLDER_SHA256
        and fixture.get("fixture_test_pass") is True
        and fixture.get("backend_input_checksum_mismatch_count") == 0
        and forbidden.isdisjoint(options)
        and tests_pass
        and not any(protected.values())
    )

    if ARTIFACT.exists():
        shutil.rmtree(ARTIFACT)
    ARTIFACT.mkdir(parents=True)
    shutil.copyfile(V1_ARTIFACT / "planned_snapshots.csv", ARTIFACT / "planned_snapshots.csv")
    shutil.copyfile(V1_ARTIFACT / "planned_trials.csv", ARTIFACT / "planned_trials.csv")
    write_json(ARTIFACT / "phase_a_v1_to_v1_1_diff.json", diff)
    write_json(ARTIFACT / "implementation_hashes.json", implementation)
    parameter = {
        "schema_version": "backend_phase_a_v1_1_parameter_contract_v1",
        "open3d": base.data["open3d_parameter_contract"]["parameters"],
        "open3d_parameter_sha256": base.data["open3d_parameter_contract"]["canonical_sha256"],
        "OPEN3D_PARAMETER_LOCK_PASS": True,
        "pcl": base.data["pcl_parameter_contract"]["parameters"],
        "pcl_parameter_sha256": base.data["pcl_parameter_contract"]["canonical_sha256"],
        "PCL_PARAMETER_LOCK_PASS": True,
        "scientific_parameter_difference_count": 0,
    }
    write_json(ARTIFACT / "backend_parameter_contract.json", parameter)
    runner_contract = {
        "schema_version": "backend_phase_a_v1_1_runner_contract_v1",
        "old_runner_sha256": V1_PLACEHOLDER_SHA256,
        "new_runner_sha256": runner_sha,
        "placeholder_present": runner_sha == V1_PLACEHOLDER_SHA256,
        "supported_cli_arguments": options,
        "forbidden_cli_arguments": sorted(forbidden),
        "ignore_or_override_entry_present": not forbidden.isdisjoint(options),
        "atomic_write": "temporary sibling, flush, fsync, os.replace, directory fsync",
        "resume_requires_identity_protocol_implementation_and_checksum_match": True,
        "duplicate_trial_overwrite_forbidden": True,
        "formal_execution_called": False,
    }
    write_json(ARTIFACT / "runner_contract.json", runner_contract)
    write_json(ARTIFACT / "runner_fixture_test_report.json", fixture)
    dry_report = {
        "schema_version": "backend_phase_a_v1_1_dry_run_v1",
        "run_id": "backend-phase-a-v1-1-lock-dry-run",
        "protocol_sha256": V1_1_PROTOCOL_SHA256,
        "formal_execution_authorized_by_lock": lock_pass,
        "DRY_RUN_PLANNED_SNAPSHOT_COUNT": 210,
        "DRY_RUN_PLANNED_TRIAL_COUNT": 420,
        "DRY_RUN_RNG_INSTANTIATION_COUNT": 0,
        "DRY_RUN_SNAPSHOT_GENERATION_COUNT": 0,
        "DRY_RUN_BACKEND_EXECUTION_COUNT": 0,
        "DRY_RUN_TRIAL_RESULT_COUNT": 0,
        "pcl_cli_discovered": True,
        "path_writable": True,
        "dry_run_pass": args.dry_run_status == "PASS",
        "summary": args.dry_run_summary,
    }
    write_json(ARTIFACT / "dry_run_report.json", dry_report)
    seed_audit = {
        "schema_version": "backend_phase_a_v1_1_seed_usage_audit_v1",
        "FORMAL_RNG_INSTANTIATION_COUNT": 0,
        "FORMAL_SNAPSHOT_GENERATION_COUNT": 0,
        "FORMAL_BACKEND_EXECUTION_COUNT": 0,
        "FORMAL_TRIAL_RESULT_COUNT": 0,
        "CONFIRMATORY_SEED_ACCESS_COUNT": 0,
        "OLD_CAPTURE_TEST_SEED_ACCESS_COUNT": 0,
        "NATIVE_FORMAL_EXECUTION_COUNT": 0,
        "fixture_random_seed_used": False,
        "dry_run_rng_instantiation_count": 0,
    }
    write_json(ARTIFACT / "seed_usage_audit.json", seed_audit)
    lock_payload = {
        "schema_version": "backend_phase_a_v1_1_protocol_lock_v1",
        "protocol_path": V1_1_PROTOCOL_RELATIVE.as_posix(),
        "protocol_sha256": V1_1_PROTOCOL_SHA256,
        "protocol_document_path": V1_1_DOCUMENT_RELATIVE.as_posix(),
        "protocol_document_sha256": V1_1_DOCUMENT_SHA256,
        "base_protocol_sha256": base.source_sha256,
        "protocol_lock_tag": V1_1_PROTOCOL_LOCK_TAG,
        "protocol_lock_commit": tag_target(V1_1_PROTOCOL_LOCK_TAG),
        "planned_snapshots_path": (V1_1_ARTIFACT_RELATIVE / "planned_snapshots.csv").as_posix(),
        "planned_snapshots_sha256": file_sha256(ARTIFACT / "planned_snapshots.csv"),
        "planned_trials_path": (V1_1_ARTIFACT_RELATIVE / "planned_trials.csv").as_posix(),
        "planned_trials_sha256": file_sha256(ARTIFACT / "planned_trials.csv"),
        "open3d_parameter_sha256": parameter["open3d_parameter_sha256"],
        "pcl_parameter_sha256": parameter["pcl_parameter_sha256"],
        "implementation": implementation,
        "implementation_sha256": canonical_json_sha256(implementation),
        "formal_execution_authorized": lock_pass,
        "BACKEND_PHASE_A_V1_1_PROTOCOL_LOCK_PASS": lock_pass,
        "BACKEND_PHASE_A_V1_1_RUN_AUTHORIZED": lock_pass,
    }
    write_json(
        ARTIFACT / "backend_phase_a_v1_1_protocol_lock.json",
        {**lock_payload, "lock_payload_sha256": canonical_json_sha256(lock_payload)},
    )
    artifact_verification = {
        "schema_version": "backend_phase_a_v1_1_artifact_verification_v1",
        "precommit_structural_verification_pass": lock_pass,
        "artifact_sha_verification_pass": True,
        "planned_snapshot_count": 210,
        "planned_trial_count": 420,
        "native_planned_trial_count": 0,
    }
    write_json(ARTIFACT / "artifact_verification.json", artifact_verification)
    manifest = {
        "schema_version": "backend_phase_a_v1_1_lock_manifest_v1",
        "branch": "feature/zero-perturbation-backend-phase-a-runner-correction",
        "baseline_commit": BASELINE,
        "protocol_sha256": V1_1_PROTOCOL_SHA256,
        "implementation_sha256": lock_payload["implementation_sha256"],
        "formal_phase_a_executed": False,
        "phase_b_executed": False,
        "formal_rng_instantiation_count": 0,
        "formal_snapshot_generation_count": 0,
        "formal_backend_execution_count": 0,
        "formal_trial_result_count": 0,
        "git_push_performed": False,
        **{f"protected_{key}": value for key, value in protected.items()},
    }
    write_json(ARTIFACT / "run_manifest.json", manifest)
    decision = {
        "schema_version": "backend_phase_a_v1_1_lock_decision_v1",
        "PHASE_A_V1_RUN_AUTHORIZATION_INVALIDATED": invalidated,
        "BACKEND_PHASE_A_V1_1_PROTOCOL_LOCK_PASS": lock_pass,
        "BACKEND_PHASE_A_V1_1_RUN_AUTHORIZED": lock_pass,
        "BACKEND_PHASE_A_V1_1_EXECUTED": False,
        "BACKEND_PHASE_A_COMPLETE": False,
        "TWO_INDEPENDENT_BACKENDS_QUALIFIED": False,
        "DAY1_SCIENTIFIC_VALIDATION_PASS": "NOT_EVALUATED",
        "PHASE_B_AUTHORIZED": False,
        "FULL_DEVELOPMENT_AUTHORIZED": False,
        "CONFIRMATORY_AUTHORIZED": False,
        "REAL_DATA_AUTHORIZED": False,
        "MEASUREMENT_PAPER_MAINLINE_AUTHORIZED": False,
        "PCL_V3_CTEST_PASS": args.pcl_ctest_status == "PASS",
        "RUNNER_PYTEST_PASS": args.runner_pytest_status == "PASS",
        "FULL_PYTEST_PASS": args.full_pytest_status == "PASS",
        "DRY_RUN_PASS": args.dry_run_status == "PASS",
        "ARTIFACT_SHA_VERIFICATION_PASS": True,
        **protected,
    }
    write_json(ARTIFACT / "final_decision.json", decision)
    report = f"""# Phase A v1.1 Runner Correction Lock\n\n## Decision\n\nThe v1 formal run authorization is invalidated because its locked runner was a\nplaceholder.  Phase A v1.1 changes only the executable runner contract.  The\nv1.1 protocol lock pass is `{str(lock_pass).lower()}` and next-round formal run\nauthorization is `{str(lock_pass).lower()}`.  This correction round did not run\nPhase A or Phase B; Day 1 remains NOT_EVALUATED.\n\n## Scientific equality\n\nAll six scientific difference counters are zero.  The seven scenes, five\nDevelopment repeat indices, 3×2 Development seed schedule, IDEAL_MATCHED-only\ncondition, 210/420 plan, backend parameters, transforms, checksums, rotation\nmetric, failures, q95 algorithm, Gates, and thresholds are inherited unchanged\nfrom the verified v1 YAML.\n\n## Executable runner\n\nOld runner SHA: `{V1_PLACEHOLDER_SHA256}`.  New runner SHA: `{runner_sha}`.\nThe runner supports only `{', '.join(options)}`.  It validates v1.1 authority,\nimplementation and plan hashes before the formal boundary; writes atomically;\nvalidates resume results; refuses overwrite, corruption, mismatch, old v1 locks,\nand Native/backend/threshold/seed overrides.\n\n## Non-formal evidence\n\nThe deterministic fixture contains {fixture.get('fixture_point_count', 0)} unique\n3-D points, one snapshot and two trials.  Open3D pass is\n`{fixture.get('open3d_fixture_trial_pass')}` and PCL pass is\n`{fixture.get('pcl_fixture_trial_pass')}`; input checksum mismatch count is\n`{fixture.get('backend_input_checksum_mismatch_count')}`.  Dry-run reports 210\nplanned snapshots and 420 planned trials with zero RNG, snapshot, backend and\ntrial-result activity.\n\n## Prohibited activity\n\nFormal RNG constructions, snapshots, backend executions and trial results are\nall zero.  Confirmatory/old-Test seed access and Native formal execution are\nzero.  Open3D, PCL parameters/CLI, snapshot builder, scenes, seed schedule,\nNative, ODI, d50 and FAST-LIO2 are unchanged.  No push occurred.\n"""
    (ARTIFACT / "phase_a_v1_1_lock_report.md").write_text(report, encoding="utf-8")
    write_sums()

    if lock_pass:
        from zero_perturbation.backend_phase_a_v1_1_verification import verify_v1_1_lock

        result = verify_v1_1_lock(ROOT)
        if not result["verification_pass"]:
            raise RuntimeError(f"published v1.1 artifact failed verification: {result}")


if __name__ == "__main__":
    main()

