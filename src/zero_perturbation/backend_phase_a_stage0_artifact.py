"""Publish and verify the compact Phase A v1.2 Stage-0 decision artifact."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .backend_phase_a_protocol import canonical_json_sha256, file_sha256
from .backend_phase_a_stage0_verification import verify_stage0_cache
from .backend_phase_a_v1_2 import (
    SNAPSHOT_LOCK_SCHEMA,
    V1_2_PROTOCOL_SHA256,
    V1_2_STAGE0_ARTIFACT_RELATIVE,
    planned_rows,
    snapshot_directory,
    validate_protocol_lock,
    validate_snapshot_directory,
)


TABLE_FILES = (
    "tables/snapshot_inventory.csv",
    "tables/snapshot_file_inventory.csv",
    "tables/parent_lineage_summary.csv",
    "tables/reconstruction_error_summary.csv",
    "tables/snapshot_diversity.csv",
    "tables/stage0_failure_inventory.csv",
    "tables/gate_summary.csv",
)
FIGURE_FILES = (
    "figures/reconstruction_error_distribution.png",
    "figures/reconstruction_error_by_scene.png",
    "figures/quantization_predicted_vs_actual.png",
    "figures/closure_residual_ratio.png",
    "figures/snapshot_diversity.png",
)
ROOT_FILES = (
    "backend_phase_a_v1_2_snapshot_lock.json",
    "stage0_report.md",
    "final_decision.json",
    "run_manifest.json",
    "independent_verification.json",
    "artifact_verification.json",
)
REQUIRED_FILES = (*TABLE_FILES, *FIGURE_FILES, *ROOT_FILES, "SHA256SUMS")


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _write_csv(
    path: Path, rows: list[Mapping[str, Any]], fieldnames: Iterable[str]
) -> None:
    names = list(fieldnames)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=names, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_sums(artifact: Path) -> None:
    files = sorted(
        path
        for path in artifact.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    )
    (artifact / "SHA256SUMS").write_text(
        "".join(
            f"{file_sha256(path)}  {path.relative_to(artifact).as_posix()}\n"
            for path in files
        ),
        encoding="utf-8",
    )


def verify_sha256_manifest(artifact: str | Path) -> dict[str, Any]:
    root = Path(artifact)
    manifest = root / "SHA256SUMS"
    failures: list[str] = []
    entries = 0
    if not manifest.is_file():
        return {"entry_count": 0, "failure_paths": ["SHA256SUMS"], "pass": False}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        digest, separator, relative = line.partition("  ")
        entries += 1
        candidate = root / relative
        if (
            not separator
            or len(digest) != 64
            or not candidate.is_file()
            or file_sha256(candidate) != digest
        ):
            failures.append(relative or line)
    return {"entry_count": entries, "failure_paths": failures, "pass": not failures}


def verify_stage0_artifact(root: str | Path) -> dict[str, Any]:
    artifact = Path(root).resolve() / V1_2_STAGE0_ARTIFACT_RELATIVE
    missing = [relative for relative in REQUIRED_FILES if not (artifact / relative).is_file()]
    checksum = verify_sha256_manifest(artifact) if not missing else {
        "entry_count": 0,
        "failure_paths": missing,
        "pass": False,
    }
    semantic_failures: list[str] = []
    try:
        decision = json.loads((artifact / "final_decision.json").read_text())
        independent = json.loads(
            (artifact / "independent_verification.json").read_text()
        )
        snapshot_lock = json.loads(
            (artifact / "backend_phase_a_v1_2_snapshot_lock.json").read_text()
        )
        payload = {
            key: value
            for key, value in snapshot_lock.items()
            if key != "lock_payload_sha256"
        }
        required_true = (
            "PHASE_A_V1_2_PROTOCOL_LOCK_PASS",
            "SEED_CONTINUATION_AFTER_PRE_BACKEND_ABORT_JUSTIFIED",
            "ALL_210_STAGE0_SNAPSHOTS_COMPLETE",
            "SNAPSHOT_PROVENANCE_LINEAGE_PASS",
            "FLOAT32_RECONSTRUCTION_CLOSURE_PASS",
            "CANONICAL_INPUT_CACHE_PASS",
            "IDEAL_MATCHED_SNAPSHOT_DIVERSITY_PASS",
            "STAGE0_ANALYSIS_VERIFIER_MATCH",
            "STAGE0_ARTIFACT_VERIFICATION_PASS",
            "PHASE_A_V1_2_STAGE0_PASS",
            "PHASE_A_STAGE1_BACKEND_RUN_AUTHORIZED",
        )
        if any(decision.get(name) is not True for name in required_true):
            semantic_failures.append("decision_true_gate")
        if (
            decision.get("FORMAL_STAGE0_SNAPSHOT_BUILD_COUNT") != 210
            or decision.get("FORMAL_BACKEND_EXECUTION_COUNT") != 0
            or decision.get("FORMAL_TRIAL_RESULT_COUNT") != 0
        ):
            semantic_failures.append("decision_count_gate")
        if independent.get("verification_pass") is not True:
            semantic_failures.append("independent_verification")
        if (
            snapshot_lock.get("schema_version") != SNAPSHOT_LOCK_SCHEMA
            or canonical_json_sha256(payload)
            != snapshot_lock.get("lock_payload_sha256")
        ):
            semantic_failures.append("snapshot_lock_payload")
    except (OSError, json.JSONDecodeError, TypeError) as error:
        semantic_failures.append(f"parse:{type(error).__name__}")
    passed = not missing and checksum["pass"] and not semantic_failures
    return {
        "schema_version": "backend_phase_a_v1_2_stage0_artifact_verification_v1",
        "required_file_count": len(REQUIRED_FILES),
        "missing_files": missing,
        "sha256_entry_count": checksum["entry_count"],
        "sha256_failure_paths": checksum["failure_paths"],
        "semantic_failures": semantic_failures,
        "verification_pass": passed,
    }


def _main_verifier_match(
    metadata_rows: list[dict[str, Any]], verifier_rows: list[dict[str, Any]]
) -> bool:
    by_id = {str(row["snapshot_id"]): row for row in verifier_rows}
    fields = (
        "source_point_count",
        "target_point_count",
        "source_raw_checksum",
        "target_raw_checksum",
        "reference_pose_raw_checksum",
        "parent_index_raw_checksum",
        "snapshot_checksum",
        "parent_index_unique_count",
        "parent_index_out_of_range_count",
        "parent_index_duplicate_count",
        "reconstruction_error_median_m",
        "reconstruction_error_q95_m",
        "reconstruction_error_max_m",
        "predicted_quantization_median_m",
        "predicted_quantization_q95_m",
        "predicted_quantization_max_m",
        "closure_residual_max_m",
        "float64_guard_max_m",
        "max_normalized_closure_ratio",
        "closure_residual_violation_count",
        "actual_error_bound_violation_count",
        "quantization_closure_pass",
    )
    if len(metadata_rows) != 210 or len(verifier_rows) != 210:
        return False
    for metadata in metadata_rows:
        other = by_id.get(str(metadata["snapshot_id"]))
        if other is None:
            return False
        for field in fields:
            left, right = metadata.get(field), other.get(field)
            if isinstance(left, float) or isinstance(right, float):
                if not np.isclose(float(left), float(right), rtol=0.0, atol=0.0):
                    return False
            elif left != right:
                return False
    return True


def _figures(artifact: Path, rows: list[dict[str, Any]], diversity: list[dict[str, Any]]) -> None:
    figures = artifact / "figures"
    scenes = sorted({str(row["scene_variant"]) for row in rows})
    actual = np.asarray([row["reconstruction_error_max_m"] for row in rows], dtype=float)
    predicted = np.asarray([row["predicted_quantization_max_m"] for row in rows], dtype=float)
    ratios = np.asarray([row["max_normalized_closure_ratio"] for row in rows], dtype=float)

    fig, axis = plt.subplots(figsize=(8, 5))
    axis.hist(actual, bins=30, color="#3268a8", alpha=0.85)
    axis.set(xlabel="Per-snapshot maximum reconstruction error (m)", ylabel="Snapshot count", title="Float32 reconstruction error distribution")
    fig.tight_layout()
    fig.savefig(figures / "reconstruction_error_distribution.png", dpi=160)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(11, 5))
    grouped = [[row["reconstruction_error_max_m"] for row in rows if row["scene_variant"] == scene] for scene in scenes]
    axis.boxplot(grouped, labels=scenes, showfliers=True)
    axis.tick_params(axis="x", rotation=30)
    axis.set(ylabel="Maximum reconstruction error (m)", title="Reconstruction error by scene")
    fig.tight_layout()
    fig.savefig(figures / "reconstruction_error_by_scene.png", dpi=160)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(6, 6))
    axis.scatter(predicted, actual, s=18, alpha=0.75)
    bound = max(float(actual.max()), float(predicted.max())) if len(actual) else 1.0
    axis.plot([0, bound], [0, bound], linestyle="--", color="black", linewidth=1)
    axis.set(xlabel="Predicted quantization maximum (m)", ylabel="Actual reconstruction maximum (m)", title="Predicted versus actual float32 error")
    fig.tight_layout()
    fig.savefig(figures / "quantization_predicted_vs_actual.png", dpi=160)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(8, 5))
    axis.plot(np.arange(len(ratios)), np.sort(ratios), color="#a84232")
    axis.axhline(1.0, color="black", linestyle="--", linewidth=1)
    axis.set(xlabel="Sorted snapshot index", ylabel="Maximum normalized closure ratio", title="Closure residual / float64 guard")
    fig.tight_layout()
    fig.savefig(figures / "closure_residual_ratio.png", dpi=160)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(11, 5))
    labels = [str(row["scene_variant"]) for row in diversity]
    values = [int(row["unique_source_checksum_count"]) for row in diversity]
    axis.bar(labels, values, color="#4f8f5b")
    axis.axhline(10, color="black", linestyle="--", linewidth=1)
    axis.tick_params(axis="x", rotation=30)
    axis.set(ylabel="Unique source checksum count", title="IDEAL_MATCHED source diversity")
    fig.tight_layout()
    fig.savefig(figures / "snapshot_diversity.png", dpi=160)
    plt.close(fig)


def publish_stage0_artifact(
    *,
    root: str | Path,
    protocol_lock: str | Path,
    cache_root: str | Path,
    run_id: str,
    targeted_pytest_summary: str,
    full_pytest_summary: str,
    pcl_ctest_summary: str,
) -> dict[str, Any]:
    repository = Path(root).resolve()
    artifact = repository / V1_2_STAGE0_ARTIFACT_RELATIVE
    if artifact.exists():
        raise FileExistsError(f"refusing to overwrite Stage-0 artifact: {artifact}")
    protocol = validate_protocol_lock(protocol_lock, repository)
    cache = Path(cache_root).resolve()
    plans, _ = planned_rows(repository)
    independent = verify_stage0_cache(
        root=repository, protocol_lock=protocol_lock, cache_root=cache
    )
    metadata_rows: list[dict[str, Any]] = []
    for plan in plans:
        directory = snapshot_directory(cache, str(plan["snapshot_id"]))
        if directory.is_dir():
            metadata_rows.append(validate_snapshot_directory(directory))
    analysis_match = _main_verifier_match(
        metadata_rows, independent.get("snapshot_rows", [])
    )
    required_gates = {
        "PHASE_A_V1_2_PROTOCOL_LOCK_PASS": protocol.get("PHASE_A_V1_2_PROTOCOL_LOCK_PASS") is True,
        "SEED_CONTINUATION_AFTER_PRE_BACKEND_ABORT_JUSTIFIED": protocol.get("SEED_CONTINUATION_AFTER_PRE_BACKEND_ABORT_JUSTIFIED") is True,
        "ALL_210_STAGE0_SNAPSHOTS_COMPLETE": independent.get("ALL_210_STAGE0_SNAPSHOTS_COMPLETE") is True,
        "SNAPSHOT_PROVENANCE_LINEAGE_PASS": independent.get("SNAPSHOT_PROVENANCE_LINEAGE_PASS") is True,
        "FLOAT32_RECONSTRUCTION_CLOSURE_PASS": independent.get("FLOAT32_RECONSTRUCTION_CLOSURE_PASS") is True,
        "CANONICAL_INPUT_CACHE_PASS": independent.get("CANONICAL_INPUT_CACHE_PASS") is True,
        "IDEAL_MATCHED_SNAPSHOT_DIVERSITY_PASS": independent.get("IDEAL_MATCHED_SNAPSHOT_DIVERSITY_PASS") is True,
        "STAGE0_ANALYSIS_VERIFIER_MATCH": analysis_match,
        "STAGE0_ARTIFACT_VERIFICATION_PASS": True,
    }
    stage0_pass = bool(
        all(required_gates.values())
        and independent.get("actual_complete_snapshot_count") == 210
        and independent.get("FORMAL_BACKEND_EXECUTION_COUNT") == 0
        and independent.get("FORMAL_TRIAL_RESULT_COUNT") == 0
    )
    artifact.mkdir(parents=True)
    (artifact / "tables").mkdir()
    (artifact / "figures").mkdir()
    rows = independent.get("snapshot_rows", [])
    file_rows = independent.get("snapshot_file_rows", [])
    diversity_rows = independent.get("diversity_rows", [])
    failures = independent.get("failure_rows", [])
    _write_csv(artifact / TABLE_FILES[0], rows, rows[0].keys() if rows else ("snapshot_id",))
    _write_csv(artifact / TABLE_FILES[1], file_rows, file_rows[0].keys() if file_rows else ("snapshot_id", "filename", "file_sha256", "metadata_file_sha256", "file_checksum_pass"))
    lineage_fields = ("snapshot_id", "scene_variant", "source_point_count", "target_point_count", "parent_index_unique_count", "parent_index_out_of_range_count", "parent_index_duplicate_count", "lineage_violation_count", "source_inverse_transform_pass")
    _write_csv(artifact / TABLE_FILES[2], rows, lineage_fields)
    reconstruction_fields = ("snapshot_id", "scene_variant", "reconstruction_error_median_m", "reconstruction_error_q95_m", "reconstruction_error_max_m", "predicted_quantization_median_m", "predicted_quantization_q95_m", "predicted_quantization_max_m", "closure_residual_max_m", "float64_guard_max_m", "max_normalized_closure_ratio", "closure_residual_violation_count", "actual_error_bound_violation_count", "quantization_closure_pass")
    _write_csv(artifact / TABLE_FILES[3], rows, reconstruction_fields)
    _write_csv(artifact / TABLE_FILES[4], diversity_rows, diversity_rows[0].keys() if diversity_rows else ("scene_variant",))
    _write_csv(artifact / TABLE_FILES[5], failures, ("snapshot_id", "classification", "detail"))
    gate_rows = [{"gate": name, "value": value} for name, value in required_gates.items()]
    gate_rows.extend(
        {"gate": name, "value": independent.get(name)}
        for name in ("planned_snapshot_count", "actual_complete_snapshot_count", "missing_snapshot_count", "extra_snapshot_count", "duplicate_snapshot_count", "corrupt_snapshot_count", "parent_index_out_of_range_count", "parent_index_duplicate_count", "lineage_violation_count", "cache_checksum_violation_count", "closure_violation_count")
    )
    _write_csv(artifact / TABLE_FILES[6], gate_rows, ("gate", "value"))
    _figures(artifact, rows, diversity_rows)
    compact_independent = {
        key: value
        for key, value in independent.items()
        if key not in {"snapshot_rows", "snapshot_file_rows", "diversity_rows", "failure_rows"}
    }
    _write_json(artifact / "independent_verification.json", compact_independent)
    inventory_path = V1_2_STAGE0_ARTIFACT_RELATIVE / TABLE_FILES[0]
    cache_relative = cache.relative_to(repository).as_posix()
    snapshot_lock_payload = {
        "schema_version": SNAPSHOT_LOCK_SCHEMA,
        "run_id": run_id,
        "protocol_sha256": V1_2_PROTOCOL_SHA256,
        "implementation_sha256": protocol["implementation_sha256"],
        "snapshot_cache_root": cache_relative,
        "snapshot_inventory_path": inventory_path.as_posix(),
        "snapshot_inventory_sha256": file_sha256(artifact / TABLE_FILES[0]),
        "FORMAL_STAGE0_SNAPSHOT_BUILD_COUNT": independent.get("actual_complete_snapshot_count"),
        "FORMAL_BACKEND_EXECUTION_COUNT": 0,
        "FORMAL_TRIAL_RESULT_COUNT": 0,
        "PHASE_A_V1_2_STAGE0_PASS": stage0_pass,
        "PHASE_A_STAGE1_BACKEND_RUN_AUTHORIZED": stage0_pass,
    }
    _write_json(
        artifact / "backend_phase_a_v1_2_snapshot_lock.json",
        {**snapshot_lock_payload, "lock_payload_sha256": canonical_json_sha256(snapshot_lock_payload)},
    )
    decision = {
        "schema_version": "backend_phase_a_v1_2_stage0_decision_v1",
        **required_gates,
        "FORMAL_STAGE0_SNAPSHOT_BUILD_COUNT": independent.get("actual_complete_snapshot_count", 0),
        "FORMAL_BACKEND_EXECUTION_COUNT": 0,
        "FORMAL_TRIAL_RESULT_COUNT": 0,
        "CONFIRMATORY_SEED_ACCESS_COUNT": 0,
        "OLD_CAPTURE_TEST_SEED_ACCESS_COUNT": 0,
        "NATIVE_EXECUTION_COUNT": 0,
        "PHASE_A_V1_2_STAGE0_PASS": stage0_pass,
        "PHASE_A_STAGE1_BACKEND_RUN_AUTHORIZED": stage0_pass,
        "PHASE_A_STAGE1_BACKEND_EXECUTED": False,
        "BACKEND_PHASE_A_COMPLETE": False,
        "TWO_INDEPENDENT_BACKENDS_QUALIFIED": False,
        "DAY1_SCIENTIFIC_VALIDATION_PASS": "NOT_EVALUATED",
        "PHASE_B_AUTHORIZED": False,
        "FULL_DEVELOPMENT_AUTHORIZED": False,
        "CONFIRMATORY_AUTHORIZED": False,
        "REAL_DATA_AUTHORIZED": False,
        "MEASUREMENT_PAPER_MAINLINE_AUTHORIZED": False,
        "PHASE_A_ROUTE_PAUSED_FOR_CONCENTRATED_CODE_AUDIT": not stage0_pass,
    }
    _write_json(artifact / "final_decision.json", decision)
    _write_json(
        artifact / "run_manifest.json",
        {
            "schema_version": "backend_phase_a_v1_2_stage0_run_manifest_v1",
            "run_id": run_id,
            "protocol_sha256": V1_2_PROTOCOL_SHA256,
            "implementation_sha256": protocol["implementation_sha256"],
            "snapshot_cache_root": cache_relative,
            "planned_snapshot_count": independent.get("planned_snapshot_count"),
            "complete_snapshot_count": independent.get("actual_complete_snapshot_count"),
            "stage0_backend_import_count": 0,
            "stage0_backend_execution_count": 0,
            "formal_trial_result_count": 0,
            "confirmatory_seed_access_count": 0,
            "old_capture_test_seed_access_count": 0,
            "native_execution_count": 0,
            "targeted_pytest_summary": targeted_pytest_summary,
            "full_pytest_summary": full_pytest_summary,
            "pcl_v3_ctest_summary": pcl_ctest_summary,
            "phase_a_stage1_executed": False,
            "phase_b_executed": False,
            "git_push_performed": False,
        },
    )
    aggregate = independent.get("aggregate_reconstruction", {})
    report = f"""# Phase A v1.2 Stage-0 Snapshot Audit

