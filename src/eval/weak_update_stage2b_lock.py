"""Immutable source/config/update lock for Weak-Subspace Update Stage 2B."""

from __future__ import annotations

import platform
import sys
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

import numpy as np
import scipy

from eval.analysis_lock import (
    changed_snapshot_files,
    compute_bundle_hash,
    compute_directory_hash,
    compute_source_tree_hash,
    compute_source_tree_snapshot,
    git_commit,
    git_status_clean,
    sha256_file,
)


STAGE2A_LOCK = "artifacts/current/detector_stage2a/locked/detector_lock.json"


def stage2b_config_paths(root: Path) -> list[Path]:
    root = Path(root).resolve()
    return [
        root / "configs/update/stage2b_common.yaml",
        root / "configs/update/stage2b_quick.yaml",
        root / "configs/update/stage2b_development.yaml",
        root / "configs/update/stage2b_test.yaml",
        root / "configs/update/stage2b_stress.yaml",
        root / "configs/toy_lio/motion_surrogate_stage2b.yaml",
        root / "configs/detector/odi_stage2a.yaml",
    ]


def stage2b_source_paths(root: Path) -> list[Path]:
    root = Path(root).resolve()
    return [
        root / "src/degen_detector",
        root / "src/minibench/map_lio.py",
        root / "src/minibench/update_strategies.py",
        root / "src/minibench/correspondence_stress.py",
        root / "src/minibench/motion_simulator.py",
        root / "src/minibench/observation_simulator.py",
        root / "src/minibench/nested_geometry_observations.py",
        root / "src/minibench/scene_generator.py",
        root / "src/eval/update_metrics.py",
        root / "src/eval/weak_update_stage2b.py",
        root / "src/eval/weak_update_stage2b_lock.py",
        root / "src/eval/synthetic_pipeline_common.py",
        root / "src/eval/hierarchical_statistics.py",
        root / "scripts/31_run_weak_update_stage2b.py",
        root / "scripts/29_run_verified_pytest.py",
        root / "tests",
        *stage2b_config_paths(root),
        root / "pytest.ini",
    ]


def build_update_lock(
    root: Path,
    development_run_dir: Path,
    manifest: Mapping[str, Any],
    threshold: Mapping[str, Any],
    alpha_selection: Sequence[Mapping[str, Any]],
    selected_alpha: float,
    common: Mapping[str, Any],
    motion: Mapping[str, Any],
    stress: Mapping[str, Any],
    development: Mapping[str, Any],
    reserved_test: Mapping[str, Any],
) -> Dict[str, Any]:
    root = Path(root).resolve()
    source_hash, snapshot = compute_source_tree_snapshot(stage2b_source_paths(root))
    stage2a_path = root / STAGE2A_LOCK
    return {
        "stage2a_detector_lock_sha256": sha256_file(stage2a_path),
        "detector_metric_version": str(common["metric_definition_version"]),
        "online_odi_threshold": float(threshold["online_odi_threshold"]),
        "odi_control_quantile": float(common["odi_control_quantile"]),
        "primary_direction_min_eigengap_ratio": float(common["primary_direction_min_eigengap_ratio"]),
        "huber_delta_sigma": float(common["huber_delta_sigma"]),
        "attenuation_alpha_candidates": list(common["attenuation_alpha_candidates"]),
        "selected_attenuation_alpha": float(selected_alpha),
        "alpha_selection_table": [dict(row) for row in alpha_selection],
        "alpha_selection_rule": "feasible maximum severe-slip median axis reduction; ties <1pp choose largest alpha",
        "initial_covariance_diag": list(common["initial_covariance_diag"]),
        "motion_covariance_parameters": dict(motion),
        "stress_parameters": dict(stress),
        "method_list": list(common["method_list"]),
        "primary_baseline": str(common["primary_baseline"]),
        "primary_method": str(common["primary_method"]),
        "oracle_method": str(common["oracle_method"]),
        "development_geometry_seeds": list(development["geometry_seeds"]),
        "development_sensor_seeds": list(development["sensor_seeds"]),
        "development_process_seeds": list(development["process_seeds"]),
        "reserved_test_geometry_seeds": list(reserved_test["geometry_seeds"]),
        "reserved_test_sensor_seeds": list(reserved_test["sensor_seeds"]),
        "reserved_test_process_seeds": list(reserved_test["process_seeds"]),
        "source_tree_sha256": source_hash,
        "source_file_hashes": snapshot,
        "config_bundle_sha256": compute_bundle_hash(stage2b_config_paths(root)),
        "update_code_sha256": compute_source_tree_hash([
            root / "src/minibench/map_lio.py", root / "src/minibench/update_strategies.py",
            root / "src/minibench/correspondence_stress.py",
        ]),
        "statistics_code_sha256": compute_source_tree_hash([
            root / "src/eval/update_metrics.py", root / "src/eval/weak_update_stage2b.py",
        ]),
        "development_data_sha256": compute_directory_hash(root / str(manifest["data_run_dir"])),
        "development_summary_sha256": compute_directory_hash(Path(development_run_dir) / "tables"),
        "git_commit_at_lock": git_commit(root),
        "git_status_clean_at_lock": git_status_clean(root),
        "python_version": sys.version,
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "platform": platform.platform(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def verify_update_lock(root: Path, lock: Mapping[str, Any], require_clean: bool = True) -> Dict[str, Any]:
    root = Path(root).resolve()
    source_hash, snapshot = compute_source_tree_snapshot(stage2b_source_paths(root))
    config_hash = compute_bundle_hash(stage2b_config_paths(root))
    stage2a_hash = sha256_file(root / STAGE2A_LOCK)
    changed = changed_snapshot_files(lock.get("source_file_hashes", {}), snapshot)
    common = _load_yaml(root / "configs/update/stage2b_common.yaml")
    stress = _load_yaml(root / "configs/update/stage2b_stress.yaml")
    development = _load_yaml(root / "configs/update/stage2b_development.yaml")
    reserved = _load_yaml(root / "configs/update/stage2b_test.yaml")
    selected_alpha = float(lock.get("selected_attenuation_alpha", float("nan")))
    candidates = [float(value) for value in common["attenuation_alpha_candidates"]]
    selected_rows = [
        row for row in lock.get("alpha_selection_table", [])
        if str(row.get("selected", "")).strip().lower() in {"true", "1", "yes"}
    ]
    seed_isolation = all(
        not (set(development[field]) & set(reserved[field]))
        for field in ["geometry_seeds", "sensor_seeds", "process_seeds"]
    )
    checks = {
        "source_hash_matched": source_hash == str(lock.get("source_tree_sha256")),
        "config_hash_matched": config_hash == str(lock.get("config_bundle_sha256")),
        "stage2a_detector_artifact_matched": stage2a_hash == str(lock.get("stage2a_detector_lock_sha256")),
        "stress_parameters_matched": stress == lock.get("stress_parameters"),
        "selected_alpha_matched": (
            selected_alpha in candidates
            and len(selected_rows) == 1
            and selected_alpha == float(selected_rows[0]["attenuation_alpha"])
        ),
        "seed_isolation_matched": seed_isolation,
        "git_status_clean": git_status_clean(root),
        "changed_files": changed,
    }
    failures = [
        name
        for name in [
            "source_hash_matched",
            "config_hash_matched",
            "stage2a_detector_artifact_matched",
            "stress_parameters_matched",
            "selected_alpha_matched",
            "seed_isolation_matched",
        ]
        if not checks[name]
    ]
    if require_clean and not checks["git_status_clean"]:
        failures.append("git_status_clean")
    if failures:
        raise RuntimeError(f"REFUSE_TEST_EXECUTION: update lock mismatch {failures}; changed_files={changed}")
    return checks


def validate_seed_isolation(development: Mapping[str, Any], test: Mapping[str, Any]) -> None:
    for field in ["geometry_seeds", "sensor_seeds", "process_seeds"]:
        if set(development[field]) & set(test[field]):
            raise RuntimeError(f"Development/Test {field} overlap")


def validate_reserved_test_seeds(config: Mapping[str, Any], lock: Mapping[str, Any]) -> None:
    for field, lock_field in [
        ("geometry_seeds", "reserved_test_geometry_seeds"),
        ("sensor_seeds", "reserved_test_sensor_seeds"),
        ("process_seeds", "reserved_test_process_seeds"),
    ]:
        if list(config[field]) != list(lock[lock_field]):
            raise RuntimeError(f"REFUSE_TEST_EXECUTION: reserved {field} changed")


def _load_yaml(path: Path) -> Dict[str, Any]:
    """Load lock inputs without importing the evaluation pipeline."""

    import yaml

    with Path(path).open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Stage 2B lock input must be a mapping: {path}")
    # Normalize through JSON so NumPy/YAML scalar subclasses cannot affect
    # equality checks in a lock audit.
    return json.loads(json.dumps(value))