## Decision

`PHASE_A_V1_2_STAGE0_PASS = {str(stage0_pass).lower()}` and
`PHASE_A_STAGE1_BACKEND_RUN_AUTHORIZED = {str(stage0_pass).lower()}`. Stage 1
was not executed. Phase A remains incomplete and Day 1 remains NOT_EVALUATED.

## Completeness and provenance

The frozen plan contains 210 snapshots; {independent.get('actual_complete_snapshot_count')} complete cache entries were independently verified. Missing,
extra, duplicate, and corrupt counts are {independent.get('missing_snapshot_count')},
{independent.get('extra_snapshot_count')}, {independent.get('duplicate_snapshot_count')}, and
{independent.get('corrupt_snapshot_count')}. Parent out-of-range, duplicate, and
lineage-violation totals are {independent.get('parent_index_out_of_range_count')},
{independent.get('parent_index_duplicate_count')}, and {independent.get('lineage_violation_count')}.

## Float32 closure

Across all cached source points, reconstruction error median/q95/max is
{aggregate.get('reconstruction_error_median_m')}, {aggregate.get('reconstruction_error_q95_m')}, and
{aggregate.get('reconstruction_error_max_m')} m. Predicted quantization error
median/q95/max is {aggregate.get('predicted_quantization_median_m')},
{aggregate.get('predicted_quantization_q95_m')}, and {aggregate.get('predicted_quantization_max_m')} m.
The maximum closure residual is {aggregate.get('closure_residual_max_m')} m,
maximum guard is {aggregate.get('float64_guard_max_m')} m, and maximum normalized
ratio is {aggregate.get('max_normalized_closure_ratio')}.

## Boundary

Stage-0 backend imports, backend executions, formal trial results, Confirmatory
seed accesses, old capture-range Test seed accesses, and Native executions are
all zero. No backend performance or registration-error result exists in this
artifact. Open3D, PCL, scenes, seeds, metrics, Gates, ODI, d50, and FAST-LIO2
remain unchanged.
"""
    (artifact / "stage0_report.md").write_text(report, encoding="utf-8")
    _write_json(
        artifact / "artifact_verification.json",
        {
            "schema_version": "backend_phase_a_v1_2_stage0_artifact_verification_v1",
            "required_file_count": len(REQUIRED_FILES),
            "missing_files": [],
            "sha256_failure_paths": [],
            "semantic_failures": [],
            "verification_pass": stage0_pass,
        },
    )
    _write_sums(artifact)
    verification = verify_stage0_artifact(repository)
    if verification["verification_pass"] != stage0_pass:
        raise RuntimeError(f"Stage-0 artifact verification mismatch: {verification}")
    return {"decision": decision, "artifact_verification": verification}


__all__ = [
    "FIGURE_FILES",
    "REQUIRED_FILES",
    "ROOT_FILES",
    "TABLE_FILES",
    "publish_stage0_artifact",
    "verify_sha256_manifest",
    "verify_stage0_artifact",
]
